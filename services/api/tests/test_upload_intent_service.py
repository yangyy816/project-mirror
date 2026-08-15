from __future__ import annotations

import os
from asyncio import gather
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import Asset, AuditLog, UploadIntent, UploadIntentEvent, User, new_id
from mirror_api.providers.base import (
    DeleteResult,
    PrivateUploadGrant,
    QuarantineObjectMetadata,
)
from mirror_api.providers.local import (
    UPLOAD_AUTHORIZATION_HEADER,
    UPLOAD_CHECKSUM_HEADER,
    LocalObjectStorageProvider,
)
from mirror_api.rate_limit import FakeRateLimiter
from mirror_api.upload_control.service import ConsentService, UploadIntentService
from mirror_api.upload_control.types import (
    ConsentRequirement,
    UploadDeclaration,
    UploadIntentFailure,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 16, 9, tzinfo=UTC)
REQUIREMENT = ConsentRequirement(
    consent_type="facial_data_processing",
    purpose_code="personal_aesthetic_baseline",
    purpose_version="purpose-v1",
    policy_code="facial-data-policy",
    policy_version="privacy-v1",
    policy_digest="a" * 64,
    operations=("private_upload", "security_validation"),
)
HMAC_KEYRING = {"fixture-v1": "h" * 64}


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
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


async def _user(
    sessions: async_sessionmaker[AsyncSession], *, seed: str, status: str = "active"
) -> User:
    user = User(id=new_id(), phone_hash=seed * 64, status=status)
    async with sessions() as session:
        session.add(user)
        await session.commit()
    return user


async def _grant_consent(
    sessions: async_sessionmaker[AsyncSession], user_id: str
) -> ConsentService:
    service = ConsentService(
        session_factory=sessions,
        requirement=REQUIREMENT,
        hmac_keyring=HMAC_KEYRING,
        hmac_active_kid="fixture-v1",
        source="integration_fixture",
        now=lambda: NOW,
    )
    await service.grant(
        user_id=user_id,
        idempotency_key="consent-fixture",
        request_id="consent-request",
    )
    return service


def _service(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider | _RecordingStorage,
    *,
    now: datetime = NOW,
    max_active_intents: int = 3,
) -> UploadIntentService:
    keys = iter(("1" * 64, "2" * 64, "3" * 64, "4" * 64))
    return UploadIntentService(
        session_factory=sessions,
        storage=storage,
        rate_limiter=FakeRateLimiter(now=lambda: 100.0),
        requirement=REQUIREMENT,
        hmac_keyring=HMAC_KEYRING,
        hmac_active_kid="fixture-v1",
        max_active_intents=max_active_intents,
        now=lambda: now,
        object_key_factory=lambda: f"quarantine/v1/{next(keys)}",
    )


def _declaration(body: bytes = b"synthetic-non-face-fixture") -> UploadDeclaration:
    import hashlib

    return UploadDeclaration(
        content_type="image/png",
        byte_size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )


async def _body(payload: bytes) -> AsyncIterator[bytes]:
    yield payload


class _RecordingStorage:
    def __init__(self, *, now: datetime = NOW) -> None:
        self.now = now
        self.metadata: QuarantineObjectMetadata | None = None
        self.deleted: list[str] = []
        self.granted: list[str] = []
        self.fail_create = False
        self.fail_delete = False

    async def create_private_upload_grant(
        self,
        *,
        object_key: str,
        content_type: str,
        content_length: int,
        checksum_sha256: str,
    ) -> PrivateUploadGrant:
        del content_type, content_length, checksum_sha256
        if self.fail_create:
            raise RuntimeError("deterministic grant failure")
        self.granted.append(object_key)
        return PrivateUploadGrant(
            method="PUT",
            url="https://storage.invalid/opaque",
            required_headers={},
            expires_at=self.now + timedelta(minutes=5),
        )

    async def inspect_quarantine_object(
        self, *, object_key: str
    ) -> QuarantineObjectMetadata | None:
        del object_key
        return self.metadata

    async def delete_quarantine_object(self, *, object_key: str) -> DeleteResult:
        if self.fail_delete:
            raise RuntimeError("deterministic cleanup failure")
        self.deleted.append(object_key)
        return "deleted"


@pytest.mark.asyncio
async def test_create_upload_and_complete_are_owner_bound_and_idempotent(tmp_path: Path) -> None:
    payload = b"synthetic-non-face-fixture"
    async with _database() as sessions:
        user = await _user(sessions, seed="1")
        await _grant_consent(sessions, user.id)
        storage = LocalObjectStorageProvider(root=tmp_path, clock=lambda: NOW)
        service = _service(sessions, storage)

        created = await service.create(
            user_id=user.id,
            declaration=_declaration(payload),
            idempotency_key="create-fixture",
            request_id="create-request",
        )
        replay = await service.create(
            user_id=user.id,
            declaration=_declaration(payload),
            idempotency_key="create-fixture",
            request_id="create-replay",
        )
        assert created.created and created.grant is not None
        assert replay.intent.intent_id == created.intent.intent_id
        assert replay.grant is None and not replay.created

        grant_id = created.grant.url.rsplit("/", 1)[-1]
        headers = created.grant.required_headers
        await storage.receive_private_upload(
            grant_id=grant_id,
            authorization=headers[UPLOAD_AUTHORIZATION_HEADER],
            content_type=headers["Content-Type"],
            content_length=int(headers["Content-Length"]),
            checksum_sha256=headers[UPLOAD_CHECKSUM_HEADER],
            body=_body(payload),
        )
        completed = await service.complete(
            user_id=user.id,
            intent_id=created.intent.intent_id,
            idempotency_key="complete-fixture",
            request_id="complete-request",
        )
        replayed = await service.complete(
            user_id=user.id,
            intent_id=created.intent.intent_id,
            idempotency_key="complete-fixture",
            request_id="complete-replay",
        )
        assert completed.intent.status == "uploaded_unverified" and completed.completed
        assert replayed.intent.status == "uploaded_unverified" and not replayed.completed
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Asset)) == 0
            assert await session.scalar(select(func.count()).select_from(UploadIntent)) == 1
            assert await session.scalar(select(func.count()).select_from(UploadIntentEvent)) == 3
            audits = list((await session.scalars(select(AuditLog))).all())
            assert {audit.action for audit in audits} >= {
                "upload_intent_created",
                "upload_intent_completed",
            }
            assert all("url" not in audit.metadata_json for audit in audits)


@pytest.mark.asyncio
async def test_missing_consent_pending_user_and_cross_user_access_are_rejected() -> None:
    async with _database() as sessions:
        active = await _user(sessions, seed="2")
        pending = await _user(sessions, seed="3", status="pending")
        other = await _user(sessions, seed="4")
        storage = _RecordingStorage()
        service = _service(sessions, storage)
        for user in (active, pending):
            with pytest.raises(UploadIntentFailure):
                await service.create(
                    user_id=user.id,
                    declaration=_declaration(),
                    idempotency_key=f"create-{user.id}",
                    request_id="rejected-create",
                )

        await _grant_consent(sessions, active.id)
        created = await service.create(
            user_id=active.id,
            declaration=_declaration(),
            idempotency_key="owner-create",
            request_id="owner-create-request",
        )
        with pytest.raises(UploadIntentFailure):
            await service.get(user_id=other.id, intent_id=created.intent.intent_id)
        with pytest.raises(UploadIntentFailure):
            await service.cancel(
                user_id=other.id,
                intent_id=created.intent.intent_id,
                request_id="cross-user-cancel",
            )
        with pytest.raises(UploadIntentFailure):
            await service.complete(
                user_id=other.id,
                intent_id=created.intent.intent_id,
                idempotency_key="cross-user-complete",
                request_id="cross-user-complete-request",
            )


@pytest.mark.asyncio
async def test_withdrawal_tombstones_and_deletes_a_late_upload(tmp_path: Path) -> None:
    payload = b"synthetic-late-upload"
    async with _database() as sessions:
        user = await _user(sessions, seed="5")
        consent = await _grant_consent(sessions, user.id)
        storage = LocalObjectStorageProvider(root=tmp_path, clock=lambda: NOW)
        service = _service(sessions, storage)
        created = await service.create(
            user_id=user.id,
            declaration=_declaration(payload),
            idempotency_key="late-create",
            request_id="late-create-request",
        )
        state = await consent.current_state(user_id=user.id)
        assert state.grant_id is not None
        await consent.withdraw(
            user_id=user.id,
            grant_id=state.grant_id,
            idempotency_key="consent-withdraw",
            request_id="consent-withdraw-request",
        )

        assert created.grant is not None
        grant_id = created.grant.url.rsplit("/", 1)[-1]
        headers = created.grant.required_headers
        await storage.receive_private_upload(
            grant_id=grant_id,
            authorization=headers[UPLOAD_AUTHORIZATION_HEADER],
            content_type=headers["Content-Type"],
            content_length=int(headers["Content-Length"]),
            checksum_sha256=headers[UPLOAD_CHECKSUM_HEADER],
            body=_body(payload),
        )
        with pytest.raises(UploadIntentFailure) as rejected:
            await service.complete(
                user_id=user.id,
                intent_id=created.intent.intent_id,
                idempotency_key="late-complete",
                request_id="late-complete-request",
            )
        assert rejected.value.code == "upload_intent_cancelled"
        assert (
            await storage.inspect_quarantine_object(object_key=f"quarantine/v1/{'1' * 64}") is None
        )


@pytest.mark.asyncio
async def test_metadata_mismatch_is_tombstoned_before_cleanup() -> None:
    async with _database() as sessions:
        user = await _user(sessions, seed="6")
        await _grant_consent(sessions, user.id)
        storage = _RecordingStorage()
        service = _service(sessions, storage)
        declaration = _declaration()
        created = await service.create(
            user_id=user.id,
            declaration=declaration,
            idempotency_key="mismatch-create",
            request_id="mismatch-create-request",
        )
        storage.metadata = QuarantineObjectMetadata(
            byte_size=declaration.byte_size + 1,
            content_type=declaration.content_type,
            sha256=declaration.sha256,
            etag="fixture-etag",
            uploaded_at=NOW,
        )
        with pytest.raises(UploadIntentFailure) as mismatch:
            await service.complete(
                user_id=user.id,
                intent_id=created.intent.intent_id,
                idempotency_key="mismatch-complete",
                request_id="mismatch-complete-request",
            )
        assert mismatch.value.code == "upload_metadata_mismatch"
        assert (await service.get(user_id=user.id, intent_id=created.intent.intent_id)).status == (
            "cancelled"
        )
        assert storage.deleted == [f"quarantine/v1/{'1' * 64}"]


@pytest.mark.asyncio
async def test_quota_and_cleanup_failure_remain_fail_closed() -> None:
    async with _database() as sessions:
        user = await _user(sessions, seed="7")
        await _grant_consent(sessions, user.id)
        storage = _RecordingStorage()
        service = _service(sessions, storage, max_active_intents=1)
        created = await service.create(
            user_id=user.id,
            declaration=_declaration(),
            idempotency_key="quota-create-one",
            request_id="quota-create-one-request",
        )
        with pytest.raises(UploadIntentFailure) as quota:
            await service.create(
                user_id=user.id,
                declaration=_declaration(b"second-synthetic-fixture"),
                idempotency_key="quota-create-two",
                request_id="quota-create-two-request",
            )
        assert quota.value.code == "upload_intent_quota_exceeded"

        storage.fail_delete = True
        with pytest.raises(UploadIntentFailure) as cleanup:
            await service.cancel(
                user_id=user.id,
                intent_id=created.intent.intent_id,
                request_id="cancel-with-cleanup-failure",
            )
        assert cleanup.value.code == "quarantine_cleanup_failed"
        assert (await service.get(user_id=user.id, intent_id=created.intent.intent_id)).status == (
            "cancelled"
        )
        storage.fail_delete = False
        replay = await service.cancel(
            user_id=user.id,
            intent_id=created.intent.intent_id,
            request_id="cancel-cleanup-retry",
        )
        assert not replay.cancelled and replay.cleanup_result == "deleted"


@pytest.mark.asyncio
async def test_concurrent_create_issues_one_grant_and_conflicting_replay_is_rejected() -> None:
    async with _database() as sessions:
        user = await _user(sessions, seed="8")
        await _grant_consent(sessions, user.id)
        storage = _RecordingStorage()
        service = _service(sessions, storage)
        first, second = await gather(
            service.create(
                user_id=user.id,
                declaration=_declaration(),
                idempotency_key="concurrent-create",
                request_id="concurrent-create-one",
            ),
            service.create(
                user_id=user.id,
                declaration=_declaration(),
                idempotency_key="concurrent-create",
                request_id="concurrent-create-two",
            ),
        )
        assert first.intent.intent_id == second.intent.intent_id
        assert sum(result.created for result in (first, second)) == 1
        assert len(storage.granted) == 1
        with pytest.raises(UploadIntentFailure) as conflict:
            await service.create(
                user_id=user.id,
                declaration=_declaration(b"different-fixture"),
                idempotency_key="concurrent-create",
                request_id="conflicting-create",
            )
        assert conflict.value.code == "idempotency_conflict"


@pytest.mark.asyncio
async def test_expired_intent_is_persistently_tombstoned_and_cleaned() -> None:
    async with _database() as sessions:
        user = await _user(sessions, seed="9")
        await _grant_consent(sessions, user.id)
        storage = _RecordingStorage()
        created = await _service(sessions, storage).create(
            user_id=user.id,
            declaration=_declaration(),
            idempotency_key="expiry-create",
            request_id="expiry-create-request",
        )
        expired_service = _service(sessions, storage, now=NOW + timedelta(minutes=6))
        with pytest.raises(UploadIntentFailure) as expired:
            await expired_service.complete(
                user_id=user.id,
                intent_id=created.intent.intent_id,
                idempotency_key="expiry-complete",
                request_id="expiry-complete-request",
            )
        assert expired.value.code == "upload_intent_expired"
        assert (
            await expired_service.get(user_id=user.id, intent_id=created.intent.intent_id)
        ).status == "expired"
        assert storage.deleted == [f"quarantine/v1/{'1' * 64}"]


@pytest.mark.asyncio
async def test_storage_grant_failure_rolls_back_intent_and_idempotency() -> None:
    async with _database() as sessions:
        user = await _user(sessions, seed="a")
        await _grant_consent(sessions, user.id)
        storage = _RecordingStorage()
        storage.fail_create = True
        service = _service(sessions, storage)
        with pytest.raises(RuntimeError, match="grant failure"):
            await service.create(
                user_id=user.id,
                declaration=_declaration(),
                idempotency_key="failed-grant-create",
                request_id="failed-grant-request",
            )
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(UploadIntent)) == 0
