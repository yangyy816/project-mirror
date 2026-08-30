from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import pytest

from mirror_api.demo_job_service import (
    DemoJobService,
    DemoJobSnapshot,
    DemoJobStatus,
    DemoJobTargetSnapshot,
)
from mirror_api.demo_memory_coordinator import DemoMemoryCoordinator
from mirror_api.demo_memory_service import (
    DemoMemoryReconciliationCandidate,
    DemoMemoryService,
    DemoProfileRebuildAccepted,
    RebuildDemoAestheticProfile,
)
from mirror_api.demo_memory_task_contract import (
    DemoMemoryDispatcher,
    DemoMemoryTaskMessage,
)


def _command() -> RebuildDemoAestheticProfile:
    return RebuildDemoAestheticProfile(
        demo_actor_id="a" * 32,
        reason="USER_REQUEST",
        idempotency_key="memory-rebuild-key",
        request_id="memory-http-request",
    )


def _snapshot(*, status: str = "PENDING") -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id="b" * 32,
        demo_actor_id="a" * 32,
        demo_session_id=None,
        status=cast(DemoJobStatus, status),
        capability="P7_PROFILE_REBUILD",
        job_binding_digest="c" * 64,
        target=DemoJobTargetSnapshot("DEMO_ACTOR", "a" * 32, "d" * 64),
        result_code=None,
        finalized_at=None,
    )


@dataclass
class _Service:
    accepted: DemoProfileRebuildAccepted
    candidates: tuple[DemoMemoryReconciliationCandidate, ...] = ()

    async def admit_rebuild(
        self, command: RebuildDemoAestheticProfile
    ) -> DemoProfileRebuildAccepted:
        assert command == _command()
        return self.accepted

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoMemoryReconciliationCandidate, ...]:
        assert limit == 100
        return self.candidates


@dataclass
class _Jobs:
    snapshot: DemoJobSnapshot

    async def get(self, *, demo_actor_id: str, job_id: str) -> DemoJobSnapshot:
        assert demo_actor_id == "a" * 32
        assert job_id == "b" * 32
        return self.snapshot


@dataclass
class _Dispatcher:
    fail: bool = False
    messages: list[DemoMemoryTaskMessage] = field(default_factory=list)

    def dispatch_demo_memory(self, message: DemoMemoryTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("broker unavailable")
        return message.job_id


def _coordinator(service: _Service, jobs: _Jobs, dispatcher: _Dispatcher) -> DemoMemoryCoordinator:
    return DemoMemoryCoordinator(
        service=cast(DemoMemoryService, service),
        jobs=cast(DemoJobService, jobs),
        dispatcher=cast(DemoMemoryDispatcher, dispatcher),
    )


@pytest.mark.asyncio
async def test_pending_admission_dispatches_only_durable_reference() -> None:
    accepted = DemoProfileRebuildAccepted(
        job_id="b" * 32,
        request_id="durable-memory-request",
        replayed=True,
    )
    dispatcher = _Dispatcher()

    result = await _coordinator(_Service(accepted), _Jobs(_snapshot()), dispatcher).create(
        _command()
    )

    assert result.replayed is True
    assert result.job.status == "PENDING"
    assert dispatcher.messages == [
        DemoMemoryTaskMessage("a" * 32, "b" * 32, "durable-memory-request")
    ]


@pytest.mark.asyncio
async def test_dispatch_failure_preserves_admitted_pending_job() -> None:
    accepted = DemoProfileRebuildAccepted(
        job_id="b" * 32,
        request_id="durable-memory-request",
        replayed=False,
    )
    dispatcher = _Dispatcher(fail=True)

    result = await _coordinator(_Service(accepted), _Jobs(_snapshot()), dispatcher).create(
        _command()
    )

    assert result.job.status == "PENDING"
    assert len(dispatcher.messages) == 1


@pytest.mark.asyncio
async def test_terminal_replay_is_not_redispatched() -> None:
    accepted = DemoProfileRebuildAccepted(
        job_id="b" * 32,
        request_id="durable-memory-request",
        replayed=True,
    )
    dispatcher = _Dispatcher()

    result = await _coordinator(
        _Service(accepted), _Jobs(_snapshot(status="COMPLETED")), dispatcher
    ).create(_command())

    assert result.job.status == "COMPLETED"
    assert dispatcher.messages == []


@pytest.mark.asyncio
async def test_reconciler_surfaces_dispatch_failure() -> None:
    accepted = DemoProfileRebuildAccepted("b" * 32, "durable-memory-request", True)
    candidates = (
        DemoMemoryReconciliationCandidate("a" * 32, "b" * 32, "first-request"),
        DemoMemoryReconciliationCandidate("e" * 32, "f" * 32, "second-request"),
    )
    dispatcher = _Dispatcher()
    coordinator = _coordinator(_Service(accepted, candidates), _Jobs(_snapshot()), dispatcher)

    assert await coordinator.reconcile() == ("b" * 32, "f" * 32)
    assert [message.job_id for message in dispatcher.messages] == ["b" * 32, "f" * 32]

    failing = _coordinator(
        _Service(accepted, candidates), _Jobs(_snapshot()), _Dispatcher(fail=True)
    )
    with pytest.raises(RuntimeError, match="broker unavailable"):
        await failing.reconcile()
