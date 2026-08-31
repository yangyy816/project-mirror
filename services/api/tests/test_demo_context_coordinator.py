from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

import pytest

from mirror_api.demo_context_coordinator import DemoContextCoordinator
from mirror_api.demo_context_queue_service import (
    CreateDemoContextCompilation,
    DemoContextCompilationAccepted,
    DemoContextQueueService,
    DemoContextReconciliationCandidate,
)
from mirror_api.demo_context_task_contract import DemoContextDispatcher, DemoContextTaskMessage
from mirror_api.demo_job_service import (
    DemoJobService,
    DemoJobSnapshot,
    DemoJobStatus,
    DemoJobTargetSnapshot,
)


def _command() -> CreateDemoContextCompilation:
    return CreateDemoContextCompilation(
        demo_actor_id="a" * 32,
        demo_session_id="b" * 32,
        aesthetic_profile_id="c" * 32,
        current_instruction_digest="d" * 64,
        context_as_of_time=datetime(2026, 9, 1, tzinfo=UTC),
        idempotency_key="context-coordinator-key",
        request_id="context-http-request",
    )


def _snapshot(*, status: str = "PENDING") -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id="e" * 32,
        demo_actor_id="a" * 32,
        demo_session_id="b" * 32,
        status=cast(DemoJobStatus, status),
        capability="P7_CONTEXT_COMPILER",
        job_binding_digest="f" * 64,
        target=DemoJobTargetSnapshot("DEMO_SESSION", "b" * 32, "1" * 64),
        result_code=None,
        finalized_at=None,
    )


@dataclass
class _Service:
    accepted: DemoContextCompilationAccepted
    candidates: tuple[DemoContextReconciliationCandidate, ...] = ()

    async def admit(self, command: CreateDemoContextCompilation) -> DemoContextCompilationAccepted:
        assert command == _command()
        return self.accepted

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoContextReconciliationCandidate, ...]:
        assert limit == 100
        return self.candidates


@dataclass
class _Jobs:
    snapshot: DemoJobSnapshot

    async def get(self, *, demo_actor_id: str, job_id: str) -> DemoJobSnapshot:
        assert (demo_actor_id, job_id) == ("a" * 32, "e" * 32)
        return self.snapshot


@dataclass
class _Dispatcher:
    fail: bool = False
    messages: list[DemoContextTaskMessage] = field(default_factory=list)

    def dispatch_demo_context(self, message: DemoContextTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("broker unavailable")
        return message.job_id


def _coordinator(service: _Service, jobs: _Jobs, dispatcher: _Dispatcher) -> DemoContextCoordinator:
    return DemoContextCoordinator(
        service=cast(DemoContextQueueService, service),
        jobs=cast(DemoJobService, jobs),
        dispatcher=cast(DemoContextDispatcher, dispatcher),
    )


@pytest.mark.asyncio
async def test_pending_context_admission_dispatches_only_opaque_reference() -> None:
    accepted = DemoContextCompilationAccepted(
        "e" * 32,
        "2" * 32,
        "context-http-request",
        False,
    )
    dispatcher = _Dispatcher()

    result = await _coordinator(_Service(accepted), _Jobs(_snapshot()), dispatcher).create(
        _command()
    )

    assert result.job.status == "PENDING"
    assert dispatcher.messages == [
        DemoContextTaskMessage(
            "a" * 32,
            "e" * 32,
            "2" * 32,
            "context-http-request",
        )
    ]


@pytest.mark.asyncio
async def test_context_dispatch_failure_preserves_pending_and_terminal_is_not_redispatched() -> (
    None
):
    accepted = DemoContextCompilationAccepted("e" * 32, "2" * 32, "context-http-request", True)
    failing = _Dispatcher(fail=True)

    pending = await _coordinator(_Service(accepted), _Jobs(_snapshot()), failing).create(_command())
    terminal_dispatcher = _Dispatcher()
    terminal = await _coordinator(
        _Service(accepted),
        _Jobs(_snapshot(status="COMPLETED")),
        terminal_dispatcher,
    ).create(_command())

    assert pending.job.status == "PENDING" and len(failing.messages) == 1
    assert terminal.job.status == "COMPLETED" and terminal_dispatcher.messages == []


@pytest.mark.asyncio
async def test_context_reconciler_dispatches_all_and_surfaces_broker_failure() -> None:
    accepted = DemoContextCompilationAccepted("e" * 32, "2" * 32, "context-http-request", True)
    candidates = (
        DemoContextReconciliationCandidate("a" * 32, "e" * 32, "2" * 32, "request-1"),
        DemoContextReconciliationCandidate("3" * 32, "4" * 32, "5" * 32, "request-2"),
    )
    dispatcher = _Dispatcher()
    coordinator = _coordinator(_Service(accepted, candidates), _Jobs(_snapshot()), dispatcher)

    assert await coordinator.reconcile() == ("e" * 32, "4" * 32)
    assert [message.job_id for message in dispatcher.messages] == ["e" * 32, "4" * 32]

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await _coordinator(
            _Service(accepted, candidates),
            _Jobs(_snapshot()),
            _Dispatcher(fail=True),
        ).reconcile()
