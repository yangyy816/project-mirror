"""Worker-boundary tests for deterministic Demo P5 profile compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from mirror_api.config import Settings
from mirror_api.demo_profile_service import (
    DemoProfileAuthorityCorruption,
    DemoProfileCompilationResult,
    DemoProfileRejected,
    DemoProfileUnavailable,
)
from mirror_api.demo_profile_task_contract import (
    DEMO_PROFILE_TASK_SCHEMA,
    DemoProfileTaskMessage,
)

from mirror_worker import runtime as runtime_module
from mirror_worker.celery_adapter import (
    CeleryTaskDispatcher,
    celery_app,
    compile_demo_profile,
    reconcile_demo_profile,
)
from mirror_worker.demo_profile import DemoProfileTaskExecutor
from mirror_worker.local import LocalTaskRunner

_ACTOR_ID = "a" * 32
_JOB_ID = "b" * 32
_REQUEST_ID = "d05-profile-worker-request"


def _message() -> DemoProfileTaskMessage:
    return DemoProfileTaskMessage(
        demo_actor_id=_ACTOR_ID,
        job_id=_JOB_ID,
        request_id=_REQUEST_ID,
    )


def _result(*, replayed: bool = False) -> DemoProfileCompilationResult:
    return DemoProfileCompilationResult(
        job_id=_JOB_ID,
        bundle_id="c" * 32,
        desired_delta_profile_id="d" * 32,
        style_profile_id="e" * 32,
        persistent_constraints_id="f" * 32,
        session_override_constraints_id="1" * 32,
        compilation_digest="2" * 64,
        replayed=replayed,
    )


class _Application:
    def __init__(
        self,
        *,
        result: DemoProfileCompilationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or _result()
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def compile(self, *, demo_actor_id: str, job_id: str) -> DemoProfileCompilationResult:
        self.calls.append((demo_actor_id, job_id))
        if self.error is not None:
            raise self.error
        return self.result


def test_profile_task_contract_is_strict_and_reference_only() -> None:
    message = _message()
    assert message.to_message() == {
        "demo_actor_id": _ACTOR_ID,
        "job_id": _JOB_ID,
        "request_id": _REQUEST_ID,
        "schema_version": DEMO_PROFILE_TASK_SCHEMA,
    }
    assert DemoProfileTaskMessage.from_message(message.to_message()) == message

    with pytest.raises(ValueError, match="invalid shape"):
        DemoProfileTaskMessage.from_message(
            {**message.to_message(), "private_payload": "forbidden"}
        )
    with pytest.raises(ValueError, match="identifiers must be opaque"):
        DemoProfileTaskMessage(
            demo_actor_id="actor-name",
            job_id=_JOB_ID,
            request_id=_REQUEST_ID,
        ).validate()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (DemoProfileRejected("invalid authority"), "REJECTED"),
        (DemoProfileAuthorityCorruption("corrupt authority"), "FAILED"),
        (DemoProfileUnavailable("cancelled or terminal"), "NO_OP"),
    ],
)
async def test_executor_maps_durable_terminal_and_noop_outcomes(
    error: Exception, expected_status: str
) -> None:
    application = _Application(error=error)

    result = await DemoProfileTaskExecutor(application=application).execute(_message())

    assert result.status == expected_status
    assert result.bundle_id is None
    assert result.compilation_digest is None
    assert application.calls == [(_ACTOR_ID, _JOB_ID)]


@pytest.mark.asyncio
async def test_executor_propagates_unexpected_failure_for_reconciliation() -> None:
    application = _Application(error=RuntimeError("transient database failure"))

    with pytest.raises(RuntimeError, match="transient database failure"):
        await DemoProfileTaskExecutor(application=application).execute(_message())

    assert application.calls == [(_ACTOR_ID, _JOB_ID)]


@pytest.mark.asyncio
async def test_executor_returns_only_opaque_completed_publication() -> None:
    application = _Application()

    result = await DemoProfileTaskExecutor(application=application).execute(_message())

    assert result.status == "COMPLETED"
    assert result.demo_actor_id == _ACTOR_ID
    assert result.job_id == _JOB_ID
    assert result.bundle_id == "c" * 32
    assert result.compilation_digest == "2" * 64


@pytest.mark.asyncio
async def test_duplicate_delivery_relies_on_durable_replay_without_second_publication() -> None:
    application = _Application(result=_result(replayed=True))
    executor = DemoProfileTaskExecutor(application=application)

    first = await executor.execute(_message())
    second = await executor.execute(_message())

    assert (first.status, first.bundle_id, first.compilation_digest) == (
        second.status,
        second.bundle_id,
        second.compilation_digest,
    )
    assert application.calls == [(_ACTOR_ID, _JOB_ID), (_ACTOR_ID, _JOB_ID)]


def test_local_runner_dispatches_only_strict_profile_message(
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
            "bundle_id": None,
            "compilation_digest": None,
        }

    monkeypatch.setattr("mirror_worker.local.run_demo_profile_message", fake_run)
    runner = LocalTaskRunner(Settings(app_env="test"))

    assert runner.dispatch_demo_profile(_message()) == _JOB_ID
    assert captured == [_message().to_message()]


def test_celery_registration_routes_and_dispatch_preserve_opaque_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert {"mirror.demo_profile.compile", "mirror.demo_profile.reconcile"} <= set(celery_app.tasks)
    assert celery_app.conf.task_routes["mirror.demo_profile.compile"]["queue"] == "mirror.demo"
    assert (
        celery_app.conf.task_routes["mirror.demo_profile.reconcile"]["queue"]
        == "mirror.maintenance"
    )
    assert compile_demo_profile.acks_late is True
    assert compile_demo_profile.reject_on_worker_lost is True
    assert reconcile_demo_profile.acks_late is True
    assert reconcile_demo_profile.reject_on_worker_lost is True

    captured: dict[str, object] = {}

    def fake_apply_async(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(compile_demo_profile, "apply_async", fake_apply_async)
    assert CeleryTaskDispatcher().dispatch_demo_profile(_message()) == _JOB_ID
    assert captured["args"] == [_message().to_message()]
    assert captured["headers"] == {"request_id": _REQUEST_ID, "job_id": _JOB_ID}
    assert captured["queue"] == "mirror.demo"


@dataclass(frozen=True)
class _Candidate:
    demo_actor_id: str
    job_id: str
    request_id: str


class _Commands:
    async def reconciliation_candidates(self, *, limit: int) -> tuple[_Candidate, ...]:
        assert limit == 2
        return (
            _Candidate(_ACTOR_ID, _JOB_ID, _REQUEST_ID),
            _Candidate("c" * 32, "d" * 32, "second-profile-request"),
        )


class _Engine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


@dataclass(frozen=True)
class _Runtime:
    engine: _Engine
    commands: _Commands


class _Dispatcher:
    def __init__(self) -> None:
        self.messages: list[DemoProfileTaskMessage] = []

    def dispatch_demo_profile(self, message: DemoProfileTaskMessage) -> str:
        self.messages.append(message)
        return cast(str, message.job_id)


@pytest.mark.asyncio
async def test_reconciliation_dispatches_only_reference_messages_and_disposes_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine()
    monkeypatch.setattr(
        runtime_module,
        "create_demo_profile_runtime",
        lambda settings: _Runtime(engine=engine, commands=_Commands()),
    )
    dispatcher = _Dispatcher()

    dispatched = await runtime_module.run_demo_profile_reconciliation(
        dispatcher=dispatcher,
        limit=2,
        settings=Settings(app_env="test"),
    )

    assert dispatched == (_JOB_ID, "d" * 32)
    assert [message.to_message() for message in dispatcher.messages] == [
        _message().to_message(),
        DemoProfileTaskMessage(
            demo_actor_id="c" * 32,
            job_id="d" * 32,
            request_id="second-profile-request",
        ).to_message(),
    ]
    assert engine.disposed is True
