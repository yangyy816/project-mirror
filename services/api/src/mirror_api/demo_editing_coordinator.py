"""Recoverable application orchestration for D07 command admission.

The command service commits PostgreSQL authority before this module attempts a
broker dispatch.  A dispatcher failure is deliberately observable but never
rolls back the accepted PENDING Job; reconciliation can safely redeliver the
same opaque message later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, cast

from mirror_api.demo_editing_commands import (
    CreateDemoEditingSession,
    CreateDemoEditPlan,
    DemoEditExecutionResult,
    DemoEditingCommandAccepted,
    DemoEditingCommandService,
    DemoOwnedToolRun,
    ExecuteDemoEditPlan,
    RestoreDemoImageVersion,
)
from mirror_api.demo_editing_task_contract import DemoEditingDispatcher, DemoEditingTaskMessage
from mirror_api.demo_job_service import DemoJobService, DemoJobSnapshot
from mirror_api.logging import OperationalEvent, emit_operational_event

logger = logging.getLogger(__name__)
_Operation = Literal[
    "editing_session.create", "edit_plan.create", "edit_plan.execute", "image_version.restore"
]


@dataclass(frozen=True)
class DemoEditingCreateResult:
    job: DemoJobSnapshot
    target_id: str
    replayed: bool


class DemoEditingCoordinator:
    """Bridge durable D07 admissions to reference-only task dispatch."""

    def __init__(
        self,
        *,
        commands: DemoEditingCommandService,
        jobs: DemoJobService,
        dispatcher: DemoEditingDispatcher,
    ) -> None:
        self._commands = commands
        self._jobs = jobs
        self._dispatcher = dispatcher

    async def create_editing_session(
        self, command: CreateDemoEditingSession
    ) -> DemoEditingCreateResult:
        accepted = await self._commands.create_editing_session(command)
        return await self._accepted(
            actor_id=command.demo_actor_id,
            accepted=accepted,
            operation="editing_session.create",
        )

    async def create_edit_plan(self, command: CreateDemoEditPlan) -> DemoEditingCreateResult:
        accepted = await self._commands.create_edit_plan(command)
        return await self._accepted(
            actor_id=command.demo_actor_id,
            accepted=accepted,
            operation="edit_plan.create",
        )

    async def execute_edit_plan(self, command: ExecuteDemoEditPlan) -> DemoEditingCreateResult:
        accepted = await self._commands.execute_edit_plan(command)
        return await self._accepted(
            actor_id=command.demo_actor_id,
            accepted=accepted,
            operation="edit_plan.execute",
        )

    async def restore_image_version(
        self, command: RestoreDemoImageVersion
    ) -> DemoEditingCreateResult:
        accepted = await self._commands.restore_image_version(command)
        return await self._accepted(
            actor_id=command.demo_actor_id,
            accepted=accepted,
            operation="image_version.restore",
        )

    async def get_tool_run(self, *, demo_actor_id: str, tool_run_id: str) -> DemoOwnedToolRun:
        return await self._commands.get_tool_run(
            demo_actor_id=demo_actor_id,
            tool_run_id=tool_run_id,
        )

    async def read_execution_result(
        self, *, demo_actor_id: str, job_id: str
    ) -> DemoEditExecutionResult:
        return await self._commands.read_execution_result(
            demo_actor_id=demo_actor_id,
            job_id=job_id,
        )

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        """Redispatch only the command service's durable PENDING projection."""

        dispatched: list[str] = []
        for candidate in await self._commands.reconciliation_candidates(limit=limit):
            message = DemoEditingTaskMessage(
                demo_actor_id=candidate.demo_actor_id,
                job_id=candidate.job_id,
                operation=cast(_Operation, candidate.endpoint_operation),
                request_id=candidate.request_id,
            )
            self._dispatch(message, raise_on_failure=True)
            dispatched.append(candidate.job_id)
        return tuple(dispatched)

    async def _accepted(
        self,
        *,
        actor_id: str,
        accepted: DemoEditingCommandAccepted,
        operation: _Operation,
    ) -> DemoEditingCreateResult:
        job = await self._jobs.get(demo_actor_id=actor_id, job_id=accepted.job_id)
        if job.status == "PENDING":
            self._dispatch(
                DemoEditingTaskMessage(
                    demo_actor_id=actor_id,
                    job_id=accepted.job_id,
                    operation=operation,
                    request_id=accepted.request_id,
                ),
                raise_on_failure=False,
            )
        return DemoEditingCreateResult(
            job=job,
            target_id=accepted.target_id,
            replayed=accepted.replayed,
        )

    def _dispatch(self, message: DemoEditingTaskMessage, *, raise_on_failure: bool) -> None:
        try:
            self._dispatcher.dispatch_demo_editing(message)
        except Exception:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="deferred",
                    operation="demo_editing",
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
                    operation="demo_editing",
                    job_id=message.job_id,
                    request_id=message.request_id,
                ),
            )


__all__ = ["DemoEditingCoordinator", "DemoEditingCreateResult"]
