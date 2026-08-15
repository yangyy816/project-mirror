from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from mirror_api.ingestion.types import IngestionJobClaim, IngestionJobResult

INGESTION_TASK_SCHEMA = "ingestion-task-v1"


class RetryableWorkerFailure(RuntimeError):
    """An infrastructure failure that may be retried by a task adapter."""


@dataclass(frozen=True)
class IngestionTaskMessage:
    """Provider-neutral ingestion message containing references only."""

    job_id: str
    request_id: str
    schema_version: str = INGESTION_TASK_SCHEMA

    def validate(self) -> None:
        if re.fullmatch(r"[0-9a-f]{32}", self.job_id) is None:
            raise ValueError("job_id must be an opaque 32-character lowercase hex identifier")
        if not 8 <= len(self.request_id) <= 128:
            raise ValueError("request_id length is invalid")
        if self.schema_version != INGESTION_TASK_SCHEMA:
            raise ValueError("unsupported ingestion task schema version")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> IngestionTaskMessage:
        expected = {"job_id", "request_id", "schema_version"}
        if set(message) != expected or not all(
            isinstance(value, str) for value in message.values()
        ):
            raise ValueError("ingestion task message has an invalid shape")
        task_message = cls(
            job_id=message["job_id"],
            request_id=message["request_id"],
            schema_version=message["schema_version"],
        )
        task_message.validate()
        return task_message


@dataclass(frozen=True)
class CleanupResult:
    status: str
    quarantine_result: str | None = None
    sanitized_result: str | None = None


@dataclass(frozen=True)
class WorkerExecutionResult:
    job_id: str
    status: str


@dataclass(frozen=True)
class SweepResult:
    terminal_jobs_checked: int
    expired_intents_tombstoned: int


class IngestionApplication(Protocol):
    async def claim(self, *, job_id: str) -> IngestionJobClaim | None: ...

    async def process(self, *, claim: IngestionJobClaim) -> IngestionJobResult | None: ...

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]: ...


class IngestionCleanup(Protocol):
    async def cleanup_job(self, *, job_id: str) -> CleanupResult: ...

    async def sweep(self, *, limit: int = 100) -> SweepResult: ...


class IngestionDispatcher(Protocol):
    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str: ...


class IngestionTaskExecutor:
    """Celery-independent at-least-once execution of one authoritative Job."""

    def __init__(self, application: IngestionApplication, cleanup: IngestionCleanup) -> None:
        self._application = application
        self._cleanup = cleanup

    async def execute(self, message: IngestionTaskMessage) -> WorkerExecutionResult:
        message.validate()
        claim = await self._application.claim(job_id=message.job_id)
        if claim is None:
            cleanup = await self._cleanup.cleanup_job(job_id=message.job_id)
            return WorkerExecutionResult(job_id=message.job_id, status=cleanup.status)
        result = await self._application.process(claim=claim)
        if result is None:
            raise RetryableWorkerFailure("ingestion job remains retryable")
        await self._cleanup.cleanup_job(job_id=message.job_id)
        return WorkerExecutionResult(job_id=message.job_id, status=result.job.status)


class IngestionReconciler:
    """Redis-independent recovery of pending and stale PostgreSQL Jobs."""

    def __init__(self, application: IngestionApplication, dispatcher: IngestionDispatcher) -> None:
        self._application = application
        self._dispatcher = dispatcher

    async def execute(self, *, request_id: str, limit: int = 100) -> tuple[str, ...]:
        if not 8 <= len(request_id) <= 128:
            raise ValueError("request_id length is invalid")
        candidates = await self._application.reconcile(limit=limit)
        dispatched: list[str] = []
        for job_id in candidates:
            message = IngestionTaskMessage(job_id=job_id, request_id=request_id)
            self._dispatcher.dispatch_ingestion(message)
            dispatched.append(job_id)
        return tuple(dispatched)


class IngestionMaintenance:
    def __init__(self, cleanup: IngestionCleanup) -> None:
        self._cleanup = cleanup

    async def execute(self, *, limit: int = 100) -> SweepResult:
        if limit < 1 or limit > 1_000:
            raise ValueError("maintenance limit must be between 1 and 1000")
        return await self._cleanup.sweep(limit=limit)
