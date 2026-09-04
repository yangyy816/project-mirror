from __future__ import annotations

import logging
from dataclasses import dataclass

from mirror_api.demo_job_service import DemoJobService, DemoJobSnapshot
from mirror_api.demo_reference_profile_service import (
    CreateDemoReferenceProfileCompilation,
    DemoReferenceProfileService,
)
from mirror_api.demo_reference_profile_task_contract import (
    DemoReferenceProfileDispatcher,
    DemoReferenceProfileTaskMessage,
)
from mirror_api.logging import OperationalEvent, emit_operational_event

logger = logging.getLogger(__name__)
_REFERENCE_DISPATCH_CORRELATION = "d06-reference-dispatch"


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileCreateResult:
    job: DemoJobSnapshot
    replayed: bool


class DemoReferenceProfileCoordinator:
    """Bind immutable D06 admissions to recoverable reference-only dispatch."""

    def __init__(
        self,
        *,
        service: DemoReferenceProfileService,
        jobs: DemoJobService,
        dispatcher: DemoReferenceProfileDispatcher,
    ) -> None:
        self._service = service
        self._jobs = jobs
        self._dispatcher = dispatcher

    async def create(
        self, command: CreateDemoReferenceProfileCompilation
    ) -> DemoReferenceProfileCreateResult:
        accepted = await self._service.admit(command)
        job = await self._jobs.get(
            demo_actor_id=command.demo_actor_id,
            job_id=accepted.job_id,
        )
        if job.status == "PENDING":
            self._dispatch(
                DemoReferenceProfileTaskMessage(
                    demo_actor_id=command.demo_actor_id,
                    job_id=accepted.job_id,
                    compile_request_id=accepted.compile_request_id,
                    request_id=accepted.request_id,
                ),
                raise_on_failure=False,
            )
        return DemoReferenceProfileCreateResult(job, accepted.replayed)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        dispatched: list[str] = []
        for candidate in await self._service.reconciliation_candidates(limit=limit):
            self._dispatch(
                DemoReferenceProfileTaskMessage(
                    demo_actor_id=candidate.demo_actor_id,
                    job_id=candidate.job_id,
                    compile_request_id=candidate.compile_request_id,
                    request_id=candidate.request_id,
                ),
                raise_on_failure=True,
            )
            dispatched.append(candidate.job_id)
        return tuple(dispatched)

    def _dispatch(
        self,
        message: DemoReferenceProfileTaskMessage,
        *,
        raise_on_failure: bool,
    ) -> None:
        try:
            self._dispatcher.dispatch_demo_reference_profile(message)
        except Exception:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="deferred",
                    operation="demo_reference_profile",
                    request_id=_REFERENCE_DISPATCH_CORRELATION,
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
                    operation="demo_reference_profile",
                    request_id=_REFERENCE_DISPATCH_CORRELATION,
                ),
            )


__all__ = ["DemoReferenceProfileCoordinator", "DemoReferenceProfileCreateResult"]
