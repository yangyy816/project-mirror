from __future__ import annotations

import logging
from dataclasses import dataclass

from mirror_api.demo_job_service import DemoJobService, DemoJobSnapshot
from mirror_api.demo_memory_service import DemoMemoryService, RebuildDemoAestheticProfile
from mirror_api.demo_memory_task_contract import DemoMemoryDispatcher, DemoMemoryTaskMessage
from mirror_api.logging import OperationalEvent, emit_operational_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemoMemoryCreateResult:
    job: DemoJobSnapshot
    replayed: bool


class DemoMemoryCoordinator:
    """Bind D10 admission to recoverable dispatch without executing inline."""

    def __init__(
        self,
        *,
        service: DemoMemoryService,
        jobs: DemoJobService,
        dispatcher: DemoMemoryDispatcher,
    ) -> None:
        self._service = service
        self._jobs = jobs
        self._dispatcher = dispatcher

    async def create(self, command: RebuildDemoAestheticProfile) -> DemoMemoryCreateResult:
        accepted = await self._service.admit_rebuild(command)
        job = await self._jobs.get(demo_actor_id=command.demo_actor_id, job_id=accepted.job_id)
        if job.status == "PENDING":
            self._dispatch(
                DemoMemoryTaskMessage(
                    command.demo_actor_id,
                    job.job_id,
                    accepted.request_id,
                ),
                raise_on_failure=False,
            )
        return DemoMemoryCreateResult(job=job, replayed=accepted.replayed)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        dispatched: list[str] = []
        for candidate in await self._service.reconciliation_candidates(limit=limit):
            self._dispatch(
                DemoMemoryTaskMessage(
                    candidate.demo_actor_id,
                    candidate.job_id,
                    candidate.request_id,
                ),
                raise_on_failure=True,
            )
            dispatched.append(candidate.job_id)
        return tuple(dispatched)

    def _dispatch(self, message: DemoMemoryTaskMessage, *, raise_on_failure: bool) -> None:
        try:
            self._dispatcher.dispatch_demo_memory(message)
        except Exception:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="deferred",
                    operation="demo_memory",
                    job_id=message.job_id,
                    request_id=message.request_id,
                ),
            )
            if raise_on_failure:
                raise
        else:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="succeeded",
                    operation="demo_memory",
                    job_id=message.job_id,
                    request_id=message.request_id,
                ),
            )


__all__ = ["DemoMemoryCoordinator", "DemoMemoryCreateResult"]
