from __future__ import annotations

from typing import Any

import pytest

from mirror_api.demo_analysis_dispatcher import (
    DEMO_ANALYSIS_QUEUE,
    CeleryDemoAnalysisDispatcher,
    RecoverablePendingDemoAnalysisDispatcher,
)
from mirror_api.demo_analysis_task_contract import DemoAnalysisTaskMessage


def _message() -> DemoAnalysisTaskMessage:
    return DemoAnalysisTaskMessage(
        analysis_run_id="a" * 32,
        job_id="b" * 32,
        request_id="d03-dispatch-request",
    )


def test_analysis_dispatchers_preserve_reference_only_dedicated_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = _message()
    assert (
        RecoverablePendingDemoAnalysisDispatcher().dispatch_demo_analysis(message) == message.job_id
    )
    captured: dict[str, Any] = {}
    dispatcher = CeleryDemoAnalysisDispatcher(redis_url="redis://127.0.0.1:6379/15")

    def fake_send_task(name: str, **kwargs: Any) -> object:
        captured["name"] = name
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(dispatcher._celery, "send_task", fake_send_task)
    assert dispatcher.dispatch_demo_analysis(message) == message.job_id
    assert captured["name"] == "mirror.demo_analysis.process"
    assert captured["args"] == [message.to_message()]
    assert captured["headers"] == {
        "request_id": message.request_id,
        "job_id": message.job_id,
    }
    assert captured["queue"] == DEMO_ANALYSIS_QUEUE
    serialized = str(captured)
    assert all(
        marker not in serialized
        for marker in ("storage_key", "runtime_locator", "content", "prompt", "image_bytes")
    )
