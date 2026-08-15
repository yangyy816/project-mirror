from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mirror_api.account_deletion.service import AccountDeletionResult
from mirror_api.data_export.service import DataExportResult
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
)

from mirror_worker.data_rights import AccountDeletionTaskExecutor, DataExportTaskExecutor

NOW = datetime(2026, 8, 16, tzinfo=UTC)
EXPORT_JOB = "f" * 32
ACCOUNT_JOB = "e" * 32


class _ExportApplication:
    async def process(self, *, job_id: str) -> DataExportResult:
        return DataExportResult(
            export_id="d" * 32,
            job_id=job_id,
            status="ready",
            schema_version="mirror-data-export-v1",
            requested_at=NOW,
        )


class _AccountApplication:
    async def process(self, *, job_id: str) -> AccountDeletionResult:
        return AccountDeletionResult(
            request_id="c" * 32,
            job_id=job_id,
            status="completed",
            requested_at=NOW,
        )


def test_data_rights_messages_reject_payload_expansion() -> None:
    export = DataExportTaskMessage(job_id=EXPORT_JOB, request_id="export-worker-request")
    account = AccountDeletionTaskMessage(job_id=ACCOUNT_JOB, request_id="account-worker-request")
    assert set(export.to_message()) == {"job_id", "request_id", "schema_version"}
    assert set(account.to_message()) == {"job_id", "request_id", "schema_version"}
    with pytest.raises(ValueError, match="invalid shape"):
        DataExportTaskMessage.from_message({**export.to_message(), "object_key": "forbidden"})
    with pytest.raises(ValueError, match="invalid shape"):
        AccountDeletionTaskMessage.from_message(
            {**account.to_message(), "owner_user_id": "forbidden"}
        )


@pytest.mark.asyncio
async def test_data_rights_executors_return_authoritative_status() -> None:
    export = await DataExportTaskExecutor(_ExportApplication()).execute(
        DataExportTaskMessage(job_id=EXPORT_JOB, request_id="export-worker-request")
    )
    account = await AccountDeletionTaskExecutor(_AccountApplication()).execute(
        AccountDeletionTaskMessage(job_id=ACCOUNT_JOB, request_id="account-worker-request")
    )
    assert export.status == "ready"
    assert account.status == "completed"
