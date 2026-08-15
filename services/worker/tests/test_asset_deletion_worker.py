from __future__ import annotations

import pytest
from mirror_api.asset_deletion.service import AssetDeletionResult
from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage

from mirror_worker.asset_deletion import AssetDeletionTaskExecutor

JOB_ID = "e" * 32
REQUEST_ID = "asset-delete-worker-request"


class _Application:
    def __init__(self, result: AssetDeletionResult | None) -> None:
        self.result = result
        self.calls: list[str] = []

    async def process(self, *, job_id: str) -> AssetDeletionResult | None:
        self.calls.append(job_id)
        return self.result


def test_asset_deletion_message_contains_references_only() -> None:
    message = AssetDeletionTaskMessage(job_id=JOB_ID, request_id=REQUEST_ID).to_message()
    assert message == {
        "job_id": JOB_ID,
        "request_id": REQUEST_ID,
        "schema_version": "asset-deletion-task-v1",
    }
    assert not {"object_key", "asset_id", "owner_user_id", "payload", "bytes"} & set(message)
    with pytest.raises(ValueError, match="invalid shape"):
        AssetDeletionTaskMessage.from_message({**message, "object_key": "forbidden"})


@pytest.mark.asyncio
async def test_asset_deletion_executor_is_idempotent_for_terminal_delivery() -> None:
    completed = _Application(
        AssetDeletionResult(request_id="f" * 32, job_id=JOB_ID, status="completed")
    )
    result = await AssetDeletionTaskExecutor(completed).execute(
        AssetDeletionTaskMessage(job_id=JOB_ID, request_id=REQUEST_ID)
    )
    assert result.status == "completed"
    assert completed.calls == [JOB_ID]

    terminal = _Application(None)
    no_op = await AssetDeletionTaskExecutor(terminal).execute(
        AssetDeletionTaskMessage(job_id=JOB_ID, request_id=REQUEST_ID)
    )
    assert no_op.status == "no_op"
