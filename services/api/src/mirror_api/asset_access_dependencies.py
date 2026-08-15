from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.asset_access.service import AssetAccessService
from mirror_api.providers.base import ObjectStorageProvider


@dataclass(frozen=True)
class AssetAccessInfrastructure:
    service: AssetAccessService


def create_asset_access_infrastructure(
    *, sessions: async_sessionmaker[AsyncSession], storage: ObjectStorageProvider
) -> AssetAccessInfrastructure:
    return AssetAccessInfrastructure(
        service=AssetAccessService(session_factory=sessions, storage=storage)
    )


def get_asset_access_service(request: Request) -> AssetAccessService:
    return cast(AssetAccessService, request.app.state.asset_access_infrastructure.service)
