from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _insert_full_demo_graph,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)
from test_demo_self_transfer_service import _create_command, _published_result

from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_models import (
    DemoJobBinding,
    DemoReferenceProfile,
    DemoReferenceProfileCompileRequest,
    DemoReferenceProfileCompileResult,
)
from mirror_api.demo_reference_profile_service import (
    CreateDemoReferenceProfileCompilation,
    DemoReferenceProfileAuthorityCorruption,
    DemoReferenceProfileConflict,
    DemoReferenceProfileResultNotReady,
    DemoReferenceProfileResultTerminal,
    DemoReferenceProfileService,
    DemoReferenceProfileUnavailable,
)
from mirror_api.demo_self_transfer_service import (
    DemoReferenceSource,
    DemoSelfTransferService,
    FinalizeDemoSelfTransferResult,
)
from mirror_api.models import Asset, Job, JobAttempt, utcnow

pytestmark = pytest.mark.integration


def _truncate_d06_queue(session: Session) -> None:
    session.execute(
        text(
            "TRUNCATE TABLE demo_reference_compile_results, demo_reference_compile_requests CASCADE"
        )
    )
    session.commit()


@pytest.fixture
def postgres_session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        _truncate_d06_queue(session)
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
        yield session
        session.rollback()
        _truncate_d06_queue(session)
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
    engine.dispose()


def _service(*, now: Any | None = None) -> tuple[DemoReferenceProfileService, AsyncEngine]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    if now is None:
        return DemoReferenceProfileService(session_factory=sessions), engine
    return DemoReferenceProfileService(session_factory=sessions, now=now), engine


def _command(
    graph: dict[str, Any],
    *,
    source_asset_id: str,
    case: str,
) -> CreateDemoReferenceProfileCompilation:
    idempotency_key = f"d06-reference-{case}"
    return CreateDemoReferenceProfileCompilation(
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=graph["desired_delta"].id,
        style_profile_id=graph["style"].id,
        identity_constraints_id=graph["constraints"].id,
        sources=(DemoReferenceSource(source_asset_id, "FRONT"),),
        idempotency_key=idempotency_key,
        request_id=f"request-{idempotency_key}",
    )


async def _accepted_reference_source(
    postgres_session: Session,
    graph: dict[str, Any],
    service: DemoReferenceProfileService,
    *,
    case: str,
) -> str:
    published = _published_result(postgres_session, graph)
    transfer = DemoSelfTransferService(session_factory=service._sessions)
    created = await transfer.create_request(
        _create_command(graph, key=f"d06-reference-{case}-transfer")
    )
    await transfer.reserve(
        demo_actor_id=graph["actor"].id,
        request_run_id=created.request_run_id,
    )
    await transfer.finalize(
        FinalizeDemoSelfTransferResult(
            demo_actor_id=graph["actor"].id,
            request_run_id=created.request_run_id,
            result_image_version_id=published["image"].id,
            user_outcome="ACCEPTED",
        )
    )
    return published["output_asset"].id


@pytest.mark.asyncio
async def test_admit_replay_collision_and_one_atomic_envelope(postgres_session: Session) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="admission-race",
        )
        command = _command(
            graph,
            source_asset_id=source_asset_id,
            case="admission-race",
        )
        first, second = await asyncio.gather(service.admit(command), service.admit(command))
        assert first.job_id == second.job_id
        assert first.compile_request_id == second.compile_request_id
        assert sorted((first.replayed, second.replayed)) == [False, True]
        with pytest.raises(DemoReferenceProfileResultNotReady):
            await service.read_completed_result(
                demo_actor_id=graph["actor"].id,
                job_id=first.job_id,
            )
        with pytest.raises(DemoReferenceProfileUnavailable):
            await service.read_completed_result(
                demo_actor_id="f" * 32,
                job_id=first.job_id,
            )

        with pytest.raises(DemoReferenceProfileConflict, match="idempotency key"):
            await service.admit(
                replace(
                    command,
                    sources=(DemoReferenceSource(source_asset_id, "SIDE"),),
                )
            )

        postgres_session.expire_all()
        job_count = postgres_session.scalar(
            select(func.count()).select_from(Job).where(Job.id == first.job_id)
        )
        binding_count = postgres_session.scalar(
            select(func.count())
            .select_from(DemoJobBinding)
            .where(DemoJobBinding.job_id == first.job_id)
        )
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoReferenceProfileCompileRequest)
                .where(DemoReferenceProfileCompileRequest.id == first.compile_request_id)
            )
            == 1
        )
        assert job_count == 1
        assert binding_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reservation_redelivery_expiry_and_max_attempts(postgres_session: Session) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    clock = [datetime(2026, 9, 1, tzinfo=UTC)]
    service, engine = _service(now=lambda: clock[0])
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="lease-expiry",
        )
        accepted = await service.admit(
            _command(
                graph,
                source_asset_id=source_asset_id,
                case="lease-expiry",
            )
        )
        first = await service.reserve(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
            compile_request_id=accepted.compile_request_id,
        )
        active = await service.reserve(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
            compile_request_id=accepted.compile_request_id,
        )
        assert first.state == "RESERVED" and first.attempt == 1
        assert active.state == "ACTIVE" and active.attempt == 1

        for expected_attempt in (2, 3):
            clock[0] += timedelta(seconds=301)
            reservation = await service.reserve(
                demo_actor_id=graph["actor"].id,
                job_id=accepted.job_id,
                compile_request_id=accepted.compile_request_id,
            )
            assert reservation.state == "RESERVED" and reservation.attempt == expected_attempt
        clock[0] += timedelta(seconds=301)
        exhausted = await service.reserve(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
            compile_request_id=accepted.compile_request_id,
        )
        assert exhausted.state == "TERMINAL" and exhausted.terminal_status == "FAILED"

        postgres_session.expire_all()
        job = postgres_session.get(Job, accepted.job_id)
        attempts = postgres_session.scalars(
            select(JobAttempt)
            .where(JobAttempt.job_id == accepted.job_id)
            .order_by(JobAttempt.attempt)
        ).all()
        assert job is not None and job.status == "FAILED" and job.attempt_count == 3
        assert [attempt.status for attempt in attempts] == ["FAILED", "FAILED", "FAILED"]
        assert all(attempt.error_code == "LEASE_EXPIRED" for attempt in attempts)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_pending_or_running_job_cannot_publish_result(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    jobs = DemoJobService(session_factory=service._sessions)
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="cancel",
        )
        for key, expected_status in (
            ("d06-cancel-pending", "PENDING"),
            ("d06-cancel-running", "RUNNING"),
        ):
            accepted = await service.admit(
                _command(graph, source_asset_id=source_asset_id, case=key)
            )
            if expected_status == "RUNNING":
                await service.reserve(
                    demo_actor_id=graph["actor"].id,
                    job_id=accepted.job_id,
                    compile_request_id=accepted.compile_request_id,
                )
            cancelled = await jobs.cancel(
                demo_actor_id=graph["actor"].id,
                job_id=accepted.job_id,
                expected_status=expected_status,  # type: ignore[arg-type]
                reason="USER_REQUEST",
                idempotency_key=f"{key}-command",
            )
            result = await service.execute_task(
                demo_actor_id=graph["actor"].id,
                job_id=accepted.job_id,
                compile_request_id=accepted.compile_request_id,
            )
            assert cancelled.status == "CANCELLED"
            assert result.status == "CANCELLED" and result.reference_profile_id is None
            with pytest.raises(DemoReferenceProfileResultTerminal):
                await service.read_completed_result(
                    demo_actor_id=graph["actor"].id,
                    job_id=accepted.job_id,
                )
            async with service._sessions() as session:
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(DemoReferenceProfileCompileResult)
                        .where(
                            DemoReferenceProfileCompileResult.compile_request_id
                            == accepted.compile_request_id
                        )
                    )
                    == 0
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_owner_mismatch_is_unavailable_without_mutating_envelope(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="owner-bound",
        )
        accepted = await service.admit(
            _command(
                graph,
                source_asset_id=source_asset_id,
                case="owner-bound",
            )
        )
        with pytest.raises(DemoReferenceProfileUnavailable, match="unavailable"):
            await service.reserve(
                demo_actor_id="f" * 32,
                job_id=accepted.job_id,
                compile_request_id=accepted.compile_request_id,
            )
        postgres_session.expire_all()
        job = postgres_session.get(Job, accepted.job_id)
        assert job is not None and job.status == "PENDING" and job.attempt_count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_execute_creates_one_result_and_terminal_redelivery_replays(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="execute-success",
        )
        accepted = await service.admit(
            _command(
                graph,
                source_asset_id=source_asset_id,
                case="execute-success",
            )
        )
        result = await service.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
            compile_request_id=accepted.compile_request_id,
        )
        replay = await service.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
            compile_request_id=accepted.compile_request_id,
        )
        assert result.status == "COMPLETED"
        assert result.reference_profile_id is not None
        assert replay.status == "COMPLETED"
        assert replay.reference_profile_id == result.reference_profile_id
        assert replay.replayed is True
        completed = await service.read_completed_result(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
        )
        assert completed.job_id == accepted.job_id
        assert completed.demo_session_id == graph["session"].id
        assert completed.reference_profile_id == result.reference_profile_id
        assert completed.job_binding_digest
        assert completed.compile_result_digest
        assert completed.profile_digest == result.profile_digest

        postgres_session.expire_all()
        job = postgres_session.get(Job, accepted.job_id)
        assert job is not None and job.status == "COMPLETED"
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoReferenceProfileCompileResult)
                .where(
                    DemoReferenceProfileCompileResult.compile_request_id
                    == accepted.compile_request_id
                )
            )
            == 1
        )
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoReferenceProfile)
                .where(DemoReferenceProfile.id == result.reference_profile_id)
            )
            == 1
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_exact_result_rejects_compile_result_substitution(
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="result-substitution",
        )
        accepted = await service.admit(
            _command(
                graph,
                source_asset_id=source_asset_id,
                case="result-substitution",
            )
        )
        executed = await service.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
            compile_request_id=accepted.compile_request_id,
        )
        assert executed.reference_profile_id is not None
        persisted = postgres_session.scalar(
            select(DemoReferenceProfileCompileResult).where(
                DemoReferenceProfileCompileResult.compile_request_id == accepted.compile_request_id
            )
        )
        assert persisted is not None
        substituted = DemoReferenceProfileCompileResult(
            id=persisted.id,
            schema_version=persisted.schema_version,
            canonical_payload=dict(persisted.canonical_payload),
            content_digest=persisted.content_digest,
            created_at=persisted.created_at,
            demo_actor_id=persisted.demo_actor_id,
            demo_session_id=persisted.demo_session_id,
            compile_request_id=persisted.compile_request_id,
            demo_job_binding_id=persisted.demo_job_binding_id,
            reference_profile_id=persisted.reference_profile_id,
            reference_profile_digest="f" * 64,
            input_digest=persisted.input_digest,
            result_code=persisted.result_code,
        )

        async def substituted_result(
            _session: Any, _compile_request_id: str
        ) -> DemoReferenceProfileCompileResult:
            return substituted

        monkeypatch.setattr(service, "_result_for_request", substituted_result)
        with pytest.raises(DemoReferenceProfileAuthorityCorruption):
            await service.read_completed_result(
                demo_actor_id=graph["actor"].id,
                job_id=accepted.job_id,
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_populated_d06_downgrade_fails_closed(postgres_session: Session) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="populated-downgrade",
        )
        await service.admit(
            _command(
                graph,
                source_asset_id=source_asset_id,
                case="populated-downgrade",
            )
        )
    finally:
        await engine.dispose()

    # This test targets the D06 guard, so remove the unrelated D03 v2 Repeat
    # fixture before asking Alembic to cross the D03 downgrade.
    postgres_session.execute(text("TRUNCATE TABLE demo_face_observation_repeats"))
    postgres_session.commit()

    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option(
        "script_location",
        str(root / "services" / "api" / "migrations"),
    )
    postgres_session.commit()
    try:
        with pytest.raises(ProgrammingError, match="downgrade is forbidden"):
            alembic_command.downgrade(config, "demo_0015_d02_source_acq_pool")
        postgres_session.expire_all()
        assert postgres_session.scalar(text("SELECT version_num FROM alembic_version")) == (
            "demo_0019_d06_stepped_transfer"
        )
    finally:
        alembic_command.upgrade(config, "demo_0019_d06_stepped_transfer")


@pytest.mark.asyncio
async def test_source_invalidation_rejects_without_partial_result(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    try:
        source_asset_id = await _accepted_reference_source(
            postgres_session,
            graph,
            service,
            case="source-invalidated",
        )
        accepted = await service.admit(
            _command(
                graph,
                source_asset_id=source_asset_id,
                case="source-invalidated",
            )
        )
        asset = postgres_session.get(Asset, source_asset_id)
        assert asset is not None
        asset.deleted_at = utcnow()
        postgres_session.commit()

        result = await service.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=accepted.job_id,
            compile_request_id=accepted.compile_request_id,
        )
        assert result.status == "REJECTED"
        postgres_session.expire_all()
        job = postgres_session.get(Job, accepted.job_id)
        assert job is not None and job.status == "REJECTED"
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoReferenceProfileCompileResult)
                .where(
                    DemoReferenceProfileCompileResult.compile_request_id
                    == accepted.compile_request_id
                )
            )
            == 0
        )
    finally:
        await engine.dispose()
