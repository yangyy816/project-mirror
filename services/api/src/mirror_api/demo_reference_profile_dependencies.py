from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_reference_profile_coordinator import DemoReferenceProfileCoordinator
from mirror_api.demo_reference_profile_dispatcher import (
    CeleryDemoReferenceProfileDispatcher,
    RecoverablePendingDemoReferenceProfileDispatcher,
)
from mirror_api.demo_reference_profile_service import DemoReferenceProfileService
from mirror_api.demo_reference_profile_task_contract import DemoReferenceProfileDispatcher


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileInfrastructure:
    coordinator: DemoReferenceProfileCoordinator
    service: DemoReferenceProfileService


def create_demo_reference_profile_infrastructure(
    *,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
) -> DemoReferenceProfileInfrastructure:
    dispatcher: DemoReferenceProfileDispatcher
    if settings.task_runner == "celery":
        dispatcher = CeleryDemoReferenceProfileDispatcher(redis_url=settings.redis_url)
    else:
        dispatcher = RecoverablePendingDemoReferenceProfileDispatcher()
    service = DemoReferenceProfileService(session_factory=sessions)
    return DemoReferenceProfileInfrastructure(
        coordinator=DemoReferenceProfileCoordinator(
            service=service,
            jobs=DemoJobService(session_factory=sessions),
            dispatcher=dispatcher,
        ),
        service=service,
    )


def get_demo_reference_profile_coordinator(request: Request) -> DemoReferenceProfileCoordinator:
    return cast(
        DemoReferenceProfileCoordinator,
        request.app.state.demo_reference_profile_infrastructure.coordinator,
    )


def get_demo_reference_profile_service(request: Request) -> DemoReferenceProfileService:
    return cast(
        DemoReferenceProfileService,
        request.app.state.demo_reference_profile_infrastructure.service,
    )


__all__ = [
    "DemoReferenceProfileInfrastructure",
    "create_demo_reference_profile_infrastructure",
    "get_demo_reference_profile_coordinator",
    "get_demo_reference_profile_service",
]
