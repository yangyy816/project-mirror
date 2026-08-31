"""Celery-independent executor for queued D10 Context compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from mirror_api.demo_context_queue_service import DemoContextExecutionResult
from mirror_api.demo_context_task_contract import DemoContextTaskMessage

ExecutionStatus = Literal["COMPLETED", "REJECTED", "FAILED", "CANCELLED", "NO_OP"]


class DemoContextApplication(Protocol):
    async def execute_task(
        self, *, demo_actor_id: str, job_id: str, context_request_id: str
    ) -> DemoContextExecutionResult: ...


@dataclass(frozen=True, slots=True)
class DemoContextTaskResult:
    demo_actor_id: str
    job_id: str
    status: ExecutionStatus
    result_code: str | None = None
    context_compilation_id: str | None = None
    context_digest: str | None = None


class DemoContextTaskExecutor:
    def __init__(self, *, application: DemoContextApplication) -> None:
        self._application = application

    async def execute(self, message: DemoContextTaskMessage) -> DemoContextTaskResult:
        message.validate()
        result = await self._application.execute_task(
            demo_actor_id=message.demo_actor_id,
            job_id=message.job_id,
            context_request_id=message.context_request_id,
        )
        return DemoContextTaskResult(
            result.demo_actor_id,
            result.job_id,
            result.status,
            result.result_code,
            result.context_compilation_id,
            result.context_digest,
        )


__all__ = ["DemoContextTaskExecutor", "DemoContextTaskResult"]
