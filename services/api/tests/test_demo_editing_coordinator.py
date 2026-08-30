from __future__ import annotations

from dataclasses import dataclass

import pytest

from mirror_api.demo_editing_commands import (
    CreateDemoEditingSession,
    DemoEditingCommandAccepted,
    DemoEditingPendingJob,
)
from mirror_api.demo_editing_coordinator import DemoEditingCoordinator
from mirror_api.demo_editing_task_contract import DemoEditingTaskMessage

_ID = "a" * 32


@dataclass
class _Job:
    status: str


class _Commands:
    def __init__(self, *, replayed: bool = False) -> None:
        self.replayed = replayed
        self.pending = (
            DemoEditingPendingJob(
                demo_actor_id=_ID,
                demo_session_id="b" * 32,
                job_id="c" * 32,
                endpoint_operation="edit_plan.execute",
                target_id="d" * 32,
                request_id="authority-request-01",
            ),
        )

    async def create_editing_session(self, _: object) -> DemoEditingCommandAccepted:
        return DemoEditingCommandAccepted(
            job_id="e" * 32,
            target_id="f" * 32,
            request_id="authority-request-01",
            replayed=self.replayed,
        )

    async def reconciliation_candidates(self, *, limit: int) -> tuple[DemoEditingPendingJob, ...]:
        assert limit == 10
        return self.pending


class _Jobs:
    async def get(self, **_: str) -> _Job:
        return _Job(status="PENDING")


class _Dispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[DemoEditingTaskMessage] = []

    def dispatch_demo_editing(self, message: DemoEditingTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("broker unavailable")
        return message.job_id


def _coordinator(dispatcher: _Dispatcher, *, replayed: bool = False) -> DemoEditingCoordinator:
    return DemoEditingCoordinator(
        commands=_Commands(replayed=replayed),  # type: ignore[arg-type]
        jobs=_Jobs(),  # type: ignore[arg-type]
        dispatcher=dispatcher,
    )


def _session_command() -> CreateDemoEditingSession:
    return CreateDemoEditingSession(
        demo_actor_id=_ID,
        demo_session_id="b" * 32,
        source_asset_id="c" * 32,
        idempotency_key="idempotency-key-01",
        request_id="http-request-02",
    )


@pytest.mark.asyncio
async def test_create_uses_authority_request_id_for_replay() -> None:
    dispatcher = _Dispatcher()
    result = await _coordinator(dispatcher, replayed=True).create_editing_session(
        _session_command()
    )
    assert result.replayed is True
    assert dispatcher.messages[0].request_id == "authority-request-01"
    assert dispatcher.messages[0].operation == "editing_session.create"


@pytest.mark.asyncio
async def test_dispatch_failure_keeps_accepted_result() -> None:
    dispatcher = _Dispatcher(fail=True)
    result = await _coordinator(dispatcher).create_editing_session(_session_command())
    assert result.job.status == "PENDING"
    assert len(dispatcher.messages) == 1


@pytest.mark.asyncio
async def test_reconcile_redispatches_only_command_projection() -> None:
    dispatcher = _Dispatcher()
    jobs = await _coordinator(dispatcher).reconcile(limit=10)
    assert jobs == ("c" * 32,)
    assert dispatcher.messages[0].request_id == "authority-request-01"


@pytest.mark.asyncio
async def test_reconcile_raises_for_dispatch_failure() -> None:
    with pytest.raises(RuntimeError, match="broker unavailable"):
        await _coordinator(_Dispatcher(fail=True)).reconcile(limit=10)
