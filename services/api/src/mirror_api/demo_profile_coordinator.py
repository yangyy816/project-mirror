from __future__ import annotations

import logging
from dataclasses import dataclass

from mirror_api.demo_job_service import DemoJobService, DemoJobSnapshot
from mirror_api.demo_profile_commands import (
    CreateDemoProfileCompilation,
    DemoProfileCommandService,
)
from mirror_api.demo_profile_task_contract import (
    DemoProfileDispatcher,
    DemoProfileTaskMessage,
)
from mirror_api.logging import OperationalEvent, emit_operational_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemoProfileCreateResult:
    job: DemoJobSnapshot
    replayed: bool


class DemoProfileCoordinator:
    """Bind idempotent profile Jobs to recoverable reference-only dispatch."""

    def __init__(
        self,
        *,
        commands: DemoProfileCommandService,
        jobs: DemoJobService,
        dispatcher: DemoProfileDispatcher,
    ) -> None:
        self._commands = commands
        self._jobs = jobs
        self._dispatcher = dispatcher

    async def create(self, command: CreateDemoProfileCompilation) -> DemoProfileCreateResult:
        accepted = await self._commands.create_compilation(command)
        job = await self._jobs.get(
            demo_actor_id=command.demo_actor_id,
            job_id=accepted.job_id,
        )
        if job.status == "PENDING":
            self._dispatch(
                DemoProfileTaskMessage(
                    demo_actor_id=command.demo_actor_id,
                    job_id=accepted.job_id,
                    request_id=accepted.request_id,
                ),
                raise_on_failure=False,
            )
        return DemoProfileCreateResult(job=job, replayed=accepted.replayed)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        dispatched: list[str] = []
        for candidate in await self._commands.reconciliation_candidates(limit=limit):
            self._dispatch(
                DemoProfileTaskMessage(
                    demo_actor_id=candidate.demo_actor_id,
                    job_id=candidate.job_id,
                    request_id=candidate.request_id,
                ),
                raise_on_failure=True,
            )
            dispatched.append(candidate.job_id)
        return tuple(dispatched)

    def _dispatch(self, message: DemoProfileTaskMessage, *, raise_on_failure: bool) -> None:
        try:
            self._dispatcher.dispatch_demo_profile(message)
        except Exception:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="deferred",
                    operation="demo_profile",
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
                    operation="demo_profile",
                    job_id=message.job_id,
                    request_id=message.request_id,
                ),
            )


__all__ = ["DemoProfileCoordinator", "DemoProfileCreateResult"]
