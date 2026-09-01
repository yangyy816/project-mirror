"""Durable, byte-free queue authority for D10 Context compilation."""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable, Mapping
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
from mirror_api.demo_memory_service import (
    DEMO_CONTEXT_COMPILE_OPERATION,
    DEMO_CONTEXT_COMPILER_VERSION,
    CompileDemoContext,
    DemoContextInputSnapshot,
    DemoMemoryAuthorityCorruption,
    DemoMemoryConflict,
    DemoMemoryInputError,
    DemoMemoryService,
    DemoMemoryUnavailable,
    _acquire_actor_lock,
    _lock_active_actor,
    _lock_active_session,
)
from mirror_api.demo_models import (
    DemoContextCompilation,
    DemoContextCompileRequest,
    DemoContextCompileResult,
    DemoJobBinding,
)
from mirror_api.models import Job, JobAttempt, new_id, utcnow

DEMO_CONTEXT_JOB_TYPE: Final = "demo_p3_p7.context.compile"
DEMO_CONTEXT_REQUEST_SCHEMA: Final = "mirror.demo/DemoContextCompileRequest/v1"
DEMO_CONTEXT_RESULT_SCHEMA: Final = "mirror.demo/DemoContextCompileResult/v1"
DEMO_CONTEXT_CAPABILITY: Final = "P7_CONTEXT_COMPILER"
DEMO_CONTEXT_EXECUTION_POLICY: Final = "demo-context-queue-v1"
DEMO_CONTEXT_MAX_ATTEMPTS: Final = 3
DEMO_CONTEXT_LEASE_SECONDS: Final = 300
DEMO_JOB_BINDING_SCHEMA: Final = "mirror.demo/DemoJobBinding/v1"
_ID = re.compile(r"^[0-9a-f]{32}$")
_TERMINAL: Final = frozenset({"COMPLETED", "REJECTED", "FAILED", "CANCELLED"})
_NON_AUTHORITY: Final = frozenset(
    {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
)

ContextExecutionStatus = Literal["COMPLETED", "REJECTED", "FAILED", "CANCELLED", "NO_OP"]
ContextReservationState = Literal["RESERVED", "ACTIVE", "TERMINAL"]


class DemoContextQueueError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DemoContextQueueInputError(DemoContextQueueError):
    pass


class DemoContextQueueUnavailable(DemoContextQueueError):
    pass


class DemoContextQueueConflict(DemoContextQueueError):
    pass


class DemoContextQueueAuthorityCorruption(DemoContextQueueError):
    pass


@dataclass(frozen=True, slots=True)
class CreateDemoContextCompilation:
    demo_actor_id: str
    demo_session_id: str
    aesthetic_profile_id: str
    current_instruction_digest: str
    context_as_of_time: datetime
    idempotency_key: str
    request_id: str
    compiler_version: str = DEMO_CONTEXT_COMPILER_VERSION

    def as_compile_command(self) -> CompileDemoContext:
        return CompileDemoContext(
            self.demo_actor_id,
            self.demo_session_id,
            self.aesthetic_profile_id,
            self.current_instruction_digest,
            self.context_as_of_time,
            self.idempotency_key,
            self.request_id,
            self.compiler_version,
        )

    def validate(self) -> None:
        self.as_compile_command().validate()


@dataclass(frozen=True, slots=True)
class DemoContextCompilationAccepted:
    job_id: str
    context_request_id: str
    request_id: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class DemoContextReservation:
    state: ContextReservationState
    job_id: str
    context_request_id: str
    attempt_id: str | None
    attempt: int | None
    lease_token: str | None
    terminal_status: str | None


@dataclass(frozen=True, slots=True)
class DemoContextReconciliationCandidate:
    demo_actor_id: str
    job_id: str
    context_request_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class DemoContextExecutionResult:
    demo_actor_id: str
    job_id: str
    context_request_id: str
    status: ContextExecutionStatus
    result_code: str | None
    context_compilation_id: str | None = None
    context_digest: str | None = None
    replayed: bool = False


class DemoContextQueueService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions, self._now = session_factory, now
        self._compiler = DemoMemoryService(session_factory=session_factory, now=now)

    async def admit(self, command: CreateDemoContextCompilation) -> DemoContextCompilationAccepted:
        command.validate()
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {
                "aesthetic_profile_id": command.aesthetic_profile_id,
                "compiler_version": command.compiler_version,
                "context_as_of_time": _time(command.context_as_of_time),
                "current_instruction_digest": command.current_instruction_digest,
                "session_id": command.demo_session_id,
            }
        )
        async with self._sessions() as session:
            async with session.begin():
                now = self._normalized_now()
                await _acquire_actor_lock(session, command.demo_actor_id)
                try:
                    await _lock_active_actor(session, command.demo_actor_id)
                    await _lock_active_session(
                        session,
                        actor_id=command.demo_actor_id,
                        session_id=command.demo_session_id,
                        as_of=max(command.context_as_of_time.astimezone(UTC), now),
                    )
                except DemoMemoryUnavailable as exc:
                    raise DemoContextQueueUnavailable("CONTEXT_UNAVAILABLE", str(exc)) from exc
                existing = await self._binding_for_key(session, command.demo_actor_id, key_hash)
                if existing is not None:
                    return await self._replay_admission(session, existing, request_digest)
                try:
                    frozen = await self._compiler.freeze_context_inputs_in_session(
                        session, command.as_compile_command()
                    )
                except DemoMemoryInputError as exc:
                    raise DemoContextQueueInputError("INVALID_INPUT", str(exc)) from exc
                except DemoMemoryUnavailable as exc:
                    raise DemoContextQueueUnavailable("CONTEXT_UNAVAILABLE", str(exc)) from exc
                except (DemoMemoryConflict, DemoMemoryAuthorityCorruption) as exc:
                    raise DemoContextQueueConflict("CONTEXT_CONFLICT", str(exc)) from exc
                prior = await session.scalar(
                    select(DemoContextCompilation.id).where(
                        DemoContextCompilation.demo_actor_id == command.demo_actor_id,
                        DemoContextCompilation.demo_session_id == command.demo_session_id,
                        DemoContextCompilation.context_as_of_time == frozen.context_as_of_time,
                        DemoContextCompilation.compiler_version == command.compiler_version,
                    )
                )
                if prior is not None:
                    raise DemoContextQueueConflict(
                        "IMMUTABLE_CONTEXT_EXISTS", "Context input already has immutable authority"
                    )
                prior_request = await self._request_for_input(
                    session,
                    actor=command.demo_actor_id,
                    input_digest=frozen.input_digest,
                )
                if prior_request is not None:
                    raise DemoContextQueueConflict(
                        "IMMUTABLE_CONTEXT_INPUT_EXISTS",
                        "Context input is already bound to another immutable request",
                    )
                job_id, request_id, binding_id = new_id(), new_id(), new_id()
                job = Job(
                    id=job_id,
                    job_type=DEMO_CONTEXT_JOB_TYPE,
                    status="PENDING",
                    idempotency_key_hash=_formal_key(command.demo_actor_id, key_hash),
                    request_id=command.request_id,
                    payload={},
                    owner_user_id=None,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
                request = _authority_row(
                    DemoContextCompileRequest,
                    row_id=request_id,
                    schema_version=DEMO_CONTEXT_REQUEST_SCHEMA,
                    created_at=now,
                    fields=_request_fields(command, binding_id, frozen),
                )
                binding = _authority_row(
                    DemoJobBinding,
                    row_id=binding_id,
                    schema_version=DEMO_JOB_BINDING_SCHEMA,
                    created_at=now,
                    fields=_binding_fields(
                        command.demo_actor_id,
                        command.demo_session_id,
                        job_id,
                        key_hash,
                        request_digest,
                    ),
                )
                try:
                    async with session.begin_nested():
                        session.add(job)
                        await session.flush()
                        session.add(binding)
                        await session.flush()
                        session.add(request)
                        await session.flush()
                except IntegrityError as exc:
                    winner = await self._binding_for_key(session, command.demo_actor_id, key_hash)
                    if winner is not None:
                        return await self._replay_admission(session, winner, request_digest)
                    input_winner = await self._request_for_input(
                        session,
                        actor=command.demo_actor_id,
                        input_digest=frozen.input_digest,
                    )
                    if input_winner is not None:
                        raise DemoContextQueueConflict(
                            "IMMUTABLE_CONTEXT_INPUT_EXISTS",
                            "Context input is already bound to another immutable request",
                        ) from exc
                    raise DemoContextQueueAuthorityCorruption(
                        "ADMISSION_CONFLICT_WITHOUT_WINNER",
                        "Context admission conflict has no winner",
                    ) from exc
                return DemoContextCompilationAccepted(job_id, request_id, command.request_id, False)

    async def reserve(
        self, *, demo_actor_id: str, job_id: str, context_request_id: str
    ) -> DemoContextReservation:
        _ids(demo_actor_id, job_id, context_request_id)
        async with self._sessions() as session:
            async with session.begin():
                request, _, job = await self._context(
                    session, demo_actor_id, job_id, context_request_id, lock=True
                )
                if job.status in _TERMINAL:
                    return DemoContextReservation(
                        "TERMINAL", job.id, request.id, None, None, None, job.status
                    )
                now = self._normalized_now()
                if job.status == "RUNNING":
                    attempt = await self._attempt(session, job)
                    if (
                        attempt.status != "RUNNING"
                        or attempt.finished_at is not None
                        or attempt.lease_token != job.lease_token
                        or job.lease_token is None
                        or job.lease_acquired_at is None
                        or job.lease_expires_at is None
                    ):
                        raise DemoContextQueueAuthorityCorruption(
                            "RUNNING_ATTEMPT_INVALID", "running Context attempt is invalid"
                        )
                    if job.lease_expires_at > now:
                        return DemoContextReservation(
                            "ACTIVE", job.id, request.id, attempt.id, attempt.attempt, None, None
                        )
                    attempt.status, attempt.error_code, attempt.finished_at = (
                        "FAILED",
                        "LEASE_EXPIRED",
                        now,
                    )
                    if job.attempt_count >= request.max_attempts:
                        _exhaust(job, now)
                        await session.flush()
                        return DemoContextReservation(
                            "TERMINAL", job.id, request.id, None, None, None, "FAILED"
                        )
                elif (
                    job.status != "PENDING"
                    or job.attempt_count != 0
                    or any(
                        value is not None
                        for value in (job.lease_token, job.lease_acquired_at, job.lease_expires_at)
                    )
                ):
                    raise DemoContextQueueAuthorityCorruption(
                        "PENDING_JOB_INVALID", "pending Context Job has invalid lease authority"
                    )
                number, token = job.attempt_count + 1, secrets.token_hex(32)
                if number > request.max_attempts:
                    raise DemoContextQueueAuthorityCorruption(
                        "ATTEMPT_LIMIT_INVALID", "Context attempt limit was bypassed"
                    )
                attempt = JobAttempt(
                    id=new_id(),
                    job_id=job.id,
                    attempt=number,
                    status="RUNNING",
                    lease_token=token,
                    started_at=now,
                )
                session.add(attempt)
                job.status, job.attempt_count, job.lease_token = "RUNNING", number, token
                job.lease_acquired_at, job.lease_expires_at, job.updated_at = (
                    now,
                    now + timedelta(seconds=request.lease_timeout_seconds),
                    now,
                )
                await session.flush()
                return DemoContextReservation(
                    "RESERVED", job.id, request.id, attempt.id, number, token, None
                )

    async def execute_task(
        self, *, demo_actor_id: str, job_id: str, context_request_id: str
    ) -> DemoContextExecutionResult:
        reserved = await self.reserve(
            demo_actor_id=demo_actor_id, job_id=job_id, context_request_id=context_request_id
        )
        if reserved.state == "ACTIVE":
            return DemoContextExecutionResult(
                demo_actor_id, job_id, context_request_id, "NO_OP", None, replayed=True
            )
        if reserved.state == "TERMINAL":
            return await self._terminal(demo_actor_id, job_id, context_request_id)
        return await self._finalize(demo_actor_id, reserved)

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoContextReconciliationCandidate, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise DemoContextQueueInputError(
                "INVALID_RECONCILIATION_LIMIT", "limit is outside boundary"
            )
        now = self._normalized_now()
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(DemoJobBinding, Job, DemoContextCompileRequest)
                    .join(Job, Job.id == DemoJobBinding.job_id)
                    .join(
                        DemoContextCompileRequest,
                        DemoContextCompileRequest.demo_job_binding_id == DemoJobBinding.id,
                    )
                    .where(
                        DemoJobBinding.endpoint_operation == DEMO_CONTEXT_COMPILE_OPERATION,
                        DemoJobBinding.target_type == "DEMO_SESSION",
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
            return tuple(
                DemoContextReconciliationCandidate(
                    binding.demo_actor_id, job.id, request.id, job.request_id
                )
                for binding, job, request in rows
                if _validate(request, binding, job)
            )

    async def _finalize(
        self, demo_actor_id: str, reservation: DemoContextReservation
    ) -> DemoContextExecutionResult:
        if (
            reservation.attempt_id is None
            or reservation.attempt is None
            or reservation.lease_token is None
        ):
            raise DemoContextQueueAuthorityCorruption(
                "RESERVATION_INVALID", "incomplete Context reservation"
            )
        async with self._sessions() as session:
            async with session.begin():
                request, binding, job = await self._context(
                    session,
                    demo_actor_id,
                    reservation.job_id,
                    reservation.context_request_id,
                    lock=True,
                )
                if job.status in _TERMINAL:
                    return await self._terminal_in_session(session, request, binding, job)
                attempt, now = await self._attempt(session, job), self._normalized_now()
                if (
                    job.status != "RUNNING"
                    or attempt.id != reservation.attempt_id
                    or attempt.lease_token != reservation.lease_token
                    or job.lease_token != reservation.lease_token
                    or job.lease_expires_at is None
                    or job.lease_expires_at <= now
                ):
                    return DemoContextExecutionResult(
                        demo_actor_id, job.id, request.id, "NO_OP", None, replayed=True
                    )
                if await self._result(session, request.id) is not None:
                    raise DemoContextQueueAuthorityCorruption(
                        "ACTIVE_RESULT_EXISTS", "active Context Job already has result"
                    )
                try:
                    await _acquire_actor_lock(session, demo_actor_id)
                    await _lock_active_actor(session, demo_actor_id)
                    await _lock_active_session(
                        session,
                        actor_id=demo_actor_id,
                        session_id=request.demo_session_id,
                        as_of=max(request.context_as_of_time.astimezone(UTC), now),
                    )
                except DemoMemoryUnavailable:
                    _finish(job, attempt, "REJECTED", "CONTEXT_REJECTED", None, now)
                    await session.flush()
                    return DemoContextExecutionResult(
                        demo_actor_id, job.id, request.id, "REJECTED", job.result_code
                    )
                try:
                    async with session.begin_nested():
                        command, frozen = _command_and_snapshot(request)
                        context = await self._compiler.materialize_context_in_session(
                            session,
                            command=command,
                            expected=frozen,
                            demo_job_binding_id=binding.id,
                            audit_now=now,
                        )
                except (DemoMemoryUnavailable, DemoMemoryConflict):
                    _finish(job, attempt, "REJECTED", "CONTEXT_REJECTED", None, now)
                    await session.flush()
                    return DemoContextExecutionResult(
                        demo_actor_id, job.id, request.id, "REJECTED", job.result_code
                    )
                except (DemoMemoryInputError, DemoMemoryAuthorityCorruption):
                    _finish(
                        job,
                        attempt,
                        "FAILED",
                        "CONTEXT_AUTHORITY_FAILURE",
                        "CONTEXT_AUTHORITY_FAILURE",
                        now,
                    )
                    await session.flush()
                    return DemoContextExecutionResult(
                        demo_actor_id, job.id, request.id, "FAILED", job.result_code
                    )
                except IntegrityError:
                    collision = await session.scalar(
                        select(DemoContextCompilation.id).where(
                            DemoContextCompilation.demo_actor_id == request.demo_actor_id,
                            DemoContextCompilation.demo_session_id == request.demo_session_id,
                            DemoContextCompilation.context_as_of_time == request.context_as_of_time,
                            DemoContextCompilation.compiler_version == request.compiler_version,
                        )
                    )
                    if collision is not None:
                        _finish(job, attempt, "REJECTED", "CONTEXT_REJECTED", None, now)
                        status: Literal["REJECTED", "FAILED"] = "REJECTED"
                    else:
                        _finish(
                            job,
                            attempt,
                            "FAILED",
                            "CONTEXT_AUTHORITY_FAILURE",
                            "CONTEXT_AUTHORITY_FAILURE",
                            now,
                        )
                        status = "FAILED"
                    await session.flush()
                    return DemoContextExecutionResult(
                        demo_actor_id,
                        job.id,
                        request.id,
                        status,
                        job.result_code,
                    )
                result = _authority_row(
                    DemoContextCompileResult,
                    row_id=None,
                    schema_version=DEMO_CONTEXT_RESULT_SCHEMA,
                    created_at=now,
                    fields={
                        "demo_actor_id": request.demo_actor_id,
                        "demo_session_id": request.demo_session_id,
                        "compile_request_id": request.id,
                        "demo_job_binding_id": binding.id,
                        "context_compilation_id": context.context_compilation_id,
                        "context_digest": context.context_digest,
                        "input_digest": request.input_digest,
                        "result_code": "CONTEXT_COMPILED",
                    },
                )
                session.add(result)
                _finish(job, attempt, "COMPLETED", "CONTEXT_COMPILED", None, now)
                await session.flush()
                return DemoContextExecutionResult(
                    demo_actor_id,
                    job.id,
                    request.id,
                    "COMPLETED",
                    job.result_code,
                    context.context_compilation_id,
                    context.context_digest,
                )

    async def _terminal(
        self, actor: str, job_id: str, request_id: str
    ) -> DemoContextExecutionResult:
        async with self._sessions() as session:
            request, binding, job = await self._context(
                session, actor, job_id, request_id, lock=False
            )
            return await self._terminal_in_session(session, request, binding, job)

    async def _terminal_in_session(
        self,
        session: AsyncSession,
        request: DemoContextCompileRequest,
        binding: DemoJobBinding,
        job: Job,
    ) -> DemoContextExecutionResult:
        if job.status not in _TERMINAL or job.finalized_at is None or job.result_code is None:
            raise DemoContextQueueAuthorityCorruption(
                "TERMINAL_JOB_INVALID", "terminal Context Job invalid"
            )
        result = await self._result(session, request.id)
        if job.status == "COMPLETED":
            if result is None:
                raise DemoContextQueueAuthorityCorruption(
                    "COMPLETED_RESULT_MISSING", "completed Context Job has no result"
                )
            context = await session.get(DemoContextCompilation, result.context_compilation_id)
            if (
                context is None
                or result.demo_job_binding_id != binding.id
                or result.input_digest != request.input_digest
                or result.context_digest != context.content_digest
                or result.result_code != job.result_code
            ):
                raise DemoContextQueueAuthorityCorruption(
                    "COMPLETED_RESULT_INVALID", "Context result cannot replay"
                )
            return DemoContextExecutionResult(
                request.demo_actor_id,
                job.id,
                request.id,
                "COMPLETED",
                job.result_code,
                context.id,
                context.content_digest,
                True,
            )
        if result is not None:
            raise DemoContextQueueAuthorityCorruption(
                "NON_COMPLETED_RESULT_EXISTS", "nonterminal Context has result"
            )
        return DemoContextExecutionResult(
            request.demo_actor_id,
            job.id,
            request.id,
            cast(Literal["REJECTED", "FAILED", "CANCELLED"], job.status),
            job.result_code,
            replayed=True,
        )

    async def _binding_for_key(
        self, session: AsyncSession, actor: str, key: str
    ) -> DemoJobBinding | None:
        return cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.demo_actor_id == actor,
                    DemoJobBinding.endpoint_operation == DEMO_CONTEXT_COMPILE_OPERATION,
                    DemoJobBinding.idempotency_key_hash == key,
                )
            ),
        )

    @staticmethod
    async def _request_for_input(
        session: AsyncSession, *, actor: str, input_digest: str
    ) -> DemoContextCompileRequest | None:
        return cast(
            DemoContextCompileRequest | None,
            await session.scalar(
                select(DemoContextCompileRequest).where(
                    DemoContextCompileRequest.demo_actor_id == actor,
                    DemoContextCompileRequest.input_digest == input_digest,
                )
            ),
        )

    async def _replay_admission(
        self, session: AsyncSession, binding: DemoJobBinding, digest: str
    ) -> DemoContextCompilationAccepted:
        if binding.request_digest != digest:
            raise DemoContextQueueConflict(
                "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD", "key is bound to another request"
            )
        request, _, job = await self._context(
            session, binding.demo_actor_id, binding.job_id, "", lock=False, binding=binding
        )
        return DemoContextCompilationAccepted(job.id, request.id, job.request_id, True)

    async def _context(
        self,
        session: AsyncSession,
        actor: str,
        job_id: str,
        request_id: str,
        *,
        lock: bool,
        binding: DemoJobBinding | None = None,
    ) -> tuple[DemoContextCompileRequest, DemoJobBinding, Job]:
        if binding is None:
            request = await session.get(DemoContextCompileRequest, request_id)
            if request is None or request.demo_actor_id != actor:
                raise DemoContextQueueUnavailable(
                    "REQUEST_UNAVAILABLE", "Context request unavailable"
                )
            binding = await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.id == request.demo_job_binding_id,
                    DemoJobBinding.job_id == job_id,
                )
            )
        else:
            request = await session.scalar(
                select(DemoContextCompileRequest).where(
                    DemoContextCompileRequest.demo_job_binding_id == binding.id
                )
            )
        statement = select(Job).where(Job.id == job_id)
        if lock:
            statement = statement.with_for_update()
        job = await session.scalar(statement)
        if request is None or binding is None or job is None:
            raise DemoContextQueueAuthorityCorruption(
                "EXECUTION_ENVELOPE_MISSING", "Context envelope incomplete"
            )
        _validate(request, binding, job)
        return request, binding, job

    @staticmethod
    async def _attempt(session: AsyncSession, job: Job) -> JobAttempt:
        attempt = await session.scalar(
            select(JobAttempt)
            .where(JobAttempt.job_id == job.id, JobAttempt.attempt == job.attempt_count)
            .with_for_update()
        )
        if attempt is None:
            raise DemoContextQueueAuthorityCorruption(
                "JOB_ATTEMPT_MISSING", "Context attempt missing"
            )
        return attempt

    @staticmethod
    async def _result(session: AsyncSession, request_id: str) -> DemoContextCompileResult | None:
        return cast(
            DemoContextCompileResult | None,
            await session.scalar(
                select(DemoContextCompileResult).where(
                    DemoContextCompileResult.compile_request_id == request_id
                )
            ),
        )

    def _normalized_now(self) -> datetime:
        now = self._now()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise DemoContextQueueAuthorityCorruption(
                "INVALID_CLOCK", "queue clock must be timezone-aware"
            )
        return now.astimezone(UTC)


def _request_fields(
    command: CreateDemoContextCompilation, binding_id: str, frozen: DemoContextInputSnapshot
) -> dict[str, Any]:
    return {
        "demo_actor_id": command.demo_actor_id,
        "demo_session_id": command.demo_session_id,
        "demo_job_binding_id": binding_id,
        "aesthetic_profile_id": frozen.aesthetic_profile_id,
        "aesthetic_profile_digest": frozen.profile_digest,
        "context_as_of_time": frozen.context_as_of_time,
        "current_instruction_digest": frozen.current_instruction_digest,
        "compiler_version": frozen.compiler_version,
        "selected_evidence": list(frozen.selected_evidence),
        "rejected_evidence": list(frozen.rejected_evidence),
        "budgets": dict(frozen.budgets),
        "trace_payload": dict(frozen.trace_payload),
        "compilation_watermark": frozen.compilation_watermark,
        "input_digest": frozen.input_digest,
        "expires_at": frozen.expires_at,
        "execution_policy_version": DEMO_CONTEXT_EXECUTION_POLICY,
        "max_attempts": DEMO_CONTEXT_MAX_ATTEMPTS,
        "lease_timeout_seconds": DEMO_CONTEXT_LEASE_SECONDS,
    }


def _binding_fields(
    actor: str, session_id: str, job_id: str, key: str, digest: str
) -> dict[str, Any]:
    return {
        "demo_actor_id": actor,
        "demo_session_id": session_id,
        "job_id": job_id,
        "endpoint_operation": DEMO_CONTEXT_COMPILE_OPERATION,
        "idempotency_key_hash": key,
        "request_digest": digest,
        "target_type": "DEMO_SESSION",
        "target_id": session_id,
    }


def _command_and_snapshot(
    request: DemoContextCompileRequest,
) -> tuple[CompileDemoContext, DemoContextInputSnapshot]:
    command = CompileDemoContext(
        request.demo_actor_id,
        request.demo_session_id,
        request.aesthetic_profile_id,
        request.current_instruction_digest,
        request.context_as_of_time,
        "replayed-context-key",
        "replayed-context-request",
        request.compiler_version,
    )
    snapshot = DemoContextInputSnapshot(
        request.aesthetic_profile_id,
        request.aesthetic_profile_digest,
        request.context_as_of_time,
        request.compiler_version,
        request.current_instruction_digest,
        tuple(cast(list[dict[str, object]], request.selected_evidence)),
        tuple(cast(list[dict[str, object]], request.rejected_evidence)),
        cast(dict[str, int], request.budgets),
        cast(dict[str, object], request.trace_payload),
        request.compilation_watermark,
        request.input_digest,
        request.expires_at,
    )
    return command, snapshot


def _validate(request: DemoContextCompileRequest, binding: DemoJobBinding, job: Job) -> bool:
    expected_request = {
        key: _canon(value)
        for key, value in _request_fields(
            CreateDemoContextCompilation(
                request.demo_actor_id,
                request.demo_session_id,
                request.aesthetic_profile_id,
                request.current_instruction_digest,
                request.context_as_of_time,
                "ignored-key",
                "ignored-request",
                request.compiler_version,
            ),
            binding.id,
            _command_and_snapshot(request)[1],
        ).items()
    }
    expected_binding = _binding_fields(
        request.demo_actor_id,
        request.demo_session_id,
        job.id,
        binding.idempotency_key_hash,
        binding.request_digest,
    )
    if (
        request.schema_version != DEMO_CONTEXT_REQUEST_SCHEMA
        or request.canonical_payload != expected_request
        or request.content_digest != _digest(DEMO_CONTEXT_REQUEST_SCHEMA, expected_request)
        or binding.schema_version != DEMO_JOB_BINDING_SCHEMA
        or binding.canonical_payload != expected_binding
        or binding.content_digest != _digest(DEMO_JOB_BINDING_SCHEMA, expected_binding)
        or binding.target_id != request.demo_session_id
        or job.job_type != DEMO_CONTEXT_JOB_TYPE
        or job.idempotency_key_hash
        != _formal_key(request.demo_actor_id, binding.idempotency_key_hash)
        or job.payload != {}
        or job.owner_user_id is not None
        or job.ingestion_upload_intent_id is not None
        or job.result_asset_id is not None
    ):
        raise DemoContextQueueAuthorityCorruption(
            "EXECUTION_ENVELOPE_INVALID", "Context execution envelope invalid"
        )
    return True


def _finish(
    job: Job,
    attempt: JobAttempt,
    status: Literal["COMPLETED", "REJECTED", "FAILED"],
    code: str,
    error: str | None,
    now: datetime,
) -> None:
    if job.status != "RUNNING" or attempt.status != "RUNNING":
        raise DemoContextQueueAuthorityCorruption(
            "TERMINAL_TRANSITION_INVALID", "Context Job cannot finish"
        )
    attempt.status, attempt.result_code, attempt.error_code, attempt.finished_at = (
        status,
        (code if status != "FAILED" else None),
        error,
        now,
    )
    (
        job.status,
        job.lease_token,
        job.lease_acquired_at,
        job.lease_expires_at,
        job.finalized_at,
        job.result_code,
        job.updated_at,
    ) = status, None, None, None, now, code, now


def _exhaust(job: Job, now: datetime) -> None:
    if job.status != "RUNNING":
        raise DemoContextQueueAuthorityCorruption(
            "TERMINAL_TRANSITION_INVALID",
            "Context Job cannot exhaust attempts from its current state",
        )
    (
        job.status,
        job.lease_token,
        job.lease_acquired_at,
        job.lease_expires_at,
        job.finalized_at,
        job.result_code,
        job.updated_at,
    ) = "FAILED", None, None, None, now, "CONTEXT_MAX_ATTEMPTS", now


def _authority_row(
    model: type[Any],
    *,
    row_id: str | None,
    schema_version: str,
    created_at: datetime,
    fields: Mapping[str, Any],
) -> Any:
    row = model(
        id=row_id or new_id(),
        schema_version=schema_version,
        canonical_payload={},
        content_digest="0" * 64,
        created_at=created_at,
        **dict(fields),
    )
    payload = {
        column.name: _canon(getattr(row, column.name))
        for column in row.__table__.columns
        if column.name not in _NON_AUTHORITY
    }
    row.canonical_payload, row.content_digest = payload, _digest(schema_version, payload)
    return row


def _canon(value: Any) -> Any:
    return _time(value) if isinstance(value, datetime) else value


def _time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _digest(schema: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(schema.encode() + b"\n" + canonical_json_bytes(payload)).hexdigest()


def _formal_key(actor: str, key: str) -> str:
    return hashlib.sha256(
        f"mirror.demo/JobIdempotency/v1\n{actor}\n{DEMO_CONTEXT_COMPILE_OPERATION}\n{key}".encode()
    ).hexdigest()


def _ids(*values: str) -> None:
    if any(type(value) is not str or _ID.fullmatch(value) is None for value in values):
        raise DemoContextQueueInputError("INVALID_ID", "identifiers must be opaque lowercase IDs")


__all__ = [
    "CreateDemoContextCompilation",
    "DemoContextCompilationAccepted",
    "DemoContextExecutionResult",
    "DemoContextQueueAuthorityCorruption",
    "DemoContextQueueConflict",
    "DemoContextQueueInputError",
    "DemoContextQueueService",
    "DemoContextQueueUnavailable",
    "DemoContextReconciliationCandidate",
    "DemoContextReservation",
]
