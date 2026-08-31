from __future__ import annotations

import logging
from dataclasses import dataclass

from mirror_api.demo_context_queue_service import (
    CreateDemoContextCompilation,
    DemoContextQueueService,
)
from mirror_api.demo_context_task_contract import DemoContextDispatcher, DemoContextTaskMessage
from mirror_api.demo_job_service import DemoJobService, DemoJobSnapshot
from mirror_api.logging import OperationalEvent, emit_operational_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DemoContextCreateResult:
    job: DemoJobSnapshot
    replayed: bool


class DemoContextCoordinator:
    def __init__(
        self,
        *,
        service: DemoContextQueueService,
        jobs: DemoJobService,
        dispatcher: DemoContextDispatcher,
    ) -> None:
        self._service, self._jobs, self._dispatcher = service, jobs, dispatcher

    async def create(self, command: CreateDemoContextCompilation) -> DemoContextCreateResult:
        accepted = await self._service.admit(command)
        job = await self._jobs.get(demo_actor_id=command.demo_actor_id, job_id=accepted.job_id)
        if job.status == "PENDING":
            self._dispatch(
                DemoContextTaskMessage(
                    command.demo_actor_id,
                    job.job_id,
                    accepted.context_request_id,
                    accepted.request_id,
                ),
                raise_on_failure=False,
            )
        return DemoContextCreateResult(job, accepted.replayed)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        result: list[str] = []
        for candidate in await self._service.reconciliation_candidates(limit=limit):
            self._dispatch(
                DemoContextTaskMessage(
                    candidate.demo_actor_id,
                    candidate.job_id,
                    candidate.context_request_id,
                    candidate.request_id,
                ),
                raise_on_failure=True,
            )
            result.append(candidate.job_id)
        return tuple(result)

    def _dispatch(self, message: DemoContextTaskMessage, *, raise_on_failure: bool) -> None:
        try:
            self._dispatcher.dispatch_demo_context(message)
        except Exception:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="deferred",
                    operation="demo_context",
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
                    operation="demo_context",
                    job_id=message.job_id,
                    request_id=message.request_id,
                ),
            )


__all__ = ["DemoContextCoordinator", "DemoContextCreateResult"]
