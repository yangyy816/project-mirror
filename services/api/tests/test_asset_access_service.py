from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.asset_access.service import AssetAccessDenied, AssetAccessService
from mirror_api.models import Asset, AssetAccessAudit, User, new_id
from mirror_api.providers.local import (
    DOWNLOAD_AUTHORIZATION_HEADER,
    LocalObjectStorageProvider,
    LocalStorageOperationError,
    sanitized_object_key_for_job,
)

pytestmark = pytest.mark.integration


async def _body(payload: bytes) -> AsyncIterator[bytes]:
    yield payload


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE users CASCADE"))
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE users CASCADE"))
        await engine.dispose()


@pytest.mark.asyncio
async def test_asset_access_is_owner_bound_audited_and_revocable(tmp_path: Path) -> None:
    async with _database() as sessions:
        owner = User(id=new_id(), phone_hash="o" * 128, status="active")
        outsider = User(id=new_id(), phone_hash="p" * 128, status="active")
        key = sanitized_object_key_for_job(new_id())
        payload = b"synthetic-non-face-private-asset"
        asset = Asset(
            id=new_id(),
            owner_user_id=owner.id,
            asset_role="original",
            storage_key=key,
            mime_type="image/jpeg",
            byte_size=len(payload),
            width=64,
            height=64,
            sha256=sha256(payload).hexdigest(),
            synthetic=True,
        )
        async with sessions() as session:
            session.add_all([owner, outsider])
            await session.commit()
            session.add(asset)
            await session.commit()

        storage = LocalObjectStorageProvider(root=tmp_path)
        await storage.create_sanitized_object_if_absent(
            object_key=key,
            content_type="image/jpeg",
            content_length=len(payload),
            checksum_sha256=sha256(payload).hexdigest(),
            body=_body(payload),
        )
        service = AssetAccessService(session_factory=sessions, storage=storage)
        assert [item.id for item in await service.list_assets(user_id=owner.id)] == [asset.id]
        assert await service.list_assets(user_id=outsider.id) == ()
        with pytest.raises(AssetAccessDenied):
            await service.get_asset(user_id=outsider.id, asset_id=asset.id)

        result = await service.create_download_grant(
            user_id=owner.id, asset_id=asset.id, request_id="grant-request"
        )
        assert key not in result.grant.url
        grant_id = urlsplit(result.grant.url).path.rsplit("/", 1)[-1]
        redemption = await service.redeem_local_download(
            grant_id=grant_id,
            authorization=result.grant.required_headers[DOWNLOAD_AUTHORIZATION_HEADER],
            request_id="redeem-request",
        )
        assert b"".join([chunk async for chunk in redemption.body]) == payload
        with pytest.raises(LocalStorageOperationError):
            await service.redeem_local_download(
                grant_id=grant_id,
                authorization=result.grant.required_headers[DOWNLOAD_AUTHORIZATION_HEADER],
                request_id="replay-request",
            )
        revoked = await service.create_download_grant(
            user_id=owner.id, asset_id=asset.id, request_id="revoked-grant-request"
        )
        async with sessions() as session:
            stored = await session.get(Asset, asset.id)
            assert stored is not None
            stored.deleted_at = datetime.now(UTC)
            await session.commit()

        with pytest.raises(AssetAccessDenied):
            await service.redeem_local_download(
                grant_id=urlsplit(revoked.grant.url).path.rsplit("/", 1)[-1],
                authorization=revoked.grant.required_headers[DOWNLOAD_AUTHORIZATION_HEADER],
                request_id="revoked-redeem-request",
            )
        async with sessions() as session:
            actions = list(
                await session.scalars(
                    select(AssetAccessAudit.action).where(AssetAccessAudit.asset_id == asset.id)
                )
            )
            assert sorted(actions) == [
                "download_grant_created",
                "download_grant_created",
                "download_grant_redeemed",
            ]
            assert await session.scalar(select(func.count()).select_from(AssetAccessAudit)) == 3

        with pytest.raises(AssetAccessDenied):
            await service.create_download_grant(
                user_id=owner.id, asset_id=asset.id, request_id="deleted-request"
            )


@pytest.mark.asyncio
async def test_asset_download_rejects_storage_metadata_drift(tmp_path: Path) -> None:
    async with _database() as sessions:
        owner = User(id=new_id(), phone_hash="q" * 128, status="active")
        key = sanitized_object_key_for_job(new_id())
        stored_payload = b"synthetic-storage-payload"
        asset_payload = b"different-authoritative-payload"
        asset = Asset(
            id=new_id(),
            owner_user_id=owner.id,
            asset_role="original",
            storage_key=key,
            mime_type="image/jpeg",
            byte_size=len(asset_payload),
            width=64,
            height=64,
            sha256=sha256(asset_payload).hexdigest(),
            synthetic=True,
        )
        async with sessions() as session:
            session.add(owner)
            await session.commit()
            session.add(asset)
            await session.commit()
        storage = LocalObjectStorageProvider(root=tmp_path)
        await storage.create_sanitized_object_if_absent(
            object_key=key,
            content_type="image/jpeg",
            content_length=len(stored_payload),
            checksum_sha256=sha256(stored_payload).hexdigest(),
            body=_body(stored_payload),
        )
        service = AssetAccessService(session_factory=sessions, storage=storage)
        with pytest.raises(AssetAccessDenied):
            await service.create_download_grant(
                user_id=owner.id, asset_id=asset.id, request_id="drift-request"
            )
