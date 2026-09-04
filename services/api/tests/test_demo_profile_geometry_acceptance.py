from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Generator
from dataclasses import fields
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)
from test_demo_stepped_self_transfer_acceptance import (
    _append_persistent_constraints,
    _stepped_execution,
)

from mirror_api.demo_editing_commands import (
    DemoEditingCommandService,
    DemoEditingCommandUnavailable,
    DemoEditResultNotReady,
    DemoEditResultTerminal,
)
from mirror_api.demo_image_feedback_service import DemoImageFeedbackService
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_models import (
    DemoAcceptedVisualEpisode,
    DemoSelfTransferDimensionEvidence,
    DemoSelfTransferRun,
)
from mirror_api.demo_profile_geometry_acceptance import (
    AcceptProfileGeometryExecution,
    DemoProfileGeometryAcceptanceError,
    DemoProfileGeometryAcceptanceFacade,
    DemoProfileGeometryAcceptanceResult,
)
from mirror_api.demo_reference_profile_coordinator import DemoReferenceProfileCoordinator
from mirror_api.demo_reference_profile_service import DemoReferenceProfileService
from mirror_api.demo_self_transfer_acceptance import (
    DemoSteppedSelfTransferAcceptanceCoordinator,
)
from mirror_api.demo_self_transfer_service import (
    DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA,
    DemoSelfTransferService,
    DemoSelfTransferServiceError,
)
from mirror_api.models import Job, utcnow

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def postgres_session() -> Generator[Session]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is unavailable")
    engine = create_engine(url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
        yield session
        session.rollback()
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
    engine.dispose()


class _Dispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[Any] = []

    def dispatch_demo_reference_profile(self, message: Any) -> None:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("synthetic dispatch failure")


def _facade(
    sessions: async_sessionmaker[AsyncSession],
    *,
    dispatcher: _Dispatcher,
) -> tuple[
    DemoProfileGeometryAcceptanceFacade,
    DemoReferenceProfileService,
    DemoReferenceProfileCoordinator,
]:
    transfer = DemoSelfTransferService(session_factory=sessions)
    reference = DemoReferenceProfileService(session_factory=sessions)
    jobs = DemoJobService(session_factory=sessions)
    reference_coordinator = DemoReferenceProfileCoordinator(
        service=reference,
        jobs=jobs,
        dispatcher=cast(Any, dispatcher),
    )
    atomic = DemoSteppedSelfTransferAcceptanceCoordinator(
        session_factory=sessions,
        feedback=DemoImageFeedbackService(session_factory=sessions),
        transfer=transfer,
        reference_service=reference,
        reference_coordinator=reference_coordinator,
    )
    return (
        DemoProfileGeometryAcceptanceFacade(
            session_factory=sessions,
            editing=DemoEditingCommandService(session_factory=sessions),
            transfer=transfer,
            acceptance=atomic,
            jobs=jobs,
        ),
        reference,
        reference_coordinator,
    )


def _command(actor_id: str, execution_job_id: str) -> AcceptProfileGeometryExecution:
    return AcceptProfileGeometryExecution(
        demo_actor_id=actor_id,
        execution_job_id=execution_job_id,
        idempotency_key="test-accept-key-00000000",
        outcome="FINAL_SAVE_AND_USE_AS_REFERENCE",
    )


@pytest.mark.asyncio
async def test_job_only_accept_is_concurrent_replay_safe_and_reference_recovers(
    postgres_session: Session,
    tmp_path: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions, engine, graph, _, execution, _ = await _stepped_execution(postgres_session, tmp_path)
    dispatcher = _Dispatcher(fail=True)
    facade, reference, reference_coordinator = _facade(sessions, dispatcher=dispatcher)
    command = _command(graph["actor"].id, execution.job_id)
    caplog.set_level(logging.INFO)
    try:
        first, replay = await asyncio.gather(facade.accept(command), facade.accept(command))
        assert first == replay
        assert first.status == "REFERENCE_PROFILE_PENDING"
        assert first.queue_state == "PENDING"
        assert first.reference_profile_job_id is not None
        assert {item.name for item in fields(DemoProfileGeometryAcceptanceResult)} == {
            "status",
            "reference_profile_job_id",
            "queue_state",
        }
        assert command.idempotency_key not in caplog.text
        postgres_session.expire_all()
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoSelfTransferRun)
                .where(DemoSelfTransferRun.schema_version == DEMO_STEPPED_SELF_TRANSFER_RUN_SCHEMA)
            )
            == 2
        )
        assert (
            postgres_session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
            == 1
        )
        assert (
            postgres_session.scalar(
                select(func.count()).select_from(DemoSelfTransferDimensionEvidence)
            )
            == 1
        )
        assert len(dispatcher.messages) >= 1
        message = dispatcher.messages[0]
        dispatcher.fail = False
        assert await reference_coordinator.reconcile() == (first.reference_profile_job_id,)
        completed = await reference.execute_task(
            demo_actor_id=graph["actor"].id,
            job_id=message.job_id,
            compile_request_id=message.compile_request_id,
        )
        assert completed.status == "COMPLETED"
        ready = await facade.accept(command)
        assert ready == DemoProfileGeometryAcceptanceResult(
            "REFERENCE_PROFILE_READY",
            first.reference_profile_job_id,
            "READY",
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_job_only_accept_rejects_wrong_owner_and_nonterminal_execution(
    postgres_session: Session,
    tmp_path: Any,
) -> None:
    sessions, engine, graph, _, execution, _ = await _stepped_execution(postgres_session, tmp_path)
    facade, _, _ = _facade(sessions, dispatcher=_Dispatcher())
    try:
        with pytest.raises(DemoEditingCommandUnavailable):
            await facade.accept(_command("f" * 32, execution.job_id))
        postgres_session.execute(
            update(Job)
            .where(Job.id == execution.job_id)
            .values(status="PENDING", finalized_at=None, result_code=None)
        )
        postgres_session.commit()
        with pytest.raises(DemoEditResultNotReady):
            await facade.accept(_command(graph["actor"].id, execution.job_id))
        postgres_session.execute(
            update(Job)
            .where(Job.id == execution.job_id)
            .values(
                status="FAILED",
                finalized_at=utcnow(),
                result_code="SYNTHETIC_TERMINAL",
            )
        )
        postgres_session.commit()
        with pytest.raises(DemoEditResultTerminal):
            await facade.accept(_command(graph["actor"].id, execution.job_id))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_job_only_accept_constraint_drift_leaves_zero_partial_rows(
    postgres_session: Session,
    tmp_path: Any,
) -> None:
    sessions, engine, graph, _, execution, _ = await _stepped_execution(postgres_session, tmp_path)
    _append_persistent_constraints(
        postgres_session,
        graph,
        locks={"jaw_width": {"mode": "PRESERVE"}},
        prohibited_operations=[],
    )
    facade, _, _ = _facade(sessions, dispatcher=_Dispatcher())
    before = (
        postgres_session.scalar(select(func.count()).select_from(DemoSelfTransferRun)),
        postgres_session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode)),
    )
    try:
        with pytest.raises(DemoSelfTransferServiceError):
            await facade.accept(_command(graph["actor"].id, execution.job_id))
        postgres_session.expire_all()
        after = (
            postgres_session.scalar(select(func.count()).select_from(DemoSelfTransferRun)),
            postgres_session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode)),
        )
        assert after == before
    finally:
        await engine.dispose()


def test_job_only_accept_command_is_strict() -> None:
    with pytest.raises(DemoProfileGeometryAcceptanceError) as short_key:
        AcceptProfileGeometryExecution(
            demo_actor_id="a" * 32,
            execution_job_id="b" * 32,
            idempotency_key="short",
            outcome="FINAL_SAVE_AND_USE_AS_REFERENCE",
        ).validate()
    assert short_key.value.code == "INVALID_IDEMPOTENCY_KEY"
