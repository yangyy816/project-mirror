"""D03 application authority for asynchronous synthetic face analysis.

The service deliberately accepts only typed, reference-only runtime evidence.
It does not locate or materialize the frozen M3 runtime.  A live runtime handle
is required only by the Worker adapter that actually produces fresh evidence.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_face_runtime import (
    DimensionObservation,
    FaceObservation,
    FaceRuntimeCompilation,
    compile_face_runtime,
)
from mirror_api.demo_idempotency import (
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DemoAnalysisRun,
    DemoBaselineFaceModel,
    DemoFaceObservation,
    DemoFaceObservationRepeat,
    DemoJobBinding,
    DemoSelfState,
    DemoSession,
    DemoSyntheticIdentity,
)
from mirror_api.models import Job, JobAttempt, new_id, utcnow

DEMO_ANALYSIS_RUN_SCHEMA = "mirror.demo/DemoAnalysisRun/v1"
DEMO_FACE_OBSERVATION_SCHEMA = "mirror.demo/DemoFaceObservation/v2"
DEMO_FACE_OBSERVATION_REPEAT_SCHEMA = "mirror.demo/DemoFaceObservationRepeat/v1"
DEMO_BASELINE_FACE_MODEL_SCHEMA = "mirror.demo/DemoBaselineFaceModel/v1"
DEMO_SELF_STATE_SCHEMA = "mirror.demo/DemoSelfState/v1"
DEMO_JOB_BINDING_SCHEMA = "mirror.demo/DemoJobBinding/v1"
DEMO_ANALYSIS_OPERATION = "analysis.create"
DEMO_ANALYSIS_JOB_TYPE = "demo_p3_p7.analysis.create"
DEMO_ANALYSIS_MAX_ATTEMPTS = 3
DEMO_ANALYSIS_LEASE_EXPIRED = "D03_LEASE_EXPIRED"
DEMO_ANALYSIS_LEASE_RETRY_EXHAUSTED = "D03_LEASE_RETRY_EXHAUSTED"

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^[a-z][a-z0-9._-]{2,63}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_TERMINAL = frozenset({"COMPLETED", "REJECTED", "FAILED", "CANCELLED"})

JobStatus = Literal["PENDING", "RUNNING", "COMPLETED", "REJECTED", "FAILED", "CANCELLED"]
TerminalFailureStatus = Literal["REJECTED", "FAILED"]


class DemoAnalysisError(RuntimeError):
    """Base D03 application failure."""


class DemoAnalysisInputError(DemoAnalysisError):
    """A caller supplied an invalid command or runtime result."""


class DemoAnalysisUnavailable(DemoAnalysisError):
    """The requested actor/session/analysis authority is unavailable."""


class DemoAnalysisPayloadConflict(DemoAnalysisError):
    """An idempotency key is already bound to another semantic request."""

    code = "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

    def __init__(self) -> None:
        super().__init__(self.code)


class DemoAnalysisAuthorityCorruption(DemoAnalysisError):
    """Persisted D03 authority cannot be replayed safely."""


class DemoAnalysisLeaseLost(DemoAnalysisError):
    """A Worker reservation no longer owns the Job."""


@dataclass(frozen=True)
class DemoAnalysisConfiguration:
    analyzer_version: str
    runtime_manifest_digest: str
    model_manifest_digest: str
    observation_config_digest: str
    baseline_aggregation_version: str
    measurement_version: str
    self_state_ontology_version: str
    self_state_derivation_version: str
    lease_seconds: int = 300
    max_attempts: int = DEMO_ANALYSIS_MAX_ATTEMPTS

    def validate(self) -> None:
        for name, value in (
            ("analyzer_version", self.analyzer_version),
            ("baseline_aggregation_version", self.baseline_aggregation_version),
            ("measurement_version", self.measurement_version),
            ("self_state_ontology_version", self.self_state_ontology_version),
            ("self_state_derivation_version", self.self_state_derivation_version),
        ):
            if _VERSION.fullmatch(value) is None:
                raise DemoAnalysisInputError(f"{name} is invalid")
        for name, value in (
            ("runtime_manifest_digest", self.runtime_manifest_digest),
            ("model_manifest_digest", self.model_manifest_digest),
            ("observation_config_digest", self.observation_config_digest),
        ):
            _require_digest(value, name)
        if type(self.lease_seconds) is not int or not 30 <= self.lease_seconds <= 3_600:
            raise DemoAnalysisInputError("lease_seconds must be in [30, 3600]")
        if self.max_attempts != DEMO_ANALYSIS_MAX_ATTEMPTS:
            raise DemoAnalysisInputError("max_attempts must match the frozen D03 retry authority")


@dataclass(frozen=True)
class CreateDemoAnalysis:
    demo_actor_id: str
    demo_session_id: str
    source_asset_id: str
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.demo_session_id, "demo_session_id")
        _require_id(self.source_asset_id, "source_asset_id")
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class DemoAnalysisAccepted:
    job_id: str
    analysis_run_id: str
    demo_session_id: str
    request_id: str
    replayed: bool


@dataclass(frozen=True)
class DemoAnalysisDispatchCandidate:
    analysis_run_id: str
    job_id: str
    request_id: str


@dataclass(frozen=True)
class DemoLandmark:
    x_ppm: int
    y_ppm: int
    z_ppm: int

    def __post_init__(self) -> None:
        for name, value in (("x_ppm", self.x_ppm), ("y_ppm", self.y_ppm), ("z_ppm", self.z_ppm)):
            if type(value) is not int or not -2_000_000 <= value <= 2_000_000:
                raise DemoAnalysisInputError(f"landmark {name} is outside the fixed-point range")

    def payload(self) -> dict[str, int]:
        return {"x_ppm": self.x_ppm, "y_ppm": self.y_ppm, "z_ppm": self.z_ppm}


@dataclass(frozen=True)
class DemoPose:
    yaw_ppm: int
    pitch_ppm: int
    roll_ppm: int

    def __post_init__(self) -> None:
        for name, value in (
            ("yaw_ppm", self.yaw_ppm),
            ("pitch_ppm", self.pitch_ppm),
            ("roll_ppm", self.roll_ppm),
        ):
            if type(value) is not int or not -1_000_000 <= value <= 1_000_000:
                raise DemoAnalysisInputError(f"pose {name} is outside the fixed-point range")

    def payload(self) -> dict[str, int]:
        return {
            "pitch_ppm": self.pitch_ppm,
            "roll_ppm": self.roll_ppm,
            "yaw_ppm": self.yaw_ppm,
        }


@dataclass(frozen=True)
class DemoAnalysisRepeatEvidence:
    repeat_index: int
    evidence_reference: str
    landmarks: tuple[DemoLandmark, ...]
    pose: DemoPose
    dimensions: tuple[DimensionObservation, ...]
    face_count: int = 1

    def __post_init__(self) -> None:
        if type(self.repeat_index) is not int or self.repeat_index not in {1, 2, 3}:
            raise DemoAnalysisInputError("repeat_index must be 1, 2, or 3")
        if len(self.landmarks) != 478:
            raise DemoAnalysisInputError("each D03 repeat must contain exactly 478 landmarks")
        if self.face_count != 1:
            raise DemoAnalysisInputError("each D03 repeat must observe exactly one face")
        try:
            FaceObservation(
                evidence_reference=self.evidence_reference,
                repeat_index=self.repeat_index,
                dimensions=self.dimensions,
            )
        except ValueError as exc:
            raise DemoAnalysisInputError(str(exc)) from exc

    def domain_observation(self) -> FaceObservation:
        return FaceObservation(
            evidence_reference=self.evidence_reference,
            repeat_index=self.repeat_index,
            dimensions=self.dimensions,
        )

    def quality_payload(self) -> dict[str, Any]:
        confidence = {
            entry.dimension: entry.measurement_confidence_ppm
            for entry in sorted(self.dimensions, key=lambda item: item.dimension)
        }
        unsupported = {
            entry.dimension: entry.unsupported_reason
            for entry in sorted(self.dimensions, key=lambda item: item.dimension)
            if entry.unsupported_reason is not None
        }
        return {
            "dimension_confidence_ppm": confidence,
            "evidence_reference": self.evidence_reference,
            "face_count": self.face_count,
            "unsupported_reason": unsupported,
        }

    def measurement_payload(self) -> dict[str, int | None]:
        return {
            entry.dimension: entry.value_ppm
            for entry in sorted(self.dimensions, key=lambda item: item.dimension)
        }


@dataclass(frozen=True)
class DemoAnalysisRuntimeEvidence:
    repeats: tuple[
        DemoAnalysisRepeatEvidence, DemoAnalysisRepeatEvidence, DemoAnalysisRepeatEvidence
    ]

    def compile(self) -> FaceRuntimeCompilation:
        ordered = tuple(sorted(self.repeats, key=lambda item: item.repeat_index))
        if tuple(item.repeat_index for item in ordered) != (1, 2, 3):
            raise DemoAnalysisInputError("runtime evidence must contain repeats 1, 2, and 3")
        if len({item.evidence_reference for item in ordered}) != 3:
            raise DemoAnalysisInputError("runtime evidence references must be unique")
        try:
            return compile_face_runtime(tuple(item.domain_observation() for item in ordered))
        except ValueError as exc:
            raise DemoAnalysisInputError(str(exc)) from exc


@dataclass(frozen=True)
class DemoAnalysisReservation:
    analysis_run_id: str
    job_id: str
    attempt_id: str
    attempt: int
    lease_token: str
    lease_expires_at: datetime
    request_id: str
    demo_actor_id: str
    demo_session_id: str
    demo_synthetic_identity_id: str
    source_asset_id: str
    source_asset_sha256: str
    analyzer_version: str
    runtime_manifest_digest: str
    model_manifest_digest: str
    observation_config_digest: str


@dataclass(frozen=True)
class DemoAnalysisPublication:
    analysis_run_id: str
    job_id: str
    observation_id: str
    observation_digest: str
    baseline_face_model_id: str
    self_state_id: str
    observation_state: Literal["SUPPORTED", "UNSUPPORTED"]


@dataclass(frozen=True)
class DemoAnalysisJobSnapshot:
    analysis_run_id: str
    job_id: str
    demo_actor_id: str
    demo_session_id: str
    status: JobStatus
    result_code: str | None
    observation_id: str | None
    observation_digest: str | None


class DemoAnalysisService:
    """PostgreSQL-authoritative D03 create, claim, publish and cancel lifecycle."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        configuration: DemoAnalysisConfiguration,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        configuration.validate()
        self._sessions = session_factory
        self._configuration = configuration
        self._now = now

    async def create(self, command: CreateDemoAnalysis) -> DemoAnalysisAccepted:
        command.validate()
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {"session_id": command.demo_session_id, "source_asset_id": command.source_asset_id}
        )
        async with self._sessions() as session:
            async with session.begin():
                existing = await self._binding_for_key(
                    session, demo_actor_id=command.demo_actor_id, key_hash=key_hash
                )
                if existing is not None:
                    return await self._replay_create(
                        session, existing, request_digest=request_digest
                    )

                identity = await self._lock_creation_context(session, command)
                job_id = new_id()
                run_id = new_id()
                binding_id = new_id()
                now = self._normalized_now()
                job = Job(
                    id=job_id,
                    job_type=DEMO_ANALYSIS_JOB_TYPE,
                    status="PENDING",
                    idempotency_key_hash=_formal_job_key_hash(command.demo_actor_id, key_hash),
                    request_id=command.request_id,
                    payload={},
                    owner_user_id=None,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
                run_payload = _analysis_run_payload(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                    demo_synthetic_identity_id=identity.id,
                    source_asset_id=command.source_asset_id,
                    source_asset_sha256=identity.formal_canonical_asset_sha256,
                    demo_job_binding_id=binding_id,
                    configuration=self._configuration,
                )
                run = DemoAnalysisRun(
                    id=run_id,
                    schema_version=DEMO_ANALYSIS_RUN_SCHEMA,
                    canonical_payload=run_payload,
                    content_digest=_authority_digest(DEMO_ANALYSIS_RUN_SCHEMA, run_payload),
                    created_at=now,
                    **run_payload,
                )
                binding_payload = _job_binding_payload(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                    job_id=job_id,
                    idempotency_key_hash_value=key_hash,
                    request_digest=request_digest,
                    target_id=run_id,
                )
                binding = DemoJobBinding(
                    id=binding_id,
                    schema_version=DEMO_JOB_BINDING_SCHEMA,
                    canonical_payload=binding_payload,
                    content_digest=_authority_digest(DEMO_JOB_BINDING_SCHEMA, binding_payload),
                    created_at=now,
                    **binding_payload,
                )
                try:
                    async with session.begin_nested():
                        session.add(job)
                        await session.flush()
                        session.add(run)
                        await session.flush()
                        session.add(binding)
                        await session.flush()
                except IntegrityError as exc:
                    winner = await self._binding_for_key(
                        session, demo_actor_id=command.demo_actor_id, key_hash=key_hash
                    )
                    if winner is None:
                        raise DemoAnalysisAuthorityCorruption(
                            "analysis creation failed without a reloadable idempotency winner"
                        ) from exc
                    return await self._replay_create(session, winner, request_digest=request_digest)
                return DemoAnalysisAccepted(
                    job_id=job_id,
                    analysis_run_id=run_id,
                    demo_session_id=command.demo_session_id,
                    request_id=command.request_id,
                    replayed=False,
                )

    async def claim(
        self, *, analysis_run_id: str, job_id: str, request_id: str
    ) -> DemoAnalysisReservation | None:
        _require_id(analysis_run_id, "analysis_run_id")
        _require_id(job_id, "job_id")
        _require_request_id(request_id)
        async with self._sessions() as session:
            async with session.begin():
                job = await self._lock_job(session, job_id)
                run = await self._lock_bound_run(session, job=job, expected_run_id=analysis_run_id)
                self._validate_job_envelope(job, request_id=request_id)
                if job.status in _TERMINAL:
                    return None
                now = self._normalized_now()
                if job.status == "RUNNING":
                    if job.lease_expires_at is None or job.lease_expires_at > now:
                        return None
                    current_attempt = await self._lock_current_attempt(session, job)
                    if job.attempt_count >= self._configuration.max_attempts:
                        self._terminalize_expired_attempt(
                            job,
                            current_attempt,
                            now=now,
                            code=DEMO_ANALYSIS_LEASE_RETRY_EXHAUSTED,
                        )
                        await session.flush()
                        return None
                    self._expire_attempt_for_retry(current_attempt, now=now)
                elif job.status == "PENDING" and job.attempt_count == 0:
                    pass
                else:
                    raise DemoAnalysisAuthorityCorruption("D03 Job cannot be claimed")
                lease_token = secrets.token_hex(32)
                expires_at = now + timedelta(seconds=self._configuration.lease_seconds)
                attempt_number = job.attempt_count + 1
                attempt = JobAttempt(
                    id=new_id(),
                    job_id=job.id,
                    attempt=attempt_number,
                    status="RUNNING",
                    lease_token=lease_token,
                    started_at=now,
                )
                session.add(attempt)
                job.status = "RUNNING"
                job.attempt_count = attempt_number
                job.lease_token = lease_token
                job.lease_acquired_at = now
                job.lease_expires_at = expires_at
                job.updated_at = now
                await session.flush()
                return DemoAnalysisReservation(
                    analysis_run_id=run.id,
                    job_id=job.id,
                    attempt_id=attempt.id,
                    attempt=attempt.attempt,
                    lease_token=lease_token,
                    lease_expires_at=expires_at,
                    request_id=job.request_id,
                    demo_actor_id=run.demo_actor_id,
                    demo_session_id=run.demo_session_id,
                    demo_synthetic_identity_id=run.demo_synthetic_identity_id,
                    source_asset_id=run.source_asset_id,
                    source_asset_sha256=run.source_asset_sha256,
                    analyzer_version=run.analyzer_version,
                    runtime_manifest_digest=run.runtime_manifest_digest,
                    model_manifest_digest=run.model_manifest_digest,
                    observation_config_digest=run.observation_config_digest,
                )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoAnalysisDispatchCandidate, ...]:
        """Return durable PENDING or expired-RUNNING dispatch intents."""

        if type(limit) is not int or not 1 <= limit <= 1_000:
            raise DemoAnalysisInputError("reconciliation limit must be in [1, 1000]")
        now = self._normalized_now()
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(Job, DemoJobBinding, DemoAnalysisRun)
                    .join(DemoJobBinding, DemoJobBinding.job_id == Job.id)
                    .join(DemoAnalysisRun, DemoAnalysisRun.id == DemoJobBinding.target_id)
                    .where(
                        Job.job_type == DEMO_ANALYSIS_JOB_TYPE,
                        DemoJobBinding.endpoint_operation == DEMO_ANALYSIS_OPERATION,
                        DemoJobBinding.target_type == "ANALYSIS_RUN",
                        or_(
                            Job.status == "PENDING",
                            and_(
                                Job.status == "RUNNING",
                                Job.lease_expires_at.is_not(None),
                                Job.lease_expires_at <= now,
                            ),
                        ),
                    )
                    .order_by(Job.created_at, Job.id)
                    .limit(limit)
                )
            ).all()
            candidates: list[DemoAnalysisDispatchCandidate] = []
            for job, binding, run in rows:
                self._validate_job_envelope(job, request_id=job.request_id)
                if (
                    binding.target_id != run.id
                    or run.demo_job_binding_id != binding.id
                    or binding.job_id != job.id
                ):
                    raise DemoAnalysisAuthorityCorruption(
                        "D03 reconciliation authority is inconsistent"
                    )
                candidates.append(
                    DemoAnalysisDispatchCandidate(
                        analysis_run_id=run.id,
                        job_id=job.id,
                        request_id=job.request_id,
                    )
                )
            return tuple(candidates)

    async def complete(
        self,
        reservation: DemoAnalysisReservation,
        evidence: DemoAnalysisRuntimeEvidence,
    ) -> DemoAnalysisPublication | None:
        compilation = evidence.compile()
        ordered_evidence = tuple(sorted(evidence.repeats, key=lambda item: item.repeat_index))
        async with self._sessions() as session:
            async with session.begin():
                job, run, attempt = await self._lock_reservation(session, reservation)
                if job.status in _TERMINAL:
                    return None
                self._require_current_reservation(
                    job, attempt, reservation, now=self._normalized_now()
                )
                await self._lock_completion_authority(session, run)
                if (
                    await session.scalar(
                        select(DemoFaceObservation.id).where(
                            DemoFaceObservation.analysis_run_id == run.id
                        )
                    )
                    is not None
                ):
                    raise DemoAnalysisAuthorityCorruption(
                        "running D03 Job already has final observation authority"
                    )
                await session.execute(
                    text("SELECT mirror_demo_require_current_synthetic_admission(:identity_id)"),
                    {"identity_id": run.demo_synthetic_identity_id},
                )
                observation_state: Literal["SUPPORTED", "UNSUPPORTED"] = (
                    "SUPPORTED"
                    if any(
                        dimension.support_state == "SUPPORTED"
                        for dimension in compilation.baseline.dimensions
                    )
                    else "UNSUPPORTED"
                )
                now = self._normalized_now()
                observation = _observation_row(
                    run=run, observation_state=observation_state, now=now
                )
                session.add(observation)
                await session.flush()
                repeats = tuple(
                    _repeat_row(
                        run=run,
                        observation_id=observation.id,
                        evidence=item,
                        now=now,
                    )
                    for item in ordered_evidence
                )
                session.add_all(repeats)
                await session.flush()
                baseline = _baseline_row(
                    run=run,
                    observation_id=observation.id,
                    compilation=compilation,
                    ordered_repeat_digests=[item.content_digest for item in repeats],
                    now=now,
                )
                session.add(baseline)
                await session.flush()
                self_state = _self_state_row(
                    run=run,
                    baseline_face_model_id=baseline.id,
                    compilation=compilation,
                    now=now,
                )
                session.add(self_state)
                await session.flush()

                attempt.status = "COMPLETED"
                attempt.result_code = observation_state
                attempt.error_code = None
                attempt.finished_at = now
                job.status = "COMPLETED"
                job.lease_token = None
                job.lease_acquired_at = None
                job.lease_expires_at = None
                job.finalized_at = now
                job.result_code = observation_state
                job.updated_at = now
                await session.flush()
                return DemoAnalysisPublication(
                    analysis_run_id=run.id,
                    job_id=job.id,
                    observation_id=observation.id,
                    observation_digest=observation.content_digest,
                    baseline_face_model_id=baseline.id,
                    self_state_id=self_state.id,
                    observation_state=observation_state,
                )

    async def terminalize(
        self,
        reservation: DemoAnalysisReservation,
        *,
        status: TerminalFailureStatus,
        code: str,
    ) -> bool:
        _require_code(code)
        async with self._sessions() as session:
            async with session.begin():
                job, _, attempt = await self._lock_reservation(session, reservation)
                if job.status in _TERMINAL:
                    return False
                self._require_current_reservation(
                    job, attempt, reservation, now=self._normalized_now()
                )
                now = self._normalized_now()
                attempt.status = status
                attempt.result_code = None if status == "FAILED" else code
                attempt.error_code = code if status == "FAILED" else None
                attempt.finished_at = now
                job.status = status
                job.lease_token = None
                job.lease_acquired_at = None
                job.lease_expires_at = None
                job.finalized_at = now
                job.result_code = code
                job.updated_at = now
                await session.flush()
                return True

    async def cancel(
        self,
        *,
        demo_actor_id: str,
        demo_session_id: str,
        job_id: str,
        expected_status: Literal["PENDING", "RUNNING"],
        code: str = "USER_REQUEST",
    ) -> bool:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(demo_session_id, "demo_session_id")
        _require_id(job_id, "job_id")
        _require_code(code)
        async with self._sessions() as session:
            async with session.begin():
                job = await self._lock_job(session, job_id)
                run = await self._lock_bound_run(session, job=job)
                if run.demo_actor_id != demo_actor_id or run.demo_session_id != demo_session_id:
                    raise DemoAnalysisUnavailable("D03 Job ownership mismatch")
                if job.status in _TERMINAL:
                    return False
                if job.status != expected_status:
                    raise DemoAnalysisInputError("D03 Job status differs from expected_status")
                now = self._normalized_now()
                if job.status == "RUNNING":
                    attempt = await self._lock_current_attempt(session, job)
                    attempt.status = "CANCELLED"
                    attempt.result_code = code
                    attempt.error_code = None
                    attempt.finished_at = now
                job.status = "CANCELLED"
                job.lease_token = None
                job.lease_acquired_at = None
                job.lease_expires_at = None
                job.finalized_at = now
                job.result_code = code
                job.updated_at = now
                await session.flush()
                return True

    async def snapshot(
        self, *, demo_actor_id: str, analysis_run_id: str
    ) -> DemoAnalysisJobSnapshot:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(analysis_run_id, "analysis_run_id")
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(DemoAnalysisRun, DemoJobBinding, Job)
                    .join(
                        DemoJobBinding,
                        DemoJobBinding.id == DemoAnalysisRun.demo_job_binding_id,
                    )
                    .join(Job, Job.id == DemoJobBinding.job_id)
                    .where(
                        DemoAnalysisRun.id == analysis_run_id,
                        DemoAnalysisRun.demo_actor_id == demo_actor_id,
                    )
                )
            ).one_or_none()
            if row is None:
                raise DemoAnalysisUnavailable("D03 analysis is unavailable")
            run, _, job = row
            observation = await session.scalar(
                select(DemoFaceObservation).where(DemoFaceObservation.analysis_run_id == run.id)
            )
            return _snapshot(run, job, observation)

    async def _lock_creation_context(
        self, session: AsyncSession, command: CreateDemoAnalysis
    ) -> DemoSyntheticIdentity:
        demo_session = cast(
            DemoSession | None,
            await session.scalar(
                select(DemoSession)
                .where(
                    DemoSession.id == command.demo_session_id,
                    DemoSession.demo_actor_id == command.demo_actor_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        now = self._normalized_now()
        if (
            demo_session is None
            or demo_session.closed_at is not None
            or demo_session.tombstoned_at is not None
            or demo_session.expires_at <= now
        ):
            raise DemoAnalysisUnavailable("D03 requires an active owned Session")
        config = demo_session.config
        if not isinstance(config, dict) or set(config) != {
            "schema_version",
            "synthetic_identity_id",
        }:
            raise DemoAnalysisUnavailable("D03 Session configuration is invalid")
        identity_id = config.get("synthetic_identity_id")
        if not isinstance(identity_id, str) or _ID.fullmatch(identity_id) is None:
            raise DemoAnalysisUnavailable("D03 Session identity is invalid")
        await session.execute(
            text("SELECT mirror_demo_require_current_synthetic_admission(:identity_id)"),
            {"identity_id": identity_id},
        )
        identity = cast(
            DemoSyntheticIdentity | None,
            await session.scalar(
                select(DemoSyntheticIdentity).where(DemoSyntheticIdentity.id == identity_id)
            ),
        )
        if (
            identity is None
            or identity.formal_canonical_asset_id != command.source_asset_id
            or _DIGEST.fullmatch(identity.formal_canonical_asset_sha256) is None
        ):
            raise DemoAnalysisUnavailable("D03 source differs from Session identity authority")
        return identity

    async def _replay_create(
        self,
        session: AsyncSession,
        binding: DemoJobBinding,
        *,
        request_digest: str,
    ) -> DemoAnalysisAccepted:
        if binding.request_digest != request_digest:
            raise DemoAnalysisPayloadConflict()
        if (
            binding.endpoint_operation != DEMO_ANALYSIS_OPERATION
            or binding.target_type != "ANALYSIS_RUN"
        ):
            raise DemoAnalysisAuthorityCorruption("idempotency winner is not a D03 AnalysisRun")
        run = await session.get(DemoAnalysisRun, binding.target_id)
        job = await session.get(Job, binding.job_id)
        if (
            run is None
            or job is None
            or run.demo_job_binding_id != binding.id
            or run.demo_actor_id != binding.demo_actor_id
            or run.demo_session_id != binding.demo_session_id
            or job.job_type != DEMO_ANALYSIS_JOB_TYPE
        ):
            raise DemoAnalysisAuthorityCorruption("D03 idempotency winner is incomplete")
        return DemoAnalysisAccepted(
            job_id=job.id,
            analysis_run_id=run.id,
            demo_session_id=run.demo_session_id,
            request_id=job.request_id,
            replayed=True,
        )

    async def _lock_completion_authority(self, session: AsyncSession, run: DemoAnalysisRun) -> None:
        demo_session = cast(
            DemoSession | None,
            await session.scalar(
                select(DemoSession)
                .where(
                    DemoSession.id == run.demo_session_id,
                    DemoSession.demo_actor_id == run.demo_actor_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        expected_config = {
            "schema_version": "mirror.demo/DemoSessionConfig/v1",
            "synthetic_identity_id": run.demo_synthetic_identity_id,
        }
        if (
            demo_session is None
            or demo_session.closed_at is not None
            or demo_session.tombstoned_at is not None
            or demo_session.expires_at <= self._normalized_now()
            or demo_session.config != expected_config
        ):
            raise DemoAnalysisUnavailable("D03 completion Session authority is unavailable")
        try:
            async with session.begin_nested():
                await session.execute(
                    text("SELECT mirror_demo_require_current_synthetic_admission(:identity_id)"),
                    {"identity_id": run.demo_synthetic_identity_id},
                )
        except DBAPIError as exc:
            raise DemoAnalysisUnavailable(
                "D03 completion synthetic admission is unavailable"
            ) from exc
        identity = await session.get(DemoSyntheticIdentity, run.demo_synthetic_identity_id)
        if (
            identity is None
            or identity.formal_canonical_asset_id != run.source_asset_id
            or identity.formal_canonical_asset_sha256 != run.source_asset_sha256
        ):
            raise DemoAnalysisUnavailable("D03 completion source authority is unavailable")

    @staticmethod
    async def _binding_for_key(
        session: AsyncSession, *, demo_actor_id: str, key_hash: str
    ) -> DemoJobBinding | None:
        return cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.demo_actor_id == demo_actor_id,
                    DemoJobBinding.endpoint_operation == DEMO_ANALYSIS_OPERATION,
                    DemoJobBinding.idempotency_key_hash == key_hash,
                )
            ),
        )

    @staticmethod
    async def _lock_job(session: AsyncSession, job_id: str) -> Job:
        job = cast(
            Job | None,
            await session.scalar(
                select(Job)
                .where(Job.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if job is None:
            raise DemoAnalysisUnavailable("D03 Job is unavailable")
        return job

    async def _lock_bound_run(
        self,
        session: AsyncSession,
        *,
        job: Job,
        expected_run_id: str | None = None,
    ) -> DemoAnalysisRun:
        if job.job_type != DEMO_ANALYSIS_JOB_TYPE:
            raise DemoAnalysisUnavailable("Job is not owned by D03 analysis")
        binding = cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding)
                .where(DemoJobBinding.job_id == job.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if (
            binding is None
            or binding.endpoint_operation != DEMO_ANALYSIS_OPERATION
            or binding.target_type != "ANALYSIS_RUN"
            or (expected_run_id is not None and binding.target_id != expected_run_id)
        ):
            raise DemoAnalysisUnavailable("D03 Job binding is unavailable")
        run = cast(
            DemoAnalysisRun | None,
            await session.scalar(
                select(DemoAnalysisRun)
                .where(DemoAnalysisRun.id == binding.target_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if run is None or run.demo_job_binding_id != binding.id:
            raise DemoAnalysisAuthorityCorruption("D03 Job/Run reverse binding is invalid")
        return run

    async def _lock_reservation(
        self, session: AsyncSession, reservation: DemoAnalysisReservation
    ) -> tuple[Job, DemoAnalysisRun, JobAttempt]:
        job = await self._lock_job(session, reservation.job_id)
        run = await self._lock_bound_run(
            session, job=job, expected_run_id=reservation.analysis_run_id
        )
        attempt = cast(
            JobAttempt | None,
            await session.scalar(
                select(JobAttempt)
                .where(JobAttempt.id == reservation.attempt_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if attempt is None or attempt.job_id != job.id:
            raise DemoAnalysisLeaseLost("D03 JobAttempt is unavailable")
        return job, run, attempt

    @staticmethod
    async def _lock_current_attempt(session: AsyncSession, job: Job) -> JobAttempt:
        attempt = cast(
            JobAttempt | None,
            await session.scalar(
                select(JobAttempt)
                .where(
                    JobAttempt.job_id == job.id,
                    JobAttempt.attempt == job.attempt_count,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if attempt is None:
            raise DemoAnalysisAuthorityCorruption("D03 RUNNING Job lacks its current Attempt")
        return attempt

    @staticmethod
    def _require_current_reservation(
        job: Job,
        attempt: JobAttempt,
        reservation: DemoAnalysisReservation,
        *,
        now: datetime,
    ) -> None:
        if (
            job.status != "RUNNING"
            or job.attempt_count != reservation.attempt
            or job.lease_token != reservation.lease_token
            or attempt.id != reservation.attempt_id
            or attempt.status != "RUNNING"
            or attempt.lease_token != reservation.lease_token
            or attempt.finished_at is not None
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise DemoAnalysisLeaseLost("D03 reservation is no longer current")

    @staticmethod
    def _expire_attempt_for_retry(attempt: JobAttempt, *, now: datetime) -> None:
        if attempt.status != "RUNNING" or attempt.finished_at is not None:
            raise DemoAnalysisAuthorityCorruption("expired D03 attempt is not RUNNING")
        attempt.status = "FAILED"
        attempt.result_code = None
        attempt.error_code = DEMO_ANALYSIS_LEASE_EXPIRED
        attempt.finished_at = now

    @staticmethod
    def _terminalize_expired_attempt(
        job: Job,
        attempt: JobAttempt,
        *,
        now: datetime,
        code: str,
    ) -> None:
        if attempt.status != "RUNNING" or attempt.finished_at is not None:
            raise DemoAnalysisAuthorityCorruption("expired D03 attempt is not RUNNING")
        attempt.status = "FAILED"
        attempt.result_code = None
        attempt.error_code = code
        attempt.finished_at = now
        job.status = "FAILED"
        job.lease_token = None
        job.lease_acquired_at = None
        job.lease_expires_at = None
        job.finalized_at = now
        job.result_code = code
        job.updated_at = now

    @staticmethod
    def _validate_job_envelope(job: Job, *, request_id: str) -> None:
        if (
            job.job_type != DEMO_ANALYSIS_JOB_TYPE
            or job.request_id != request_id
            or job.owner_user_id is not None
            or job.ingestion_upload_intent_id is not None
            or job.result_asset_id is not None
            or job.payload != {}
        ):
            raise DemoAnalysisUnavailable("D03 Job envelope does not match the task")

    def _normalized_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise DemoAnalysisAuthorityCorruption("D03 clock must be timezone-aware")
        return value.astimezone(UTC)


def _analysis_run_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    demo_synthetic_identity_id: str,
    source_asset_id: str,
    source_asset_sha256: str,
    demo_job_binding_id: str,
    configuration: DemoAnalysisConfiguration,
) -> dict[str, Any]:
    return {
        "analyzer_version": configuration.analyzer_version,
        "baseline_aggregation_version": configuration.baseline_aggregation_version,
        "demo_actor_id": demo_actor_id,
        "demo_job_binding_id": demo_job_binding_id,
        "demo_session_id": demo_session_id,
        "demo_synthetic_identity_id": demo_synthetic_identity_id,
        "measurement_version": configuration.measurement_version,
        "model_manifest_digest": configuration.model_manifest_digest,
        "observation_config_digest": configuration.observation_config_digest,
        "repeat_count": 3,
        "runtime_manifest_digest": configuration.runtime_manifest_digest,
        "self_state_derivation_version": configuration.self_state_derivation_version,
        "self_state_ontology_version": configuration.self_state_ontology_version,
        "source_asset_id": source_asset_id,
        "source_asset_sha256": source_asset_sha256,
    }


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
        "endpoint_operation": DEMO_ANALYSIS_OPERATION,
        "idempotency_key_hash": idempotency_key_hash_value,
        "job_id": job_id,
        "request_digest": request_digest,
        "target_id": target_id,
        "target_type": "ANALYSIS_RUN",
    }


def _observation_row(
    *,
    run: DemoAnalysisRun,
    observation_state: Literal["SUPPORTED", "UNSUPPORTED"],
    now: datetime,
) -> DemoFaceObservation:
    payload = {
        "analysis_run_id": run.id,
        "analyzer_version": run.analyzer_version,
        "config_digest": run.observation_config_digest,
        "demo_actor_id": run.demo_actor_id,
        "demo_session_id": run.demo_session_id,
        "demo_synthetic_identity_id": run.demo_synthetic_identity_id,
        "observation_state": observation_state,
        "repeat_count": 3,
        "runtime_manifest_digest": run.runtime_manifest_digest,
        "source_asset_id": run.source_asset_id,
        "source_asset_sha256": run.source_asset_sha256,
        "unsupported_reason": (
            None if observation_state == "SUPPORTED" else "NO_SUPPORTED_DIMENSIONS"
        ),
    }
    return DemoFaceObservation(
        id=new_id(),
        schema_version=DEMO_FACE_OBSERVATION_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_FACE_OBSERVATION_SCHEMA, payload),
        created_at=now,
        **payload,
    )


def _repeat_row(
    *,
    run: DemoAnalysisRun,
    observation_id: str,
    evidence: DemoAnalysisRepeatEvidence,
    now: datetime,
) -> DemoFaceObservationRepeat:
    payload = {
        "demo_actor_id": run.demo_actor_id,
        "demo_session_id": run.demo_session_id,
        "landmarks": [item.payload() for item in evidence.landmarks],
        "measurements": evidence.measurement_payload(),
        "model_manifest_digest": run.model_manifest_digest,
        "observation_id": observation_id,
        "pose": evidence.pose.payload(),
        "quality": evidence.quality_payload(),
        "repeat_index": evidence.repeat_index,
        "runtime_manifest_digest": run.runtime_manifest_digest,
    }
    return DemoFaceObservationRepeat(
        id=new_id(),
        schema_version=DEMO_FACE_OBSERVATION_REPEAT_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_FACE_OBSERVATION_REPEAT_SCHEMA, payload),
        created_at=now,
        **payload,
    )


def _baseline_row(
    *,
    run: DemoAnalysisRun,
    observation_id: str,
    compilation: FaceRuntimeCompilation,
    ordered_repeat_digests: Sequence[str],
    now: datetime,
) -> DemoBaselineFaceModel:
    dimensions = sorted(compilation.baseline.dimensions, key=lambda item: item.dimension)
    payload = {
        "aggregation_version": run.baseline_aggregation_version,
        "demo_actor_id": run.demo_actor_id,
        "demo_session_id": run.demo_session_id,
        "measurement_version": run.measurement_version,
        "measurements": {item.dimension: item.value_ppm for item in dimensions},
        "observation_id": observation_id,
        "ordered_repeat_digests": list(ordered_repeat_digests),
        "reliability": {item.dimension: item.reliability_ppm for item in dimensions},
        "uncertainty": {item.dimension: item.uncertainty_ppm for item in dimensions},
        "unsupported_state": {
            item.dimension: item.unsupported_reason
            for item in dimensions
            if item.unsupported_reason is not None
        },
        "version": 1,
    }
    return DemoBaselineFaceModel(
        id=new_id(),
        schema_version=DEMO_BASELINE_FACE_MODEL_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_BASELINE_FACE_MODEL_SCHEMA, payload),
        created_at=now,
        **payload,
    )


def _self_state_row(
    *,
    run: DemoAnalysisRun,
    baseline_face_model_id: str,
    compilation: FaceRuntimeCompilation,
    now: datetime,
) -> DemoSelfState:
    dimensions = sorted(compilation.self_state.dimensions, key=lambda item: item.dimension)
    payload = {
        "baseline_face_model_id": baseline_face_model_id,
        "demo_actor_id": run.demo_actor_id,
        "demo_session_id": run.demo_session_id,
        "derivation_version": run.self_state_derivation_version,
        "measurements": {item.dimension: item.value_ppm for item in dimensions},
        "ontology_version": run.self_state_ontology_version,
        "reliability": {item.dimension: item.reliability_ppm for item in dimensions},
        "routing_eligibility": {item.dimension: item.routing_eligibility for item in dimensions},
        "uncertainty": {item.dimension: item.uncertainty_ppm for item in dimensions},
        "version": 1,
    }
    return DemoSelfState(
        id=new_id(),
        schema_version=DEMO_SELF_STATE_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_SELF_STATE_SCHEMA, payload),
        created_at=now,
        **payload,
    )


def _snapshot(
    run: DemoAnalysisRun, job: Job, observation: DemoFaceObservation | None
) -> DemoAnalysisJobSnapshot:
    if job.status not in {
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "REJECTED",
        "FAILED",
        "CANCELLED",
    }:
        raise DemoAnalysisAuthorityCorruption("D03 Job status is unsupported")
    return DemoAnalysisJobSnapshot(
        analysis_run_id=run.id,
        job_id=job.id,
        demo_actor_id=run.demo_actor_id,
        demo_session_id=run.demo_session_id,
        status=cast(JobStatus, job.status),
        result_code=job.result_code,
        observation_id=observation.id if observation is not None else None,
        observation_digest=observation.content_digest if observation is not None else None,
    )


def _formal_job_key_hash(demo_actor_id: str, client_key_hash: str) -> str:
    preimage = (
        f"mirror.demo/JobIdempotency/v1\n{demo_actor_id}\n"
        f"{DEMO_ANALYSIS_OPERATION}\n{client_key_hash}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _authority_digest(schema_version: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoAnalysisInputError(f"{name} must be a lowercase hexadecimal ID")


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DemoAnalysisInputError(f"{name} must be a SHA-256 digest")


def _require_request_id(value: str) -> None:
    if (
        not isinstance(value, str)
        or not 8 <= len(value) <= 128
        or any(character in value for character in "\r\n\0")
    ):
        raise DemoAnalysisInputError("request_id is outside the safe boundary")


def _require_code(value: str) -> None:
    if not isinstance(value, str) or _CODE.fullmatch(value) is None:
        raise DemoAnalysisInputError("terminal result code is invalid")
