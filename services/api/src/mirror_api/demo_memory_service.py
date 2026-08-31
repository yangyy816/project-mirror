"""Deterministic P7 Profile rebuild, Context compilation and recall.

This module is an internal application boundary.  It consumes the accepted
D05/D06/D09 authorities and writes only the existing Demo P7 derived tables.
It deliberately has no router, Celery, Provider, D02 runtime or wall-clock
context dependency.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal, cast

from sqlalchemy import func, select, text
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
    DemoAestheticProfile,
    DemoContextCompilation,
    DemoDesiredDeltaProfile,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoReferenceProfile,
    DemoSession,
    DemoStyleProfile,
)
from mirror_api.demo_preference_ledger import (
    GENESIS_EVENT_DIGEST,
    DemoPreferenceLedgerCorruption,
    verify_demo_preference_event_chain,
)
from mirror_api.models import Job, JobAttempt, new_id, utcnow

DEMO_AESTHETIC_PROFILE_SCHEMA: Final = "mirror.demo/DemoAestheticProfile/v1"
DEMO_CONTEXT_COMPILATION_SCHEMA: Final = "mirror.demo/DemoContextCompilation/v1"
DEMO_JOB_BINDING_SCHEMA: Final = "mirror.demo/DemoJobBinding/v1"
DEMO_MEMORY_PROFILE_COMPILER_VERSION: Final = "demo-memory-profile-compiler-v1"
DEMO_CONTEXT_COMPILER_VERSION: Final = "demo-context-compiler-v1"
DEMO_PROFILE_REBUILD_OPERATION: Final = "profile.rebuild"
DEMO_CONTEXT_COMPILE_OPERATION: Final = "context.compile"
DEMO_PROFILE_REBUILD_JOB_TYPE: Final = "demo_p3_p7.profile.rebuild"
DEMO_CONTEXT_COMPILE_JOB_TYPE: Final = "demo_p3_p7.context.compile"

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REQUEST_ID = re.compile(r"^[^\r\n\x00]{8,128}$")
_PROFILE_REASONS: Final = frozenset({"USER_REQUEST", "RESET", "ROLLBACK", "TOMBSTONE_PROPAGATION"})
_CONTEXT_TTL: Final = timedelta(minutes=30)
_NON_EVENT_SEQUENCE: Final = 0
_CONTEXT_BUDGETS: Final[dict[str, int]] = {
    "accepted_visual_episodes": 4,
    "current_session_events": 8,
    "persistent_control_events": 8,
    "profile_core": 1,
    "total_selected_evidence": 21,
}
_PERSISTENT_EVENT_TYPES: Final = frozenset(
    {
        "EXPLICIT_STYLE_SELECTION",
        "FEATURE_LOCKED",
        "FEATURE_UNLOCKED",
        "LEARNING_DISABLED",
        "LEARNING_ENABLED",
        "MAXIMUM_INTENSITY_CHANGED",
        "PROHIBITED_OPERATION_ADDED",
        "RESET",
        "ROLLBACK",
        "TOMBSTONE",
        "DELETE",
    }
)
_CURRENT_SESSION_EVENT_TYPES: Final = frozenset(
    {"TEMPORARY_SESSION_OVERRIDE", "IMAGE_REJECTED", "IMAGE_ADJUSTED"}
)
_PROFILE_CONTROL_EVENT_TYPES: Final = _PERSISTENT_EVENT_TYPES
_INVALIDATION_EVENT_TYPES: Final = frozenset({"TOMBSTONE", "DELETE"})


class DemoMemoryError(RuntimeError):
    """Base D10 application failure."""


class DemoMemoryInputError(DemoMemoryError):
    """A D10 command violates the frozen internal contract."""


class DemoMemoryUnavailable(DemoMemoryError):
    """Required actor, session, source Profile or Context is unavailable."""


class DemoMemoryConflict(DemoMemoryError):
    """An idempotency key or immutable compilation input already has authority."""


class DemoMemoryRejected(DemoMemoryConflict):
    """A claimed rebuild is ineligible for materialization and was rejected."""


class DemoMemoryAuthorityCorruption(DemoMemoryError):
    """Persisted P5/P6/P7 authority cannot be safely replayed."""


@dataclass(frozen=True)
class DemoProfileRebuildAccepted:
    """Durable admission result for a queued Profile rebuild."""

    job_id: str
    request_id: str
    replayed: bool


@dataclass(frozen=True)
class DemoMemoryReconciliationCandidate:
    """A recoverable PENDING Profile rebuild that may be dispatched again."""

    demo_actor_id: str
    job_id: str
    request_id: str


@dataclass(frozen=True)
class RebuildDemoAestheticProfile:
    demo_actor_id: str
    reason: Literal["USER_REQUEST", "RESET", "ROLLBACK", "TOMBSTONE_PROPAGATION"]
    idempotency_key: str
    request_id: str
    compiler_version: str = DEMO_MEMORY_PROFILE_COMPILER_VERSION

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        if self.reason not in _PROFILE_REASONS:
            raise DemoMemoryInputError("profile rebuild reason is unsupported")
        if self.compiler_version != DEMO_MEMORY_PROFILE_COMPILER_VERSION:
            raise DemoMemoryInputError("profile compiler version is unsupported")
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class CompileDemoContext:
    demo_actor_id: str
    demo_session_id: str
    aesthetic_profile_id: str
    current_instruction_digest: str
    context_as_of_time: datetime
    idempotency_key: str
    request_id: str
    compiler_version: str = DEMO_CONTEXT_COMPILER_VERSION

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.demo_session_id, "demo_session_id")
        _require_id(self.aesthetic_profile_id, "aesthetic_profile_id")
        _require_digest(self.current_instruction_digest, "current_instruction_digest")
        _normalize_explicit_time(self.context_as_of_time, "context_as_of_time")
        if self.compiler_version != DEMO_CONTEXT_COMPILER_VERSION:
            raise DemoMemoryInputError("context compiler version is unsupported")
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class DemoAestheticProfileResult:
    job_id: str
    aesthetic_profile_id: str
    generation: int
    compilation_watermark: str
    profile_digest: str
    replayed: bool


@dataclass(frozen=True)
class DemoContextCompilationResult:
    job_id: str
    context_compilation_id: str
    aesthetic_profile_id: str
    compilation_watermark: str
    context_digest: str
    expires_at: datetime
    replayed: bool


@dataclass(frozen=True)
class DemoContextInputSnapshot:
    """Frozen, byte-free D10 compiler input for a queued Context request.

    The snapshot deliberately contains only already-derived authority.  It is
    suitable for persistence in the D10 request table and must be compared
    exactly before a worker materializes a ContextCompilation.
    """

    aesthetic_profile_id: str
    profile_digest: str
    context_as_of_time: datetime
    compiler_version: str
    current_instruction_digest: str
    selected_evidence: tuple[dict[str, object], ...]
    rejected_evidence: tuple[dict[str, object], ...]
    budgets: dict[str, int]
    trace_payload: dict[str, object]
    compilation_watermark: str
    input_digest: str
    expires_at: datetime


@dataclass(frozen=True)
class DemoContextRecall:
    context_compilation_id: str
    aesthetic_profile_id: str
    context_digest: str
    expires_at: datetime


@dataclass(frozen=True)
class _LifecycleProjection:
    events: tuple[DemoPreferenceEvent, ...]
    active_events: tuple[DemoPreferenceEvent, ...]
    active_sequences: frozenset[int]
    active_event_digests: frozenset[str]
    all_event_digests: frozenset[str]
    learning_at_event: Mapping[str, bool]
    learning_enabled: bool
    invalidated_targets: frozenset[tuple[str, str]]
    reset_epoch: int
    tail_sequence: int
    tail_digest: str


@dataclass(frozen=True)
class _ProfileSources:
    desired: DemoDesiredDeltaProfile | None
    style: DemoStyleProfile | None
    constraints: DemoIdentityConstraints | None
    reference: DemoReferenceProfile | None
    reference_dependencies: _ReferenceDependencies | None
    episodes: tuple[tuple[DemoAcceptedVisualEpisode, DemoPreferenceEvent], ...]
    controls: tuple[DemoPreferenceEvent, ...]
    negative_feedback: tuple[DemoPreferenceEvent, ...]
    excluded_acceptance: tuple[DemoPreferenceEvent, ...]


@dataclass(frozen=True)
class _ReferenceDependencies:
    style_profile_id: str | None
    identity_constraints_id: str | None
    source_asset_ids: tuple[str, ...]
    source_image_version_ids: tuple[str, ...]
    source_image_version_digests: tuple[str, ...]
    dependency_event_digests: tuple[str, ...]


class DemoMemoryService:
    """Materialize deterministic P7 derived state through PostgreSQL authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
        post_write_probe: Callable[[Literal["PROFILE", "CONTEXT"]], None] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._now = now
        self._post_write_probe = post_write_probe

    async def admit_rebuild(
        self, command: RebuildDemoAestheticProfile
    ) -> DemoProfileRebuildAccepted:
        """Create or replay an immutable, recoverable PENDING rebuild intent."""
        command.validate()
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {"compiler_version": command.compiler_version, "reason": command.reason}
        )
        async with self._sessions() as session:
            async with session.begin():
                await _acquire_actor_lock(session, command.demo_actor_id)
                await _lock_active_actor(session, command.demo_actor_id)
                existing_binding = await _binding_for_key(
                    session,
                    actor_id=command.demo_actor_id,
                    operation=DEMO_PROFILE_REBUILD_OPERATION,
                    key_hash=key_hash,
                )
                if existing_binding is not None:
                    return await _replay_rebuild_admission(
                        session, existing_binding, request_digest=request_digest
                    )
                audit_now = self._normalized_audit_now()
                try:
                    job, _ = await _create_pending_execution(
                        session,
                        actor_id=command.demo_actor_id,
                        operation=DEMO_PROFILE_REBUILD_OPERATION,
                        target_type="DEMO_ACTOR",
                        target_id=command.demo_actor_id,
                        key_hash=key_hash,
                        request_digest=request_digest,
                        request_id=command.request_id,
                        audit_now=audit_now,
                    )
                except IntegrityError as exc:
                    winner = await _binding_for_key(
                        session,
                        actor_id=command.demo_actor_id,
                        operation=DEMO_PROFILE_REBUILD_OPERATION,
                        key_hash=key_hash,
                    )
                    if winner is None:
                        raise DemoMemoryAuthorityCorruption(
                            "rebuild admission failed without a reloadable winner"
                        ) from exc
                    return await _replay_rebuild_admission(
                        session, winner, request_digest=request_digest
                    )
                return DemoProfileRebuildAccepted(
                    job_id=job.id, request_id=job.request_id, replayed=False
                )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoMemoryReconciliationCandidate, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise DemoMemoryInputError("reconciliation limit is invalid")
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(DemoJobBinding, Job)
                    .join(Job, Job.id == DemoJobBinding.job_id)
                    .where(
                        DemoJobBinding.endpoint_operation == DEMO_PROFILE_REBUILD_OPERATION,
                        DemoJobBinding.target_type == "DEMO_ACTOR",
                        Job.job_type == DEMO_PROFILE_REBUILD_JOB_TYPE,
                        Job.status == "PENDING",
                        Job.attempt_count == 1,
                    )
                    .order_by(Job.created_at, Job.id)
                    .limit(limit)
                )
            ).all()
            candidates: list[DemoMemoryReconciliationCandidate] = []
            for binding, job in rows:
                _validate_pending_rebuild_execution(binding, job)
                initial_attempt = await session.scalar(
                    select(JobAttempt).where(
                        JobAttempt.job_id == job.id,
                        JobAttempt.attempt == 1,
                        JobAttempt.status == "PENDING",
                    )
                )
                if initial_attempt is None or initial_attempt.finished_at is not None:
                    raise DemoMemoryAuthorityCorruption(
                        "pending profile rebuild Job lacks its initial PENDING attempt"
                    )
                candidates.append(
                    DemoMemoryReconciliationCandidate(
                        demo_actor_id=binding.demo_actor_id,
                        job_id=job.id,
                        request_id=job.request_id,
                    )
                )
            return tuple(candidates)

    async def execute_rebuild(
        self, *, demo_actor_id: str, job_id: str
    ) -> DemoAestheticProfileResult:
        """Claim and execute exactly one owner-bound queued Profile rebuild."""
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(job_id, "job_id")
        terminal_error: DemoMemoryError | None = None
        result: DemoAestheticProfileResult | None = None
        async with self._sessions() as session:
            async with session.begin():
                await _acquire_actor_lock(session, demo_actor_id)
                job, binding = await _lock_rebuild_execution(session, demo_actor_id, job_id)
                if job.status == "COMPLETED":
                    return await _replay_profile(
                        session, binding, request_digest=binding.request_digest
                    )
                if job.status != "PENDING" or job.attempt_count != 1:
                    raise DemoMemoryUnavailable(
                        "profile rebuild Job is not a fresh durable execution"
                    )
                _validate_pending_rebuild_execution(binding, job)
                audit_now = self._normalized_audit_now()
                attempt = cast(
                    JobAttempt | None,
                    await session.scalar(
                        select(JobAttempt)
                        .where(JobAttempt.job_id == job.id, JobAttempt.attempt == 1)
                        .with_for_update()
                    ),
                )
                if (
                    attempt is None
                    or attempt.status != "PENDING"
                    or attempt.finished_at is not None
                ):
                    raise DemoMemoryAuthorityCorruption(
                        "fresh profile rebuild Job lacks its initial PENDING attempt"
                    )
                attempt.status = "RUNNING"
                attempt.started_at = audit_now
                job.status = "RUNNING"
                job.updated_at = audit_now
                await session.flush()
                try:
                    result = await self._materialize_rebuild(
                        session,
                        binding=binding,
                        audit_now=audit_now,
                    )
                except DemoMemoryUnavailable as exc:
                    terminal_error = DemoMemoryRejected(str(exc))
                    _finish_execution_state(
                        job,
                        attempt,
                        status="REJECTED",
                        result_code="PROFILE_REJECTED",
                        error_code=None,
                        audit_now=audit_now,
                    )
                except (DemoMemoryConflict, DemoMemoryInputError) as exc:
                    terminal_error = exc
                    _finish_execution_state(
                        job,
                        attempt,
                        status="REJECTED",
                        result_code="PROFILE_REJECTED",
                        error_code=None,
                        audit_now=audit_now,
                    )
                except DemoMemoryAuthorityCorruption as exc:
                    terminal_error = exc
                    _finish_execution_state(
                        job,
                        attempt,
                        status="FAILED",
                        result_code="PROFILE_AUTHORITY_CORRUPTION",
                        error_code="PROFILE_AUTHORITY_CORRUPTION",
                        audit_now=audit_now,
                    )
                else:
                    _finish_execution_state(
                        job,
                        attempt,
                        status="COMPLETED",
                        result_code="PROFILE_REBUILT",
                        error_code=None,
                        audit_now=audit_now,
                    )
                await session.flush()
        if terminal_error is not None:
            raise terminal_error
        if result is None:
            raise DemoMemoryAuthorityCorruption("profile rebuild produced no durable result")
        return result

    async def _materialize_rebuild(
        self, session: AsyncSession, *, binding: DemoJobBinding, audit_now: datetime
    ) -> DemoAestheticProfileResult:
        events = await _events(session, binding.demo_actor_id)
        profiles = await _aesthetic_profiles(session, binding.demo_actor_id)
        projection = _project_lifecycle(events, profiles)
        sources = await _profile_sources(
            session, actor_id=binding.demo_actor_id, projection=projection
        )
        source_manifest = _profile_source_manifest(sources)
        compiler_version = DEMO_MEMORY_PROFILE_COMPILER_VERSION
        watermark_payload = {
            "active_event_sequences": sorted(projection.active_sequences),
            "actor_id": binding.demo_actor_id,
            "compiler_version": compiler_version,
            "invalidated_targets": [
                {"target_id": target_id, "target_type": target_type}
                for target_type, target_id in sorted(projection.invalidated_targets)
            ],
            "ledger_tail_digest": projection.tail_digest,
            "ledger_tail_sequence": projection.tail_sequence,
            "reset_epoch": projection.reset_epoch,
            "source_manifest": source_manifest,
        }
        compilation_watermark = hashlib.sha256(canonical_json_bytes(watermark_payload)).hexdigest()
        duplicate = await session.scalar(
            select(DemoAestheticProfile).where(
                DemoAestheticProfile.demo_actor_id == binding.demo_actor_id,
                DemoAestheticProfile.compilation_watermark == compilation_watermark,
                DemoAestheticProfile.compiler_version == compiler_version,
                DemoAestheticProfile.reset_epoch == projection.reset_epoch,
            )
        )
        if duplicate is not None:
            raise DemoMemoryConflict(
                "profile rebuild input already has immutable authority under another key"
            )
        generation = (
            cast(
                int,
                await session.scalar(
                    select(func.coalesce(func.max(DemoAestheticProfile.generation), 0)).where(
                        DemoAestheticProfile.demo_actor_id == binding.demo_actor_id
                    )
                ),
            )
            + 1
        )
        profile_payload = _profile_payload(sources, projection, source_manifest)
        authority_payload = {
            "as_of_event_sequence": projection.tail_sequence,
            "compilation_watermark": compilation_watermark,
            "compiler_version": compiler_version,
            "demo_actor_id": binding.demo_actor_id,
            "demo_job_binding_id": binding.id,
            "evidence_digests": list(_profile_evidence_digests(sources)),
            "generation": generation,
            "profile_payload": profile_payload,
            "reset_epoch": projection.reset_epoch,
        }
        profile = DemoAestheticProfile(
            id=new_id(),
            schema_version=DEMO_AESTHETIC_PROFILE_SCHEMA,
            canonical_payload=authority_payload,
            content_digest=_authority_digest(DEMO_AESTHETIC_PROFILE_SCHEMA, authority_payload),
            created_at=audit_now,
            **authority_payload,
        )
        session.add(profile)
        await session.flush()
        self._run_post_write_probe("PROFILE")
        return DemoAestheticProfileResult(
            job_id=binding.job_id,
            aesthetic_profile_id=profile.id,
            generation=profile.generation,
            compilation_watermark=profile.compilation_watermark,
            profile_digest=profile.content_digest,
            replayed=False,
        )

    async def freeze_context_inputs_in_session(
        self,
        session: AsyncSession,
        command: CompileDemoContext,
    ) -> DemoContextInputSnapshot:
        """Freeze deterministic Context inputs using the caller's explicit as-of time.

        Callers own actor/session locking and transaction scope.  This method
        never reads the clock: audit time is intentionally not compiler input.
        """
        command.validate()
        context_as_of = _normalize_explicit_time(command.context_as_of_time, "context_as_of_time")
        events = await _events(session, command.demo_actor_id)
        profiles = await _aesthetic_profiles(session, command.demo_actor_id)
        projection = _project_lifecycle(events, profiles)
        profile = next((item for item in profiles if item.id == command.aesthetic_profile_id), None)
        if profile is None or not _profile_is_active(profile, projection):
            raise DemoMemoryUnavailable("AestheticProfile is unavailable for Context")
        selected, rejected = await _context_evidence(
            session,
            actor_id=command.demo_actor_id,
            session_id=command.demo_session_id,
            profile=profile,
            projection=projection,
            context_as_of=context_as_of,
        )
        trace_payload: dict[str, object] = {
            "current_instruction_priority": 1,
            "evidence_precedence": [
                "CURRENT_INSTRUCTION",
                "EXPLICIT_LOCK_OR_OVERRIDE",
                "ACCEPTED_SELF_TRANSFER_OR_REFERENCE",
                "ACCEPTED_VISUAL_EPISODE",
                "QUESTIONNAIRE",
            ],
            "next_session_recall": any(
                entry.get("source_session_id") not in {None, command.demo_session_id}
                for entry in selected
            ),
            "profile_generation": profile.generation,
            "rejected_count": len(rejected),
            "selected_count": len(selected),
        }
        compiler_input = {
            "aesthetic_profile_digest": profile.content_digest,
            "compiler_version": command.compiler_version,
            "context_as_of_time": _canonical_time(context_as_of),
            "current_instruction_digest": command.current_instruction_digest,
            "rejected_evidence": rejected,
            "selected_evidence": selected,
            "session_id": command.demo_session_id,
        }
        watermark = hashlib.sha256(canonical_json_bytes(compiler_input)).hexdigest()
        input_payload = {
            "aesthetic_profile_id": profile.id,
            "profile_digest": profile.content_digest,
            "compiler_version": command.compiler_version,
            "context_as_of_time": _canonical_time(context_as_of),
            "current_instruction_digest": command.current_instruction_digest,
            "selected_evidence": selected,
            "rejected_evidence": rejected,
            "budgets": dict(_CONTEXT_BUDGETS),
            "trace_payload": trace_payload,
            "compilation_watermark": watermark,
            "expires_at": _canonical_time(context_as_of + _CONTEXT_TTL),
        }
        return DemoContextInputSnapshot(
            aesthetic_profile_id=profile.id,
            profile_digest=profile.content_digest,
            context_as_of_time=context_as_of,
            compiler_version=command.compiler_version,
            current_instruction_digest=command.current_instruction_digest,
            selected_evidence=tuple(selected),
            rejected_evidence=tuple(rejected),
            budgets=dict(_CONTEXT_BUDGETS),
            trace_payload=trace_payload,
            compilation_watermark=watermark,
            input_digest=hashlib.sha256(canonical_json_bytes(input_payload)).hexdigest(),
            expires_at=context_as_of + _CONTEXT_TTL,
        )

    async def materialize_context_in_session(
        self,
        session: AsyncSession,
        *,
        command: CompileDemoContext,
        expected: DemoContextInputSnapshot,
        demo_job_binding_id: str,
        audit_now: datetime,
    ) -> DemoContextCompilationResult:
        """Re-freeze and exactly verify queued input before creating Context authority."""
        actual = await self.freeze_context_inputs_in_session(session, command)
        if actual != expected:
            raise DemoMemoryConflict("frozen Context input no longer matches request authority")
        _require_id(demo_job_binding_id, "demo_job_binding_id")
        authority_payload = {
            "aesthetic_profile_id": expected.aesthetic_profile_id,
            "budgets": dict(expected.budgets),
            "compilation_watermark": expected.compilation_watermark,
            "compiler_version": expected.compiler_version,
            "context_as_of_time": _canonical_time(expected.context_as_of_time),
            "current_instruction_digest": expected.current_instruction_digest,
            "demo_actor_id": command.demo_actor_id,
            "demo_job_binding_id": demo_job_binding_id,
            "demo_session_id": command.demo_session_id,
            "expires_at": _canonical_time(expected.expires_at),
            "rejected_evidence": list(expected.rejected_evidence),
            "selected_evidence": list(expected.selected_evidence),
            "trace_payload": dict(expected.trace_payload),
        }
        context = DemoContextCompilation(
            id=new_id(),
            schema_version=DEMO_CONTEXT_COMPILATION_SCHEMA,
            canonical_payload=authority_payload,
            content_digest=_authority_digest(DEMO_CONTEXT_COMPILATION_SCHEMA, authority_payload),
            created_at=audit_now,
            aesthetic_profile_id=expected.aesthetic_profile_id,
            budgets=dict(expected.budgets),
            compilation_watermark=expected.compilation_watermark,
            compiler_version=expected.compiler_version,
            context_as_of_time=expected.context_as_of_time,
            current_instruction_digest=expected.current_instruction_digest,
            demo_actor_id=command.demo_actor_id,
            demo_job_binding_id=demo_job_binding_id,
            demo_session_id=command.demo_session_id,
            expires_at=expected.expires_at,
            rejected_evidence=list(expected.rejected_evidence),
            selected_evidence=list(expected.selected_evidence),
            trace_payload=dict(expected.trace_payload),
        )
        session.add(context)
        await session.flush()
        self._run_post_write_probe("CONTEXT")
        return DemoContextCompilationResult(
            job_id="",
            context_compilation_id=context.id,
            aesthetic_profile_id=context.aesthetic_profile_id,
            compilation_watermark=context.compilation_watermark,
            context_digest=context.content_digest,
            expires_at=context.expires_at,
            replayed=False,
        )

    async def compile_context(self, command: CompileDemoContext) -> DemoContextCompilationResult:
        command.validate()
        context_as_of = _normalize_explicit_time(command.context_as_of_time, "context_as_of_time")
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {
                "aesthetic_profile_id": command.aesthetic_profile_id,
                "compiler_version": command.compiler_version,
                "context_as_of_time": _canonical_time(context_as_of),
                "current_instruction_digest": command.current_instruction_digest,
                "session_id": command.demo_session_id,
            }
        )
        async with self._sessions() as session:
            async with session.begin():
                await _acquire_actor_lock(session, command.demo_actor_id)
                await _lock_active_actor(session, command.demo_actor_id)
                await _lock_active_session(
                    session,
                    actor_id=command.demo_actor_id,
                    session_id=command.demo_session_id,
                    as_of=context_as_of,
                )
                existing_binding = await _binding_for_key(
                    session,
                    actor_id=command.demo_actor_id,
                    operation=DEMO_CONTEXT_COMPILE_OPERATION,
                    key_hash=key_hash,
                )
                if existing_binding is not None:
                    return await _replay_context(
                        session,
                        existing_binding,
                        request_digest=request_digest,
                    )

                frozen = await self.freeze_context_inputs_in_session(session, command)
                same_input = await session.scalar(
                    select(DemoContextCompilation).where(
                        DemoContextCompilation.demo_actor_id == command.demo_actor_id,
                        DemoContextCompilation.demo_session_id == command.demo_session_id,
                        DemoContextCompilation.context_as_of_time == frozen.context_as_of_time,
                        DemoContextCompilation.compiler_version == command.compiler_version,
                    )
                )
                if same_input is not None:
                    raise DemoMemoryConflict(
                        "context input already has immutable authority under another key"
                    )

                job, binding, attempt, audit_now = await _create_execution(
                    session,
                    actor_id=command.demo_actor_id,
                    session_id=command.demo_session_id,
                    operation=DEMO_CONTEXT_COMPILE_OPERATION,
                    target_type="DEMO_SESSION",
                    target_id=command.demo_session_id,
                    key_hash=key_hash,
                    request_digest=request_digest,
                    request_id=command.request_id,
                    audit_now=self._normalized_audit_now(),
                )
                context = await self.materialize_context_in_session(
                    session,
                    command=command,
                    expected=frozen,
                    demo_job_binding_id=binding.id,
                    audit_now=audit_now,
                )
                _finish_execution(
                    job,
                    attempt,
                    result_code="CONTEXT_COMPILED",
                    audit_now=audit_now,
                )
                await session.flush()
                return DemoContextCompilationResult(
                    job_id=job.id,
                    context_compilation_id=context.context_compilation_id,
                    aesthetic_profile_id=context.aesthetic_profile_id,
                    compilation_watermark=context.compilation_watermark,
                    context_digest=context.context_digest,
                    expires_at=context.expires_at,
                    replayed=False,
                )

    async def recall_context(
        self,
        *,
        demo_actor_id: str,
        demo_session_id: str,
        recall_at: datetime,
    ) -> DemoContextRecall:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(demo_session_id, "demo_session_id")
        effective_recall_at = _normalize_explicit_time(recall_at, "recall_at")
        async with self._sessions() as session:
            await _lock_active_actor(session, demo_actor_id)
            await _lock_active_session(
                session,
                actor_id=demo_actor_id,
                session_id=demo_session_id,
                as_of=effective_recall_at,
                lock=False,
            )
            events = await _events(session, demo_actor_id)
            profiles = await _aesthetic_profiles(session, demo_actor_id)
            projection = _project_lifecycle(events, profiles)
            contexts = tuple(
                (
                    await session.scalars(
                        select(DemoContextCompilation)
                        .where(
                            DemoContextCompilation.demo_actor_id == demo_actor_id,
                            DemoContextCompilation.demo_session_id == demo_session_id,
                            DemoContextCompilation.context_as_of_time <= effective_recall_at,
                            DemoContextCompilation.expires_at >= effective_recall_at,
                        )
                        .order_by(
                            DemoContextCompilation.context_as_of_time.desc(),
                            DemoContextCompilation.id.desc(),
                        )
                    )
                ).all()
            )
            profiles_by_id = {profile.id: profile for profile in profiles}
            events_by_digest = {event.content_digest: event for event in projection.events}
            episode_rows = tuple(
                (
                    await session.execute(
                        select(DemoAcceptedVisualEpisode, DemoPreferenceEvent)
                        .join(
                            DemoPreferenceEvent,
                            DemoPreferenceEvent.id == DemoAcceptedVisualEpisode.acceptance_event_id,
                        )
                        .where(DemoAcceptedVisualEpisode.demo_actor_id == demo_actor_id)
                    )
                ).all()
            )
            episodes_by_digest = {
                episode.content_digest: (episode, event) for episode, event in episode_rows
            }
            for context in contexts:
                profile = profiles_by_id.get(context.aesthetic_profile_id)
                if (
                    profile is not None
                    and _profile_is_active(profile, projection)
                    and _context_selected_evidence_is_active(
                        context,
                        profile=profile,
                        projection=projection,
                        events_by_digest=events_by_digest,
                        episodes_by_digest=episodes_by_digest,
                    )
                    and (
                        "CONTEXT_COMPILATION",
                        context.id,
                    )
                    not in projection.invalidated_targets
                ):
                    return DemoContextRecall(
                        context_compilation_id=context.id,
                        aesthetic_profile_id=profile.id,
                        context_digest=context.content_digest,
                        expires_at=context.expires_at,
                    )
        raise DemoMemoryUnavailable("no active unexpired Context is available")

    def _normalized_audit_now(self) -> datetime:
        value = self._now()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise DemoMemoryAuthorityCorruption("D10 audit clock must be timezone-aware")
        return value.astimezone(UTC)

    def _run_post_write_probe(self, stage: Literal["PROFILE", "CONTEXT"]) -> None:
        if self._post_write_probe is not None:
            self._post_write_probe(stage)


async def _acquire_actor_lock(session: AsyncSession, actor_id: str) -> None:
    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended('mirror.demo.preference/' || :actor_id, 0))"
        ),
        {"actor_id": actor_id},
    )


async def _lock_active_actor(session: AsyncSession, actor_id: str) -> DemoActor:
    actor = cast(
        DemoActor | None,
        await session.scalar(select(DemoActor).where(DemoActor.id == actor_id).with_for_update()),
    )
    if actor is None or actor.tombstoned_at is not None:
        raise DemoMemoryUnavailable("Demo actor is unavailable")
    return actor


async def _lock_active_session(
    session: AsyncSession,
    *,
    actor_id: str,
    session_id: str,
    as_of: datetime,
    lock: bool = True,
) -> DemoSession:
    query = select(DemoSession).where(DemoSession.id == session_id)
    if lock:
        query = query.with_for_update()
    demo_session = cast(DemoSession | None, await session.scalar(query))
    if (
        demo_session is None
        or demo_session.demo_actor_id != actor_id
        or demo_session.closed_at is not None
        or demo_session.tombstoned_at is not None
        or demo_session.expires_at < as_of
    ):
        raise DemoMemoryUnavailable("Demo Session is unavailable")
    return demo_session


async def _events(session: AsyncSession, actor_id: str) -> tuple[DemoPreferenceEvent, ...]:
    values = tuple(
        (
            await session.scalars(
                select(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == actor_id)
                .order_by(DemoPreferenceEvent.event_sequence)
            )
        ).all()
    )
    try:
        verification = verify_demo_preference_event_chain(values)
    except DemoPreferenceLedgerCorruption as exc:
        raise DemoMemoryAuthorityCorruption(str(exc)) from exc
    if values and verification.demo_actor_id != actor_id:
        raise DemoMemoryAuthorityCorruption("preference ledger actor is inconsistent")
    return values


async def _aesthetic_profiles(
    session: AsyncSession, actor_id: str
) -> tuple[DemoAestheticProfile, ...]:
    return tuple(
        (
            await session.scalars(
                select(DemoAestheticProfile)
                .where(DemoAestheticProfile.demo_actor_id == actor_id)
                .order_by(DemoAestheticProfile.generation, DemoAestheticProfile.id)
            )
        ).all()
    )


def _project_lifecycle(
    events: Sequence[DemoPreferenceEvent],
    profiles: Sequence[DemoAestheticProfile],
) -> _LifecycleProjection:
    state_at: dict[int, tuple[DemoPreferenceEvent, ...]] = {0: ()}
    profiles_by_id = {profile.id: profile for profile in profiles}
    active: list[DemoPreferenceEvent] = []
    reset_epoch = 0
    for event in events:
        if event.event_type == "RESET":
            reset_epoch += 1
            watermark = event.signal.get("reset_watermark")
            if (
                type(watermark) is not int
                or watermark < 0
                or watermark >= event.event_sequence
                or watermark not in state_at
            ):
                raise DemoMemoryAuthorityCorruption("RESET watermark authority is invalid")
            active = list(state_at[watermark])
        elif event.event_type == "ROLLBACK" and event.target_type == "AESTHETIC_PROFILE":
            target = profiles_by_id.get(cast(str, event.target_id))
            if (
                target is None
                or target.demo_actor_id != event.demo_actor_id
                or target.as_of_event_sequence < 0
                or target.as_of_event_sequence >= event.event_sequence
                or target.as_of_event_sequence not in state_at
            ):
                raise DemoMemoryAuthorityCorruption("ROLLBACK Profile watermark is invalid")
            active = list(state_at[target.as_of_event_sequence])
        active.append(event)
        state_at[event.event_sequence] = tuple(active)

    learning_enabled = True
    learning_at_event: dict[str, bool] = {}
    invalidated_targets: set[tuple[str, str]] = set()
    for event in active:
        learning_at_event[event.id] = learning_enabled
        if event.event_type == "LEARNING_DISABLED":
            learning_enabled = False
        elif event.event_type == "LEARNING_ENABLED":
            learning_enabled = True
        if event.event_type in _INVALIDATION_EVENT_TYPES and event.target_type and event.target_id:
            invalidated_targets.add((event.target_type, event.target_id))

    tail = events[-1] if events else None
    return _LifecycleProjection(
        events=tuple(events),
        active_events=tuple(active),
        active_sequences=frozenset(item.event_sequence for item in active),
        active_event_digests=frozenset(item.content_digest for item in active),
        all_event_digests=frozenset(item.content_digest for item in events),
        learning_at_event=learning_at_event,
        learning_enabled=learning_enabled,
        invalidated_targets=frozenset(invalidated_targets),
        reset_epoch=reset_epoch,
        tail_sequence=tail.event_sequence if tail is not None else 0,
        tail_digest=tail.content_digest if tail is not None else GENESIS_EVENT_DIGEST,
    )


async def _profile_sources(
    session: AsyncSession,
    *,
    actor_id: str,
    projection: _LifecycleProjection,
) -> _ProfileSources:
    desired_rows = tuple(
        (
            await session.scalars(
                select(DemoDesiredDeltaProfile)
                .where(DemoDesiredDeltaProfile.demo_actor_id == actor_id)
                .order_by(
                    DemoDesiredDeltaProfile.version.desc(),
                    DemoDesiredDeltaProfile.id.desc(),
                )
            )
        ).all()
    )
    desired = next(
        (
            item
            for item in desired_rows
            if _source_is_active(
                target_type="DESIRED_DELTA_PROFILE",
                target_id=item.id,
                as_of_event_sequence=item.as_of_event_sequence,
                evidence_digests=item.evidence_digests,
                projection=projection,
            )
            and ("SELF_STATE", item.self_state_id) not in projection.invalidated_targets
        ),
        None,
    )
    if desired is None and not desired_rows:
        raise DemoMemoryUnavailable("no active DesiredDeltaProfile is available")

    style_rows = tuple(
        (
            await session.scalars(
                select(DemoStyleProfile)
                .where(DemoStyleProfile.demo_actor_id == actor_id)
                .order_by(DemoStyleProfile.version.desc(), DemoStyleProfile.id.desc())
            )
        ).all()
    )
    style = next(
        (
            item
            for item in style_rows
            if desired is not None
            and item.desired_delta_profile_id in {None, desired.id}
            and _source_is_active(
                target_type="STYLE_PROFILE",
                target_id=item.id,
                as_of_event_sequence=item.as_of_event_sequence,
                evidence_digests=item.evidence_digests,
                projection=projection,
            )
        ),
        None,
    )

    constraint_rows = tuple(
        (
            await session.scalars(
                select(DemoIdentityConstraints)
                .where(
                    DemoIdentityConstraints.demo_actor_id == actor_id,
                    DemoIdentityConstraints.constraint_scope == "PERSISTENT",
                )
                .order_by(
                    DemoIdentityConstraints.version.desc(),
                    DemoIdentityConstraints.id.desc(),
                )
            )
        ).all()
    )
    constraints = next(
        (
            item
            for item in constraint_rows
            if desired is not None
            and _event_evidence_is_active(item.source_event_digests, projection)
            and (
                item.self_state_id is None
                or ("SELF_STATE", item.self_state_id) not in projection.invalidated_targets
            )
        ),
        None,
    )

    reference_rows = tuple(
        (
            await session.scalars(
                select(DemoReferenceProfile)
                .where(DemoReferenceProfile.demo_actor_id == actor_id)
                .order_by(DemoReferenceProfile.version.desc(), DemoReferenceProfile.id.desc())
            )
        ).all()
    )
    image_versions_by_result_asset = {
        item.result_asset_id: item
        for item in (
            await session.scalars(
                select(DemoImageVersion).where(DemoImageVersion.demo_actor_id == actor_id)
            )
        ).all()
    }
    styles_by_id = {item.id: item for item in style_rows}
    constraints_by_id = {item.id: item for item in constraint_rows}
    reference: DemoReferenceProfile | None = None
    reference_dependencies: _ReferenceDependencies | None = None
    for item in reference_rows:
        if (
            desired is None
            or item.desired_delta_profile_id != desired.id
            or ("REFERENCE_PROFILE", item.id) in projection.invalidated_targets
            or not _event_evidence_is_active(item.evidence_digests, projection)
        ):
            continue
        linked_style = (
            None if item.style_profile_id is None else styles_by_id.get(item.style_profile_id)
        )
        if item.style_profile_id is not None and (
            linked_style is None
            or not _source_is_active(
                target_type="STYLE_PROFILE",
                target_id=linked_style.id,
                as_of_event_sequence=linked_style.as_of_event_sequence,
                evidence_digests=linked_style.evidence_digests,
                projection=projection,
            )
        ):
            continue
        linked_constraints = (
            None
            if item.identity_constraints_id is None
            else constraints_by_id.get(item.identity_constraints_id)
        )
        if item.identity_constraints_id is not None and (
            linked_constraints is None
            or not _event_evidence_is_active(linked_constraints.source_event_digests, projection)
            or (
                linked_constraints.self_state_id is not None
                and ("SELF_STATE", linked_constraints.self_state_id)
                in projection.invalidated_targets
            )
        ):
            continue
        expected_dependency_digests = {desired.content_digest}
        if linked_style is not None:
            expected_dependency_digests.add(linked_style.content_digest)
        if linked_constraints is not None:
            expected_dependency_digests.add(linked_constraints.content_digest)
        if not expected_dependency_digests.issubset(set(item.evidence_digests)):
            continue
        candidate_dependencies = _reference_dependencies(
            item,
            desired=desired,
            style=linked_style,
            constraints=linked_constraints,
            image_versions_by_result_asset=image_versions_by_result_asset,
            projection=projection,
        )
        if candidate_dependencies is None:
            continue
        reference = item
        reference_dependencies = candidate_dependencies
        break

    episodes = tuple(
        (
            await session.execute(
                select(DemoAcceptedVisualEpisode, DemoPreferenceEvent)
                .join(
                    DemoPreferenceEvent,
                    DemoPreferenceEvent.id == DemoAcceptedVisualEpisode.acceptance_event_id,
                )
                .where(DemoAcceptedVisualEpisode.demo_actor_id == actor_id)
                .order_by(
                    DemoPreferenceEvent.event_sequence,
                    DemoAcceptedVisualEpisode.id,
                )
            )
        ).all()
    )
    active_episodes = tuple(
        (episode, event)
        for episode, event in episodes
        if event.content_digest in projection.active_event_digests
        and projection.learning_at_event.get(event.id, False)
        and ("IMAGE_VERSION", episode.accepted_image_version_id)
        not in projection.invalidated_targets
    )
    episode_event_ids = {event.id for _, event in active_episodes}
    controls = tuple(
        event
        for event in projection.active_events
        if event.event_type in _PROFILE_CONTROL_EVENT_TYPES
    )
    negative_feedback = tuple(
        event
        for event in projection.active_events
        if event.event_type in {"IMAGE_REJECTED", "IMAGE_ADJUSTED"}
        and projection.learning_at_event.get(event.id, False)
    )
    excluded_acceptance = tuple(
        event
        for event in projection.active_events
        if event.event_type == "IMAGE_ACCEPTED" and event.id not in episode_event_ids
    )
    return _ProfileSources(
        desired=desired,
        style=style,
        constraints=constraints,
        reference=reference,
        reference_dependencies=reference_dependencies,
        episodes=active_episodes,
        controls=controls,
        negative_feedback=negative_feedback,
        excluded_acceptance=excluded_acceptance,
    )


def _source_is_active(
    *,
    target_type: str,
    target_id: str,
    as_of_event_sequence: int,
    evidence_digests: Sequence[str],
    projection: _LifecycleProjection,
) -> bool:
    return (
        (target_type, target_id) not in projection.invalidated_targets
        and (as_of_event_sequence == 0 or as_of_event_sequence in projection.active_sequences)
        and _event_evidence_is_active(evidence_digests, projection)
    )


def _event_evidence_is_active(digests: Sequence[str], projection: _LifecycleProjection) -> bool:
    for digest in digests:
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            raise DemoMemoryAuthorityCorruption("source evidence digest is invalid")
        if digest in projection.all_event_digests and digest not in projection.active_event_digests:
            return False
    return True


def _reference_dependencies(
    reference: DemoReferenceProfile,
    *,
    desired: DemoDesiredDeltaProfile,
    style: DemoStyleProfile | None,
    constraints: DemoIdentityConstraints | None,
    image_versions_by_result_asset: Mapping[str, DemoImageVersion],
    projection: _LifecycleProjection,
) -> _ReferenceDependencies | None:
    source_assets = reference.source_assets
    source_views = reference.structured_profile.get("source_views")
    if (
        not isinstance(source_assets, list)
        or not source_assets
        or not isinstance(source_views, list)
        or len(source_views) != len(source_assets)
    ):
        return None

    views_by_asset: dict[str, Mapping[str, object]] = {}
    for raw_view in source_views:
        if not isinstance(raw_view, dict):
            return None
        asset_id = raw_view.get("asset_id")
        image_digest = raw_view.get("image_version_digest")
        sha256 = raw_view.get("sha256")
        if (
            not isinstance(asset_id, str)
            or _ID.fullmatch(asset_id) is None
            or not isinstance(image_digest, str)
            or _DIGEST.fullmatch(image_digest) is None
            or not isinstance(sha256, str)
            or _DIGEST.fullmatch(sha256) is None
            or asset_id in views_by_asset
        ):
            return None
        views_by_asset[asset_id] = raw_view

    source_asset_ids: list[str] = []
    image_version_ids: list[str] = []
    image_version_digests: list[str] = []
    for raw_source in source_assets:
        if not isinstance(raw_source, dict):
            return None
        asset_id = raw_source.get("asset_id")
        sha256 = raw_source.get("sha256")
        if (
            not isinstance(asset_id, str)
            or _ID.fullmatch(asset_id) is None
            or not isinstance(sha256, str)
            or _DIGEST.fullmatch(sha256) is None
            or asset_id in source_asset_ids
        ):
            return None
        source_view = views_by_asset.get(asset_id)
        image_version = image_versions_by_result_asset.get(asset_id)
        if (
            source_view is None
            or image_version is None
            or image_version.content_digest != source_view.get("image_version_digest")
            or image_version.result_asset_sha256 != sha256
            or source_view.get("sha256") != sha256
            or image_version.content_digest not in reference.evidence_digests
            or ("IMAGE_VERSION", image_version.id) in projection.invalidated_targets
        ):
            return None
        source_asset_ids.append(asset_id)
        image_version_ids.append(image_version.id)
        image_version_digests.append(image_version.content_digest)

    if set(views_by_asset) != set(source_asset_ids):
        return None
    dependency_event_digests = sorted(
        {
            *desired.evidence_digests,
            *(style.evidence_digests if style is not None else ()),
            *(constraints.source_event_digests if constraints is not None else ()),
        }
    )
    if not _event_evidence_is_active(dependency_event_digests, projection):
        return None
    return _ReferenceDependencies(
        style_profile_id=None if style is None else style.id,
        identity_constraints_id=None if constraints is None else constraints.id,
        source_asset_ids=tuple(source_asset_ids),
        source_image_version_ids=tuple(image_version_ids),
        source_image_version_digests=tuple(image_version_digests),
        dependency_event_digests=tuple(dependency_event_digests),
    )


def _profile_source_manifest(sources: _ProfileSources) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    if sources.desired is not None:
        values.append(
            {
                "digest": sources.desired.content_digest,
                "id": sources.desired.id,
                "kind": "DESIRED_DELTA_PROFILE",
                "version": sources.desired.version,
            }
        )
    if sources.style is not None:
        values.append(
            {
                "digest": sources.style.content_digest,
                "id": sources.style.id,
                "kind": "STYLE_PROFILE",
                "version": sources.style.version,
            }
        )
    if sources.constraints is not None:
        values.append(
            {
                "digest": sources.constraints.content_digest,
                "id": sources.constraints.id,
                "kind": "IDENTITY_CONSTRAINTS",
                "version": sources.constraints.version,
            }
        )
    if sources.reference is not None:
        dependencies = sources.reference_dependencies
        if dependencies is None:
            raise DemoMemoryAuthorityCorruption(
                "active ReferenceProfile has no validated dependency manifest"
            )
        values.append(
            {
                "dependency_event_digests": list(dependencies.dependency_event_digests),
                "digest": sources.reference.content_digest,
                "id": sources.reference.id,
                "identity_constraints_id": dependencies.identity_constraints_id,
                "kind": "REFERENCE_PROFILE",
                "source_asset_ids": list(dependencies.source_asset_ids),
                "source_image_version_digests": list(dependencies.source_image_version_digests),
                "source_image_version_ids": list(dependencies.source_image_version_ids),
                "style_profile_id": dependencies.style_profile_id,
                "version": sources.reference.version,
            }
        )
    values.extend(
        {
            "accepted_image_version_id": episode.accepted_image_version_id,
            "acceptance_event_sequence": event.event_sequence,
            "digest": episode.content_digest,
            "id": episode.id,
            "kind": "ACCEPTED_VISUAL_EPISODE",
        }
        for episode, event in sources.episodes
    )
    values.extend(
        {
            "digest": event.content_digest,
            "event_sequence": event.event_sequence,
            "event_type": event.event_type,
            "id": event.id,
            "kind": "PREFERENCE_CONTROL_EVENT",
        }
        for event in sources.controls
    )
    values.extend(
        {
            "digest": event.content_digest,
            "event_sequence": event.event_sequence,
            "event_type": event.event_type,
            "id": event.id,
            "kind": "NEGATIVE_FEEDBACK_EVENT",
        }
        for event in sources.negative_feedback
    )
    values.extend(
        {
            "digest": event.content_digest,
            "event_sequence": event.event_sequence,
            "id": event.id,
            "kind": "EXCLUDED_EVENT_ONLY_ACCEPTANCE",
        }
        for event in sources.excluded_acceptance
    )
    return values


def _profile_payload(
    sources: _ProfileSources,
    projection: _LifecycleProjection,
    source_manifest: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "accepted_visual_episodes": [
            {
                "accepted_image_version_id": episode.accepted_image_version_id,
                "acceptance_event_digest": event.content_digest,
                "digest": episode.content_digest,
                "final_asset_sha256": episode.final_asset_sha256,
                "source_session_id": episode.demo_session_id,
            }
            for episode, event in sources.episodes
        ],
        "desired_delta": (
            None
            if sources.desired is None
            else {
                "digest": sources.desired.content_digest,
                "dimensions": sources.desired.dimensions,
                "id": sources.desired.id,
                "restraint": sources.desired.restraint,
                "self_state_id": sources.desired.self_state_id,
            }
        ),
        "evidence_precedence": [
            "CURRENT_INSTRUCTION",
            "EXPLICIT_LOCK_OR_OVERRIDE",
            "ACCEPTED_SELF_TRANSFER_OR_REFERENCE",
            "ACCEPTED_VISUAL_EPISODE",
            "QUESTIONNAIRE",
        ],
        "excluded_feedback": [
            {"digest": event.content_digest, "reason": "FINAL_SAVE_REQUIRED"}
            for event in sources.excluded_acceptance
        ],
        "identity_constraints": (
            None
            if sources.constraints is None
            else {
                "bounds": sources.constraints.bounds,
                "digest": sources.constraints.content_digest,
                "id": sources.constraints.id,
                "locks": sources.constraints.locks,
                "prohibited_operations": sources.constraints.prohibited_operations,
            }
        ),
        "learning_enabled": projection.learning_enabled,
        "negative_feedback": [
            {
                "digest": event.content_digest,
                "event_type": event.event_type,
                "source_session_id": event.demo_session_id,
            }
            for event in sources.negative_feedback
        ],
        "reference_profile": (
            None
            if sources.reference is None
            else {
                "digest": sources.reference.content_digest,
                "id": sources.reference.id,
                "source_assets": sources.reference.source_assets,
                "structured_profile": sources.reference.structured_profile,
            }
        ),
        "source_manifest": list(source_manifest),
        "style": (
            None
            if sources.style is None
            else {
                "digest": sources.style.content_digest,
                "id": sources.style.id,
                "negative_evidence": sources.style.negative_evidence,
                "preferences": sources.style.preferences,
            }
        ),
    }


def _profile_evidence_digests(sources: _ProfileSources) -> tuple[str, ...]:
    values = [item["digest"] for item in _profile_source_manifest(sources)]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
            raise DemoMemoryAuthorityCorruption("profile evidence manifest digest is invalid")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


async def _context_evidence(
    session: AsyncSession,
    *,
    actor_id: str,
    session_id: str,
    profile: DemoAestheticProfile,
    projection: _LifecycleProjection,
    context_as_of: datetime,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    selected: list[dict[str, object]] = [
        {
            "digest": profile.content_digest,
            "event_sequence": _NON_EVENT_SEQUENCE,
            "kind": "AESTHETIC_PROFILE",
            "priority": 2,
            "source_session_id": None,
        }
    ]
    rejected: list[dict[str, object]] = []

    persistent = [
        event
        for event in projection.active_events
        if event.event_type in _PERSISTENT_EVENT_TYPES and event.occurred_at <= context_as_of
    ]
    current_session = [
        event
        for event in projection.active_events
        if event.event_type in _CURRENT_SESSION_EVENT_TYPES
        and event.demo_session_id == session_id
        and event.occurred_at <= context_as_of
    ]
    prior_session_overrides = [
        event
        for event in projection.active_events
        if event.event_type == "TEMPORARY_SESSION_OVERRIDE"
        and event.demo_session_id not in {None, session_id}
        and event.occurred_at <= context_as_of
    ]

    _select_event_budget(
        persistent,
        limit=_CONTEXT_BUDGETS["persistent_control_events"],
        kind="PERSISTENT_CONTROL_EVENT",
        priority=3,
        selected=selected,
        rejected=rejected,
    )
    _select_event_budget(
        current_session,
        limit=_CONTEXT_BUDGETS["current_session_events"],
        kind="CURRENT_SESSION_EVENT",
        priority=1,
        selected=selected,
        rejected=rejected,
    )
    rejected.extend(
        {
            "digest": event.content_digest,
            "kind": "TEMPORARY_SESSION_OVERRIDE",
            "reason": "SESSION_SCOPE_MISMATCH",
            "source_session_id": event.demo_session_id,
        }
        for event in prior_session_overrides
    )

    episode_rows = tuple(
        (
            await session.execute(
                select(DemoAcceptedVisualEpisode, DemoPreferenceEvent)
                .join(
                    DemoPreferenceEvent,
                    DemoPreferenceEvent.id == DemoAcceptedVisualEpisode.acceptance_event_id,
                )
                .where(DemoAcceptedVisualEpisode.demo_actor_id == actor_id)
                .order_by(
                    DemoPreferenceEvent.event_sequence.desc(),
                    DemoAcceptedVisualEpisode.id.desc(),
                )
            )
        ).all()
    )
    eligible_episodes = [
        (episode, event)
        for episode, event in episode_rows
        if event.content_digest in projection.active_event_digests
        and projection.learning_at_event.get(event.id, False)
        and event.occurred_at <= context_as_of
        and ("IMAGE_VERSION", episode.accepted_image_version_id)
        not in projection.invalidated_targets
    ]
    episode_limit = _CONTEXT_BUDGETS["accepted_visual_episodes"]
    for episode, _event in eligible_episodes[:episode_limit]:
        selected.append(
            {
                "acceptance_event_digest": _event.content_digest,
                "accepted_image_version_id": episode.accepted_image_version_id,
                "digest": episode.content_digest,
                "event_sequence": _event.event_sequence,
                "kind": "ACCEPTED_VISUAL_EPISODE",
                "priority": 4,
                "source_session_id": episode.demo_session_id,
            }
        )
    rejected.extend(
        {
            "digest": episode.content_digest,
            "kind": "ACCEPTED_VISUAL_EPISODE",
            "reason": "BUDGET_EXCEEDED",
            "source_session_id": episode.demo_session_id,
        }
        for episode, _event in eligible_episodes[episode_limit:]
    )

    linked_acceptance_ids = {event.id for _, event in episode_rows}
    rejected.extend(
        {
            "digest": event.content_digest,
            "kind": "IMAGE_ACCEPTED_FEEDBACK",
            "reason": "FINAL_SAVE_REQUIRED",
            "source_session_id": event.demo_session_id,
        }
        for event in projection.active_events
        if event.event_type == "IMAGE_ACCEPTED"
        and event.id not in linked_acceptance_ids
        and event.occurred_at <= context_as_of
    )

    selected = _deduplicate_selected(selected, rejected)
    selected.sort(
        key=lambda item: (
            cast(int, item["priority"]),
            cast(int, item["event_sequence"]),
            cast(str, item["kind"]),
            cast(str, item["digest"]),
        )
    )
    rejected.sort(
        key=lambda item: (
            cast(str, item["reason"]),
            cast(str, item["kind"]),
            cast(str, item["digest"]),
        )
    )
    if len(selected) > _CONTEXT_BUDGETS["total_selected_evidence"]:
        overflow = selected[_CONTEXT_BUDGETS["total_selected_evidence"] :]
        selected = selected[: _CONTEXT_BUDGETS["total_selected_evidence"]]
        rejected.extend(
            {
                "digest": item["digest"],
                "kind": item["kind"],
                "reason": "TOTAL_BUDGET_EXCEEDED",
                "source_session_id": item.get("source_session_id"),
            }
            for item in overflow
        )
        rejected.sort(
            key=lambda item: (
                cast(str, item["reason"]),
                cast(str, item["kind"]),
                cast(str, item["digest"]),
            )
        )
    return selected, rejected


def _select_event_budget(
    events: Sequence[DemoPreferenceEvent],
    *,
    limit: int,
    kind: str,
    priority: int,
    selected: list[dict[str, object]],
    rejected: list[dict[str, object]],
) -> None:
    ordered = sorted(events, key=lambda item: (-item.event_sequence, item.content_digest))
    selected.extend(
        {
            "digest": event.content_digest,
            "event_sequence": event.event_sequence,
            "event_type": event.event_type,
            "kind": kind,
            "priority": priority,
            "source_session_id": event.demo_session_id,
        }
        for event in ordered[:limit]
    )
    rejected.extend(
        {
            "digest": event.content_digest,
            "kind": kind,
            "reason": "BUDGET_EXCEEDED",
            "source_session_id": event.demo_session_id,
        }
        for event in ordered[limit:]
    )


def _deduplicate_selected(
    values: Sequence[dict[str, object]], rejected: list[dict[str, object]]
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in values:
        digest = cast(str, item["digest"])
        if digest in seen:
            rejected.append(
                {
                    "digest": digest,
                    "kind": cast(str, item["kind"]),
                    "reason": "DUPLICATE_EVIDENCE",
                    "source_session_id": item.get("source_session_id"),
                }
            )
            continue
        seen.add(digest)
        result.append(item)
    return result


def _profile_is_active(profile: DemoAestheticProfile, projection: _LifecycleProjection) -> bool:
    if ("AESTHETIC_PROFILE", profile.id) in projection.invalidated_targets:
        return False
    if (
        profile.as_of_event_sequence != 0
        and profile.as_of_event_sequence not in projection.active_sequences
    ):
        return False
    if any(
        digest in projection.all_event_digests and digest not in projection.active_event_digests
        for digest in profile.evidence_digests
    ):
        return False
    manifest = profile.profile_payload.get("source_manifest")
    if not isinstance(manifest, list):
        return False
    kind_to_target = {
        "DESIRED_DELTA_PROFILE": "DESIRED_DELTA_PROFILE",
        "STYLE_PROFILE": "STYLE_PROFILE",
        "REFERENCE_PROFILE": "REFERENCE_PROFILE",
    }
    for item in manifest:
        if not isinstance(item, dict):
            return False
        kind = item.get("kind")
        target_type = kind_to_target.get(cast(str, kind))
        target_id = item.get("id")
        if (
            target_type is not None
            and isinstance(target_id, str)
            and (target_type, target_id) in projection.invalidated_targets
        ):
            return False
        if kind == "REFERENCE_PROFILE" and not _reference_manifest_is_active(item, projection):
            return False
        image_version_id = item.get("accepted_image_version_id")
        if (
            isinstance(image_version_id, str)
            and ("IMAGE_VERSION", image_version_id) in projection.invalidated_targets
        ):
            return False
    desired = profile.profile_payload.get("desired_delta")
    if isinstance(desired, dict):
        self_state_id = desired.get("self_state_id")
        if (
            isinstance(self_state_id, str)
            and ("SELF_STATE", self_state_id) in projection.invalidated_targets
        ):
            return False
    return True


def _context_selected_evidence_is_active(
    context: DemoContextCompilation,
    *,
    profile: DemoAestheticProfile,
    projection: _LifecycleProjection,
    events_by_digest: Mapping[str, DemoPreferenceEvent],
    episodes_by_digest: Mapping[str, tuple[DemoAcceptedVisualEpisode, DemoPreferenceEvent]],
) -> bool:
    entries = context.selected_evidence
    if not isinstance(entries, list) or not entries:
        return False
    profile_entries = 0
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        digest = entry.get("digest")
        kind = entry.get("kind")
        event_sequence = entry.get("event_sequence")
        if (
            not isinstance(digest, str)
            or _DIGEST.fullmatch(digest) is None
            or not isinstance(kind, str)
            or type(event_sequence) is not int
            or event_sequence < 0
        ):
            return False
        if kind == "AESTHETIC_PROFILE":
            profile_entries += 1
            if digest != profile.content_digest or event_sequence != _NON_EVENT_SEQUENCE:
                return False
            continue
        if kind in {"CURRENT_SESSION_EVENT", "PERSISTENT_CONTROL_EVENT"}:
            event = events_by_digest.get(digest)
            expected_types = (
                _CURRENT_SESSION_EVENT_TYPES
                if kind == "CURRENT_SESSION_EVENT"
                else _PERSISTENT_EVENT_TYPES
            )
            if (
                event is None
                or event.content_digest not in projection.active_event_digests
                or event.event_sequence != event_sequence
                or event.event_type not in expected_types
                or (
                    kind == "CURRENT_SESSION_EVENT"
                    and event.demo_session_id != context.demo_session_id
                )
            ):
                return False
            continue
        if kind == "ACCEPTED_VISUAL_EPISODE":
            episode_row = episodes_by_digest.get(digest)
            if episode_row is None:
                return False
            episode, event = episode_row
            if (
                event.content_digest not in projection.active_event_digests
                or not projection.learning_at_event.get(event.id, False)
                or event.event_sequence != event_sequence
                or entry.get("acceptance_event_digest") != event.content_digest
                or entry.get("accepted_image_version_id") != episode.accepted_image_version_id
                or entry.get("source_session_id") != episode.demo_session_id
                or ("IMAGE_VERSION", episode.accepted_image_version_id)
                in projection.invalidated_targets
            ):
                return False
            continue
        return False
    return profile_entries == 1


def _reference_manifest_is_active(
    item: Mapping[str, object], projection: _LifecycleProjection
) -> bool:
    style_profile_id = item.get("style_profile_id")
    identity_constraints_id = item.get("identity_constraints_id")
    source_asset_ids = item.get("source_asset_ids")
    source_image_version_ids = item.get("source_image_version_ids")
    source_image_version_digests = item.get("source_image_version_digests")
    dependency_event_digests = item.get("dependency_event_digests")
    if (
        (style_profile_id is not None and not _valid_id_value(style_profile_id))
        or (identity_constraints_id is not None and not _valid_id_value(identity_constraints_id))
        or not _valid_unique_values(source_asset_ids, _ID)
        or not _valid_unique_values(source_image_version_ids, _ID)
        or not _valid_unique_values(source_image_version_digests, _DIGEST)
        or not _valid_unique_values(dependency_event_digests, _DIGEST, allow_empty=True)
        or len(cast(list[object], source_asset_ids))
        != len(cast(list[object], source_image_version_ids))
        or len(cast(list[object], source_asset_ids))
        != len(cast(list[object], source_image_version_digests))
    ):
        return False
    if (
        isinstance(style_profile_id, str)
        and ("STYLE_PROFILE", style_profile_id) in projection.invalidated_targets
    ):
        return False
    if any(
        ("IMAGE_VERSION", cast(str, image_version_id)) in projection.invalidated_targets
        for image_version_id in cast(list[object], source_image_version_ids)
    ):
        return False
    return _event_evidence_is_active(cast(list[str], dependency_event_digests), projection)


def _valid_id_value(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _valid_unique_values(
    value: object, pattern: re.Pattern[str], *, allow_empty: bool = False
) -> bool:
    if not isinstance(value, list) or (not allow_empty and not value):
        return False
    typed_values = [item for item in value if isinstance(item, str)]
    return (
        len(typed_values) == len(value)
        and len(set(typed_values)) == len(typed_values)
        and all(pattern.fullmatch(item) is not None for item in typed_values)
    )


async def _binding_for_key(
    session: AsyncSession,
    *,
    actor_id: str,
    operation: str,
    key_hash: str,
) -> DemoJobBinding | None:
    return cast(
        DemoJobBinding | None,
        await session.scalar(
            select(DemoJobBinding).where(
                DemoJobBinding.demo_actor_id == actor_id,
                DemoJobBinding.endpoint_operation == operation,
                DemoJobBinding.idempotency_key_hash == key_hash,
            )
        ),
    )


async def _create_execution(
    session: AsyncSession,
    *,
    actor_id: str,
    session_id: str | None,
    operation: str,
    target_type: Literal["DEMO_ACTOR", "DEMO_SESSION"],
    target_id: str,
    key_hash: str,
    request_digest: str,
    request_id: str,
    audit_now: datetime,
) -> tuple[Job, DemoJobBinding, JobAttempt, datetime]:
    job = Job(
        id=new_id(),
        job_type=f"demo_p3_p7.{operation}",
        status="PENDING",
        idempotency_key_hash=_formal_job_key_hash(actor_id, operation, key_hash),
        request_id=request_id,
        payload={},
        owner_user_id=None,
        ingestion_upload_intent_id=None,
        attempt_count=0,
        lease_token=None,
        lease_acquired_at=None,
        lease_expires_at=None,
        finalized_at=None,
        result_asset_id=None,
        result_code=None,
        created_at=audit_now,
        updated_at=audit_now,
    )
    session.add(job)
    await session.flush()
    binding_payload = {
        "demo_actor_id": actor_id,
        "demo_session_id": session_id,
        "endpoint_operation": operation,
        "idempotency_key_hash": key_hash,
        "job_id": job.id,
        "request_digest": request_digest,
        "target_id": target_id,
        "target_type": target_type,
    }
    binding = DemoJobBinding(
        id=new_id(),
        schema_version=DEMO_JOB_BINDING_SCHEMA,
        canonical_payload=binding_payload,
        content_digest=_authority_digest(DEMO_JOB_BINDING_SCHEMA, binding_payload),
        created_at=audit_now,
        **binding_payload,
    )
    session.add(binding)
    await session.flush()
    attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=1,
        status="RUNNING",
        lease_token=None,
        result_code=None,
        error_code=None,
        started_at=audit_now,
        finished_at=None,
    )
    session.add(attempt)
    job.status = "RUNNING"
    job.attempt_count = 1
    job.updated_at = audit_now
    await session.flush()
    return job, binding, attempt, audit_now


async def _create_pending_execution(
    session: AsyncSession,
    *,
    actor_id: str,
    operation: str,
    target_type: Literal["DEMO_ACTOR"],
    target_id: str,
    key_hash: str,
    request_digest: str,
    request_id: str,
    audit_now: datetime,
) -> tuple[Job, DemoJobBinding]:
    """Create the durable D10 envelope without claiming or materializing it."""
    job = Job(
        id=new_id(),
        job_type=f"demo_p3_p7.{operation}",
        status="PENDING",
        idempotency_key_hash=_formal_job_key_hash(actor_id, operation, key_hash),
        request_id=request_id,
        payload={},
        owner_user_id=None,
        ingestion_upload_intent_id=None,
        attempt_count=0,
        lease_token=None,
        lease_acquired_at=None,
        lease_expires_at=None,
        finalized_at=None,
        result_asset_id=None,
        result_code=None,
        created_at=audit_now,
        updated_at=audit_now,
    )
    binding_payload = {
        "demo_actor_id": actor_id,
        "demo_session_id": None,
        "endpoint_operation": operation,
        "idempotency_key_hash": key_hash,
        "job_id": job.id,
        "request_digest": request_digest,
        "target_id": target_id,
        "target_type": target_type,
    }
    binding = DemoJobBinding(
        id=new_id(),
        schema_version=DEMO_JOB_BINDING_SCHEMA,
        canonical_payload=binding_payload,
        content_digest=_authority_digest(DEMO_JOB_BINDING_SCHEMA, binding_payload),
        created_at=audit_now,
        **binding_payload,
    )
    attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=1,
        status="PENDING",
        lease_token=None,
        result_code=None,
        error_code=None,
        started_at=audit_now,
        finished_at=None,
    )
    # A savepoint allows unique-key contention to reload the committed winner
    # while retaining the outer transaction and actor advisory lock.
    async with session.begin_nested():
        session.add(job)
        await session.flush()
        session.add(binding)
        await session.flush()
        session.add(attempt)
        job.attempt_count = 1
        await session.flush()
    return job, binding


async def _replay_rebuild_admission(
    session: AsyncSession, binding: DemoJobBinding, *, request_digest: str
) -> DemoProfileRebuildAccepted:
    if binding.request_digest != request_digest:
        raise DemoMemoryConflict("idempotency key is bound to a different request")
    job = await session.get(Job, binding.job_id)
    _validate_rebuild_envelope(binding, job)
    assert job is not None
    return DemoProfileRebuildAccepted(job_id=job.id, request_id=job.request_id, replayed=True)


async def _lock_rebuild_execution(
    session: AsyncSession, demo_actor_id: str, job_id: str
) -> tuple[Job, DemoJobBinding]:
    job = cast(
        Job | None,
        await session.scalar(select(Job).where(Job.id == job_id).with_for_update()),
    )
    binding = cast(
        DemoJobBinding | None,
        await session.scalar(
            select(DemoJobBinding).where(DemoJobBinding.job_id == job_id).with_for_update()
        ),
    )
    if job is None or binding is None or binding.demo_actor_id != demo_actor_id:
        raise DemoMemoryUnavailable("profile rebuild Job authority is unavailable")
    _validate_rebuild_envelope(binding, job)
    actor = await _lock_active_actor(session, demo_actor_id)
    if actor.id != binding.target_id:
        raise DemoMemoryAuthorityCorruption("profile rebuild target authority is invalid")
    return job, binding


def _validate_rebuild_envelope(binding: DemoJobBinding, job: Job | None) -> None:
    payload = {
        "demo_actor_id": binding.demo_actor_id,
        "demo_session_id": binding.demo_session_id,
        "endpoint_operation": DEMO_PROFILE_REBUILD_OPERATION,
        "idempotency_key_hash": binding.idempotency_key_hash,
        "job_id": binding.job_id,
        "request_digest": binding.request_digest,
        "target_id": binding.target_id,
        "target_type": binding.target_type,
    }
    if (
        job is None
        or binding.demo_session_id is not None
        or binding.endpoint_operation != DEMO_PROFILE_REBUILD_OPERATION
        or binding.target_type != "DEMO_ACTOR"
        or binding.target_id != binding.demo_actor_id
        or binding.schema_version != DEMO_JOB_BINDING_SCHEMA
        or binding.canonical_payload != payload
        or binding.content_digest != _authority_digest(DEMO_JOB_BINDING_SCHEMA, payload)
        or job.id != binding.job_id
        or job.job_type != DEMO_PROFILE_REBUILD_JOB_TYPE
        or job.idempotency_key_hash
        != _formal_job_key_hash(
            binding.demo_actor_id, DEMO_PROFILE_REBUILD_OPERATION, binding.idempotency_key_hash
        )
        or job.payload != {}
        or job.owner_user_id is not None
        or job.ingestion_upload_intent_id is not None
        or job.result_asset_id is not None
        or job.status not in {"PENDING", "RUNNING", "COMPLETED", "REJECTED", "FAILED", "CANCELLED"}
    ):
        raise DemoMemoryAuthorityCorruption("profile rebuild Job envelope is invalid")
    assert job is not None
    if (
        job.lease_token is not None
        or job.lease_acquired_at is not None
        or job.lease_expires_at is not None
    ):
        raise DemoMemoryAuthorityCorruption("profile rebuild Job contains unsupported lease state")
    if job.status in {"PENDING", "RUNNING"}:
        if job.finalized_at is not None or job.result_code is not None:
            raise DemoMemoryAuthorityCorruption("active profile rebuild Job has terminal fields")
    elif job.finalized_at is None or job.result_code is None:
        raise DemoMemoryAuthorityCorruption("terminal profile rebuild Job lacks terminal fields")


def _validate_pending_rebuild_execution(binding: DemoJobBinding, job: Job) -> None:
    _validate_rebuild_envelope(binding, job)
    if (
        job.status != "PENDING"
        or job.attempt_count != 1
        or job.finalized_at is not None
        or job.result_code is not None
    ):
        raise DemoMemoryAuthorityCorruption("pending profile rebuild envelope is invalid")
    # The initial pending attempt is intentionally created at admission.  It is
    # transitioned in-place on the single legal PENDING -> RUNNING claim.


def _finish_execution_state(
    job: Job,
    attempt: JobAttempt,
    *,
    status: Literal["COMPLETED", "REJECTED", "FAILED"],
    result_code: str,
    error_code: str | None,
    audit_now: datetime,
) -> None:
    if job.status != "RUNNING" or attempt.status != "RUNNING":
        raise DemoMemoryAuthorityCorruption("D10 execution cannot finish from current state")
    attempt.status = status
    attempt.result_code = result_code
    attempt.error_code = error_code
    attempt.finished_at = audit_now
    job.status = status
    job.finalized_at = audit_now
    job.result_code = result_code
    job.updated_at = audit_now


def _finish_execution(
    job: Job,
    attempt: JobAttempt,
    *,
    result_code: str,
    audit_now: datetime,
) -> None:
    if job.status != "RUNNING" or attempt.status != "RUNNING":
        raise DemoMemoryAuthorityCorruption("D10 execution cannot finish from current state")
    attempt.status = "COMPLETED"
    attempt.result_code = result_code
    attempt.error_code = None
    attempt.finished_at = audit_now
    job.status = "COMPLETED"
    job.finalized_at = audit_now
    job.result_code = result_code
    job.updated_at = audit_now


async def _replay_profile(
    session: AsyncSession,
    binding: DemoJobBinding,
    *,
    request_digest: str,
) -> DemoAestheticProfileResult:
    job = await session.get(Job, binding.job_id)
    profile = await session.scalar(
        select(DemoAestheticProfile).where(DemoAestheticProfile.demo_job_binding_id == binding.id)
    )
    await _validate_completed_execution(
        session,
        binding=binding,
        job=job,
        request_digest=request_digest,
        operation=DEMO_PROFILE_REBUILD_OPERATION,
        expected_result_code="PROFILE_REBUILT",
    )
    if profile is None or profile.demo_actor_id != binding.demo_actor_id:
        raise DemoMemoryAuthorityCorruption("completed Profile rebuild has no Profile")
    return DemoAestheticProfileResult(
        job_id=cast(Job, job).id,
        aesthetic_profile_id=profile.id,
        generation=profile.generation,
        compilation_watermark=profile.compilation_watermark,
        profile_digest=profile.content_digest,
        replayed=True,
    )


async def _replay_context(
    session: AsyncSession,
    binding: DemoJobBinding,
    *,
    request_digest: str,
) -> DemoContextCompilationResult:
    job = await session.get(Job, binding.job_id)
    context = await session.scalar(
        select(DemoContextCompilation).where(
            DemoContextCompilation.demo_job_binding_id == binding.id
        )
    )
    await _validate_completed_execution(
        session,
        binding=binding,
        job=job,
        request_digest=request_digest,
        operation=DEMO_CONTEXT_COMPILE_OPERATION,
        expected_result_code="CONTEXT_COMPILED",
    )
    if (
        context is None
        or context.demo_actor_id != binding.demo_actor_id
        or context.demo_session_id != binding.demo_session_id
    ):
        raise DemoMemoryAuthorityCorruption("completed Context compilation has no Context")
    return DemoContextCompilationResult(
        job_id=cast(Job, job).id,
        context_compilation_id=context.id,
        aesthetic_profile_id=context.aesthetic_profile_id,
        compilation_watermark=context.compilation_watermark,
        context_digest=context.content_digest,
        expires_at=context.expires_at,
        replayed=True,
    )


async def _validate_completed_execution(
    session: AsyncSession,
    *,
    binding: DemoJobBinding,
    job: Job | None,
    request_digest: str,
    operation: str,
    expected_result_code: str,
) -> None:
    if binding.request_digest != request_digest:
        raise DemoMemoryConflict("idempotency key is bound to a different request")
    binding_payload = {
        "demo_actor_id": binding.demo_actor_id,
        "demo_session_id": binding.demo_session_id,
        "endpoint_operation": operation,
        "idempotency_key_hash": binding.idempotency_key_hash,
        "job_id": binding.job_id,
        "request_digest": binding.request_digest,
        "target_id": binding.target_id,
        "target_type": binding.target_type,
    }
    if (
        job is None
        or binding.endpoint_operation != operation
        or binding.schema_version != DEMO_JOB_BINDING_SCHEMA
        or binding.canonical_payload != binding_payload
        or binding.content_digest != _authority_digest(DEMO_JOB_BINDING_SCHEMA, binding_payload)
        or job.job_type != f"demo_p3_p7.{operation}"
        or job.idempotency_key_hash
        != _formal_job_key_hash(binding.demo_actor_id, operation, binding.idempotency_key_hash)
        or job.status != "COMPLETED"
        or job.attempt_count != 1
        or job.result_code != expected_result_code
        or job.finalized_at is None
        or job.payload != {}
        or job.owner_user_id is not None
        or job.ingestion_upload_intent_id is not None
        or job.result_asset_id is not None
    ):
        raise DemoMemoryAuthorityCorruption("D10 execution replay envelope is invalid")
    attempt = await session.scalar(
        select(JobAttempt).where(JobAttempt.job_id == job.id, JobAttempt.attempt == 1)
    )
    if (
        attempt is None
        or attempt.status != "COMPLETED"
        or attempt.result_code != expected_result_code
        or attempt.error_code is not None
        or attempt.finished_at is None
    ):
        raise DemoMemoryAuthorityCorruption("D10 execution replay attempt is invalid")


def _formal_job_key_hash(actor_id: str, operation: str, key_hash: str) -> str:
    preimage = f"mirror.demo/JobIdempotency/v1\n{actor_id}\n{operation}\n{key_hash}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _authority_digest(schema_version: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _normalize_explicit_time(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DemoMemoryInputError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _canonical_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoMemoryInputError(f"{name} must be a lowercase hexadecimal ID")


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DemoMemoryInputError(f"{name} must be a lowercase SHA-256 digest")


def _require_request_id(value: str) -> None:
    if not isinstance(value, str) or _REQUEST_ID.fullmatch(value) is None:
        raise DemoMemoryInputError("request_id must be 8-128 visible non-control characters")


def evidence_digests(entries: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    """Expose the canonical digest order for trace/UI adapters without raw evidence."""

    result: list[str] = []
    for entry in entries:
        digest = entry.get("digest")
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            raise DemoMemoryAuthorityCorruption("Context evidence entry digest is invalid")
        result.append(digest)
    return tuple(result)
