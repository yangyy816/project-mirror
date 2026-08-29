from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import Any, Protocol, cast

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

import mirror_api.demo_analysis_service as analysis_module
from mirror_api.demo_analysis_service import (
    CreateDemoAnalysis,
    DemoAnalysisConfiguration,
    DemoAnalysisInputError,
    DemoAnalysisLeaseLost,
    DemoAnalysisPayloadConflict,
    DemoAnalysisRepeatEvidence,
    DemoAnalysisRuntimeEvidence,
    DemoAnalysisService,
    DemoAnalysisUnavailable,
    DemoLandmark,
    DemoPose,
)
from mirror_api.demo_face_runtime import DimensionObservation
from mirror_api.demo_models import (
    DemoAnalysisRun,
    DemoBaselineFaceModel,
    DemoFaceObservation,
    DemoFaceObservationRepeat,
    DemoJobBinding,
    DemoSelfState,
)
from mirror_api.models import Job, JobAttempt, new_id


class _TruncateDemoAuthority(Protocol):
    def __call__(self, session: Session) -> None: ...


class _AnalysisContext(Protocol):
    def __call__(self, session: Session) -> tuple[Any, Any, Any]: ...


@dataclass(frozen=True)
class _Fixture:
    demo_actor_id: str
    demo_session_id: str
    demo_synthetic_identity_id: str
    source_asset_id: str


@asynccontextmanager
async def _database() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], _Fixture]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    sync_database_url = database_url.replace("+asyncpg", "+psycopg")
    sync_engine = create_engine(sync_database_url)
    analysis_authority = import_module("test_demo_analysis_authority")
    truncate = cast(
        _TruncateDemoAuthority,
        vars(analysis_authority)["_truncate_demo_analysis_test_authority"],
    )
    create_context = cast(_AnalysisContext, vars(analysis_authority)["_analysis_context"])
    try:
        with Session(sync_engine) as sync_session:
            truncate(sync_session)
            actor, demo_session, identity = create_context(sync_session)
            fixture = _Fixture(
                demo_actor_id=actor.id,
                demo_session_id=demo_session.id,
                demo_synthetic_identity_id=identity.id,
                source_asset_id=identity.formal_canonical_asset_id,
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


def _configuration() -> DemoAnalysisConfiguration:
    return DemoAnalysisConfiguration(
        analyzer_version="demo-face-observation-v1",
        runtime_manifest_digest="a" * 64,
        model_manifest_digest="b" * 64,
        observation_config_digest="c" * 64,
        baseline_aggregation_version="demo-baseline-median-v1",
        measurement_version="demo-face-height-normalized-v1",
        self_state_ontology_version="demo-self-state-ontology-v1",
        self_state_derivation_version="demo-self-state-derivation-v1",
    )


def _service(sessions: async_sessionmaker[AsyncSession]) -> DemoAnalysisService:
    return DemoAnalysisService(session_factory=sessions, configuration=_configuration())


def _command(fixture: _Fixture, *, key: str = "d03-idempotency-key") -> CreateDemoAnalysis:
    return CreateDemoAnalysis(
        demo_actor_id=fixture.demo_actor_id,
        demo_session_id=fixture.demo_session_id,
        source_asset_id=fixture.source_asset_id,
        idempotency_key=key,
        request_id=f"d03-request-{new_id()}",
    )


def _runtime_evidence(*, supported: bool = True) -> DemoAnalysisRuntimeEvidence:
    landmarks = tuple(DemoLandmark(x_ppm=0, y_ppm=0, z_ppm=0) for _ in range(478))
    repeats: list[DemoAnalysisRepeatEvidence] = []
    for repeat_index in (1, 2, 3):
        dimensions: tuple[DimensionObservation, ...]
        if supported:
            dimensions = (
                DimensionObservation(
                    dimension="chin_height",
                    support_state="SUPPORTED",
                    value_ppm=200_000 + repeat_index,
                    measurement_confidence_ppm=850_000,
                ),
                DimensionObservation(
                    dimension="jaw_width",
                    support_state="SUPPORTED",
                    value_ppm=300_000 + repeat_index,
                    measurement_confidence_ppm=900_000,
                ),
            )
        else:
            dimensions = (
                DimensionObservation(
                    dimension="jaw_width",
                    support_state="UNSUPPORTED",
                    value_ppm=None,
                    measurement_confidence_ppm=0,
                    unsupported_reason="LANDMARK_UNAVAILABLE",
                ),
            )
        repeats.append(
            DemoAnalysisRepeatEvidence(
                repeat_index=repeat_index,
                evidence_reference=f"d03-repeat-{repeat_index}",
                landmarks=landmarks,
                pose=DemoPose(yaw_ppm=0, pitch_ppm=0, roll_ppm=0),
                dimensions=dimensions,
            )
        )
    return DemoAnalysisRuntimeEvidence((repeats[0], repeats[1], repeats[2]))


async def _count(sessions: async_sessionmaker[AsyncSession], model: type[Any]) -> int:
    async with sessions() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _count_d03_jobs(sessions: async_sessionmaker[AsyncSession]) -> int:
    async with sessions() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.job_type == "demo_p3_p7.analysis.create")
            )
            or 0
        )


async def _count_job_attempts(sessions: async_sessionmaker[AsyncSession], job_id: str) -> int:
    async with sessions() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(JobAttempt).where(JobAttempt.job_id == job_id)
            )
            or 0
        )


@pytest.mark.asyncio
async def test_create_replays_same_request_and_rejects_payload_conflict() -> None:
    async with _database() as (sessions, fixture):
        service = _service(sessions)
        command = _command(fixture)
        first = await service.create(command)
        replay = await service.create(
            CreateDemoAnalysis(
                demo_actor_id=command.demo_actor_id,
                demo_session_id=command.demo_session_id,
                source_asset_id=command.source_asset_id,
                idempotency_key=command.idempotency_key,
                request_id=f"different-transport-{new_id()}",
            )
        )
        assert first.analysis_run_id == replay.analysis_run_id
        assert first.job_id == replay.job_id
        assert first.replayed is False and replay.replayed is True
        assert await _count(sessions, DemoAnalysisRun) == 1
        assert await _count(sessions, DemoJobBinding) == 1
        assert await _count_d03_jobs(sessions) == 1

        with pytest.raises(DemoAnalysisPayloadConflict):
            await service.create(
                CreateDemoAnalysis(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                    source_asset_id=new_id(),
                    idempotency_key=command.idempotency_key,
                    request_id=f"conflict-{new_id()}",
                )
            )


@pytest.mark.asyncio
async def test_concurrent_create_has_one_canonical_job_run_and_binding() -> None:
    async with _database() as (sessions, fixture):
        service = _service(sessions)
        command = _command(fixture, key="d03-concurrent-key")
        left, right = await asyncio.gather(
            service.create(command),
            service.create(
                CreateDemoAnalysis(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=command.demo_session_id,
                    source_asset_id=command.source_asset_id,
                    idempotency_key=command.idempotency_key,
                    request_id=f"concurrent-{new_id()}",
                )
            ),
        )
        assert left.analysis_run_id == right.analysis_run_id
        assert left.job_id == right.job_id
        assert sorted((left.replayed, right.replayed)) == [False, True]
        assert await _count(sessions, DemoAnalysisRun) == 1
        assert await _count(sessions, DemoJobBinding) == 1
        assert await _count_d03_jobs(sessions) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("supported", "expected_state"),
    [(True, "SUPPORTED"), (False, "UNSUPPORTED")],
)
async def test_claim_and_complete_publish_exact_graph_atomically(
    supported: bool, expected_state: str
) -> None:
    async with _database() as (sessions, fixture):
        service = _service(sessions)
        command = _command(fixture, key=f"d03-complete-{supported}")
        accepted = await service.create(command)
        reservation = await service.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=command.request_id,
        )
        assert reservation is not None
        assert (
            await service.claim(
                analysis_run_id=accepted.analysis_run_id,
                job_id=accepted.job_id,
                request_id=command.request_id,
            )
            is None
        )
        publication = await service.complete(reservation, _runtime_evidence(supported=supported))
        assert publication is not None
        assert publication.observation_state == expected_state
        snapshot = await service.snapshot(
            demo_actor_id=fixture.demo_actor_id,
            analysis_run_id=accepted.analysis_run_id,
        )
        assert snapshot.status == "COMPLETED"
        assert snapshot.result_code == expected_state
        assert snapshot.observation_id == publication.observation_id
        assert await _count_job_attempts(sessions, accepted.job_id) == 1
        assert await _count(sessions, DemoFaceObservation) == 1
        assert await _count(sessions, DemoFaceObservationRepeat) == 3
        assert await _count(sessions, DemoBaselineFaceModel) == 1
        assert await _count(sessions, DemoSelfState) == 1


@pytest.mark.asyncio
async def test_expired_leases_create_bounded_attempts_and_then_fail_terminal() -> None:
    async with _database() as (sessions, fixture):
        wall_clock = datetime.now(UTC)
        current = [wall_clock - timedelta(seconds=120)]
        service = DemoAnalysisService(
            session_factory=sessions,
            configuration=replace(_configuration(), lease_seconds=30),
            now=lambda: current[0],
        )
        command = _command(fixture, key="d03-expired-lease-retry")
        accepted = await service.create(command)
        first = await service.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=accepted.request_id,
        )
        assert first is not None and first.attempt == 1

        current[0] = wall_clock - timedelta(seconds=60)
        assert [item.job_id for item in await service.reconciliation_candidates()] == [
            accepted.job_id
        ]
        second = await service.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=accepted.request_id,
        )
        assert second is not None and second.attempt == 2

        current[0] = wall_clock - timedelta(seconds=10)
        with pytest.raises(DemoAnalysisLeaseLost):
            await service.complete(first, _runtime_evidence())
        third = await service.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=accepted.request_id,
        )
        assert third is not None and third.attempt == 3

        current[0] = wall_clock + timedelta(seconds=21)
        exhausted = await service.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=accepted.request_id,
        )
        assert exhausted is None
        snapshot = await service.snapshot(
            demo_actor_id=fixture.demo_actor_id,
            analysis_run_id=accepted.analysis_run_id,
        )
        assert snapshot.status == "FAILED"
        assert snapshot.result_code == "D03_LEASE_RETRY_EXHAUSTED"
        async with sessions() as session:
            attempts = list(
                (
                    await session.scalars(
                        select(JobAttempt)
                        .where(JobAttempt.job_id == accepted.job_id)
                        .order_by(JobAttempt.attempt)
                    )
                ).all()
            )
        assert [attempt.status for attempt in attempts] == ["FAILED", "FAILED", "FAILED"]
        assert [attempt.error_code for attempt in attempts] == [
            "D03_LEASE_EXPIRED",
            "D03_LEASE_EXPIRED",
            "D03_LEASE_RETRY_EXHAUSTED",
        ]
        with pytest.raises(DBAPIError, match="cannot downgrade populated multi-attempt"):
            alembic_command.downgrade(Config("alembic.ini"), "demo_0010_d03_analysis_run")


@pytest.mark.asyncio
async def test_cancel_before_claim_and_running_cancel_publish_no_graph() -> None:
    async with _database() as (sessions, fixture):
        service = _service(sessions)
        pending_command = _command(fixture, key="d03-pending-cancel")
        pending = await service.create(pending_command)
        assert await service.cancel(
            demo_actor_id=fixture.demo_actor_id,
            demo_session_id=fixture.demo_session_id,
            job_id=pending.job_id,
            expected_status="PENDING",
        )
        assert (
            await service.claim(
                analysis_run_id=pending.analysis_run_id,
                job_id=pending.job_id,
                request_id=pending_command.request_id,
            )
            is None
        )

        running_command = _command(fixture, key="d03-running-cancel")
        running = await service.create(running_command)
        reservation = await service.claim(
            analysis_run_id=running.analysis_run_id,
            job_id=running.job_id,
            request_id=running_command.request_id,
        )
        assert reservation is not None
        assert await service.cancel(
            demo_actor_id=fixture.demo_actor_id,
            demo_session_id=fixture.demo_session_id,
            job_id=running.job_id,
            expected_status="RUNNING",
        )
        assert await service.complete(reservation, _runtime_evidence()) is None
        assert await _count(sessions, DemoFaceObservation) == 0
        assert await _count(sessions, DemoFaceObservationRepeat) == 0
        assert await _count(sessions, DemoBaselineFaceModel) == 0
        assert await _count(sessions, DemoSelfState) == 0


@pytest.mark.asyncio
async def test_complete_and_cancel_race_has_one_terminal_winner() -> None:
    async with _database() as (sessions, fixture):
        service = _service(sessions)
        command = _command(fixture, key="d03-complete-cancel-race")
        accepted = await service.create(command)
        reservation = await service.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=command.request_id,
        )
        assert reservation is not None
        completion, cancellation = await asyncio.gather(
            service.complete(reservation, _runtime_evidence()),
            service.cancel(
                demo_actor_id=fixture.demo_actor_id,
                demo_session_id=fixture.demo_session_id,
                job_id=accepted.job_id,
                expected_status="RUNNING",
            ),
        )
        snapshot = await service.snapshot(
            demo_actor_id=fixture.demo_actor_id,
            analysis_run_id=accepted.analysis_run_id,
        )
        assert snapshot.status in {"COMPLETED", "CANCELLED"}
        if snapshot.status == "COMPLETED":
            assert completion is not None and cancellation is False
            assert await _count(sessions, DemoFaceObservation) == 1
            assert await _count(sessions, DemoFaceObservationRepeat) == 3
        else:
            assert completion is None and cancellation is True
            assert await _count(sessions, DemoFaceObservation) == 0
            assert await _count(sessions, DemoFaceObservationRepeat) == 0


@pytest.mark.asyncio
async def test_publication_exception_rolls_back_every_candidate_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _database() as (sessions, fixture):
        service = _service(sessions)
        command = _command(fixture, key="d03-publication-rollback")
        accepted = await service.create(command)
        reservation = await service.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=command.request_id,
        )
        assert reservation is not None

        original = analysis_module._self_state_row

        def fail_after_baseline(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            raise RuntimeError("injected publication failure")

        monkeypatch.setattr(analysis_module, "_self_state_row", fail_after_baseline)
        with pytest.raises(RuntimeError, match="injected publication failure"):
            await service.complete(reservation, _runtime_evidence())
        monkeypatch.setattr(analysis_module, "_self_state_row", original)

        assert await _count(sessions, DemoFaceObservation) == 0
        assert await _count(sessions, DemoFaceObservationRepeat) == 0
        assert await _count(sessions, DemoBaselineFaceModel) == 0
        assert await _count(sessions, DemoSelfState) == 0
        snapshot = await service.snapshot(
            demo_actor_id=fixture.demo_actor_id,
            analysis_run_id=accepted.analysis_run_id,
        )
        assert snapshot.status == "RUNNING"
        assert await service.terminalize(reservation, status="FAILED", code="PUBLICATION_FAILED")


@pytest.mark.asyncio
async def test_task_mismatch_and_invalid_runtime_evidence_fail_closed() -> None:
    async with _database() as (sessions, fixture):
        service = _service(sessions)
        command = _command(fixture, key="d03-mismatch")
        accepted = await service.create(command)
        with pytest.raises(DemoAnalysisUnavailable, match="unavailable"):
            await service.claim(
                analysis_run_id=new_id(),
                job_id=accepted.job_id,
                request_id=command.request_id,
            )
        with pytest.raises(DemoAnalysisInputError):
            DemoAnalysisRepeatEvidence(
                repeat_index=1,
                evidence_reference="d03-invalid",
                landmarks=(),
                pose=DemoPose(yaw_ppm=0, pitch_ppm=0, roll_ppm=0),
                dimensions=(
                    DimensionObservation(
                        dimension="jaw_width",
                        support_state="SUPPORTED",
                        value_ppm=300_000,
                        measurement_confidence_ppm=900_000,
                    ),
                ),
            )
