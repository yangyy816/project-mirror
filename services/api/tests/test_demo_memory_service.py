from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _insert_demo_row,
    _insert_full_demo_graph,
    _insert_session,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)
from test_demo_schema_authority_invariants import (
    _insert_preference_event as _insert_preference_event_authority,
)

from mirror_api.demo_context_queue_service import (
    CreateDemoContextCompilation,
    DemoContextCompilationAccepted,
    DemoContextQueueConflict,
    DemoContextQueueService,
    DemoContextQueueUnavailable,
    DemoContextReconciliationCandidate,
)
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_memory_service import (
    CompileDemoContext,
    DemoAestheticProfileResult,
    DemoMemoryConflict,
    DemoMemoryReconciliationCandidate,
    DemoMemoryService,
    DemoMemoryUnavailable,
    RebuildDemoAestheticProfile,
)
from mirror_api.demo_models import (
    DemoActor,
    DemoAestheticProfile,
    DemoContextCompilation,
    DemoContextCompileRequest,
    DemoContextCompileResult,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoReferenceProfile,
    DemoSession,
)
from mirror_api.demo_preference_ledger import (
    AppendDemoPreferenceEvent,
    DemoPreferenceEventType,
    DemoPreferenceSourceType,
    DemoPreferenceTargetType,
    append_demo_preference_event,
    preference_event_content_digest,
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


def _service(
    *, post_write_probe: Callable[[Literal["PROFILE", "CONTEXT"]], None] | None = None
) -> tuple[DemoMemoryService, async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return (
        DemoMemoryService(
            session_factory=sessions,
            post_write_probe=post_write_probe,
        ),
        sessions,
        engine,
    )


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


async def _rebuild_execute(
    service: DemoMemoryService, command: RebuildDemoAestheticProfile
) -> DemoAestheticProfileResult:
    accepted = await service.admit_rebuild(command)
    return await service.execute_rebuild(
        demo_actor_id=command.demo_actor_id,
        job_id=accepted.job_id,
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


def _queued_context(
    graph: dict[str, Any],
    profile_id: str,
    *,
    key: str = "d10-context-queue-key-0001",
    as_of: datetime = AS_OF,
    instruction: str = "a" * 64,
) -> CreateDemoContextCompilation:
    return CreateDemoContextCompilation(
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        aesthetic_profile_id=profile_id,
        current_instruction_digest=instruction,
        context_as_of_time=as_of,
        idempotency_key=key,
        request_id=f"d10-context-queue-{key}",
    )


def _context_queue(
    sessions: async_sessionmaker[AsyncSession],
    *,
    now: datetime = AS_OF + timedelta(minutes=5),
) -> DemoContextQueueService:
    return DemoContextQueueService(session_factory=sessions, now=lambda: now)


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


async def _terminalize_context_owner(
    sessions: async_sessionmaker[AsyncSession],
    authority_session: Session,
    graph: dict[str, Any],
    *,
    state: Literal["ACTOR_TOMBSTONED", "SESSION_CLOSED", "SESSION_TOMBSTONED"],
    occurred_at: datetime,
) -> None:
    if state == "ACTOR_TOMBSTONED":
        async with sessions() as session:
            async with session.begin():
                await append_demo_preference_event(
                    session,
                    AppendDemoPreferenceEvent(
                        demo_actor_id=graph["actor"].id,
                        demo_session_id=None,
                        event_type=DemoPreferenceEventType.ACTOR_TOMBSTONED,
                        source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
                        target_type=DemoPreferenceTargetType.DEMO_ACTOR,
                        target_id=graph["actor"].id,
                        signal={},
                        occurred_at=occurred_at,
                    ),
                )
                await session.execute(
                    update(DemoActor)
                    .where(DemoActor.id == graph["actor"].id)
                    .values(tombstoned_at=occurred_at)
                )
        return

    async with sessions() as session:
        async with session.begin():
            await append_demo_preference_event(
                session,
                AppendDemoPreferenceEvent(
                    demo_actor_id=graph["actor"].id,
                    demo_session_id=graph["session"].id,
                    event_type=DemoPreferenceEventType.SESSION_CLOSED,
                    source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
                    target_type=None,
                    target_id=None,
                    signal={},
                    occurred_at=occurred_at,
                ),
            )
            await session.execute(
                update(DemoSession)
                .where(DemoSession.id == graph["session"].id)
                .values(closed_at=occurred_at)
            )
    if state == "SESSION_CLOSED":
        return

    tombstoned_at = occurred_at + timedelta(minutes=1)
    authority_session.rollback()
    actor = authority_session.get(DemoActor, graph["actor"].id)
    demo_session = authority_session.get(DemoSession, graph["session"].id)
    tail = authority_session.scalar(
        select(DemoPreferenceEvent)
        .where(DemoPreferenceEvent.demo_actor_id == graph["actor"].id)
        .order_by(DemoPreferenceEvent.event_sequence.desc())
        .limit(1)
    )
    assert actor is not None and demo_session is not None and tail is not None
    _insert_preference_event_authority(
        authority_session,
        actor,
        sequence=tail.event_sequence + 1,
        previous_digest=tail.content_digest,
        signal={
            "authority_id": demo_session.id,
            "authority_type": "DEMO_SESSION",
        },
        demo_session=demo_session,
        event_type="TOMBSTONE",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=tombstoned_at,
        commit=False,
    )
    authority_session.execute(
        update(DemoSession)
        .where(DemoSession.id == demo_session.id)
        .values(tombstoned_at=tombstoned_at)
    )
    authority_session.commit()


def _insert_valid_reference(session: Session, graph: dict[str, Any]) -> DemoReferenceProfile:
    return _insert_demo_row(
        session,
        DemoReferenceProfile,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=graph["desired_delta"].id,
        style_profile_id=graph["style"].id,
        identity_constraints_id=None,
        version=2,
        source_assets=[
            {
                "asset_id": graph["image1_asset"].id,
                "sha256": graph["image1_asset"].sha256,
                "view": "FRONT",
            }
        ],
        analysis_version="fixture-d10-reference-v1",
        compiler_version="fixture-d10-reference-compiler-v1",
        structured_profile={
            "dimensions": {"jaw_width": {"evidence_kind": "ACCEPTED_SELF_TRANSFER"}},
            "identity_constraints_digest": None,
            "identity_reference_frame": "SELF_STATE_ANCHORED",
            "profile_schema_version": "mirror.demo/DemoReferenceStructure/v1",
            "source_views": [
                {
                    "asset_id": graph["image1_asset"].id,
                    "image_version_digest": graph["image1"].content_digest,
                    "self_transfer_run_digest": graph["transfer_result"].content_digest,
                    "sha256": graph["image1_asset"].sha256,
                    "verifier_digest": graph["verification"].content_digest,
                    "view": "FRONT",
                }
            ],
            "style_profile_digest": graph["style"].content_digest,
        },
        evidence_digests=sorted(
            {
                graph["desired_delta"].content_digest,
                graph["style"].content_digest,
                graph["image1"].content_digest,
                graph["transfer_result"].content_digest,
                graph["verification"].content_digest,
            }
        ),
    )


@pytest.mark.asyncio
async def test_profile_context_and_recall_are_exactly_replayable(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(service, _rebuild(graph))
        profile_replay = await _rebuild_execute(service, _rebuild(graph))
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
async def test_context_queue_admission_execution_and_terminal_replay_are_atomic(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        queue = _context_queue(sessions)
        command = _queued_context(graph, profile.aesthetic_profile_id)

        admitted = await queue.admit(command)
        replay = await queue.admit(command)
        assert replay == DemoContextCompilationAccepted(
            admitted.job_id,
            admitted.context_request_id,
            admitted.request_id,
            True,
        )
        with pytest.raises(
            DemoContextQueueConflict,
            match="key is bound to another request",
        ):
            await queue.admit(
                _queued_context(
                    graph,
                    profile.aesthetic_profile_id,
                    key=command.idempotency_key,
                    instruction="f" * 64,
                )
            )

        assert await queue.reconciliation_candidates() == (
            DemoContextReconciliationCandidate(
                command.demo_actor_id,
                admitted.job_id,
                admitted.context_request_id,
                admitted.request_id,
            ),
        )
        snapshot = await DemoJobService(session_factory=sessions).get(
            demo_actor_id=command.demo_actor_id,
            job_id=admitted.job_id,
        )
        assert snapshot.capability == "P7_CONTEXT_COMPILER"
        assert (
            snapshot.target.target_type,
            snapshot.target.target_id,
        ) == ("DEMO_SESSION", command.demo_session_id)

        async with sessions() as session:
            job = await session.get(Job, admitted.job_id)
            request = await session.get(DemoContextCompileRequest, admitted.context_request_id)
            assert job is not None and (job.status, job.attempt_count, job.payload) == (
                "PENDING",
                0,
                {},
            )
            assert request is not None and request.demo_actor_id == graph["actor"].id
            assert set(request.canonical_payload) == {
                "aesthetic_profile_digest",
                "aesthetic_profile_id",
                "budgets",
                "compilation_watermark",
                "compiler_version",
                "context_as_of_time",
                "current_instruction_digest",
                "demo_actor_id",
                "demo_job_binding_id",
                "demo_session_id",
                "execution_policy_version",
                "expires_at",
                "input_digest",
                "lease_timeout_seconds",
                "max_attempts",
                "rejected_evidence",
                "selected_evidence",
                "trace_payload",
            }
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompilation)
                    .where(
                        DemoContextCompilation.demo_job_binding_id == request.demo_job_binding_id
                    )
                )
                == 0
            )

        completed = await queue.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        terminal_replay = await queue.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        assert completed.status == "COMPLETED"
        assert completed.context_compilation_id is not None
        assert terminal_replay == type(completed)(
            completed.demo_actor_id,
            completed.job_id,
            completed.context_request_id,
            completed.status,
            completed.result_code,
            completed.context_compilation_id,
            completed.context_digest,
            True,
        )
        assert await queue.reconciliation_candidates() == ()

        async with sessions() as session:
            job = await session.get(Job, admitted.job_id)
            result = await session.scalar(
                select(DemoContextCompileResult).where(
                    DemoContextCompileResult.compile_request_id == admitted.context_request_id
                )
            )
            assert job is not None and (job.status, job.attempt_count, job.result_code) == (
                "COMPLETED",
                1,
                "CONTEXT_COMPILED",
            )
            assert result is not None
            assert result.context_compilation_id == completed.context_compilation_id
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(JobAttempt)
                    .where(JobAttempt.job_id == admitted.job_id)
                )
                == 1
            )
        async with sessions() as session:
            with pytest.raises(DBAPIError):
                async with session.begin():
                    await session.execute(
                        update(DemoContextCompileRequest)
                        .where(DemoContextCompileRequest.id == admitted.context_request_id)
                        .values(content_digest="0" * 64)
                    )
        async with sessions() as session:
            with pytest.raises(DBAPIError):
                async with session.begin():
                    await session.execute(
                        delete(DemoContextCompileResult).where(
                            DemoContextCompileResult.compile_request_id
                            == admitted.context_request_id
                        )
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_state",
    ["ACTOR_TOMBSTONED", "SESSION_CLOSED", "SESSION_TOMBSTONED"],
)
async def test_context_queue_finalize_rechecks_current_actor_and_session_lifecycle(
    postgres_session: Session,
    terminal_state: Literal["ACTOR_TOMBSTONED", "SESSION_CLOSED", "SESSION_TOMBSTONED"],
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        clock = [AS_OF + timedelta(minutes=5)]
        queue = DemoContextQueueService(session_factory=sessions, now=lambda: clock[0])
        admitted = await queue.admit(
            _queued_context(
                graph,
                profile.aesthetic_profile_id,
                key=f"d10-context-lifecycle-{terminal_state.lower()}",
                instruction="7" * 64,
            )
        )
        await _terminalize_context_owner(
            sessions,
            postgres_session,
            graph,
            state=terminal_state,
            occurred_at=AS_OF + timedelta(minutes=10),
        )
        clock[0] = AS_OF + timedelta(minutes=20)

        rejected = await queue.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        assert (rejected.status, rejected.result_code) == ("REJECTED", "CONTEXT_REJECTED")
        async with sessions() as session:
            request = await session.get(DemoContextCompileRequest, admitted.context_request_id)
            job = await session.get(Job, admitted.job_id)
            assert request is not None
            assert job is not None and (job.status, job.result_code) == (
                "REJECTED",
                "CONTEXT_REJECTED",
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompilation)
                    .where(
                        DemoContextCompilation.demo_job_binding_id == request.demo_job_binding_id
                    )
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompileResult)
                    .where(
                        DemoContextCompileResult.compile_request_id == admitted.context_request_id
                    )
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_queue_finalize_and_actor_tombstone_have_one_consistent_winner(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        clock = [AS_OF + timedelta(minutes=5)]
        queue = DemoContextQueueService(session_factory=sessions, now=lambda: clock[0])
        admitted = await queue.admit(
            _queued_context(
                graph,
                profile.aesthetic_profile_id,
                key="d10-context-lifecycle-race",
                instruction="5" * 64,
            )
        )
        clock[0] = AS_OF + timedelta(minutes=20)

        executed, _ = await asyncio.gather(
            queue.execute_task(
                demo_actor_id=graph["actor"].id,
                job_id=admitted.job_id,
                context_request_id=admitted.context_request_id,
            ),
            _terminalize_context_owner(
                sessions,
                postgres_session,
                graph,
                state="ACTOR_TOMBSTONED",
                occurred_at=AS_OF + timedelta(minutes=10),
            ),
        )
        assert executed.status in {"COMPLETED", "REJECTED"}

        async with sessions() as session:
            actor = await session.get(DemoActor, graph["actor"].id)
            request = await session.get(DemoContextCompileRequest, admitted.context_request_id)
            job = await session.get(Job, admitted.job_id)
            assert actor is not None and actor.tombstoned_at is not None
            assert request is not None and job is not None
            context_count = await session.scalar(
                select(func.count())
                .select_from(DemoContextCompilation)
                .where(DemoContextCompilation.demo_job_binding_id == request.demo_job_binding_id)
            )
            result_count = await session.scalar(
                select(func.count())
                .select_from(DemoContextCompileResult)
                .where(DemoContextCompileResult.compile_request_id == admitted.context_request_id)
            )
            if executed.status == "COMPLETED":
                assert (job.status, context_count, result_count) == ("COMPLETED", 1, 1)
            else:
                assert (job.status, job.result_code, context_count, result_count) == (
                    "REJECTED",
                    "CONTEXT_REJECTED",
                    0,
                    0,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ["ACTOR_TOMBSTONED", "SESSION_EXPIRED"])
async def test_context_queue_admission_requires_current_actor_and_session(
    postgres_session: Session,
    terminal_state: Literal["ACTOR_TOMBSTONED", "SESSION_EXPIRED"],
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        if terminal_state == "ACTOR_TOMBSTONED":
            await _terminalize_context_owner(
                sessions,
                postgres_session,
                graph,
                state="ACTOR_TOMBSTONED",
                occurred_at=AS_OF + timedelta(minutes=10),
            )
            audit_now = AS_OF + timedelta(minutes=20)
        else:
            audit_now = graph["session"].expires_at + timedelta(minutes=1)
        queue = _context_queue(sessions, now=audit_now)

        with pytest.raises(DemoContextQueueUnavailable, match="unavailable"):
            await queue.admit(
                _queued_context(
                    graph,
                    profile.aesthetic_profile_id,
                    key=f"d10-context-admission-{terminal_state.lower()}",
                    instruction="6" * 64,
                )
            )
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompileRequest)
                    .where(DemoContextCompileRequest.demo_actor_id == graph["actor"].id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(
                        Job.job_type == "demo_p3_p7.context.compile",
                        Job.request_id
                        == f"d10-context-queue-d10-context-admission-{terminal_state.lower()}",
                    )
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_queue_populated_downgrade_fails_closed(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        queue = _context_queue(sessions)
        admitted = await queue.admit(
            _queued_context(
                graph,
                profile.aesthetic_profile_id,
                key="d10-context-populated-downgrade",
                instruction="9" * 64,
            )
        )
        await engine.dispose()

        root = Path(__file__).resolve().parents[3]
        config = Config(root / "services" / "api" / "alembic.ini")
        config.set_main_option(
            "script_location",
            str(root / "services" / "api" / "migrations"),
        )
        with pytest.raises(DBAPIError, match="D10 queued Context authority exists"):
            await asyncio.to_thread(
                command.downgrade,
                config,
                "demo_0016_d06_ref_profile_queue",
            )

        sync_engine = create_engine(os.environ["TEST_DATABASE_URL"])
        try:
            with sync_engine.connect() as connection:
                assert (
                    connection.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    ).scalar_one()
                    == "demo_0017_d10_context_queue"
                )
                assert (
                    connection.exec_driver_sql(
                        "SELECT count(*) FROM demo_context_compile_requests WHERE id = %s",
                        (admitted.context_request_id,),
                    ).scalar_one()
                    == 1
                )
        finally:
            sync_engine.dispose()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_queue_pending_cancel_wins_without_partial_context(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        queue = _context_queue(sessions)
        admitted = await queue.admit(
            _queued_context(
                graph,
                profile.aesthetic_profile_id,
                key="d10-context-cancel-pending",
                instruction="c" * 64,
            )
        )
        cancelled = await DemoJobService(session_factory=sessions).cancel(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            expected_status="PENDING",
            reason="USER_REQUEST",
            idempotency_key="d10-context-cancel-command",
        )
        executed = await queue.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        assert cancelled.status == "CANCELLED"
        assert executed.status == "CANCELLED" and executed.replayed is True

        async with sessions() as session:
            request = await session.get(DemoContextCompileRequest, admitted.context_request_id)
            assert request is not None
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompilation)
                    .where(
                        DemoContextCompilation.demo_job_binding_id == request.demo_job_binding_id
                    )
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompileResult)
                    .where(
                        DemoContextCompileResult.compile_request_id == admitted.context_request_id
                    )
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_queue_rejects_stale_frozen_snapshot_without_partial_result(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        queue = _context_queue(sessions)
        admitted = await queue.admit(
            _queued_context(
                graph,
                profile.aesthetic_profile_id,
                key="d10-context-stale-snapshot",
                instruction="d" * 64,
            )
        )
        await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.RESET,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            target_type=DemoPreferenceTargetType.DEMO_ACTOR,
            target_id=graph["actor"].id,
            signal={"reset_watermark": graph["accepted_event"].event_sequence},
        )

        rejected = await queue.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        assert (rejected.status, rejected.result_code) == ("REJECTED", "CONTEXT_REJECTED")
        async with sessions() as session:
            request = await session.get(DemoContextCompileRequest, admitted.context_request_id)
            job = await session.get(Job, admitted.job_id)
            assert request is not None
            assert job is not None and (job.status, job.result_code) == (
                "REJECTED",
                "CONTEXT_REJECTED",
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompilation)
                    .where(
                        DemoContextCompilation.demo_job_binding_id == request.demo_job_binding_id
                    )
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompileResult)
                    .where(
                        DemoContextCompileResult.compile_request_id == admitted.context_request_id
                    )
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_queue_cross_path_collision_rejects_without_stranding_running_job(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        queue = _context_queue(sessions)
        queued = await queue.admit(
            _queued_context(
                graph,
                profile.aesthetic_profile_id,
                key="d10-context-cross-path-queued",
                instruction="8" * 64,
            )
        )
        direct = await memory.compile_context(
            _context(
                graph,
                profile.aesthetic_profile_id,
                key="d10-context-cross-path-direct",
                instruction="8" * 64,
            )
        )
        rejected = await queue.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=queued.job_id,
            context_request_id=queued.context_request_id,
        )
        assert direct.context_compilation_id is not None
        assert (rejected.status, rejected.result_code) == ("REJECTED", "CONTEXT_REJECTED")

        async with sessions() as session:
            job = await session.get(Job, queued.job_id)
            result_count = await session.scalar(
                select(func.count())
                .select_from(DemoContextCompileResult)
                .where(DemoContextCompileResult.compile_request_id == queued.context_request_id)
            )
            assert job is not None and (job.status, job.result_code) == (
                "REJECTED",
                "CONTEXT_REJECTED",
            )
            assert result_count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_queue_expired_leases_exhaust_exactly_three_attempts(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        clock = [AS_OF + timedelta(hours=1)]
        queue = DemoContextQueueService(session_factory=sessions, now=lambda: clock[0])
        admitted = await queue.admit(
            _queued_context(
                graph,
                profile.aesthetic_profile_id,
                key="d10-context-lease-exhaustion",
                instruction="e" * 64,
            )
        )

        first = await queue.reserve(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        active = await queue.reserve(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        assert (first.state, first.attempt) == ("RESERVED", 1)
        assert active.state == "ACTIVE"

        for expected_attempt in (2, 3):
            clock[0] += timedelta(seconds=301)
            retried = await queue.reserve(
                demo_actor_id=graph["actor"].id,
                job_id=admitted.job_id,
                context_request_id=admitted.context_request_id,
            )
            assert (retried.state, retried.attempt) == ("RESERVED", expected_attempt)
        clock[0] += timedelta(seconds=301)
        exhausted = await queue.reserve(
            demo_actor_id=graph["actor"].id,
            job_id=admitted.job_id,
            context_request_id=admitted.context_request_id,
        )
        assert (exhausted.state, exhausted.terminal_status) == ("TERMINAL", "FAILED")

        async with sessions() as session:
            job = await session.get(Job, admitted.job_id)
            attempts = list(
                (
                    await session.scalars(
                        select(JobAttempt)
                        .where(JobAttempt.job_id == admitted.job_id)
                        .order_by(JobAttempt.attempt)
                    )
                ).all()
            )
            assert job is not None and (job.status, job.attempt_count, job.result_code) == (
                "FAILED",
                3,
                "CONTEXT_MAX_ATTEMPTS",
            )
            assert [(item.attempt, item.status, item.error_code) for item in attempts] == [
                (1, "FAILED", "LEASE_EXPIRED"),
                (2, "FAILED", "LEASE_EXPIRED"),
                (3, "FAILED", "LEASE_EXPIRED"),
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_queue_same_input_different_keys_has_one_admission_winner(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    memory, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(memory, _rebuild(graph))
        queue = _context_queue(sessions)
        results = await asyncio.gather(
            queue.admit(
                _queued_context(
                    graph,
                    profile.aesthetic_profile_id,
                    key="d10-context-input-winner-a",
                    instruction="b" * 64,
                )
            ),
            queue.admit(
                _queued_context(
                    graph,
                    profile.aesthetic_profile_id,
                    key="d10-context-input-winner-b",
                    instruction="b" * 64,
                )
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(item, DemoContextCompilationAccepted) for item in results) == 1
        assert sum(isinstance(item, DemoContextQueueConflict) for item in results) == 1

        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoContextCompileRequest)
                    .where(DemoContextCompileRequest.demo_actor_id == graph["actor"].id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoJobBinding)
                    .join(
                        DemoContextCompileRequest,
                        DemoContextCompileRequest.demo_job_binding_id == DemoJobBinding.id,
                    )
                    .where(
                        DemoJobBinding.demo_actor_id == graph["actor"].id,
                        DemoJobBinding.endpoint_operation == "context.compile",
                    )
                )
                == 1
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rebuild_admission_is_pending_before_owner_bound_execution(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        async with sessions() as session:
            profile_count_before = await session.scalar(
                select(func.count()).select_from(DemoAestheticProfile)
            )
        assert isinstance(profile_count_before, int)
        command = _rebuild(graph)
        admitted = await service.admit_rebuild(command)
        replay = await service.admit_rebuild(command)
        assert replay == type(admitted)(
            job_id=admitted.job_id,
            request_id=admitted.request_id,
            replayed=True,
        )
        async with sessions() as session:
            job = await session.get(Job, admitted.job_id)
            profiles = list((await session.scalars(select(DemoAestheticProfile))).all())
            attempts = list(
                (
                    await session.scalars(
                        select(JobAttempt).where(JobAttempt.job_id == admitted.job_id)
                    )
                ).all()
            )
        assert job is not None and (job.status, job.attempt_count, job.result_code) == (
            "PENDING",
            1,
            None,
        )
        assert [(attempt.attempt, attempt.status) for attempt in attempts] == [(1, "PENDING")]
        assert len(profiles) == profile_count_before
        assert await service.reconciliation_candidates() == (
            DemoMemoryReconciliationCandidate(
                demo_actor_id=command.demo_actor_id,
                job_id=admitted.job_id,
                request_id=admitted.request_id,
            ),
        )
        completed = await service.execute_rebuild(
            demo_actor_id=command.demo_actor_id,
            job_id=admitted.job_id,
        )
        assert completed.replayed is False
        assert await service.reconciliation_candidates() == ()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pending_rebuild_attempt_cancels_atomically_before_execution(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        command = _rebuild(graph, key="d10-cancel-pending-rebuild")
        admitted = await service.admit_rebuild(command)
        cancelled = await DemoJobService(session_factory=sessions).cancel(
            demo_actor_id=command.demo_actor_id,
            job_id=admitted.job_id,
            expected_status="PENDING",
            reason="USER_REQUEST",
            idempotency_key="d10-cancel-command-key",
        )

        assert cancelled.status == "CANCELLED"
        assert cancelled.result_code == "USER_REQUEST"
        async with sessions() as session:
            attempt = await session.scalar(
                select(JobAttempt).where(JobAttempt.job_id == admitted.job_id)
            )
            assert attempt is not None
            assert attempt.status == "CANCELLED"
            assert attempt.result_code == "USER_REQUEST"
            assert attempt.finished_at == cancelled.finalized_at
        assert await service.reconciliation_candidates() == ()
        with pytest.raises(DemoMemoryUnavailable, match="fresh durable execution"):
            await service.execute_rebuild(
                demo_actor_id=command.demo_actor_id,
                job_id=admitted.job_id,
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
        first = await _rebuild_execute(service, _rebuild(graph))
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
        second = await _rebuild_execute(service, _rebuild(graph, key="d10-profile-key-0002"))
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
        baseline = await _rebuild_execute(service, _rebuild(graph))
        discarded = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION,
            signal={"style_key": "discarded"},
        )
        after_event = await _rebuild_execute(service, _rebuild(graph, key="d10-profile-key-0002"))
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
        after_reset = await _rebuild_execute(
            service,
            _rebuild(
                graph,
                key="d10-profile-key-0003",
                reason="RESET",
            ),
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
        after_rollback = await _rebuild_execute(
            service,
            _rebuild(
                graph,
                key="d10-profile-key-0004",
                reason="ROLLBACK",
            ),
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
@pytest.mark.parametrize(
    "lifecycle_type",
    [DemoPreferenceEventType.RESET, DemoPreferenceEventType.ROLLBACK],
)
async def test_recall_rejects_context_with_lifecycle_stale_session_evidence(
    postgres_session: Session,
    lifecycle_type: DemoPreferenceEventType,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(service, _rebuild(graph))
        override = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.TEMPORARY_SESSION_OVERRIDE,
            demo_session_id=graph["session"].id,
            signal={"dimension_key": "jaw_width", "value_ppm": 1_000},
        )
        context = await service.compile_context(_context(graph, profile.aesthetic_profile_id))
        async with sessions() as session:
            stored = await session.get(DemoContextCompilation, context.context_compilation_id)
            assert stored is not None
            assert override.content_digest in {
                entry["digest"] for entry in stored.selected_evidence
            }
        assert (
            await service.recall_context(
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                recall_at=AS_OF + timedelta(minutes=1),
            )
        ).context_compilation_id == context.context_compilation_id

        await _append(
            sessions,
            graph,
            event_type=lifecycle_type,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            target_type=(
                DemoPreferenceTargetType.DEMO_ACTOR
                if lifecycle_type is DemoPreferenceEventType.RESET
                else DemoPreferenceTargetType.AESTHETIC_PROFILE
            ),
            target_id=(
                graph["actor"].id
                if lifecycle_type is DemoPreferenceEventType.RESET
                else profile.aesthetic_profile_id
            ),
            signal=(
                {"reset_watermark": graph["accepted_event"].event_sequence}
                if lifecycle_type is DemoPreferenceEventType.RESET
                else {}
            ),
        )
        with pytest.raises(DemoMemoryUnavailable, match="no active unexpired Context"):
            await service.recall_context(
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                recall_at=AS_OF + timedelta(minutes=2),
            )
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
        rebuilt = await _rebuild_execute(
            service, _rebuild(graph, key="d10-profile-genesis-reset", reason="RESET")
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
        profile = await _rebuild_execute(service, _rebuild(graph))
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
@pytest.mark.parametrize(
    ("target_type", "target_key"),
    [
        (DemoPreferenceTargetType.STYLE_PROFILE, "style"),
        (DemoPreferenceTargetType.IMAGE_VERSION, "image1"),
    ],
)
async def test_reference_dependencies_invalidate_profiles_contexts_and_new_rebuilds(
    postgres_session: Session,
    target_type: DemoPreferenceTargetType,
    target_key: str,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    reference = _insert_valid_reference(postgres_session, graph)
    service, sessions, engine = _service()
    try:
        profile = await _rebuild_execute(service, _rebuild(graph))
        context = await service.compile_context(_context(graph, profile.aesthetic_profile_id))
        async with sessions() as session:
            stored = await session.get(DemoAestheticProfile, profile.aesthetic_profile_id)
            assert stored is not None
            assert stored.profile_payload["reference_profile"]["id"] == reference.id

        await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.DELETE,
            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
            target_type=target_type,
            target_id=graph[target_key].id,
        )
        with pytest.raises(DemoMemoryUnavailable, match="no active unexpired Context"):
            await service.recall_context(
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                recall_at=AS_OF + timedelta(minutes=1),
            )

        rebuilt = await _rebuild_execute(
            service,
            _rebuild(
                graph,
                key=f"d10-reference-invalidation-{target_key}",
                reason="TOMBSTONE_PROPAGATION",
            ),
        )
        async with sessions() as session:
            stored = await session.get(DemoAestheticProfile, rebuilt.aesthetic_profile_id)
            assert stored is not None
            assert stored.profile_payload["reference_profile"] is None
            assert await session.get(DemoReferenceProfile, reference.id) is not None
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
        profile = await _rebuild_execute(service, _rebuild(graph))
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
        profile = await _rebuild_execute(service, _rebuild(graph))
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
async def test_context_selected_evidence_uses_frozen_event_sequence_order(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    occurred_at = AS_OF - timedelta(minutes=20)
    try:
        first = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.FEATURE_LOCKED,
            signal={"dimension_key": "ordering_first"},
            occurred_at=occurred_at,
        )
        second_signal: dict[str, Any] | None = None
        second_digest: str | None = None
        for candidate in range(1_000):
            signal = {"dimension_key": f"ordering_second_{candidate}"}
            payload = {
                "demo_actor_id": graph["actor"].id,
                "demo_session_id": None,
                "event_sequence": first.event_sequence + 1,
                "event_type": DemoPreferenceEventType.FEATURE_LOCKED.value,
                "occurred_at": occurred_at.isoformat(timespec="microseconds").replace(
                    "+00:00", "Z"
                ),
                "previous_event_digest": first.content_digest,
                "signal": signal,
                "source_type": DemoPreferenceSourceType.EXPLICIT_USER_ACTION.value,
                "target_id": None,
                "target_type": None,
            }
            candidate_digest = preference_event_content_digest(payload)
            if candidate_digest < first.content_digest:
                second_signal = signal
                second_digest = candidate_digest
                break
        assert second_signal is not None
        assert second_digest is not None
        second = await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.FEATURE_LOCKED,
            signal=second_signal,
            occurred_at=occurred_at,
        )
        assert second.content_digest == second_digest
        assert second.content_digest < first.content_digest

        profile = await _rebuild_execute(service, _rebuild(graph))
        context = await service.compile_context(_context(graph, profile.aesthetic_profile_id))
        async with sessions() as session:
            stored = await session.get(DemoContextCompilation, context.context_compilation_id)
            assert stored is not None
            ordered_pair = [
                entry
                for entry in stored.selected_evidence
                if entry["digest"] in {first.content_digest, second.content_digest}
            ]
            assert [entry["event_sequence"] for entry in ordered_pair] == [
                first.event_sequence,
                second.event_sequence,
            ]
            assert [entry["digest"] for entry in ordered_pair] != sorted(
                [entry["digest"] for entry in ordered_pair]
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_idempotency_concurrency_and_failures_preserve_recoverable_authority(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, sessions, engine = _service()
    try:
        first, second = await asyncio.gather(
            _rebuild_execute(service, _rebuild(graph, key="d10-concurrent-key")),
            _rebuild_execute(service, _rebuild(graph, key="d10-concurrent-key")),
        )
        assert first.aesthetic_profile_id == second.aesthetic_profile_id
        assert {first.replayed, second.replayed} == {False, True}

        with pytest.raises(DemoMemoryConflict, match="another key"):
            await _rebuild_execute(service, _rebuild(graph, key="d10-same-input-different-key"))

        with pytest.raises(DemoMemoryConflict, match="different request"):
            await _rebuild_execute(
                service,
                _rebuild(
                    graph,
                    key="d10-concurrent-key",
                    reason="RESET",
                ),
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

        async def d10_row_counts() -> tuple[int, int, int, int, int]:
            async with sessions() as session:
                jobs = cast(
                    int,
                    await session.scalar(
                        select(func.count())
                        .select_from(Job)
                        .where(
                            Job.job_type.in_(
                                (
                                    "demo_p3_p7.profile.rebuild",
                                    "demo_p3_p7.context.compile",
                                )
                            )
                        )
                    ),
                )
                attempts = cast(
                    int,
                    await session.scalar(
                        select(func.count())
                        .select_from(JobAttempt)
                        .join(Job, Job.id == JobAttempt.job_id)
                        .where(
                            Job.job_type.in_(
                                (
                                    "demo_p3_p7.profile.rebuild",
                                    "demo_p3_p7.context.compile",
                                )
                            )
                        )
                    ),
                )
                bindings = cast(
                    int,
                    await session.scalar(
                        select(func.count())
                        .select_from(DemoJobBinding)
                        .where(
                            DemoJobBinding.endpoint_operation.in_(
                                ("profile.rebuild", "context.compile")
                            )
                        )
                    ),
                )
                profiles = cast(
                    int,
                    await session.scalar(select(func.count()).select_from(DemoAestheticProfile)),
                )
                contexts = cast(
                    int,
                    await session.scalar(select(func.count()).select_from(DemoContextCompilation)),
                )
                return jobs, attempts, bindings, profiles, contexts

        def fail_profile_after_write(stage: Literal["PROFILE", "CONTEXT"]) -> None:
            if stage == "PROFILE":
                raise RuntimeError("injected profile post-write failure")

        await _append(
            sessions,
            graph,
            event_type=DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION,
            signal={"style_key": "post_write_rollback"},
        )
        before_profile_failure = await d10_row_counts()
        profile_fault_service = DemoMemoryService(
            session_factory=sessions,
            post_write_probe=fail_profile_after_write,
        )
        fault_command = _rebuild(graph, key="d10-profile-post-write-failure")
        fault_admission = await profile_fault_service.admit_rebuild(fault_command)
        with pytest.raises(RuntimeError, match="profile post-write"):
            await profile_fault_service.execute_rebuild(
                demo_actor_id=fault_command.demo_actor_id,
                job_id=fault_admission.job_id,
            )
        after_profile_failure = await d10_row_counts()
        assert after_profile_failure == tuple(
            before + delta
            for before, delta in zip(
                before_profile_failure,
                (1, 1, 1, 0, 0),
                strict=True,
            )
        )
        assert fault_admission.job_id in {
            candidate.job_id
            for candidate in await profile_fault_service.reconciliation_candidates()
        }

        def fail_context_after_write(stage: Literal["PROFILE", "CONTEXT"]) -> None:
            if stage == "CONTEXT":
                raise RuntimeError("injected context post-write failure")

        before_context_failure = await d10_row_counts()
        context_fault_service = DemoMemoryService(
            session_factory=sessions,
            post_write_probe=fail_context_after_write,
        )
        with pytest.raises(RuntimeError, match="context post-write"):
            await context_fault_service.compile_context(
                _context(
                    graph,
                    first.aesthetic_profile_id,
                    key="d10-context-post-write-failure",
                    as_of=AS_OF + timedelta(minutes=2),
                )
            )
        assert await d10_row_counts() == before_context_failure
    finally:
        await engine.dispose()
