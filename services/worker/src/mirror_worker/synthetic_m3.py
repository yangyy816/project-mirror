"""Celery-independent reference-only M3 normalization and QA task adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mirror_api.synthetic_dataset.orchestration_service import (
    M3RetryableError,
    M3TaskResult,
)
from mirror_api.synthetic_dataset.task_contract import (
    SyntheticM3Dispatcher,
    SyntheticNormalizationTaskMessage,
    SyntheticQATaskMessage,
)

from mirror_worker.ingestion import RetryableWorkerFailure


class SyntheticM3Application(Protocol):
    async def execute_normalization(
        self, message: SyntheticNormalizationTaskMessage
    ) -> M3TaskResult: ...

    async def execute_qa(self, message: SyntheticQATaskMessage) -> M3TaskResult: ...

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[SyntheticNormalizationTaskMessage | SyntheticQATaskMessage, ...]: ...


@dataclass(frozen=True)
class SyntheticM3ExecutionResult:
    target_id: str
    job_id: str
    status: str
    identity_id: str | None


class SyntheticM3TaskExecutor:
    """At-least-once safe adapter; task messages are parsed before any database work."""

    def __init__(self, application: SyntheticM3Application) -> None:
        self._application = application

    async def execute_normalization(
        self, message: SyntheticNormalizationTaskMessage
    ) -> SyntheticM3ExecutionResult:
        message.validate()
        try:
            result = await self._application.execute_normalization(message)
        except M3RetryableError as error:
            raise RetryableWorkerFailure("synthetic normalization remains retryable") from error
        return self._result(result)

    async def execute_qa(self, message: SyntheticQATaskMessage) -> SyntheticM3ExecutionResult:
        message.validate()
        try:
            result = await self._application.execute_qa(message)
        except M3RetryableError as error:
            raise RetryableWorkerFailure("synthetic QA remains retryable") from error
        return self._result(result)

    @staticmethod
    def _result(result: M3TaskResult) -> SyntheticM3ExecutionResult:
        return SyntheticM3ExecutionResult(
            target_id=result.target_id,
            job_id=result.job_id,
            status=result.status,
            identity_id=result.identity_id,
        )


class SyntheticM3Reconciler:
    def __init__(
        self, application: SyntheticM3Application, dispatcher: SyntheticM3Dispatcher
    ) -> None:
        self._application = application
        self._dispatcher = dispatcher

    async def execute(self, *, limit: int = 100) -> tuple[str, ...]:
        messages = await self._application.reconciliation_candidates(limit=limit)
        dispatched: list[str] = []
        for message in messages:
            if isinstance(message, SyntheticNormalizationTaskMessage):
                self._dispatcher.dispatch_synthetic_normalization(message)
                dispatched.append(message.record_id)
            else:
                self._dispatcher.dispatch_synthetic_qa(message)
                dispatched.append(message.qa_run_id)
        return tuple(dispatched)
