from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from mirror_api.config import Settings
from mirror_api.demo_context_queue_service import (
    DemoContextExecutionResult,
    DemoContextReconciliationCandidate,
)
from mirror_api.demo_context_task_contract import DemoContextDispatcher, DemoContextTaskMessage

from mirror_worker import runtime as runtime_module
from mirror_worker.celery_adapter import (
    CeleryTaskDispatcher,
    celery_app,
    compile_demo_context,
    reconcile_demo_context,
)
from mirror_worker.demo_context import DemoContextTaskExecutor
from mirror_worker.local import LocalTaskRunner


@dataclass
class _Application:
    calls: list[tuple[str, str, str]]

    async def execute_task(
        self, *, demo_actor_id: str, job_id: str, context_request_id: str
    ) -> DemoContextExecutionResult:
        self.calls.append((demo_actor_id, job_id, context_request_id))
        return DemoContextExecutionResult(
            demo_actor_id,
            job_id,
            context_request_id,
            "COMPLETED",
            "CONTEXT_COMPILED",
            "c" * 32,
            "d" * 64,
        )


@pytest.mark.asyncio
async def test_context_worker_maps_only_opaque_envelope() -> None:
    application = _Application([])
    message = DemoContextTaskMessage("a" * 32, "b" * 32, "c" * 32, "request-01")

    result = await DemoContextTaskExecutor(application=application).execute(message)

    assert application.calls == [("a" * 32, "b" * 32, "c" * 32)]
    assert result.status == "COMPLETED"
    assert result.context_digest == "d" * 64


def test_context_task_envelope_rejects_payload_expansion() -> None:
    message = DemoContextTaskMessage("a" * 32, "b" * 32, "c" * 32, "request-01")
    payload: dict[str, object] = message.to_message() | {"selected_evidence": []}

    with pytest.raises(ValueError, match="invalid shape"):
        DemoContextTaskMessage.from_message(payload)


def test_context_celery_registration_and_dispatch_are_reference_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert {"mirror.demo_context.compile", "mirror.demo_context.reconcile"} <= set(celery_app.tasks)
    assert celery_app.conf.task_routes["mirror.demo_context.compile"]["queue"] == "mirror.demo"
    assert (
        celery_app.conf.task_routes["mirror.demo_context.reconcile"]["queue"]
        == "mirror.maintenance"
    )
    assert compile_demo_context.acks_late is True
    assert compile_demo_context.reject_on_worker_lost is True
    assert reconcile_demo_context.acks_late is True
    assert reconcile_demo_context.reject_on_worker_lost is True

    captured: dict[str, object] = {}

    def fake_apply_async(**kwargs: object) -> None:
        captured.update(kwargs)

    message = DemoContextTaskMessage("a" * 32, "b" * 32, "c" * 32, "request-01")
    monkeypatch.setattr(compile_demo_context, "apply_async", fake_apply_async)

    assert CeleryTaskDispatcher().dispatch_demo_context(message) == message.job_id
    assert captured["args"] == [message.to_message()]
    assert captured["headers"] == {
        "request_id": message.request_id,
        "job_id": message.job_id,
    }
    assert captured["queue"] == "mirror.demo"


def test_context_local_runner_executes_only_opaque_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, str]] = []

    async def fake_run(message: dict[str, str], *, settings: Settings) -> dict[str, str | None]:
        assert settings.app_env == "test"
        captured.append(message)
        return {
            "demo_actor_id": message["demo_actor_id"],
            "job_id": message["job_id"],
            "status": "NO_OP",
            "result_code": None,
            "context_compilation_id": None,
            "context_digest": None,
        }

    monkeypatch.setattr("mirror_worker.local.run_demo_context_message", fake_run)
    message = DemoContextTaskMessage("a" * 32, "b" * 32, "c" * 32, "request-01")

    runner = LocalTaskRunner(Settings(app_env="test"))

    assert runner.dispatch_demo_context(message) == message.job_id
    assert captured == [message.to_message()]


class _ReconciliationApplication:
    async def reconciliation_candidates(
        self, *, limit: int
    ) -> tuple[DemoContextReconciliationCandidate, ...]:
        assert limit == 2
        return (
            DemoContextReconciliationCandidate(
                "a" * 32,
                "b" * 32,
                "c" * 32,
                "request-01",
            ),
            DemoContextReconciliationCandidate(
                "e" * 32,
                "f" * 32,
                "1" * 32,
                "request-02",
            ),
        )


class _Engine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


@dataclass(frozen=True)
class _Runtime:
    engine: _Engine
    application: _ReconciliationApplication


class _Dispatcher:
    def __init__(self) -> None:
        self.messages: list[DemoContextTaskMessage] = []

    def dispatch_demo_context(self, message: DemoContextTaskMessage) -> str:
        self.messages.append(message)
        return message.job_id


@pytest.mark.asyncio
async def test_context_reconciliation_dispatches_references_and_disposes_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine()
    monkeypatch.setattr(
        runtime_module,
        "create_demo_context_runtime",
        lambda settings: _Runtime(engine, _ReconciliationApplication()),
    )
    dispatcher = _Dispatcher()

    dispatched = await runtime_module.run_demo_context_reconciliation(
        dispatcher=cast(DemoContextDispatcher, dispatcher),
        limit=2,
        settings=Settings(app_env="test"),
    )

    assert dispatched == ("b" * 32, "f" * 32)
    assert [message.to_message() for message in dispatcher.messages] == [
        DemoContextTaskMessage("a" * 32, "b" * 32, "c" * 32, "request-01").to_message(),
        DemoContextTaskMessage("e" * 32, "f" * 32, "1" * 32, "request-02").to_message(),
    ]
    assert engine.disposed is True
