"""D06 self-transfer and Reference Profile application authority.

This module deliberately stays behind the public API contract.  It bridges
an owner-bound D05 profile and a published D07-B ImageVersion without reading
private image bytes or inventing measurements.  All learned values come from
the persisted integer verifier evidence.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_idempotency import (
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    D02SelectedSourceManifest,
    DemoAcceptedVisualEpisode,
    DemoActor,
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
    DemoDesiredDeltaProfile,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoPairScreeningReport,
    DemoReferenceProfile,
    DemoSelfTransferDimensionEvidence,
    DemoSelfTransferRun,
    DemoSession,
    DemoStyleProfile,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.demo_profile_geometry_selector import (
    DemoProfileGeometryCase,
    DemoProfileGeometryDimension,
    DemoProfileGeometrySelection,
    DemoProfileGeometrySelectionError,
    select_profile_guided_geometry_step,
    selection_from_envelope,
)
from mirror_api.demo_profile_service import (
    DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST,
    DEMO_SELF_TRANSFER_PROJECTION_VERSION,
)
from mirror_api.models import Asset, Job, JobAttempt, new_id, utcnow

DEMO_SELF_TRANSFER_OPERATION: Final = "self_transfer.execute"
DEMO_SELF_TRANSFER_JOB_TYPE: Final = "demo_p3_p7.self_transfer.execute"
DEMO_SELF_TRANSFER_RUN_SCHEMA: Final = "mirror.demo/DemoSelfTransferRun/v1"
DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA: Final = "mirror.demo/DemoSelfTransferRun/v2"
DEMO_SELF_TRANSFER_EVIDENCE_SCHEMA: Final = "mirror.demo/DemoSelfTransferDimensionEvidence/v1"
DEMO_REFERENCE_PROFILE_SCHEMA: Final = "mirror.demo/DemoReferenceProfile/v1"
DEMO_REFERENCE_STRUCTURE_SCHEMA: Final = "mirror.demo/ReferenceProfileStructure/v1"
DEMO_REFERENCE_ANALYSIS_VERSION: Final = "demo-reference-authority-analysis-v1"
DEMO_REFERENCE_COMPILER_VERSION: Final = "demo-reference-profile-compiler-v1"
DEMO_JOB_BINDING_SCHEMA: Final = "mirror.demo/DemoJobBinding/v1"

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_DIMENSION = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PPM = 1_000_000
_VIEWS: Final = ("FRONT", "THREE_QUARTER", "SIDE")
_VIEW_ORDER: Final = {value: index for index, value in enumerate(_VIEWS)}
_NON_AUTHORITY_COLUMNS: Final = frozenset(
    {
        "id",
        "schema_version",
        "canonical_payload",
        "content_digest",
        "created_at",
        "closed_at",
        "tombstoned_at",
    }
)

SelfTransferOutcome = Literal["ACCEPTED", "REJECTED", "ADJUSTED"]
ReferenceView = Literal["FRONT", "THREE_QUARTER", "SIDE"]


class DemoSelfTransferServiceError(RuntimeError):
    """Stable fail-closed D06 application error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DemoSelfTransferInputError(DemoSelfTransferServiceError):
    """The internal command is outside the frozen D06 boundary."""


class DemoSelfTransferUnavailable(DemoSelfTransferServiceError):
    """Required owner-bound authority is unavailable."""


class DemoSelfTransferConflict(DemoSelfTransferServiceError):
    """A legal request conflicts with an existing immutable authority."""


class DemoSelfTransferAuthorityCorruption(DemoSelfTransferServiceError):
    """Persisted authority cannot be replayed safely."""


@dataclass(frozen=True, slots=True)
class CreateDemoSelfTransferRequest:
    demo_actor_id: str
    demo_session_id: str
    desired_delta_profile_id: str
    source_asset_id: str
    dimension_key: str
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.demo_session_id, "demo_session_id")
        _require_id(self.desired_delta_profile_id, "desired_delta_profile_id")
        _require_id(self.source_asset_id, "source_asset_id")
        _require_dimension(self.dimension_key)
        idempotency_key_hash(self.idempotency_key)
        if not isinstance(self.request_id, str) or _REQUEST_ID.fullmatch(self.request_id) is None:
            raise DemoSelfTransferInputError(
                "INVALID_REQUEST_ID", "request_id is outside the internal boundary"
            )


@dataclass(frozen=True, slots=True)
class CreateDemoSteppedSelfTransferRequest:
    demo_actor_id: str
    demo_session_id: str
    desired_delta_profile_id: str
    source_asset_id: str
    execution_job_id: str
    result_image_version_id: str
    selection: DemoProfileGeometrySelection
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        for name, value in (
            ("demo_actor_id", self.demo_actor_id),
            ("demo_session_id", self.demo_session_id),
            ("desired_delta_profile_id", self.desired_delta_profile_id),
            ("source_asset_id", self.source_asset_id),
            ("execution_job_id", self.execution_job_id),
            ("result_image_version_id", self.result_image_version_id),
        ):
            _require_id(value, name)
        try:
            if not isinstance(self.selection, DemoProfileGeometrySelection):
                raise DemoProfileGeometrySelectionError(
                    "INVALID_STEPPED_SELECTION", "stepped selection is invalid"
                )
            if selection_from_envelope(_selection_payload(self.selection)) != self.selection:
                raise DemoProfileGeometrySelectionError(
                    "INVALID_STEPPED_SELECTION", "stepped selection does not replay"
                )
        except DemoProfileGeometrySelectionError as exc:
            raise DemoSelfTransferInputError(exc.code, str(exc)) from exc
        idempotency_key_hash(self.idempotency_key)
        if not isinstance(self.request_id, str) or _REQUEST_ID.fullmatch(self.request_id) is None:
            raise DemoSelfTransferInputError(
                "INVALID_REQUEST_ID", "request_id is outside the internal boundary"
            )


@dataclass(frozen=True, slots=True)
class DemoSelfTransferRequestAccepted:
    job_id: str
    request_run_id: str
    demo_session_id: str
    requested_delta_ppm: int
    replayed: bool


@dataclass(frozen=True, slots=True)
class DemoSelfTransferReservation:
    job_id: str
    request_run_id: str
    formal_job_attempt_id: str
    attempt: int
    replayed: bool


@dataclass(frozen=True, slots=True)
class FinalizeDemoSelfTransferResult:
    demo_actor_id: str
    request_run_id: str
    result_image_version_id: str
    user_outcome: SelfTransferOutcome
    final_save_episode_id: str | None = None

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.request_run_id, "request_run_id")
        _require_id(self.result_image_version_id, "result_image_version_id")
        if self.final_save_episode_id is not None:
            _require_id(self.final_save_episode_id, "final_save_episode_id")
        if self.user_outcome not in {"ACCEPTED", "REJECTED", "ADJUSTED"}:
            raise DemoSelfTransferInputError("INVALID_USER_OUTCOME", "user_outcome is unsupported")


@dataclass(frozen=True, slots=True)
class DemoSelfTransferResultAccepted:
    job_id: str
    request_run_id: str
    result_run_id: str
    evidence_id: str | None
    result_image_version_id: str
    dimension_key: str
    measured_delta_ppm: int
    confidence_ppm: int
    user_outcome: SelfTransferOutcome
    replayed: bool


@dataclass(frozen=True, slots=True)
class DemoReferenceSource:
    """Categorical reference slot supplied by policy, never measured pose evidence."""

    asset_id: str
    view: ReferenceView

    def validate(self) -> None:
        _require_id(self.asset_id, "reference source asset_id")
        if self.view not in _VIEWS:
            raise DemoSelfTransferInputError(
                "INVALID_REFERENCE_VIEW", "reference source view is unsupported"
            )


@dataclass(frozen=True, slots=True)
class CompileDemoReferenceProfile:
    demo_actor_id: str
    demo_session_id: str
    desired_delta_profile_id: str
    style_profile_id: str | None
    identity_constraints_id: str | None
    sources: tuple[DemoReferenceSource, ...]

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.demo_session_id, "demo_session_id")
        _require_id(self.desired_delta_profile_id, "desired_delta_profile_id")
        if self.style_profile_id is not None:
            _require_id(self.style_profile_id, "style_profile_id")
        if self.identity_constraints_id is not None:
            _require_id(self.identity_constraints_id, "identity_constraints_id")
        if not isinstance(self.sources, tuple) or not 1 <= len(self.sources) <= 3:
            raise DemoSelfTransferInputError(
                "INVALID_REFERENCE_SOURCES", "one to three reference sources are required"
            )
        for source in self.sources:
            if not isinstance(source, DemoReferenceSource):
                raise DemoSelfTransferInputError(
                    "INVALID_REFERENCE_SOURCES", "reference source type is invalid"
                )
            source.validate()
        if len({source.asset_id for source in self.sources}) != len(self.sources):
            raise DemoSelfTransferInputError(
                "DUPLICATE_REFERENCE_ASSET", "reference source assets must be unique"
            )
        if len({source.view for source in self.sources}) != len(self.sources):
            raise DemoSelfTransferInputError(
                "DUPLICATE_REFERENCE_VIEW", "reference source views must be unique"
            )


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileAccepted:
    reference_profile_id: str
    version: int
    content_digest: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileInputSnapshot:
    """Immutable, byte-free D06 compiler input frozen at queued admission."""

    source_bindings: tuple[dict[str, Any], ...]
    input_digest: str


@dataclass(frozen=True, slots=True)
class _DesiredDimension:
    dimension_key: str
    desired_delta_ppm: int
    confidence_ppm: int


@dataclass(frozen=True, slots=True)
class _VerifiedProjection:
    dimension_key: str
    requested_delta_ppm: int
    measured_delta_ppm: int
    non_target_drift_ppm: int
    confidence_ppm: int


@dataclass(frozen=True, slots=True)
class _SteppedD02Authority:
    admission: DemoD02R2Epoch2Admission
    report: DemoPairScreeningReport


@dataclass(frozen=True, slots=True)
class _AcceptedReferenceAuthority:
    source_asset: Asset
    image_version: DemoImageVersion
    transfer_run: DemoSelfTransferRun
    verifier: DemoVerificationResult
    evidence: tuple[DemoSelfTransferDimensionEvidence, ...]


class DemoSelfTransferService:
    """Persist and replay D06 authority through PostgreSQL transactions."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._now = now

    async def create_request(
        self, command: CreateDemoSelfTransferRequest
    ) -> DemoSelfTransferRequestAccepted:
        command.validate()
        key_hash = idempotency_key_hash(command.idempotency_key)
        semantic_request = {
            "desired_delta_profile_id": command.desired_delta_profile_id,
            "dimension_key": command.dimension_key,
            "session_id": command.demo_session_id,
            "source_asset_id": command.source_asset_id,
        }
        request_digest = semantic_request_digest(semantic_request)
        async with self._sessions() as session:
            async with session.begin():
                existing = await self._binding_for_key(session, command.demo_actor_id, key_hash)
                if existing is not None:
                    return await self._replay_create(session, existing, request_digest)

                profile, source = await self._create_context(session, command)
                desired = _desired_dimension(profile, command.dimension_key)
                now = self._normalized_now()
                job_id, request_id, binding_id = new_id(), new_id(), new_id()
                request_payload = {
                    "demo_actor_id": command.demo_actor_id,
                    "demo_session_id": command.demo_session_id,
                    "desired_delta_profile_id": profile.id,
                    "record_kind": "REQUEST",
                    "request_run_id": None,
                    "demo_job_binding_id": None,
                    "source_asset_id": source.id,
                    "result_asset_id": None,
                    "requested_delta": {desired.dimension_key: desired.desired_delta_ppm},
                    "measured_delta": None,
                    "non_target_drift": None,
                    "verifier_digest": None,
                    "user_outcome": None,
                }
                duplicate_request = await session.scalar(
                    select(DemoSelfTransferRun.id).where(
                        DemoSelfTransferRun.content_digest
                        == _authority_digest(DEMO_SELF_TRANSFER_RUN_SCHEMA, request_payload)
                    )
                )
                if duplicate_request is not None:
                    raise DemoSelfTransferConflict(
                        "DUPLICATE_REQUEST_AUTHORITY",
                        "an identical immutable self-transfer request already exists",
                    )
                request = _authority_row(
                    DemoSelfTransferRun,
                    row_id=request_id,
                    schema_version=DEMO_SELF_TRANSFER_RUN_SCHEMA,
                    created_at=now,
                    fields=request_payload,
                )
                job = Job(
                    id=job_id,
                    job_type=DEMO_SELF_TRANSFER_JOB_TYPE,
                    status="PENDING",
                    idempotency_key_hash=_formal_job_key_hash(command.demo_actor_id, key_hash),
                    request_id=command.request_id,
                    payload={},
                    owner_user_id=None,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
                binding_payload = _job_binding_payload(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                    job_id=job_id,
                    idempotency_key_hash_value=key_hash,
                    request_digest=request_digest,
                    target_id=request_id,
                )
                binding = _authority_row(
                    DemoJobBinding,
                    row_id=binding_id,
                    schema_version=DEMO_JOB_BINDING_SCHEMA,
                    created_at=now,
                    fields=binding_payload,
                )
                try:
                    async with session.begin_nested():
                        session.add(job)
                        await session.flush()
                        session.add(request)
                        await session.flush()
                        session.add(binding)
                        await session.flush()
                except IntegrityError as exc:
                    winner = await self._binding_for_key(session, command.demo_actor_id, key_hash)
                    if winner is None:
                        duplicate = await session.scalar(
                            select(DemoSelfTransferRun.id).where(
                                DemoSelfTransferRun.content_digest == request.content_digest
                            )
                        )
                        if duplicate is not None:
                            raise DemoSelfTransferConflict(
                                "DUPLICATE_REQUEST_AUTHORITY",
                                "an identical immutable self-transfer request already exists",
                            ) from exc
                        raise DemoSelfTransferAuthorityCorruption(
                            "CREATE_CONFLICT_WITHOUT_WINNER",
                            "self-transfer create conflict has no reloadable winner",
                        ) from exc
                    return await self._replay_create(session, winner, request_digest)
                return DemoSelfTransferRequestAccepted(
                    job.id,
                    request.id,
                    command.demo_session_id,
                    desired.desired_delta_ppm,
                    False,
                )

    async def create_stepped_request(
        self, command: CreateDemoSteppedSelfTransferRequest
    ) -> DemoSelfTransferRequestAccepted:
        """Admit one v2 envelope; v1 request creation remains byte-for-byte separate."""

        command.validate()
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {
                "desired_delta_profile_id": command.desired_delta_profile_id,
                "result_image_version_id": command.result_image_version_id,
                "selection": _selection_payload(command.selection),
                "session_id": command.demo_session_id,
                "source_asset_id": command.source_asset_id,
                "execution_job_id": command.execution_job_id,
            }
        )
        async with self._sessions() as session:
            async with session.begin():
                existing = await self._binding_for_key(session, command.demo_actor_id, key_hash)
                if existing is not None:
                    return await self._replay_stepped_create(session, existing, request_digest)
                profile, source = await self._create_stepped_context(session, command)
                await self._require_stepped_command_execution(
                    session, command=command, profile=profile, source=source
                )
                now = self._normalized_now()
                job_id, request_id, binding_id = new_id(), new_id(), new_id()
                fields = _stepped_request_fields(command)
                request = _authority_row(
                    DemoSelfTransferRun,
                    row_id=request_id,
                    schema_version=DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA,
                    created_at=now,
                    fields=fields,
                )
                job = Job(
                    id=job_id,
                    job_type=DEMO_SELF_TRANSFER_JOB_TYPE,
                    status="PENDING",
                    idempotency_key_hash=_formal_job_key_hash(command.demo_actor_id, key_hash),
                    request_id=command.request_id,
                    payload={},
                    owner_user_id=None,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
                binding = _authority_row(
                    DemoJobBinding,
                    row_id=binding_id,
                    schema_version=DEMO_JOB_BINDING_SCHEMA,
                    created_at=now,
                    fields=_job_binding_payload(
                        demo_actor_id=command.demo_actor_id,
                        demo_session_id=command.demo_session_id,
                        job_id=job_id,
                        idempotency_key_hash_value=key_hash,
                        request_digest=request_digest,
                        target_id=request_id,
                    ),
                )
                try:
                    async with session.begin_nested():
                        session.add(job)
                        await session.flush()
                        session.add(request)
                        await session.flush()
                        session.add(binding)
                        await session.flush()
                except IntegrityError as exc:
                    winner = await self._binding_for_key(session, command.demo_actor_id, key_hash)
                    if winner is None:
                        raise DemoSelfTransferAuthorityCorruption(
                            "CREATE_CONFLICT_WITHOUT_WINNER",
                            "stepped self-transfer admission conflict has no winner",
                        ) from exc
                    return await self._replay_stepped_create(session, winner, request_digest)
                return DemoSelfTransferRequestAccepted(
                    job.id,
                    request.id,
                    command.demo_session_id,
                    command.selection.execution_delta_ppm,
                    False,
                )

    async def reserve(
        self, *, demo_actor_id: str, request_run_id: str
    ) -> DemoSelfTransferReservation:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(request_run_id, "request_run_id")
        async with self._sessions() as session:
            async with session.begin():
                request, binding, job = await self._request_execution_context(
                    session,
                    demo_actor_id=demo_actor_id,
                    request_run_id=request_run_id,
                    lock_job=True,
                )
                if job.status == "RUNNING":
                    attempt = await self._current_attempt(session, job)
                    if attempt.status != "RUNNING" or attempt.finished_at is not None:
                        raise DemoSelfTransferAuthorityCorruption(
                            "RUNNING_ATTEMPT_INVALID",
                            "RUNNING self-transfer Job has an invalid current attempt",
                        )
                    return DemoSelfTransferReservation(
                        job.id, request.id, attempt.id, attempt.attempt, True
                    )
                if job.status != "PENDING" or job.attempt_count != 0:
                    raise DemoSelfTransferConflict(
                        "JOB_NOT_RESERVABLE", "self-transfer Job is not PENDING"
                    )
                now = self._normalized_now()
                attempt = JobAttempt(
                    id=new_id(),
                    job_id=job.id,
                    attempt=1,
                    status="RUNNING",
                    started_at=now,
                )
                session.add(attempt)
                job.status = "RUNNING"
                job.attempt_count = 1
                job.updated_at = now
                await session.flush()
                _validate_job_binding(binding, job, request)
                return DemoSelfTransferReservation(job.id, request.id, attempt.id, 1, False)

    async def finalize(
        self, command: FinalizeDemoSelfTransferResult
    ) -> DemoSelfTransferResultAccepted:
        command.validate()
        async with self._sessions() as session:
            async with session.begin():
                return await self.finalize_in_session(session, command)

    async def finalize_in_session(
        self, session: AsyncSession, command: FinalizeDemoSelfTransferResult
    ) -> DemoSelfTransferResultAccepted:
        """Finalize in a caller-owned transaction (used by D09/D06 acceptance)."""

        command.validate()
        request, binding, job = await self._request_execution_context(
            session,
            demo_actor_id=command.demo_actor_id,
            request_run_id=command.request_run_id,
            lock_job=True,
        )
        existing = await self._result_for_binding(session, binding.id)
        if existing is not None:
            return await self._replay_result(session, command, request, binding, job, existing)
        if job.status != "RUNNING" or job.attempt_count != 1:
            raise DemoSelfTransferConflict(
                "JOB_NOT_RUNNING", "self-transfer Job must be RUNNING before finalization"
            )
        attempt = await self._current_attempt(session, job)
        if attempt.status != "RUNNING" or attempt.finished_at is not None:
            raise DemoSelfTransferAuthorityCorruption(
                "RUNNING_ATTEMPT_INVALID", "self-transfer Job attempt is not RUNNING"
            )
        profile = await session.get(DemoDesiredDeltaProfile, request.desired_delta_profile_id)
        if profile is None:
            raise DemoSelfTransferAuthorityCorruption(
                "PROFILE_MISSING", "self-transfer DesiredDeltaProfile is missing"
            )
        requested = _requested_dimension(request)
        desired = _desired_dimension(profile, requested.dimension_key)
        if request.schema_version == DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA:
            if command.user_outcome == "ACCEPTED" and command.final_save_episode_id is None:
                raise DemoSelfTransferInputError(
                    "FINAL_SAVE_EPISODE_REQUIRED",
                    "accepted stepped self-transfer requires a Final Save episode",
                )
            stepped = _stepped_envelope(request)
            if command.result_image_version_id != _stepped_result_image_id(request):
                raise DemoSelfTransferConflict(
                    "STEPPED_RESULT_SUBSTITUTION",
                    "stepped finalization requires its exact ImageVersion",
                )
            if desired.desired_delta_ppm != stepped.profile_desired_delta_ppm:
                raise DemoSelfTransferAuthorityCorruption(
                    "REQUEST_PROFILE_MISMATCH", "stepped request differs from DesiredDeltaProfile"
                )
            expected_projection = _DesiredDimension(
                stepped.dimension_key,
                stepped.execution_delta_ppm,
                desired.confidence_ppm,
            )
            await self._require_stepped_execution(session, request=request, profile=profile)
        else:
            if desired.desired_delta_ppm != requested.desired_delta_ppm:
                raise DemoSelfTransferAuthorityCorruption(
                    "REQUEST_PROFILE_MISMATCH",
                    "self-transfer request differs from DesiredDeltaProfile",
                )
            expected_projection = desired
        if command.user_outcome == "ACCEPTED":
            await self._require_unclaimed_dimension(
                session,
                actor_id=request.demo_actor_id,
                session_id=request.demo_session_id,
                self_state_id=profile.self_state_id,
                dimension_key=desired.dimension_key,
            )
        image, verifier = await self._published_result(
            session,
            request=request,
            profile=profile,
            image_version_id=command.result_image_version_id,
        )
        if command.final_save_episode_id is not None:
            await self._require_exact_final_save_episode(
                session,
                episode_id=command.final_save_episode_id,
                request=request,
                image=image,
                verifier=verifier,
            )
        projection = _verified_projection(verifier, expected_projection)
        now = self._normalized_now()
        result_payload = {
            "demo_actor_id": request.demo_actor_id,
            "demo_session_id": request.demo_session_id,
            "desired_delta_profile_id": request.desired_delta_profile_id,
            "record_kind": "RESULT",
            "request_run_id": request.id,
            "demo_job_binding_id": binding.id,
            "source_asset_id": request.source_asset_id,
            "result_asset_id": image.result_asset_id,
            "requested_delta": dict(request.requested_delta),
            "measured_delta": {projection.dimension_key: projection.measured_delta_ppm},
            "non_target_drift": {
                "absolute_ppm": abs(projection.non_target_drift_ppm),
                "signed_ppm": projection.non_target_drift_ppm,
            },
            "verifier_digest": verifier.content_digest,
            "user_outcome": command.user_outcome,
        }
        result = _authority_row(
            DemoSelfTransferRun,
            schema_version=request.schema_version,
            created_at=now,
            fields=result_payload,
        )
        session.add(result)
        await session.flush()
        evidence: DemoSelfTransferDimensionEvidence | None = None
        if command.user_outcome == "ACCEPTED":
            evidence = _authority_row(
                DemoSelfTransferDimensionEvidence,
                schema_version=DEMO_SELF_TRANSFER_EVIDENCE_SCHEMA,
                created_at=now,
                fields={
                    "demo_actor_id": request.demo_actor_id,
                    "demo_session_id": request.demo_session_id,
                    "self_transfer_run_id": result.id,
                    "dimension_key": projection.dimension_key,
                    "desired_delta_ppm": projection.measured_delta_ppm,
                    "confidence_ppm": projection.confidence_ppm,
                    "verifier_outcome": "PASS",
                    "verifier_digest": verifier.content_digest,
                    "projection_version": DEMO_SELF_TRANSFER_PROJECTION_VERSION,
                    "projection_config_digest": DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST,
                },
            )
            session.add(evidence)
            await session.flush()
        result_code = f"SELF_TRANSFER_{command.user_outcome}"
        attempt.status = "COMPLETED"
        attempt.result_code = result_code
        attempt.error_code = None
        attempt.finished_at = now
        job.status = "COMPLETED"
        job.finalized_at = now
        job.result_code = result_code
        job.updated_at = now
        await session.flush()
        return DemoSelfTransferResultAccepted(
            job.id,
            request.id,
            result.id,
            None if evidence is None else evidence.id,
            image.id,
            projection.dimension_key,
            projection.measured_delta_ppm,
            projection.confidence_ppm if evidence is not None else 0,
            command.user_outcome,
            False,
        )

    async def revalidate_stepped_result_in_session(
        self,
        session: AsyncSession,
        *,
        demo_actor_id: str,
        result_run_id: str,
    ) -> DemoSelfTransferRun:
        """Replay accepted v2 evidence for post-commit queue admission.

        The caller owns its transaction/session.  This method is deliberately
        read-only: it exposes no locator or capability and creates no rows.
        """

        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(result_run_id, "result_run_id")
        result = await session.get(DemoSelfTransferRun, result_run_id)
        if (
            result is None
            or result.demo_actor_id != demo_actor_id
            or result.schema_version != DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA
            or result.record_kind != "RESULT"
            or result.user_outcome != "ACCEPTED"
            or result.request_run_id is None
        ):
            raise DemoSelfTransferUnavailable(
                "STEPPED_RESULT_UNAVAILABLE", "accepted stepped self-transfer result is unavailable"
            )
        request = await session.get(DemoSelfTransferRun, result.request_run_id)
        profile = (
            None
            if request is None
            else await session.get(DemoDesiredDeltaProfile, request.desired_delta_profile_id)
        )
        if (
            request is None
            or profile is None
            or request.schema_version != DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA
            or request.record_kind != "REQUEST"
            or request.demo_actor_id != result.demo_actor_id
            or request.demo_session_id != result.demo_session_id
            or request.desired_delta_profile_id != result.desired_delta_profile_id
            or request.requested_delta != result.requested_delta
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_RESULT_REQUEST_INVALID",
                "accepted stepped result cannot replay its immutable request",
            )
        await self._require_stepped_execution(session, request=request, profile=profile)
        image, verifier = await self._published_result(
            session,
            request=request,
            profile=profile,
            image_version_id=_stepped_result_image_id(request),
        )
        if (
            result.result_asset_id != image.result_asset_id
            or result.verifier_digest != verifier.content_digest
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_RESULT_LINEAGE_MISMATCH",
                "accepted stepped result does not match terminal D08 authority",
            )
        return result

    async def compile_reference_profile(
        self, command: CompileDemoReferenceProfile
    ) -> DemoReferenceProfileAccepted:
        command.validate()
        async with self._sessions() as session:
            async with session.begin():
                snapshot = await self.freeze_reference_profile_inputs(session, command)
                return await self.compile_reference_profile_in_session(
                    session,
                    command=command,
                    expected_source_bindings=snapshot.source_bindings,
                    expected_input_digest=snapshot.input_digest,
                )

    async def freeze_reference_profile_inputs(
        self, session: AsyncSession, command: CompileDemoReferenceProfile
    ) -> DemoReferenceProfileInputSnapshot:
        """Recompute the complete byte-free compiler input in the caller's transaction."""
        command.validate()
        sources = tuple(sorted(command.sources, key=lambda item: _VIEW_ORDER[item.view]))
        actor = await session.scalar(
            select(DemoActor).where(DemoActor.id == command.demo_actor_id).with_for_update()
        )
        if actor is None or actor.tombstoned_at is not None:
            raise DemoSelfTransferUnavailable("ACTOR_UNAVAILABLE", "Demo actor is unavailable")
        owner_session = await session.get(DemoSession, command.demo_session_id)
        if (
            owner_session is None
            or owner_session.demo_actor_id != command.demo_actor_id
            or owner_session.tombstoned_at is not None
        ):
            raise DemoSelfTransferUnavailable("SESSION_UNAVAILABLE", "Demo session is unavailable")
        desired, style, constraints = await self._reference_inputs(session, command)
        authorities = tuple(
            [
                await self._accepted_reference_authority(
                    session,
                    actor_id=command.demo_actor_id,
                    session_id=command.demo_session_id,
                    desired_profile_id=desired.id,
                    asset_id=source.asset_id,
                )
                for source in sources
            ]
        )
        source_bindings = tuple(
            {
                "asset_id": authority.source_asset.id,
                "asset_sha256": authority.source_asset.sha256,
                "view": source.view,
                "self_transfer_run_id": authority.transfer_run.id,
                "self_transfer_run_digest": authority.transfer_run.content_digest,
                "image_version_id": authority.image_version.id,
                "image_version_digest": authority.image_version.content_digest,
                "verifier_digest": authority.verifier.content_digest,
                "evidence_digests": [item.content_digest for item in authority.evidence],
            }
            for source, authority in zip(sources, authorities, strict=True)
        )
        input_payload = {
            "desired_delta_profile_digest": desired.content_digest,
            "style_profile_digest": None if style is None else style.content_digest,
            "identity_constraints_digest": None
            if constraints is None
            else constraints.content_digest,
            "source_bindings": list(source_bindings),
            "analysis_version": DEMO_REFERENCE_ANALYSIS_VERSION,
            "compiler_version": DEMO_REFERENCE_COMPILER_VERSION,
        }
        return DemoReferenceProfileInputSnapshot(
            source_bindings=source_bindings,
            input_digest=_authority_digest("mirror.demo/ReferenceProfileInput/v1", input_payload),
        )

    async def compile_reference_profile_in_session(
        self,
        session: AsyncSession,
        *,
        command: CompileDemoReferenceProfile,
        expected_source_bindings: Sequence[Mapping[str, Any]],
        expected_input_digest: str,
    ) -> DemoReferenceProfileAccepted:
        """Materialize a legacy or queued profile without owning the transaction."""
        snapshot = await self.freeze_reference_profile_inputs(session, command)
        if (
            tuple(dict(item) for item in expected_source_bindings) != snapshot.source_bindings
            or expected_input_digest != snapshot.input_digest
        ):
            raise DemoSelfTransferConflict(
                "REFERENCE_INPUT_SNAPSHOT_MISMATCH", "frozen Reference Profile input changed"
            )
        sources = tuple(sorted(command.sources, key=lambda item: _VIEW_ORDER[item.view]))
        desired, style, constraints = await self._reference_inputs(session, command)
        authorities = tuple(
            [
                await self._accepted_reference_authority(
                    session,
                    actor_id=command.demo_actor_id,
                    session_id=command.demo_session_id,
                    desired_profile_id=desired.id,
                    asset_id=source.asset_id,
                )
                for source in sources
            ]
        )
        source_assets = [
            {
                "asset_id": authority.source_asset.id,
                "sha256": authority.source_asset.sha256,
                "view": source.view,
            }
            for source, authority in zip(sources, authorities, strict=True)
        ]
        structured, evidence_digests = _reference_structure(
            desired=desired,
            style=style,
            constraints=constraints,
            sources=sources,
            authorities=authorities,
        )
        existing = await self._matching_reference_profile(
            session,
            actor_id=command.demo_actor_id,
            session_id=command.demo_session_id,
            desired_id=desired.id,
            style_id=None if style is None else style.id,
            constraints_id=None if constraints is None else constraints.id,
            source_assets=source_assets,
            structured_profile=structured,
            evidence_digests=evidence_digests,
        )
        if existing is not None:
            return DemoReferenceProfileAccepted(
                existing.id,
                existing.version,
                existing.content_digest,
                True,
            )
        max_version = await session.scalar(
            select(func.coalesce(func.max(DemoReferenceProfile.version), 0)).where(
                DemoReferenceProfile.demo_actor_id == command.demo_actor_id
            )
        )
        if type(max_version) is not int:
            raise DemoSelfTransferAuthorityCorruption(
                "REFERENCE_VERSION_INVALID", "Reference Profile version is invalid"
            )
        payload = {
            "demo_actor_id": command.demo_actor_id,
            "demo_session_id": command.demo_session_id,
            "desired_delta_profile_id": desired.id,
            "style_profile_id": None if style is None else style.id,
            "identity_constraints_id": None if constraints is None else constraints.id,
            "version": max_version + 1,
            "source_assets": source_assets,
            "analysis_version": DEMO_REFERENCE_ANALYSIS_VERSION,
            "compiler_version": DEMO_REFERENCE_COMPILER_VERSION,
            "structured_profile": structured,
            "evidence_digests": evidence_digests,
        }
        reference = _authority_row(
            DemoReferenceProfile,
            schema_version=DEMO_REFERENCE_PROFILE_SCHEMA,
            created_at=self._normalized_now(),
            fields=payload,
        )
        session.add(reference)
        await session.flush()
        return DemoReferenceProfileAccepted(
            reference.id, reference.version, reference.content_digest, False
        )

    async def _create_context(
        self, session: AsyncSession, command: CreateDemoSelfTransferRequest
    ) -> tuple[DemoDesiredDeltaProfile, Asset]:
        owner_session = await session.get(DemoSession, command.demo_session_id)
        if (
            owner_session is None
            or owner_session.demo_actor_id != command.demo_actor_id
            or owner_session.tombstoned_at is not None
        ):
            raise DemoSelfTransferUnavailable("SESSION_UNAVAILABLE", "Demo session is unavailable")
        profile = await session.get(DemoDesiredDeltaProfile, command.desired_delta_profile_id)
        if (
            profile is None
            or profile.demo_actor_id != command.demo_actor_id
            or profile.demo_session_id != command.demo_session_id
        ):
            raise DemoSelfTransferUnavailable(
                "PROFILE_UNAVAILABLE", "DesiredDeltaProfile is unavailable"
            )
        source = await session.get(Asset, command.source_asset_id)
        if (
            source is None
            or source.deleted_at is not None
            or source.synthetic is not True
            or source.owner_user_id is not None
        ):
            raise DemoSelfTransferUnavailable(
                "SOURCE_ASSET_UNAVAILABLE",
                "self-transfer source must be an available Demo synthetic Asset",
            )
        return profile, source

    async def _create_stepped_context(
        self, session: AsyncSession, command: CreateDemoSteppedSelfTransferRequest
    ) -> tuple[DemoDesiredDeltaProfile, Asset]:
        owner_session = await session.get(DemoSession, command.demo_session_id)
        profile = await session.get(DemoDesiredDeltaProfile, command.desired_delta_profile_id)
        source = await session.get(Asset, command.source_asset_id)
        if (
            owner_session is None
            or owner_session.demo_actor_id != command.demo_actor_id
            or owner_session.tombstoned_at is not None
        ):
            raise DemoSelfTransferUnavailable("SESSION_UNAVAILABLE", "Demo session is unavailable")
        if (
            profile is None
            or profile.demo_actor_id != command.demo_actor_id
            or profile.demo_session_id != command.demo_session_id
        ):
            raise DemoSelfTransferUnavailable(
                "PROFILE_UNAVAILABLE", "DesiredDeltaProfile is unavailable"
            )
        if (
            source is None
            or source.deleted_at is not None
            or source.synthetic is not True
            or source.owner_user_id is not None
        ):
            raise DemoSelfTransferUnavailable(
                "SOURCE_ASSET_UNAVAILABLE", "stepped source must be a Demo synthetic Asset"
            )
        return profile, source

    async def _binding_for_key(
        self, session: AsyncSession, actor_id: str, key_hash: str
    ) -> DemoJobBinding | None:
        return cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.demo_actor_id == actor_id,
                    DemoJobBinding.endpoint_operation == DEMO_SELF_TRANSFER_OPERATION,
                    DemoJobBinding.idempotency_key_hash == key_hash,
                )
            ),
        )

    async def _replay_create(
        self, session: AsyncSession, binding: DemoJobBinding, request_digest: str
    ) -> DemoSelfTransferRequestAccepted:
        if binding.request_digest != request_digest:
            raise DemoSelfTransferConflict(
                "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                "self-transfer idempotency key is bound to another request",
            )
        request = await session.get(DemoSelfTransferRun, binding.target_id)
        job = await session.get(Job, binding.job_id)
        if request is None or job is None:
            raise DemoSelfTransferAuthorityCorruption(
                "CREATE_WINNER_MISSING", "self-transfer create winner is incomplete"
            )
        _validate_job_binding(binding, job, request)
        _, requested_delta = _single_requested_delta(request.requested_delta)
        return DemoSelfTransferRequestAccepted(
            job.id, request.id, request.demo_session_id, requested_delta, True
        )

    async def _replay_stepped_create(
        self, session: AsyncSession, binding: DemoJobBinding, request_digest: str
    ) -> DemoSelfTransferRequestAccepted:
        if binding.request_digest != request_digest:
            raise DemoSelfTransferConflict(
                "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                "stepped self-transfer idempotency key is bound to another request",
            )
        request = await session.get(DemoSelfTransferRun, binding.target_id)
        job = await session.get(Job, binding.job_id)
        if request is None or job is None:
            raise DemoSelfTransferAuthorityCorruption(
                "CREATE_WINNER_MISSING", "stepped self-transfer winner is incomplete"
            )
        _validate_job_binding(binding, job, request)
        profile = await session.get(DemoDesiredDeltaProfile, request.desired_delta_profile_id)
        if profile is None:
            raise DemoSelfTransferAuthorityCorruption(
                "PROFILE_MISSING", "stepped self-transfer profile is missing"
            )
        await self._require_stepped_execution(session, request=request, profile=profile)
        selection = _stepped_envelope(request)
        return DemoSelfTransferRequestAccepted(
            job.id,
            request.id,
            request.demo_session_id,
            selection.execution_delta_ppm,
            True,
        )

    async def _request_execution_context(
        self,
        session: AsyncSession,
        *,
        demo_actor_id: str,
        request_run_id: str,
        lock_job: bool,
    ) -> tuple[DemoSelfTransferRun, DemoJobBinding, Job]:
        request = await session.get(DemoSelfTransferRun, request_run_id)
        if (
            request is None
            or request.demo_actor_id != demo_actor_id
            or request.record_kind != "REQUEST"
        ):
            raise DemoSelfTransferUnavailable(
                "REQUEST_UNAVAILABLE", "self-transfer request is unavailable"
            )
        binding = await session.scalar(
            select(DemoJobBinding).where(
                DemoJobBinding.demo_actor_id == demo_actor_id,
                DemoJobBinding.endpoint_operation == DEMO_SELF_TRANSFER_OPERATION,
                DemoJobBinding.target_type == "SELF_TRANSFER_RUN",
                DemoJobBinding.target_id == request.id,
            )
        )
        if binding is None:
            raise DemoSelfTransferAuthorityCorruption(
                "JOB_BINDING_MISSING", "self-transfer request lacks a Job binding"
            )
        statement = select(Job).where(Job.id == binding.job_id)
        if lock_job:
            statement = statement.with_for_update()
        job = await session.scalar(statement)
        if job is None:
            raise DemoSelfTransferAuthorityCorruption("JOB_MISSING", "self-transfer Job is missing")
        _validate_job_binding(binding, job, request)
        if request.schema_version == DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA:
            _stepped_envelope(request)
        elif request.schema_version != DEMO_SELF_TRANSFER_RUN_SCHEMA:
            raise DemoSelfTransferAuthorityCorruption(
                "REQUEST_SCHEMA_UNSUPPORTED", "self-transfer request schema is unsupported"
            )
        return request, binding, job

    @staticmethod
    async def _current_attempt(session: AsyncSession, job: Job) -> JobAttempt:
        attempt = await session.scalar(
            select(JobAttempt)
            .where(JobAttempt.job_id == job.id, JobAttempt.attempt == job.attempt_count)
            .with_for_update()
        )
        if attempt is None:
            raise DemoSelfTransferAuthorityCorruption(
                "JOB_ATTEMPT_MISSING", "self-transfer Job attempt is missing"
            )
        return attempt

    @staticmethod
    async def _result_for_binding(
        session: AsyncSession, binding_id: str
    ) -> DemoSelfTransferRun | None:
        return cast(
            DemoSelfTransferRun | None,
            await session.scalar(
                select(DemoSelfTransferRun).where(
                    DemoSelfTransferRun.record_kind == "RESULT",
                    DemoSelfTransferRun.demo_job_binding_id == binding_id,
                )
            ),
        )

    async def _replay_result(
        self,
        session: AsyncSession,
        command: FinalizeDemoSelfTransferResult,
        request: Any,
        binding: DemoJobBinding,
        job: Job,
        result: DemoSelfTransferRun,
    ) -> DemoSelfTransferResultAccepted:
        image = await session.get(DemoImageVersion, command.result_image_version_id)
        evidences = tuple(
            await session.scalars(
                select(DemoSelfTransferDimensionEvidence).where(
                    DemoSelfTransferDimensionEvidence.self_transfer_run_id == result.id
                )
            )
        )
        expected_evidence_count = 1 if command.user_outcome == "ACCEPTED" else 0
        if (
            image is None
            or result.request_run_id != request.id
            or result.demo_job_binding_id != binding.id
            or result.result_asset_id != image.result_asset_id
            or result.verifier_digest != image.verifier_digest
            or result.user_outcome != command.user_outcome
            or len(evidences) != expected_evidence_count
            or job.status != "COMPLETED"
            or job.finalized_at is None
        ):
            raise DemoSelfTransferConflict(
                "FINALIZATION_REPLAY_CONFLICT",
                "self-transfer finalization differs from the immutable winner",
            )
        if request.schema_version == DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA:
            if command.user_outcome == "ACCEPTED" and command.final_save_episode_id is None:
                raise DemoSelfTransferInputError(
                    "FINAL_SAVE_EPISODE_REQUIRED",
                    "accepted stepped self-transfer replay requires a Final Save episode",
                )
            profile = await session.get(DemoDesiredDeltaProfile, request.desired_delta_profile_id)
            if profile is None:
                raise DemoSelfTransferAuthorityCorruption(
                    "PROFILE_MISSING", "stepped self-transfer replay profile is missing"
                )
            await self._require_stepped_execution(session, request=request, profile=profile)
        if command.final_save_episode_id is not None:
            verifier = await session.scalar(
                select(DemoVerificationResult).where(
                    DemoVerificationResult.content_digest == image.verifier_digest
                )
            )
            if verifier is None:
                raise DemoSelfTransferAuthorityCorruption(
                    "VERIFIER_MISSING", "self-transfer replay verifier is missing"
                )
            await self._require_exact_final_save_episode(
                session,
                episode_id=command.final_save_episode_id,
                request=request,
                image=image,
                verifier=verifier,
            )
        attempt = await self._current_attempt(session, job)
        if attempt.status != "COMPLETED" or attempt.finished_at is None:
            raise DemoSelfTransferAuthorityCorruption(
                "TERMINAL_ATTEMPT_INVALID", "completed self-transfer attempt is invalid"
            )
        if result.schema_version != request.schema_version:
            raise DemoSelfTransferAuthorityCorruption(
                "RESULT_SCHEMA_MISMATCH", "self-transfer result schema differs from request"
            )
        if request.schema_version == DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA and (
            command.result_image_version_id != _stepped_result_image_id(request)
            or result.requested_delta != request.requested_delta
            or _stepped_envelope(result) != _stepped_envelope(request)
        ):
            raise DemoSelfTransferConflict(
                "FINALIZATION_REPLAY_CONFLICT",
                "stepped self-transfer finalization differs from the immutable winner",
            )
        if request.schema_version == DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA:
            profile = await session.get(DemoDesiredDeltaProfile, request.desired_delta_profile_id)
            if profile is None:
                raise DemoSelfTransferAuthorityCorruption(
                    "PROFILE_MISSING", "stepped self-transfer replay profile is missing"
                )
            await self._require_stepped_execution(session, request=request, profile=profile)
        measured = result.measured_delta
        dimension_key = _requested_dimension(request).dimension_key
        measured_delta = None if measured is None else measured.get(dimension_key)
        if not _is_ppm(measured_delta):
            raise DemoSelfTransferAuthorityCorruption(
                "RESULT_EVIDENCE_MISMATCH", "self-transfer result/evidence mismatch"
            )
        evidence = evidences[0] if evidences else None
        if evidence is not None and (
            evidence.dimension_key != dimension_key or evidence.desired_delta_ppm != measured_delta
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "RESULT_EVIDENCE_MISMATCH", "self-transfer result/evidence mismatch"
            )
        return DemoSelfTransferResultAccepted(
            job.id,
            request.id,
            result.id,
            None if evidence is None else evidence.id,
            image.id,
            dimension_key,
            cast(int, measured_delta),
            0 if evidence is None else evidence.confidence_ppm,
            command.user_outcome,
            True,
        )

    @staticmethod
    async def _require_unclaimed_dimension(
        session: AsyncSession,
        *,
        actor_id: str,
        session_id: str,
        self_state_id: str,
        dimension_key: str,
    ) -> None:
        lock_key = (
            "mirror.demo.self-transfer-dimension/"
            f"{actor_id}/{session_id}/{self_state_id}/{dimension_key}"
        )
        await session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
        )
        existing = await session.scalar(
            select(DemoSelfTransferDimensionEvidence.id)
            .join(
                DemoSelfTransferRun,
                DemoSelfTransferRun.id == DemoSelfTransferDimensionEvidence.self_transfer_run_id,
            )
            .join(
                DemoDesiredDeltaProfile,
                DemoDesiredDeltaProfile.id == DemoSelfTransferRun.desired_delta_profile_id,
            )
            .where(
                DemoSelfTransferDimensionEvidence.demo_actor_id == actor_id,
                DemoSelfTransferDimensionEvidence.demo_session_id == session_id,
                DemoSelfTransferDimensionEvidence.dimension_key == dimension_key,
                DemoSelfTransferRun.record_kind == "RESULT",
                DemoSelfTransferRun.user_outcome == "ACCEPTED",
                DemoDesiredDeltaProfile.self_state_id == self_state_id,
            )
            .limit(1)
        )
        if existing is not None:
            raise DemoSelfTransferConflict(
                "ACCEPTED_DIMENSION_AUTHORITY_EXISTS",
                "an accepted self-transfer authority already owns this SelfState dimension",
            )

    @staticmethod
    async def _published_result(
        session: AsyncSession,
        *,
        request: DemoSelfTransferRun,
        profile: DemoDesiredDeltaProfile,
        image_version_id: str,
    ) -> tuple[DemoImageVersion, DemoVerificationResult]:
        image = await session.get(DemoImageVersion, image_version_id)
        if (
            image is None
            or image.demo_actor_id != request.demo_actor_id
            or image.demo_session_id != request.demo_session_id
            or image.version_kind != "EDITED"
            or image.verifier_digest is None
        ):
            raise DemoSelfTransferUnavailable(
                "PUBLISHED_IMAGE_UNAVAILABLE",
                "self-transfer requires an owner-bound published edited ImageVersion",
            )
        editing = await session.get(DemoEditingSession, image.editing_session_id)
        if (
            editing is None
            or editing.demo_actor_id != request.demo_actor_id
            or editing.demo_session_id != request.demo_session_id
            or editing.source_asset_id != request.source_asset_id
            or editing.desired_delta_profile_digest != profile.content_digest
        ):
            raise DemoSelfTransferConflict(
                "EDITING_LINEAGE_MISMATCH",
                "published ImageVersion does not belong to the self-transfer request",
            )
        verifier = await session.scalar(
            select(DemoVerificationResult).where(
                DemoVerificationResult.content_digest == image.verifier_digest
            )
        )
        if (
            verifier is None
            or verifier.demo_actor_id != request.demo_actor_id
            or verifier.demo_session_id != request.demo_session_id
            or verifier.image_version_id != image.id
            or verifier.output_asset_id != image.result_asset_id
            or verifier.output_asset_sha256 != image.result_asset_sha256
            or verifier.outcome != "PASS"
        ):
            raise DemoSelfTransferConflict(
                "VERIFIER_AUTHORITY_MISMATCH",
                "published ImageVersion lacks a matching PASS verifier",
            )
        result_asset = await session.get(Asset, image.result_asset_id)
        if (
            result_asset is None
            or result_asset.deleted_at is not None
            or result_asset.synthetic is not True
            or result_asset.sha256 != image.result_asset_sha256
        ):
            raise DemoSelfTransferUnavailable(
                "RESULT_ASSET_UNAVAILABLE", "published result Asset is unavailable"
            )
        return image, verifier

    async def _require_stepped_execution(
        self,
        session: AsyncSession,
        *,
        request: DemoSelfTransferRun,
        profile: DemoDesiredDeltaProfile,
    ) -> None:
        """Replay the terminal D08 execution and its selected public case."""

        selection = await self._revalidate_stepped_selection(
            session, request=request, profile=profile
        )
        result_image_version_id = _stepped_result_image_id(request)
        execution_job_id = _stepped_execution_job_id(request)
        image, verifier = await self._published_result(
            session,
            request=request,
            profile=profile,
            image_version_id=result_image_version_id,
        )
        editing = await session.get(DemoEditingSession, image.editing_session_id)
        profile_dimension = _desired_dimension(profile, selection.dimension_key)
        if (
            editing is None
            or profile_dimension.desired_delta_ppm != selection.profile_desired_delta_ppm
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_PROFILE_OR_RESULT_MISMATCH",
                "stepped profile or published result cannot replay",
            )
        projection = _verified_projection(
            verifier,
            _DesiredDimension(
                selection.dimension_key,
                selection.execution_delta_ppm,
                _PPM,
            ),
        )
        if projection.requested_delta_ppm != selection.execution_delta_ppm:
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_VERIFIER_MISMATCH", "verifier request differs from selected step"
            )
        tool = await session.get(DemoToolRun, verifier.tool_run_id)
        binding = (
            None if tool is None else await session.get(DemoJobBinding, tool.demo_job_binding_id)
        )
        job = None if binding is None else await session.get(Job, binding.job_id)
        operation = (
            None if tool is None else await session.get(DemoEditOperation, tool.edit_operation_id)
        )
        plan = None if binding is None else await session.get(DemoEditPlan, binding.target_id)
        if (
            tool is None
            or binding is None
            or job is None
            or operation is None
            or plan is None
            or tool.demo_actor_id != request.demo_actor_id
            or tool.demo_session_id != request.demo_session_id
            or tool.content_digest != image.tool_run_digest
            or tool.demo_job_binding_id != binding.id
            or tool.edit_operation_digest != operation.content_digest
            or tool.outcome != "COMPLETED"
            or tool.output_asset_id is not None
            or tool.output_asset_sha256 is not None
            or binding.job_id != execution_job_id
            or binding.demo_actor_id != request.demo_actor_id
            or binding.demo_session_id != request.demo_session_id
            or binding.endpoint_operation != "edit_plan.execute"
            or binding.target_type != "EDIT_PLAN"
            or job.id != execution_job_id
            or job.job_type != "demo_p3_p7.edit_plan.execute"
            or plan.id != binding.target_id
            or plan.record_kind != "RESULT"
            or plan.demo_actor_id != request.demo_actor_id
            or plan.demo_session_id != request.demo_session_id
            or plan.editing_session_id != image.editing_session_id
            or plan.desired_delta_profile_digest != profile.content_digest
            or plan.instruction_digest != editing.instruction_digest
            or operation.demo_actor_id != request.demo_actor_id
            or operation.demo_session_id != request.demo_session_id
            or operation.edit_plan_id != plan.id
            or operation.engine != "GEOMETRY"
            or operation.parameters.get("dimension_key") != selection.dimension_key
            or operation.parameters.get("delta_ppm") != selection.execution_delta_ppm
            or job.status != "COMPLETED"
            or job.finalized_at is None
            or job.result_code != "EDIT_EXECUTION_COMPLETED"
        ):
            raise DemoSelfTransferUnavailable(
                "STEPPED_EXECUTION_UNAVAILABLE", "exact terminal D08 execution is unavailable"
            )
        geometry_metrics = (
            verifier.metrics.get("geometry_verification")
            if isinstance(verifier.metrics, Mapping)
            else None
        )
        case_id = geometry_metrics.get("case_id") if isinstance(geometry_metrics, Mapping) else None
        matches: list[Mapping[str, Any]] = []
        d02_authority = await self._stepped_d02_report(session, request=request)
        reports = (d02_authority.report,)
        direction = "INCREASE" if selection.execution_delta_ppm > 0 else "DECREASE"
        for report in reports:
            cases = (
                report.report_payload.get("ordered_case_manifest")
                if isinstance(report.report_payload, Mapping)
                else None
            )
            if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
                continue
            matches.extend(
                value
                for value in cases
                if isinstance(value, Mapping)
                and value.get("record_digest") == selection.selected_case_digest
                and value.get("case_id") == case_id
                and value.get("source_asset_id") == request.source_asset_id
                and value.get("dimension_key") == selection.dimension_key
                and value.get("direction") == direction
                and value.get("magnitude_ppm") == abs(selection.execution_delta_ppm)
                and selection.dimension_key in report.selected_dimension_keys
            )
        if len(matches) != 1:
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_SELECTED_CASE_MISMATCH", "selected D08 case cannot replay exactly"
            )
        stable_core = (
            verifier.metrics.get("geometry_execution", {}).get("stable_core")
            if isinstance(verifier.metrics, Mapping)
            and isinstance(verifier.metrics.get("geometry_execution"), Mapping)
            else None
        )
        match = matches[0]
        source = await session.get(Asset, request.source_asset_id)
        if (
            not isinstance(verifier.canonical_payload, Mapping)
            or verifier.content_digest
            != _authority_digest(verifier.schema_version, verifier.canonical_payload)
            or not isinstance(stable_core, Mapping)
            or not isinstance(geometry_metrics, Mapping)
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_VERIFIER_CANONICAL_INVALID",
                "terminal verifier authority cannot replay canonically",
            )
        try:
            from mirror_api.demo_d08_geometry_adapter import (
                GeometryAdapterAuthorityError,
                GeometryStableMaterializationCore,
            )

            core = GeometryStableMaterializationCore(
                **{key: value for key, value in stable_core.items() if key != "schema_version"}
            )
        except (GeometryAdapterAuthorityError, TypeError, ValueError) as exc:
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_STABLE_CORE_INVALID",
                "terminal D08 stable core cannot replay",
            ) from exc
        if (
            stable_core.get("case_record_digest") != selection.selected_case_digest
            or stable_core.get("case_id") != match.get("case_id")
            or stable_core.get("root_source_asset_id") != request.source_asset_id
            or source is None
            or stable_core.get("root_source_asset_sha256") != source.sha256
            or stable_core.get("operation_id") != operation.id
            or stable_core.get("operation_authority_digest") != operation.content_digest
            or geometry_metrics.get("stable_core_digest") != core.stable_core_digest
            or geometry_metrics.get("authority_digest") != core.authority_digest
            or geometry_metrics.get("case_id") != core.case_id
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_STABLE_CORE_MISMATCH",
                "terminal D08 stable core does not bind the selected case",
            )

    async def _revalidate_stepped_selection(
        self,
        session: AsyncSession,
        *,
        request: DemoSelfTransferRun,
        profile: DemoDesiredDeltaProfile,
    ) -> DemoProfileGeometrySelection:
        """Rebuild the frozen selector from public D05/D02 authority facts."""

        selection = _stepped_envelope(request)
        d02_authority = await self._stepped_d02_report(session, request=request)
        report = d02_authority.report
        persistent, override = await self._stepped_constraints(session, request=request)
        prohibited = set(persistent.prohibited_operations)
        if override is not None:
            prohibited.update(override.prohibited_operations)
        dimensions: list[DemoProfileGeometryDimension] = []
        for dimension_key in profile.dimensions:
            if not isinstance(dimension_key, str):
                raise DemoSelfTransferAuthorityCorruption(
                    "PROFILE_DIMENSION_INVALID", "DesiredDeltaProfile dimension key is invalid"
                )
            desired = _desired_dimension(profile, dimension_key)
            restraint = profile.restraint.get(dimension_key)
            if restraint is None:
                raw_dimension = profile.dimensions.get(dimension_key)
                restraint = (
                    raw_dimension.get("restraint") if isinstance(raw_dimension, Mapping) else None
                )
            if not isinstance(restraint, str):
                raise DemoSelfTransferAuthorityCorruption(
                    "PROFILE_RESTRAINT_INVALID", "DesiredDeltaProfile restraint is invalid"
                )
            persistent_mode = _constraint_mode(persistent.locks, dimension_key)
            override_mode = (
                None if override is None else _constraint_mode(override.locks, dimension_key)
            )
            dimensions.append(
                DemoProfileGeometryDimension(
                    dimension_key=dimension_key,
                    desired_delta_ppm=desired.desired_delta_ppm,
                    confidence_ppm=desired.confidence_ppm,
                    restraint=restraint,
                    geometry_prohibited="GEOMETRY" in prohibited,
                    d02_selected_dimension=dimension_key in report.selected_dimension_keys,
                    persistent_preserve_lock=persistent_mode == "PRESERVE",
                    current_session_allow_change=override_mode == "ALLOW_CHANGE",
                )
            )
        cases = await self._stepped_cases(
            session,
            request=request,
            authority=d02_authority,
        )
        try:
            selected = select_profile_guided_geometry_step(
                dimensions=dimensions,
                cases=cases,
                policy_version=selection.selection_policy_version,
                policy_digest=selection.selection_policy_digest,
            )
        except DemoProfileGeometrySelectionError as exc:
            raise DemoSelfTransferAuthorityCorruption(exc.code, str(exc)) from exc
        if selected != selection:
            raise DemoSelfTransferConflict(
                "STEPPED_SELECTOR_MISMATCH",
                "stepped request does not equal the authoritative selector result",
            )
        return selected

    @staticmethod
    async def _stepped_constraints(
        session: AsyncSession, *, request: DemoSelfTransferRun
    ) -> tuple[DemoIdentityConstraints, DemoIdentityConstraints | None]:
        persistent = await session.scalar(
            select(DemoIdentityConstraints)
            .where(
                DemoIdentityConstraints.demo_actor_id == request.demo_actor_id,
                DemoIdentityConstraints.constraint_scope == "PERSISTENT",
            )
            .order_by(DemoIdentityConstraints.version.desc(), DemoIdentityConstraints.id.desc())
            .limit(1)
        )
        override = await session.scalar(
            select(DemoIdentityConstraints)
            .where(
                DemoIdentityConstraints.demo_actor_id == request.demo_actor_id,
                DemoIdentityConstraints.demo_session_id == request.demo_session_id,
                DemoIdentityConstraints.constraint_scope == "SESSION_OVERRIDE",
            )
            .order_by(DemoIdentityConstraints.version.desc(), DemoIdentityConstraints.id.desc())
            .limit(1)
        )
        if persistent is None:
            raise DemoSelfTransferUnavailable(
                "CONSTRAINTS_UNAVAILABLE", "persistent identity constraints are unavailable"
            )
        return persistent, override

    @staticmethod
    async def _stepped_d02_report(
        session: AsyncSession, *, request: DemoSelfTransferRun
    ) -> _SteppedD02Authority:
        """Resolve one generic D02 source → manifest → admission → report chain."""

        from mirror_api import demo_d02_generic_admission as d02_generic
        from mirror_api import demo_d02_generic_screening as d02_screening
        from mirror_api import demo_d02_source_acquisition as d02_acquisition
        from mirror_api.demo_editing_repository import (
            DemoEditingRepositoryError,
            SqlAlchemyDemoEditingRepository,
            _canonical_authority_matches,
        )

        source = await session.get(Asset, request.source_asset_id)
        if source is None:
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_SOURCE_MISMATCH", "stepped source authority is inconsistent"
            )
        try:
            await SqlAlchemyDemoEditingRepository._require_generic_d02_source_authority(
                session, source
            )
        except DemoEditingRepositoryError as exc:
            raise DemoSelfTransferUnavailable(exc.code, str(exc)) from exc
        authorities = tuple(
            await session.scalars(
                select(DemoD02R2SourceAuthority)
                .where(
                    DemoD02R2SourceAuthority.source_asset_id == source.id,
                    DemoD02R2SourceAuthority.source_asset_sha256 == source.sha256,
                    DemoD02R2SourceAuthority.schema_version == d02_generic.SOURCE_SCHEMA,
                )
                .with_for_update()
            )
        )
        if len(authorities) != 1 or authorities[0].selected_source_manifest_id is None:
            raise DemoSelfTransferUnavailable(
                "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 selected source authority is unavailable"
            )
        manifest = await session.scalar(
            select(D02SelectedSourceManifest)
            .where(
                D02SelectedSourceManifest.id == authorities[0].selected_source_manifest_id,
                D02SelectedSourceManifest.schema_version
                == d02_acquisition.SELECTED_SOURCE_MANIFEST_SCHEMA,
                D02SelectedSourceManifest.manifest_state == "FINALIZED",
            )
            .with_for_update()
        )
        admission = await session.scalar(
            select(DemoD02R2Epoch2Admission)
            .where(
                DemoD02R2Epoch2Admission.selected_source_manifest_id
                == authorities[0].selected_source_manifest_id,
                DemoD02R2Epoch2Admission.schema_version == d02_generic.ADMISSION_SCHEMA,
                DemoD02R2Epoch2Admission.admission_state == "COMPLETED",
            )
            .with_for_update()
        )
        report = (
            None
            if admission is None
            else await session.scalar(
                select(DemoPairScreeningReport)
                .where(
                    DemoPairScreeningReport.id == admission.screening_report_id,
                    DemoPairScreeningReport.schema_version == d02_screening.REPORT_SCHEMA,
                    DemoPairScreeningReport.status == "PASSED",
                    DemoPairScreeningReport.report_digest == admission.screening_report_digest,
                )
                .with_for_update()
            )
        )
        if (
            manifest is None
            or admission is None
            or report is None
            or not _canonical_authority_matches(
                manifest, d02_acquisition.SELECTED_SOURCE_MANIFEST_SCHEMA
            )
            or not _canonical_authority_matches(admission, d02_generic.ADMISSION_SCHEMA)
            or not _canonical_authority_matches(report, d02_screening.REPORT_SCHEMA)
            or report.selected_pair_manifest_digest != admission.selected_pair_manifest_digest
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "D02_REPORT_AUTHORITY_UNAVAILABLE", "D02 screening authority cannot replay"
            )
        return _SteppedD02Authority(
            admission=admission,
            report=cast(DemoPairScreeningReport, report),
        )

    @staticmethod
    async def _stepped_cases(
        session: AsyncSession,
        *,
        request: DemoSelfTransferRun,
        authority: _SteppedD02Authority,
    ) -> tuple[DemoProfileGeometryCase, ...]:
        from mirror_api.demo_d08_geometry_authority import _is_selected_question_pair_side

        report = authority.report
        cases = report.report_payload.get("ordered_case_manifest")
        if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
            raise DemoSelfTransferAuthorityCorruption(
                "D02_CASE_MANIFEST_INVALID", "D02 case manifest is invalid"
            )
        source = await session.get(Asset, request.source_asset_id)
        if source is None:
            raise DemoSelfTransferAuthorityCorruption(
                "D02_CASE_AUTHORITY_UNAVAILABLE", "D02 selected case authority is unavailable"
            )
        output: list[DemoProfileGeometryCase] = []
        for raw in cases:
            if not isinstance(raw, Mapping):
                raise DemoSelfTransferAuthorityCorruption(
                    "D02_CASE_MANIFEST_INVALID", "D02 case entry is invalid"
                )
            if (
                raw.get("source_asset_id") != source.id
                or raw.get("source_asset_sha256") != source.sha256
            ):
                continue
            dimension = raw.get("dimension_key")
            direction = raw.get("direction")
            magnitude = raw.get("magnitude_ppm")
            digest = raw.get("record_digest")
            if (
                not isinstance(dimension, str)
                or direction not in {"INCREASE", "DECREASE"}
                or type(magnitude) is not int
                or not isinstance(digest, str)
            ):
                raise DemoSelfTransferAuthorityCorruption(
                    "D02_CASE_MANIFEST_INVALID", "D02 case fields are invalid"
                )
            selected = await _is_selected_question_pair_side(
                session,
                admission=authority.admission,
                report=report,
                root=source,
                case=raw,
                dimension=dimension,
                direction=direction,
                magnitude_ppm=magnitude,
            )
            output.append(
                DemoProfileGeometryCase(dimension, direction, magnitude, digest, selected)
            )
        return tuple(output)

    @staticmethod
    async def _require_exact_final_save_episode(
        session: AsyncSession,
        *,
        episode_id: str,
        request: DemoSelfTransferRun,
        image: DemoImageVersion,
        verifier: DemoVerificationResult,
    ) -> None:
        episode = await session.scalar(
            select(DemoAcceptedVisualEpisode)
            .where(
                DemoAcceptedVisualEpisode.id == episode_id,
                DemoAcceptedVisualEpisode.demo_actor_id == request.demo_actor_id,
                DemoAcceptedVisualEpisode.demo_session_id == request.demo_session_id,
                DemoAcceptedVisualEpisode.accepted_image_version_id == image.id,
                DemoAcceptedVisualEpisode.verification_result_id == verifier.id,
            )
            .with_for_update()
        )
        if episode is None:
            raise DemoSelfTransferConflict(
                "FINAL_SAVE_EPISODE_MISMATCH",
                "self-transfer acceptance requires the exact Final Save episode",
            )

    async def _require_stepped_command_execution(
        self,
        session: AsyncSession,
        *,
        command: CreateDemoSteppedSelfTransferRequest,
        profile: DemoDesiredDeltaProfile,
        source: Asset,
    ) -> None:
        """Revalidate a create command through the same immutable v2 envelope."""

        provisional = _authority_row(
            DemoSelfTransferRun,
            row_id="0" * 32,
            schema_version=DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA,
            created_at=self._normalized_now(),
            fields=_stepped_request_fields(command),
        )
        if provisional.source_asset_id != source.id:
            raise DemoSelfTransferAuthorityCorruption(
                "STEPPED_SOURCE_MISMATCH", "stepped source cannot replay"
            )
        await self._require_stepped_execution(session, request=provisional, profile=profile)

    @staticmethod
    async def _reference_inputs(
        session: AsyncSession, command: CompileDemoReferenceProfile
    ) -> tuple[
        DemoDesiredDeltaProfile,
        DemoStyleProfile | None,
        DemoIdentityConstraints | None,
    ]:
        desired = await session.get(DemoDesiredDeltaProfile, command.desired_delta_profile_id)
        if (
            desired is None
            or desired.demo_actor_id != command.demo_actor_id
            or desired.demo_session_id != command.demo_session_id
        ):
            raise DemoSelfTransferUnavailable(
                "PROFILE_UNAVAILABLE", "DesiredDeltaProfile is unavailable"
            )
        style = None
        if command.style_profile_id is not None:
            style = await session.get(DemoStyleProfile, command.style_profile_id)
            if (
                style is None
                or style.demo_actor_id != command.demo_actor_id
                or style.demo_session_id not in {None, command.demo_session_id}
                or style.desired_delta_profile_id not in {None, desired.id}
            ):
                raise DemoSelfTransferUnavailable(
                    "STYLE_PROFILE_UNAVAILABLE", "StyleProfile is unavailable"
                )
        constraints = None
        if command.identity_constraints_id is not None:
            constraints = await session.get(
                DemoIdentityConstraints, command.identity_constraints_id
            )
            if (
                constraints is None
                or constraints.demo_actor_id != command.demo_actor_id
                or constraints.demo_session_id not in {None, command.demo_session_id}
                or constraints.self_state_id not in {None, desired.self_state_id}
            ):
                raise DemoSelfTransferUnavailable(
                    "IDENTITY_CONSTRAINTS_UNAVAILABLE",
                    "IdentityConstraints are unavailable",
                )
        return desired, style, constraints

    @staticmethod
    async def _accepted_reference_authority(
        session: AsyncSession,
        *,
        actor_id: str,
        session_id: str,
        desired_profile_id: str,
        asset_id: str,
    ) -> _AcceptedReferenceAuthority:
        source_asset = await session.get(Asset, asset_id)
        if (
            source_asset is None
            or source_asset.deleted_at is not None
            or source_asset.synthetic is not True
        ):
            raise DemoSelfTransferUnavailable(
                "REFERENCE_ASSET_UNAVAILABLE", "reference Asset is unavailable"
            )
        runs = tuple(
            await session.scalars(
                select(DemoSelfTransferRun).where(
                    DemoSelfTransferRun.demo_actor_id == actor_id,
                    DemoSelfTransferRun.demo_session_id == session_id,
                    DemoSelfTransferRun.desired_delta_profile_id == desired_profile_id,
                    DemoSelfTransferRun.record_kind == "RESULT",
                    DemoSelfTransferRun.result_asset_id == asset_id,
                    DemoSelfTransferRun.user_outcome == "ACCEPTED",
                )
            )
        )
        if len(runs) != 1:
            raise DemoSelfTransferConflict(
                "REFERENCE_ACCEPTANCE_AMBIGUOUS",
                "reference Asset must have exactly one accepted self-transfer authority",
            )
        run = runs[0]
        verifier = await session.scalar(
            select(DemoVerificationResult).where(
                DemoVerificationResult.content_digest == run.verifier_digest
            )
        )
        image = await session.scalar(
            select(DemoImageVersion).where(
                DemoImageVersion.demo_actor_id == actor_id,
                DemoImageVersion.demo_session_id == session_id,
                DemoImageVersion.result_asset_id == asset_id,
                DemoImageVersion.verifier_digest == run.verifier_digest,
            )
        )
        evidences = tuple(
            await session.scalars(
                select(DemoSelfTransferDimensionEvidence)
                .where(DemoSelfTransferDimensionEvidence.self_transfer_run_id == run.id)
                .order_by(DemoSelfTransferDimensionEvidence.dimension_key)
            )
        )
        if (
            verifier is None
            or verifier.outcome != "PASS"
            or verifier.output_asset_id != asset_id
            or image is None
            or image.verifier_digest != verifier.content_digest
            or not evidences
            or any(
                evidence.verifier_digest != verifier.content_digest
                or evidence.verifier_outcome != "PASS"
                or evidence.projection_version != DEMO_SELF_TRANSFER_PROJECTION_VERSION
                or evidence.projection_config_digest != DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST
                for evidence in evidences
            )
        ):
            raise DemoSelfTransferAuthorityCorruption(
                "REFERENCE_AUTHORITY_INVALID",
                "accepted self-transfer reference authority is invalid",
            )
        return _AcceptedReferenceAuthority(source_asset, image, run, verifier, evidences)

    @staticmethod
    async def _matching_reference_profile(
        session: AsyncSession,
        *,
        actor_id: str,
        session_id: str,
        desired_id: str,
        style_id: str | None,
        constraints_id: str | None,
        source_assets: list[dict[str, str]],
        structured_profile: dict[str, Any],
        evidence_digests: list[str],
    ) -> DemoReferenceProfile | None:
        rows = tuple(
            await session.scalars(
                select(DemoReferenceProfile).where(
                    DemoReferenceProfile.demo_actor_id == actor_id,
                    DemoReferenceProfile.demo_session_id == session_id,
                    DemoReferenceProfile.desired_delta_profile_id == desired_id,
                    DemoReferenceProfile.analysis_version == DEMO_REFERENCE_ANALYSIS_VERSION,
                    DemoReferenceProfile.compiler_version == DEMO_REFERENCE_COMPILER_VERSION,
                )
            )
        )
        matches = tuple(
            row
            for row in rows
            if row.style_profile_id == style_id
            and row.identity_constraints_id == constraints_id
            and row.source_assets == source_assets
            and row.structured_profile == structured_profile
            and row.evidence_digests == evidence_digests
        )
        if len(matches) > 1:
            raise DemoSelfTransferAuthorityCorruption(
                "DUPLICATE_REFERENCE_AUTHORITY",
                "multiple Reference Profiles represent the same canonical input",
            )
        return matches[0] if matches else None

    def _normalized_now(self) -> datetime:
        now = self._now()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise DemoSelfTransferAuthorityCorruption(
                "INVALID_CLOCK", "D06 clock must be timezone-aware"
            )
        return now.astimezone(UTC)


def _desired_dimension(profile: DemoDesiredDeltaProfile, dimension_key: str) -> _DesiredDimension:
    raw = profile.dimensions.get(dimension_key)
    if isinstance(raw, Mapping):
        key = raw.get("dimension_key")
        delta = raw.get("desired_delta_ppm")
        confidence = raw.get("confidence_ppm")
        if key != dimension_key or not _is_ppm(delta) or not _is_confidence(confidence):
            raise DemoSelfTransferAuthorityCorruption(
                "PROFILE_DIMENSION_INVALID", "DesiredDeltaProfile dimension is invalid"
            )
        return _DesiredDimension(dimension_key, cast(int, delta), cast(int, confidence))
    legacy_key = f"{dimension_key}_ppm"
    legacy = profile.dimensions.get(legacy_key)
    if _is_ppm(legacy):
        return _DesiredDimension(dimension_key, cast(int, legacy), _PPM)
    raise DemoSelfTransferUnavailable(
        "DIMENSION_UNAVAILABLE", "DesiredDeltaProfile does not contain the requested dimension"
    )


def _constraint_mode(value: Mapping[str, Any], dimension_key: str) -> str | None:
    entry = value.get(dimension_key)
    if entry is None:
        return None
    if not isinstance(entry, Mapping) or not isinstance(entry.get("mode"), str):
        raise DemoSelfTransferAuthorityCorruption(
            "CONSTRAINT_LOCK_INVALID", "identity constraint lock is invalid"
        )
    return cast(str, entry["mode"])


def _single_requested_delta(value: Mapping[str, Any]) -> tuple[str, int]:
    if not isinstance(value, Mapping) or len(value) != 1:
        raise DemoSelfTransferAuthorityCorruption(
            "REQUESTED_DELTA_INVALID", "self-transfer request must contain one dimension"
        )
    dimension_key, delta = next(iter(value.items()))
    if not isinstance(dimension_key, str) or _DIMENSION.fullmatch(dimension_key) is None:
        raise DemoSelfTransferAuthorityCorruption(
            "REQUESTED_DIMENSION_INVALID", "self-transfer requested dimension is invalid"
        )
    if not _is_ppm(delta):
        raise DemoSelfTransferAuthorityCorruption(
            "REQUESTED_DELTA_INVALID", "self-transfer requested delta is invalid"
        )
    return dimension_key, cast(int, delta)


def _requested_dimension(row: DemoSelfTransferRun) -> _DesiredDimension:
    if row.schema_version == DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA:
        selection = _stepped_envelope(row)
        return _DesiredDimension(selection.dimension_key, selection.profile_desired_delta_ppm, _PPM)
    dimension_key, desired_delta = _single_requested_delta(row.requested_delta)
    return _DesiredDimension(dimension_key, desired_delta, _PPM)


def _selection_payload(selection: DemoProfileGeometrySelection) -> dict[str, Any]:
    return {
        "dimension_key": selection.dimension_key,
        "profile_desired_delta_ppm": selection.profile_desired_delta_ppm,
        "execution_delta_ppm": selection.execution_delta_ppm,
        "selection_policy_version": selection.selection_policy_version,
        "selection_policy_digest": selection.selection_policy_digest,
        "selected_case_digest": selection.selected_case_digest,
    }


def _stepped_request_fields(command: CreateDemoSteppedSelfTransferRequest) -> dict[str, Any]:
    return {
        "demo_actor_id": command.demo_actor_id,
        "demo_session_id": command.demo_session_id,
        "desired_delta_profile_id": command.desired_delta_profile_id,
        "record_kind": "REQUEST",
        "request_run_id": None,
        "demo_job_binding_id": None,
        "source_asset_id": command.source_asset_id,
        "result_asset_id": None,
        "requested_delta": {
            **_selection_payload(command.selection),
            "execution_job_id": command.execution_job_id,
            "result_image_version_id": command.result_image_version_id,
        },
        "measured_delta": None,
        "non_target_drift": None,
        "verifier_digest": None,
        "user_outcome": None,
    }


def _stepped_envelope(row: DemoSelfTransferRun) -> DemoProfileGeometrySelection:
    raw = row.requested_delta
    required = {
        "dimension_key",
        "profile_desired_delta_ppm",
        "execution_delta_ppm",
        "selection_policy_version",
        "selection_policy_digest",
        "selected_case_digest",
        "execution_job_id",
        "result_image_version_id",
    }
    if row.schema_version != DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA or set(raw) != required:
        raise DemoSelfTransferAuthorityCorruption(
            "STEPPED_ENVELOPE_INVALID", "stepped request envelope is invalid"
        )
    try:
        selection = selection_from_envelope(
            {
                key: raw[key]
                for key in required
                if key not in {"execution_job_id", "result_image_version_id"}
            }
        )
    except DemoProfileGeometrySelectionError as exc:
        raise DemoSelfTransferAuthorityCorruption(exc.code, str(exc)) from exc
    _require_id(raw["execution_job_id"], "execution_job_id")
    _require_id(raw["result_image_version_id"], "result_image_version_id")
    return selection


def _stepped_execution_job_id(row: DemoSelfTransferRun) -> str:
    _stepped_envelope(row)
    value = row.requested_delta["execution_job_id"]
    _require_id(value, "execution_job_id")
    return cast(str, value)


def _stepped_result_image_id(row: DemoSelfTransferRun) -> str:
    _stepped_envelope(row)
    value = row.requested_delta["result_image_version_id"]
    _require_id(value, "result_image_version_id")
    return cast(str, value)


def _verified_projection(
    verifier: DemoVerificationResult, desired: _DesiredDimension
) -> _VerifiedProjection:
    metrics = verifier.metrics
    categories = metrics.get("categories") if isinstance(metrics, Mapping) else None
    if not isinstance(categories, Sequence) or isinstance(categories, (str, bytes)):
        raise DemoSelfTransferAuthorityCorruption(
            "VERIFIER_METRICS_INVALID", "verifier categories are unavailable"
        )
    by_category: dict[str, Mapping[str, Any]] = {}
    for raw in categories:
        if not isinstance(raw, Mapping):
            raise DemoSelfTransferAuthorityCorruption(
                "VERIFIER_METRICS_INVALID", "verifier category is invalid"
            )
        category = raw.get("category")
        if not isinstance(category, str) or category in by_category:
            raise DemoSelfTransferAuthorityCorruption(
                "VERIFIER_METRICS_INVALID", "verifier category authority is ambiguous"
            )
        by_category[category] = raw
    target = by_category.get("TARGET_DELTA")
    drift = by_category.get("NON_TARGET_DRIFT")
    if (
        target is None
        or drift is None
        or target.get("status") != "PASS"
        or drift.get("status") != "PASS"
    ):
        raise DemoSelfTransferAuthorityCorruption(
            "VERIFIER_METRICS_INVALID", "required PASS verifier categories are unavailable"
        )
    target_evidence = target.get("evidence")
    drift_evidence = drift.get("evidence")
    if not isinstance(target_evidence, Mapping) or not isinstance(drift_evidence, Mapping):
        raise DemoSelfTransferAuthorityCorruption(
            "VERIFIER_METRICS_INVALID", "verifier category evidence is invalid"
        )
    dimension = target_evidence.get("target_dimension_key")
    requested = target_evidence.get("requested_delta_ppm")
    measured = target_evidence.get("measured_delta_ppm")
    non_target = drift_evidence.get("drift_ppm")
    if (
        dimension != desired.dimension_key
        or requested != desired.desired_delta_ppm
        or not _is_ppm(measured)
        or not _is_ppm(non_target)
    ):
        raise DemoSelfTransferAuthorityCorruption(
            "VERIFIER_PROJECTION_MISMATCH",
            "verifier integer projection differs from the requested profile",
        )
    measured_int = cast(int, measured)
    confidence = min(
        desired.confidence_ppm,
        max(0, _PPM - abs(desired.desired_delta_ppm - measured_int)),
    )
    return _VerifiedProjection(
        desired.dimension_key,
        desired.desired_delta_ppm,
        measured_int,
        cast(int, non_target),
        confidence,
    )


def _reference_structure(
    *,
    desired: DemoDesiredDeltaProfile,
    style: DemoStyleProfile | None,
    constraints: DemoIdentityConstraints | None,
    sources: tuple[DemoReferenceSource, ...],
    authorities: tuple[_AcceptedReferenceAuthority, ...],
) -> tuple[dict[str, Any], list[str]]:
    dimensions: dict[str, dict[str, Any]] = {}
    evidence_digests = {desired.content_digest}
    if style is not None:
        evidence_digests.add(style.content_digest)
    if constraints is not None:
        evidence_digests.add(constraints.content_digest)
    source_views: list[dict[str, Any]] = []
    for source, authority in zip(sources, authorities, strict=True):
        evidence_digests.update(
            {
                authority.image_version.content_digest,
                authority.transfer_run.content_digest,
                authority.verifier.content_digest,
            }
        )
        source_views.append(
            {
                "asset_id": authority.source_asset.id,
                "image_version_digest": authority.image_version.content_digest,
                "self_transfer_run_digest": authority.transfer_run.content_digest,
                "sha256": authority.source_asset.sha256,
                "verifier_digest": authority.verifier.content_digest,
                "view": source.view,
            }
        )
        for item in authority.evidence:
            current = dimensions.get(item.dimension_key)
            if current is None:
                current = {
                    "confidence_ppm": item.confidence_ppm,
                    "desired_delta_ppm": item.desired_delta_ppm,
                    "evidence_kind": "ACCEPTED_SELF_TRANSFER",
                    "source_run_digests": [authority.transfer_run.content_digest],
                }
                dimensions[item.dimension_key] = current
            elif (
                current["desired_delta_ppm"] != item.desired_delta_ppm
                or current["confidence_ppm"] != item.confidence_ppm
            ):
                raise DemoSelfTransferConflict(
                    "REFERENCE_DIMENSION_CONFLICT",
                    "accepted reference sources disagree on a dimension",
                )
            else:
                run_digests = cast(list[str], current["source_run_digests"])
                run_digests.append(authority.transfer_run.content_digest)
                run_digests.sort()
    if not dimensions:
        raise DemoSelfTransferAuthorityCorruption(
            "REFERENCE_DIMENSIONS_MISSING", "Reference Profile has no accepted dimensions"
        )
    structured: dict[str, Any] = {
        "dimensions": dict(sorted(dimensions.items())),
        "identity_constraints_digest": None if constraints is None else constraints.content_digest,
        "identity_reference_frame": "SELF_STATE_ANCHORED",
        "profile_schema_version": DEMO_REFERENCE_STRUCTURE_SCHEMA,
        "source_views": source_views,
        "style_profile_digest": None if style is None else style.content_digest,
    }
    return structured, sorted(evidence_digests)


def _validate_job_binding(binding: DemoJobBinding, job: Job, request: DemoSelfTransferRun) -> None:
    payload = _job_binding_payload(
        demo_actor_id=request.demo_actor_id,
        demo_session_id=request.demo_session_id,
        job_id=job.id,
        idempotency_key_hash_value=binding.idempotency_key_hash,
        request_digest=binding.request_digest,
        target_id=request.id,
    )
    if (
        binding.schema_version != DEMO_JOB_BINDING_SCHEMA
        or binding.canonical_payload != payload
        or binding.content_digest != _authority_digest(DEMO_JOB_BINDING_SCHEMA, payload)
        or binding.job_id != job.id
        or binding.target_id != request.id
        or binding.target_type != "SELF_TRANSFER_RUN"
        or binding.endpoint_operation != DEMO_SELF_TRANSFER_OPERATION
        or job.job_type != DEMO_SELF_TRANSFER_JOB_TYPE
        or job.idempotency_key_hash
        != _formal_job_key_hash(request.demo_actor_id, binding.idempotency_key_hash)
        or job.owner_user_id is not None
        or job.ingestion_upload_intent_id is not None
        or job.payload != {}
        or job.result_asset_id is not None
        or job.status not in {"PENDING", "RUNNING", "COMPLETED", "REJECTED", "FAILED", "CANCELLED"}
    ):
        raise DemoSelfTransferAuthorityCorruption(
            "JOB_BINDING_INVALID", "self-transfer Job binding authority is invalid"
        )


def _job_binding_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    job_id: str,
    idempotency_key_hash_value: str,
    request_digest: str,
    target_id: str,
) -> dict[str, Any]:
    return {
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "endpoint_operation": DEMO_SELF_TRANSFER_OPERATION,
        "idempotency_key_hash": idempotency_key_hash_value,
        "job_id": job_id,
        "request_digest": request_digest,
        "target_id": target_id,
        "target_type": "SELF_TRANSFER_RUN",
    }


def _formal_job_key_hash(actor_id: str, client_key_hash: str) -> str:
    return hashlib.sha256(
        (
            f"mirror.demo/JobIdempotency/v1\n{actor_id}\n"
            f"{DEMO_SELF_TRANSFER_OPERATION}\n{client_key_hash}"
        ).encode()
    ).hexdigest()


def _authority_row[AuthorityT](
    model: type[AuthorityT],
    /,
    *,
    row_id: str | None = None,
    schema_version: str,
    created_at: datetime,
    fields: Mapping[str, Any],
) -> AuthorityT:
    row = cast(Any, model)(
        id=row_id or new_id(),
        schema_version=schema_version,
        canonical_payload={},
        content_digest="0" * 64,
        created_at=created_at,
        **dict(fields),
    )
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:
        if column.name in _NON_AUTHORITY_COLUMNS:
            continue
        value = getattr(row, column.name)
        payload[column.name] = _canonical_value(value)
    row.canonical_payload = payload
    row.content_digest = _authority_digest(schema_version, payload)
    return cast(AuthorityT, row)


def _authority_digest(schema_version: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return value


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoSelfTransferInputError("INVALID_ID", f"{name} must be a lowercase hexadecimal ID")


def _require_dimension(value: str) -> None:
    if not isinstance(value, str) or _DIMENSION.fullmatch(value) is None:
        raise DemoSelfTransferInputError("INVALID_DIMENSION", "dimension_key is invalid")


def _is_ppm(value: object) -> bool:
    return type(value) is int and -_PPM <= value <= _PPM


def _is_confidence(value: object) -> bool:
    return type(value) is int and 0 <= value <= _PPM


__all__ = [
    "DEMO_REFERENCE_ANALYSIS_VERSION",
    "DEMO_REFERENCE_COMPILER_VERSION",
    "CompileDemoReferenceProfile",
    "CreateDemoSelfTransferRequest",
    "DemoReferenceProfileAccepted",
    "DemoReferenceProfileInputSnapshot",
    "DemoReferenceSource",
    "DemoSelfTransferAuthorityCorruption",
    "DemoSelfTransferConflict",
    "DemoSelfTransferInputError",
    "DemoSelfTransferRequestAccepted",
    "DemoSelfTransferReservation",
    "DemoSelfTransferResultAccepted",
    "DemoSelfTransferService",
    "DemoSelfTransferServiceError",
    "DemoSelfTransferUnavailable",
    "FinalizeDemoSelfTransferResult",
]
