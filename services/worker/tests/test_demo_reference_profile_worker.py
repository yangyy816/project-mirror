from __future__ import annotations

from dataclasses import dataclass

import pytest
from mirror_api.config import Settings
from mirror_api.demo_reference_profile_service import DemoReferenceProfileExecutionResult
from mirror_api.demo_reference_profile_task_contract import DemoReferenceProfileTaskMessage

from mirror_worker.celery_adapter import (
    CeleryTaskDispatcher,
    celery_app,
    compile_demo_reference_profile,
    reconcile_demo_reference_profile,
)
from mirror_worker.demo_reference_profile import DemoReferenceProfileTaskExecutor
from mirror_worker.local import LocalTaskRunner


@dataclass
class _Application:
    result: DemoReferenceProfileExecutionResult
    calls: list[tuple[str, str, str]]

    async def execute_task(
        self, *, demo_actor_id: str, job_id: str, compile_request_id: str
    ) -> DemoReferenceProfileExecutionResult:
        self.calls.append((demo_actor_id, job_id, compile_request_id))
        return self.result


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["COMPLETED", "REJECTED", "FAILED", "CANCELLED", "NO_OP"])
async def test_executor_preserves_reference_only_execution_status(status: str) -> None:
    message = DemoReferenceProfileTaskMessage(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        compile_request_id="c" * 32,
        request_id="d06-worker-request",
    )
    application = _Application(
        DemoReferenceProfileExecutionResult(
            demo_actor_id=message.demo_actor_id,
            job_id=message.job_id,
            compile_request_id=message.compile_request_id,
            status=status,  # type: ignore[arg-type]
            result_code="REFERENCE_PROFILE_COMPILED" if status == "COMPLETED" else None,
            reference_profile_id="d" * 32 if status == "COMPLETED" else None,
            profile_digest="e" * 64 if status == "COMPLETED" else None,
        ),
        [],
    )

    result = await DemoReferenceProfileTaskExecutor(application=application).execute(message)

    assert application.calls == [
        (message.demo_actor_id, message.job_id, message.compile_request_id)
    ]
    assert result.status == status
    assert result.reference_profile_id == application.result.reference_profile_id
    assert result.profile_digest == application.result.profile_digest


def test_task_message_is_exact_opaque_reference_only_envelope() -> None:
    message = DemoReferenceProfileTaskMessage(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        compile_request_id="c" * 32,
        request_id="d06-worker-request",
    )

    assert message.to_message() == {
        "demo_actor_id": "a" * 32,
        "job_id": "b" * 32,
        "compile_request_id": "c" * 32,
        "request_id": "d06-worker-request",
        "schema_version": "demo-reference-profile-task-v1",
    }
    with pytest.raises(ValueError, match="invalid shape"):
        DemoReferenceProfileTaskMessage.from_message(
            {**message.to_message(), "source_asset": "must-not-cross-boundary"}
        )
    with pytest.raises(ValueError, match="opaque"):
        DemoReferenceProfileTaskMessage.from_message(
            {**message.to_message(), "job_id": "not-an-opaque-id"}
        )


def test_celery_registration_and_dispatch_preserve_reference_only_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert {
        "mirror.demo_reference_profile.compile",
        "mirror.demo_reference_profile.reconcile",
    } <= set(celery_app.tasks)
    assert (
        celery_app.conf.task_routes["mirror.demo_reference_profile.compile"]["queue"]
        == "mirror.demo"
    )
    assert (
        celery_app.conf.task_routes["mirror.demo_reference_profile.reconcile"]["queue"]
        == "mirror.maintenance"
    )
    assert compile_demo_reference_profile.acks_late is True
    assert compile_demo_reference_profile.reject_on_worker_lost is True
    assert reconcile_demo_reference_profile.acks_late is True
    assert reconcile_demo_reference_profile.reject_on_worker_lost is True

    captured: dict[str, object] = {}

    def fake_apply_async(**kwargs: object) -> None:
        captured.update(kwargs)

    message = DemoReferenceProfileTaskMessage(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        compile_request_id="c" * 32,
        request_id="d06-worker-request",
    )
    monkeypatch.setattr(compile_demo_reference_profile, "apply_async", fake_apply_async)
    assert CeleryTaskDispatcher().dispatch_demo_reference_profile(message) == message.job_id
    assert captured["args"] == [message.to_message()]
    assert captured["headers"] == {
        "request_id": message.request_id,
        "job_id": message.job_id,
    }
    assert captured["queue"] == "mirror.demo"


def test_local_runner_executes_only_the_opaque_message(
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
            "reference_profile_id": None,
            "profile_digest": None,
        }

    monkeypatch.setattr(
        "mirror_worker.local.run_demo_reference_profile_message",
        fake_run,
    )
    message = DemoReferenceProfileTaskMessage(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        compile_request_id="c" * 32,
        request_id="d06-worker-request",
    )
    runner = LocalTaskRunner(Settings(app_env="test"))
    assert runner.dispatch_demo_reference_profile(message) == message.job_id
    assert captured == [message.to_message()]
