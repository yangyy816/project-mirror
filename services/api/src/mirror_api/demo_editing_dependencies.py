"""FastAPI dependency composition for D07 application orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings, get_settings
from mirror_api.demo_editing_asset_loader import LocalDemoAssetByteLoader
from mirror_api.demo_editing_commands import DemoEditingCommandService
from mirror_api.demo_editing_coordinator import DemoEditingCoordinator
from mirror_api.demo_editing_dispatcher import (
    CeleryDemoEditingDispatcher,
    RecoverablePendingDemoEditingDispatcher,
)
from mirror_api.demo_editing_media import DemoEditingMediaService
from mirror_api.demo_editing_task_contract import DemoEditingDispatcher
from mirror_api.demo_job_service import DemoJobService
from mirror_api.errors import APIError


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


def get_demo_editing_media_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> DemoEditingMediaService:
    if (
        settings.app_env not in {"development", "test", "ci"}
        or settings.synthetic_storage_provider != "local"
    ):
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DEMO_EDIT_MEDIA_RUNTIME_UNAVAILABLE",
            message="Demo 编辑图片运行环境当前不可用。",
            details={"track": "DEMO_PROTOTYPE"},
        )
    infrastructure = request.app.state.auth_infrastructure
    sessions = cast(async_sessionmaker[AsyncSession], infrastructure.sessions)
    return DemoEditingMediaService(
        session_factory=sessions,
        asset_loader=LocalDemoAssetByteLoader(root=settings.local_storage_root),
    )


__all__ = [
    "DemoEditingInfrastructure",
    "create_demo_editing_infrastructure",
    "get_demo_editing_commands",
    "get_demo_editing_coordinator",
    "get_demo_editing_media_service",
]
