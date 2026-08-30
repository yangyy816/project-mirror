"""D02 autonomous source acquisition state machine and two-copy materialization.

PostgreSQL is the sole budget and business-state authority.  This module does
not persist prompts, private locators, provider payloads, or raw image bytes.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, NoReturn, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mirror_api.demo_d02_r2_generation_receiver import (
    BoundPngFile,
    D02R2PngReceiverError,
    ImageGenResultMaterializer,
    PreallocatedDestination,
    ReceivedPng,
)
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import (
    D02CohortSpec,
    D02SelectedSourceManifest,
    D02SourceAcquisitionEvent,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
)
from mirror_api.models import utcnow

COHORT_SPEC_SCHEMA: Final = "mirror.demo/D02CohortSpec/v1"
COHORT_SPEC_ID_SCHEMA: Final = "mirror.demo/D02CohortSpecId/v1"
ACQUISITION_RUN_SCHEMA: Final = "mirror.demo/D02SourceAcquisitionRun/v1"
ACQUISITION_RUN_ID_SCHEMA: Final = "mirror.demo/D02SourceAcquisitionRunId/v1"
ACQUISITION_EVENT_SCHEMA: Final = "mirror.demo/D02SourceAcquisitionEvent/v1"
ACQUISITION_EVENT_ID_SCHEMA: Final = "mirror.demo/D02SourceAcquisitionEventId/v1"
SOURCE_CANDIDATE_SCHEMA: Final = "mirror.demo/D02SourceCandidate/v1"
SOURCE_CANDIDATE_ID_SCHEMA: Final = "mirror.demo/D02SourceCandidateId/v1"
SELECTED_SOURCE_MANIFEST_SCHEMA: Final = "mirror.demo/D02SelectedSourceManifest/v1"
SELECTED_SOURCE_MANIFEST_ID_SCHEMA: Final = "mirror.demo/D02SelectedSourceManifestId/v1"
D02_GENERATION_POLICY_V1_SCHEMA: Final = "mirror.demo/D02GenerationPolicy/v1"
MATERIALIZER_POLICY_SCHEMA: Final = "mirror.demo/D02MaterializerPolicy/v1"
PROVIDER_RESULT_SCHEMA: Final = "mirror.demo/D02ProviderResultBinding/v1"
SOURCE_OUTPUT_ID_SCHEMA: Final = "mirror.demo/D02SourceOutputId/v1"

TOTAL_BUDGET: Final = 50
TRANCHE_SIZE: Final = 10
CONCURRENCY: Final = 1
SAME_ORDINAL_RETRY: Final = 0
TARGET_SOURCE_COUNT: Final = 4
OUTPUTS_PER_CALL: Final = 1
CONTENT_REJECT_PAUSE_THRESHOLD: Final = 5
CALLS_WITHOUT_ACCEPT_PAUSE_THRESHOLD: Final = 10

_DIGEST = re.compile(r"[0-9a-f]{64}$")
_OUTPUT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CALL_AUTHORIZATION_FACTORY_TOKEN: Final = object()
_PRIMARY_RECOVERY_AUTHORIZATION_FACTORY_TOKEN: Final = object()
_DURABLE_CANDIDATE_FACTORY_TOKEN: Final = object()
_PRIMARY_MATERIALIZATION_FACTORY_TOKEN: Final = object()

type RunState = Literal[
    "ACTIVE",
    "PAUSED_INFRASTRUCTURE",
    "PAUSED_CONTENT_REVIEW",
    "MANIFEST_FINALIZED",
    "ADMITTED",
    "FAILED_CLOSED",
]


class D02SourceAcquisitionError(RuntimeError):
    """A fail-closed acquisition precondition or state transition failed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class D02TwoCopyStorageError(RuntimeError):
    """Two-copy persistence failed without exposing a private locator."""

    def __init__(
        self,
        code: str,
        *,
        durable_candidate: DurableCandidateBytes | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.durable_candidate = durable_candidate

    @property
    def primary_persisted(self) -> bool:
        return self.durable_candidate is not None


@dataclass(frozen=True, slots=True)
class SelectorSlot:
    slot_id: str
    declared_age_band: Literal["ADULT_18_19", "ADULT_20_25"]
    style_context: str


SELECTOR_SLOTS: Final[tuple[SelectorSlot, ...]] = (
    SelectorSlot("D02_SLOT_01", "ADULT_20_25", "CLEAR_NATURAL"),
    SelectorSlot("D02_SLOT_02", "ADULT_20_25", "REFINED_COOL"),
    SelectorSlot("D02_SLOT_03", "ADULT_20_25", "GENTLE_SWEET"),
    SelectorSlot("D02_SLOT_04", "ADULT_18_19", "FRESH_NATURAL"),
)


def generation_policy_v1_payload() -> dict[str, object]:
    return {
        "schema_version": D02_GENERATION_POLICY_V1_SCHEMA,
        "selector_slots": [
            {
                "slot_id": slot.slot_id,
                "declared_age_band": slot.declared_age_band,
                "style_context": slot.style_context,
            }
            for slot in SELECTOR_SLOTS
        ],
        "selection_order": [slot.slot_id for slot in SELECTOR_SLOTS],
        "synthetic_only_required": True,
        "adult_status_required": "VERIFIED_SYNTHETIC_ADULT",
        "allowed_age_bands": ["ADULT_18_19", "ADULT_20_25"],
        "suspected_minor_required": False,
        "real_person_reference_forbidden": True,
        "unique_identity_family_required": True,
        "style_and_anti_homogenization_enforcement": "APPLICATION_SERVICE_AND_TESTS",
    }


D02_GENERATION_POLICY_V1_DIGEST: Final = hashlib.sha256(
    D02_GENERATION_POLICY_V1_SCHEMA.encode("utf-8")
    + b"\n"
    + canonical_json_bytes(generation_policy_v1_payload())
).hexdigest()

MATERIALIZER_POLICY_PAYLOAD: Final[dict[str, object]] = {
    "schema_version": MATERIALIZER_POLICY_SCHEMA,
    "typed_image_reference_count": 1,
    "cli_input": "NON_TTY_STDIN_ONLY",
    "output_hint_authority": False,
    "local_file_binding": "LEXICAL_RESOLVED_NO_FOLLOW_REGULAR_DESCRIPTOR_IDENTITY",
    "two_copy_storage": "AVAILABILITY_MEASURE_NOT_AUTHORITY_CHAIN",
}
MATERIALIZER_POLICY_DIGEST: Final = hashlib.sha256(
    MATERIALIZER_POLICY_SCHEMA.encode("utf-8")
    + b"\n"
    + canonical_json_bytes(MATERIALIZER_POLICY_PAYLOAD)
).hexdigest()


@dataclass(frozen=True, slots=True)
class D02SpecIdentity:
    provider_identity_digest: str
    runtime_identity_digest: str
    model_identity_digest: str
    m3_prescreen_policy_digest: str
    qa_policy_digest: str
    provider_interface: str = "image_gen.imagegen"
    materializer_version: str = "d02-imagegen-materializer-v2"


@dataclass(frozen=True, slots=True, init=False)
class CallAuthorization:
    run_id: str
    cohort_spec_id: str
    provider_ordinal: int
    selector_slot: SelectorSlot
    tranche_number: int
    call_started_event_digest: str

    def __init__(
        self,
        *,
        run_id: str,
        cohort_spec_id: str,
        provider_ordinal: int,
        selector_slot: SelectorSlot,
        tranche_number: int,
        call_started_event_digest: str,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _CALL_AUTHORIZATION_FACTORY_TOKEN:
            raise TypeError("CallAuthorization must be issued by the acquisition service")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "cohort_spec_id", cohort_spec_id)
        object.__setattr__(self, "provider_ordinal", provider_ordinal)
        object.__setattr__(self, "selector_slot", selector_slot)
        object.__setattr__(self, "tranche_number", tranche_number)
        object.__setattr__(self, "call_started_event_digest", call_started_event_digest)


@dataclass(frozen=True, slots=True, init=False)
class PrimaryRecoveryAuthorization:
    """Recovery-only binding for exact primary bytes already published before a crash."""

    run_id: str
    cohort_spec_id: str
    provider_ordinal: int
    selector_slot: SelectorSlot
    tranche_number: int
    call_started_event_digest: str

    def __init__(
        self,
        *,
        run_id: str,
        cohort_spec_id: str,
        provider_ordinal: int,
        selector_slot: SelectorSlot,
        tranche_number: int,
        call_started_event_digest: str,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _PRIMARY_RECOVERY_AUTHORIZATION_FACTORY_TOKEN:
            raise TypeError(
                "PrimaryRecoveryAuthorization must be issued by the acquisition service"
            )
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "cohort_spec_id", cohort_spec_id)
        object.__setattr__(self, "provider_ordinal", provider_ordinal)
        object.__setattr__(self, "selector_slot", selector_slot)
        object.__setattr__(self, "tranche_number", tranche_number)
        object.__setattr__(self, "call_started_event_digest", call_started_event_digest)


@dataclass(frozen=True, slots=True, init=False)
class DurableCandidateBytes:
    run_id: str
    cohort_spec_id: str
    provider_ordinal: int
    selector_slot_id: str
    call_started_event_digest: str
    output_id: str
    provider_result_digest: str
    media_type: Literal["image/png"]
    byte_size: int
    primary_sha256: str
    backup_sha256: str | None
    width: int
    height: int

    def __init__(
        self,
        *,
        run_id: str,
        cohort_spec_id: str,
        provider_ordinal: int,
        selector_slot_id: str,
        call_started_event_digest: str,
        output_id: str,
        provider_result_digest: str,
        media_type: Literal["image/png"],
        byte_size: int,
        primary_sha256: str,
        backup_sha256: str | None,
        width: int,
        height: int,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _DURABLE_CANDIDATE_FACTORY_TOKEN:
            raise TypeError("DurableCandidateBytes must be issued by D02 two-copy storage")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "cohort_spec_id", cohort_spec_id)
        object.__setattr__(self, "provider_ordinal", provider_ordinal)
        object.__setattr__(self, "selector_slot_id", selector_slot_id)
        object.__setattr__(self, "call_started_event_digest", call_started_event_digest)
        object.__setattr__(self, "output_id", output_id)
        object.__setattr__(self, "provider_result_digest", provider_result_digest)
        object.__setattr__(self, "media_type", media_type)
        object.__setattr__(self, "byte_size", byte_size)
        object.__setattr__(self, "primary_sha256", primary_sha256)
        object.__setattr__(self, "backup_sha256", backup_sha256)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, init=False)
class DurablePrimaryMaterialization:
    """Primary bytes plus the exact no-follow file capability that published them."""

    candidate: DurableCandidateBytes
    primary_file: BoundPngFile

    def __init__(
        self,
        *,
        candidate: DurableCandidateBytes,
        primary_file: BoundPngFile,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _PRIMARY_MATERIALIZATION_FACTORY_TOKEN:
            raise TypeError("DurablePrimaryMaterialization must be issued by D02 storage")
        if candidate.backup_sha256 is not None:
            raise TypeError("primary materialization cannot already contain a backup")
        object.__setattr__(self, "candidate", candidate)
        object.__setattr__(self, "primary_file", primary_file)


class D02TwoCopyStorage:
    """Persist/re-read primary and backup bytes without creating receipt chains."""

    def persist_primary_png(
        self,
        *,
        authorization: CallAuthorization,
        result_metadata: object,
        primary_destination: PreallocatedDestination,
        allowed_saved_file: Path | None = None,
    ) -> DurablePrimaryMaterialization:
        """Publish and bind primary bytes before any backup attempt.

        The caller must persist ``candidate`` in PostgreSQL and commit that
        primary-stage projection before requesting a backup.  This ordering
        leaves a recoverable open call if the process stops between file
        publication and Candidate persistence.
        """

        if type(authorization) is not CallAuthorization:
            raise D02TwoCopyStorageError("CALL_AUTHORIZATION_INVALID")
        try:
            primary = ImageGenResultMaterializer().receive(
                result_metadata=result_metadata,
                destination=primary_destination,
                allowed_saved_file=allowed_saved_file,
            )
        except D02R2PngReceiverError as error:
            raise D02TwoCopyStorageError("PRIMARY_STORAGE_FAILED") from error
        except Exception as error:
            raise D02TwoCopyStorageError("PRIMARY_STORAGE_INTERNAL_FAILURE") from error
        candidate = _issue_durable_candidate(
            authorization=authorization,
            primary=primary,
            backup=None,
        )
        try:
            primary_file = primary_destination.bind_published_png(expected=primary)
        except D02R2PngReceiverError as error:
            raise D02TwoCopyStorageError(
                "PRIMARY_BINDING_FAILED",
                durable_candidate=candidate,
            ) from error
        return DurablePrimaryMaterialization(
            candidate=candidate,
            primary_file=primary_file,
            _factory_token=_PRIMARY_MATERIALIZATION_FACTORY_TOKEN,
        )

    def recover_primary_png(
        self,
        *,
        authorization: PrimaryRecoveryAuthorization,
        primary_file: BoundPngFile,
    ) -> DurablePrimaryMaterialization:
        """Replay an exact private-index file for an existing open CALL_STARTED."""

        if type(authorization) is not PrimaryRecoveryAuthorization:
            raise D02TwoCopyStorageError("PRIMARY_RECOVERY_AUTHORIZATION_INVALID")
        try:
            primary = primary_file.validate()
        except D02R2PngReceiverError as error:
            raise D02TwoCopyStorageError("PRIMARY_RECOVERY_FAILED") from error
        candidate = _issue_durable_candidate(
            authorization=authorization,
            primary=primary,
            backup=None,
        )
        return DurablePrimaryMaterialization(
            candidate=candidate,
            primary_file=primary_file,
            _factory_token=_PRIMARY_MATERIALIZATION_FACTORY_TOKEN,
        )

    def repair_backup(
        self,
        *,
        primary: DurableCandidateBytes,
        primary_file: BoundPngFile,
        backup_destination: PreallocatedDestination,
    ) -> DurableCandidateBytes:
        """Re-read an already durable primary and create the missing backup."""

        if primary.backup_sha256 is not None:
            _fail("BACKUP_ALREADY_RECONCILED")
        try:
            backup = primary_file.copy_create_new(destination=backup_destination)
        except D02R2PngReceiverError as error:
            raise D02TwoCopyStorageError(
                "BACKUP_STORAGE_FAILED",
                durable_candidate=primary,
            ) from error
        except Exception as error:
            raise D02TwoCopyStorageError(
                "BACKUP_STORAGE_INTERNAL_FAILURE",
                durable_candidate=primary,
            ) from error
        if (
            primary.primary_sha256 != backup.sha256
            or primary.byte_size != backup.byte_size
            or primary.width != backup.width
            or primary.height != backup.height
        ):
            raise D02TwoCopyStorageError(
                "TWO_COPY_DIGEST_MISMATCH",
                durable_candidate=primary,
            )
        return DurableCandidateBytes(
            run_id=primary.run_id,
            cohort_spec_id=primary.cohort_spec_id,
            provider_ordinal=primary.provider_ordinal,
            selector_slot_id=primary.selector_slot_id,
            call_started_event_digest=primary.call_started_event_digest,
            output_id=primary.output_id,
            provider_result_digest=primary.provider_result_digest,
            media_type=primary.media_type,
            byte_size=primary.byte_size,
            primary_sha256=primary.primary_sha256,
            backup_sha256=backup.sha256,
            width=primary.width,
            height=primary.height,
            _factory_token=_DURABLE_CANDIDATE_FACTORY_TOKEN,
        )


class D02SourceAcquisitionService:
    """Serialized transactional projection writer for the D02 acquisition ledger."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def register_spec(self, identity: D02SpecIdentity) -> D02CohortSpec:
        for name in (
            "provider_identity_digest",
            "runtime_identity_digest",
            "model_identity_digest",
            "m3_prescreen_policy_digest",
            "qa_policy_digest",
        ):
            _require_digest(cast(str, getattr(identity, name)), name)
        if not identity.provider_interface or not identity.materializer_version:
            _fail("INVALID_SPEC_IDENTITY")
        payload = {
            "generation_policy_version": "D02_GENERATION_POLICY_V1",
            "generation_policy_digest": D02_GENERATION_POLICY_V1_DIGEST,
            "provider_interface": identity.provider_interface,
            "provider_identity_digest": identity.provider_identity_digest,
            "runtime_identity_digest": identity.runtime_identity_digest,
            "model_identity_digest": identity.model_identity_digest,
            "materializer_version": identity.materializer_version,
            "materializer_policy_digest": MATERIALIZER_POLICY_DIGEST,
            "m3_prescreen_policy_digest": identity.m3_prescreen_policy_digest,
            "qa_policy_digest": identity.qa_policy_digest,
            "total_budget": TOTAL_BUDGET,
            "tranche_size": TRANCHE_SIZE,
            "concurrency": CONCURRENCY,
            "same_ordinal_retry": SAME_ORDINAL_RETRY,
            "target_source_count": TARGET_SOURCE_COUNT,
            "outputs_per_call": OUTPUTS_PER_CALL,
            "spec_state": "REGISTERED",
        }
        content_digest = _digest(COHORT_SPEC_SCHEMA, payload)
        spec_id = _identifier(COHORT_SPEC_ID_SCHEMA, {"content_digest": content_digest})
        self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended("mirror.demo/D02AutonomyBootstrapSpecSingleton/v1", 0)
                )
            )
        )
        existing = self._session.scalar(select(D02CohortSpec).with_for_update())
        if existing is not None:
            if existing.id != spec_id or existing.content_digest != content_digest:
                _fail("COHORT_SPEC_SINGLETON_COLLISION")
            return existing
        row = D02CohortSpec(
            id=spec_id,
            schema_version=COHORT_SPEC_SCHEMA,
            canonical_payload=payload,
            content_digest=content_digest,
            created_at=utcnow(),
            **payload,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def create_run(self, *, cohort_spec_id: str, run_key_digest: str) -> D02SourceAcquisitionRun:
        _require_digest(run_key_digest, "run_key_digest")
        spec = self._session.scalar(
            select(D02CohortSpec).where(D02CohortSpec.id == cohort_spec_id).with_for_update()
        )
        if spec is None or spec.schema_version != COHORT_SPEC_SCHEMA:
            _fail("UNKNOWN_COHORT_SPEC")
        run_id = _identifier(
            ACQUISITION_RUN_ID_SCHEMA,
            {"cohort_spec_id": cohort_spec_id, "run_key_digest": run_key_digest},
        )
        existing = self._session.scalar(select(D02SourceAcquisitionRun).with_for_update())
        if existing is not None:
            if (
                existing.id != run_id
                or existing.cohort_spec_id != cohort_spec_id
                or existing.run_key_digest != run_key_digest
            ):
                _fail("ACQUISITION_RUN_SINGLETON_COLLISION")
            return existing
        row = D02SourceAcquisitionRun(
            id=run_id,
            schema_version=ACQUISITION_RUN_SCHEMA,
            canonical_payload={},
            content_digest="0" * 64,
            created_at=utcnow(),
            cohort_spec_id=cohort_spec_id,
            run_key_digest=run_key_digest,
            run_state="ACTIVE",
            budget_consumed=0,
            next_ordinal=1,
            open_call_ordinal=None,
            open_selector_slot_id=None,
            accepted_count=0,
            consecutive_content_rejects=0,
            calls_without_accept=0,
            content_review_epoch=0,
            terminal_reason=None,
        )
        _seal_run(row)
        self._session.add(row)
        self._session.flush()
        self._append_event(row, event_kind="RUN_CREATED")
        return row

    def start_call(self, *, run_id: str) -> CallAuthorization:
        run = self._lock_run(run_id)
        if run.run_state != "ACTIVE" or run.open_call_ordinal is not None:
            _fail("CALL_NOT_AUTHORIZED_IN_CURRENT_STATE")
        incomplete_candidate = self._session.scalar(
            select(D02SourceCandidate.id).where(
                D02SourceCandidate.acquisition_run_id == run.id,
                D02SourceCandidate.candidate_state.in_(
                    {"PRIMARY_DURABLE", "DURABLE", "M3_SUPPORTED"}
                ),
            )
        )
        if incomplete_candidate is not None:
            _fail("CANDIDATE_PROCESSING_INCOMPLETE")
        if run.accepted_count >= TARGET_SOURCE_COUNT:
            _fail("TARGET_ALREADY_REACHED")
        if run.budget_consumed >= TOTAL_BUDGET:
            self._fail_budget_exhausted(run)
            _fail("CALL_BUDGET_EXHAUSTED")
        if run.next_ordinal > 1 and (run.next_ordinal - 1) % TRANCHE_SIZE == 0:
            previous_tranche = (run.next_ordinal - 1) // TRANCHE_SIZE
            reconciled = self._session.scalar(
                select(D02SourceAcquisitionEvent.id).where(
                    D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                    D02SourceAcquisitionEvent.event_kind == "TRANCHE_RECONCILED",
                    D02SourceAcquisitionEvent.tranche_number == previous_tranche,
                )
            )
            if reconciled is None:
                _fail("PREVIOUS_TRANCHE_NOT_RECONCILED")
        slot = self._next_selector_slot(run)
        ordinal = run.next_ordinal
        run.budget_consumed += 1
        run.next_ordinal += 1
        run.open_call_ordinal = ordinal
        run.open_selector_slot_id = slot.slot_id
        run.calls_without_accept += 1
        _seal_run(run)
        event = self._append_event(
            run,
            event_kind="CALL_STARTED",
            provider_ordinal=ordinal,
            selector_slot_id=slot.slot_id,
        )
        return CallAuthorization(
            run_id=run.id,
            cohort_spec_id=run.cohort_spec_id,
            provider_ordinal=ordinal,
            selector_slot=slot,
            tranche_number=((ordinal - 1) // TRANCHE_SIZE) + 1,
            call_started_event_digest=event.content_digest,
            _factory_token=_CALL_AUTHORIZATION_FACTORY_TOKEN,
        )

    def authorize_primary_recovery(
        self,
        *,
        run_id: str,
        call_started_event_digest: str,
    ) -> PrimaryRecoveryAuthorization:
        """Issue a recovery-only capability for exact primary bytes already published.

        This token cannot be used by ``persist_primary_png`` or any Provider
        dispatch path.  The caller must also present the exact ``BoundPngFile``
        from the private checkpoint to ``recover_primary_png``.
        """

        run, slot_id = self._require_open_call_recovery(
            run_id=run_id,
            call_started_event_digest=call_started_event_digest,
        )
        assert run.open_call_ordinal is not None
        return PrimaryRecoveryAuthorization(
            run_id=run.id,
            cohort_spec_id=run.cohort_spec_id,
            provider_ordinal=run.open_call_ordinal,
            selector_slot=_slot(slot_id),
            tranche_number=((run.open_call_ordinal - 1) // TRANCHE_SIZE) + 1,
            call_started_event_digest=call_started_event_digest,
            _factory_token=_PRIMARY_RECOVERY_AUTHORIZATION_FACTORY_TOKEN,
        )

    def fail_open_call_as_provider_outcome_uncertain(
        self,
        *,
        run_id: str,
        call_started_event_digest: str,
    ) -> None:
        """Fail closed after restart when the Provider outcome is unknowable."""

        run, slot_id = self._require_open_call_recovery(
            run_id=run_id,
            call_started_event_digest=call_started_event_digest,
        )
        assert run.open_call_ordinal is not None
        ordinal = run.open_call_ordinal
        self._append_event(
            run,
            event_kind="PROVIDER_OUTCOME_UNCERTAIN",
            provider_ordinal=ordinal,
            selector_slot_id=slot_id,
            detail_code="PROVIDER_OUTCOME_UNCERTAIN",
            call_started_event_digest=call_started_event_digest,
        )
        self._close_open_call(run)
        self._fail_run(run, "PROVIDER_OUTCOME_UNCERTAIN")

    def record_call_consumed_no_result(
        self, *, authorization: CallAuthorization, detail_code: str
    ) -> None:
        run, slot_id = self._require_open_authorization(authorization)
        _require_code(detail_code)
        self._append_event(
            run,
            event_kind="CALL_CONSUMED_NO_RESULT",
            provider_ordinal=authorization.provider_ordinal,
            selector_slot_id=slot_id,
            detail_code=detail_code,
            call_started_event_digest=authorization.call_started_event_digest,
        )
        self._close_open_call(run)
        self._post_unsuccessful_outcome(run)

    def record_provider_outcome_uncertain(self, *, authorization: CallAuthorization) -> None:
        run, slot_id = self._require_open_authorization(authorization)
        self._append_event(
            run,
            event_kind="PROVIDER_OUTCOME_UNCERTAIN",
            provider_ordinal=authorization.provider_ordinal,
            selector_slot_id=slot_id,
            detail_code="PROVIDER_OUTCOME_UNCERTAIN",
            call_started_event_digest=authorization.call_started_event_digest,
        )
        self._close_open_call(run)
        self._fail_run(run, "PROVIDER_OUTCOME_UNCERTAIN")

    def record_materialization_failed(
        self, *, authorization: CallAuthorization, detail_code: str
    ) -> None:
        """Use only when no provider bytes reached durable storage."""

        run, slot_id = self._require_open_authorization(authorization)
        _require_code(detail_code)
        self._append_event(
            run,
            event_kind="MATERIALIZATION_FAILED",
            provider_ordinal=authorization.provider_ordinal,
            selector_slot_id=slot_id,
            detail_code=detail_code,
            call_started_event_digest=authorization.call_started_event_digest,
        )
        self._close_open_call(run)
        if run.budget_consumed >= TOTAL_BUDGET:
            self._fail_budget_exhausted(run)
            return
        self._pause_infrastructure(
            run,
            detail_code=detail_code,
            provider_ordinal=authorization.provider_ordinal,
            selector_slot_id=slot_id,
            call_started_event_digest=authorization.call_started_event_digest,
        )

    def record_materialized_candidate(
        self,
        *,
        candidate: DurableCandidateBytes,
    ) -> D02SourceCandidate:
        run, slot_id = self._require_open_materialization(candidate)
        if _OUTPUT_ID.fullmatch(candidate.output_id) is None:
            _fail("INVALID_OUTPUT_ID")
        for name, value in (
            ("provider_result_digest", candidate.provider_result_digest),
            ("primary_sha256", candidate.primary_sha256),
            ("call_started_event_digest", candidate.call_started_event_digest),
        ):
            _require_digest(value, name)
        if (
            candidate.byte_size <= 0
            or candidate.width <= 0
            or candidate.height <= 0
            or candidate.media_type != "image/png"
        ):
            _fail("DURABLE_BYTES_INVALID")
        if candidate.backup_sha256 is not None:
            _require_digest(candidate.backup_sha256, "backup_sha256")
            if candidate.primary_sha256 != candidate.backup_sha256:
                _fail("DURABLE_BYTES_NOT_RECONCILED")
        slot = _slot(slot_id)
        candidate_id = _identifier(
            SOURCE_CANDIDATE_ID_SCHEMA,
            {
                "acquisition_run_id": run.id,
                "provider_ordinal": candidate.provider_ordinal,
                "output_id": candidate.output_id,
                "durable_sha256": candidate.primary_sha256,
            },
        )
        row = D02SourceCandidate(
            id=candidate_id,
            schema_version=SOURCE_CANDIDATE_SCHEMA,
            canonical_payload={},
            content_digest="0" * 64,
            created_at=utcnow(),
            acquisition_run_id=run.id,
            cohort_spec_id=run.cohort_spec_id,
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=slot.slot_id,
            call_started_event_digest=candidate.call_started_event_digest,
            output_id=candidate.output_id,
            provider_result_digest=candidate.provider_result_digest,
            durable_primary_sha256=candidate.primary_sha256,
            durable_backup_sha256=candidate.backup_sha256,
            durable_byte_size=candidate.byte_size,
            durable_media_type=candidate.media_type,
            durable_width=candidate.width,
            durable_height=candidate.height,
            candidate_state=(
                "DURABLE" if candidate.backup_sha256 is not None else "PRIMARY_DURABLE"
            ),
            m3_state="PENDING",
            m3_evidence_digest=None,
            qa_state="PENDING",
            qa_evidence_digest=None,
            adult_status="UNVERIFIED",
            declared_age_band=slot.declared_age_band,
            suspected_minor=None,
            synthetic_only_attested=True,
            real_person_reference_used=False,
            identity_family_digest=None,
            rejection_code=None,
        )
        _seal_candidate(row)
        self._session.add(row)
        self._session.flush()
        self._append_event(
            run,
            event_kind=(
                "CANDIDATE_DURABLE"
                if candidate.backup_sha256 is not None
                else "CANDIDATE_PRIMARY_DURABLE"
            ),
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=slot.slot_id,
            candidate_id=row.id,
            evidence_digest=row.content_digest,
            call_started_event_digest=candidate.call_started_event_digest,
        )
        self._close_open_call(run)
        if candidate.backup_sha256 is None:
            self._pause_infrastructure(
                run,
                detail_code="BACKUP_STORAGE_INCOMPLETE",
                candidate_id=row.id,
                provider_ordinal=row.provider_ordinal,
                selector_slot_id=row.selector_slot_id,
                call_started_event_digest=row.call_started_event_digest,
            )
        return row

    def authorize_backup_repair(self, *, candidate_id: str) -> DurableCandidateBytes:
        """Re-issue typed primary facts from PostgreSQL for a same-candidate repair."""

        candidate, run = self._lock_candidate_and_run(candidate_id)
        if (
            run.run_state != "PAUSED_INFRASTRUCTURE"
            or candidate.candidate_state != "PRIMARY_DURABLE"
            or candidate.durable_backup_sha256 is not None
        ):
            _fail("BACKUP_REPAIR_NOT_AUTHORIZED")
        self._require_call_binding(
            run=run,
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            call_started_event_digest=candidate.call_started_event_digest,
        )
        return DurableCandidateBytes(
            run_id=run.id,
            cohort_spec_id=run.cohort_spec_id,
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            call_started_event_digest=candidate.call_started_event_digest,
            output_id=candidate.output_id,
            provider_result_digest=candidate.provider_result_digest,
            media_type=cast(Literal["image/png"], candidate.durable_media_type),
            byte_size=candidate.durable_byte_size,
            primary_sha256=candidate.durable_primary_sha256,
            backup_sha256=None,
            width=candidate.durable_width,
            height=candidate.durable_height,
            _factory_token=_DURABLE_CANDIDATE_FACTORY_TOKEN,
        )

    def record_backup_reconciled(
        self,
        *,
        candidate: DurableCandidateBytes,
        recovery_digest: str,
    ) -> D02SourceCandidate:
        _require_digest(recovery_digest, "recovery_digest")
        if candidate.backup_sha256 is None:
            _fail("BACKUP_NOT_RECONCILED")
        candidate_id = _identifier(
            SOURCE_CANDIDATE_ID_SCHEMA,
            {
                "acquisition_run_id": candidate.run_id,
                "provider_ordinal": candidate.provider_ordinal,
                "output_id": candidate.output_id,
                "durable_sha256": candidate.primary_sha256,
            },
        )
        row, run = self._lock_candidate_and_run(candidate_id)
        if (
            run.run_state != "PAUSED_INFRASTRUCTURE"
            or row.candidate_state != "PRIMARY_DURABLE"
            or row.durable_backup_sha256 is not None
        ):
            _fail("BACKUP_RECONCILIATION_TRANSITION_INVALID")
        self._require_materialization_matches_candidate(candidate, row)
        if candidate.backup_sha256 != row.durable_primary_sha256:
            _fail("DURABLE_BYTES_NOT_RECONCILED")
        row.durable_backup_sha256 = candidate.backup_sha256
        row.candidate_state = "DURABLE"
        _seal_candidate(row)
        self._append_event(
            run,
            event_kind="CANDIDATE_DURABLE",
            provider_ordinal=row.provider_ordinal,
            selector_slot_id=row.selector_slot_id,
            candidate_id=row.id,
            evidence_digest=row.content_digest,
            call_started_event_digest=row.call_started_event_digest,
        )
        run.run_state = "ACTIVE"
        _seal_run(run)
        self._append_event(
            run,
            event_kind="INFRASTRUCTURE_RESUMED",
            provider_ordinal=row.provider_ordinal,
            selector_slot_id=row.selector_slot_id,
            candidate_id=row.id,
            evidence_digest=recovery_digest,
            call_started_event_digest=row.call_started_event_digest,
        )
        return row

    def reconcile_tranche(
        self,
        *,
        run_id: str,
        tranche_number: int,
        reconciliation_digest: str,
    ) -> None:
        _require_digest(reconciliation_digest, "reconciliation_digest")
        if tranche_number not in range(1, (TOTAL_BUDGET // TRANCHE_SIZE) + 1):
            _fail("INVALID_TRANCHE_NUMBER")
        run = self._lock_run(run_id)
        if run.run_state not in {"ACTIVE", "PAUSED_CONTENT_REVIEW"}:
            _fail("TRANCHE_RECONCILIATION_NOT_AUTHORIZED")
        tranche_end = tranche_number * TRANCHE_SIZE
        if run.open_call_ordinal is not None or run.budget_consumed != tranche_end:
            _fail("TRANCHE_NOT_COMPLETE")
        tranche_start = tranche_end - TRANCHE_SIZE + 1
        started_ordinals = set(
            self._session.scalars(
                select(D02SourceAcquisitionEvent.provider_ordinal).where(
                    D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                    D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
                    D02SourceAcquisitionEvent.provider_ordinal.between(tranche_start, tranche_end),
                )
            )
        )
        terminal_ordinals = set(
            self._session.scalars(
                select(D02SourceAcquisitionEvent.provider_ordinal).where(
                    D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                    D02SourceAcquisitionEvent.event_kind.in_(
                        {
                            "CALL_CONSUMED_NO_RESULT",
                            "MATERIALIZATION_FAILED",
                            "M3_UNSUPPORTED",
                            "QA_ACCEPTED",
                            "QA_REJECTED",
                        }
                    ),
                    D02SourceAcquisitionEvent.provider_ordinal.between(tranche_start, tranche_end),
                )
            )
        )
        expected_ordinals = set(range(tranche_start, tranche_end + 1))
        if started_ordinals != expected_ordinals or terminal_ordinals != expected_ordinals:
            _fail("TRANCHE_OUTCOMES_NOT_RECONCILED")
        existing = self._session.scalar(
            select(D02SourceAcquisitionEvent).where(
                D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                D02SourceAcquisitionEvent.event_kind == "TRANCHE_RECONCILED",
                D02SourceAcquisitionEvent.tranche_number == tranche_number,
            )
        )
        if existing is not None:
            if existing.evidence_digest != reconciliation_digest:
                _fail("TRANCHE_RECONCILIATION_COLLISION")
            return
        self._append_event(
            run,
            event_kind="TRANCHE_RECONCILED",
            tranche_number=tranche_number,
            evidence_digest=reconciliation_digest,
        )

    def record_m3_supported(self, *, candidate_id: str, evidence_digest: str) -> None:
        _require_digest(evidence_digest, "m3_evidence_digest")
        candidate, run = self._lock_candidate_and_run(candidate_id)
        if run.run_state != "ACTIVE" or candidate.candidate_state != "DURABLE":
            _fail("M3_TRANSITION_INVALID")
        candidate.candidate_state = "M3_SUPPORTED"
        candidate.m3_state = "SUPPORTED"
        candidate.m3_evidence_digest = evidence_digest
        _seal_candidate(candidate)
        self._append_event(
            run,
            event_kind="M3_SUPPORTED",
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            candidate_id=candidate.id,
            evidence_digest=evidence_digest,
            call_started_event_digest=candidate.call_started_event_digest,
        )

    def record_m3_unsupported(
        self, *, candidate_id: str, evidence_digest: str, rejection_code: str
    ) -> None:
        _require_digest(evidence_digest, "m3_evidence_digest")
        _require_code(rejection_code)
        candidate, run = self._lock_candidate_and_run(candidate_id)
        if run.run_state != "ACTIVE" or candidate.candidate_state != "DURABLE":
            _fail("M3_TRANSITION_INVALID")
        candidate.candidate_state = "QA_REJECTED"
        candidate.m3_state = "UNSUPPORTED"
        candidate.m3_evidence_digest = evidence_digest
        candidate.qa_state = "REJECTED"
        candidate.qa_evidence_digest = evidence_digest
        candidate.rejection_code = rejection_code
        _seal_candidate(candidate)
        self._append_event(
            run,
            event_kind="M3_UNSUPPORTED",
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            candidate_id=candidate.id,
            detail_code=rejection_code,
            evidence_digest=evidence_digest,
            call_started_event_digest=candidate.call_started_event_digest,
        )
        self._register_content_reject(run)

    def record_qa_accepted(
        self,
        *,
        candidate_id: str,
        evidence_digest: str,
        identity_family_digest: str,
    ) -> D02SelectedSourceManifest | None:
        _require_digest(evidence_digest, "qa_evidence_digest")
        _require_digest(identity_family_digest, "identity_family_digest")
        candidate, run = self._lock_candidate_and_run(candidate_id)
        if run.run_state != "ACTIVE" or candidate.candidate_state != "M3_SUPPORTED":
            _fail("QA_TRANSITION_INVALID")
        existing_family = self._session.scalar(
            select(D02SourceCandidate.id).where(
                D02SourceCandidate.acquisition_run_id == run.id,
                D02SourceCandidate.qa_state == "ACCEPTED",
                D02SourceCandidate.identity_family_digest == identity_family_digest,
            )
        )
        if existing_family is not None:
            _fail("DUPLICATE_IDENTITY_FAMILY")
        candidate.candidate_state = "QA_ACCEPTED"
        candidate.qa_state = "ACCEPTED"
        candidate.qa_evidence_digest = evidence_digest
        candidate.adult_status = "VERIFIED_SYNTHETIC_ADULT"
        candidate.suspected_minor = False
        candidate.identity_family_digest = identity_family_digest
        _seal_candidate(candidate)
        self._append_event(
            run,
            event_kind="QA_ACCEPTED",
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            candidate_id=candidate.id,
            evidence_digest=evidence_digest,
            call_started_event_digest=candidate.call_started_event_digest,
        )
        run.accepted_count += 1
        run.consecutive_content_rejects = 0
        run.calls_without_accept = 0
        if run.accepted_count == TARGET_SOURCE_COUNT:
            run.run_state = "MANIFEST_FINALIZED"
            _seal_run(run)
            return self._finalize_manifest(run)
        _seal_run(run)
        return None

    def record_qa_rejected(
        self, *, candidate_id: str, evidence_digest: str, rejection_code: str
    ) -> None:
        _require_digest(evidence_digest, "qa_evidence_digest")
        _require_code(rejection_code)
        candidate, run = self._lock_candidate_and_run(candidate_id)
        if run.run_state != "ACTIVE" or candidate.candidate_state != "M3_SUPPORTED":
            _fail("QA_TRANSITION_INVALID")
        candidate.candidate_state = "QA_REJECTED"
        candidate.qa_state = "REJECTED"
        candidate.qa_evidence_digest = evidence_digest
        candidate.rejection_code = rejection_code
        _seal_candidate(candidate)
        self._append_event(
            run,
            event_kind="QA_REJECTED",
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            candidate_id=candidate.id,
            detail_code=rejection_code,
            evidence_digest=evidence_digest,
            call_started_event_digest=candidate.call_started_event_digest,
        )
        self._register_content_reject(run)

    def pause_infrastructure_for_candidate(self, *, candidate_id: str, stage_code: str) -> None:
        _require_code(stage_code)
        candidate, run = self._lock_candidate_and_run(candidate_id)
        if run.run_state != "ACTIVE" or candidate.candidate_state not in {
            "DURABLE",
            "M3_SUPPORTED",
        }:
            _fail("CANDIDATE_NOT_REPROCESSABLE")
        self._pause_infrastructure(
            run,
            detail_code=stage_code,
            candidate_id=candidate.id,
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            call_started_event_digest=candidate.call_started_event_digest,
        )

    def resume_infrastructure(self, *, run_id: str, review_digest: str) -> None:
        _require_digest(review_digest, "review_digest")
        run = self._lock_run(run_id)
        if run.run_state != "PAUSED_INFRASTRUCTURE":
            _fail("RUN_NOT_PAUSED_INFRASTRUCTURE")
        unresolved_primary = self._session.scalar(
            select(D02SourceCandidate.id).where(
                D02SourceCandidate.acquisition_run_id == run.id,
                D02SourceCandidate.candidate_state == "PRIMARY_DURABLE",
            )
        )
        if unresolved_primary is not None:
            _fail("PRIMARY_BACKUP_NOT_RECONCILED")
        reprocessable_candidate = self._session.scalar(
            select(D02SourceCandidate.id).where(
                D02SourceCandidate.acquisition_run_id == run.id,
                D02SourceCandidate.candidate_state.in_({"DURABLE", "M3_SUPPORTED"}),
            )
        )
        if (
            reprocessable_candidate is None
            and run.calls_without_accept >= CALLS_WITHOUT_ACCEPT_PAUSE_THRESHOLD
        ):
            run.run_state = "PAUSED_CONTENT_REVIEW"
            _seal_run(run)
            self._append_event(
                run,
                event_kind="CONTENT_REVIEW_PAUSED",
                detail_code="TEN_CALLS_WITHOUT_ACCEPT",
                evidence_digest=review_digest,
            )
            return
        run.run_state = "ACTIVE"
        _seal_run(run)
        self._append_event(
            run,
            event_kind="INFRASTRUCTURE_RESUMED",
            evidence_digest=review_digest,
        )

    def resume_content_review(self, *, run_id: str, review_digest: str) -> None:
        _require_digest(review_digest, "review_digest")
        run = self._lock_run(run_id)
        if run.run_state != "PAUSED_CONTENT_REVIEW":
            _fail("RUN_NOT_PAUSED_CONTENT_REVIEW")
        run.run_state = "ACTIVE"
        run.consecutive_content_rejects = 0
        run.calls_without_accept = 0
        run.content_review_epoch += 1
        _seal_run(run)
        self._append_event(
            run,
            event_kind="CONTENT_REVIEW_RESUMED",
            evidence_digest=review_digest,
        )

    def mark_admitted(self, *, run_id: str, admission_digest: str) -> None:
        _require_digest(admission_digest, "admission_digest")
        run = self._lock_run(run_id)
        if run.run_state != "MANIFEST_FINALIZED":
            _fail("MANIFEST_NOT_FINALIZED")
        manifest = self._session.scalar(
            select(D02SelectedSourceManifest).where(
                D02SelectedSourceManifest.acquisition_run_id == run.id
            )
        )
        if manifest is None:
            _fail("MANIFEST_NOT_FINALIZED")
        ready = self._session.scalar(
            select(D02SourceAcquisitionEvent.id).where(
                D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                D02SourceAcquisitionEvent.event_kind == "FORMAL_SOURCES_READY",
            )
        )
        admission = self._session.scalar(
            select(DemoD02R2Epoch2Admission).where(
                DemoD02R2Epoch2Admission.schema_version == "mirror.demo/D02GenericAdmission/v1",
                DemoD02R2Epoch2Admission.selected_source_manifest_id == manifest.id,
                DemoD02R2Epoch2Admission.content_digest == admission_digest,
            )
        )
        if ready is None or admission is None:
            _fail("FORMAL_GATE_NOT_COMPLETE")
        run.run_state = "ADMITTED"
        _seal_run(run)
        self._append_event(
            run,
            event_kind="ADMISSION_COMPLETED",
            evidence_digest=admission_digest,
        )

    def mark_formal_sources_ready(
        self,
        *,
        run_id: str,
        formal_source_set_digest: str,
    ) -> None:
        _require_digest(formal_source_set_digest, "formal_source_set_digest")
        run = self._lock_run(run_id)
        if run.run_state != "MANIFEST_FINALIZED":
            _fail("MANIFEST_NOT_FINALIZED")
        manifest = self._session.scalar(
            select(D02SelectedSourceManifest).where(
                D02SelectedSourceManifest.acquisition_run_id == run.id,
                D02SelectedSourceManifest.cohort_spec_id == run.cohort_spec_id,
                D02SelectedSourceManifest.manifest_state == "FINALIZED",
            )
        )
        if manifest is None:
            _fail("MANIFEST_NOT_FINALIZED")
        rows = list(
            self._session.scalars(
                select(DemoD02R2SourceAuthority)
                .where(
                    DemoD02R2SourceAuthority.schema_version
                    == "mirror.demo/D02GenericSourceAuthorityRecord/v1",
                    DemoD02R2SourceAuthority.selected_source_manifest_id == manifest.id,
                )
                .order_by(DemoD02R2SourceAuthority.manifest_position)
            )
        )
        if (
            len(rows) != TARGET_SOURCE_COUNT
            or [row.manifest_position for row in rows] != [1, 2, 3, 4]
            or [row.source_ordinal for row in rows] != [1, 2, 3, 4]
            or [row.acquisition_candidate_id for row in rows] != manifest.ordered_candidate_ids
            or len({row.source_authority_digest for row in rows}) != TARGET_SOURCE_COUNT
            or len({row.source_qa_snapshot_digest for row in rows}) != TARGET_SOURCE_COUNT
        ):
            _fail("FORMAL_SOURCE_SET_INVALID")
        existing = self._session.scalar(
            select(D02SourceAcquisitionEvent).where(
                D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                D02SourceAcquisitionEvent.event_kind == "FORMAL_SOURCES_READY",
            )
        )
        if existing is not None:
            if existing.evidence_digest != formal_source_set_digest:
                _fail("FORMAL_SOURCE_SET_COLLISION")
            return
        self._append_event(
            run,
            event_kind="FORMAL_SOURCES_READY",
            evidence_digest=formal_source_set_digest,
        )

    def pause_final_gate(
        self,
        *,
        run_id: str,
        stage_code: str,
        evidence_digest: str,
    ) -> None:
        _require_code(stage_code)
        _require_digest(evidence_digest, "evidence_digest")
        run = self._lock_run(run_id)
        if run.run_state != "MANIFEST_FINALIZED":
            _fail("MANIFEST_NOT_FINALIZED")
        self._append_event(
            run,
            event_kind="FINAL_GATE_PAUSED",
            detail_code=stage_code,
            evidence_digest=evidence_digest,
        )

    def _next_selector_slot(self, run: D02SourceAcquisitionRun) -> SelectorSlot:
        accepted = set(
            self._session.scalars(
                select(D02SourceCandidate.selector_slot_id).where(
                    D02SourceCandidate.acquisition_run_id == run.id,
                    D02SourceCandidate.qa_state == "ACCEPTED",
                )
            )
        )
        for slot in SELECTOR_SLOTS:
            if slot.slot_id not in accepted:
                return slot
        _fail("SELECTOR_SLOTS_ALREADY_COMPLETE")

    def _finalize_manifest(self, run: D02SourceAcquisitionRun) -> D02SelectedSourceManifest:
        if run.run_state != "MANIFEST_FINALIZED" or run.accepted_count != TARGET_SOURCE_COUNT:
            _fail("FINAL_MANIFEST_RUN_STATE_INVALID")
        candidates = list(
            self._session.scalars(
                select(D02SourceCandidate)
                .where(
                    D02SourceCandidate.acquisition_run_id == run.id,
                    D02SourceCandidate.cohort_spec_id == run.cohort_spec_id,
                    D02SourceCandidate.qa_state == "ACCEPTED",
                )
                .with_for_update()
            )
        )
        by_slot = {candidate.selector_slot_id: candidate for candidate in candidates}
        ordered_ids = [
            by_slot[slot.slot_id].id for slot in SELECTOR_SLOTS if slot.slot_id in by_slot
        ]
        if len(candidates) != TARGET_SOURCE_COUNT or len(ordered_ids) != TARGET_SOURCE_COUNT:
            _fail("FINAL_MANIFEST_CANDIDATES_INVALID")
        payload = {
            "acquisition_run_id": run.id,
            "cohort_spec_id": run.cohort_spec_id,
            "generation_policy_digest": D02_GENERATION_POLICY_V1_DIGEST,
            "ordered_candidate_ids": ordered_ids,
            "source_count": TARGET_SOURCE_COUNT,
            "manifest_state": "FINALIZED",
        }
        content_digest = _digest(SELECTED_SOURCE_MANIFEST_SCHEMA, payload)
        manifest = D02SelectedSourceManifest(
            id=_identifier(
                SELECTED_SOURCE_MANIFEST_ID_SCHEMA,
                {"acquisition_run_id": run.id, "content_digest": content_digest},
            ),
            schema_version=SELECTED_SOURCE_MANIFEST_SCHEMA,
            canonical_payload=payload,
            content_digest=content_digest,
            created_at=utcnow(),
            **payload,
        )
        self._session.add(manifest)
        self._session.flush()
        self._append_event(
            run,
            event_kind="MANIFEST_FINALIZED",
            evidence_digest=manifest.content_digest,
        )
        return manifest

    def _register_content_reject(self, run: D02SourceAcquisitionRun) -> None:
        run.consecutive_content_rejects += 1
        if run.consecutive_content_rejects >= CONTENT_REJECT_PAUSE_THRESHOLD:
            run.run_state = "PAUSED_CONTENT_REVIEW"
            _seal_run(run)
            self._append_event(
                run,
                event_kind="CONTENT_REVIEW_PAUSED",
                detail_code="FIVE_CONSECUTIVE_CONTENT_REJECTS",
            )
            return
        self._post_unsuccessful_outcome(run)

    def _post_unsuccessful_outcome(self, run: D02SourceAcquisitionRun) -> None:
        if run.budget_consumed >= TOTAL_BUDGET:
            self._fail_budget_exhausted(run)
            return
        if run.calls_without_accept >= CALLS_WITHOUT_ACCEPT_PAUSE_THRESHOLD:
            run.run_state = "PAUSED_CONTENT_REVIEW"
            _seal_run(run)
            self._append_event(
                run,
                event_kind="CONTENT_REVIEW_PAUSED",
                detail_code="TEN_CALLS_WITHOUT_ACCEPT",
            )
            return
        _seal_run(run)

    def _pause_infrastructure(
        self,
        run: D02SourceAcquisitionRun,
        *,
        detail_code: str,
        candidate_id: str | None = None,
        provider_ordinal: int | None = None,
        selector_slot_id: str | None = None,
        call_started_event_digest: str | None = None,
    ) -> None:
        if run.run_state != "ACTIVE":
            _fail("RUN_NOT_ACTIVE")
        run.run_state = "PAUSED_INFRASTRUCTURE"
        _seal_run(run)
        self._append_event(
            run,
            event_kind="INFRASTRUCTURE_PAUSED",
            provider_ordinal=provider_ordinal,
            selector_slot_id=selector_slot_id,
            candidate_id=candidate_id,
            detail_code=detail_code,
            call_started_event_digest=call_started_event_digest,
        )

    def _fail_budget_exhausted(self, run: D02SourceAcquisitionRun) -> None:
        self._fail_run(run, "CALL_BUDGET_EXHAUSTED")

    def _fail_run(self, run: D02SourceAcquisitionRun, reason: str) -> None:
        _require_code(reason)
        run.run_state = "FAILED_CLOSED"
        run.terminal_reason = reason
        run.open_call_ordinal = None
        run.open_selector_slot_id = None
        _seal_run(run)
        self._append_event(
            run,
            event_kind="RUN_FAILED_CLOSED",
            detail_code=reason,
        )

    def _require_open_authorization(
        self, authorization: CallAuthorization
    ) -> tuple[D02SourceAcquisitionRun, str]:
        if type(authorization) is not CallAuthorization:
            _fail("CALL_AUTHORIZATION_INVALID")
        run = self._lock_run(authorization.run_id)
        if (
            run.run_state != "ACTIVE"
            or run.cohort_spec_id != authorization.cohort_spec_id
            or run.open_call_ordinal != authorization.provider_ordinal
            or run.open_selector_slot_id is None
            or run.open_selector_slot_id != authorization.selector_slot.slot_id
        ):
            _fail("OPEN_CALL_MISMATCH")
        self._require_call_binding(
            run=run,
            provider_ordinal=authorization.provider_ordinal,
            selector_slot_id=authorization.selector_slot.slot_id,
            call_started_event_digest=authorization.call_started_event_digest,
        )
        return run, run.open_selector_slot_id

    def _require_open_call_recovery(
        self,
        *,
        run_id: str,
        call_started_event_digest: str,
    ) -> tuple[D02SourceAcquisitionRun, str]:
        _require_digest(call_started_event_digest, "call_started_event_digest")
        run = self._lock_run(run_id)
        if (
            run.run_state != "ACTIVE"
            or run.open_call_ordinal is None
            or run.open_selector_slot_id is None
        ):
            _fail("OPEN_CALL_RECOVERY_NOT_AUTHORIZED")
        slot_id = run.open_selector_slot_id
        self._require_call_binding(
            run=run,
            provider_ordinal=run.open_call_ordinal,
            selector_slot_id=slot_id,
            call_started_event_digest=call_started_event_digest,
        )
        return run, slot_id

    def _require_open_materialization(
        self, candidate: DurableCandidateBytes
    ) -> tuple[D02SourceAcquisitionRun, str]:
        run = self._lock_run(candidate.run_id)
        if (
            run.run_state != "ACTIVE"
            or run.cohort_spec_id != candidate.cohort_spec_id
            or run.open_call_ordinal != candidate.provider_ordinal
            or run.open_selector_slot_id != candidate.selector_slot_id
        ):
            _fail("OPEN_CALL_MISMATCH")
        self._require_call_binding(
            run=run,
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            call_started_event_digest=candidate.call_started_event_digest,
        )
        return run, candidate.selector_slot_id

    def _require_call_binding(
        self,
        *,
        run: D02SourceAcquisitionRun,
        provider_ordinal: int,
        selector_slot_id: str,
        call_started_event_digest: str,
    ) -> D02SourceAcquisitionEvent:
        _require_digest(call_started_event_digest, "call_started_event_digest")
        event = self._session.scalar(
            select(D02SourceAcquisitionEvent).where(
                D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                D02SourceAcquisitionEvent.cohort_spec_id == run.cohort_spec_id,
                D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
                D02SourceAcquisitionEvent.provider_ordinal == provider_ordinal,
                D02SourceAcquisitionEvent.selector_slot_id == selector_slot_id,
                D02SourceAcquisitionEvent.content_digest == call_started_event_digest,
            )
        )
        if event is None:
            _fail("CALL_STARTED_BINDING_MISMATCH")
        return event

    def _require_materialization_matches_candidate(
        self,
        materialization: DurableCandidateBytes,
        candidate: D02SourceCandidate,
    ) -> None:
        if (
            materialization.run_id != candidate.acquisition_run_id
            or materialization.cohort_spec_id != candidate.cohort_spec_id
            or materialization.provider_ordinal != candidate.provider_ordinal
            or materialization.selector_slot_id != candidate.selector_slot_id
            or materialization.call_started_event_digest != candidate.call_started_event_digest
            or materialization.output_id != candidate.output_id
            or materialization.provider_result_digest != candidate.provider_result_digest
            or materialization.primary_sha256 != candidate.durable_primary_sha256
            or materialization.byte_size != candidate.durable_byte_size
            or materialization.media_type != candidate.durable_media_type
            or materialization.width != candidate.durable_width
            or materialization.height != candidate.durable_height
        ):
            _fail("DURABLE_CANDIDATE_BINDING_MISMATCH")

    def _close_open_call(self, run: D02SourceAcquisitionRun) -> None:
        run.open_call_ordinal = None
        run.open_selector_slot_id = None
        _seal_run(run)

    def _lock_run(self, run_id: str) -> D02SourceAcquisitionRun:
        row = self._session.scalar(
            select(D02SourceAcquisitionRun)
            .where(D02SourceAcquisitionRun.id == run_id)
            .with_for_update()
        )
        if row is None or row.schema_version != ACQUISITION_RUN_SCHEMA:
            _fail("ACQUISITION_RUN_NOT_FOUND")
        return row

    def _lock_candidate_and_run(
        self, candidate_id: str
    ) -> tuple[D02SourceCandidate, D02SourceAcquisitionRun]:
        candidate = self._session.scalar(
            select(D02SourceCandidate)
            .where(D02SourceCandidate.id == candidate_id)
            .with_for_update()
        )
        if candidate is None or candidate.schema_version != SOURCE_CANDIDATE_SCHEMA:
            _fail("SOURCE_CANDIDATE_NOT_FOUND")
        run = self._lock_run(candidate.acquisition_run_id)
        if candidate.cohort_spec_id != run.cohort_spec_id:
            _fail("CANDIDATE_RUN_SPEC_MISMATCH")
        return candidate, run

    def _append_event(
        self,
        run: D02SourceAcquisitionRun,
        *,
        event_kind: str,
        provider_ordinal: int | None = None,
        selector_slot_id: str | None = None,
        tranche_number: int | None = None,
        candidate_id: str | None = None,
        detail_code: str | None = None,
        evidence_digest: str | None = None,
        call_started_event_digest: str | None = None,
    ) -> D02SourceAcquisitionEvent:
        last = self._session.scalar(
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
            "provider_ordinal": provider_ordinal,
            "selector_slot_id": selector_slot_id,
            "tranche_number": tranche_number,
            "candidate_id": candidate_id,
            "detail_code": detail_code,
            "evidence_digest": evidence_digest,
            "call_started_event_digest": call_started_event_digest,
        }
        content_digest = _digest(ACQUISITION_EVENT_SCHEMA, payload)
        event = D02SourceAcquisitionEvent(
            id=_identifier(
                ACQUISITION_EVENT_ID_SCHEMA,
                {
                    "acquisition_run_id": run.id,
                    "event_sequence": event_sequence,
                    "content_digest": content_digest,
                },
            ),
            schema_version=ACQUISITION_EVENT_SCHEMA,
            canonical_payload=payload,
            content_digest=content_digest,
            created_at=utcnow(),
            **payload,
        )
        self._session.add(event)
        self._session.flush()
        return event


def _issue_durable_candidate(
    *,
    authorization: CallAuthorization | PrimaryRecoveryAuthorization,
    primary: ReceivedPng,
    backup: ReceivedPng | None,
) -> DurableCandidateBytes:
    image_facts = {
        "media_type": "image/png",
        "byte_size": primary.byte_size,
        "sha256": primary.sha256,
        "width": primary.width,
        "height": primary.height,
    }
    output_id = "d02-" + _identifier(
        SOURCE_OUTPUT_ID_SCHEMA,
        {
            "call_started_event_digest": authorization.call_started_event_digest,
            "provider_ordinal": authorization.provider_ordinal,
            "image_facts": image_facts,
        },
    )
    provider_result_digest = _digest(
        PROVIDER_RESULT_SCHEMA,
        {
            "call_started_event_digest": authorization.call_started_event_digest,
            "output_id": output_id,
            "image_facts": image_facts,
        },
    )
    return DurableCandidateBytes(
        run_id=authorization.run_id,
        cohort_spec_id=authorization.cohort_spec_id,
        provider_ordinal=authorization.provider_ordinal,
        selector_slot_id=authorization.selector_slot.slot_id,
        call_started_event_digest=authorization.call_started_event_digest,
        output_id=output_id,
        provider_result_digest=provider_result_digest,
        media_type="image/png",
        byte_size=primary.byte_size,
        primary_sha256=primary.sha256,
        backup_sha256=backup.sha256 if backup is not None else None,
        width=primary.width,
        height=primary.height,
        _factory_token=_DURABLE_CANDIDATE_FACTORY_TOKEN,
    )


def _slot(slot_id: str) -> SelectorSlot:
    for item in SELECTOR_SLOTS:
        if item.slot_id == slot_id:
            return item
    _fail("UNKNOWN_SELECTOR_SLOT")


def _seal_run(row: D02SourceAcquisitionRun) -> None:
    payload = {
        "cohort_spec_id": row.cohort_spec_id,
        "run_key_digest": row.run_key_digest,
        "run_state": row.run_state,
        "budget_consumed": row.budget_consumed,
        "next_ordinal": row.next_ordinal,
        "open_call_ordinal": row.open_call_ordinal,
        "open_selector_slot_id": row.open_selector_slot_id,
        "accepted_count": row.accepted_count,
        "consecutive_content_rejects": row.consecutive_content_rejects,
        "calls_without_accept": row.calls_without_accept,
        "content_review_epoch": row.content_review_epoch,
        "terminal_reason": row.terminal_reason,
    }
    row.canonical_payload = payload
    row.content_digest = _digest(ACQUISITION_RUN_SCHEMA, payload)


def _seal_candidate(row: D02SourceCandidate) -> None:
    payload = {
        "acquisition_run_id": row.acquisition_run_id,
        "cohort_spec_id": row.cohort_spec_id,
        "provider_ordinal": row.provider_ordinal,
        "selector_slot_id": row.selector_slot_id,
        "call_started_event_digest": row.call_started_event_digest,
        "output_id": row.output_id,
        "provider_result_digest": row.provider_result_digest,
        "durable_primary_sha256": row.durable_primary_sha256,
        "durable_backup_sha256": row.durable_backup_sha256,
        "durable_byte_size": row.durable_byte_size,
        "durable_media_type": row.durable_media_type,
        "durable_width": row.durable_width,
        "durable_height": row.durable_height,
        "candidate_state": row.candidate_state,
        "m3_state": row.m3_state,
        "m3_evidence_digest": row.m3_evidence_digest,
        "qa_state": row.qa_state,
        "qa_evidence_digest": row.qa_evidence_digest,
        "adult_status": row.adult_status,
        "declared_age_band": row.declared_age_band,
        "suspected_minor": row.suspected_minor,
        "synthetic_only_attested": row.synthetic_only_attested,
        "real_person_reference_used": row.real_person_reference_used,
        "identity_family_digest": row.identity_family_digest,
        "rejection_code": row.rejection_code,
    }
    row.canonical_payload = payload
    row.content_digest = _digest(SOURCE_CANDIDATE_SCHEMA, payload)


def _digest(schema_version: str, payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _identifier(schema_version: str, payload: Mapping[str, object]) -> str:
    return _digest(schema_version, payload)[:32]


def _require_digest(value: str, name: str) -> None:
    if _DIGEST.fullmatch(value) is None:
        _fail(f"INVALID_{name.upper()}")


def _require_code(value: str) -> None:
    if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value) is None:
        _fail("INVALID_DETAIL_CODE")


def _fail(code: str) -> NoReturn:
    raise D02SourceAcquisitionError(code)
