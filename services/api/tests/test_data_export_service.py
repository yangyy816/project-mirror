from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.account_deletion.service import AccountDeletionService
from mirror_api.data_export.service import (
    DataExportAccessDenied,
    DataExportService,
    RetryableDataExportFailure,
)
from mirror_api.models import (
    Asset,
    ConsentRecord,
    DataExportRequest,
    ObjectDeletionEvidence,
    PolicyAcceptanceRecord,
    User,
    new_id,
)
from mirror_api.providers.local import LocalObjectStorageProvider, sanitized_object_key_for_job
from mirror_api.storage_keys import data_export_object_key

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 16, 22, tzinfo=UTC)


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


async def _fixture(
    sessions: async_sessionmaker[AsyncSession], storage: LocalObjectStorageProvider
) -> tuple[User, Asset, User]:
    user = User(id=new_id(), phone_hash="1" * 128, status="active", created_at=NOW)
    outsider = User(id=new_id(), phone_hash="2" * 128, status="active", created_at=NOW)
    payload = b"synthetic-export-asset"
    key = sanitized_object_key_for_job(new_id())
    await storage.create_sanitized_object_if_absent(
        object_key=key,
        content_type="image/jpeg",
        content_length=len(payload),
        checksum_sha256=sha256(payload).hexdigest(),
        body=_body(payload),
    )
    asset = Asset(
        id=new_id(),
        owner_user_id=user.id,
        asset_role="original",
        storage_key=key,
        mime_type="image/jpeg",
        byte_size=len(payload),
        width=64,
        height=64,
        sha256=sha256(payload).hexdigest(),
        synthetic=True,
        created_at=NOW,
    )
    policy = PolicyAcceptanceRecord(
        id=new_id(),
        user_id=user.id,
        document_code="terms",
        document_version="v1",
        document_digest="a" * 64,
        accepted_at=NOW,
        source="web",
        request_id="policy-fixture",
        created_at=NOW,
    )
    consent = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type="facial_data_processing",
        purpose="personal_aesthetic_baseline",
        purpose_version="purpose-v1",
        scope={"operations": ["private_upload"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="b" * 64,
        action="grant",
        granted_at=NOW,
        source="web",
        request_id="consent-fixture",
        created_at=NOW,
    )
    async with sessions() as session:
        session.add_all([user, outsider])
        await session.commit()
        session.add_all([asset, policy, consent])
        await session.commit()
    return user, asset, outsider


def _service(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider,
    clock: list[datetime],
) -> DataExportService:
    return DataExportService(
        session_factory=sessions,
        storage=storage,
        hmac_keyring={"fixture-v1": "h" * 64},
        hmac_active_kid="fixture-v1",
        retention_seconds=300,
        now=lambda: clock[0],
    )


async def _bytes(body: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in body])


@pytest.mark.asyncio
async def test_export_is_deterministic_isolated_and_excludes_internal_data(tmp_path: Path) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = LocalObjectStorageProvider(root=tmp_path, clock=lambda: clock[0])
        user, asset, outsider = await _fixture(sessions, storage)
        service = _service(sessions, storage, clock)
        requested = await service.request_export(
            user_id=user.id,
            idempotency_key="export-once",
            request_id="export-request",
        )
        replay = await service.request_export(
            user_id=user.id,
            idempotency_key="export-once",
            request_id="export-replay",
        )
        assert replay.export_id == requested.export_id and not replay.created
        ready = await service.process(job_id=requested.job_id)
        assert ready is not None and ready.status == "ready"
        repeated = await service.process(job_id=requested.job_id)
        assert repeated is not None and repeated.status == "ready"

        async with sessions() as session:
            export = await session.get(DataExportRequest, requested.export_id)
            assert export is not None and export.storage_key is not None
            first_digest = export.sha256
        archive_bytes = await _bytes(storage.stream_data_export(object_key=export.storage_key))
        assert sha256(archive_bytes).hexdigest() == first_digest
        with ZipFile(BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            assert names == [
                "account.json",
                "policy_acceptances.json",
                "consents.json",
                "assets/index.json",
                f"assets/{asset.id}.jpg",
                "manifest.json",
            ]
            assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)
            serialized = b"".join(archive.read(name) for name in names)
        assert outsider.id.encode() not in serialized
        assert user.phone_hash.encode() not in serialized
        assert asset.storage_key.encode() not in serialized
        assert b"refresh_token" not in serialized
        assert b"quarantine/v1" not in serialized

        with pytest.raises(DataExportAccessDenied):
            await service.get_export(user_id=outsider.id, export_id=requested.export_id)
        grant = await service.create_download_grant(user_id=user.id, export_id=requested.export_id)
        grant_id = grant.url.rsplit("/", 1)[-1]
        redemption = await service.redeem_local_download(
            grant_id=grant_id,
            authorization=grant.required_headers["X-Mirror-Download-Authorization"],
        )
        assert redemption.content_type == "application/zip"
        assert await _bytes(redemption.body) == archive_bytes


@pytest.mark.asyncio
async def test_export_retention_cleanup_is_idempotent_and_revokes_access(tmp_path: Path) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = LocalObjectStorageProvider(root=tmp_path, clock=lambda: clock[0])
        user, _, _ = await _fixture(sessions, storage)
        service = _service(sessions, storage, clock)
        requested = await service.request_export(
            user_id=user.id,
            idempotency_key="export-expiring",
            request_id="export-expiring-request",
        )
        ready = await service.process(job_id=requested.job_id)
        assert ready is not None and ready.expires_at == NOW + timedelta(seconds=300)
        clock[0] = NOW + timedelta(seconds=301)
        assert await service.cleanup_expired() == (requested.export_id,)
        assert await service.cleanup_expired() == ()
        with pytest.raises(DataExportAccessDenied):
            await service.create_download_grant(user_id=user.id, export_id=requested.export_id)
        async with sessions() as session:
            export = await session.get(DataExportRequest, requested.export_id)
            assert export is not None and export.status == "expired"
            assert (
                await session.scalar(select(func.count()).select_from(ObjectDeletionEvidence)) == 1
            )


class FaultOnceExportStorage(LocalObjectStorageProvider):
    fail_next = True

    async def create_data_export_if_absent(self, **kwargs):  # type: ignore[no-untyped-def]
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("synthetic export storage outage")
        return await super().create_data_export_if_absent(**kwargs)


class BlockingExportPublicationStorage(LocalObjectStorageProvider):
    def __init__(self, *, root: Path, clock: Callable[[], datetime]) -> None:
        super().__init__(root=root, clock=clock)
        self.object_created = asyncio.Event()
        self.allow_ready_commit = asyncio.Event()

    async def create_data_export_if_absent(self, **kwargs):  # type: ignore[no-untyped-def]
        metadata = await super().create_data_export_if_absent(**kwargs)
        self.object_created.set()
        await self.allow_ready_commit.wait()
        return metadata


@pytest.mark.asyncio
async def test_export_storage_failure_does_not_create_false_ready_state(tmp_path: Path) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = FaultOnceExportStorage(root=tmp_path, clock=lambda: clock[0])
        user, _, _ = await _fixture(sessions, storage)
        service = _service(sessions, storage, clock)
        requested = await service.request_export(
            user_id=user.id,
            idempotency_key="export-retry",
            request_id="export-retry-request",
        )
        with pytest.raises(RetryableDataExportFailure):
            await service.process(job_id=requested.job_id)
        async with sessions() as session:
            export = await session.get(DataExportRequest, requested.export_id)
            assert export is not None and export.status == "processing"
            assert export.storage_key is None
        ready = await service.process(job_id=requested.job_id)
        assert ready is not None and ready.status == "ready"


@pytest.mark.asyncio
async def test_export_publication_serializes_with_account_deletion_admission(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = BlockingExportPublicationStorage(root=tmp_path, clock=lambda: clock[0])
        user, _, _ = await _fixture(sessions, storage)
        export_service = _service(sessions, storage, clock)
        deletion_service = AccountDeletionService(
            session_factory=sessions,
            storage=storage,
            hmac_keyring={"fixture-v1": "h" * 64},
            hmac_active_kid="fixture-v1",
            now=lambda: clock[0],
        )
        requested = await export_service.request_export(
            user_id=user.id,
            idempotency_key="concurrent-export",
            request_id="concurrent-export-request",
        )

        publication = asyncio.create_task(export_service.process(job_id=requested.job_id))
        await asyncio.wait_for(storage.object_created.wait(), timeout=5)
        key = data_export_object_key(requested.export_id)
        assert await storage.inspect_data_export(object_key=key) is not None

        deletion_admission = asyncio.create_task(
            deletion_service.request_deletion(
                user_id=user.id,
                idempotency_key="concurrent-account-deletion",
                request_id="concurrent-account-deletion-request",
            )
        )
        _, still_waiting = await asyncio.wait({deletion_admission}, timeout=0.1)
        assert deletion_admission in still_waiting

        storage.allow_ready_commit.set()
        ready = await publication
        admitted = await deletion_admission
        assert ready is not None and ready.status == "ready"
        completed = await deletion_service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"
        assert await storage.inspect_data_export(object_key=key) is None


@pytest.mark.asyncio
async def test_account_deletion_recovers_export_object_without_ready_commit(tmp_path: Path) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = LocalObjectStorageProvider(root=tmp_path, clock=lambda: clock[0])
        user, _, _ = await _fixture(sessions, storage)
        export_service = _service(sessions, storage, clock)
        deletion_service = AccountDeletionService(
            session_factory=sessions,
            storage=storage,
            hmac_keyring={"fixture-v1": "h" * 64},
            hmac_active_kid="fixture-v1",
            now=lambda: clock[0],
        )
        requested = await export_service.request_export(
            user_id=user.id,
            idempotency_key="orphan-export",
            request_id="orphan-export-request",
        )
        started = await export_service._start(requested.job_id)
        assert started is not None and started.status == "processing"

        key = data_export_object_key(requested.export_id)
        payload = b"synthetic-export-created-before-ready-commit"
        await storage.create_data_export_if_absent(
            object_key=key,
            content_length=len(payload),
            checksum_sha256=sha256(payload).hexdigest(),
            body=_body(payload),
        )
        async with sessions() as session:
            export = await session.get(DataExportRequest, requested.export_id)
            assert export is not None and export.status == "processing"
            assert export.storage_key is None

        admitted = await deletion_service.request_deletion(
            user_id=user.id,
            idempotency_key="delete-account-with-orphan-export",
            request_id="delete-account-with-orphan-export-request",
        )
        completed = await deletion_service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"
        assert await storage.inspect_data_export(object_key=key) is None
        async with sessions() as session:
            export = await session.get(DataExportRequest, requested.export_id)
            assert export is not None and export.status == "failed"
            assert export.result_code == "account_deletion_requested"
            evidence = await session.scalar(
                select(ObjectDeletionEvidence).where(
                    ObjectDeletionEvidence.account_deletion_request_id == admitted.request_id,
                    ObjectDeletionEvidence.target_data_export_request_id == requested.export_id,
                )
            )
            assert evidence is not None
