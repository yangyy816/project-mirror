from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.account_deletion.service import (
    AccountDeletionService,
    RetryableAccountDeletionFailure,
)
from mirror_api.models import (
    AccountDeletionRequest,
    Asset,
    ConsentRecord,
    DataExportRequest,
    Job,
    ObjectDeletionEvidence,
    UploadIntent,
    User,
    UserSession,
    new_id,
)
from mirror_api.providers.local import (
    LocalObjectStorageProvider,
    sanitized_object_key_for_job,
)
from mirror_api.storage_keys import data_export_object_key

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 16, 23, tzinfo=UTC)


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


def _service(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider,
    clock: list[datetime],
) -> AccountDeletionService:
    return AccountDeletionService(
        session_factory=sessions,
        storage=storage,
        hmac_keyring={"fixture-v1": "h" * 64},
        hmac_active_kid="fixture-v1",
        now=lambda: clock[0],
    )


async def _create_quarantine_object(storage: LocalObjectStorageProvider, payload: bytes) -> str:
    digest = sha256(payload).hexdigest()
    key = f"quarantine/v1/{digest}"
    grant = await storage.create_private_upload_grant(
        object_key=key,
        content_type="image/png",
        content_length=len(payload),
        checksum_sha256=digest,
    )
    await storage.receive_private_upload(
        grant_id=grant.url.rsplit("/", 1)[-1],
        authorization=grant.required_headers["X-Mirror-Upload-Authorization"],
        content_type="image/png",
        content_length=len(payload),
        checksum_sha256=digest,
        body=_body(payload),
    )
    return key


async def _full_fixture(
    sessions: async_sessionmaker[AsyncSession], storage: LocalObjectStorageProvider
) -> tuple[User, Asset, UploadIntent, DataExportRequest, ConsentRecord, UserSession]:
    user = User(id=new_id(), phone_hash="3" * 128, status="active", created_at=NOW)
    session_row = UserSession(
        id=new_id(),
        user_id=user.id,
        family_id=new_id(),
        token_id=sha256(b"synthetic-session-reference").hexdigest(),
        refresh_token_hash="4" * 128,
        refresh_key_id="fixture-v1",
        expires_at=NOW + timedelta(days=1),
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
        policy_digest="5" * 64,
        action="grant",
        granted_at=NOW - timedelta(hours=1),
        source="web",
        request_id="account-consent-fixture",
        created_at=NOW - timedelta(hours=1),
    )
    quarantine_payload = b"synthetic-quarantine-object"
    quarantine_key = await _create_quarantine_object(storage, quarantine_payload)
    intent = UploadIntent(
        id=new_id(),
        owner_user_id=user.id,
        consent_record_id=consent.id,
        object_key=quarantine_key,
        declared_mime_type="image/png",
        declared_byte_size=len(quarantine_payload),
        declared_sha256=sha256(quarantine_payload).hexdigest(),
        status="uploaded_unverified",
        grant_expires_at=NOW - timedelta(minutes=1),
        uploaded_at=NOW - timedelta(minutes=5),
        quarantine_retention_deadline=NOW + timedelta(hours=1),
        created_at=NOW - timedelta(minutes=10),
    )
    asset_payload = b"synthetic-account-asset"
    asset_key = sanitized_object_key_for_job(new_id())
    await storage.create_sanitized_object_if_absent(
        object_key=asset_key,
        content_type="image/jpeg",
        content_length=len(asset_payload),
        checksum_sha256=sha256(asset_payload).hexdigest(),
        body=_body(asset_payload),
    )
    asset = Asset(
        id=new_id(),
        owner_user_id=user.id,
        asset_role="original",
        storage_key=asset_key,
        mime_type="image/jpeg",
        byte_size=len(asset_payload),
        width=64,
        height=64,
        sha256=sha256(asset_payload).hexdigest(),
        synthetic=True,
        created_at=NOW,
    )
    export_id = new_id()
    export_key = data_export_object_key(export_id)
    export_payload = b"synthetic-private-export"
    await storage.create_data_export_if_absent(
        object_key=export_key,
        content_length=len(export_payload),
        checksum_sha256=sha256(export_payload).hexdigest(),
        body=_body(export_payload),
    )
    export_job = Job(
        id=new_id(),
        owner_user_id=user.id,
        job_type="data_export",
        status="completed",
        idempotency_key_hash="6" * 64,
        request_id="export-job-fixture",
        payload={"schema_version": "data-export-task-v1"},
        finalized_at=NOW,
        result_code="archive_ready",
        created_at=NOW,
        updated_at=NOW,
    )
    export = DataExportRequest(
        id=export_id,
        owner_user_id=user.id,
        job_id=export_job.id,
        idempotency_key_hash="7" * 64,
        status="requested",
        schema_version="mirror-data-export-v1",
        requested_at=NOW - timedelta(minutes=2),
    )
    async with sessions() as session:
        session.add(user)
        await session.commit()
        session.add_all([session_row, consent, asset, export_job])
        await session.commit()
        session.add_all([intent, export])
        await session.commit()
        export.status = "processing"
        await session.commit()
        export.status = "ready"
        export.storage_key = export_key
        export.sha256 = sha256(export_payload).hexdigest()
        export.byte_size = len(export_payload)
        export.ready_at = NOW - timedelta(minutes=1)
        export.expires_at = NOW + timedelta(minutes=30)
        export.result_code = "archive_ready"
        await session.commit()
    return user, asset, intent, export, consent, session_row


@pytest.mark.asyncio
async def test_account_deletion_freezes_propagates_and_records_all_objects(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = LocalObjectStorageProvider(
            root=tmp_path, clock=lambda: NOW - timedelta(minutes=10)
        )
        user, asset, intent, export, consent, user_session = await _full_fixture(sessions, storage)
        service = _service(sessions, storage, clock)
        admitted = await service.request_deletion(
            user_id=user.id,
            idempotency_key="delete-account-once",
            request_id="account-delete-request",
        )
        replay = await service.request_deletion(
            user_id=user.id,
            idempotency_key="delete-account-once",
            request_id="account-delete-replay",
        )
        assert replay.request_id == admitted.request_id and not replay.created
        async with sessions() as session:
            frozen = await session.get(User, user.id)
            revoked = await session.get(UserSession, user_session.id)
            assert frozen is not None and frozen.status == "deletion_requested"
            assert revoked is not None and revoked.revoked_at == NOW

        completed = await service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"
        repeated = await service.process(job_id=admitted.job_id)
        assert repeated is not None and repeated.status == "completed"
        async with sessions() as session:
            deleted_user = await session.get(User, user.id)
            deleted_asset = await session.get(Asset, asset.id)
            deleted_intent = await session.get(UploadIntent, intent.id)
            deleted_export = await session.get(DataExportRequest, export.id)
            request = await session.get(AccountDeletionRequest, admitted.request_id)
            assert deleted_user is not None and deleted_user.status == "deleted"
            assert deleted_user.phone_hash != "3" * 128
            assert deleted_asset is not None and deleted_asset.deleted_at == NOW
            assert deleted_intent is not None and deleted_intent.status == "cancelled"
            assert deleted_export is not None and deleted_export.status == "expired"
            assert request is not None and request.result_code == "phase1_data_deleted"
            assert (
                await session.scalar(select(func.count()).select_from(ObjectDeletionEvidence)) == 3
            )
            withdrawal = await session.scalar(
                select(ConsentRecord).where(ConsentRecord.supersedes_id == consent.id)
            )
            assert withdrawal is not None and withdrawal.action == "withdraw"
        assert await storage.inspect_sanitized_object(object_key=asset.storage_key) is None
        assert await storage.inspect_quarantine_object(object_key=intent.object_key) is None
        assert await storage.inspect_data_export(object_key=export.storage_key) is None


@pytest.mark.asyncio
async def test_account_deletion_waits_for_preexisting_upload_grant_expiry(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = LocalObjectStorageProvider(root=tmp_path, clock=lambda: NOW)
        user = User(id=new_id(), phone_hash="8" * 128, status="active", created_at=NOW)
        consent = ConsentRecord(
            id=new_id(),
            user_id=user.id,
            consent_type="facial_data_processing",
            purpose="personal_aesthetic_baseline",
            purpose_version="purpose-v1",
            scope={"operations": ["private_upload"]},
            policy_code="facial-data-policy",
            policy_version="privacy-v1",
            policy_digest="9" * 64,
            action="grant",
            granted_at=NOW,
            source="web",
            request_id="future-grant-consent",
            created_at=NOW,
        )
        intent = UploadIntent(
            id=new_id(),
            owner_user_id=user.id,
            consent_record_id=consent.id,
            object_key=f"quarantine/v1/{'a' * 64}",
            declared_mime_type="image/png",
            declared_byte_size=10,
            declared_sha256="a" * 64,
            status="awaiting_upload",
            grant_expires_at=NOW + timedelta(minutes=5),
            created_at=NOW,
        )
        async with sessions() as session:
            session.add(user)
            await session.commit()
            session.add(consent)
            await session.commit()
            session.add(intent)
            await session.commit()
        service = _service(sessions, storage, clock)
        admitted = await service.request_deletion(
            user_id=user.id,
            idempotency_key="delete-with-live-grant",
            request_id="delete-with-live-grant-request",
        )
        with pytest.raises(RetryableAccountDeletionFailure, match="upload grant expiry"):
            await service.process(job_id=admitted.job_id)
        async with sessions() as session:
            request = await session.get(AccountDeletionRequest, admitted.request_id)
            assert request is not None and request.status == "processing"
            assert (
                await session.scalar(select(func.count()).select_from(ObjectDeletionEvidence)) == 0
            )
        clock[0] = NOW + timedelta(minutes=6)
        completed = await service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"


class FaultOnceAccountStorage(LocalObjectStorageProvider):
    fail_next_delete = True

    async def delete_sanitized_object(self, *, object_key: str):  # type: ignore[no-untyped-def]
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise RuntimeError("synthetic account storage outage")
        return await super().delete_sanitized_object(object_key=object_key)


class ConcurrentAccountStorage(LocalObjectStorageProvider):
    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._asset_delete_calls = 0
        self.both_asset_deletes_started = asyncio.Event()

    async def delete_sanitized_object(self, *, object_key: str):  # type: ignore[no-untyped-def]
        self._asset_delete_calls += 1
        if self._asset_delete_calls == 2:
            self.both_asset_deletes_started.set()
        await self.both_asset_deletes_started.wait()
        return await super().delete_sanitized_object(object_key=object_key)


@pytest.mark.asyncio
async def test_account_storage_failure_does_not_report_false_completion(tmp_path: Path) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = FaultOnceAccountStorage(root=tmp_path, clock=lambda: NOW - timedelta(minutes=10))
        user, _, _, _, _, _ = await _full_fixture(sessions, storage)
        service = _service(sessions, storage, clock)
        admitted = await service.request_deletion(
            user_id=user.id,
            idempotency_key="delete-account-retry",
            request_id="delete-account-retry-request",
        )
        with pytest.raises(RetryableAccountDeletionFailure):
            await service.process(job_id=admitted.job_id)
        async with sessions() as session:
            request = await session.get(AccountDeletionRequest, admitted.request_id)
            assert request is not None and request.status == "processing"
        completed = await service.process(job_id=admitted.job_id)
        assert completed is not None and completed.status == "completed"


@pytest.mark.asyncio
async def test_concurrent_duplicate_account_deletion_serializes_authority_before_evidence(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        clock = [NOW]
        storage = ConcurrentAccountStorage(
            root=tmp_path, clock=lambda: NOW - timedelta(minutes=10)
        )
        user, _, _, _, _, _ = await _full_fixture(sessions, storage)
        service = _service(sessions, storage, clock)
        admitted = await service.request_deletion(
            user_id=user.id,
            idempotency_key="delete-account-concurrently",
            request_id="account-delete-concurrent-request",
        )

        first = asyncio.create_task(service.process(job_id=admitted.job_id))
        second = asyncio.create_task(service.process(job_id=admitted.job_id))
        await asyncio.wait_for(storage.both_asset_deletes_started.wait(), timeout=5)
        results = await asyncio.wait_for(asyncio.gather(first, second), timeout=10)

        assert all(result is not None and result.status == "completed" for result in results)
        async with sessions() as session:
            assert await session.scalar(
                select(func.count()).select_from(ObjectDeletionEvidence)
            ) == 3
