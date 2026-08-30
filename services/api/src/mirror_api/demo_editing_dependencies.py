"""FastAPI dependency composition for D07 application orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.demo_editing_commands import DemoEditingCommandService
from mirror_api.demo_editing_coordinator import DemoEditingCoordinator
from mirror_api.demo_editing_dispatcher import (
    CeleryDemoEditingDispatcher,
    RecoverablePendingDemoEditingDispatcher,
)
from mirror_api.demo_editing_task_contract import DemoEditingDispatcher
from mirror_api.demo_job_service import DemoJobService


@dataclass(frozen=True)
class DemoEditingInfrastructure:
    coordinator: DemoEditingCoordinator
    commands: DemoEditingCommandService


def create_demo_editing_infrastructure(
    *, settings: Settings, sessions: async_sessionmaker[AsyncSession]
) -> DemoEditingInfrastructure:
    """Select only the existing task-runner adapter; never create a Provider."""

    dispatcher: DemoEditingDispatcher
    if settings.task_runner == "celery":
        dispatcher = CeleryDemoEditingDispatcher(redis_url=settings.redis_url)
    else:
        dispatcher = RecoverablePendingDemoEditingDispatcher()
    commands = DemoEditingCommandService(session_factory=sessions)
    jobs = DemoJobService(session_factory=sessions)
    return DemoEditingInfrastructure(
        coordinator=DemoEditingCoordinator(
            commands=commands,
            jobs=jobs,
            dispatcher=dispatcher,
        ),
        commands=commands,
    )


def get_demo_editing_coordinator(request: Request) -> DemoEditingCoordinator:
    return cast(
        DemoEditingCoordinator,
        request.app.state.demo_editing_infrastructure.coordinator,
    )


def get_demo_editing_commands(request: Request) -> DemoEditingCommandService:
    return cast(
        DemoEditingCommandService,
        request.app.state.demo_editing_infrastructure.commands,
    )


__all__ = [
    "DemoEditingInfrastructure",
    "create_demo_editing_infrastructure",
    "get_demo_editing_commands",
    "get_demo_editing_coordinator",
]
