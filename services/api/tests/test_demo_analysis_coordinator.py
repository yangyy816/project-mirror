from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import pytest

from mirror_api.demo_analysis_coordinator import DemoAnalysisCoordinator
from mirror_api.demo_analysis_service import (
    CreateDemoAnalysis,
    DemoAnalysisAccepted,
    DemoAnalysisDispatchCandidate,
    DemoAnalysisService,
)
from mirror_api.demo_analysis_task_contract import (
    DemoAnalysisDispatcher,
    DemoAnalysisTaskMessage,
)
from mirror_api.demo_job_service import (
    DemoJobService,
    DemoJobSnapshot,
    DemoJobStatus,
    DemoJobTargetSnapshot,
)


def _command() -> CreateDemoAnalysis:
    return CreateDemoAnalysis(
        demo_actor_id="a" * 32,
        demo_session_id="b" * 32,
        source_asset_id="c" * 32,
        idempotency_key="analysis-create-key",
        request_id="transport-request-id",
    )


def _snapshot(*, status: str = "PENDING") -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id="d" * 32,
        demo_actor_id="a" * 32,
        demo_session_id="b" * 32,
        status=cast(DemoJobStatus, status),
        capability="P3_FACE_ANALYSIS",
        job_binding_digest="e" * 64,
        target=DemoJobTargetSnapshot("ANALYSIS_RUN", "f" * 32, "1" * 64),
        result_code=None,
        finalized_at=None,
    )


@dataclass
class _Service:
    accepted: DemoAnalysisAccepted
    candidates: tuple[DemoAnalysisDispatchCandidate, ...] = ()

    async def create(self, command: CreateDemoAnalysis) -> DemoAnalysisAccepted:
        del command
        return self.accepted

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoAnalysisDispatchCandidate, ...]:
        assert limit == 100
        return self.candidates


@dataclass
class _Jobs:
    snapshot: DemoJobSnapshot

    async def get(self, *, demo_actor_id: str, job_id: str) -> DemoJobSnapshot:
        assert demo_actor_id == "a" * 32
        assert job_id == "d" * 32
        return self.snapshot


@dataclass
class _Dispatcher:
    fail: bool = False
    messages: list[DemoAnalysisTaskMessage] = field(default_factory=list)

    def dispatch_demo_analysis(self, message: DemoAnalysisTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("broker unavailable")
        return message.job_id


def _coordinator(
    service: _Service, jobs: _Jobs, dispatcher: _Dispatcher
) -> DemoAnalysisCoordinator:
    return DemoAnalysisCoordinator(
        service=cast(DemoAnalysisService, service),
        jobs=cast(DemoJobService, jobs),
        dispatcher=cast(DemoAnalysisDispatcher, dispatcher),
    )


@pytest.mark.asyncio
async def test_pending_idempotent_replay_redispatches_durable_request_reference() -> None:
    accepted = DemoAnalysisAccepted(
        job_id="d" * 32,
        analysis_run_id="f" * 32,
        demo_session_id="b" * 32,
        request_id="durable-request-id",
        replayed=True,
    )
    service = _Service(accepted)
    dispatcher = _Dispatcher()

    result = await _coordinator(service, _Jobs(_snapshot()), dispatcher).create(_command())

    assert result.replayed is True
    assert dispatcher.messages == [
        DemoAnalysisTaskMessage("f" * 32, "d" * 32, "durable-request-id")
    ]


@pytest.mark.asyncio
async def test_create_keeps_committed_pending_job_when_broker_is_unavailable() -> None:
    accepted = DemoAnalysisAccepted(
        job_id="d" * 32,
        analysis_run_id="f" * 32,
        demo_session_id="b" * 32,
        request_id="durable-request-id",
        replayed=False,
    )
    dispatcher = _Dispatcher(fail=True)

    result = await _coordinator(_Service(accepted), _Jobs(_snapshot()), dispatcher).create(
        _command()
    )

    assert result.job.status == "PENDING"
    assert len(dispatcher.messages) == 1


@pytest.mark.asyncio
async def test_reconciler_dispatches_each_durable_candidate_and_surfaces_broker_failure() -> None:
    accepted = DemoAnalysisAccepted(
        job_id="d" * 32,
        analysis_run_id="f" * 32,
        demo_session_id="b" * 32,
        request_id="durable-request-id",
        replayed=True,
    )
    candidates = (
        DemoAnalysisDispatchCandidate("f" * 32, "d" * 32, "durable-request-id"),
        DemoAnalysisDispatchCandidate("2" * 32, "3" * 32, "second-request-id"),
    )
    dispatcher = _Dispatcher()
    coordinator = _coordinator(_Service(accepted, candidates), _Jobs(_snapshot()), dispatcher)

    assert await coordinator.reconcile() == ("d" * 32, "3" * 32)
    assert [message.job_id for message in dispatcher.messages] == ["d" * 32, "3" * 32]

    failing = _coordinator(_Service(accepted, candidates), _Jobs(_snapshot()), _Dispatcher(True))
    with pytest.raises(RuntimeError, match="broker unavailable"):
        await failing.reconcile()
