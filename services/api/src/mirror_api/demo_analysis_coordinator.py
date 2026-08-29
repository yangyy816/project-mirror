from __future__ import annotations

import logging
from dataclasses import dataclass

from mirror_api.demo_analysis_service import CreateDemoAnalysis, DemoAnalysisService
from mirror_api.demo_analysis_task_contract import (
    DemoAnalysisDispatcher,
    DemoAnalysisTaskMessage,
)
from mirror_api.demo_job_service import DemoJobService, DemoJobSnapshot
from mirror_api.logging import OperationalEvent, emit_operational_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemoAnalysisCreateResult:
    job: DemoJobSnapshot
    replayed: bool


class DemoAnalysisCoordinator:
    """Bind durable D03 creation to recoverable reference-only dispatch."""

    def __init__(
        self,
        *,
        service: DemoAnalysisService,
        jobs: DemoJobService,
        dispatcher: DemoAnalysisDispatcher,
    ) -> None:
        self._service = service
        self._jobs = jobs
        self._dispatcher = dispatcher

    async def create(self, command: CreateDemoAnalysis) -> DemoAnalysisCreateResult:
        accepted = await self._service.create(command)
        job = await self._jobs.get(
            demo_actor_id=command.demo_actor_id,
            job_id=accepted.job_id,
        )
        if job.status == "PENDING":
            self._dispatch(
                DemoAnalysisTaskMessage(
                    analysis_run_id=accepted.analysis_run_id,
                    job_id=accepted.job_id,
                    request_id=accepted.request_id,
                ),
                raise_on_failure=False,
            )
        return DemoAnalysisCreateResult(job=job, replayed=accepted.replayed)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        """Redispatch durable PENDING and expired-RUNNING D03 intents."""

        dispatched: list[str] = []
        for candidate in await self._service.reconciliation_candidates(limit=limit):
            message = DemoAnalysisTaskMessage(
                analysis_run_id=candidate.analysis_run_id,
                job_id=candidate.job_id,
                request_id=candidate.request_id,
            )
            self._dispatch(message, raise_on_failure=True)
            dispatched.append(candidate.job_id)
        return tuple(dispatched)

    async def snapshot(
        self, *, demo_actor_id: str, analysis_run_id: str
    ) -> tuple[DemoJobSnapshot, str | None, str | None]:
        analysis = await self._service.snapshot(
            demo_actor_id=demo_actor_id,
            analysis_run_id=analysis_run_id,
        )
        job = await self._jobs.get(
            demo_actor_id=demo_actor_id,
            job_id=analysis.job_id,
        )
        return job, analysis.observation_id, analysis.observation_digest

    def _dispatch(self, message: DemoAnalysisTaskMessage, *, raise_on_failure: bool) -> None:
        try:
            self._dispatcher.dispatch_demo_analysis(message)
        except Exception:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="deferred",
                    operation="demo_analysis",
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
                    operation="demo_analysis",
                    job_id=message.job_id,
                    request_id=message.request_id,
                ),
            )
