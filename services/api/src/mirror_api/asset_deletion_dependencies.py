from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.asset_deletion.coordinator import AssetDeletionCoordinator
from mirror_api.asset_deletion.dispatcher import (
    CeleryAssetDeletionDispatcher,
    RecoverableAssetDeletionDispatcher,
)
from mirror_api.asset_deletion.service import AssetDeletionService
from mirror_api.config import Settings
from mirror_api.providers.base import ObjectStorageProvider


@dataclass(frozen=True)
class AssetDeletionInfrastructure:
    coordinator: AssetDeletionCoordinator


def create_asset_deletion_infrastructure(
    *,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    storage: ObjectStorageProvider,
) -> AssetDeletionInfrastructure:
    dispatcher = (
        CeleryAssetDeletionDispatcher(redis_url=settings.redis_url)
        if settings.task_runner == "celery"
        else RecoverableAssetDeletionDispatcher()
    )
    service = AssetDeletionService(
        session_factory=sessions,
        storage=storage,
        hmac_keyring=dict(settings.auth_hmac_keyring),
        hmac_active_kid=settings.auth_hmac_active_kid,
    )
    return AssetDeletionInfrastructure(
        coordinator=AssetDeletionCoordinator(service=service, dispatcher=dispatcher)
    )


def get_asset_deletion_coordinator(request: Request) -> AssetDeletionCoordinator:
    return cast(
        AssetDeletionCoordinator,
        request.app.state.asset_deletion_infrastructure.coordinator,
    )
