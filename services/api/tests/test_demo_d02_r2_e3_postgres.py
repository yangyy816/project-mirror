from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_demo_d02_r2_authority import _packet, _report_input_template
from test_demo_d02_r2_epoch2_admission import (
    _asset_rows,
    _database,
    _variant_rows,
)
from test_demo_d02_r2_schema_authority import _build_r2_bank_and_pairs
from test_demo_d02_r2_screening_execution import _Adapters, _request

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as r2
from mirror_api import demo_d02_r2_e3_admission as e3
from mirror_api import demo_d02_r2_screening_execution as screening
from mirror_api.config import get_settings
from mirror_api.demo_d02_r2_epoch3_generation_receipt import (
    build_epoch3_source_generation_receipt,
)
from mirror_api.demo_d02_r2_generation_e3 import (
    E3_CONTEXT,
    E4_CONTEXT,
    GenerationExecutionContext,
    build_epoch3_allocation,
    build_epoch3_generation_contract,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.demo_models import (
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
    DemoSyntheticIdentity,
)
from mirror_api.models import Asset, AssetVariant


def _digest(marker: str) -> str:
    return hashlib.sha256(marker.encode("utf-8")).hexdigest()


def _policy_review() -> dict[str, object]:
    return {
        "adult_status": "VERIFIED_SYNTHETIC_ADULT",
        "suspected_minor": False,
        "real_person_reference": False,
        "celebrity_resemblance": False,
        "visual_quality": "PASS",
        "anti_homogenization": "PASS",
        "capture_grammar": "PASS",
        "qa_result": "PASS",
        "rejection_reason": None,
    }


@lru_cache(maxsize=2)
def _generation_contract(
    context: GenerationExecutionContext = E3_CONTEXT,
) -> dict[str, object]:
    allocations: list[dict[str, object]] = []
    for ordinal, marker in enumerate("abcd", start=1):
        template = _packet(marker, source_ordinal=ordinal)
        receipt = cast(Mapping[str, object], template["generation_receipt"])
        allocations.append(
            build_epoch3_allocation(
                ordinal=ordinal,
                source_output_id=cast(str, receipt["source_output_id"]),
                provenance_output_id=cast(str, receipt["source_provenance_output_id"]),
                normalized_jpeg_output_id=(
                    f"{context.cohort_label.lower()}-normalized-source-{ordinal}"
                ),
                context=context,
            )
        )
    return build_epoch3_generation_contract(allocations=allocations, context=context)


def _normalized_source(
    *,
    generation_receipt: Mapping[str, object],
    source_sha256: str,
    source_byte_size: int,
    width: int,
    height: int,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> e3.NormalizedSource:
    receipt: dict[str, object] = {
        "schema_version": context.source_normalization_schema,
        "normalization_version": context.source_normalization_version,
        "source_generation_receipt_digest": generation_receipt["receipt_digest"],
        "generation_source_asset_sha256": generation_receipt["source_asset_sha256"],
        "generation_source_asset_byte_size": generation_receipt["source_asset_byte_size"],
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": width,
        "generation_source_asset_height": height,
        "normalized_source_asset_sha256": source_sha256,
        "normalized_source_asset_byte_size": source_byte_size,
        "normalized_source_asset_mime_type": "image/jpeg",
        "normalized_source_asset_width": width,
        "normalized_source_asset_height": height,
        "jpeg_quality": 95,
        "jpeg_subsampling": 0,
        "metadata_policy": "STRIP_ALL",
    }
    receipt["normalization_receipt_digest"] = mirror_demo_digest(
        context.source_normalization_schema,
        cast(Mapping[str, e3.JsonValue], receipt),
    )
    return e3.NormalizedSource(
        jpeg_bytes=b"deterministic-e3-test-only-jpeg-projection",
        sha256=source_sha256,
        byte_size=source_byte_size,
        width=width,
        height=height,
        receipt=cast(Mapping[str, e3.JsonValue], receipt),
    )


def _epoch3_packet(
    marker: str,
    ordinal: int,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> dict[str, object]:
    label = context.cohort_label.lower()
    template = _packet(marker, source_ordinal=ordinal)
    facts = deepcopy(cast(dict[str, object], template["facts"]))
    source_asset_id = cast(
        str,
        cast(Mapping[str, object], template["identity_row"])["formal_canonical_asset_id"],
    )
    generation_receipt = build_epoch3_source_generation_receipt(
        contract=_generation_contract(context),
        ordinal=ordinal,
        root_name_receipt_digest=_digest(f"{label}-root-name"),
        generation_preregistration_digest=_digest(f"{label}-preregistration"),
        source_allocation_manifest_digest=_digest(f"{label}-allocation"),
        source_producer_dispatch_digest=_digest(f"{label}-dispatch"),
        output_name_receipt_digest=_digest(f"{label}-name-{ordinal}"),
        output_seal_receipt_digest=_digest(f"{label}-seal-{ordinal}"),
        registry_commit_receipt_digest=_digest(f"{label}-commit-{ordinal}"),
        generation_capability_authority_digest=_digest(f"{label}-capability"),
        generation_request_digest=_digest(f"{label}-request-{ordinal}"),
        generation_result_provenance_digest=_digest(f"{label}-provenance-{ordinal}"),
        source_provenance_name_receipt_digest=_digest(f"{label}-provenance-name-{ordinal}"),
        source_provenance_seal_receipt_digest=_digest(f"{label}-provenance-seal-{ordinal}"),
        source_provenance_registry_commit_receipt_digest=_digest(
            f"{label}-provenance-commit-{ordinal}"
        ),
        source_asset_sha256=_digest(f"{label}-original-png-{marker}"),
        source_asset_byte_size=cast(int, facts["source_asset_byte_size"]) + ordinal,
        source_asset_width=cast(int, facts["source_asset_width"]),
        source_asset_height=cast(int, facts["source_asset_height"]),
        context=context,
    )
    normalized = _normalized_source(
        generation_receipt=generation_receipt,
        source_sha256=cast(str, facts["source_asset_sha256"]),
        source_byte_size=cast(int, facts["source_asset_byte_size"]),
        width=cast(int, facts["source_asset_width"]),
        height=cast(int, facts["source_asset_height"]),
        context=context,
    )
    authority = e3.build_epoch3_source_authority(
        generation_receipt=generation_receipt,
        normalized_source=normalized,
        source_asset_id=source_asset_id,
        policy_review=_policy_review(),
        context=context,
    )
    qa = e3.build_epoch3_source_qa_snapshot(
        source_authority=authority,
        generation_receipt=generation_receipt,
        qa_policy_digest=_digest(f"{label}-qa-policy-{marker}"),
        decode_record_digest=_digest(f"{label}-decode-{marker}"),
        ordered_review_decision_digests=[
            _digest(f"{label}-review-{marker}-{index}") for index in range(6)
        ],
        context=context,
    )
    supporting = e3.build_epoch3_source_record(
        source_authority=authority,
        source_qa_snapshot=qa,
        generation_receipt=generation_receipt,
        created_at="2026-08-30T00:00:00Z",
        context=context,
    )
    source_key = cast(str, supporting["source_authority_key"])
    facts.update(
        source_output_id=supporting["source_output_id"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
    )
    identity = deepcopy(cast(dict[str, object], template["identity_row"]))
    identity.update(
        formal_canonical_asset_id=supporting["source_asset_id"],
        formal_canonical_asset_sha256=supporting["source_asset_sha256"],
        source_output_id=supporting["source_output_id"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot=facts,
        source_fact_snapshot_digest=r2.digest_r2_facts(facts),
        source_authority_key=source_key,
        r2_source_authority_record_id=supporting["id"],
    )
    identity_canonical = {
        key: value
        for key, value in identity.items()
        if key
        not in {
            "id",
            "schema_version",
            "canonical_payload",
            "content_digest",
            "created_at",
        }
    }
    identity["canonical_payload"] = identity_canonical
    identity["content_digest"] = mirror_demo_digest(
        r2.R2_IDENTITY_SCHEMA,
        cast(Mapping[str, e3.JsonValue], identity_canonical),
    )
    identity["id"] = mirror_demo_digest(
        r2.R2_IDENTITY_ID_DOMAIN,
        {
            "source_authority_kind": r2.R2_SOURCE_AUTHORITY_KIND,
            "source_authority_key": source_key,
            "r2_source_authority_record_id": supporting["id"],
            "admission_sequence": cast(int, identity["admission_sequence"]),
            "admission_action": cast(str, identity["admission_action"]),
            "supersedes_id": cast(str | None, identity["supersedes_id"]),
            "admission_config_digest": cast(str, identity["admission_config_digest"]),
            "canonical_payload_digest": cast(str, identity["content_digest"]),
        },
    )[:32]
    entry = deepcopy(cast(dict[str, object], template["source_manifest_entry"]))
    entry.update(
        source_authority_key=source_key,
        source_admission_event_id=identity["id"],
        source_admission_content_digest=identity["content_digest"],
        source_output_id=supporting["source_output_id"],
        source_asset_id=supporting["source_asset_id"],
        source_asset_sha256=supporting["source_asset_sha256"],
        source_asset_byte_size=supporting["source_asset_byte_size"],
        source_asset_mime_type=supporting["source_asset_mime_type"],
        source_asset_width=supporting["source_asset_width"],
        source_asset_height=supporting["source_asset_height"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot_digest=identity["source_fact_snapshot_digest"],
        r2_source_authority_record_id=supporting["id"],
    )
    entry["record_digest"] = mirror_demo_digest(
        r2.R2_SOURCE_ENTRY_SCHEMA,
        cast(
            Mapping[str, e3.JsonValue],
            {
                key: value
                for key, value in entry.items()
                if key not in {"schema_version", "record_digest"}
            },
        ),
    )
    return {
        "generation_receipt": generation_receipt,
        "source_authority": authority,
        "source_qa_snapshot": qa,
        "supporting_row": supporting,
        "facts": facts,
        "identity_row": identity,
        "source_manifest_entry": entry,
        "source_manifest_digest": _digest(f"pending-{label}-manifest"),
    }


def _epoch3_packets(
    context: GenerationExecutionContext = E3_CONTEXT,
) -> list[dict[str, object]]:
    packets = [
        _epoch3_packet(marker, ordinal, context) for ordinal, marker in enumerate("abcd", start=1)
    ]
    manifest = legacy._sequence_digest(
        r2.R2_SOURCE_MANIFEST_SCHEMA,
        [cast(dict[str, object], packet["source_manifest_entry"]) for packet in packets],
    )
    for packet in packets:
        packet["source_manifest_digest"] = manifest
        e3.validate_epoch3_admission_packet(packet, context=context)
        r2.validate_r2_admission_packet(packet)
    return packets


@lru_cache(maxsize=2)
def _bundle(
    context: GenerationExecutionContext = E3_CONTEXT,
) -> e3.Epoch3AdmissionBundle:
    packets = _epoch3_packets(context)
    fields, _ = _report_input_template()
    report = screening.run_offline_screening(_request(_Adapters(fields), fields, packets))
    bank, pairs = _build_r2_bank_and_pairs(report, packets)
    return e3.Epoch3AdmissionBundle(
        source_packets=tuple(packets),
        asset_rows=_asset_rows(report, packets),
        asset_variant_rows=_variant_rows(report),
        report_row=report,
        question_bank_row=bank,
        question_pair_rows=tuple(pairs),
    )


def test_epoch3_full_graph_replays_and_rejects_pair_substitution() -> None:
    bundle = _bundle()
    e3.validate_epoch3_admission_bundle(bundle)
    assert bundle.report_row["source_m3_repeat_count"] == 12
    assert bundle.report_row["manual_decision_count"] == 48
    assert bundle.report_row["candidate_pair_count"] == 24
    assert len(bundle.question_pair_rows) == 16

    pairs = [dict(row) for row in bundle.question_pair_rows]
    pairs[0]["left_asset_sha256"] = _digest("substituted-result")
    tampered = e3.Epoch3AdmissionBundle(
        source_packets=bundle.source_packets,
        asset_rows=bundle.asset_rows,
        asset_variant_rows=bundle.asset_variant_rows,
        report_row=bundle.report_row,
        question_bank_row=bundle.question_bank_row,
        question_pair_rows=tuple(pairs),
    )
    with pytest.raises(e3.D02R2Epoch3AdmissionError):
        e3.validate_epoch3_admission_bundle(tampered)


async def _count(sessions: async_sessionmaker[AsyncSession], model: type[Any]) -> int:
    async with sessions() as session:
        value = await session.scalar(select(func.count()).select_from(model))
    assert isinstance(value, int)
    return value


@pytest.mark.asyncio
async def test_epoch3_atomic_admission_replay_and_exact_cardinality() -> None:
    bundle = _bundle()
    async with _database() as sessions:
        coordinator = e3.D02R2Epoch3AdmissionCoordinator(session_factory=sessions)
        key = _digest("epoch3-admission-replay")
        first, replay = await asyncio.gather(
            coordinator.admit(idempotency_key=key, bundle=bundle),
            coordinator.admit(idempotency_key=key, bundle=bundle),
        )
        assert {first.replayed, replay.replayed} == {False, True}
        assert first.admission_id == replay.admission_id
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 1
        assert await _count(sessions, DemoD02R2SourceAuthority) == 4
        assert await _count(sessions, DemoSyntheticIdentity) == 4
        assert await _count(sessions, DemoPairScreeningReport) == 1
        assert await _count(sessions, DemoQuestionBank) == 1
        assert await _count(sessions, DemoQuestionPair) == 16
        assert await _count(sessions, Asset) == 52
        assert await _count(sessions, AssetVariant) == 48


@pytest.mark.asyncio
async def test_epoch4_atomic_admission_replay_and_exact_cardinality() -> None:
    bundle = _bundle(E4_CONTEXT)
    e3.validate_epoch3_admission_bundle(bundle, context=E4_CONTEXT)
    async with _database() as sessions:
        coordinator = e3.D02R2Epoch3AdmissionCoordinator(
            session_factory=sessions, context=E4_CONTEXT
        )
        key = _digest("epoch4-admission-replay")
        first, replay = await asyncio.gather(
            coordinator.admit(idempotency_key=key, bundle=bundle),
            coordinator.admit(idempotency_key=key, bundle=bundle),
        )
        assert {first.replayed, replay.replayed} == {False, True}
        assert first.admission_id == replay.admission_id
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 1
        assert await _count(sessions, DemoD02R2SourceAuthority) == 4
        assert await _count(sessions, DemoSyntheticIdentity) == 4
        assert await _count(sessions, DemoPairScreeningReport) == 1
        assert await _count(sessions, DemoQuestionBank) == 1
        assert await _count(sessions, DemoQuestionPair) == 16
        assert await _count(sessions, Asset) == 52
        assert await _count(sessions, AssetVariant) == 48


@pytest.mark.asyncio
async def test_epoch3_mid_transaction_failure_rolls_back_all_rows() -> None:
    bundle = _bundle()
    async with _database() as sessions:
        conflicting = dict(bundle.asset_rows[0])
        conflicting["sha256"] = _digest("preexisting-conflict")
        async with sessions() as session, session.begin():
            await session.execute(
                pg_insert(Asset)
                .values(**conflicting)
                .on_conflict_do_nothing(index_elements=(Asset.id,))
            )
        coordinator = e3.D02R2Epoch3AdmissionCoordinator(session_factory=sessions)
        with pytest.raises(e3.D02R2Epoch3AuthorityCorruption):
            await coordinator.admit(
                idempotency_key=_digest("epoch3-rollback"),
                bundle=bundle,
            )
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 0
        assert await _count(sessions, DemoD02R2SourceAuthority) == 0
        assert await _count(sessions, DemoSyntheticIdentity) == 0
        assert await _count(sessions, DemoPairScreeningReport) == 0
        assert await _count(sessions, DemoQuestionBank) == 0
        assert await _count(sessions, DemoQuestionPair) == 0


@pytest.mark.asyncio
async def test_populated_epoch3_downgrade_fails_closed() -> None:
    bundle = _bundle()
    async with _database() as sessions:
        coordinator = e3.D02R2Epoch3AdmissionCoordinator(session_factory=sessions)
        await coordinator.admit(
            idempotency_key=_digest("epoch3-populated-downgrade"),
            bundle=bundle,
        )
        root = Path(__file__).resolve().parents[3]
        config = Config(root / "services" / "api" / "alembic.ini")
        config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
        get_settings.cache_clear()
        with pytest.raises(DBAPIError, match="Epoch 03 authority exists"):
            await asyncio.to_thread(
                command.downgrade,
                config,
                "demo_0013_d07_publish_auth",
            )
        get_settings.cache_clear()
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 1
