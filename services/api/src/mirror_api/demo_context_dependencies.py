from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.demo_context_coordinator import DemoContextCoordinator
from mirror_api.demo_context_dispatcher import (
    CeleryDemoContextDispatcher,
    RecoverablePendingDemoContextDispatcher,
)
from mirror_api.demo_context_queue_service import DemoContextQueueService
from mirror_api.demo_context_task_contract import DemoContextDispatcher
from mirror_api.demo_job_service import DemoJobService


@dataclass(frozen=True, slots=True)
class DemoContextInfrastructure:
    coordinator: DemoContextCoordinator
    service: DemoContextQueueService


def create_demo_context_infrastructure(
    *, settings: Settings, sessions: async_sessionmaker[AsyncSession]
) -> DemoContextInfrastructure:
    dispatcher: DemoContextDispatcher = (
        CeleryDemoContextDispatcher(redis_url=settings.redis_url)
        if settings.task_runner == "celery"
        else RecoverablePendingDemoContextDispatcher()
    )
    service = DemoContextQueueService(session_factory=sessions)
    return DemoContextInfrastructure(
        DemoContextCoordinator(
            service=service, jobs=DemoJobService(session_factory=sessions), dispatcher=dispatcher
        ),
        service,
    )


def get_demo_context_coordinator(request: Request) -> DemoContextCoordinator:
    return cast(DemoContextCoordinator, request.app.state.demo_context_infrastructure.coordinator)


def get_demo_context_service(request: Request) -> DemoContextQueueService:
    return cast(DemoContextQueueService, request.app.state.demo_context_infrastructure.service)


__all__ = [
    "DemoContextInfrastructure",
    "create_demo_context_infrastructure",
    "get_demo_context_coordinator",
    "get_demo_context_service",
]
