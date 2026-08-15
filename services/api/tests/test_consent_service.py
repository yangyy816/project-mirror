from __future__ import annotations

import os
from asyncio import gather
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import (
    AuditLog,
    ConsentRecord,
    IdempotencyRecord,
    UploadIntent,
    UploadIntentEvent,
    User,
    new_id,
)
from mirror_api.upload_control.service import ConsentService
from mirror_api.upload_control.types import ConsentFailure, ConsentRequirement

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 16, 8, tzinfo=UTC)
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


def _service(
    sessions: async_sessionmaker[AsyncSession],
    *,
    requirement: ConsentRequirement = REQUIREMENT,
) -> ConsentService:
    return ConsentService(
        session_factory=sessions,
        requirement=requirement,
        hmac_keyring={"fixture-v1": "h" * 64},
        hmac_active_kid="fixture-v1",
        source="integration_fixture",
        now=lambda: NOW,
    )


async def _add_user(
    sessions: async_sessionmaker[AsyncSession], *, status: str = "active", seed: str = "1"
) -> User:
    user = User(id=new_id(), phone_hash=seed * 64, status=status)
    async with sessions() as session:
        session.add(user)
        await session.commit()
    return user


@pytest.mark.asyncio
async def test_only_active_user_can_grant_and_replays_are_idempotent() -> None:
    async with _database() as sessions:
        user = await _add_user(sessions, status="pending")
        service = _service(sessions)
        with pytest.raises(ConsentFailure, match="rejected") as inactive:
            await service.grant(
                user_id=user.id,
                idempotency_key="grant-key",
                request_id="inactive-grant-request",
            )
        assert inactive.value.code == "active_user_required"

        async with sessions() as session:
            persisted = await session.get(User, user.id, with_for_update=True)
            assert persisted is not None
            persisted.status = "active"
            await session.commit()

        first, concurrent = await gather(
            service.grant(
                user_id=user.id,
                idempotency_key="grant-key",
                request_id="grant-request",
            ),
            service.grant(
                user_id=user.id,
                idempotency_key="other-grant-key",
                request_id="concurrent-grant-request",
            ),
        )
        replay = await service.grant(
            user_id=user.id,
            idempotency_key="grant-key",
            request_id="grant-replay-request",
        )
        assert first.grant_id == concurrent.grant_id == replay.grant_id
        assert sum(result.created for result in (first, concurrent)) == 1
        assert not replay.created
        state = await service.current_state(user_id=user.id)
        assert state.status == "granted"
        assert state.grant_id == first.grant_id

        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(ConsentRecord)) == 1
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.action == "purpose_consent_granted")
                )
                == 1
            )
            claims = list((await session.scalars(select(IdempotencyRecord))).all())
            assert len(claims) == 2
            assert all("grant-key" not in claim.key_hash for claim in claims)


@pytest.mark.asyncio
async def test_grant_idempotency_rejects_requirement_change() -> None:
    async with _database() as sessions:
        user = await _add_user(sessions)
        service = _service(sessions)
        await service.grant(
            user_id=user.id,
            idempotency_key="stable-key",
            request_id="first-requirement",
        )
        changed = ConsentRequirement(
            consent_type=REQUIREMENT.consent_type,
            purpose_code=REQUIREMENT.purpose_code,
            purpose_version="purpose-v2",
            policy_code=REQUIREMENT.policy_code,
            policy_version=REQUIREMENT.policy_version,
            policy_digest="b" * 64,
            operations=REQUIREMENT.operations,
        )
        with pytest.raises(ConsentFailure) as conflict:
            await _service(sessions, requirement=changed).grant(
                user_id=user.id,
                idempotency_key="stable-key",
                request_id="changed-requirement",
            )
        assert conflict.value.code == "idempotency_conflict"


@pytest.mark.asyncio
async def test_current_state_reports_expired_and_version_mismatch_as_missing() -> None:
    async with _database() as sessions:
        user = await _add_user(sessions)
        service = _service(sessions)
        expired = ConsentRecord(
            id=new_id(),
            user_id=user.id,
            consent_type=REQUIREMENT.consent_type,
            purpose=REQUIREMENT.purpose_code,
            purpose_version=REQUIREMENT.purpose_version,
            scope=REQUIREMENT.scope,
            policy_code=REQUIREMENT.policy_code,
            policy_version=REQUIREMENT.policy_version,
            policy_digest=REQUIREMENT.policy_digest,
            action="grant",
            granted_at=NOW - timedelta(days=2),
            expires_at=NOW - timedelta(days=1),
            source="integration_fixture",
            request_id="expired-grant",
            created_at=NOW - timedelta(days=2),
        )
        async with sessions() as session:
            session.add(expired)
            await session.commit()
        state = await service.current_state(user_id=user.id)
        assert state.status == "missing"
        assert state.missing_reason == "expired"

        async with sessions() as session:
            await session.execute(text("TRUNCATE TABLE consent_records CASCADE"))
            session.add(
                ConsentRecord(
                    id=new_id(),
                    user_id=user.id,
                    consent_type=REQUIREMENT.consent_type,
                    purpose=REQUIREMENT.purpose_code,
                    purpose_version="purpose-v0",
                    scope=REQUIREMENT.scope,
                    policy_code=REQUIREMENT.policy_code,
                    policy_version="privacy-v0",
                    policy_digest="c" * 64,
                    action="grant",
                    granted_at=NOW,
                    source="integration_fixture",
                    request_id="old-version-grant",
                    created_at=NOW,
                )
            )
            await session.commit()
        state = await service.current_state(user_id=user.id)
        assert state.status == "missing"
        assert state.missing_reason == "version_mismatch"


@pytest.mark.asyncio
async def test_withdrawal_is_concurrent_idempotent_and_tombstones_pending_intents() -> None:
    async with _database() as sessions:
        user = await _add_user(sessions)
        service = _service(sessions)
        grant = await service.grant(
            user_id=user.id,
            idempotency_key="grant-for-withdrawal",
            request_id="grant-for-withdrawal-request",
        )
        intents = (
            UploadIntent(
                id=new_id(),
                owner_user_id=user.id,
                consent_record_id=grant.grant_id,
                object_key=f"quarantine/v1/{'1' * 64}",
                declared_mime_type="image/png",
                declared_byte_size=128,
                declared_sha256="2" * 64,
                status="awaiting_upload",
                grant_expires_at=NOW + timedelta(minutes=5),
                created_at=NOW,
                updated_at=NOW,
            ),
            UploadIntent(
                id=new_id(),
                owner_user_id=user.id,
                consent_record_id=grant.grant_id,
                object_key=f"quarantine/v1/{'3' * 64}",
                declared_mime_type="image/png",
                declared_byte_size=128,
                declared_sha256="4" * 64,
                status="uploaded_unverified",
                grant_expires_at=NOW + timedelta(minutes=5),
                uploaded_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            ),
        )
        async with sessions() as session:
            session.add_all(intents)
            await session.commit()

        first, second = await gather(
            service.withdraw(
                user_id=user.id,
                grant_id=grant.grant_id,
                idempotency_key="key-1",
                request_id="withdraw-request-1",
            ),
            service.withdraw(
                user_id=user.id,
                grant_id=grant.grant_id,
                idempotency_key="key-2",
                request_id="withdraw-request-2",
            ),
        )
        replay = await service.withdraw(
            user_id=user.id,
            grant_id=grant.grant_id,
            idempotency_key="key-1",
            request_id="withdraw-replay",
        )
        assert first.withdrawal_id == second.withdrawal_id == replay.withdrawal_id
        assert sum(result.created for result in (first, second)) == 1
        assert not replay.created
        assert (await service.current_state(user_id=user.id)).status == "withdrawn"

        async with sessions() as session:
            withdrawals = await session.scalar(
                select(func.count())
                .select_from(ConsentRecord)
                .where(ConsentRecord.action == "withdraw")
            )
            cancelled = list(
                (
                    await session.scalars(select(UploadIntent).order_by(UploadIntent.object_key))
                ).all()
            )
            events = list((await session.scalars(select(UploadIntentEvent))).all())
            assert withdrawals == 1
            assert [intent.status for intent in cancelled] == ["cancelled", "cancelled"]
            assert all(intent.cancelled_at == NOW for intent in cancelled)
            assert len(events) == 2
            assert all(event.metadata_json == {"reason": "consent_withdrawn"} for event in events)


@pytest.mark.asyncio
async def test_withdrawal_is_owner_bound_but_does_not_require_active_status() -> None:
    async with _database() as sessions:
        owner = await _add_user(sessions, seed="5")
        other = await _add_user(sessions, seed="6")
        service = _service(sessions)
        grant = await service.grant(
            user_id=owner.id,
            idempotency_key="owner-grant",
            request_id="owner-grant-request",
        )
        with pytest.raises(ConsentFailure):
            await service.withdraw(
                user_id=other.id,
                grant_id=grant.grant_id,
                idempotency_key="cross-user-withdraw",
                request_id="cross-user-request",
            )

        async with sessions() as session:
            persisted = await session.get(User, owner.id, with_for_update=True)
            assert persisted is not None
            persisted.status = "pending"
            await session.commit()
        withdrawal = await service.withdraw(
            user_id=owner.id,
            grant_id=grant.grant_id,
            idempotency_key="owner-withdraw",
            request_id="owner-withdraw-request",
        )
        assert withdrawal.grant_id == grant.grant_id
