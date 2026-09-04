"""Durable queued orchestration for byte-free D06 Reference Profile compilation."""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal, cast

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_idempotency import (
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DemoAcceptedVisualEpisode,
    DemoActor,
    DemoDesiredDeltaProfile,
    DemoEditingSession,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoReferenceProfile,
    DemoReferenceProfileCompileRequest,
    DemoReferenceProfileCompileResult,
    DemoSelfTransferRun,
    DemoStyleProfile,
    DemoVerificationResult,
)
from mirror_api.demo_self_transfer_service import (
    DEMO_REFERENCE_COMPILER_VERSION,
    CompileDemoReferenceProfile,
    DemoReferenceProfileInputSnapshot,
    DemoReferenceSource,
    DemoSelfTransferAuthorityCorruption,
    DemoSelfTransferConflict,
    DemoSelfTransferInputError,
    DemoSelfTransferService,
    DemoSelfTransferUnavailable,
)
from mirror_api.models import Job, JobAttempt, new_id, utcnow

DEMO_REFERENCE_PROFILE_OPERATION: Final = "reference_profile.compile"
DEMO_REFERENCE_PROFILE_JOB_TYPE: Final = "demo_p3_p7.reference_profile.compile"
DEMO_REFERENCE_PROFILE_REQUEST_SCHEMA: Final = "mirror.demo/DemoReferenceProfileCompileRequest/v1"
DEMO_REFERENCE_PROFILE_RESULT_SCHEMA: Final = "mirror.demo/DemoReferenceProfileCompileResult/v1"
DEMO_REFERENCE_PROFILE_CAPABILITY: Final = "P5_REFERENCE_PROFILE"
DEMO_REFERENCE_PROFILE_EXECUTION_POLICY: Final = "demo-reference-profile-queue-v1"
DEMO_REFERENCE_PROFILE_MAX_ATTEMPTS: Final = 3
DEMO_REFERENCE_PROFILE_LEASE_SECONDS: Final = 300
DEMO_JOB_BINDING_SCHEMA: Final = "mirror.demo/DemoJobBinding/v1"

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REQUEST_ID = re.compile(r"^[^\r\n\x00]{8,128}$")
_VIEW_ORDER: Final = {"FRONT": 0, "THREE_QUARTER": 1, "SIDE": 2}
_TERMINAL: Final = frozenset({"COMPLETED", "REJECTED", "FAILED", "CANCELLED"})
_NON_AUTHORITY_COLUMNS: Final = frozenset(
    {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
)

DemoReferenceProfileExecutionStatus = Literal[
    "COMPLETED", "REJECTED", "FAILED", "CANCELLED", "NO_OP"
]
DemoReferenceProfileReservationState = Literal["RESERVED", "ACTIVE", "TERMINAL"]


class DemoReferenceProfileError(RuntimeError):
    """Stable public/application D06 queue error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DemoReferenceProfileInputError(DemoReferenceProfileError):
    """The request is outside the frozen D06 public contract."""


class DemoReferenceProfileUnavailable(DemoReferenceProfileError):
    """Required owner-bound authority is unavailable."""


class DemoReferenceProfileConflict(DemoReferenceProfileError):
    """The request conflicts with an immutable winner or lifecycle state."""


class DemoReferenceProfileAuthorityCorruption(DemoReferenceProfileError):
    """Persisted queue authority cannot be safely replayed."""


class DemoReferenceProfileResultNotReady(DemoReferenceProfileError):
    """The exact Reference Profile compilation is still pending."""


class DemoReferenceProfileResultTerminal(DemoReferenceProfileError):
    """The exact Reference Profile compilation ended without a result."""


@dataclass(frozen=True, slots=True)
class CreateDemoReferenceProfileCompilation:
    demo_actor_id: str
    demo_session_id: str
    desired_delta_profile_id: str
    style_profile_id: str | None
    identity_constraints_id: str | None
    sources: tuple[DemoReferenceSource, ...]
    idempotency_key: str
    request_id: str
    compiler_version: str = DEMO_REFERENCE_COMPILER_VERSION

    def validate(self) -> None:
        self.compile_command().validate()
        if self.compiler_version != DEMO_REFERENCE_COMPILER_VERSION:
            raise DemoReferenceProfileInputError(
                "UNSUPPORTED_COMPILER_VERSION",
                "Reference Profile compiler version is unsupported",
            )
        idempotency_key_hash(self.idempotency_key)
        if not isinstance(self.request_id, str) or _REQUEST_ID.fullmatch(self.request_id) is None:
            raise DemoReferenceProfileInputError(
                "INVALID_REQUEST_ID",
                "request_id is outside the safe boundary",
            )

    def compile_command(self) -> CompileDemoReferenceProfile:
        ordered_sources = tuple(sorted(self.sources, key=lambda item: _VIEW_ORDER[item.view]))
        return CompileDemoReferenceProfile(
            demo_actor_id=self.demo_actor_id,
            demo_session_id=self.demo_session_id,
            desired_delta_profile_id=self.desired_delta_profile_id,
            style_profile_id=self.style_profile_id,
            identity_constraints_id=self.identity_constraints_id,
            sources=ordered_sources,
        )


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileCompilationAccepted:
    job_id: str
    compile_request_id: str
    request_id: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileReservation:
    state: DemoReferenceProfileReservationState
    job_id: str
    compile_request_id: str
    attempt_id: str | None
    attempt: int | None
    lease_token: str | None
    terminal_status: str | None


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileReconciliationCandidate:
    demo_actor_id: str
    job_id: str
    compile_request_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileExecutionResult:
    demo_actor_id: str
    job_id: str
    compile_request_id: str
    status: DemoReferenceProfileExecutionStatus
    result_code: str | None
    reference_profile_id: str | None = None
    profile_digest: str | None = None
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileSnapshot:
    reference_profile_id: str
    version: int
    content_digest: str
    source_count: int


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileCompletedResult:
    job_id: str
    demo_session_id: str
    reference_profile_id: str
    job_binding_digest: str
    compile_result_digest: str
    profile_digest: str


class DemoReferenceProfileService:
    """Own immutable admission and recoverable execution around the D06 compiler."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._now = now
        self._compiler = DemoSelfTransferService(session_factory=session_factory, now=now)

    async def admit(
        self, command: CreateDemoReferenceProfileCompilation
    ) -> DemoReferenceProfileCompilationAccepted:
        command.validate()
        compile_command = command.compile_command()
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {
                "compiler_version": command.compiler_version,
                "desired_delta_profile_id": command.desired_delta_profile_id,
                "identity_constraints_id": command.identity_constraints_id,
                "session_id": command.demo_session_id,
                "sources": [
                    {"asset_id": item.asset_id, "view": item.view}
                    for item in compile_command.sources
                ],
                "style_profile_id": command.style_profile_id,
            }
        )
        async with self._sessions() as session:
            async with session.begin():
                existing = await self._binding_for_key(
                    session,
                    demo_actor_id=command.demo_actor_id,
                    key_hash=key_hash,
                )
                if existing is not None:
                    return await self._replay_admission(
                        session,
                        existing,
                        request_digest=request_digest,
                    )
                try:
                    frozen = await self._compiler.freeze_reference_profile_inputs(
                        session,
                        compile_command,
                    )
                except DemoSelfTransferInputError as exc:
                    raise DemoReferenceProfileInputError(exc.code, str(exc)) from exc
                except DemoSelfTransferUnavailable as exc:
                    raise DemoReferenceProfileUnavailable(exc.code, str(exc)) from exc
                except DemoSelfTransferConflict as exc:
                    raise DemoReferenceProfileConflict(exc.code, str(exc)) from exc
                except DemoSelfTransferAuthorityCorruption as exc:
                    raise DemoReferenceProfileAuthorityCorruption(exc.code, str(exc)) from exc

                now = self._normalized_now()
                job_id, compile_request_id, binding_id = new_id(), new_id(), new_id()
                job = Job(
                    id=job_id,
                    job_type=DEMO_REFERENCE_PROFILE_JOB_TYPE,
                    status="PENDING",
                    idempotency_key_hash=_formal_job_key_hash(command.demo_actor_id, key_hash),
                    request_id=command.request_id,
                    payload={},
                    owner_user_id=None,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
                compile_request = _authority_row(
                    DemoReferenceProfileCompileRequest,
                    row_id=compile_request_id,
                    schema_version=DEMO_REFERENCE_PROFILE_REQUEST_SCHEMA,
                    created_at=now,
                    fields=_request_payload(
                        demo_actor_id=command.demo_actor_id,
                        demo_session_id=command.demo_session_id,
                        demo_job_binding_id=binding_id,
                        desired_delta_profile_id=command.desired_delta_profile_id,
                        style_profile_id=command.style_profile_id,
                        identity_constraints_id=command.identity_constraints_id,
                        compiler_version=command.compiler_version,
                        frozen=frozen,
                    ),
                )
                binding = _authority_row(
                    DemoJobBinding,
                    row_id=binding_id,
                    schema_version=DEMO_JOB_BINDING_SCHEMA,
                    created_at=now,
                    fields=_binding_payload(
                        demo_actor_id=command.demo_actor_id,
                        demo_session_id=command.demo_session_id,
                        job_id=job_id,
                        idempotency_key_hash_value=key_hash,
                        request_digest=request_digest,
                        compile_request_id=compile_request_id,
                    ),
                )
                try:
                    async with session.begin_nested():
                        session.add(job)
                        await session.flush()
                        session.add(compile_request)
                        await session.flush()
                        session.add(binding)
                        await session.flush()
                except IntegrityError as exc:
                    winner = await self._binding_for_key(
                        session,
                        demo_actor_id=command.demo_actor_id,
                        key_hash=key_hash,
                    )
                    if winner is None:
                        raise DemoReferenceProfileAuthorityCorruption(
                            "ADMISSION_CONFLICT_WITHOUT_WINNER",
                            "Reference Profile admission conflict has no reloadable winner",
                        ) from exc
                    return await self._replay_admission(
                        session,
                        winner,
                        request_digest=request_digest,
                    )
                return DemoReferenceProfileCompilationAccepted(
                    job.id,
                    compile_request.id,
                    job.request_id,
                    False,
                )

    async def reserve(
        self,
        *,
        demo_actor_id: str,
        job_id: str,
        compile_request_id: str,
    ) -> DemoReferenceProfileReservation:
        for name, value in (
            ("demo_actor_id", demo_actor_id),
            ("job_id", job_id),
            ("compile_request_id", compile_request_id),
        ):
            _require_id(value, name)
        async with self._sessions() as session:
            async with session.begin():
                request, _, job = await self._execution_context(
                    session,
                    demo_actor_id=demo_actor_id,
                    job_id=job_id,
                    compile_request_id=compile_request_id,
                    lock_job=True,
                )
                if job.status in _TERMINAL:
                    return DemoReferenceProfileReservation(
                        "TERMINAL", job.id, request.id, None, None, None, job.status
                    )
                now = self._normalized_now()
                if job.status == "PENDING":
                    if (
                        job.attempt_count != 0
                        or job.lease_token is not None
                        or job.lease_acquired_at is not None
                        or job.lease_expires_at is not None
                    ):
                        raise DemoReferenceProfileAuthorityCorruption(
                            "PENDING_JOB_INVALID",
                            "PENDING Reference Profile Job has invalid lease authority",
                        )
                elif job.status == "RUNNING":
                    attempt = await self._current_attempt(session, job)
                    if (
                        attempt.status != "RUNNING"
                        or attempt.finished_at is not None
                        or attempt.lease_token != job.lease_token
                        or job.lease_token is None
                        or job.lease_acquired_at is None
                        or job.lease_expires_at is None
                    ):
                        raise DemoReferenceProfileAuthorityCorruption(
                            "RUNNING_ATTEMPT_INVALID",
                            "RUNNING Reference Profile Job has invalid attempt authority",
                        )
                    if job.lease_expires_at > now:
                        return DemoReferenceProfileReservation(
                            "ACTIVE",
                            job.id,
                            request.id,
                            attempt.id,
                            attempt.attempt,
                            None,
                            None,
                        )
                    attempt.status = "FAILED"
                    attempt.result_code = None
                    attempt.error_code = "LEASE_EXPIRED"
                    attempt.finished_at = now
                    if job.attempt_count >= request.max_attempts:
                        _finish_exhausted_job(job, now=now)
                        await session.flush()
                        return DemoReferenceProfileReservation(
                            "TERMINAL", job.id, request.id, None, None, None, "FAILED"
                        )
                else:
                    raise DemoReferenceProfileAuthorityCorruption(
                        "JOB_STATUS_INVALID",
                        "Reference Profile Job status is unsupported",
                    )

                attempt_number = job.attempt_count + 1
                if attempt_number > request.max_attempts:
                    raise DemoReferenceProfileAuthorityCorruption(
                        "ATTEMPT_LIMIT_INVALID",
                        "Reference Profile attempt limit was bypassed",
                    )
                lease_token = secrets.token_hex(32)
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
                job.lease_expires_at = now + timedelta(seconds=request.lease_timeout_seconds)
                job.updated_at = now
                await session.flush()
                return DemoReferenceProfileReservation(
                    "RESERVED",
                    job.id,
                    request.id,
                    attempt.id,
                    attempt.attempt,
                    lease_token,
                    None,
                )

    async def command_for_accepted_stepped_result(
        self, *, demo_actor_id: str, result_run_id: str
    ) -> CreateDemoReferenceProfileCompilation:
        """Derive the one deterministic queue command from immutable v2 evidence.

        This runs only after D09/D06 has committed.  It intentionally derives
        every source/profile reference from the persisted result instead of
        accepting a caller supplied compile command.
        """

        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(result_run_id, "result_run_id")
        async with self._sessions() as session:
            result = await session.get(DemoSelfTransferRun, result_run_id)
            if (
                result is None
                or result.demo_actor_id != demo_actor_id
                or result.schema_version != "mirror.demo/DemoSelfTransferRun/v2"
                or result.record_kind != "RESULT"
                or result.user_outcome != "ACCEPTED"
                or result.request_run_id is None
                or result.result_asset_id is None
                or result.verifier_digest is None
            ):
                raise DemoReferenceProfileUnavailable(
                    "STEPPED_RESULT_UNAVAILABLE",
                    "accepted stepped self-transfer result is unavailable",
                )
            try:
                replayed_result = await self._compiler.revalidate_stepped_result_in_session(
                    session,
                    demo_actor_id=demo_actor_id,
                    result_run_id=result_run_id,
                )
            except DemoSelfTransferInputError as exc:
                raise DemoReferenceProfileInputError(exc.code, str(exc)) from exc
            except DemoSelfTransferUnavailable as exc:
                raise DemoReferenceProfileUnavailable(exc.code, str(exc)) from exc
            except DemoSelfTransferConflict as exc:
                raise DemoReferenceProfileConflict(exc.code, str(exc)) from exc
            except DemoSelfTransferAuthorityCorruption as exc:
                raise DemoReferenceProfileAuthorityCorruption(exc.code, str(exc)) from exc
            if (
                replayed_result.id != result.id
                or replayed_result.content_digest != result.content_digest
            ):
                raise DemoReferenceProfileAuthorityCorruption(
                    "STEPPED_RESULT_REPLAY_MISMATCH",
                    "accepted stepped result does not replay exactly",
                )
            request = await session.get(DemoSelfTransferRun, result.request_run_id)
            if (
                request is None
                or request.schema_version != result.schema_version
                or request.record_kind != "REQUEST"
                or request.demo_actor_id != result.demo_actor_id
                or request.demo_session_id != result.demo_session_id
                or request.desired_delta_profile_id != result.desired_delta_profile_id
                or request.requested_delta != result.requested_delta
            ):
                raise DemoReferenceProfileAuthorityCorruption(
                    "STEPPED_RESULT_REQUEST_INVALID",
                    "accepted stepped self-transfer result cannot replay its request",
                )
            result_image_version_id = request.requested_delta.get("result_image_version_id")
            if not isinstance(result_image_version_id, str):
                raise DemoReferenceProfileAuthorityCorruption(
                    "STEPPED_RESULT_IMAGE_INVALID",
                    "accepted stepped result lacks its exact ImageVersion",
                )
            _require_id(result_image_version_id, "result_image_version_id")
            image = await session.get(DemoImageVersion, result_image_version_id)
            editing = (
                None
                if image is None
                else await session.get(DemoEditingSession, image.editing_session_id)
            )
            desired = await session.get(DemoDesiredDeltaProfile, result.desired_delta_profile_id)
            verifier = (
                None
                if image is None or image.verifier_digest is None
                else await session.scalar(
                    select(DemoVerificationResult).where(
                        DemoVerificationResult.content_digest == image.verifier_digest
                    )
                )
            )
            episode = await session.scalar(
                select(DemoAcceptedVisualEpisode).where(
                    DemoAcceptedVisualEpisode.demo_actor_id == demo_actor_id,
                    DemoAcceptedVisualEpisode.demo_session_id == result.demo_session_id,
                    DemoAcceptedVisualEpisode.accepted_image_version_id == result_image_version_id,
                )
            )
            if (
                image is None
                or editing is None
                or desired is None
                or verifier is None
                or episode is None
                or image.demo_actor_id != demo_actor_id
                or image.demo_session_id != result.demo_session_id
                or image.version_kind != "EDITED"
                or image.result_asset_id != result.result_asset_id
                or image.verifier_digest != result.verifier_digest
                or verifier.demo_actor_id != demo_actor_id
                or verifier.demo_session_id != result.demo_session_id
                or verifier.image_version_id != image.id
                or verifier.output_asset_id != image.result_asset_id
                or verifier.output_asset_sha256 != image.result_asset_sha256
                or verifier.outcome != "PASS"
                or desired.demo_actor_id != demo_actor_id
                or desired.demo_session_id != result.demo_session_id
                or editing.demo_actor_id != demo_actor_id
                or editing.demo_session_id != result.demo_session_id
                or editing.id != image.editing_session_id
                or editing.source_asset_id != result.source_asset_id
                or editing.desired_delta_profile_digest != desired.content_digest
                or episode.editing_session_id != editing.id
                or episode.accepted_image_version_id != image.id
                or episode.verification_result_id != verifier.id
                or episode.source_asset_id != result.source_asset_id
                or episode.final_asset_id != result.result_asset_id
                or episode.final_asset_sha256 != image.result_asset_sha256
                or episode.profile_digest != desired.content_digest
                or episode.instruction_digest != editing.instruction_digest
            ):
                raise DemoReferenceProfileAuthorityCorruption(
                    "STEPPED_RESULT_LINEAGE_INVALID",
                    "accepted stepped result lineage is invalid",
                )
            styles = tuple(
                await session.scalars(
                    select(DemoStyleProfile).where(
                        DemoStyleProfile.demo_actor_id == demo_actor_id,
                        DemoStyleProfile.demo_session_id == result.demo_session_id,
                        DemoStyleProfile.content_digest == editing.style_profile_digest,
                    )
                )
            )
            constraints = tuple(
                await session.scalars(
                    select(DemoIdentityConstraints).where(
                        DemoIdentityConstraints.demo_actor_id == demo_actor_id,
                        or_(
                            DemoIdentityConstraints.demo_session_id == result.demo_session_id,
                            DemoIdentityConstraints.demo_session_id.is_(None),
                        ),
                        DemoIdentityConstraints.content_digest
                        == editing.identity_constraints_digest,
                    )
                )
            )
            if len(styles) != 1 or len(constraints) != 1:
                raise DemoReferenceProfileAuthorityCorruption(
                    "STEPPED_RESULT_PROFILE_CONTEXT_INVALID",
                    "accepted stepped result does not have one profile context",
                )
            stable_key = f"d06-stepped-reference-{result.content_digest}"
            return CreateDemoReferenceProfileCompilation(
                demo_actor_id=demo_actor_id,
                demo_session_id=result.demo_session_id,
                desired_delta_profile_id=desired.id,
                style_profile_id=styles[0].id,
                identity_constraints_id=constraints[0].id,
                # FRONT is a categorical D02 presentation slot inherited
                # through the exact public stepped-result replay above.  It is
                # deliberately not fresh D03 pose evidence.
                sources=(DemoReferenceSource(result.result_asset_id, "FRONT"),),
                idempotency_key=stable_key,
                # The deterministic authority key remains inside the one-way
                # idempotency boundary.  Operational correlation must not
                # expose the accepted D06 result digest.
                request_id=f"d06-reference-{new_id()}",
            )

    async def execute_task(
        self,
        *,
        demo_actor_id: str,
        job_id: str,
        compile_request_id: str,
    ) -> DemoReferenceProfileExecutionResult:
        reservation = await self.reserve(
            demo_actor_id=demo_actor_id,
            job_id=job_id,
            compile_request_id=compile_request_id,
        )
        if reservation.state == "ACTIVE":
            return DemoReferenceProfileExecutionResult(
                demo_actor_id, job_id, compile_request_id, "NO_OP", None, replayed=True
            )
        if reservation.state == "TERMINAL":
            return await self._terminal_result(
                demo_actor_id=demo_actor_id,
                job_id=job_id,
                compile_request_id=compile_request_id,
            )
        return await self._finalize_reservation(
            demo_actor_id=demo_actor_id,
            reservation=reservation,
        )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoReferenceProfileReconciliationCandidate, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise DemoReferenceProfileInputError(
                "INVALID_RECONCILIATION_LIMIT",
                "reconciliation limit is outside the supported boundary",
            )
        now = self._normalized_now()
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(DemoJobBinding, Job, DemoReferenceProfileCompileRequest)
                    .join(Job, Job.id == DemoJobBinding.job_id)
                    .join(
                        DemoReferenceProfileCompileRequest,
                        DemoReferenceProfileCompileRequest.id == DemoJobBinding.target_id,
                    )
                    .where(
                        DemoJobBinding.endpoint_operation == DEMO_REFERENCE_PROFILE_OPERATION,
                        DemoJobBinding.target_type == "REFERENCE_PROFILE_REQUEST",
                        or_(
                            and_(Job.status == "PENDING", Job.attempt_count == 0),
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
            candidates: list[DemoReferenceProfileReconciliationCandidate] = []
            for binding, job, request in rows:
                _validate_context(request, binding, job)
                candidates.append(
                    DemoReferenceProfileReconciliationCandidate(
                        binding.demo_actor_id,
                        job.id,
                        request.id,
                        job.request_id,
                    )
                )
            return tuple(candidates)

    async def active_profiles(
        self, *, demo_actor_id: str
    ) -> tuple[DemoReferenceProfileSnapshot, ...]:
        _require_id(demo_actor_id, "demo_actor_id")
        async with self._sessions() as session:
            actor = await session.get(DemoActor, demo_actor_id)
            if actor is None or actor.tombstoned_at is not None:
                raise DemoReferenceProfileUnavailable(
                    "ACTOR_UNAVAILABLE", "Demo actor is unavailable"
                )
            profile = await session.scalar(
                select(DemoReferenceProfile)
                .where(DemoReferenceProfile.demo_actor_id == demo_actor_id)
                .order_by(DemoReferenceProfile.version.desc(), DemoReferenceProfile.id.desc())
                .limit(1)
            )
            if profile is None:
                return ()
            if (
                _DIGEST.fullmatch(profile.content_digest) is None
                or not isinstance(profile.source_assets, list)
                or not profile.source_assets
            ):
                raise DemoReferenceProfileAuthorityCorruption(
                    "REFERENCE_PROFILE_INVALID",
                    "active Reference Profile authority is invalid",
                )
            return (
                DemoReferenceProfileSnapshot(
                    profile.id,
                    profile.version,
                    profile.content_digest,
                    len(profile.source_assets),
                ),
            )

    async def read_completed_result(
        self, *, demo_actor_id: str, job_id: str
    ) -> DemoReferenceProfileCompletedResult:
        """Replay exactly one completed compile envelope; never select a latest profile."""

        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(job_id, "job_id")
        async with self._sessions() as session:
            binding = await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.demo_actor_id == demo_actor_id,
                    DemoJobBinding.job_id == job_id,
                    DemoJobBinding.endpoint_operation == DEMO_REFERENCE_PROFILE_OPERATION,
                    DemoJobBinding.target_type == "REFERENCE_PROFILE_REQUEST",
                )
            )
            if binding is None:
                raise DemoReferenceProfileUnavailable(
                    "RESULT_UNAVAILABLE", "Reference Profile compilation is unavailable"
                )
            request, replayed_binding, job = await self._execution_context(
                session,
                demo_actor_id=demo_actor_id,
                job_id=job_id,
                compile_request_id=binding.target_id,
                lock_job=False,
            )
            if replayed_binding.id != binding.id:
                raise DemoReferenceProfileAuthorityCorruption(
                    "RESULT_BINDING_MISMATCH", "Reference Profile binding does not replay exactly"
                )
            if job.status in {"PENDING", "RUNNING"}:
                raise DemoReferenceProfileResultNotReady(
                    "RESULT_NOT_READY", "Reference Profile compilation is not complete"
                )
            if job.status != "COMPLETED":
                if job.status not in _TERMINAL:
                    raise DemoReferenceProfileAuthorityCorruption(
                        "RESULT_JOB_INVALID", "Reference Profile Job status is invalid"
                    )
                await self._terminal_result_in_session(
                    session, request=request, binding=replayed_binding, job=job
                )
                raise DemoReferenceProfileResultTerminal(
                    "RESULT_TERMINAL", "Reference Profile compilation has no completed result"
                )
            terminal = await self._terminal_result_in_session(
                session, request=request, binding=replayed_binding, job=job
            )
            result = await self._result_for_request(session, request.id)
            if (
                result is None
                or terminal.reference_profile_id is None
                or terminal.profile_digest is None
                or result.reference_profile_id != terminal.reference_profile_id
                or result.reference_profile_digest != terminal.profile_digest
            ):
                raise DemoReferenceProfileAuthorityCorruption(
                    "RESULT_REPLAY_INVALID", "Reference Profile result cannot replay exactly"
                )
            return DemoReferenceProfileCompletedResult(
                job.id,
                request.demo_session_id,
                terminal.reference_profile_id,
                replayed_binding.content_digest,
                result.content_digest,
                terminal.profile_digest,
            )

    async def _finalize_reservation(
        self,
        *,
        demo_actor_id: str,
        reservation: DemoReferenceProfileReservation,
    ) -> DemoReferenceProfileExecutionResult:
        if (
            reservation.state != "RESERVED"
            or reservation.attempt_id is None
            or reservation.attempt is None
            or reservation.lease_token is None
        ):
            raise DemoReferenceProfileAuthorityCorruption(
                "RESERVATION_INVALID", "Reference Profile reservation is incomplete"
            )
        async with self._sessions() as session:
            async with session.begin():
                request, binding, job = await self._execution_context(
                    session,
                    demo_actor_id=demo_actor_id,
                    job_id=reservation.job_id,
                    compile_request_id=reservation.compile_request_id,
                    lock_job=True,
                )
                if job.status == "CANCELLED":
                    return DemoReferenceProfileExecutionResult(
                        demo_actor_id,
                        job.id,
                        request.id,
                        "CANCELLED",
                        job.result_code,
                        replayed=True,
                    )
                if job.status in _TERMINAL:
                    return await self._terminal_result_in_session(
                        session, request=request, binding=binding, job=job
                    )
                attempt = await self._current_attempt(session, job)
                now = self._normalized_now()
                if (
                    job.status != "RUNNING"
                    or job.attempt_count != reservation.attempt
                    or attempt.id != reservation.attempt_id
                    or attempt.status != "RUNNING"
                    or attempt.lease_token != reservation.lease_token
                    or job.lease_token != reservation.lease_token
                    or job.lease_expires_at is None
                    or job.lease_expires_at <= now
                ):
                    return DemoReferenceProfileExecutionResult(
                        demo_actor_id,
                        job.id,
                        request.id,
                        "NO_OP",
                        None,
                        replayed=True,
                    )
                if await self._result_for_request(session, request.id) is not None:
                    raise DemoReferenceProfileAuthorityCorruption(
                        "ACTIVE_RESULT_EXISTS",
                        "active Reference Profile Job already has a result authority",
                    )
                try:
                    command = _compile_command_from_request(request)
                    profile = await self._compiler.compile_reference_profile_in_session(
                        session,
                        command=command,
                        expected_source_bindings=cast(
                            Sequence[Mapping[str, Any]], request.source_bindings
                        ),
                        expected_input_digest=request.input_digest,
                    )
                except (DemoSelfTransferConflict, DemoSelfTransferUnavailable):
                    _finish_job(
                        job,
                        attempt,
                        status="REJECTED",
                        result_code="REFERENCE_PROFILE_REJECTED",
                        error_code=None,
                        now=now,
                    )
                    await session.flush()
                    return DemoReferenceProfileExecutionResult(
                        demo_actor_id,
                        job.id,
                        request.id,
                        "REJECTED",
                        job.result_code,
                    )
                except (
                    DemoReferenceProfileAuthorityCorruption,
                    DemoSelfTransferInputError,
                    DemoSelfTransferAuthorityCorruption,
                ):
                    _finish_job(
                        job,
                        attempt,
                        status="FAILED",
                        result_code="REFERENCE_PROFILE_AUTHORITY_FAILURE",
                        error_code="REFERENCE_PROFILE_AUTHORITY_FAILURE",
                        now=now,
                    )
                    await session.flush()
                    return DemoReferenceProfileExecutionResult(
                        demo_actor_id,
                        job.id,
                        request.id,
                        "FAILED",
                        job.result_code,
                    )

                result = _authority_row(
                    DemoReferenceProfileCompileResult,
                    row_id=None,
                    schema_version=DEMO_REFERENCE_PROFILE_RESULT_SCHEMA,
                    created_at=now,
                    fields={
                        "compile_request_id": request.id,
                        "demo_actor_id": request.demo_actor_id,
                        "demo_job_binding_id": binding.id,
                        "demo_session_id": request.demo_session_id,
                        "input_digest": request.input_digest,
                        "reference_profile_digest": profile.content_digest,
                        "reference_profile_id": profile.reference_profile_id,
                        "result_code": "REFERENCE_PROFILE_COMPILED",
                    },
                )
                session.add(result)
                _finish_job(
                    job,
                    attempt,
                    status="COMPLETED",
                    result_code="REFERENCE_PROFILE_COMPILED",
                    error_code=None,
                    now=now,
                )
                await session.flush()
                return DemoReferenceProfileExecutionResult(
                    demo_actor_id,
                    job.id,
                    request.id,
                    "COMPLETED",
                    job.result_code,
                    profile.reference_profile_id,
                    profile.content_digest,
                    profile.replayed,
                )

    async def _terminal_result(
        self,
        *,
        demo_actor_id: str,
        job_id: str,
        compile_request_id: str,
    ) -> DemoReferenceProfileExecutionResult:
        async with self._sessions() as session:
            request, binding, job = await self._execution_context(
                session,
                demo_actor_id=demo_actor_id,
                job_id=job_id,
                compile_request_id=compile_request_id,
                lock_job=False,
            )
            return await self._terminal_result_in_session(
                session, request=request, binding=binding, job=job
            )

    async def _terminal_result_in_session(
        self,
        session: AsyncSession,
        *,
        request: DemoReferenceProfileCompileRequest,
        binding: DemoJobBinding,
        job: Job,
    ) -> DemoReferenceProfileExecutionResult:
        if job.status not in _TERMINAL or job.finalized_at is None or job.result_code is None:
            raise DemoReferenceProfileAuthorityCorruption(
                "TERMINAL_JOB_INVALID",
                "Reference Profile Job is not a valid terminal authority",
            )
        result = await self._result_for_request(session, request.id)
        if job.status == "COMPLETED":
            if result is None:
                raise DemoReferenceProfileAuthorityCorruption(
                    "COMPLETED_RESULT_MISSING",
                    "completed Reference Profile Job lacks its result authority",
                )
            profile = await session.get(DemoReferenceProfile, result.reference_profile_id)
            if (
                profile is None
                or result.demo_job_binding_id != binding.id
                or result.reference_profile_digest != profile.content_digest
                or result.input_digest != request.input_digest
                or result.result_code != job.result_code
            ):
                raise DemoReferenceProfileAuthorityCorruption(
                    "COMPLETED_RESULT_INVALID",
                    "Reference Profile result authority cannot be replayed",
                )
            return DemoReferenceProfileExecutionResult(
                request.demo_actor_id,
                job.id,
                request.id,
                "COMPLETED",
                job.result_code,
                profile.id,
                profile.content_digest,
                True,
            )
        if result is not None:
            raise DemoReferenceProfileAuthorityCorruption(
                "NON_COMPLETED_RESULT_EXISTS",
                "non-completed Reference Profile Job has a result authority",
            )
        return DemoReferenceProfileExecutionResult(
            request.demo_actor_id,
            job.id,
            request.id,
            cast(Literal["REJECTED", "FAILED", "CANCELLED"], job.status),
            job.result_code,
            replayed=True,
        )

    async def _binding_for_key(
        self, session: AsyncSession, *, demo_actor_id: str, key_hash: str
    ) -> DemoJobBinding | None:
        return cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.demo_actor_id == demo_actor_id,
                    DemoJobBinding.endpoint_operation == DEMO_REFERENCE_PROFILE_OPERATION,
                    DemoJobBinding.idempotency_key_hash == key_hash,
                )
            ),
        )

    async def _replay_admission(
        self,
        session: AsyncSession,
        binding: DemoJobBinding,
        *,
        request_digest: str,
    ) -> DemoReferenceProfileCompilationAccepted:
        if binding.request_digest != request_digest:
            raise DemoReferenceProfileConflict(
                "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                "Reference Profile idempotency key is bound to another request",
            )
        request, _, job = await self._execution_context(
            session,
            demo_actor_id=binding.demo_actor_id,
            job_id=binding.job_id,
            compile_request_id=binding.target_id,
            lock_job=False,
        )
        return DemoReferenceProfileCompilationAccepted(job.id, request.id, job.request_id, True)

    async def _execution_context(
        self,
        session: AsyncSession,
        *,
        demo_actor_id: str,
        job_id: str,
        compile_request_id: str,
        lock_job: bool,
    ) -> tuple[DemoReferenceProfileCompileRequest, DemoJobBinding, Job]:
        request = await session.get(DemoReferenceProfileCompileRequest, compile_request_id)
        if request is None or request.demo_actor_id != demo_actor_id:
            raise DemoReferenceProfileUnavailable(
                "REQUEST_UNAVAILABLE",
                "Reference Profile compile request is unavailable",
            )
        binding = await session.scalar(
            select(DemoJobBinding).where(
                DemoJobBinding.id == request.demo_job_binding_id,
                DemoJobBinding.job_id == job_id,
            )
        )
        statement = select(Job).where(Job.id == job_id)
        if lock_job:
            statement = statement.with_for_update()
        job = await session.scalar(statement)
        if binding is None or job is None:
            raise DemoReferenceProfileAuthorityCorruption(
                "EXECUTION_ENVELOPE_MISSING",
                "Reference Profile execution envelope is incomplete",
            )
        _validate_context(request, binding, job)
        return request, binding, job

    @staticmethod
    async def _current_attempt(session: AsyncSession, job: Job) -> JobAttempt:
        attempt = await session.scalar(
            select(JobAttempt)
            .where(
                JobAttempt.job_id == job.id,
                JobAttempt.attempt == job.attempt_count,
            )
            .with_for_update()
        )
        if attempt is None:
            raise DemoReferenceProfileAuthorityCorruption(
                "JOB_ATTEMPT_MISSING", "Reference Profile Job attempt is missing"
            )
        return attempt

    @staticmethod
    async def _result_for_request(
        session: AsyncSession, compile_request_id: str
    ) -> DemoReferenceProfileCompileResult | None:
        return cast(
            DemoReferenceProfileCompileResult | None,
            await session.scalar(
                select(DemoReferenceProfileCompileResult).where(
                    DemoReferenceProfileCompileResult.compile_request_id == compile_request_id
                )
            ),
        )

    def _normalized_now(self) -> datetime:
        now = self._now()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise DemoReferenceProfileAuthorityCorruption(
                "INVALID_CLOCK", "Reference Profile queue clock must be timezone-aware"
            )
        return now.astimezone(UTC)


def _request_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    demo_job_binding_id: str,
    desired_delta_profile_id: str,
    style_profile_id: str | None,
    identity_constraints_id: str | None,
    compiler_version: str,
    frozen: DemoReferenceProfileInputSnapshot,
) -> dict[str, Any]:
    return {
        "compiler_version": compiler_version,
        "demo_actor_id": demo_actor_id,
        "demo_job_binding_id": demo_job_binding_id,
        "demo_session_id": demo_session_id,
        "desired_delta_profile_id": desired_delta_profile_id,
        "execution_policy_version": DEMO_REFERENCE_PROFILE_EXECUTION_POLICY,
        "identity_constraints_id": identity_constraints_id,
        "input_digest": frozen.input_digest,
        "lease_timeout_seconds": DEMO_REFERENCE_PROFILE_LEASE_SECONDS,
        "max_attempts": DEMO_REFERENCE_PROFILE_MAX_ATTEMPTS,
        "source_bindings": [dict(item) for item in frozen.source_bindings],
        "style_profile_id": style_profile_id,
    }


def _binding_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    job_id: str,
    idempotency_key_hash_value: str,
    request_digest: str,
    compile_request_id: str,
) -> dict[str, Any]:
    return {
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "endpoint_operation": DEMO_REFERENCE_PROFILE_OPERATION,
        "idempotency_key_hash": idempotency_key_hash_value,
        "job_id": job_id,
        "request_digest": request_digest,
        "target_id": compile_request_id,
        "target_type": "REFERENCE_PROFILE_REQUEST",
    }


def _compile_command_from_request(
    request: DemoReferenceProfileCompileRequest,
) -> CompileDemoReferenceProfile:
    if not isinstance(request.source_bindings, list):
        raise DemoReferenceProfileAuthorityCorruption(
            "SOURCE_BINDINGS_INVALID", "Reference Profile source bindings are invalid"
        )
    try:
        sources = tuple(
            DemoReferenceSource(asset_id=item["asset_id"], view=item["view"])
            for item in request.source_bindings
            if isinstance(item, Mapping)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DemoReferenceProfileAuthorityCorruption(
            "SOURCE_BINDINGS_INVALID",
            "Reference Profile source bindings cannot be reconstructed",
        ) from exc
    if len(sources) != len(request.source_bindings):
        raise DemoReferenceProfileAuthorityCorruption(
            "SOURCE_BINDINGS_INVALID", "Reference Profile source binding types are invalid"
        )
    command = CompileDemoReferenceProfile(
        request.demo_actor_id,
        request.demo_session_id,
        request.desired_delta_profile_id,
        request.style_profile_id,
        request.identity_constraints_id,
        sources,
    )
    command.validate()
    return command


def _validate_context(
    request: DemoReferenceProfileCompileRequest,
    binding: DemoJobBinding,
    job: Job,
) -> None:
    request_payload = _authority_payload(request)
    binding_payload = _binding_payload(
        demo_actor_id=request.demo_actor_id,
        demo_session_id=request.demo_session_id,
        job_id=job.id,
        idempotency_key_hash_value=binding.idempotency_key_hash,
        request_digest=binding.request_digest,
        compile_request_id=request.id,
    )
    if (
        request.schema_version != DEMO_REFERENCE_PROFILE_REQUEST_SCHEMA
        or request.compiler_version != DEMO_REFERENCE_COMPILER_VERSION
        or request.execution_policy_version != DEMO_REFERENCE_PROFILE_EXECUTION_POLICY
        or request.max_attempts != DEMO_REFERENCE_PROFILE_MAX_ATTEMPTS
        or request.lease_timeout_seconds != DEMO_REFERENCE_PROFILE_LEASE_SECONDS
        or request.demo_job_binding_id != binding.id
        or request.canonical_payload != request_payload
        or request.content_digest
        != _authority_digest(DEMO_REFERENCE_PROFILE_REQUEST_SCHEMA, request_payload)
        or binding.demo_actor_id != request.demo_actor_id
        or binding.demo_session_id != request.demo_session_id
        or binding.endpoint_operation != DEMO_REFERENCE_PROFILE_OPERATION
        or binding.target_type != "REFERENCE_PROFILE_REQUEST"
        or binding.target_id != request.id
        or binding.schema_version != DEMO_JOB_BINDING_SCHEMA
        or binding.canonical_payload != binding_payload
        or binding.content_digest != _authority_digest(DEMO_JOB_BINDING_SCHEMA, binding_payload)
        or job.id != binding.job_id
        or job.job_type != DEMO_REFERENCE_PROFILE_JOB_TYPE
        or job.idempotency_key_hash
        != _formal_job_key_hash(request.demo_actor_id, binding.idempotency_key_hash)
        or job.payload != {}
        or job.owner_user_id is not None
        or job.ingestion_upload_intent_id is not None
        or job.result_asset_id is not None
    ):
        raise DemoReferenceProfileAuthorityCorruption(
            "EXECUTION_ENVELOPE_INVALID", "Reference Profile execution envelope is invalid"
        )


def _finish_job(
    job: Job,
    attempt: JobAttempt,
    *,
    status: Literal["COMPLETED", "REJECTED", "FAILED"],
    result_code: str,
    error_code: str | None,
    now: datetime,
) -> None:
    if job.status != "RUNNING" or attempt.status != "RUNNING":
        raise DemoReferenceProfileAuthorityCorruption(
            "TERMINAL_TRANSITION_INVALID",
            "Reference Profile Job cannot finish from its current state",
        )
    attempt.status = status
    attempt.result_code = result_code if status != "FAILED" else None
    attempt.error_code = error_code
    attempt.finished_at = now
    job.status = status
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = now
    job.result_code = result_code
    job.updated_at = now


def _finish_exhausted_job(job: Job, *, now: datetime) -> None:
    if job.status != "RUNNING":
        raise DemoReferenceProfileAuthorityCorruption(
            "TERMINAL_TRANSITION_INVALID",
            "Reference Profile Job cannot exhaust attempts from its current state",
        )
    job.status = "FAILED"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = now
    job.result_code = "REFERENCE_PROFILE_MAX_ATTEMPTS"
    job.updated_at = now


def _authority_row[AuthorityT](
    model: type[AuthorityT],
    *,
    row_id: str | None,
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
    payload = _authority_payload(row)
    row.canonical_payload = payload
    row.content_digest = _authority_digest(schema_version, payload)
    return cast(AuthorityT, row)


def _authority_payload(row: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:
        if column.name in _NON_AUTHORITY_COLUMNS:
            continue
        payload[column.name] = _canonical_value(getattr(row, column.name))
    return payload


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return value


def _authority_digest(schema_version: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _formal_job_key_hash(demo_actor_id: str, client_key_hash: str) -> str:
    preimage = (
        f"mirror.demo/JobIdempotency/v1\n{demo_actor_id}\n"
        f"{DEMO_REFERENCE_PROFILE_OPERATION}\n{client_key_hash}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoReferenceProfileInputError(
            "INVALID_ID", f"{name} must be a lowercase hexadecimal ID"
        )


__all__ = [
    "DEMO_REFERENCE_PROFILE_CAPABILITY",
    "DEMO_REFERENCE_PROFILE_EXECUTION_POLICY",
    "DEMO_REFERENCE_PROFILE_JOB_TYPE",
    "DEMO_REFERENCE_PROFILE_LEASE_SECONDS",
    "DEMO_REFERENCE_PROFILE_MAX_ATTEMPTS",
    "DEMO_REFERENCE_PROFILE_OPERATION",
    "CreateDemoReferenceProfileCompilation",
    "DemoReferenceProfileAuthorityCorruption",
    "DemoReferenceProfileCompilationAccepted",
    "DemoReferenceProfileCompletedResult",
    "DemoReferenceProfileConflict",
    "DemoReferenceProfileExecutionResult",
    "DemoReferenceProfileInputError",
    "DemoReferenceProfileReconciliationCandidate",
    "DemoReferenceProfileReservation",
    "DemoReferenceProfileResultNotReady",
    "DemoReferenceProfileResultTerminal",
    "DemoReferenceProfileService",
    "DemoReferenceProfileSnapshot",
    "DemoReferenceProfileUnavailable",
]
