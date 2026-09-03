from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_profile_commands import DemoProfileCommandService
from mirror_api.demo_profile_coordinator import DemoProfileCoordinator
from mirror_api.demo_profile_dispatcher import (
    CeleryDemoProfileDispatcher,
    RecoverablePendingDemoProfileDispatcher,
)
from mirror_api.demo_profile_service import DemoProfileCompilationService
from mirror_api.demo_profile_task_contract import DemoProfileDispatcher


@dataclass(frozen=True)
class DemoProfileInfrastructure:
    coordinator: DemoProfileCoordinator
    commands: DemoProfileCommandService
    results: DemoProfileCompilationService


def create_demo_profile_infrastructure(
    *,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
) -> DemoProfileInfrastructure:
    dispatcher: DemoProfileDispatcher
    if settings.task_runner == "celery":
        dispatcher = CeleryDemoProfileDispatcher(redis_url=settings.redis_url)
    else:
        dispatcher = RecoverablePendingDemoProfileDispatcher()
    commands = DemoProfileCommandService(session_factory=sessions)
    jobs = DemoJobService(session_factory=sessions)
    return DemoProfileInfrastructure(
        coordinator=DemoProfileCoordinator(
            commands=commands,
            jobs=jobs,
            dispatcher=dispatcher,
        ),
        commands=commands,
        results=DemoProfileCompilationService(session_factory=sessions),
    )


def get_demo_profile_coordinator(request: Request) -> DemoProfileCoordinator:
    return cast(
        DemoProfileCoordinator,
        request.app.state.demo_profile_infrastructure.coordinator,
    )


def get_demo_profile_commands(request: Request) -> DemoProfileCommandService:
    return cast(
        DemoProfileCommandService,
        request.app.state.demo_profile_infrastructure.commands,
    )


def get_demo_profile_results(request: Request) -> DemoProfileCompilationService:
    return cast(
        DemoProfileCompilationService,
        request.app.state.demo_profile_infrastructure.results,
    )


__all__ = [
    "DemoProfileInfrastructure",
    "create_demo_profile_infrastructure",
    "get_demo_profile_commands",
    "get_demo_profile_coordinator",
    "get_demo_profile_results",
]
