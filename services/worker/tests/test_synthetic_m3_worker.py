from __future__ import annotations

import pytest
from mirror_api.synthetic_dataset.orchestration_service import (
    M3RetryableError,
    M3TaskResult,
)
from mirror_api.synthetic_dataset.task_contract import (
    SyntheticNormalizationTaskMessage,
    SyntheticQATaskMessage,
)

from mirror_worker.ingestion import RetryableWorkerFailure
from mirror_worker.synthetic_m3 import SyntheticM3Reconciler, SyntheticM3TaskExecutor


class FakeM3Application:
    def __init__(self) -> None:
        self.normalization = SyntheticNormalizationTaskMessage(
            record_id="a" * 32,
            job_id="b" * 32,
            request_id="m3-worker-fixture",
        )
        self.qa = SyntheticQATaskMessage(
            qa_run_id="c" * 32,
            job_id="d" * 32,
            request_id="m3-worker-fixture",
        )
        self.retry = False

    async def execute_normalization(
        self, message: SyntheticNormalizationTaskMessage
    ) -> M3TaskResult:
        assert message == self.normalization
        if self.retry:
            raise M3RetryableError("normalization_storage_unavailable")
        return M3TaskResult(message.record_id, message.job_id, "normalized")

    async def execute_qa(self, message: SyntheticQATaskMessage) -> M3TaskResult:
        assert message == self.qa
        return M3TaskResult(message.qa_run_id, message.job_id, "qa_rejected")

    async def reconciliation_candidates(self, *, limit: int = 100):  # type: ignore[no-untyped-def]
        assert limit == 10
        return (self.normalization, self.qa)


class CapturingDispatcher:
    def __init__(self) -> None:
        self.normalizations: list[SyntheticNormalizationTaskMessage] = []
        self.qas: list[SyntheticQATaskMessage] = []

    def dispatch_synthetic_normalization(self, message: SyntheticNormalizationTaskMessage) -> str:
        self.normalizations.append(message)
        return message.job_id

    def dispatch_synthetic_qa(self, message: SyntheticQATaskMessage) -> str:
        self.qas.append(message)
        return message.job_id


def test_m3_task_contracts_are_closed_and_reference_only() -> None:
    app = FakeM3Application()
    assert (
        SyntheticNormalizationTaskMessage.from_message(app.normalization.to_message())
        == app.normalization
    )
    assert SyntheticQATaskMessage.from_message(app.qa.to_message()) == app.qa
    expanded: dict[str, object] = dict(app.normalization.to_message())
    expanded["storage_key"] = "forbidden"
    with pytest.raises(ValueError, match="invalid shape"):
        SyntheticNormalizationTaskMessage.from_message(expanded)
    assert set(app.normalization.to_message()) == {
        "record_id",
        "job_id",
        "request_id",
        "schema_version",
    }
    assert set(app.qa.to_message()) == {"qa_run_id", "job_id", "request_id", "schema_version"}


@pytest.mark.asyncio
async def test_m3_worker_adapter_redacts_retryable_failure_and_reconciles_reference_messages() -> (
    None
):
    app = FakeM3Application()
    executor = SyntheticM3TaskExecutor(app)
    assert (await executor.execute_normalization(app.normalization)).status == "normalized"
    assert (await executor.execute_qa(app.qa)).status == "qa_rejected"
    app.retry = True
    with pytest.raises(RetryableWorkerFailure, match="synthetic normalization remains retryable"):
        await executor.execute_normalization(app.normalization)
    dispatcher = CapturingDispatcher()
    dispatched = await SyntheticM3Reconciler(app, dispatcher).execute(limit=10)
    assert dispatched == (app.normalization.record_id, app.qa.qa_run_id)
    assert dispatcher.normalizations == [app.normalization]
    assert dispatcher.qas == [app.qa]
