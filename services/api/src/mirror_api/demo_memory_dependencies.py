from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_memory_coordinator import DemoMemoryCoordinator
from mirror_api.demo_memory_dispatcher import (
    CeleryDemoMemoryDispatcher,
    RecoverablePendingDemoMemoryDispatcher,
)
from mirror_api.demo_memory_service import DemoMemoryService
from mirror_api.demo_memory_task_contract import DemoMemoryDispatcher


@dataclass(frozen=True)
class DemoMemoryInfrastructure:
    coordinator: DemoMemoryCoordinator
    service: DemoMemoryService


def create_demo_memory_infrastructure(
    *, settings: Settings, sessions: async_sessionmaker[AsyncSession]
) -> DemoMemoryInfrastructure:
    dispatcher: DemoMemoryDispatcher
    if settings.task_runner == "celery":
        dispatcher = CeleryDemoMemoryDispatcher(redis_url=settings.redis_url)
    else:
        dispatcher = RecoverablePendingDemoMemoryDispatcher()
    service = DemoMemoryService(session_factory=sessions)
    return DemoMemoryInfrastructure(
        coordinator=DemoMemoryCoordinator(
            service=service,
            jobs=DemoJobService(session_factory=sessions),
            dispatcher=dispatcher,
        ),
        service=service,
    )


def get_demo_memory_coordinator(request: Request) -> DemoMemoryCoordinator:
    return cast(DemoMemoryCoordinator, request.app.state.demo_memory_infrastructure.coordinator)


def get_demo_memory_service(request: Request) -> DemoMemoryService:
    return cast(DemoMemoryService, request.app.state.demo_memory_infrastructure.service)


__all__ = [
    "DemoMemoryInfrastructure",
    "create_demo_memory_infrastructure",
    "get_demo_memory_coordinator",
    "get_demo_memory_service",
]
