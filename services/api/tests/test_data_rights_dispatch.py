from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from mirror_api.account_deletion.service import AccountDeletionResult
from mirror_api.data_export.service import DataExportResult
from mirror_api.data_rights.coordinator import DataRightsCoordinator
from mirror_api.data_rights.dispatcher import (
    CeleryDataRightsDispatcher,
    RecoverableDataRightsDispatcher,
)
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
)

NOW = datetime(2026, 8, 16, tzinfo=UTC)
EXPORT_JOB = "a" * 32
ACCOUNT_JOB = "b" * 32


class _Exports:
    async def request_export(self, **_: str) -> DataExportResult:
        return DataExportResult(
            export_id="c" * 32,
            job_id=EXPORT_JOB,
            status="requested",
            schema_version="mirror-data-export-v1",
            requested_at=NOW,
            created=True,
        )

    async def reconcile(self, *, limit: int) -> tuple[str, ...]:
        assert limit == 2
        return (EXPORT_JOB,)


class _Accounts:
    async def request_deletion(self, **_: str) -> AccountDeletionResult:
        return AccountDeletionResult(
            request_id="d" * 32,
            job_id=ACCOUNT_JOB,
            status="requested",
            requested_at=NOW,
            created=True,
        )

    async def reconcile(self, *, limit: int) -> tuple[str, ...]:
        assert limit == 2
        return (ACCOUNT_JOB,)


class _Dispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[object] = []

    def dispatch_data_export(self, message: DataExportTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("synthetic broker outage")
        return message.job_id

    def dispatch_account_deletion(self, message: AccountDeletionTaskMessage) -> str:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("synthetic broker outage")
        return message.job_id


@pytest.mark.asyncio
async def test_data_rights_coordinator_preserves_durable_jobs_on_broker_outage() -> None:
    dispatcher = _Dispatcher(fail=True)
    coordinator = DataRightsCoordinator(  # type: ignore[arg-type]
        exports=_Exports(), account_deletions=_Accounts(), dispatcher=dispatcher
    )
    export = await coordinator.create_export(
        user_id="e" * 32,
        idempotency_key="export-once",
        request_id="export-dispatch-request",
    )
    account = await coordinator.create_account_deletion(
        user_id="e" * 32,
        idempotency_key="account-once",
        request_id="account-dispatch-request",
    )
    assert export.created and account.created and len(dispatcher.messages) == 2
    dispatcher.fail = False
    assert await coordinator.reconcile(request_id="reconcile-request", limit=2) == (
        EXPORT_JOB,
        ACCOUNT_JOB,
    )
    assert len(dispatcher.messages) == 4
    assert all(
        marker not in str(dispatcher.messages)
        for marker in ("object_key", "storage_key", "owner_user_id", "bytes")
    )


def test_data_rights_dispatchers_emit_reference_only_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export = DataExportTaskMessage(job_id=EXPORT_JOB, request_id="export-dispatch-request")
    account = AccountDeletionTaskMessage(job_id=ACCOUNT_JOB, request_id="account-dispatch-request")
    recoverable = RecoverableDataRightsDispatcher()
    assert recoverable.dispatch_data_export(export) == EXPORT_JOB
    assert recoverable.dispatch_account_deletion(account) == ACCOUNT_JOB
    captured: list[tuple[str, dict[str, Any]]] = []
    celery = CeleryDataRightsDispatcher(redis_url="redis://127.0.0.1:6379/15")

    def fake_send_task(name: str, **kwargs: Any) -> object:
        captured.append((name, kwargs))
        return object()

    monkeypatch.setattr(celery._celery, "send_task", fake_send_task)
    assert celery.dispatch_data_export(export) == EXPORT_JOB
    assert celery.dispatch_account_deletion(account) == ACCOUNT_JOB
    assert [item[0] for item in captured] == [
        "mirror.data_export.process",
        "mirror.account_deletion.process",
    ]
    assert all(item[1]["queue"] == "mirror.maintenance" for item in captured)
