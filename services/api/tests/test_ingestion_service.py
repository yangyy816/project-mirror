from __future__ import annotations

import hashlib
import os
from asyncio import gather
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.ingestion.service import IngestionService
from mirror_api.ingestion.types import IngestionFailure
from mirror_api.models import (
    Asset,
    AssetIngestionRecord,
    AuditLog,
    Job,
    JobAttempt,
    UploadIntentEvent,
    User,
    new_id,
)
from mirror_api.providers.local import (
    UPLOAD_AUTHORIZATION_HEADER,
    UPLOAD_CHECKSUM_HEADER,
    LocalObjectStorageProvider,
)
from mirror_api.rate_limit import FakeRateLimiter
from mirror_api.upload_control.service import ConsentService, UploadIntentService
from mirror_api.upload_control.types import ConsentRequirement, UploadDeclaration

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 16, 10, tzinfo=UTC)
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


async def _body(payload: bytes) -> AsyncIterator[bytes]:
    yield payload


def _synthetic_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 64), (15, 60, 120)).save(output, format="PNG")
    return output.getvalue()


class _ReadCountingStorage(LocalObjectStorageProvider):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.quarantine_read_count = 0

    def stream_quarantine_object(self, *, object_key: str) -> AsyncIterator[bytes]:
        self.quarantine_read_count += 1
        return super().stream_quarantine_object(object_key=object_key)


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
        source="integration_fixture",
        now=now,
    )


def _upload_service(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider,
    now: Callable[[], datetime],
    *,
    object_suffix: str,
    quarantine_retention_seconds: int = 3600,
) -> UploadIntentService:
    return UploadIntentService(
        session_factory=sessions,
        storage=storage,
        rate_limiter=FakeRateLimiter(now=lambda: 100.0),
        requirement=REQUIREMENT,
        hmac_keyring=HMAC_KEYRING,
        hmac_active_kid="fixture-v1",
        now=now,
        quarantine_retention_seconds=quarantine_retention_seconds,
        object_key_factory=lambda: f"quarantine/v1/{object_suffix * 64}",
    )


def _ingestion_service(
    sessions: async_sessionmaker[AsyncSession] | Callable[[], AsyncSession],
    storage: LocalObjectStorageProvider,
    now: Callable[[], datetime],
    *,
    lease_seconds: int = 300,
) -> IngestionService:
    return IngestionService(
        session_factory=sessions,
        storage=storage,
        requirement=REQUIREMENT,
        hmac_keyring=HMAC_KEYRING,
        hmac_active_kid="fixture-v1",
        lease_seconds=lease_seconds,
        now=now,
    )


class _CommitFailingFactory:
    def __init__(self, delegate: async_sessionmaker[AsyncSession], *, fail_at: int) -> None:
        self._delegate = delegate
        self._fail_at = fail_at
        self._commit_count = 0

    def __call__(self) -> AsyncSession:
        session = self._delegate()
        commit = session.commit

        async def fail_selected_commit() -> None:
            self._commit_count += 1
            if self._commit_count == self._fail_at:
                raise RuntimeError("deterministic database commit failure")
            await commit()

        session.commit = fail_selected_commit  # type: ignore[method-assign]
        return session


async def _uploaded_intent(
    sessions: async_sessionmaker[AsyncSession],
    storage: LocalObjectStorageProvider,
    user: User,
    now: Callable[[], datetime],
    *,
    object_suffix: str,
    payload: bytes,
    quarantine_retention_seconds: int = 3600,
) -> str:
    consent = _consent_service(sessions, now)
    await consent.grant(
        user_id=user.id,
        idempotency_key=f"consent-{object_suffix}",
        request_id=f"consent-request-{object_suffix}",
    )
    upload = _upload_service(
        sessions,
        storage,
        now,
        object_suffix=object_suffix,
        quarantine_retention_seconds=quarantine_retention_seconds,
    )
    declaration = UploadDeclaration(
        content_type="image/png",
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    created = await upload.create(
        user_id=user.id,
        declaration=declaration,
        idempotency_key=f"upload-create-{object_suffix}",
        request_id=f"upload-create-request-{object_suffix}",
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
    completed = await upload.complete(
        user_id=user.id,
        intent_id=created.intent.intent_id,
        idempotency_key=f"upload-complete-{object_suffix}",
        request_id=f"upload-complete-request-{object_suffix}",
    )
    assert completed.intent.status == "uploaded_unverified"
    return created.intent.intent_id


@pytest.mark.asyncio
async def test_promotes_once_and_preserves_safe_event_metadata(tmp_path: Path) -> None:
    def now() -> datetime:
        return NOW

    payload = _synthetic_png()
    async with _database() as sessions:
        user = await _user(sessions, "1")
        other = await _user(sessions, "2")
        storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        intent_id = await _uploaded_intent(
            sessions, storage, user, now, object_suffix="1", payload=payload
        )
        service = _ingestion_service(sessions, storage, now)
        created, replay = await gather(
            service.create(
                user_id=user.id,
                intent_id=intent_id,
                idempotency_key="ingestion-create-one",
                request_id="ingestion-create-request",
            ),
            service.create(
                user_id=user.id,
                intent_id=intent_id,
                idempotency_key="ingestion-create-two",
                request_id="ingestion-create-second-key",
            ),
        )
        assert created.job.job_id == replay.job.job_id
        assert sum(item.created for item in (created, replay)) == 1
        idempotency_replay = await service.create(
            user_id=user.id,
            intent_id=intent_id,
            idempotency_key="ingestion-create-one",
            request_id="ingestion-create-replay",
        )
        assert not idempotency_replay.created
        assert idempotency_replay.job.job_id == created.job.job_id
        with pytest.raises(IngestionFailure):
            await service.get(user_id=other.id, job_id=created.job.job_id)

        other_intent_id = await _uploaded_intent(
            sessions, storage, other, now, object_suffix="2", payload=payload
        )
        other_job = await service.create(
            user_id=other.id,
            intent_id=other_intent_id,
            idempotency_key="ingestion-create-one",
            request_id="other-ingestion-request",
        )
        assert other_job.created
        assert other_job.job.job_id != created.job.job_id

        claim = await service.claim(job_id=created.job.job_id)
        assert claim is not None
        promoted = await service.process(claim=claim)
        assert promoted is not None and promoted.job.status == "promoted"
        duplicate = await service.process(claim=claim)
        assert duplicate is not None and duplicate.job.asset_id == promoted.job.asset_id

        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Asset)) == 1
            assert await session.scalar(select(func.count()).select_from(AssetIngestionRecord)) == 1
            attempts = list((await session.scalars(select(JobAttempt))).all())
            assert [(attempt.attempt, attempt.status) for attempt in attempts] == [(1, "promoted")]
            events = list((await session.scalars(select(UploadIntentEvent))).all())
            assert {event.event_type for event in events} >= {
                "processing_started",
                "promoted",
            }
            safe_values = [event.metadata_json for event in events]
            safe_values.extend(
                audit.metadata_json for audit in await session.scalars(select(AuditLog))
            )
            assert all("object_key" not in value and "url" not in value for value in safe_values)


@pytest.mark.asyncio
async def test_stale_lease_is_closed_before_reclaim_and_old_claim_cannot_promote(
    tmp_path: Path,
) -> None:
    clock = {"now": NOW}

    def now() -> datetime:
        return clock["now"]

    payload = _synthetic_png()
    async with _database() as sessions:
        user = await _user(sessions, "3")
        storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        intent_id = await _uploaded_intent(
            sessions, storage, user, now, object_suffix="3", payload=payload
        )
        service = _ingestion_service(sessions, storage, now, lease_seconds=1)
        job = await service.create(
            user_id=user.id,
            intent_id=intent_id,
            idempotency_key="stale-claim",
            request_id="stale-request",
        )
        old_claim = await service.claim(job_id=job.job.job_id)
        assert old_claim is not None
        clock["now"] = NOW + timedelta(seconds=2)
        assert job.job.job_id in await service.reconcile()
        replacement = await service.claim(job_id=job.job.job_id)
        assert replacement is not None and replacement.attempt == 2
        assert await service.process(claim=old_claim) is None
        promoted = await service.process(claim=replacement)
        assert promoted is not None and promoted.job.status == "promoted"
        async with sessions() as session:
            attempts = list(
                (await session.scalars(select(JobAttempt).order_by(JobAttempt.attempt))).all()
            )
            assert [(attempt.attempt, attempt.status) for attempt in attempts] == [
                (1, "retryable_failure"),
                (2, "promoted"),
            ]


@pytest.mark.asyncio
async def test_deterministic_sanitizer_rejection_records_terminal_evidence(tmp_path: Path) -> None:
    def now() -> datetime:
        return NOW

    invalid_payload = b"synthetic-non-image-fixture"
    async with _database() as sessions:
        user = await _user(sessions, "4")
        storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        intent_id = await _uploaded_intent(
            sessions, storage, user, now, object_suffix="4", payload=invalid_payload
        )
        service = _ingestion_service(sessions, storage, now)
        job = await service.create(
            user_id=user.id,
            intent_id=intent_id,
            idempotency_key="invalid-image",
            request_id="invalid-image-request",
        )
        claim = await service.claim(job_id=job.job.job_id)
        assert claim is not None
        rejected = await service.process(claim=claim)
        assert rejected is not None
        assert rejected.job.status == "rejected"
        assert rejected.job.result_code == "image_magic_mismatch"
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Asset)) == 0
            record = await session.scalar(select(AssetIngestionRecord))
            assert record is not None and record.result_code == "image_magic_mismatch"
            event_types = set(await session.scalars(select(UploadIntentEvent.event_type)))
            assert "rejected" in event_types


@pytest.mark.asyncio
async def test_storage_retry_and_sanitized_conflict_have_distinct_terminal_semantics(
    tmp_path: Path,
) -> None:
    def now() -> datetime:
        return NOW

    payload = _synthetic_png()
    async with _database() as sessions:
        user = await _user(sessions, "5")
        storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        retry_intent = await _uploaded_intent(
            sessions, storage, user, now, object_suffix="5", payload=payload
        )
        service = _ingestion_service(sessions, storage, now)
        retry_job = await service.create(
            user_id=user.id,
            intent_id=retry_intent,
            idempotency_key="retry-job",
            request_id="retry-job-request",
        )
        assert retry_job.job.job_id in await service.reconcile()
        retry_claim = await service.claim(job_id=retry_job.job.job_id)
        assert retry_claim is not None
        assert retry_job.job.job_id not in await service.reconcile()
        await storage.delete_quarantine_object(object_key=f"quarantine/v1/{'5' * 64}")
        assert await service.process(claim=retry_claim) is None
        assert retry_job.job.job_id in await service.reconcile()

        conflict_intent = await _uploaded_intent(
            sessions, storage, user, now, object_suffix="6", payload=payload
        )
        conflict_job = await service.create(
            user_id=user.id,
            intent_id=conflict_intent,
            idempotency_key="conflict-job",
            request_id="conflict-job-request",
        )
        conflict_claim = await service.claim(job_id=conflict_job.job.job_id)
        assert conflict_claim is not None
        conflicting = b"synthetic-conflict"
        await storage.create_sanitized_object_if_absent(
            object_key=f"sanitized/v1/{conflict_job.job.job_id}",
            content_type="image/jpeg",
            content_length=len(conflicting),
            checksum_sha256=hashlib.sha256(conflicting).hexdigest(),
            body=_body(conflicting),
        )
        rejected = await service.process(claim=conflict_claim)
        assert rejected is not None
        assert rejected.job.status == "rejected"
        assert rejected.job.result_code == "sanitized_object_conflict"

        async with sessions() as session:
            attempts = list(
                (await session.scalars(select(JobAttempt).order_by(JobAttempt.started_at))).all()
            )
            retry_attempt = next(
                attempt for attempt in attempts if attempt.job_id == retry_job.job.job_id
            )
            assert retry_attempt.status == "retryable_failure"
            assert retry_attempt.error_code == "transient_storage_failure"


@pytest.mark.asyncio
async def test_withdrawal_and_retention_expiry_after_claim_block_promotion(tmp_path: Path) -> None:
    clock = {"now": NOW}

    def now() -> datetime:
        return clock["now"]

    payload = _synthetic_png()
    async with _database() as sessions:
        user = await _user(sessions, "7")
        storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        withdrawn_intent = await _uploaded_intent(
            sessions, storage, user, now, object_suffix="7", payload=payload
        )
        service = _ingestion_service(sessions, storage, now)
        withdrawn_job = await service.create(
            user_id=user.id,
            intent_id=withdrawn_intent,
            idempotency_key="withdrawn-job",
            request_id="withdrawn-job-request",
        )
        withdrawn_claim = await service.claim(job_id=withdrawn_job.job.job_id)
        assert withdrawn_claim is not None
        consent = _consent_service(sessions, now)
        state = await consent.current_state(user_id=user.id)
        assert state.grant_id is not None
        await consent.withdraw(
            user_id=user.id,
            grant_id=state.grant_id,
            idempotency_key="withdraw-after-claim",
            request_id="withdraw-after-claim-request",
        )
        withdrawn = await service.process(claim=withdrawn_claim)
        assert withdrawn is not None
        assert withdrawn.job.status == "rejected"
        assert withdrawn.job.result_code == "authorization_revoked"

        expiry_user = await _user(sessions, "8")
        expiry_intent = await _uploaded_intent(
            sessions,
            storage,
            expiry_user,
            now,
            object_suffix="8",
            payload=payload,
            quarantine_retention_seconds=1,
        )
        expiry_job = await service.create(
            user_id=expiry_user.id,
            intent_id=expiry_intent,
            idempotency_key="expiry-job",
            request_id="expiry-job-request",
        )
        expiry_claim = await service.claim(job_id=expiry_job.job.job_id)
        assert expiry_claim is not None
        clock["now"] = NOW + timedelta(seconds=2)
        expired = await service.process(claim=expiry_claim)
        assert expired is not None
        assert expired.job.status == "rejected"
        assert expired.job.result_code == "quarantine_retention_expired"

        frozen_user = await _user(sessions, "a")
        frozen_intent = await _uploaded_intent(
            sessions, storage, frozen_user, now, object_suffix="a", payload=payload
        )
        frozen_job = await service.create(
            user_id=frozen_user.id,
            intent_id=frozen_intent,
            idempotency_key="frozen-job",
            request_id="frozen-job-request",
        )
        frozen_claim = await service.claim(job_id=frozen_job.job.job_id)
        assert frozen_claim is not None
        async with sessions() as session:
            actor = await session.get(User, frozen_user.id)
            assert actor is not None
            actor.status = "pending"
            await session.commit()
        frozen = await service.process(claim=frozen_claim)
        assert frozen is not None
        assert frozen.job.status == "rejected"
        assert frozen.job.result_code == "authorization_revoked"


@pytest.mark.asyncio
async def test_database_commit_failure_after_sanitized_write_reuses_canonical_object_once(
    tmp_path: Path,
) -> None:
    clock = {"now": NOW}

    def now() -> datetime:
        return clock["now"]

    payload = _synthetic_png()
    async with _database() as sessions:
        user = await _user(sessions, "9")
        storage = LocalObjectStorageProvider(root=tmp_path, clock=now)
        intent_id = await _uploaded_intent(
            sessions, storage, user, now, object_suffix="9", payload=payload
        )
        faulting = _ingestion_service(
            _CommitFailingFactory(sessions, fail_at=4), storage, now, lease_seconds=1
        )
        job = await faulting.create(
            user_id=user.id,
            intent_id=intent_id,
            idempotency_key="commit-failure-job",
            request_id="commit-failure-request",
        )
        claim = await faulting.claim(job_id=job.job.job_id)
        assert claim is not None
        with pytest.raises(RuntimeError, match="database commit failure"):
            await faulting.process(claim=claim)
        assert (
            await storage.inspect_sanitized_object(object_key=f"sanitized/v1/{job.job.job_id}")
            is not None
        )

        clock["now"] = NOW + timedelta(seconds=2)
        recovered = _ingestion_service(sessions, storage, now, lease_seconds=1)
        replacement = await recovered.claim(job_id=job.job.job_id)
        assert replacement is not None and replacement.attempt == 2
        promoted = await recovered.process(claim=replacement)
        assert promoted is not None and promoted.job.status == "promoted"
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Asset)) == 1
            attempts = list(
                (await session.scalars(select(JobAttempt).order_by(JobAttempt.attempt))).all()
            )
            assert [(attempt.attempt, attempt.status) for attempt in attempts] == [
                (1, "retryable_failure"),
                (2, "promoted"),
            ]


@pytest.mark.asyncio
async def test_preclaim_tombstones_cancel_without_attempt_evidence_or_storage_read(
    tmp_path: Path,
) -> None:
    def now() -> datetime:
        return NOW

    payload = _synthetic_png()
    async with _database() as sessions:
        storage = _ReadCountingStorage(root=tmp_path, clock=now)
        service = _ingestion_service(sessions, storage, now)

        cancelled_user = await _user(sessions, "b")
        cancelled_intent = await _uploaded_intent(
            sessions, storage, cancelled_user, now, object_suffix="b", payload=payload
        )
        cancelled_job = await service.create(
            user_id=cancelled_user.id,
            intent_id=cancelled_intent,
            idempotency_key="cancel-before-claim",
            request_id="cancel-before-claim-request",
        )
        await _upload_service(sessions, storage, now, object_suffix="b").cancel(
            user_id=cancelled_user.id,
            intent_id=cancelled_intent,
            request_id="cancel-upload-request",
        )
        assert await service.claim(job_id=cancelled_job.job.job_id) is None

        withdrawn_user = await _user(sessions, "c")
        withdrawn_intent = await _uploaded_intent(
            sessions, storage, withdrawn_user, now, object_suffix="c", payload=payload
        )
        withdrawn_job = await service.create(
            user_id=withdrawn_user.id,
            intent_id=withdrawn_intent,
            idempotency_key="withdraw-before-claim",
            request_id="withdraw-before-claim-request",
        )
        consent = _consent_service(sessions, now)
        state = await consent.current_state(user_id=withdrawn_user.id)
        assert state.grant_id is not None
        await consent.withdraw(
            user_id=withdrawn_user.id,
            grant_id=state.grant_id,
            idempotency_key="withdraw-before-claim",
            request_id="withdraw-before-claim-request",
        )
        assert await service.claim(job_id=withdrawn_job.job.job_id) is None
        assert await service.claim(job_id=cancelled_job.job.job_id) is None
        assert await service.claim(job_id=withdrawn_job.job.job_id) is None
        assert storage.quarantine_read_count == 0

        async with sessions() as session:
            for job_id in (cancelled_job.job.job_id, withdrawn_job.job.job_id):
                job = await session.get(Job, job_id)
                assert job is not None
                assert job.status == "cancelled"
                assert job.attempt_count == 0
                assert job.result_code == "ingestion_cancelled_before_claim"
                assert job.finalized_at is not None
                assert job.result_asset_id is None
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(JobAttempt)
                        .where(JobAttempt.job_id == job.id)
                    )
                    == 0
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(AssetIngestionRecord)
                        .where(AssetIngestionRecord.job_id == job.id)
                    )
                    == 0
                )
            assert await session.scalar(select(func.count()).select_from(Asset)) == 0
            actions = set(
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.action == "asset_ingestion_cancelled_before_claim"
                    )
                )
            )
            assert actions == {"asset_ingestion_cancelled_before_claim"}
