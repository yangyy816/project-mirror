"""Celery-independent reference-only M4 transform adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mirror_api.synthetic_dataset.m4_orchestration_service import (
    M4RetryableError,
    M4TaskResult,
)
from mirror_api.synthetic_dataset.task_contract import (
    SyntheticM4Dispatcher,
    SyntheticTransformTaskMessage,
)

from mirror_worker.ingestion import RetryableWorkerFailure


class SyntheticM4Application(Protocol):
    async def execute_transform(self, message: SyntheticTransformTaskMessage) -> M4TaskResult: ...

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[SyntheticTransformTaskMessage, ...]: ...


@dataclass(frozen=True)
class SyntheticM4ExecutionResult:
    transform_run_id: str
    job_id: str
    status: str
    result_asset_id: str | None
    qa_run_id: str | None


class SyntheticM4TaskExecutor:
    def __init__(self, application: SyntheticM4Application) -> None:
        self._application = application

    async def execute(self, message: SyntheticTransformTaskMessage) -> SyntheticM4ExecutionResult:
        message.validate()
        try:
            result = await self._application.execute_transform(message)
        except M4RetryableError as error:
            raise RetryableWorkerFailure("synthetic transform remains retryable") from error
        return SyntheticM4ExecutionResult(
            transform_run_id=result.transform_run_id,
            job_id=result.job_id,
            status=result.status,
            result_asset_id=result.result_asset_id,
            qa_run_id=result.qa_run_id,
        )


class SyntheticM4Reconciler:
    def __init__(
        self, application: SyntheticM4Application, dispatcher: SyntheticM4Dispatcher
    ) -> None:
        self._application = application
        self._dispatcher = dispatcher

    async def execute(self, *, limit: int = 100) -> tuple[str, ...]:
        messages = await self._application.reconciliation_candidates(limit=limit)
        dispatched: list[str] = []
        for message in messages:
            self._dispatcher.dispatch_synthetic_transform(message)
            dispatched.append(message.transform_run_id)
        return tuple(dispatched)
