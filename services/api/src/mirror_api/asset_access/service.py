from __future__ import annotations

import hmac

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.asset_access.repository import AssetAccessRepository
from mirror_api.asset_access.types import AssetDownloadGrantResult, AssetView
from mirror_api.models import Asset, AssetAccessAudit, new_id
from mirror_api.providers.base import ObjectStorageProvider
from mirror_api.providers.local import LocalDownloadRedemption, LocalObjectStorageProvider


class AssetAccessDenied(Exception):
    """The requested asset is absent, deleted, or not available to this actor."""


class AssetAccessService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: ObjectStorageProvider,
    ) -> None:
        self._sessions = session_factory
        self._storage = storage

    async def list_assets(self, *, user_id: str) -> tuple[AssetView, ...]:
        async with self._sessions() as session:
            assets = await AssetAccessRepository(session).active_owned_assets(user_id=user_id)
            return tuple(self._view(asset) for asset in assets)

    async def get_asset(self, *, user_id: str, asset_id: str) -> AssetView:
        async with self._sessions() as session:
            asset = await AssetAccessRepository(session).active_owned_asset(
                user_id=user_id, asset_id=asset_id
            )
            if asset is None:
                raise AssetAccessDenied()
            return self._view(asset)

    async def create_download_grant(
        self, *, user_id: str, asset_id: str, request_id: str
    ) -> AssetDownloadGrantResult:
        async with self._sessions() as session:
            repository = AssetAccessRepository(session)
            asset = await repository.active_owned_asset(user_id=user_id, asset_id=asset_id)
            if asset is None:
                raise AssetAccessDenied()
            metadata = await self._storage.inspect_sanitized_object(object_key=asset.storage_key)
            if metadata is None or not (
                metadata.content_type == asset.mime_type
                and metadata.byte_size == asset.byte_size
                and hmac.compare_digest(metadata.sha256, asset.sha256)
            ):
                raise AssetAccessDenied()
            grant = await self._storage.create_private_download_grant(
                object_key=asset.storage_key,
                request_reference=asset.id,
            )
            session.add(
                AssetAccessAudit(
                    id=new_id(),
                    asset_id=asset.id,
                    actor_user_id=user_id,
                    action="download_grant_created",
                    request_id=request_id,
                )
            )
            await session.commit()
            return AssetDownloadGrantResult(asset=self._view(asset), grant=grant)

    async def redeem_local_download(
        self, *, grant_id: str, authorization: str, request_id: str
    ) -> LocalDownloadRedemption:
        if not isinstance(self._storage, LocalObjectStorageProvider):
            raise AssetAccessDenied()
        redemption = await self._storage.redeem_private_download_grant(
            grant_id=grant_id,
            authorization=authorization,
        )
        async with self._sessions() as session:
            asset = await AssetAccessRepository(session).active_asset_by_reference(
                asset_id=redemption.request_reference
            )
            if asset is None:
                raise AssetAccessDenied()
            if not (
                redemption.content_type == asset.mime_type
                and redemption.content_length == asset.byte_size
                and hmac.compare_digest(redemption.sha256, asset.sha256)
            ):
                raise AssetAccessDenied()
            session.add(
                AssetAccessAudit(
                    id=new_id(),
                    asset_id=asset.id,
                    actor_user_id=asset.owner_user_id,
                    action="download_grant_redeemed",
                    request_id=request_id,
                )
            )
            await session.commit()
        return redemption

    @staticmethod
    def _view(asset: Asset) -> AssetView:
        return AssetView(
            id=asset.id,
            asset_role=asset.asset_role,
            mime_type=asset.mime_type,
            byte_size=asset.byte_size,
            width=asset.width,
            height=asset.height,
            created_at=asset.created_at,
        )
