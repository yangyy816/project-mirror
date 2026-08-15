from __future__ import annotations

from typing import Any

import pytest

import mirror_api.ingestion.coordinator as coordinator_module
from mirror_api.ingestion.coordinator import IngestionCoordinator
from mirror_api.ingestion.dispatcher import (
    CeleryIngestionDispatcher,
    RecoverablePendingDispatcher,
)
from mirror_api.ingestion.task_contract import IngestionTaskMessage
from mirror_api.ingestion.types import IngestionJobResult, IngestionJobView

JOB_ID = "a" * 32
REQUEST_ID = "dispatch-request-1234"


class _Service:
    def __init__(self, *, created: bool = True) -> None:
        self.created = created

    async def create(self, **_: str) -> IngestionJobResult:
        return IngestionJobResult(
            job=IngestionJobView(
                job_id=JOB_ID,
                status="pending",
                result_code=None,
                asset_id=None,
                finalized_at=None,
            ),
            created=self.created,
        )

    async def get(self, *, user_id: str, job_id: str) -> IngestionJobView:
        del user_id, job_id
        raise AssertionError("not used")


class _Dispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[IngestionTaskMessage] = []

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("synthetic broker outage")
        return message.job_id


@pytest.mark.asyncio
async def test_coordinator_dispatches_new_job_once_and_leaves_failure_recoverable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[tuple[str, dict[str, str]]] = []

    def capture_warning(message: str, *, extra: dict[str, str]) -> None:
        warnings.append((message, extra))

    monkeypatch.setattr(coordinator_module.logger, "warning", capture_warning)
    dispatcher = _Dispatcher()
    coordinator = IngestionCoordinator(_Service(), dispatcher)  # type: ignore[arg-type]
    result = await coordinator.create(
        user_id="b" * 32,
        intent_id="c" * 32,
        idempotency_key="coordinator-key",
        request_id=REQUEST_ID,
    )
    assert result.created
    assert dispatcher.messages == [IngestionTaskMessage(job_id=JOB_ID, request_id=REQUEST_ID)]

    replay_dispatcher = _Dispatcher()
    replay = IngestionCoordinator(  # type: ignore[arg-type]
        _Service(created=False), replay_dispatcher
    )
    await replay.create(
        user_id="b" * 32,
        intent_id="c" * 32,
        idempotency_key="coordinator-key",
        request_id=REQUEST_ID,
    )
    assert replay_dispatcher.messages == []

    failing = IngestionCoordinator(_Service(), _Dispatcher(fail=True))  # type: ignore[arg-type]
    still_accepted = await failing.create(
        user_id="b" * 32,
        intent_id="c" * 32,
        idempotency_key="coordinator-key-2",
        request_id=REQUEST_ID,
    )
    assert still_accepted.job.status == "pending"
    assert warnings == [
        (
            "ingestion dispatch deferred to reconciler",
            {"job_id": JOB_ID, "request_id": REQUEST_ID},
        )
    ]
    assert "object_key" not in str(warnings)


def test_dispatch_adapters_emit_only_safe_reference_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = IngestionTaskMessage(job_id=JOB_ID, request_id=REQUEST_ID)
    pending = RecoverablePendingDispatcher()
    assert pending.dispatch_ingestion(message) == JOB_ID

    captured: dict[str, Any] = {}
    dispatcher = CeleryIngestionDispatcher(redis_url="redis://127.0.0.1:6379/15")

    def fake_send_task(name: str, **kwargs: Any) -> object:
        captured["name"] = name
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(dispatcher._celery, "send_task", fake_send_task)
    assert dispatcher.dispatch_ingestion(message) == JOB_ID
    assert captured["name"] == "mirror.asset_ingestion.process"
    assert captured["args"] == [message.to_message()]
    assert captured["queue"] == "mirror.ingestion"
    serialized = str(captured)
    assert all(
        marker not in serialized
        for marker in ("object_key", "storage_key", "idempotency_key_hash", "payload")
    )
