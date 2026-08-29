"""PostgreSQL-authoritative commands around the accepted P5 compiler.

The pure/compiler materialization service intentionally starts from an existing
Demo Job.  This module owns the public command side: idempotent Job creation,
explicit style/constraint evidence, and the deterministic active-profile read.
It contains no Celery or Provider dependency.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_idempotency import (
    DemoIdempotencyPayloadConflict,
    DemoIdempotencyTarget,
    DemoSemanticIdempotencyCoordinator,
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DemoActor,
    DemoCommandBinding,
    DemoDesiredDeltaProfile,
    DemoIdentityConstraints,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoProfileCompilationBundle,
    DemoSession,
)
from mirror_api.demo_preference_ledger import (
    AppendDemoPreferenceEvent,
    DemoPreferenceEventType,
    DemoPreferenceSourceType,
    append_demo_preference_event,
    preference_event_content_digest,
)
from mirror_api.demo_profile_service import (
    DEMO_PROFILE_COMPILE_JOB_TYPE,
    DEMO_PROFILE_COMPILE_OPERATION,
)
from mirror_api.models import Job, new_id, utcnow

DEMO_PROFILE_COMPILER_VERSION = "demo-profile-compiler-v1"
DEMO_JOB_BINDING_SCHEMA = "mirror.demo/DemoJobBinding/v1"
DEMO_CONSTRAINTS_SCHEMA = "mirror.demo/DemoIdentityConstraints/v1"
DEMO_STYLE_FEEDBACK_OPERATION = "style_feedback.create"
DEMO_CONSTRAINT_CREATE_OPERATION = "constraint.create"

_ID = re.compile(r"^[0-9a-f]{32}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REQUEST_ID = re.compile(r"^[^\r\n\x00]{8,128}$")
_TERMINAL = frozenset({"COMPLETED", "REJECTED", "FAILED", "CANCELLED"})
_LEARNING_TOGGLES = frozenset({"LEARNING_DISABLED", "LEARNING_ENABLED"})
_OPERATIONS = frozenset(
    {
        "CROP",
        "ROTATE",
        "EXPOSURE",
        "CONTRAST",
        "SATURATION",
        "TEMPERATURE",
        "GEOMETRY",
        "MAKEUP",
        "GENERATIVE",
    }
)


class DemoProfileCommandError(RuntimeError):
    """Base error for the public P5 command boundary."""


class DemoProfileCommandInputError(DemoProfileCommandError):
    """A public command violates the frozen Demo contract."""


class DemoProfileCommandUnavailable(DemoProfileCommandError):
    """The requested actor/session/profile authority is unavailable."""


class DemoProfileCommandAuthorityCorruption(DemoProfileCommandError):
    """Persisted command or profile authority cannot be safely replayed."""


@dataclass(frozen=True)
class CreateDemoProfileCompilation:
    demo_actor_id: str
    demo_session_id: str
    compiler_version: str
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.demo_session_id, "demo_session_id")
        if self.compiler_version != DEMO_PROFILE_COMPILER_VERSION:
            raise DemoProfileCommandInputError("compiler_version is not supported")
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class DemoProfileCompileAccepted:
    job_id: str
    request_id: str
    replayed: bool


@dataclass(frozen=True)
class DemoProfileReconciliationCandidate:
    demo_actor_id: str
    job_id: str
    request_id: str


@dataclass(frozen=True)
class DemoActiveProfile:
    profile_id: str
    generation: int
    compilation_watermark: str
    learning_enabled: bool


@dataclass(frozen=True)
class CreateDemoStyleFeedback:
    demo_actor_id: str
    demo_session_id: str | None
    event_type: Literal["EXPLICIT_STYLE_SELECTION", "MAXIMUM_INTENSITY_CHANGED"]
    idempotency_key: str
    style_key: str | None = None
    target_key: str | None = None
    maximum_intensity_ppm: int | None = None

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        if self.demo_session_id is not None:
            _require_id(self.demo_session_id, "demo_session_id")
        idempotency_key_hash(self.idempotency_key)
        if self.event_type == "EXPLICIT_STYLE_SELECTION":
            _require_key(self.style_key, "style_key")
            if self.target_key is not None or self.maximum_intensity_ppm is not None:
                raise DemoProfileCommandInputError("style selection payload is ambiguous")
        elif self.event_type == "MAXIMUM_INTENSITY_CHANGED":
            _require_key(self.target_key, "target_key")
            if self.style_key is not None:
                raise DemoProfileCommandInputError("maximum intensity payload is ambiguous")
            if (
                type(self.maximum_intensity_ppm) is not int
                or not 0 <= self.maximum_intensity_ppm <= 1_000_000
            ):
                raise DemoProfileCommandInputError("maximum_intensity_ppm must be in [0, 1000000]")
        else:  # pragma: no cover - Literal plus public Pydantic discriminator.
            raise DemoProfileCommandInputError("style event type is unsupported")


@dataclass(frozen=True)
class DemoStyleFeedbackResult:
    event_id: str
    event_type: Literal["EXPLICIT_STYLE_SELECTION", "MAXIMUM_INTENSITY_CHANGED"]
    event_digest: str
    replayed: bool


@dataclass(frozen=True)
class DemoConstraintLockCommand:
    dimension_key: str
    lock: Literal["PRESERVE", "UNLOCK"]
    minimum_ppm: int | None = None
    maximum_ppm: int | None = None

    def validate(self) -> None:
        _require_key(self.dimension_key, "dimension_key", maximum=48)
        if self.lock not in {"PRESERVE", "UNLOCK"}:
            raise DemoProfileCommandInputError("constraint lock action is unsupported")
        for name, value in (
            ("minimum_ppm", self.minimum_ppm),
            ("maximum_ppm", self.maximum_ppm),
        ):
            if value is not None and (
                type(value) is not int or not -1_000_000 <= value <= 1_000_000
            ):
                raise DemoProfileCommandInputError(f"{name} is outside the ppm boundary")
        if (
            self.minimum_ppm is not None
            and self.maximum_ppm is not None
            and self.minimum_ppm > self.maximum_ppm
        ):
            raise DemoProfileCommandInputError("minimum_ppm must not exceed maximum_ppm")
        if self.lock == "UNLOCK" and (self.minimum_ppm is not None or self.maximum_ppm is not None):
            raise DemoProfileCommandInputError("UNLOCK cannot carry geometric bounds")


@dataclass(frozen=True)
class CreateDemoConstraints:
    demo_actor_id: str
    demo_session_id: str | None
    scope: Literal["PERSISTENT", "SESSION_OVERRIDE"]
    locks: tuple[DemoConstraintLockCommand, ...]
    prohibited_operations: tuple[str, ...]
    idempotency_key: str

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        if self.scope == "PERSISTENT":
            if self.demo_session_id is not None:
                raise DemoProfileCommandInputError(
                    "PERSISTENT constraints must not bind a Demo Session"
                )
        elif self.scope == "SESSION_OVERRIDE":
            if self.demo_session_id is None:
                raise DemoProfileCommandInputError(
                    "SESSION_OVERRIDE constraints require a Demo Session"
                )
            _require_id(self.demo_session_id, "demo_session_id")
        else:  # pragma: no cover - Literal plus public Pydantic validation.
            raise DemoProfileCommandInputError("constraint scope is unsupported")
        if not 1 <= len(self.locks) <= 64:
            raise DemoProfileCommandInputError("constraints require between 1 and 64 locks")
        dimensions: set[str] = set()
        for item in self.locks:
            item.validate()
            if item.dimension_key in dimensions:
                raise DemoProfileCommandInputError("constraint dimensions must be unique")
            dimensions.add(item.dimension_key)
        if len(set(self.prohibited_operations)) != len(self.prohibited_operations):
            raise DemoProfileCommandInputError("prohibited operations must be unique")
        if any(item not in _OPERATIONS for item in self.prohibited_operations):
            raise DemoProfileCommandInputError("prohibited operation is unsupported")
        idempotency_key_hash(self.idempotency_key)


@dataclass(frozen=True)
class DemoConstraintsResult:
    constraints_id: str
    version: int
    scope: Literal["PERSISTENT", "SESSION_OVERRIDE"]
    replayed: bool


class DemoProfileCommandService:
    """Create/replay P5 commands and read the actor's active compiled projection."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._idempotency = DemoSemanticIdempotencyCoordinator(session_factory=session_factory)
        self._now = now

    async def create_compilation(
        self, command: CreateDemoProfileCompilation
    ) -> DemoProfileCompileAccepted:
        command.validate()
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {
                "compiler_version": command.compiler_version,
                "session_id": command.demo_session_id,
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
                    return await self._replay_compilation(
                        session, existing, request_digest=request_digest
                    )

                await self._lock_active_actor(session, command.demo_actor_id)
                await self._lock_active_session(
                    session,
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                )
                job_id = new_id()
                binding_id = new_id()
                now = self._normalized_now()
                job = Job(
                    id=job_id,
                    job_type=DEMO_PROFILE_COMPILE_JOB_TYPE,
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
                        session.add(binding)
                        await session.flush()
                except IntegrityError as exc:
                    winner = await self._binding_for_key(
                        session,
                        demo_actor_id=command.demo_actor_id,
                        key_hash=key_hash,
                    )
                    if winner is None:
                        raise DemoProfileCommandAuthorityCorruption(
                            "profile creation failed without a reloadable winner"
                        ) from exc
                    return await self._replay_compilation(
                        session, winner, request_digest=request_digest
                    )
                return DemoProfileCompileAccepted(
                    job_id=job_id,
                    request_id=command.request_id,
                    replayed=False,
                )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoProfileReconciliationCandidate, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise DemoProfileCommandInputError("reconciliation limit is invalid")
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(DemoJobBinding, Job)
                    .join(Job, Job.id == DemoJobBinding.job_id)
                    .where(
                        DemoJobBinding.endpoint_operation == DEMO_PROFILE_COMPILE_OPERATION,
                        DemoJobBinding.target_type == "DEMO_ACTOR",
                        Job.job_type == DEMO_PROFILE_COMPILE_JOB_TYPE,
                        Job.status == "PENDING",
                        Job.attempt_count == 0,
                    )
                    .order_by(Job.created_at, Job.id)
                    .limit(limit)
                )
            ).all()
            candidates: list[DemoProfileReconciliationCandidate] = []
            for binding, job in rows:
                _validate_profile_job(binding, job)
                candidates.append(
                    DemoProfileReconciliationCandidate(
                        demo_actor_id=binding.demo_actor_id,
                        job_id=job.id,
                        request_id=job.request_id,
                    )
                )
            return tuple(candidates)

    async def active_profiles(self, *, demo_actor_id: str) -> tuple[DemoActiveProfile, ...]:
        _require_id(demo_actor_id, "demo_actor_id")
        async with self._sessions() as session:
            await self._require_active_actor(session, demo_actor_id)
            row = (
                await session.execute(
                    select(DemoProfileCompilationBundle, DemoDesiredDeltaProfile)
                    .join(
                        DemoDesiredDeltaProfile,
                        DemoDesiredDeltaProfile.id
                        == DemoProfileCompilationBundle.desired_delta_profile_id,
                    )
                    .where(DemoProfileCompilationBundle.demo_actor_id == demo_actor_id)
                    .order_by(
                        DemoDesiredDeltaProfile.version.desc(),
                        DemoProfileCompilationBundle.id.desc(),
                    )
                    .limit(1)
                )
            ).one_or_none()
            if row is None:
                return ()
            bundle, desired = row
            if (
                bundle.demo_actor_id != demo_actor_id
                or desired.demo_actor_id != demo_actor_id
                or bundle.compilation_watermark != desired.compilation_watermark
                or bundle.compiler_version != DEMO_PROFILE_COMPILER_VERSION
            ):
                raise DemoProfileCommandAuthorityCorruption(
                    "active profile projection is inconsistent"
                )
            latest_toggle = await session.scalar(
                select(DemoPreferenceEvent.event_type)
                .where(
                    DemoPreferenceEvent.demo_actor_id == demo_actor_id,
                    DemoPreferenceEvent.event_type.in_(_LEARNING_TOGGLES),
                )
                .order_by(DemoPreferenceEvent.event_sequence.desc())
                .limit(1)
            )
            return (
                DemoActiveProfile(
                    profile_id=bundle.id,
                    generation=desired.version,
                    compilation_watermark=bundle.compilation_watermark,
                    learning_enabled=latest_toggle != "LEARNING_DISABLED",
                ),
            )

    async def create_style_feedback(
        self, command: CreateDemoStyleFeedback
    ) -> DemoStyleFeedbackResult:
        command.validate()
        semantic_request = _style_semantic_request(command)

        async def create_target(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoPreferenceEvent]:
            event_type, signal = _style_event(command)
            result = await append_demo_preference_event(
                session,
                AppendDemoPreferenceEvent(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                    event_type=event_type,
                    source_type=DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                    target_type=None,
                    target_id=None,
                    signal=signal,
                    occurred_at=self._normalized_now(),
                ),
            )
            return DemoIdempotencyTarget(
                value=result.event,
                response_id=result.event.id,
                demo_session_id=result.event.demo_session_id,
            )

        async def load_target(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[DemoPreferenceEvent] | None:
            event = await session.get(DemoPreferenceEvent, binding.response_id)
            if event is None:
                return None
            _validate_style_event(event, command)
            return DemoIdempotencyTarget(
                value=event,
                response_id=event.id,
                demo_session_id=event.demo_session_id,
            )

        result = await self._idempotency.execute(
            demo_actor_id=command.demo_actor_id,
            endpoint_operation=DEMO_STYLE_FEEDBACK_OPERATION,
            idempotency_key=command.idempotency_key,
            semantic_request=semantic_request,
            create_target=create_target,
            load_target=load_target,
        )
        event_type = cast(
            Literal["EXPLICIT_STYLE_SELECTION", "MAXIMUM_INTENSITY_CHANGED"],
            result.value.event_type,
        )
        return DemoStyleFeedbackResult(
            event_id=result.value.id,
            event_type=event_type,
            event_digest=result.value.content_digest,
            replayed=result.replayed,
        )

    async def create_constraints(self, command: CreateDemoConstraints) -> DemoConstraintsResult:
        command.validate()
        ordered_locks = tuple(sorted(command.locks, key=lambda item: item.dimension_key))
        ordered_operations = tuple(sorted(command.prohibited_operations))
        semantic_request = _constraint_semantic_request(
            command,
            locks=ordered_locks,
            prohibited_operations=ordered_operations,
        )

        async def create_target(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoIdentityConstraints]:
            await self._lock_active_actor(session, command.demo_actor_id)
            if command.demo_session_id is not None:
                await self._lock_active_session(
                    session,
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                )
            now = self._normalized_now()
            source_digests: list[str] = []
            for item in ordered_locks:
                event_type, signal = _constraint_lock_event(command, item)
                result = await append_demo_preference_event(
                    session,
                    AppendDemoPreferenceEvent(
                        demo_actor_id=command.demo_actor_id,
                        demo_session_id=command.demo_session_id,
                        event_type=event_type,
                        source_type=DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                        target_type=None,
                        target_id=None,
                        signal=signal,
                        occurred_at=now,
                    ),
                )
                source_digests.append(result.event.content_digest)
            for operation in ordered_operations:
                result = await append_demo_preference_event(
                    session,
                    AppendDemoPreferenceEvent(
                        demo_actor_id=command.demo_actor_id,
                        demo_session_id=command.demo_session_id,
                        event_type=DemoPreferenceEventType.PROHIBITED_OPERATION_ADDED,
                        source_type=DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                        target_type=None,
                        target_id=None,
                        signal={
                            "constraint_scope": command.scope,
                            "operation": operation,
                        },
                        occurred_at=now,
                    ),
                )
                source_digests.append(result.event.content_digest)
            version_value = await session.scalar(
                select(func.coalesce(func.max(DemoIdentityConstraints.version), 0)).where(
                    DemoIdentityConstraints.demo_actor_id == command.demo_actor_id
                )
            )
            if type(version_value) is not int:
                raise DemoProfileCommandAuthorityCorruption(
                    "constraint version authority is invalid"
                )
            payload = _constraint_payload(
                command,
                locks=ordered_locks,
                prohibited_operations=ordered_operations,
                source_event_digests=tuple(source_digests),
                version=version_value + 1,
            )
            constraints = DemoIdentityConstraints(
                id=new_id(),
                schema_version=DEMO_CONSTRAINTS_SCHEMA,
                canonical_payload=payload,
                content_digest=_authority_digest(DEMO_CONSTRAINTS_SCHEMA, payload),
                created_at=now,
                **payload,
            )
            session.add(constraints)
            await session.flush()
            return DemoIdempotencyTarget(
                value=constraints,
                response_id=constraints.id,
                demo_session_id=constraints.demo_session_id,
            )

        async def load_target(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[DemoIdentityConstraints] | None:
            constraints = await session.get(DemoIdentityConstraints, binding.response_id)
            if constraints is None:
                return None
            if (
                constraints.demo_actor_id != command.demo_actor_id
                or constraints.demo_session_id != command.demo_session_id
                or constraints.constraint_scope != command.scope
                or constraints.content_digest
                != _authority_digest(DEMO_CONSTRAINTS_SCHEMA, constraints.canonical_payload)
            ):
                raise DemoProfileCommandAuthorityCorruption(
                    "constraint command winner is inconsistent"
                )
            return DemoIdempotencyTarget(
                value=constraints,
                response_id=constraints.id,
                demo_session_id=constraints.demo_session_id,
            )

        result = await self._idempotency.execute(
            demo_actor_id=command.demo_actor_id,
            endpoint_operation=DEMO_CONSTRAINT_CREATE_OPERATION,
            idempotency_key=command.idempotency_key,
            semantic_request=semantic_request,
            create_target=create_target,
            load_target=load_target,
        )
        return DemoConstraintsResult(
            constraints_id=result.value.id,
            version=result.value.version,
            scope=cast(
                Literal["PERSISTENT", "SESSION_OVERRIDE"],
                result.value.constraint_scope,
            ),
            replayed=result.replayed,
        )

    async def _binding_for_key(
        self, session: AsyncSession, *, demo_actor_id: str, key_hash: str
    ) -> DemoJobBinding | None:
        return cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.demo_actor_id == demo_actor_id,
                    DemoJobBinding.endpoint_operation == DEMO_PROFILE_COMPILE_OPERATION,
                    DemoJobBinding.idempotency_key_hash == key_hash,
                )
            ),
        )

    async def _replay_compilation(
        self,
        session: AsyncSession,
        binding: DemoJobBinding,
        *,
        request_digest: str,
    ) -> DemoProfileCompileAccepted:
        if binding.request_digest != request_digest:
            raise DemoIdempotencyPayloadConflict()
        job = await session.get(Job, binding.job_id)
        if job is None:
            raise DemoProfileCommandAuthorityCorruption("profile command winner Job is missing")
        _validate_profile_job(binding, job)
        return DemoProfileCompileAccepted(
            job_id=job.id,
            request_id=job.request_id,
            replayed=True,
        )

    async def _lock_active_actor(self, session: AsyncSession, demo_actor_id: str) -> DemoActor:
        actor = cast(
            DemoActor | None,
            await session.scalar(
                select(DemoActor).where(DemoActor.id == demo_actor_id).with_for_update()
            ),
        )
        if actor is None or actor.tombstoned_at is not None:
            raise DemoProfileCommandUnavailable("Demo actor is unavailable")
        return actor

    async def _require_active_actor(self, session: AsyncSession, demo_actor_id: str) -> DemoActor:
        actor = await session.get(DemoActor, demo_actor_id)
        if actor is None or actor.tombstoned_at is not None:
            raise DemoProfileCommandUnavailable("Demo actor is unavailable")
        return actor

    async def _lock_active_session(
        self,
        session: AsyncSession,
        *,
        demo_actor_id: str,
        demo_session_id: str,
    ) -> DemoSession:
        demo_session = cast(
            DemoSession | None,
            await session.scalar(
                select(DemoSession)
                .where(
                    DemoSession.id == demo_session_id,
                    DemoSession.demo_actor_id == demo_actor_id,
                )
                .with_for_update()
            ),
        )
        if (
            demo_session is None
            or demo_session.closed_at is not None
            or demo_session.tombstoned_at is not None
            or demo_session.expires_at <= self._normalized_now()
        ):
            raise DemoProfileCommandUnavailable("Demo Session is unavailable")
        return demo_session

    def _normalized_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise DemoProfileCommandAuthorityCorruption(
                "profile command clock must be timezone-aware"
            )
        return value.astimezone(UTC)


def _validate_profile_job(binding: DemoJobBinding, job: Job) -> None:
    payload = _job_binding_payload(
        demo_actor_id=binding.demo_actor_id,
        demo_session_id=cast(str, binding.demo_session_id),
        job_id=binding.job_id,
        idempotency_key_hash_value=binding.idempotency_key_hash,
        request_digest=binding.request_digest,
    )
    if (
        binding.demo_session_id is None
        or binding.endpoint_operation != DEMO_PROFILE_COMPILE_OPERATION
        or binding.target_type != "DEMO_ACTOR"
        or binding.target_id != binding.demo_actor_id
        or binding.schema_version != DEMO_JOB_BINDING_SCHEMA
        or binding.canonical_payload != payload
        or binding.content_digest != _authority_digest(DEMO_JOB_BINDING_SCHEMA, payload)
        or job.id != binding.job_id
        or job.job_type != DEMO_PROFILE_COMPILE_JOB_TYPE
        or job.owner_user_id is not None
        or job.ingestion_upload_intent_id is not None
        or job.result_asset_id is not None
        or job.payload != {}
        or job.status not in {"PENDING", "RUNNING", *_TERMINAL}
    ):
        raise DemoProfileCommandAuthorityCorruption("profile command winner envelope is invalid")


def _job_binding_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    job_id: str,
    idempotency_key_hash_value: str,
    request_digest: str,
) -> dict[str, Any]:
    return {
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "endpoint_operation": DEMO_PROFILE_COMPILE_OPERATION,
        "idempotency_key_hash": idempotency_key_hash_value,
        "job_id": job_id,
        "request_digest": request_digest,
        "target_id": demo_actor_id,
        "target_type": "DEMO_ACTOR",
    }


def _style_semantic_request(command: CreateDemoStyleFeedback) -> dict[str, Any]:
    if command.event_type == "EXPLICIT_STYLE_SELECTION":
        return {
            "event_type": command.event_type,
            "session_id": command.demo_session_id,
            "style_key": command.style_key,
        }
    return {
        "event_type": command.event_type,
        "maximum_intensity_ppm": command.maximum_intensity_ppm,
        "session_id": command.demo_session_id,
        "target_key": command.target_key,
    }


def _style_event(
    command: CreateDemoStyleFeedback,
) -> tuple[DemoPreferenceEventType, dict[str, Any]]:
    if command.event_type == "EXPLICIT_STYLE_SELECTION":
        assert command.style_key is not None
        return DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION, {"style_key": command.style_key}
    assert command.target_key is not None
    assert command.maximum_intensity_ppm is not None
    return DemoPreferenceEventType.MAXIMUM_INTENSITY_CHANGED, {
        "constraint_scope": "PERSISTENT",
        "maximum_intensity_ppm": command.maximum_intensity_ppm,
        "target_key": command.target_key,
    }


def _validate_style_event(event: DemoPreferenceEvent, command: CreateDemoStyleFeedback) -> None:
    _, signal = _style_event(command)
    if (
        event.demo_actor_id != command.demo_actor_id
        or event.demo_session_id != command.demo_session_id
        or event.event_type != command.event_type
        or event.source_type != DemoPreferenceSourceType.EXPLICIT_USER_ACTION.value
        or event.target_type is not None
        or event.target_id is not None
        or event.signal != signal
        or event.content_digest != preference_event_content_digest(event.canonical_payload)
    ):
        raise DemoProfileCommandAuthorityCorruption("style command winner event is inconsistent")


def _constraint_semantic_request(
    command: CreateDemoConstraints,
    *,
    locks: Sequence[DemoConstraintLockCommand],
    prohibited_operations: Sequence[str],
) -> dict[str, Any]:
    return {
        "locks": [
            {
                "dimension_key": item.dimension_key,
                "lock": item.lock,
                "maximum_ppm": item.maximum_ppm,
                "minimum_ppm": item.minimum_ppm,
            }
            for item in locks
        ],
        "prohibited_operations": list(prohibited_operations),
        "scope": command.scope,
        "session_id": command.demo_session_id,
    }


def _constraint_lock_event(
    command: CreateDemoConstraints, item: DemoConstraintLockCommand
) -> tuple[DemoPreferenceEventType, dict[str, Any]]:
    signal: dict[str, Any] = {"dimension_key": item.dimension_key}
    if item.minimum_ppm is not None:
        signal["minimum_ppm"] = item.minimum_ppm
    if item.maximum_ppm is not None:
        signal["maximum_ppm"] = item.maximum_ppm
    if command.scope == "SESSION_OVERRIDE" and item.lock == "UNLOCK":
        return DemoPreferenceEventType.TEMPORARY_SESSION_OVERRIDE, signal
    signal["constraint_scope"] = command.scope
    return (
        DemoPreferenceEventType.FEATURE_LOCKED
        if item.lock == "PRESERVE"
        else DemoPreferenceEventType.FEATURE_UNLOCKED,
        signal,
    )


def _constraint_payload(
    command: CreateDemoConstraints,
    *,
    locks: Sequence[DemoConstraintLockCommand],
    prohibited_operations: Sequence[str],
    source_event_digests: Sequence[str],
    version: int,
) -> dict[str, Any]:
    lock_payload: dict[str, dict[str, Any]] = {}
    bounds_payload: dict[str, dict[str, int]] = {}
    for item in locks:
        mode = (
            "ALLOW_CHANGE"
            if command.scope == "SESSION_OVERRIDE" and item.lock == "UNLOCK"
            else item.lock
        )
        lock_payload[item.dimension_key] = {"mode": mode}
        bounds: dict[str, int] = {}
        if item.minimum_ppm is not None:
            bounds["minimum_ppm"] = item.minimum_ppm
        if item.maximum_ppm is not None:
            bounds["maximum_ppm"] = item.maximum_ppm
        if bounds:
            bounds_payload[item.dimension_key] = bounds
    return {
        "bounds": bounds_payload,
        "constraint_scope": command.scope,
        "demo_actor_id": command.demo_actor_id,
        "demo_session_id": command.demo_session_id,
        "locks": lock_payload,
        "prohibited_operations": list(prohibited_operations),
        "self_state_id": None,
        "source_event_digests": list(source_event_digests),
        "version": version,
    }


def _formal_job_key_hash(demo_actor_id: str, client_key_hash: str) -> str:
    preimage = (
        f"mirror.demo/JobIdempotency/v1\n{demo_actor_id}\n"
        f"{DEMO_PROFILE_COMPILE_OPERATION}\n{client_key_hash}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _authority_digest(schema_version: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoProfileCommandInputError(f"{name} must be a lowercase hexadecimal ID")


def _require_key(value: str | None, name: str, *, maximum: int = 64) -> None:
    if not isinstance(value, str) or len(value) > maximum or _KEY.fullmatch(value) is None:
        raise DemoProfileCommandInputError(f"{name} is invalid")


def _require_request_id(value: str) -> None:
    if not isinstance(value, str) or _REQUEST_ID.fullmatch(value) is None:
        raise DemoProfileCommandInputError("request_id is outside the safe boundary")


__all__ = [
    "DEMO_PROFILE_COMPILER_VERSION",
    "CreateDemoConstraints",
    "CreateDemoProfileCompilation",
    "CreateDemoStyleFeedback",
    "DemoActiveProfile",
    "DemoConstraintLockCommand",
    "DemoConstraintsResult",
    "DemoProfileCommandAuthorityCorruption",
    "DemoProfileCommandInputError",
    "DemoProfileCommandService",
    "DemoProfileCommandUnavailable",
    "DemoProfileCompileAccepted",
    "DemoProfileReconciliationCandidate",
    "DemoStyleFeedbackResult",
]
