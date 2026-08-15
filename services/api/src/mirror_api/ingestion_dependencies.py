from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.ingestion.coordinator import IngestionCoordinator
from mirror_api.ingestion.dispatcher import CeleryIngestionDispatcher, RecoverablePendingDispatcher
from mirror_api.ingestion.service import IngestionService
from mirror_api.ingestion.task_contract import IngestionDispatcher
from mirror_api.providers.base import ObjectStorageProvider
from mirror_api.upload_control.types import ConsentRequirement


@dataclass(frozen=True)
class IngestionInfrastructure:
    coordinator: IngestionCoordinator


def create_ingestion_infrastructure(
    *,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    storage: ObjectStorageProvider,
    requirement: ConsentRequirement,
) -> IngestionInfrastructure:
    dispatcher: IngestionDispatcher
    if settings.task_runner == "celery":
        dispatcher = CeleryIngestionDispatcher(redis_url=settings.redis_url)
    else:
        dispatcher = RecoverablePendingDispatcher()
    service = IngestionService(
        session_factory=sessions,
        storage=storage,
        requirement=requirement,
        hmac_keyring=settings.auth_hmac_keyring,
        hmac_active_kid=settings.auth_hmac_active_kid,
    )
    return IngestionInfrastructure(
        coordinator=IngestionCoordinator(service=service, dispatcher=dispatcher)
    )


def get_ingestion_coordinator(request: Request) -> IngestionCoordinator:
    return cast(IngestionCoordinator, request.app.state.ingestion_infrastructure.coordinator)
