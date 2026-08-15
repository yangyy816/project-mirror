from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.asset_deletion.service import (
    AssetDeletionFailure,
    AssetDeletionService,
    RetryableAssetDeletionFailure,
)
from mirror_api.models import (
    Asset,
    AssetDeletionRequest,
    AssetVariant,
    ObjectDeletionEvidence,
    User,
    new_id,
)
from mirror_api.providers.base import DeleteResult
from mirror_api.providers.local import LocalObjectStorageProvider, sanitized_object_key_for_job

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 16, 21, tzinfo=UTC)


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


class FaultOnceStorage(LocalObjectStorageProvider):
    fail_next_delete = True

    async def delete_sanitized_object(self, *, object_key: str) -> DeleteResult:
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise RuntimeError("synthetic transient storage failure")
        return await super().delete_sanitized_object(object_key=object_key)


class ConcurrentDeleteStorage(LocalObjectStorageProvider):
    def __init__(self, *, root: Path) -> None:
        super().__init__(root=root)
        self._entered = 0
        self._release = asyncio.Event()

    async def delete_sanitized_object(self, *, object_key: str) -> DeleteResult:
        self._entered += 1
        if self._entered >= 2:
            self._release.set()
        await asyncio.wait_for(self._release.wait(), timeout=2)
        return await super().delete_sanitized_object(object_key=object_key)


async def _fixture(
    sessions: async_sessionmaker[AsyncSession], storage: LocalObjectStorageProvider
) -> tuple[User, Asset, Asset]:
    user = User(id=new_id(), phone_hash="d" * 128, status="active")
    payloads = (b"synthetic-original", b"synthetic-derived")
    assets: list[Asset] = []
    for index, payload in enumerate(payloads):
        key = sanitized_object_key_for_job(new_id())
        await storage.create_sanitized_object_if_absent(
            object_key=key,
            content_type="image/jpeg",
            content_length=len(payload),
            checksum_sha256=sha256(payload).hexdigest(),
            body=_body(payload),
        )
        assets.append(
            Asset(
                id=new_id(),
                owner_user_id=user.id,
                asset_role="original" if index == 0 else "derived",
                storage_key=key,
                mime_type="image/jpeg",
                byte_size=len(payload),
                width=64,
                height=64,
                sha256=sha256(payload).hexdigest(),
                synthetic=True,
            )
        )
    async with sessions() as session:
        session.add(user)
        await session.commit()
        session.add_all(assets)
        await session.commit()
        session.add(
            AssetVariant(
                id=new_id(),
                source_asset_id=assets[0].id,
                result_asset_id=assets[1].id,
                variant_type="synthetic_fixture",
            )
        )
        await session.commit()
    return user, assets[0], assets[1]


def _service(
    sessions: async_sessionmaker[AsyncSession], storage: LocalObjectStorageProvider
) -> AssetDeletionService:
    return AssetDeletionService(
        session_factory=sessions,
        storage=storage,
        hmac_keyring={"fixture-v1": "h" * 64},
        hmac_active_kid="fixture-v1",
        now=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_asset_deletion_tombstones_dependencies_and_records_each_object(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        storage = LocalObjectStorageProvider(root=tmp_path)
        user, original, derived = await _fixture(sessions, storage)
        service = _service(sessions, storage)
        outsider = User(id=new_id(), phone_hash="e" * 128, status="active")
        async with sessions() as session:
            session.add(outsider)
            await session.commit()
        with pytest.raises(AssetDeletionFailure):
            await service.request_deletion(
                user_id=outsider.id,
                asset_id=original.id,
                idempotency_key="horizontal-delete-attempt",
                request_id="delete-request-horizontal",
            )
        admitted = await service.request_deletion(
            user_id=user.id,
            asset_id=original.id,
            idempotency_key="delete-fixture-once",
            request_id="delete-request-1",
        )
        replay = await service.request_deletion(
            user_id=user.id,
            asset_id=original.id,
            idempotency_key="delete-fixture-once",
            request_id="delete-request-replay",
        )
        assert replay.job_id == admitted.job_id
        assert not replay.created
        async with sessions() as session:
            assert (await session.get(Asset, original.id)).deleted_at == NOW
            assert (await session.get(Asset, derived.id)).deleted_at == NOW

        completed = await service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"
        assert await service.process(job_id=admitted.job_id) is None
        async with sessions() as session:
            assert (
                await session.scalar(select(func.count()).select_from(ObjectDeletionEvidence)) == 2
            )
            request = await session.get(AssetDeletionRequest, admitted.request_id)
            assert request is not None and request.result_code == "objects_deleted"
        assert await storage.inspect_sanitized_object(object_key=original.storage_key) is None
        assert await storage.inspect_sanitized_object(object_key=derived.storage_key) is None


@pytest.mark.asyncio
async def test_asset_deletion_retries_without_false_completion(tmp_path: Path) -> None:
    async with _database() as sessions:
        storage = FaultOnceStorage(root=tmp_path)
        user, original, _ = await _fixture(sessions, storage)
        service = _service(sessions, storage)
        admitted = await service.request_deletion(
            user_id=user.id,
            asset_id=original.id,
            idempotency_key="retry-delete-fixture",
            request_id="delete-request-2",
        )
        with pytest.raises(RetryableAssetDeletionFailure):
            await service.process(job_id=admitted.job_id)
        async with sessions() as session:
            request = await session.get(AssetDeletionRequest, admitted.request_id)
            assert request is not None and request.status == "processing"
            assert (
                await session.scalar(select(func.count()).select_from(ObjectDeletionEvidence)) == 0
            )
        completed = await service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"


@pytest.mark.asyncio
async def test_asset_deletion_tombstones_dependency_discovered_after_admission(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        storage = LocalObjectStorageProvider(root=tmp_path)
        user, original, derived = await _fixture(sessions, storage)
        service = _service(sessions, storage)
        admitted = await service.request_deletion(
            user_id=user.id,
            asset_id=original.id,
            idempotency_key="delete-with-late-dependency",
            request_id="delete-request-late-dependency",
        )

        payload = b"synthetic-late-derived"
        key = sanitized_object_key_for_job(new_id())
        await storage.create_sanitized_object_if_absent(
            object_key=key,
            content_type="image/jpeg",
            content_length=len(payload),
            checksum_sha256=sha256(payload).hexdigest(),
            body=_body(payload),
        )
        late_derived = Asset(
            id=new_id(),
            owner_user_id=user.id,
            asset_role="derived",
            storage_key=key,
            mime_type="image/jpeg",
            byte_size=len(payload),
            width=64,
            height=64,
            sha256=sha256(payload).hexdigest(),
            synthetic=True,
        )
        async with sessions() as session:
            session.add(late_derived)
            await session.commit()
            session.add(
                AssetVariant(
                    id=new_id(),
                    source_asset_id=derived.id,
                    result_asset_id=late_derived.id,
                    variant_type="synthetic_late_fixture",
                )
            )
            await session.commit()

        completed = await service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"
        async with sessions() as session:
            persisted = await session.get(Asset, late_derived.id)
            assert persisted is not None and persisted.deleted_at == NOW
            assert (
                await session.scalar(select(func.count()).select_from(ObjectDeletionEvidence)) == 3
            )
        assert await storage.inspect_sanitized_object(object_key=key) is None


@pytest.mark.asyncio
async def test_asset_deletion_concurrent_duplicate_processing_is_idempotent(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        storage = ConcurrentDeleteStorage(root=tmp_path)
        user, original, _ = await _fixture(sessions, storage)
        service = _service(sessions, storage)
        admitted = await service.request_deletion(
            user_id=user.id,
            asset_id=original.id,
            idempotency_key="delete-concurrently",
            request_id="delete-request-concurrent",
        )

        results = await asyncio.gather(
            service.process(job_id=admitted.job_id),
            service.process(job_id=admitted.job_id),
        )
        assert all(result is not None and result.status == "completed" for result in results)
        async with sessions() as session:
            assert (
                await session.scalar(select(func.count()).select_from(ObjectDeletionEvidence)) == 2
            )


@pytest.mark.asyncio
async def test_asset_deletion_records_already_absent_as_stable_evidence(tmp_path: Path) -> None:
    async with _database() as sessions:
        storage = LocalObjectStorageProvider(root=tmp_path)
        user, original, derived = await _fixture(sessions, storage)
        service = _service(sessions, storage)
        admitted = await service.request_deletion(
            user_id=user.id,
            asset_id=original.id,
            idempotency_key="delete-already-absent",
            request_id="delete-request-already-absent",
        )
        assert await storage.delete_sanitized_object(object_key=derived.storage_key) == "deleted"

        completed = await service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"
        async with sessions() as session:
            result_codes = set(await session.scalars(select(ObjectDeletionEvidence.result_code)))
            assert result_codes == {"deleted", "already_absent"}
