from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _insert_full_demo_graph,
    _insert_session,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)

from mirror_api.demo_memory_service import (
    CompileDemoContext,
    DemoMemoryConflict,
    DemoMemoryService,
    DemoMemoryUnavailable,
    RebuildDemoAestheticProfile,
)
from mirror_api.demo_models import (
    DemoAestheticProfile,
    DemoContextCompilation,
    DemoJobBinding,
    DemoPreferenceEvent,
)
from mirror_api.demo_preference_ledger import (
    AppendDemoPreferenceEvent,
    DemoPreferenceEventType,
    DemoPreferenceSourceType,
    DemoPreferenceTargetType,
    append_demo_preference_event,
)
from mirror_api.models import Job, JobAttempt

pytestmark = pytest.mark.integration

AS_OF = datetime(2026, 8, 23, 6, 0, tzinfo=UTC)


@pytest.fixture
def postgres_session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as db_session:
        _truncate_demo_authority(db_session)
        _truncate_formal_synthetic_fixture_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_authority(db_session)
        _truncate_formal_synthetic_fixture_authority(db_session)
    engine.dispose()


def _service() -> tuple[DemoMemoryService, async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return DemoMemoryService(session_factory=sessions), sessions, engine


def _rebuild(
    graph: dict[str, Any],
    *,
    key: str = "d10-profile-key-0001",
    reason: str = "USER_REQUEST",
) -> RebuildDemoAestheticProfile:
    return RebuildDemoAestheticProfile(
        demo_actor_id=graph["actor"].id,
        reason=reason,  # type: ignore[arg-type]
        idempotency_key=key,
        request_id=f"d10-profile-{key}",
    )


def _context(
    graph: dict[str, Any],
    profile_id: str,
    *,
    session_id: str | None = None,
    key: str = "d10-context-key-0001",
    as_of: datetime = AS_OF,
    instruction: str = "a" * 64,
) -> CompileDemoContext:
    return CompileDemoContext(
        demo_actor_id=graph["actor"].id,
        demo_session_id=session_id or graph["session"].id,
        aesthetic_profile_id=profile_id,
        current_instruction_digest=instruction,
        context_as_of_time=as_of,
        idempotency_key=key,
        request_id=f"d10-context-{key}",
    )


async def _append(
    sessions: async_sessionmaker[AsyncSession],
    graph: dict[str, Any],
    *,
    event_type: DemoPreferenceEventType,
    source_type: DemoPreferenceSourceType = DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
    demo_session_id: str | None = None,
    target_type: DemoPreferenceTargetType | None = None,
    target_id: str | None = None,
    signal: dict[str, Any] | None = None,
    occurred_at: datetime = AS_OF - timedelta(hours=1),
) -> DemoPreferenceEvent:
    async with sessions() as session:
        async with session.begin():
            result = await append_demo_preference_event(
                session,
                AppendDemoPreferenceEvent(
                    demo_actor_id=graph["actor"].id,
                    demo_session_id=demo_session_id,
                    event_type=event_type,
                    source_type=source_type,
                    target_type=target_type,
                    target_id=target_id,
                    signal=signal or {},
                    occurred_at=occurred_at,
                ),
            )
            return result.event


@pytest.mark.asyncio
async def test_profile_context_and_recall_are_exactly_replayable(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        profile = await service.rebuild_profile(_rebuild(graph))
        profile_replay = await service.rebuild_profile(_rebuild(graph))
        assert profile_replay == type(profile)(
            job_id=profile.job_id,
            aesthetic_profile_id=profile.aesthetic_profile_id,
            generation=profile.generation,
            compilation_watermark=profile.compilation_watermark,
            profile_digest=profile.profile_digest,
            replayed=True,
        )
        assert profile.generation == 2

        context = await service.compile_context(_context(graph, profile.aesthetic_profile_id))
        context_replay = await service.compile_context(
            _context(graph, profile.aesthetic_profile_id)
        )
        assert context_replay.context_compilation_id == context.context_compilation_id
        assert context_replay.context_digest == context.context_digest
        assert context_replay.replayed is True

        recalled = await service.recall_context(
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            recall_at=AS_OF + timedelta(minutes=1),
        )
        assert recalled.context_compilation_id == context.context_compilation_id
        assert recalled.context_digest == context.context_digest

        async with sessions() as session:
            stored_profile = await session.get(DemoAestheticProfile, profile.aesthetic_profile_id)
            stored_context = await session.get(
                DemoContextCompilation, context.context_compilation_id
            )
            assert stored_profile is not None
            assert stored_context is not None
            assert len(stored_profile.profile_payload["accepted_visual_episodes"]) == 1
            assert stored_context.current_instruction_digest == "a" * 64
            assert stored_context.trace_payload["current_instruction_priority"] == 1
            assert stored_context.selected_evidence[0]["kind"] == "CURRENT_SESSION_EVENT" or (
                stored_context.selected_evidence[0]["kind"] == "AESTHETIC_PROFILE"
            )
            jobs = (
                await session.scalars(
                    select(Job).where(Job.id.in_((profile.job_id, context.job_id)))
                )
            ).all()
            assert {(job.status, job.attempt_count) for job in jobs} == {("COMPLETED", 1)}
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(JobAttempt)
                    .where(JobAttempt.job_id.in_((profile.job_id, context.job_id)))
                )
                == 2
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_event_only_acceptance_is_traceable_but_not_visual_memory(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session, include_episode=False)
    service, sessions, engine = _service()
    try:
        first = await service.rebuild_profile(_rebuild(graph))
        async with sessions() as session:
            stored = await session.get(DemoAestheticProfile, first.aesthetic_profile_id)
            assert stored is not None
            assert stored.profile_payload["accepted_visual_episodes"] == []
            assert stored.profile_payload["excluded_feedback"] == [
                {
                    "digest": graph["accepted_event"].content_digest,
                    "reason": "FINAL_SAVE_REQUIRED",
                }
            ]

        new_event = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION,
            signal={"style_key": "editorial"},
        )
        second = await service.rebuild_profile(_rebuild(graph, key="d10-profile-key-0002"))
        assert second.generation == first.generation + 1
        assert second.compilation_watermark != first.compilation_watermark
        async with sessions() as session:
            stored = await session.get(DemoAestheticProfile, second.aesthetic_profile_id)
            assert stored is not None
            assert new_event.content_digest in stored.evidence_digests
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reset_and_rollback_rebuild_without_mutating_history(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        baseline = await service.rebuild_profile(_rebuild(graph))
        discarded = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION,
            signal={"style_key": "discarded"},
        )
        after_event = await service.rebuild_profile(_rebuild(graph, key="d10-profile-key-0002"))
        assert after_event.generation == baseline.generation + 1

        reset = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.RESET,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            target_type=DemoPreferenceTargetType.DEMO_ACTOR,
            target_id=graph["actor"].id,
            signal={"reset_watermark": graph["accepted_event"].event_sequence},
        )
        after_reset = await service.rebuild_profile(
            _rebuild(
                graph,
                key="d10-profile-key-0003",
                reason="RESET",
            )
        )
        with pytest.raises(DemoMemoryUnavailable, match="AestheticProfile"):
            await service.compile_context(
                _context(
                    graph,
                    after_event.aesthetic_profile_id,
                    key="d10-context-reset-stale",
                )
            )
        async with sessions() as session:
            stored = await session.get(DemoAestheticProfile, after_reset.aesthetic_profile_id)
            assert stored is not None
            assert stored.reset_epoch == 1
            assert discarded.content_digest not in stored.evidence_digests
            assert reset.content_digest in stored.evidence_digests

        rollback = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.ROLLBACK,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            target_type=DemoPreferenceTargetType.AESTHETIC_PROFILE,
            target_id=baseline.aesthetic_profile_id,
        )
        after_rollback = await service.rebuild_profile(
            _rebuild(
                graph,
                key="d10-profile-key-0004",
                reason="ROLLBACK",
            )
        )
        async with sessions() as session:
            stored = await session.get(DemoAestheticProfile, after_rollback.aesthetic_profile_id)
            event_count = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == graph["actor"].id)
            )
            assert stored is not None
            assert discarded.content_digest not in stored.evidence_digests
            assert reset.content_digest not in stored.evidence_digests
            assert rollback.content_digest in stored.evidence_digests
            assert event_count == 5
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reset_to_genesis_materializes_an_empty_rebuildable_profile(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        reset = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.RESET,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            target_type=DemoPreferenceTargetType.DEMO_ACTOR,
            target_id=graph["actor"].id,
            signal={"reset_watermark": 0},
        )
        rebuilt = await service.rebuild_profile(
            _rebuild(graph, key="d10-profile-genesis-reset", reason="RESET")
        )
        async with sessions() as session:
            stored = await session.get(DemoAestheticProfile, rebuilt.aesthetic_profile_id)
            assert stored is not None
            assert stored.reset_epoch == 1
            assert stored.profile_payload["desired_delta"] is None
            assert stored.profile_payload["style"] is None
            assert stored.profile_payload["reference_profile"] is None
            assert stored.profile_payload["accepted_visual_episodes"] == []
            assert stored.evidence_digests == [reset.content_digest]

        context = await service.compile_context(
            _context(
                graph,
                rebuilt.aesthetic_profile_id,
                key="d10-context-genesis-reset",
            )
        )
        assert context.aesthetic_profile_id == rebuilt.aesthetic_profile_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tombstone_and_delete_propagate_without_deleting_authority(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        profile = await service.rebuild_profile(_rebuild(graph))
        context = await service.compile_context(_context(graph, profile.aesthetic_profile_id))
        await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.DELETE,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            demo_session_id=graph["session"].id,
            target_type=DemoPreferenceTargetType.CONTEXT_COMPILATION,
            target_id=context.context_compilation_id,
        )
        with pytest.raises(DemoMemoryUnavailable, match="no active unexpired Context"):
            await service.recall_context(
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                recall_at=AS_OF + timedelta(minutes=1),
            )

        await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.TOMBSTONE,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            target_type=DemoPreferenceTargetType.AESTHETIC_PROFILE,
            target_id=profile.aesthetic_profile_id,
        )
        with pytest.raises(DemoMemoryUnavailable, match="AestheticProfile"):
            await service.compile_context(
                _context(
                    graph,
                    profile.aesthetic_profile_id,
                    key="d10-context-key-0002",
                    as_of=AS_OF + timedelta(minutes=2),
                )
            )
        async with sessions() as session:
            assert await session.get(DemoAestheticProfile, profile.aesthetic_profile_id)
            assert await session.get(DemoContextCompilation, context.context_compilation_id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_next_session_recall_excludes_previous_temporary_override(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    next_session = _insert_session(
        postgres_session,
        graph["actor"],
        config={"next_session": 1},
        expires_at=datetime(2026, 8, 24, 8, 0, tzinfo=UTC),
    )
    service, sessions, engine = _service()
    try:
        override = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.TEMPORARY_SESSION_OVERRIDE,
            demo_session_id=graph["session"].id,
            signal={"dimension_key": "jaw_width", "value_ppm": 1_000},
        )
        profile = await service.rebuild_profile(_rebuild(graph))
        async with sessions() as session:
            stored_profile = await session.get(DemoAestheticProfile, profile.aesthetic_profile_id)
            assert stored_profile is not None
            assert override.content_digest not in stored_profile.evidence_digests

        context = await service.compile_context(
            _context(
                graph,
                profile.aesthetic_profile_id,
                session_id=next_session.id,
                key="d10-context-next-session",
            )
        )
        async with sessions() as session:
            stored_context = await session.get(
                DemoContextCompilation, context.context_compilation_id
            )
            assert stored_context is not None
            assert override.content_digest not in {
                entry["digest"] for entry in stored_context.selected_evidence
            }
            assert {
                entry["reason"]
                for entry in stored_context.rejected_evidence
                if entry["digest"] == override.content_digest
            } == {"SESSION_SCOPE_MISMATCH"}
            assert stored_context.trace_payload["next_session_recall"] is True

        recalled = await service.recall_context(
            demo_actor_id=graph["actor"].id,
            demo_session_id=next_session.id,
            recall_at=AS_OF + timedelta(minutes=10),
        )
        assert recalled.context_compilation_id == context.context_compilation_id
        with pytest.raises(DemoMemoryUnavailable):
            await service.recall_context(
                demo_actor_id=graph["actor"].id,
                demo_session_id=next_session.id,
                recall_at=AS_OF + timedelta(minutes=31),
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_budget_is_fixed_and_overflow_is_traced(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        for index in range(10):
            await _append(
                sessions,
                graph,
                event_type=DemoPreferenceEventType.FEATURE_LOCKED,
                signal={"dimension_key": f"dimension_{index}"},
                occurred_at=AS_OF - timedelta(minutes=20) + timedelta(seconds=index),
            )
        profile = await service.rebuild_profile(_rebuild(graph))
        context = await service.compile_context(_context(graph, profile.aesthetic_profile_id))
        async with sessions() as session:
            stored = await session.get(DemoContextCompilation, context.context_compilation_id)
            assert stored is not None
            assert stored.budgets == {
                "accepted_visual_episodes": 4,
                "current_session_events": 8,
                "persistent_control_events": 8,
                "profile_core": 1,
                "total_selected_evidence": 21,
            }
            assert (
                sum(
                    entry["kind"] == "PERSISTENT_CONTROL_EVENT"
                    for entry in stored.selected_evidence
                )
                == 8
            )
            assert (
                sum(
                    entry["reason"] == "BUDGET_EXCEEDED"
                    and entry["kind"] == "PERSISTENT_CONTROL_EVENT"
                    for entry in stored.rejected_evidence
                )
                == 3
            )  # fixture source event plus ten new events
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_idempotency_collision_concurrency_and_failure_have_zero_partial_rows(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        first, second = await asyncio.gather(
            service.rebuild_profile(_rebuild(graph, key="d10-concurrent-key")),
            service.rebuild_profile(_rebuild(graph, key="d10-concurrent-key")),
        )
        assert first.aesthetic_profile_id == second.aesthetic_profile_id
        assert {first.replayed, second.replayed} == {False, True}

        with pytest.raises(DemoMemoryConflict, match="another key"):
            await service.rebuild_profile(_rebuild(graph, key="d10-same-input-different-key"))

        with pytest.raises(DemoMemoryConflict, match="different request"):
            await service.rebuild_profile(
                _rebuild(
                    graph,
                    key="d10-concurrent-key",
                    reason="RESET",
                )
            )

        async with sessions() as session:
            jobs_before = await session.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.job_type == "demo_p3_p7.context.compile")
            )
            bindings_before = await session.scalar(
                select(func.count())
                .select_from(DemoJobBinding)
                .where(DemoJobBinding.endpoint_operation == "context.compile")
            )
            contexts_before = await session.scalar(
                select(func.count()).select_from(DemoContextCompilation)
            )
        with pytest.raises(DemoMemoryUnavailable, match="AestheticProfile"):
            await service.compile_context(_context(graph, "f" * 32))
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(Job.job_type == "demo_p3_p7.context.compile")
                )
                == jobs_before
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoJobBinding)
                    .where(DemoJobBinding.endpoint_operation == "context.compile")
                )
                == bindings_before
            )
            assert (
                await session.scalar(select(func.count()).select_from(DemoContextCompilation))
                == contexts_before
            )
    finally:
        await engine.dispose()
