from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from mirror_api.ingestion.task_contract import IngestionTaskMessage
from mirror_api.ingestion.types import IngestionJobClaim, IngestionJobResult, IngestionJobView

from mirror_worker.ingestion import (
    CleanupResult,
    IngestionReconciler,
    IngestionTaskExecutor,
    RetryableWorkerFailure,
    SweepResult,
)

JOB_ID = "a" * 32
REQUEST_ID = "worker-request-1234"


class _Application:
    def __init__(self, *, result_status: str | None = "promoted", claim: bool = True) -> None:
        self.result_status = result_status
        self.should_claim = claim
        self.claim_count = 0
        self.process_count = 0
        self.reconciliation_candidates = (JOB_ID, "b" * 32)

    async def claim(self, *, job_id: str) -> IngestionJobClaim | None:
        assert job_id == JOB_ID
        self.claim_count += 1
        if not self.should_claim:
            return None
        return IngestionJobClaim(
            job_id=job_id,
            request_id=REQUEST_ID,
            lease_token="c" * 64,
            attempt=1,
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    async def process(self, *, claim: IngestionJobClaim) -> IngestionJobResult | None:
        assert claim.job_id == JOB_ID
        self.process_count += 1
        if self.result_status is None:
            return None
        return IngestionJobResult(
            job=IngestionJobView(
                job_id=JOB_ID,
                status=cast(str, self.result_status),  # type: ignore[arg-type]
                result_code="ingestion_promoted",
                asset_id="d" * 32,
                finalized_at=datetime.now(UTC),
            )
        )

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        assert limit == 2
        return self.reconciliation_candidates


class _Cleanup:
    def __init__(self, *, status: str = "no_op", fail: bool = False) -> None:
        self.status = status
        self.fail = fail
        self.job_ids: list[str] = []

    async def cleanup_job(self, *, job_id: str) -> CleanupResult:
        self.job_ids.append(job_id)
        if self.fail:
            raise RetryableWorkerFailure("synthetic cleanup outage")
        return CleanupResult(status=self.status)

    async def sweep(self, *, limit: int = 100) -> SweepResult:
        return SweepResult(terminal_jobs_checked=0, expired_intents_tombstoned=0)


class _Dispatcher:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.messages: list[IngestionTaskMessage] = []
        self.fail_after = fail_after

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str:
        if self.fail_after is not None and len(self.messages) >= self.fail_after:
            raise RuntimeError("synthetic broker outage")
        self.messages.append(message)
        return message.job_id


def _message() -> IngestionTaskMessage:
    return IngestionTaskMessage(job_id=JOB_ID, request_id=REQUEST_ID)


def test_ingestion_message_contains_references_only_and_rejects_extra_payload() -> None:
    message = _message().to_message()
    assert message == {
        "job_id": JOB_ID,
        "request_id": REQUEST_ID,
        "schema_version": "ingestion-task-v1",
    }
    assert not {"object_key", "payload", "idempotency_key_hash", "bytes"} & set(message)
    with pytest.raises(ValueError, match="invalid shape"):
        IngestionTaskMessage.from_message({**message, "payload": {}})
    with pytest.raises(ValueError, match="schema version"):
        IngestionTaskMessage.from_message({**message, "schema_version": "future"})


@pytest.mark.asyncio
async def test_executor_processes_and_cleans_up_terminal_job() -> None:
    application = _Application()
    cleanup = _Cleanup(status="promoted")
    result = await IngestionTaskExecutor(application, cleanup).execute(_message())
    assert result.status == "promoted"
    assert application.claim_count == application.process_count == 1
    assert cleanup.job_ids == [JOB_ID]


@pytest.mark.asyncio
async def test_duplicate_delivery_during_active_lease_is_a_safe_no_op() -> None:
    application = _Application(claim=False)
    cleanup = _Cleanup()
    result = await IngestionTaskExecutor(application, cleanup).execute(_message())
    assert result.status == "no_op"
    assert application.process_count == 0
    assert cleanup.job_ids == [JOB_ID]


@pytest.mark.asyncio
async def test_transient_processing_and_post_commit_cleanup_remain_retryable() -> None:
    with pytest.raises(RetryableWorkerFailure, match="remains retryable"):
        await IngestionTaskExecutor(_Application(result_status=None), _Cleanup()).execute(
            _message()
        )
    with pytest.raises(RetryableWorkerFailure, match="cleanup outage"):
        await IngestionTaskExecutor(_Application(), _Cleanup(fail=True)).execute(_message())


@pytest.mark.asyncio
async def test_reconciler_dispatches_reference_only_messages_and_preserves_pending_on_outage() -> (
    None
):
    application = _Application()
    dispatcher = _Dispatcher()
    dispatched = await IngestionReconciler(application, dispatcher).execute(
        request_id="reconcile-request", limit=2
    )
    assert dispatched == application.reconciliation_candidates
    assert [message.job_id for message in dispatcher.messages] == list(dispatched)
    assert all(message.request_id == "reconcile-request" for message in dispatcher.messages)

    failing = _Dispatcher(fail_after=1)
    with pytest.raises(RuntimeError, match="broker outage"):
        await IngestionReconciler(application, failing).execute(
            request_id="reconcile-retry", limit=2
        )
    assert [message.job_id for message in failing.messages] == [JOB_ID]
