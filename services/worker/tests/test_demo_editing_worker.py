from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from mirror_api.config import Settings
from mirror_api.demo_editing_runtime import DemoEditingRuntimeResult
from mirror_api.demo_editing_task_contract import DemoEditingTaskMessage

import mirror_worker.runtime as runtime_module
from mirror_worker.celery_adapter import (
    CeleryTaskDispatcher,
    celery_app,
    process_demo_editing,
    reconcile_demo_editing,
)
from mirror_worker.local import LocalTaskRunner

_ACTOR_ID = "a" * 32
_JOB_ID = "b" * 32
_REQUEST_ID = "d07-worker-request"


def _message() -> DemoEditingTaskMessage:
    return DemoEditingTaskMessage(
        demo_actor_id=_ACTOR_ID,
        job_id=_JOB_ID,
        operation="edit_plan.execute",
        request_id=_REQUEST_ID,
    )


def test_local_runner_dispatches_only_reference_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, str]] = []

    async def fake_run(
        message: dict[str, str], *, settings: Settings
    ) -> dict[str, str | bool | None]:
        assert settings.app_env == "test"
        captured.append(message)
        return {
            "job_id": message["job_id"],
            "status": "COMPLETED",
            "result_code": "EDIT_EXECUTION_COMPLETED",
            "executed": True,
            "replayed": False,
        }

    monkeypatch.setattr("mirror_worker.local.run_demo_editing_message", fake_run)
    runner = LocalTaskRunner(Settings(app_env="test"))

    assert runner.dispatch_demo_editing(_message()) == _JOB_ID
    assert captured == [_message().to_message()]


def test_celery_registration_routes_and_dispatch_preserve_opaque_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert {"mirror.demo_editing.process", "mirror.demo_editing.reconcile"} <= set(celery_app.tasks)
    assert celery_app.conf.task_routes["mirror.demo_editing.process"]["queue"] == "mirror.demo"
    assert (
        celery_app.conf.task_routes["mirror.demo_editing.reconcile"]["queue"]
        == "mirror.maintenance"
    )
    assert process_demo_editing.acks_late is True
    assert process_demo_editing.reject_on_worker_lost is True
    assert reconcile_demo_editing.acks_late is True
    assert reconcile_demo_editing.reject_on_worker_lost is True

    captured: dict[str, object] = {}

    def fake_apply_async(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(process_demo_editing, "apply_async", fake_apply_async)
    assert CeleryTaskDispatcher().dispatch_demo_editing(_message()) == _JOB_ID
    assert captured["args"] == [_message().to_message()]
    assert captured["headers"] == {"request_id": _REQUEST_ID, "job_id": _JOB_ID}
    assert captured["queue"] == "mirror.demo"


class _Engine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _Application:
    def __init__(self) -> None:
        self.messages: list[DemoEditingTaskMessage] = []

    async def run(self, message: DemoEditingTaskMessage) -> DemoEditingRuntimeResult:
        self.messages.append(message)
        return DemoEditingRuntimeResult(
            job_id=message.job_id,
            status="COMPLETED",
            result_code="EDIT_EXECUTION_COMPLETED",
            executed=True,
            replayed=False,
        )


@dataclass(frozen=True)
class _Candidate:
    demo_actor_id: str
    demo_session_id: str
    job_id: str
    endpoint_operation: str
    target_id: str
    request_id: str


class _Commands:
    async def reconciliation_candidates(self, *, limit: int) -> tuple[_Candidate, ...]:
        assert limit == 2
        return (
            _Candidate(
                _ACTOR_ID,
                "c" * 32,
                _JOB_ID,
                "edit_plan.execute",
                "d" * 32,
                _REQUEST_ID,
            ),
            _Candidate(
                "e" * 32,
                "f" * 32,
                "1" * 32,
                "image_version.restore",
                "2" * 32,
                "d07-second-request",
            ),
        )


@dataclass(frozen=True)
class _Runtime:
    engine: _Engine
    application: _Application
    commands: _Commands


class _Dispatcher:
    def __init__(self) -> None:
        self.messages: list[DemoEditingTaskMessage] = []

    def dispatch_demo_editing(self, message: DemoEditingTaskMessage) -> str:
        self.messages.append(message)
        return cast(str, message.job_id)


@pytest.mark.asyncio
async def test_runtime_message_and_reconciliation_dispose_and_preserve_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message_engine = _Engine()
    application = _Application()
    monkeypatch.setattr(
        runtime_module,
        "create_demo_editing_runtime",
        lambda settings: _Runtime(message_engine, application, _Commands()),
    )
    result = await runtime_module.run_demo_editing_message(
        _message().to_message(), settings=Settings(app_env="test")
    )
    assert result == {
        "job_id": _JOB_ID,
        "status": "COMPLETED",
        "result_code": "EDIT_EXECUTION_COMPLETED",
        "executed": True,
        "replayed": False,
    }
    assert application.messages == [_message()]
    assert message_engine.disposed is True

    reconciliation_engine = _Engine()
    monkeypatch.setattr(
        runtime_module,
        "create_demo_editing_runtime",
        lambda settings: _Runtime(reconciliation_engine, _Application(), _Commands()),
    )
    dispatcher = _Dispatcher()
    dispatched = await runtime_module.run_demo_editing_reconciliation(
        dispatcher=dispatcher,
        limit=2,
        settings=Settings(app_env="test"),
    )
    assert dispatched == (_JOB_ID, "1" * 32)
    assert [message.to_message() for message in dispatcher.messages] == [
        _message().to_message(),
        DemoEditingTaskMessage(
            demo_actor_id="e" * 32,
            job_id="1" * 32,
            operation="image_version.restore",
            request_id="d07-second-request",
        ).to_message(),
    ]
    assert reconciliation_engine.disposed is True
