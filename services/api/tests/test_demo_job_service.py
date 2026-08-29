from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from mirror_api.demo_idempotency import DemoIdempotencyPayloadConflict
from mirror_api.demo_job_service import (
    DemoJobService,
    DemoJobStateConflict,
    DemoJobUnavailable,
)
from mirror_api.demo_models import DemoCommandBinding
from mirror_api.models import Job, JobAttempt


class _TruncateAuthority(Protocol):
    def __call__(self, session: Session) -> None: ...


class _AnalysisContext(Protocol):
    def __call__(self, session: Session) -> tuple[Any, Any, Any]: ...


class _PendingAnalysis(Protocol):
    def __call__(
        self, session: Session, actor: Any, demo_session: Any, identity: Any
    ) -> tuple[Job, Any, Any]: ...


class _ClaimAnalysis(Protocol):
    def __call__(self, session: Session, job: Job) -> JobAttempt: ...


@dataclass(frozen=True)
class _Fixture:
    actor_id: str
    session_id: str
    job_id: str
    run_id: str
    run_digest: str


@asynccontextmanager
async def _database(
    *, running: bool = False
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], _Fixture]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    authority = import_module("test_demo_analysis_authority")
    truncate = cast(
        _TruncateAuthority,
        vars(authority)["_truncate_demo_analysis_test_authority"],
    )
    create_context = cast(_AnalysisContext, vars(authority)["_analysis_context"])
    create_analysis = cast(_PendingAnalysis, vars(authority)["_pending_analysis"])
    claim_analysis = cast(_ClaimAnalysis, vars(authority)["_claim_analysis"])
    sync_url = database_url.replace("+asyncpg", "+psycopg")
    sync_engine = create_engine(sync_url)
    try:
        with Session(sync_engine) as sync_session:
            truncate(sync_session)
            actor, demo_session, identity = create_context(sync_session)
            job, run, _ = create_analysis(sync_session, actor, demo_session, identity)
            if running:
                claim_analysis(sync_session, job)
            fixture = _Fixture(
                actor_id=actor.id,
                session_id=demo_session.id,
                job_id=job.id,
                run_id=run.id,
                run_digest=run.content_digest,
            )
        engine = create_async_engine(database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            yield sessions, fixture
        finally:
            await engine.dispose()
    finally:
        with Session(sync_engine) as sync_session:
            truncate(sync_session)
        sync_engine.dispose()


@pytest.mark.asyncio
async def test_owner_bound_job_snapshot_exposes_immutable_typed_target() -> None:
    async with _database() as (sessions, fixture):
        service = DemoJobService(session_factory=sessions)
        snapshot = await service.get(
            demo_actor_id=fixture.actor_id,
            job_id=fixture.job_id,
        )

        assert snapshot.status == "PENDING"
        assert snapshot.capability == "P3_FACE_ANALYSIS"
        assert snapshot.demo_session_id == fixture.session_id
        assert snapshot.target.target_type == "ANALYSIS_RUN"
        assert snapshot.target.target_id == fixture.run_id
        assert snapshot.target.authority_digest == fixture.run_digest
        assert len(snapshot.job_binding_digest) == 64

        with pytest.raises(DemoJobUnavailable):
            await service.get(demo_actor_id="f" * 32, job_id=fixture.job_id)


@pytest.mark.asyncio
async def test_pending_cancel_is_atomic_replayable_and_terminal() -> None:
    async with _database() as (sessions, fixture):
        service = DemoJobService(session_factory=sessions)
        first = await service.cancel(
            demo_actor_id=fixture.actor_id,
            job_id=fixture.job_id,
            expected_status="PENDING",
            reason="USER_REQUEST",
            idempotency_key="job-cancel-pending-key",
        )
        replay = await service.cancel(
            demo_actor_id=fixture.actor_id,
            job_id=fixture.job_id,
            expected_status="PENDING",
            reason="USER_REQUEST",
            idempotency_key="job-cancel-pending-key",
        )

        assert first == replay
        assert first.status == "CANCELLED"
        assert first.result_code == "USER_REQUEST"
        assert first.finalized_at is not None
        async with sessions() as session:
            job = await session.get(Job, fixture.job_id)
            assert job is not None and job.attempt_count == 0
            assert await session.scalar(select(func.count()).select_from(DemoCommandBinding)) == 1

        with pytest.raises(DemoIdempotencyPayloadConflict):
            await service.cancel(
                demo_actor_id=fixture.actor_id,
                job_id=fixture.job_id,
                expected_status="RUNNING",
                reason="USER_REQUEST",
                idempotency_key="job-cancel-pending-key",
            )
        with pytest.raises(DemoJobStateConflict):
            await service.cancel(
                demo_actor_id=fixture.actor_id,
                job_id=fixture.job_id,
                expected_status="PENDING",
                reason="USER_REQUEST",
                idempotency_key="another-cancel-command",
            )


@pytest.mark.asyncio
async def test_running_cancel_terminalizes_current_attempt_in_same_transaction() -> None:
    async with _database(running=True) as (sessions, fixture):
        service = DemoJobService(session_factory=sessions)
        snapshot = await service.cancel(
            demo_actor_id=fixture.actor_id,
            job_id=fixture.job_id,
            expected_status="RUNNING",
            reason="USER_REQUEST",
            idempotency_key="job-cancel-running-key",
        )
        assert snapshot.status == "CANCELLED"

        async with sessions() as session:
            job = await session.get(Job, fixture.job_id)
            attempt = await session.scalar(
                select(JobAttempt).where(JobAttempt.job_id == fixture.job_id)
            )
            assert job is not None and job.status == "CANCELLED"
            assert attempt is not None and attempt.status == "CANCELLED"
            assert attempt.result_code == "USER_REQUEST"
            assert attempt.finished_at == job.finalized_at


@pytest.mark.asyncio
async def test_concurrent_same_key_cancel_has_one_canonical_winner() -> None:
    async with _database() as (sessions, fixture):
        service = DemoJobService(session_factory=sessions)

        async def cancel() -> str:
            result = await service.cancel(
                demo_actor_id=fixture.actor_id,
                job_id=fixture.job_id,
                expected_status="PENDING",
                reason="USER_REQUEST",
                idempotency_key="concurrent-cancel-key",
            )
            return result.job_binding_digest

        digests = await asyncio.gather(cancel(), cancel())
        assert digests[0] == digests[1]
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(DemoCommandBinding)) == 1
            job = await session.get(Job, fixture.job_id)
            assert job is not None and job.status == "CANCELLED"
