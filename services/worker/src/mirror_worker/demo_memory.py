"""Celery-independent executor for deterministic Demo memory rebuilds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from mirror_api.demo_memory_service import (
    DemoAestheticProfileResult,
    DemoMemoryAuthorityCorruption,
    DemoMemoryConflict,
    DemoMemoryInputError,
    DemoMemoryUnavailable,
)
from mirror_api.demo_memory_task_contract import DemoMemoryTaskMessage

ExecutionStatus = Literal["COMPLETED", "REJECTED", "FAILED", "NO_OP"]


class DemoMemoryApplication(Protocol):
    async def execute_rebuild(
        self, *, demo_actor_id: str, job_id: str
    ) -> DemoAestheticProfileResult: ...


@dataclass(frozen=True)
class DemoMemoryTaskResult:
    demo_actor_id: str
    job_id: str
    status: ExecutionStatus
    aesthetic_profile_id: str | None = None
    profile_digest: str | None = None


class DemoMemoryTaskExecutor:
    """Execute one admitted D10 rebuild without a Provider or runtime handle."""

    def __init__(self, *, application: DemoMemoryApplication) -> None:
        self._application = application

    async def execute(self, message: DemoMemoryTaskMessage) -> DemoMemoryTaskResult:
        message.validate()
        try:
            result = await self._application.execute_rebuild(
                demo_actor_id=message.demo_actor_id,
                job_id=message.job_id,
            )
        except (DemoMemoryConflict, DemoMemoryInputError):
            return _result(message, status="REJECTED")
        except DemoMemoryAuthorityCorruption:
            return _result(message, status="FAILED")
        except DemoMemoryUnavailable:
            return _result(message, status="NO_OP")
        return DemoMemoryTaskResult(
            demo_actor_id=message.demo_actor_id,
            job_id=message.job_id,
            status="COMPLETED",
            aesthetic_profile_id=result.aesthetic_profile_id,
            profile_digest=result.profile_digest,
        )


def _result(message: DemoMemoryTaskMessage, *, status: ExecutionStatus) -> DemoMemoryTaskResult:
    return DemoMemoryTaskResult(
        demo_actor_id=message.demo_actor_id,
        job_id=message.job_id,
        status=status,
    )


__all__ = ["DemoMemoryTaskExecutor", "DemoMemoryTaskResult"]
