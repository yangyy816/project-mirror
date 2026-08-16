from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from mirror_api.asset_deletion.coordinator import AssetDeletionCoordinator
from mirror_api.asset_deletion.dispatcher import (
    CeleryAssetDeletionDispatcher,
    RecoverableAssetDeletionDispatcher,
)
from mirror_api.asset_deletion.service import AssetDeletionResult
from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage

JOB_ID = "a" * 32
REQUEST_ID = "asset-delete-dispatch-request"


class _Service:
    def __init__(self, *, created: bool = True) -> None:
        self.created = created

    async def request_deletion(self, **_: str) -> AssetDeletionResult:
        return AssetDeletionResult(
            request_id="b" * 32,
            job_id=JOB_ID,
            status="requested",
            created=self.created,
        )

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        assert limit == 2
        return (JOB_ID,)


class _Dispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[AssetDeletionTaskMessage] = []

    def dispatch_asset_deletion(self, message: AssetDeletionTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("synthetic broker outage")
        return message.job_id


@pytest.mark.asyncio
async def test_deletion_coordinator_keeps_durable_request_on_dispatch_failure(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger_name = "mirror_api.asset_deletion.coordinator"
    event_logger = logging.getLogger(logger_name)
    monkeypatch.setattr(event_logger, "disabled", False)
    monkeypatch.setattr(event_logger, "propagate", True)
    caplog.set_level(logging.INFO, logger=logger_name)
    dispatcher = _Dispatcher(fail=True)
    coordinator = AssetDeletionCoordinator(  # type: ignore[arg-type]
        service=_Service(), dispatcher=dispatcher
    )
    accepted = await coordinator.create(
        user_id="c" * 32,
        asset_id="d" * 32,
        idempotency_key="delete-once",
        request_id=REQUEST_ID,
    )
    assert accepted.status == "requested"
    events = [json.loads(record.message) for record in caplog.records]
    assert events[-1] == {
        "event_name": "job.dispatch.completed",
        "job_id": JOB_ID,
        "operation": "asset_deletion",
        "outcome": "deferred",
        "request_id": REQUEST_ID,
    }
    dispatcher.fail = False
    assert await coordinator.reconcile(request_id="reconcile-request", limit=2) == (JOB_ID,)
    assert len(dispatcher.messages) == 2
    assert "object_key" not in str(dispatcher.messages)


def test_asset_deletion_dispatchers_emit_reference_only_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = AssetDeletionTaskMessage(job_id=JOB_ID, request_id=REQUEST_ID)
    assert RecoverableAssetDeletionDispatcher().dispatch_asset_deletion(message) == JOB_ID
    captured: dict[str, Any] = {}
    dispatcher = CeleryAssetDeletionDispatcher(redis_url="redis://127.0.0.1:6379/15")

    def fake_send_task(name: str, **kwargs: Any) -> object:
        captured["name"] = name
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(dispatcher._celery, "send_task", fake_send_task)
    assert dispatcher.dispatch_asset_deletion(message) == JOB_ID
    assert captured["name"] == "mirror.asset_deletion.process"
    assert captured["args"] == [message.to_message()]
    assert captured["queue"] == "mirror.maintenance"
    serialized = str(captured)
    assert all(
        marker not in serialized
        for marker in ("object_key", "storage_key", "owner_user_id", "payload")
    )
