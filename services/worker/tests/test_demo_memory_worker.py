"""Worker-boundary tests for deterministic Demo D10 Profile rebuilds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from mirror_api.config import Settings
from mirror_api.demo_memory_service import (
    DemoAestheticProfileResult,
    DemoMemoryAuthorityCorruption,
    DemoMemoryConflict,
    DemoMemoryInputError,
    DemoMemoryUnavailable,
)
from mirror_api.demo_memory_task_contract import (
    DEMO_MEMORY_TASK_SCHEMA,
    DemoMemoryTaskMessage,
)

from mirror_worker import runtime as runtime_module
from mirror_worker.celery_adapter import (
    CeleryTaskDispatcher,
    celery_app,
    rebuild_demo_memory,
    reconcile_demo_memory,
)
from mirror_worker.demo_memory import DemoMemoryTaskExecutor
from mirror_worker.local import LocalTaskRunner

_ACTOR_ID = "a" * 32
_JOB_ID = "b" * 32
_REQUEST_ID = "d10-memory-worker-request"


def _message() -> DemoMemoryTaskMessage:
    return DemoMemoryTaskMessage(
        demo_actor_id=_ACTOR_ID,
        job_id=_JOB_ID,
        request_id=_REQUEST_ID,
    )


def _profile_result(*, replayed: bool = False) -> DemoAestheticProfileResult:
    return DemoAestheticProfileResult(
        job_id=_JOB_ID,
        aesthetic_profile_id="c" * 32,
        generation=2,
        compilation_watermark="d" * 64,
        profile_digest="e" * 64,
        replayed=replayed,
    )


class _Application:
    def __init__(
        self,
        *,
        result: DemoAestheticProfileResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or _profile_result()
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def execute_rebuild(
        self, *, demo_actor_id: str, job_id: str
    ) -> DemoAestheticProfileResult:
        self.calls.append((demo_actor_id, job_id))
        if self.error is not None:
            raise self.error
        return self.result


def test_memory_task_contract_is_strict_and_reference_only() -> None:
    message = _message()
    assert message.to_message() == {
        "demo_actor_id": _ACTOR_ID,
        "job_id": _JOB_ID,
        "request_id": _REQUEST_ID,
        "schema_version": DEMO_MEMORY_TASK_SCHEMA,
    }
    assert DemoMemoryTaskMessage.from_message(message.to_message()) == message

    with pytest.raises(ValueError, match="invalid shape"):
        DemoMemoryTaskMessage.from_message({**message.to_message(), "profile_payload": "forbidden"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (DemoMemoryInputError("invalid request"), "REJECTED"),
        (DemoMemoryConflict("ineligible rebuild"), "REJECTED"),
        (DemoMemoryAuthorityCorruption("corrupt authority"), "FAILED"),
        (DemoMemoryUnavailable("terminal or missing"), "NO_OP"),
    ],
)
async def test_executor_maps_durable_terminal_and_noop_outcomes(
    error: Exception, expected_status: str
) -> None:
    application = _Application(error=error)

    result = await DemoMemoryTaskExecutor(application=application).execute(_message())

    assert result.status == expected_status
    assert result.aesthetic_profile_id is None
    assert result.profile_digest is None
    assert application.calls == [(_ACTOR_ID, _JOB_ID)]


@pytest.mark.asyncio
async def test_executor_propagates_unexpected_failure_for_redelivery() -> None:
    application = _Application(error=RuntimeError("transient database failure"))

    with pytest.raises(RuntimeError, match="transient database failure"):
        await DemoMemoryTaskExecutor(application=application).execute(_message())


@pytest.mark.asyncio
async def test_executor_returns_only_opaque_completed_publication() -> None:
    result = await DemoMemoryTaskExecutor(application=_Application()).execute(_message())

    assert result.status == "COMPLETED"
    assert result.demo_actor_id == _ACTOR_ID
    assert result.job_id == _JOB_ID
    assert result.aesthetic_profile_id == "c" * 32
    assert result.profile_digest == "e" * 64


def test_local_runner_dispatches_only_strict_memory_message(
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
            "aesthetic_profile_id": None,
            "profile_digest": None,
        }

    monkeypatch.setattr("mirror_worker.local.run_demo_memory_message", fake_run)
    runner = LocalTaskRunner(Settings(app_env="test"))

    assert runner.dispatch_demo_memory(_message()) == _JOB_ID
    assert captured == [_message().to_message()]


def test_celery_registration_routes_and_dispatch_preserve_opaque_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert {"mirror.demo_memory.rebuild", "mirror.demo_memory.reconcile"} <= set(celery_app.tasks)
    assert celery_app.conf.task_routes["mirror.demo_memory.rebuild"]["queue"] == "mirror.demo"
    assert (
        celery_app.conf.task_routes["mirror.demo_memory.reconcile"]["queue"] == "mirror.maintenance"
    )
    assert rebuild_demo_memory.acks_late is True
    assert rebuild_demo_memory.reject_on_worker_lost is True
    assert reconcile_demo_memory.acks_late is True
    assert reconcile_demo_memory.reject_on_worker_lost is True

    captured: dict[str, object] = {}

    def fake_apply_async(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(rebuild_demo_memory, "apply_async", fake_apply_async)
    assert CeleryTaskDispatcher().dispatch_demo_memory(_message()) == _JOB_ID
    assert captured["args"] == [_message().to_message()]
    assert captured["headers"] == {"request_id": _REQUEST_ID, "job_id": _JOB_ID}
    assert captured["queue"] == "mirror.demo"


@dataclass(frozen=True)
class _Candidate:
    demo_actor_id: str
    job_id: str
    request_id: str


class _ReconciliationApplication:
    async def reconciliation_candidates(self, *, limit: int) -> tuple[_Candidate, ...]:
        assert limit == 2
        return (
            _Candidate(_ACTOR_ID, _JOB_ID, _REQUEST_ID),
            _Candidate("c" * 32, "d" * 32, "second-memory-request"),
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
        self.messages: list[DemoMemoryTaskMessage] = []

    def dispatch_demo_memory(self, message: DemoMemoryTaskMessage) -> str:
        self.messages.append(message)
        return cast(str, message.job_id)


@pytest.mark.asyncio
async def test_reconciliation_dispatches_only_reference_messages_and_disposes_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine()
    monkeypatch.setattr(
        runtime_module,
        "create_demo_memory_runtime",
        lambda settings: _Runtime(engine=engine, application=_ReconciliationApplication()),
    )
    dispatcher = _Dispatcher()

    dispatched = await runtime_module.run_demo_memory_reconciliation(
        dispatcher=dispatcher,
        limit=2,
        settings=Settings(app_env="test"),
    )

    assert dispatched == (_JOB_ID, "d" * 32)
    assert [message.to_message() for message in dispatcher.messages] == [
        _message().to_message(),
        DemoMemoryTaskMessage(
            demo_actor_id="c" * 32,
            job_id="d" * 32,
            request_id="second-memory-request",
        ).to_message(),
    ]
    assert engine.disposed is True
