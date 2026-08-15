from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from mirror_api.ingestion.service import IngestionService
from mirror_api.models import Asset, Job, UploadIntent, User, new_id
from mirror_api.providers.local import (
    UPLOAD_AUTHORIZATION_HEADER,
    UPLOAD_CHECKSUM_HEADER,
    LocalObjectStorageProvider,
)
from mirror_api.rate_limit import FakeRateLimiter
from mirror_api.upload_control.service import ConsentService, UploadIntentService
from mirror_api.upload_control.types import ConsentRequirement, UploadDeclaration
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_worker.cleanup import SqlAlchemyIngestionCleanup
from mirror_worker.ingestion import (
    IngestionMaintenance,
    IngestionTaskExecutor,
    IngestionTaskMessage,
    RetryableWorkerFailure,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)
HMAC_KEYRING = {"fixture-v1": "h" * 64}
REQUIREMENT = ConsentRequirement(
    consent_type="facial_data_processing",
    purpose_code="personal_aesthetic_baseline",
    purpose_version="purpose-v1",
    policy_code="facial-data-policy",
    policy_version="privacy-v1",
    policy_digest="a" * 64,
    operations=("private_upload", "security_validation"),
)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE audit_logs, users CASCADE"))
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE audit_logs, users CASCADE"))
        await engine.dispose()


async def _body(payload: bytes) -> AsyncIterator[bytes]:
    yield payload


def _synthetic_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 64), (20, 90, 140)).save(output, format="PNG")
    return output.getvalue()


async def _user(sessions: async_sessionmaker[AsyncSession], seed: str) -> User:
    user = User(id=new_id(), phone_hash=seed * 64, status="active")
    async with sessions() as session:
        session.add(user)
        await session.commit()
    return user


def _consent_service(
    sessions: async_sessionmaker[AsyncSession], now: Callable[[], datetime]
) -> ConsentService:
    return ConsentService(
        session_factory=sessions,
        requirement=REQUIREMENT,
        hmac_keyring=HMAC_KEYRING,
        hmac_active_kid="fixture-v1",
        source="worker_integration_fixture",
        now=now,
    )


def _upload_service(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider,
    now: Callable[[], datetime],
    *,
    suffix: str,
    retention_seconds: int = 3_600,
) -> UploadIntentService:
    return UploadIntentService(
        session_factory=sessions,
        storage=storage,
        rate_limiter=FakeRateLimiter(now=lambda: 100.0),
        requirement=REQUIREMENT,
        hmac_keyring=HMAC_KEYRING,
        hmac_active_kid="fixture-v1",
        now=now,
        quarantine_retention_seconds=retention_seconds,
        object_key_factory=lambda: f"quarantine/v1/{suffix * 64}",
    )


async def _uploaded_intent(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider,
    user: User,
    now: Callable[[], datetime],
    *,
    suffix: str,
    payload: bytes,
    retention_seconds: int = 3_600,
) -> str:
    await _consent_service(sessions, now).grant(
        user_id=user.id,
        idempotency_key=f"consent-{suffix}",
        request_id=f"consent-request-{suffix}",
    )
    upload = _upload_service(
        sessions, storage, now, suffix=suffix, retention_seconds=retention_seconds
    )
    declaration = UploadDeclaration(
        content_type="image/png",
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    created = await upload.create(
        user_id=user.id,
        declaration=declaration,
        idempotency_key=f"upload-{suffix}",
        request_id=f"upload-request-{suffix}",
    )
    assert created.grant is not None
    headers = created.grant.required_headers
    await storage.receive_private_upload(
        grant_id=created.grant.url.rsplit("/", 1)[-1],
        authorization=headers[UPLOAD_AUTHORIZATION_HEADER],
        content_type=headers["Content-Type"],
        content_length=int(headers["Content-Length"]),
        checksum_sha256=headers[UPLOAD_CHECKSUM_HEADER],
        body=_body(payload),
    )
    completed = await upload.complete(
        user_id=user.id,
        intent_id=created.intent.intent_id,
        idempotency_key=f"complete-{suffix}",
        request_id=f"complete-request-{suffix}",
    )
    assert completed.intent.status == "uploaded_unverified"
    return created.intent.intent_id


def _ingestion_service(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider,
    now: Callable[[], datetime],
) -> IngestionService:
    return IngestionService(
        session_factory=sessions,
        storage=storage,
        requirement=REQUIREMENT,
        hmac_keyring=HMAC_KEYRING,
        hmac_active_kid="fixture-v1",
        now=now,
    )


class _FailOnceCleanupStorage(LocalObjectStorageProvider):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.fail_next_quarantine_delete = True

    async def delete_quarantine_object(self, *, object_key: str) -> str:
        if self.fail_next_quarantine_delete:
            self.fail_next_quarantine_delete = False
            raise RuntimeError("synthetic post-commit cleanup outage")
        return await super().delete_quarantine_object(object_key=object_key)


@pytest.mark.asyncio
async def test_post_commit_cleanup_retry_does_not_duplicate_original(tmp_path: Path) -> None:
    def now() -> datetime:
        return NOW

    async with _database() as sessions:
        user = await _user(sessions, "d")
        upload_storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        intent_id = await _uploaded_intent(
            sessions,
            upload_storage,
            user,
            now,
            suffix="d",
            payload=_synthetic_png(),
        )
        worker_storage = _FailOnceCleanupStorage(root=tmp_path, clock=now)
        application = _ingestion_service(sessions, worker_storage, now)
        cleanup = SqlAlchemyIngestionCleanup(
            session_factory=sessions, storage=worker_storage, now=now
        )
        job = await application.create(
            user_id=user.id,
            intent_id=intent_id,
            idempotency_key="worker-cleanup-retry",
            request_id="worker-cleanup-request",
        )
        message = IngestionTaskMessage(job_id=job.job.job_id, request_id="worker-dispatch-request")
        executor = IngestionTaskExecutor(application, cleanup)
        with pytest.raises(RetryableWorkerFailure, match="cleanup remains retryable"):
            await executor.execute(message)
        replay = await executor.execute(message)
        assert replay.status == "promoted"
        assert (
            await worker_storage.inspect_quarantine_object(object_key=f"quarantine/v1/{'d' * 64}")
            is None
        )
        assert (
            await worker_storage.inspect_sanitized_object(
                object_key=f"sanitized/v1/{job.job.job_id}"
            )
            is not None
        )
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Asset)) == 1


@pytest.mark.asyncio
async def test_expired_quarantine_without_job_is_tombstoned_and_deleted(tmp_path: Path) -> None:
    clock = {"now": NOW}

    def now() -> datetime:
        return clock["now"]

    async with _database() as sessions:
        user = await _user(sessions, "e")
        upload_storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        intent_id = await _uploaded_intent(
            sessions,
            upload_storage,
            user,
            now,
            suffix="e",
            payload=_synthetic_png(),
            retention_seconds=1,
        )
        clock["now"] = NOW + timedelta(seconds=2)
        worker_storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        cleanup = SqlAlchemyIngestionCleanup(
            session_factory=sessions, storage=worker_storage, now=now
        )
        result = await IngestionMaintenance(cleanup).execute(limit=10)
        assert result.expired_intents_tombstoned == 1
        async with sessions() as session:
            intent = await session.get(UploadIntent, intent_id)
            assert intent is not None and intent.status == "expired"
            assert intent.expired_at == clock["now"]
            assert await session.scalar(select(func.count()).select_from(Job)) == 0
        assert (
            await worker_storage.inspect_quarantine_object(object_key=f"quarantine/v1/{'e' * 64}")
            is None
        )
