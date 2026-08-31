"""Atomic PostgreSQL coordinator for the generic D02 admission graph.

The coordinator consumes only already-built, caller-supplied authorities.  It
does not resolve private locators, read image bytes, call a Provider, or open a
network connection.  PostgreSQL claims idempotency and commits the complete
Manifest -> formal source -> screening -> admission graph as one transaction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api import demo_d02_generic_admission as generic
from mirror_api import demo_d02_generic_screening as screening
from mirror_api.demo_d02_source_acquisition import (
    ACQUISITION_EVENT_ID_SCHEMA,
    ACQUISITION_EVENT_SCHEMA,
    ACQUISITION_RUN_SCHEMA,
)
from mirror_api.demo_idempotency import (
    IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD,
    idempotency_key_hash,
)
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest
from mirror_api.demo_models import (
    D02SelectedSourceManifest,
    D02SourceAcquisitionEvent,
    D02SourceAcquisitionRun,
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
    DemoSyntheticIdentity,
)
from mirror_api.models import Asset, AssetVariant, utcnow

_MANIFEST_REPLAY_FIELDS: Final = (
    "schema_version",
    "canonical_payload",
    "content_digest",
    "acquisition_run_id",
    "cohort_spec_id",
    "generation_policy_digest",
    "ordered_candidate_ids",
    "source_count",
    "manifest_state",
)
_ASSET_REQUIRED_FIELDS: Final = frozenset(
    {
        "id",
        "owner_user_id",
        "asset_role",
        "storage_key",
        "mime_type",
        "byte_size",
        "width",
        "height",
        "sha256",
        "synthetic",
        "is_ai_generated",
        "is_ai_modified",
        "internal_purpose",
    }
)
_ASSET_OPTIONAL_FIELDS: Final = frozenset({"created_at", "updated_at", "deleted_at"})
_ASSET_REPLAY_FIELDS: Final = (
    "owner_user_id",
    "asset_role",
    "mime_type",
    "byte_size",
    "width",
    "height",
    "sha256",
    "synthetic",
    "is_ai_generated",
    "is_ai_modified",
    "internal_purpose",
    "deleted_at",
)
_VARIANT_REQUIRED_FIELDS: Final = frozenset(
    {"id", "source_asset_id", "result_asset_id", "variant_type"}
)
_VARIANT_OPTIONAL_FIELDS: Final = frozenset({"created_at"})
_VARIANT_REPLAY_FIELDS: Final = ("source_asset_id", "result_asset_id", "variant_type")


class GenericAdmissionCoordinatorError(RuntimeError):
    """Base fail-closed error for the generic admission transaction."""


class GenericPayloadConflict(GenericAdmissionCoordinatorError):
    code = IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD

    def __init__(self) -> None:
        super().__init__(self.code)


class GenericAuthorityCorruption(GenericAdmissionCoordinatorError):
    """Persisted state does not replay the caller-supplied authority graph."""


@dataclass(frozen=True, slots=True)
class GenericAdmissionBundle:
    request_payload: Mapping[str, object]
    selected_manifest: Mapping[str, object]
    source_inputs: tuple[generic.GenericSourceInput, ...]
    source_rows: tuple[Mapping[str, object], ...]
    identity_rows: tuple[Mapping[str, object], ...]
    asset_rows: tuple[Mapping[str, object], ...]
    asset_variant_rows: tuple[Mapping[str, object], ...]
    report_row: Mapping[str, object]
    question_bank_row: Mapping[str, object]
    question_pair_rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class GenericAdmissionResult:
    admission_id: str
    acquisition_run_id: str
    screening_report_id: str
    question_bank_id: str
    replayed: bool


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise generic.GenericAdmissionError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _parse_datetime(value: object) -> object:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise generic.GenericAdmissionError("created_at must be an ISO-8601 timestamp") from exc
    return value


def _orm_values(model: type[Any], row: Mapping[str, object]) -> dict[str, object]:
    columns = {column.name: column for column in model.__table__.columns}
    values: dict[str, object] = {}
    for key, raw in row.items():
        column = columns.get(key)
        if column is None or column.computed is not None:
            continue
        values[key] = _parse_datetime(raw) if key in {"created_at", "updated_at"} else raw
    return values


def _expected_value(row: Mapping[str, object], field: str) -> object:
    value = row.get(field)
    return _parse_datetime(value) if field in {"created_at", "updated_at"} else value


def _assert_row_fields(
    persisted: object,
    expected: Mapping[str, object],
    *,
    fields: Sequence[str],
    label: str,
) -> None:
    if any(getattr(persisted, field) != _expected_value(expected, field) for field in fields):
        raise GenericAuthorityCorruption(f"persisted {label} authority does not replay")


def _assert_expected_columns(
    persisted: object, expected: Mapping[str, object], *, label: str
) -> None:
    fields = tuple(key for key in expected if hasattr(persisted, key))
    _assert_row_fields(persisted, expected, fields=fields, label=label)


def _validate_selected_manifest(value: Mapping[str, object]) -> None:
    missing = {"id", *_MANIFEST_REPLAY_FIELDS} - set(value)
    if missing:
        raise generic.GenericAdmissionError("selected Manifest projection is incomplete")
    if (
        value.get("schema_version") != "mirror.demo/D02SelectedSourceManifest/v1"
        or value.get("manifest_state") != "FINALIZED"
        or value.get("source_count") != 4
    ):
        raise generic.GenericAdmissionError("selected source Manifest is not finalized")
    candidates = value.get("ordered_candidate_ids")
    if not isinstance(candidates, list) or len(candidates) != 4 or len(set(candidates)) != 4:
        raise generic.GenericAdmissionError("selected source Manifest candidates are invalid")


def _validate_asset_rows(
    rows: Sequence[Mapping[str, object]], *, report: Mapping[str, object]
) -> None:
    payload = _mapping(report.get("report_payload"), "generic Report payload")
    entries = payload.get("asset_authority_manifest")
    if not isinstance(entries, list) or len(entries) != 52 or len(rows) != 52:
        raise generic.GenericAdmissionError("generic admission requires exactly 52 Assets")
    by_id: dict[str, Mapping[str, object]] = {}
    for row in rows:
        keys = set(row)
        if not _ASSET_REQUIRED_FIELDS <= keys or not keys <= (
            _ASSET_REQUIRED_FIELDS | _ASSET_OPTIONAL_FIELDS
        ):
            raise generic.GenericAdmissionError("generic Asset row fields are invalid")
        asset_id = row.get("id")
        if not isinstance(asset_id, str) or asset_id in by_id:
            raise generic.GenericAdmissionError("generic Asset IDs must be unique")
        if (
            row.get("owner_user_id") is not None
            or row.get("asset_role") != "synthetic"
            or row.get("synthetic") is not True
            or row.get("internal_purpose") != "synthetic_dataset"
            or row.get("deleted_at") is not None
            or not isinstance(row.get("storage_key"), str)
            or not cast(str, row["storage_key"])
        ):
            raise generic.GenericAdmissionError("generic Asset scope is invalid")
        by_id[asset_id] = row
    if {
        cast(str, _mapping(entry, "Asset manifest entry").get("asset_id")) for entry in entries
    } != set(by_id):
        raise generic.GenericAdmissionError("Asset rows do not cover the Report manifest")
    for raw_entry in entries:
        entry = _mapping(raw_entry, "Asset manifest entry")
        row = by_id[cast(str, entry["asset_id"])]
        kind = entry.get("asset_kind")
        if (
            (
                kind == "SOURCE"
                and (
                    row.get("is_ai_generated") is not True or row.get("is_ai_modified") is not False
                )
            )
            or (
                kind == "RESULT"
                and (
                    row.get("is_ai_generated") is not False or row.get("is_ai_modified") is not True
                )
            )
            or kind not in {"SOURCE", "RESULT"}
        ):
            raise generic.GenericAdmissionError("generic Asset generation role is invalid")
        expected = screening.build_asset_manifest_entry(
            asset_id=cast(str, row["id"]),
            sha256=cast(str, row["sha256"]),
            byte_size=cast(int, row["byte_size"]),
            mime_type=cast(str, row["mime_type"]),
            width=cast(int, row["width"]),
            height=cast(int, row["height"]),
            asset_kind=kind,
            source_ordinal=cast(int, entry["source_ordinal"]),
            case_ordinal=cast(int | None, entry["case_ordinal"]),
        )
        if dict(entry) != expected:
            raise generic.GenericAdmissionError("Asset row does not replay the Report manifest")


def _validate_variant_rows(
    rows: Sequence[Mapping[str, object]], *, report: Mapping[str, object]
) -> None:
    payload = _mapping(report.get("report_payload"), "generic Report payload")
    entries = payload.get("asset_variant_manifest")
    if not isinstance(entries, list) or len(entries) != 48 or len(rows) != 48:
        raise generic.GenericAdmissionError("generic admission requires exactly 48 AssetVariants")
    by_id: dict[str, Mapping[str, object]] = {}
    for row in rows:
        keys = set(row)
        if not _VARIANT_REQUIRED_FIELDS <= keys or not keys <= (
            _VARIANT_REQUIRED_FIELDS | _VARIANT_OPTIONAL_FIELDS
        ):
            raise generic.GenericAdmissionError("generic AssetVariant row fields are invalid")
        variant_id = row.get("id")
        if not isinstance(variant_id, str) or variant_id in by_id:
            raise generic.GenericAdmissionError("generic AssetVariant IDs must be unique")
        by_id[variant_id] = row
    if {
        cast(str, _mapping(entry, "AssetVariant manifest entry").get("variant_id"))
        for entry in entries
    } != set(by_id):
        raise generic.GenericAdmissionError("AssetVariant rows do not cover the Report manifest")
    for raw_entry in entries:
        entry = _mapping(raw_entry, "AssetVariant manifest entry")
        row = by_id[cast(str, entry["variant_id"])]
        expected = screening.build_variant_manifest_entry(
            variant_id=cast(str, row["id"]),
            source_asset_id=cast(str, row["source_asset_id"]),
            result_asset_id=cast(str, row["result_asset_id"]),
            source_ordinal=cast(int, entry["source_ordinal"]),
            case_ordinal=cast(int, entry["case_ordinal"]),
        )
        if row.get("variant_type") != expected["variant_type"] or dict(entry) != expected:
            raise generic.GenericAdmissionError(
                "AssetVariant row does not replay the Report manifest"
            )


def validate_generic_admission_bundle(
    *, idempotency_key: str, bundle: GenericAdmissionBundle
) -> Mapping[str, object]:
    """Replay the full caller-supplied graph before opening a transaction."""

    _validate_selected_manifest(bundle.selected_manifest)
    _validate_asset_rows(bundle.asset_rows, report=bundle.report_row)
    _validate_variant_rows(bundle.asset_variant_rows, report=bundle.report_row)
    admission = generic.build_generic_admission(
        idempotency_key_hash=idempotency_key_hash(idempotency_key),
        request_payload=bundle.request_payload,
        selected_source_manifest_id=cast(str, bundle.selected_manifest["id"]),
        selected_source_manifest_digest=cast(str, bundle.selected_manifest["content_digest"]),
        formal_source_manifest_digest=cast(str, bundle.report_row["source_manifest_digest"]),
        screening_report_id=cast(str, bundle.report_row["id"]),
        screening_report_digest=cast(str, bundle.report_row["report_digest"]),
        question_bank_id=cast(str, bundle.question_bank_row["id"]),
        question_bank_content_digest=cast(str, bundle.question_bank_row["content_digest"]),
        question_bank_version=cast(str, bundle.question_bank_row["version"]),
        selected_pair_manifest_digest=cast(str, bundle.report_row["selected_pair_manifest_digest"]),
    )
    generic.validate_generic_admission_graph(
        admission,
        idempotency_key_hash=cast(str, admission["idempotency_key_hash"]),
        request_payload=bundle.request_payload,
        selected_manifest=bundle.selected_manifest,
        source_inputs=bundle.source_inputs,
        source_rows=bundle.source_rows,
        identity_rows=bundle.identity_rows,
        report=bundle.report_row,
        bank=bundle.question_bank_row,
        pair_rows=bundle.question_pair_rows,
    )
    return admission


async def _insert_or_replay_rows(
    session: AsyncSession,
    *,
    model: type[Any],
    rows: Sequence[Mapping[str, object]],
    label: str,
    replay_fields: Sequence[str] | None = None,
) -> list[Any]:
    values = [_orm_values(model, row) for row in rows]
    await session.execute(insert(model).values(values).on_conflict_do_nothing())
    return await _load_and_verify_rows(
        session,
        model=model,
        rows=rows,
        label=label,
        replay_fields=replay_fields,
    )


async def _load_and_verify_rows(
    session: AsyncSession,
    *,
    model: type[Any],
    rows: Sequence[Mapping[str, object]],
    label: str,
    replay_fields: Sequence[str] | None = None,
) -> list[Any]:
    ids = [cast(str, row["id"]) for row in rows]
    persisted = list(await session.scalars(select(model).where(model.id.in_(ids))))
    by_id = {cast(str, item.id): item for item in persisted}
    expected_by_id = {cast(str, row["id"]): row for row in rows}
    if set(by_id) != set(expected_by_id):
        raise GenericAuthorityCorruption(f"persisted {label} authority is incomplete")
    for row_id, expected in expected_by_id.items():
        if replay_fields is None:
            _assert_expected_columns(by_id[row_id], expected, label=label)
        else:
            _assert_row_fields(by_id[row_id], expected, fields=replay_fields, label=label)
    return persisted


def _run_payload(run: D02SourceAcquisitionRun) -> dict[str, object]:
    return {
        "cohort_spec_id": run.cohort_spec_id,
        "run_key_digest": run.run_key_digest,
        "run_state": run.run_state,
        "budget_consumed": run.budget_consumed,
        "next_ordinal": run.next_ordinal,
        "open_call_ordinal": run.open_call_ordinal,
        "open_selector_slot_id": run.open_selector_slot_id,
        "accepted_count": run.accepted_count,
        "consecutive_content_rejects": run.consecutive_content_rejects,
        "calls_without_accept": run.calls_without_accept,
        "content_review_epoch": run.content_review_epoch,
        "terminal_reason": run.terminal_reason,
    }


def _seal_run(run: D02SourceAcquisitionRun) -> None:
    payload = _run_payload(run)
    run.canonical_payload = payload
    run.content_digest = mirror_demo_digest(
        ACQUISITION_RUN_SCHEMA, cast(Mapping[str, JsonValue], payload)
    )


async def _append_event(
    session: AsyncSession,
    *,
    run: D02SourceAcquisitionRun,
    event_kind: str,
    evidence_digest: str,
) -> D02SourceAcquisitionEvent:
    last = await session.scalar(
        select(func.max(D02SourceAcquisitionEvent.event_sequence)).where(
            D02SourceAcquisitionEvent.acquisition_run_id == run.id
        )
    )
    event_sequence = int(last or 0) + 1
    payload = {
        "acquisition_run_id": run.id,
        "cohort_spec_id": run.cohort_spec_id,
        "event_sequence": event_sequence,
        "event_kind": event_kind,
        "provider_ordinal": None,
        "selector_slot_id": None,
        "tranche_number": None,
        "candidate_id": None,
        "detail_code": None,
        "evidence_digest": evidence_digest,
        "call_started_event_digest": None,
    }
    content_digest = mirror_demo_digest(
        ACQUISITION_EVENT_SCHEMA, cast(Mapping[str, JsonValue], payload)
    )
    event_id = mirror_demo_digest(
        ACQUISITION_EVENT_ID_SCHEMA,
        {
            "acquisition_run_id": run.id,
            "event_sequence": event_sequence,
            "content_digest": content_digest,
        },
    )[:32]
    event = D02SourceAcquisitionEvent(
        id=event_id,
        schema_version=ACQUISITION_EVENT_SCHEMA,
        canonical_payload=payload,
        content_digest=content_digest,
        created_at=utcnow(),
        **payload,
    )
    session.add(event)
    await session.flush()
    return event


class D02GenericAdmissionCoordinator:
    """Atomically persist or replay one complete generic D02 admission."""

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def admit(
        self, *, idempotency_key: str, bundle: GenericAdmissionBundle
    ) -> GenericAdmissionResult:
        expected = validate_generic_admission_bundle(idempotency_key=idempotency_key, bundle=bundle)
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    manifest = await session.scalar(
                        select(D02SelectedSourceManifest)
                        .where(
                            D02SelectedSourceManifest.id
                            == cast(str, bundle.selected_manifest["id"])
                        )
                        .with_for_update()
                    )
                    if manifest is None:
                        raise GenericAuthorityCorruption(
                            "selected source Manifest is not persisted"
                        )
                    _assert_row_fields(
                        manifest,
                        bundle.selected_manifest,
                        fields=_MANIFEST_REPLAY_FIELDS,
                        label="selected source Manifest",
                    )
                    run = await session.scalar(
                        select(D02SourceAcquisitionRun)
                        .where(D02SourceAcquisitionRun.id == manifest.acquisition_run_id)
                        .with_for_update()
                    )
                    if run is None or run.cohort_spec_id != manifest.cohort_spec_id:
                        raise GenericAuthorityCorruption(
                            "selected source Manifest run is unavailable"
                        )

                    inserted_id = await session.scalar(
                        insert(DemoD02R2Epoch2Admission)
                        .values(**_orm_values(DemoD02R2Epoch2Admission, expected))
                        .on_conflict_do_nothing()
                        .returning(DemoD02R2Epoch2Admission.id)
                    )
                    if inserted_id is None:
                        existing = await session.scalar(
                            select(DemoD02R2Epoch2Admission).where(
                                DemoD02R2Epoch2Admission.idempotency_key_hash
                                == expected["idempotency_key_hash"]
                            )
                        )
                        if existing is None:
                            raise GenericAuthorityCorruption(
                                "selected Manifest already has another admission authority"
                            )
                        if existing.request_digest != expected["request_digest"]:
                            raise GenericPayloadConflict()
                        await self._verify_existing(
                            session, existing=existing, expected=expected, bundle=bundle
                        )
                        return GenericAdmissionResult(
                            admission_id=existing.id,
                            acquisition_run_id=run.id,
                            screening_report_id=existing.screening_report_id,
                            question_bank_id=existing.question_bank_id,
                            replayed=True,
                        )

                    if run.run_state != "MANIFEST_FINALIZED":
                        raise GenericAuthorityCorruption(
                            "new generic admission requires a finalized run"
                        )
                    await _insert_or_replay_rows(
                        session,
                        model=Asset,
                        rows=bundle.asset_rows,
                        label="Asset",
                        replay_fields=_ASSET_REPLAY_FIELDS,
                    )
                    await _insert_or_replay_rows(
                        session,
                        model=AssetVariant,
                        rows=bundle.asset_variant_rows,
                        label="AssetVariant",
                        replay_fields=_VARIANT_REPLAY_FIELDS,
                    )
                    await _insert_or_replay_rows(
                        session,
                        model=DemoD02R2SourceAuthority,
                        rows=bundle.source_rows,
                        label="formal source",
                    )
                    await _insert_or_replay_rows(
                        session,
                        model=DemoSyntheticIdentity,
                        rows=bundle.identity_rows,
                        label="synthetic identity",
                    )
                    formal_digest = cast(str, bundle.report_row["source_manifest_digest"])
                    ready = await session.scalar(
                        select(D02SourceAcquisitionEvent).where(
                            D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                            D02SourceAcquisitionEvent.event_kind == "FORMAL_SOURCES_READY",
                        )
                    )
                    if ready is None:
                        await _append_event(
                            session,
                            run=run,
                            event_kind="FORMAL_SOURCES_READY",
                            evidence_digest=formal_digest,
                        )
                    elif ready.evidence_digest != formal_digest:
                        raise GenericAuthorityCorruption(
                            "formal source readiness evidence does not replay"
                        )

                    await _insert_or_replay_rows(
                        session,
                        model=DemoPairScreeningReport,
                        rows=(bundle.report_row,),
                        label="screening Report",
                    )
                    await _insert_or_replay_rows(
                        session,
                        model=DemoQuestionBank,
                        rows=(bundle.question_bank_row,),
                        label="QuestionBank",
                    )
                    await _insert_or_replay_rows(
                        session,
                        model=DemoQuestionPair,
                        rows=bundle.question_pair_rows,
                        label="QuestionPair",
                    )
                    run.run_state = "ADMITTED"
                    _seal_run(run)
                    await session.flush()
                    await _append_event(
                        session,
                        run=run,
                        event_kind="ADMISSION_COMPLETED",
                        evidence_digest=cast(str, expected["content_digest"]),
                    )
                    admission = await session.get(DemoD02R2Epoch2Admission, inserted_id)
                    if admission is None:
                        raise GenericAuthorityCorruption(
                            "new admission binding disappeared before commit"
                        )
                    await self._verify_existing(
                        session, existing=admission, expected=expected, bundle=bundle
                    )
                    return GenericAdmissionResult(
                        admission_id=admission.id,
                        acquisition_run_id=run.id,
                        screening_report_id=admission.screening_report_id,
                        question_bank_id=admission.question_bank_id,
                        replayed=False,
                    )
        except (
            generic.GenericAdmissionError,
            GenericPayloadConflict,
            GenericAuthorityCorruption,
        ):
            raise
        except SQLAlchemyError as exc:
            raise GenericAuthorityCorruption("generic admission transaction failed") from exc

    async def _verify_existing(
        self,
        session: AsyncSession,
        *,
        existing: DemoD02R2Epoch2Admission,
        expected: Mapping[str, object],
        bundle: GenericAdmissionBundle,
    ) -> None:
        _assert_expected_columns(existing, expected, label="admission")
        run = await session.get(
            D02SourceAcquisitionRun,
            cast(str, bundle.selected_manifest["acquisition_run_id"]),
        )
        if run is None or run.run_state != "ADMITTED":
            raise GenericAuthorityCorruption("persisted acquisition run is not admitted")
        payload = _run_payload(run)
        if run.canonical_payload != payload or run.content_digest != mirror_demo_digest(
            ACQUISITION_RUN_SCHEMA, cast(Mapping[str, JsonValue], payload)
        ):
            raise GenericAuthorityCorruption("persisted acquisition run does not replay")

        await _load_and_verify_rows(
            session,
            model=Asset,
            rows=bundle.asset_rows,
            label="Asset",
            replay_fields=_ASSET_REPLAY_FIELDS,
        )
        await _load_and_verify_rows(
            session,
            model=AssetVariant,
            rows=bundle.asset_variant_rows,
            label="AssetVariant",
            replay_fields=_VARIANT_REPLAY_FIELDS,
        )
        sources = await _load_and_verify_rows(
            session,
            model=DemoD02R2SourceAuthority,
            rows=bundle.source_rows,
            label="formal source",
        )
        await _load_and_verify_rows(
            session,
            model=DemoSyntheticIdentity,
            rows=bundle.identity_rows,
            label="synthetic identity",
        )
        await _load_and_verify_rows(
            session,
            model=DemoPairScreeningReport,
            rows=(bundle.report_row,),
            label="screening Report",
        )
        await _load_and_verify_rows(
            session,
            model=DemoQuestionBank,
            rows=(bundle.question_bank_row,),
            label="QuestionBank",
        )
        pairs = await _load_and_verify_rows(
            session,
            model=DemoQuestionPair,
            rows=bundle.question_pair_rows,
            label="QuestionPair",
        )
        source_count = await session.scalar(
            select(func.count())
            .select_from(DemoD02R2SourceAuthority)
            .where(
                DemoD02R2SourceAuthority.selected_source_manifest_id
                == bundle.selected_manifest["id"],
                DemoD02R2SourceAuthority.schema_version == generic.SOURCE_SCHEMA,
            )
        )
        identity_count = await session.scalar(
            select(func.count())
            .select_from(DemoSyntheticIdentity)
            .where(
                DemoSyntheticIdentity.r2_source_authority_record_id.in_(
                    cast(list[str], [item.id for item in sources])
                ),
                DemoSyntheticIdentity.schema_version == generic.IDENTITY_SCHEMA,
            )
        )
        pair_count = await session.scalar(
            select(func.count())
            .select_from(DemoQuestionPair)
            .where(
                DemoQuestionPair.question_bank_id == bundle.question_bank_row["id"],
                DemoQuestionPair.schema_version == screening.PAIR_SCHEMA,
            )
        )
        if source_count != 4 or identity_count != 4 or pair_count != 16 or len(pairs) != 16:
            raise GenericAuthorityCorruption("persisted admission cardinality is invalid")

        events = list(
            await session.scalars(
                select(D02SourceAcquisitionEvent)
                .where(
                    D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                    D02SourceAcquisitionEvent.event_kind.in_(
                        {"FORMAL_SOURCES_READY", "ADMISSION_COMPLETED"}
                    ),
                )
                .order_by(D02SourceAcquisitionEvent.event_sequence)
            )
        )
        if (
            len(events) != 2
            or events[0].event_kind != "FORMAL_SOURCES_READY"
            or events[0].evidence_digest != bundle.report_row["source_manifest_digest"]
            or events[1].event_kind != "ADMISSION_COMPLETED"
            or events[1].evidence_digest != expected["content_digest"]
        ):
            raise GenericAuthorityCorruption("persisted admission events do not replay")
