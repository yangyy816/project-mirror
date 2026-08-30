from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.demo_editing_commands import DemoEditingCommandService
from mirror_api.demo_editing_coordinator import DemoEditingCoordinator
from mirror_api.demo_editing_dependencies import create_demo_editing_infrastructure


def test_non_celery_uses_recoverable_pending_boundary() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://mirror:mirror@localhost/mirror",
        redis_url="redis://localhost:6379/0",
        task_runner="local",
        sms_provider="mock",
        storage_provider="local",
        vision_provider="mock",
        image_generation_provider="mock",
        synthetic_storage_provider="local",
        agent_provider="mock",
        object_storage_private=True,
        sensitive_processing_enabled=False,
        local_storage_root=".local-storage",
    )
    # The factory only retains the injected session maker; no connection is opened.
    infrastructure = create_demo_editing_infrastructure(
        settings=settings,
        sessions=cast(async_sessionmaker[AsyncSession], object()),
    )
    assert isinstance(infrastructure.coordinator, DemoEditingCoordinator)
    assert isinstance(infrastructure.commands, DemoEditingCommandService)
