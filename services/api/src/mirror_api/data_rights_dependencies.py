from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.account_deletion.service import AccountDeletionService
from mirror_api.config import Settings
from mirror_api.data_export.service import DataExportService
from mirror_api.data_rights.coordinator import DataRightsCoordinator
from mirror_api.data_rights.dispatcher import (
    CeleryDataRightsDispatcher,
    RecoverableDataRightsDispatcher,
)
from mirror_api.providers.base import ObjectStorageProvider


@dataclass(frozen=True)
class DataRightsInfrastructure:
    coordinator: DataRightsCoordinator


def create_data_rights_infrastructure(
    *,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    storage: ObjectStorageProvider,
) -> DataRightsInfrastructure:
    dispatcher = (
        CeleryDataRightsDispatcher(redis_url=settings.redis_url)
        if settings.task_runner == "celery"
        else RecoverableDataRightsDispatcher()
    )
    return DataRightsInfrastructure(
        coordinator=DataRightsCoordinator(
            exports=DataExportService(
                session_factory=sessions,
                storage=storage,
                hmac_keyring=dict(settings.auth_hmac_keyring),
                hmac_active_kid=settings.auth_hmac_active_kid,
                retention_seconds=settings.data_export_retention_seconds,
            ),
            account_deletions=AccountDeletionService(
                session_factory=sessions,
                storage=storage,
                hmac_keyring=dict(settings.auth_hmac_keyring),
                hmac_active_kid=settings.auth_hmac_active_kid,
            ),
            dispatcher=dispatcher,
        )
    )


def get_data_rights_coordinator(request: Request) -> DataRightsCoordinator:
    return cast(DataRightsCoordinator, request.app.state.data_rights_infrastructure.coordinator)
