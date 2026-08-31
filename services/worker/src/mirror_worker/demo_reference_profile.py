"""Celery-independent executor for queued, reference-only D06 compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from mirror_api.demo_reference_profile_service import DemoReferenceProfileExecutionResult
from mirror_api.demo_reference_profile_task_contract import DemoReferenceProfileTaskMessage

ExecutionStatus = Literal["COMPLETED", "REJECTED", "FAILED", "CANCELLED", "NO_OP"]


class DemoReferenceProfileApplication(Protocol):
    async def execute_task(
        self,
        *,
        demo_actor_id: str,
        job_id: str,
        compile_request_id: str,
    ) -> DemoReferenceProfileExecutionResult: ...


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileTaskResult:
    demo_actor_id: str
    job_id: str
    status: ExecutionStatus
    result_code: str | None = None
    reference_profile_id: str | None = None
    profile_digest: str | None = None


class DemoReferenceProfileTaskExecutor:
    """Execute one opaque D06 message; unexpected failures remain retryable."""

    def __init__(self, *, application: DemoReferenceProfileApplication) -> None:
        self._application = application

    async def execute(
        self, message: DemoReferenceProfileTaskMessage
    ) -> DemoReferenceProfileTaskResult:
        message.validate()
        result = await self._application.execute_task(
            demo_actor_id=message.demo_actor_id,
            job_id=message.job_id,
            compile_request_id=message.compile_request_id,
        )
        return DemoReferenceProfileTaskResult(
            result.demo_actor_id,
            result.job_id,
            result.status,
            result.result_code,
            result.reference_profile_id,
            result.profile_digest,
        )


__all__ = ["DemoReferenceProfileTaskExecutor", "DemoReferenceProfileTaskResult"]
