"""Celery-independent executor for deterministic Demo profile compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from mirror_api.demo_profile_service import (
    DemoProfileAuthorityCorruption,
    DemoProfileCompilationResult,
    DemoProfileRejected,
    DemoProfileUnavailable,
)
from mirror_api.demo_profile_task_contract import DemoProfileTaskMessage

ExecutionStatus = Literal["COMPLETED", "REJECTED", "FAILED", "NO_OP"]


class DemoProfileApplication(Protocol):
    async def compile(self, *, demo_actor_id: str, job_id: str) -> DemoProfileCompilationResult: ...


@dataclass(frozen=True)
class DemoProfileTaskResult:
    demo_actor_id: str
    job_id: str
    status: ExecutionStatus
    bundle_id: str | None = None
    compilation_digest: str | None = None


class DemoProfileTaskExecutor:
    """Execute one reference-only Job without any runtime or Provider call."""

    def __init__(self, *, application: DemoProfileApplication) -> None:
        self._application = application

    async def execute(self, message: DemoProfileTaskMessage) -> DemoProfileTaskResult:
        message.validate()
        try:
            result = await self._application.compile(
                demo_actor_id=message.demo_actor_id,
                job_id=message.job_id,
            )
        except DemoProfileRejected:
            return _result(message, status="REJECTED")
        except DemoProfileAuthorityCorruption:
            return _result(message, status="FAILED")
        except DemoProfileUnavailable:
            return _result(message, status="NO_OP")
        return DemoProfileTaskResult(
            demo_actor_id=message.demo_actor_id,
            job_id=message.job_id,
            status="COMPLETED",
            bundle_id=result.bundle_id,
            compilation_digest=result.compilation_digest,
        )


def _result(message: DemoProfileTaskMessage, *, status: ExecutionStatus) -> DemoProfileTaskResult:
    return DemoProfileTaskResult(
        demo_actor_id=message.demo_actor_id,
        job_id=message.job_id,
        status=status,
    )


__all__ = ["DemoProfileTaskExecutor", "DemoProfileTaskResult"]
