from __future__ import annotations

import os
from asyncio import gather
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.auth.service import AuthService
from mirror_api.auth.types import AuthFailure, PolicyRequirement
from mirror_api.models import InviteCode, User, UserSession, new_id
from mirror_api.providers.base import AgeAssuranceProvider, AgeAssuranceResult
from mirror_api.providers.mock import MockAgeAssuranceProvider
from mirror_api.rate_limit import FakeRateLimiter

pytestmark = pytest.mark.integration


class RecordingSmsProvider:
    def __init__(self) -> None:
        self.codes: list[str] = []

    async def send_verification_code(
        self, *, destination_phone: str, verification_code: str, request_reference: str
    ) -> str:
        del destination_phone, request_reference
        self.codes.append(verification_code)
        return f"fixture-message-{len(self.codes)}"


class FailOnceSmsProvider(RecordingSmsProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def send_verification_code(
        self, *, destination_phone: str, verification_code: str, request_reference: str
    ) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("fixture sms provider outage")
        return await super().send_verification_code(
            destination_phone=destination_phone,
            verification_code=verification_code,
            request_reference=request_reference,
        )


class DisableInviteAfterSmsProvider(RecordingSmsProvider):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], invite_id: str) -> None:
        super().__init__()
        self._sessions = session_factory
        self._invite_id = invite_id
        self._disabled = False

    async def send_verification_code(
        self, *, destination_phone: str, verification_code: str, request_reference: str
    ) -> str:
        message_id = await super().send_verification_code(
            destination_phone=destination_phone,
            verification_code=verification_code,
            request_reference=request_reference,
        )
        if not self._disabled:
            async with self._sessions() as session:
                async with session.begin():
                    invite = await session.get(InviteCode, self._invite_id, with_for_update=True)
                    assert invite is not None
                    invite.disabled_at = datetime.now(UTC)
            self._disabled = True
        return message_id


class FailOnceAgeProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def verify_credential(
        self, *, credential: str, request_reference: str
    ) -> AgeAssuranceResult:
        del credential
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("fixture age provider outage")
        return AgeAssuranceResult(
            status="verified",
            provider_reference=f"fixture-age-{self.calls}",
            provider_version="fixture-v1",
            policy_version="fixture-policy-v1",
            expires_at=datetime(2026, 9, 15, tzinfo=UTC),
        )


def build_service(
    session_factory: async_sessionmaker[AsyncSession],
    sms: RecordingSmsProvider,
    *,
    age_provider: AgeAssuranceProvider | None = None,
    required_policies: tuple[PolicyRequirement, ...] = (),
    allow_new_registrations: bool = True,
    now: Callable[[], datetime] | None = None,
) -> AuthService:
    return AuthService(
        session_factory=session_factory,
        sms_provider=sms,
        age_provider=age_provider or MockAgeAssuranceProvider(),
        rate_limiter=FakeRateLimiter(),
        hmac_keyring={"fixture-v1": "h" * 64},
        hmac_active_kid="fixture-v1",
        jwt_keyring={"fixture-v1": "j" * 64},
        jwt_active_kid="fixture-v1",
        jwt_issuer="mirror-test",
        jwt_audience="mirror-web",
        required_policies=required_policies,
        allow_new_registrations=allow_new_registrations,
        now=now,
    )


@pytest.mark.asyncio
async def test_postgresql_finalize_failure_marks_claim_failed_and_allows_same_key_retry() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    phone = "".join(("1", "3", "8", "0", "0", "1", "3", "8", "0", "0", "4"))
    invite_id = new_id()
    sms = DisableInviteAfterSmsProvider(sessions, invite_id)
    service = build_service(sessions, sms)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        async with sessions() as session:
            async with session.begin():
                session.add(
                    InviteCode(
                        id=invite_id,
                        code_hash=service._hmac("finalize-invite", "invite"),
                    )
                )

        with pytest.raises(AuthFailure):
            await service.request_challenge(
                phone=phone,
                invite_code="finalize-invite",
                idempotency_key="finalize-retry-key",
                request_id="finalize-first-request",
                ip_key="finalize-ip",
                device_key="finalize-device",
            )
        async with sessions() as session:
            claim_state = await session.scalar(
                text(
                    "SELECT state FROM idempotency_records "
                    "WHERE scope = 'auth.challenge' AND key_hash = :key_hash"
                ),
                {"key_hash": service._idempotency_key("finalize-retry-key")},
            )
            challenge_count = await session.scalar(
                text("SELECT count(*) FROM phone_verification_challenges")
            )
            assert claim_state == "failed"
            assert challenge_count == 0
            invite = await session.get(InviteCode, invite_id, with_for_update=True)
            assert invite is not None
            invite.disabled_at = None
            await session.commit()

        retried = await service.request_challenge(
            phone=phone,
            invite_code="finalize-invite",
            idempotency_key="finalize-retry-key",
            request_id="finalize-retry-request",
            ip_key="finalize-ip",
            device_key="finalize-device",
        )
        assert retried.challenge_id
        assert len(sms.codes) == 2
        async with sessions() as session:
            completed_claim = await session.scalar(
                text(
                    "SELECT state FROM idempotency_records "
                    "WHERE scope = 'auth.challenge' AND key_hash = :key_hash"
                ),
                {"key_hash": service._idempotency_key("finalize-retry-key")},
            )
            challenge_count = await session.scalar(
                text("SELECT count(*) FROM phone_verification_challenges")
            )
            assert completed_claim == "completed"
            assert challenge_count == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_challenge_acceptance_uses_decoys_without_sms_or_real_challenges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    monkeypatch.setattr(
        "mirror_api.auth.service.normalize_china_phone", lambda _: "+86synthetic-fixture"
    )
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sms = RecordingSmsProvider()
    service = build_service(sessions, sms, allow_new_registrations=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        decoy = await service.request_challenge(
            phone="synthetic-new-user",
            invite_code="unused",
            idempotency_key="disabled-registration-new",
            request_id="disabled-registration-new",
            ip_key="fixture-ip",
            device_key="fixture-device",
        )
        replayed_decoy = await service.request_challenge(
            phone="synthetic-new-user",
            invite_code="unused",
            idempotency_key="disabled-registration-new",
            request_id="disabled-registration-replay",
            ip_key="fixture-ip",
            device_key="fixture-device",
        )
        assert decoy == replayed_decoy
        assert sms.codes == []
        with pytest.raises(AuthFailure):
            await service.create_session(
                challenge_id=decoy.challenge_id,
                otp="000000",
                idempotency_key="decoy-session-key",
                request_id="decoy-session-request",
            )
        with pytest.raises(AuthFailure, match="idempotency_conflict"):
            await service.request_challenge(
                phone="synthetic-new-user",
                invite_code="different-unused-invite",
                idempotency_key="disabled-registration-new",
                request_id="disabled-registration-conflict",
                ip_key="fixture-ip",
                device_key="fixture-device",
            )
        enabled_service = build_service(sessions, sms, allow_new_registrations=True)
        missing_invite_decoy = await enabled_service.request_challenge(
            phone="synthetic-new-user-without-invite",
            invite_code=None,
            idempotency_key="missing-invite-decoy",
            request_id="missing-invite-decoy",
            ip_key="fixture-ip",
            device_key="fixture-device",
        )
        assert missing_invite_decoy.challenge_id != decoy.challenge_id
        assert sms.codes == []
        async with sessions() as session:
            async with session.begin():
                session.add(
                    User(
                        id=new_id(),
                        phone_hash=service._hmac("+86synthetic-fixture", "phone"),
                        status="pending",
                    )
                )
        challenge = await service.request_challenge(
            phone="synthetic-existing-user",
            invite_code=None,
            idempotency_key="disabled-registration-existing",
            request_id="disabled-registration-existing",
            ip_key="fixture-ip",
            device_key="fixture-device",
        )
        assert challenge.challenge_id
        assert len(sms.codes) == 1
        async with sessions() as session:
            decoy_record = await session.execute(
                text(
                    "SELECT response_status, response_reference, completed_at "
                    "FROM idempotency_records WHERE actor_key = :actor_key "
                    "AND scope = 'auth.challenge' AND key_hash = :key_hash"
                ),
                {
                    "actor_key": f"preauth:{service._hmac('+86synthetic-fixture', 'phone')}",
                    "key_hash": service._idempotency_key("disabled-registration-new"),
                },
            )
            status, reference, completed_at = decoy_record.one()
            assert status == 0
            assert reference == decoy.challenge_id
            assert completed_at is not None
            real_record = await session.execute(
                text(
                    "SELECT response_status, response_reference "
                    "FROM idempotency_records WHERE actor_key = :actor_key "
                    "AND scope = 'auth.challenge' AND key_hash = :key_hash"
                ),
                {
                    "actor_key": f"preauth:{service._hmac('+86synthetic-fixture', 'phone')}",
                    "key_hash": service._idempotency_key("disabled-registration-existing"),
                },
            )
            assert real_record.one() == (1, challenge.challenge_id)
            challenge_count = await session.scalar(
                text("SELECT count(*) FROM phone_verification_challenges")
            )
            assert challenge_count == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_challenge_session_refresh_replay_and_reuse_revoke() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sms = RecordingSmsProvider()
    service = build_service(sessions, sms)
    phone = "".join(("1", "3", "8", "0", "0", "1", "3", "8", "0", "0", "0"))
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        async with sessions() as session:
            async with session.begin():
                session.add(
                    InviteCode(
                        id=new_id(),
                        code_hash=service._hmac("fixture-invite", "invite"),
                    )
                )

        challenge = await service.request_challenge(
            phone=phone,
            invite_code="fixture-invite",
            idempotency_key="challenge-key",
            request_id="request-challenge",
            ip_key="fixture-ip",
            device_key="fixture-device",
        )
        replayed_challenge = await service.request_challenge(
            phone=phone,
            invite_code="fixture-invite",
            idempotency_key="challenge-key",
            request_id="request-challenge-replay",
            ip_key="fixture-ip",
            device_key="fixture-device",
        )
        assert replayed_challenge.challenge_id == challenge.challenge_id
        assert len(sms.codes) == 1

        created = await service.create_session(
            challenge_id=challenge.challenge_id,
            otp=sms.codes[0],
            idempotency_key="session-key",
            request_id="request-session",
        )
        assert created.scope == "pending"
        actor = await service.authenticate_access_token(access_token=created.access_token)
        assert actor.user_id == created.user_id
        assert actor.session_id == created.session_id
        assert actor.scope == "pending"
        replayed_session = await service.create_session(
            challenge_id=challenge.challenge_id,
            otp=sms.codes[0],
            idempotency_key="session-key",
            request_id="request-session-replay",
        )
        assert replayed_session.refresh_token == created.refresh_token

        refreshed = await service.refresh_session(
            refresh_token=created.refresh_token,
            idempotency_key="refresh-key",
            request_id="request-refresh",
        )
        assert refreshed.refresh_token != created.refresh_token
        refresh_replay = await service.refresh_session(
            refresh_token=created.refresh_token,
            idempotency_key="refresh-key",
            request_id="request-refresh-replay",
        )
        assert refresh_replay.refresh_token == refreshed.refresh_token
        with pytest.raises(AuthFailure):
            await service.create_session(
                challenge_id=challenge.challenge_id,
                otp=sms.codes[0],
                idempotency_key="session-key",
                request_id="request-session-after-refresh",
            )
        with pytest.raises(AuthFailure):
            await service.refresh_session(
                refresh_token=created.refresh_token,
                idempotency_key="refresh-reuse",
                request_id="request-refresh-reuse",
            )
        with pytest.raises(AuthFailure):
            await service.authenticate_access_token(access_token=created.access_token)
        with pytest.raises(AuthFailure):
            await service.authenticate_access_token(access_token=refreshed.access_token)
        with pytest.raises(AuthFailure):
            await service.refresh_session(
                refresh_token=created.refresh_token,
                idempotency_key="refresh-key",
                request_id="request-refresh-replay-after-revoke",
            )

        logout_challenge = await service.request_challenge(
            phone=phone,
            invite_code=None,
            idempotency_key="logout-challenge-key",
            request_id="request-logout-challenge",
            ip_key="fixture-ip",
            device_key="fixture-device",
        )
        logout_session = await service.create_session(
            challenge_id=logout_challenge.challenge_id,
            otp=sms.codes[-1],
            idempotency_key="logout-session-key",
            request_id="request-logout-session",
        )
        await service.logout_family(
            session_id=logout_session.session_id,
            request_id="request-logout",
        )
        async with sessions() as session:
            persisted_logout_session = await session.get(UserSession, logout_session.session_id)
            assert persisted_logout_session is not None
            live_in_logout_family = await session.scalar(
                text(
                    "SELECT count(*) FROM user_sessions "
                    "WHERE family_id = :family_id AND revoked_at IS NULL"
                ),
                {"family_id": persisted_logout_session.family_id},
            )
        assert live_in_logout_family == 0
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_age_policy_idempotency_and_single_activation_audit() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sms = RecordingSmsProvider()
    credential = "fixture-age-credential"
    requirement = PolicyRequirement("privacy", "v1", "d" * 64)
    age = MockAgeAssuranceProvider(
        fixture_statuses={
            MockAgeAssuranceProvider.fixture_credential_key(credential): "verified",
        }
    )
    service = build_service(sessions, sms, age_provider=age, required_policies=(requirement,))
    user_id = new_id()
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        async with sessions() as session:
            async with session.begin():
                session.add(User(id=user_id, phone_hash="fixture-user-hash", status="pending"))

        first_age = await service.record_age_assurance(
            user_id=user_id,
            credential=credential,
            idempotency_key="age-key",
            request_id="age-request",
        )
        replayed_age = await service.record_age_assurance(
            user_id=user_id,
            credential=credential,
            idempotency_key="age-key",
            request_id="age-replay-request",
        )
        assert first_age.record_id == replayed_age.record_id
        assert not first_age.activated
        with pytest.raises(AuthFailure):
            await service.record_age_assurance(
                user_id=user_id,
                credential="different-fixture-age-credential",
                idempotency_key="age-key",
                request_id="age-conflict-request",
            )

        activated = await service.accept_policy(
            user_id=user_id,
            requirement=requirement,
            source="fixture",
            idempotency_key="policy-key",
            request_id="policy-request",
        )
        replayed_policy = await service.accept_policy(
            user_id=user_id,
            requirement=requirement,
            source="fixture",
            idempotency_key="policy-key",
            request_id="policy-replay-request",
        )
        assert activated and replayed_policy
        with pytest.raises(AuthFailure):
            await service.accept_policy(
                user_id=user_id,
                requirement=requirement,
                source="different-fixture-source",
                idempotency_key="policy-key",
                request_id="policy-conflict-request",
            )
        async with sessions() as session:
            activation_count = await session.scalar(
                text(
                    "SELECT count(*) FROM audit_logs "
                    "WHERE action = 'user_activated' AND target_id = :user_id"
                ),
                {"user_id": user_id},
            )
        assert activation_count == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_invite_race_and_otp_failure_state_are_durable() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sms = RecordingSmsProvider()
    service = build_service(sessions, sms)
    first_phone = "".join(("1", "3", "8", "0", "0", "1", "3", "8", "0", "0", "1"))
    second_phone = "".join(("1", "3", "8", "0", "0", "1", "3", "8", "0", "0", "2"))
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        async with sessions() as session:
            async with session.begin():
                session.add(
                    InviteCode(
                        id=new_id(),
                        code_hash=service._hmac("race-invite", "invite"),
                        max_uses=1,
                    )
                )
        first_challenge = await service.request_challenge(
            phone=first_phone,
            invite_code="race-invite",
            idempotency_key="race-challenge-one",
            request_id="race-challenge-one",
            ip_key="race-ip-one",
            device_key="race-device-one",
        )
        second_challenge = await service.request_challenge(
            phone=second_phone,
            invite_code="race-invite",
            idempotency_key="race-challenge-two",
            request_id="race-challenge-two",
            ip_key="race-ip-two",
            device_key="race-device-two",
        )
        outcomes = await gather(
            service.create_session(
                challenge_id=first_challenge.challenge_id,
                otp=sms.codes[0],
                idempotency_key="race-session-one",
                request_id="race-session-one",
            ),
            service.create_session(
                challenge_id=second_challenge.challenge_id,
                otp=sms.codes[1],
                idempotency_key="race-session-two",
                request_id="race-session-two",
            ),
            return_exceptions=True,
        )
        assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
        assert sum(isinstance(outcome, AuthFailure) for outcome in outcomes) == 1

        winner_phone = first_phone if not isinstance(outcomes[0], Exception) else second_phone
        otp_challenge = await service.request_challenge(
            phone=winner_phone,
            invite_code=None,
            idempotency_key="attempt-challenge",
            request_id="attempt-challenge",
            ip_key="attempt-ip",
            device_key="attempt-device",
        )
        valid_otp = sms.codes[-1]
        invalid_otp = ("0" if valid_otp[0] != "0" else "1") + valid_otp[1:]
        for attempt in range(5):
            with pytest.raises(AuthFailure):
                await service.create_session(
                    challenge_id=otp_challenge.challenge_id,
                    otp=invalid_otp,
                    idempotency_key=f"wrong-otp-{attempt}",
                    request_id=f"wrong-otp-{attempt}",
                )
        with pytest.raises(AuthFailure):
            await service.create_session(
                challenge_id=otp_challenge.challenge_id,
                otp=valid_otp,
                idempotency_key="correct-after-limit",
                request_id="correct-after-limit",
            )
        async with sessions() as session:
            state = await session.execute(
                text(
                    "SELECT attempts, invalidated_at IS NOT NULL AS invalidated "
                    "FROM phone_verification_challenges WHERE id = :challenge_id"
                ),
                {"challenge_id": otp_challenge.challenge_id},
            )
            assert state.one() == (5, True)
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_provider_failure_retry_expiry_and_nonverified_age() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sms = FailOnceSmsProvider()
    clock = {"now": datetime(2026, 8, 15, tzinfo=UTC)}
    service = build_service(sessions, sms, now=lambda: clock["now"])
    phone = "".join(("1", "3", "8", "0", "0", "1", "3", "8", "0", "0", "3"))
    user_id = new_id()
    failure_user_id = new_id()
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        async with sessions() as session:
            async with session.begin():
                session.add(
                    InviteCode(id=new_id(), code_hash=service._hmac("retry-invite", "invite"))
                )
                session.add(User(id=user_id, phone_hash="nonverified-user", status="pending"))
                session.add(User(id=failure_user_id, phone_hash="failure-user", status="pending"))
        with pytest.raises(AuthFailure):
            await service.request_challenge(
                phone=phone,
                invite_code="retry-invite",
                idempotency_key="retry-challenge-key",
                request_id="retry-challenge-request",
                ip_key="retry-ip",
                device_key="retry-device",
            )
        async with sessions() as session:
            failed_state = await session.scalar(
                text("SELECT state FROM idempotency_records WHERE scope = 'auth.challenge'")
            )
            challenge_count = await session.scalar(
                text("SELECT count(*) FROM phone_verification_challenges")
            )
            assert failed_state == "failed"
            assert challenge_count == 0
        challenge = await service.request_challenge(
            phone=phone,
            invite_code="retry-invite",
            idempotency_key="retry-challenge-key",
            request_id="retry-challenge-retry",
            ip_key="retry-ip",
            device_key="retry-device",
        )
        assert challenge.challenge_id
        clock["now"] += timedelta(minutes=6)
        with pytest.raises(AuthFailure):
            await service.create_session(
                challenge_id=challenge.challenge_id,
                otp=sms.codes[-1],
                idempotency_key="expired-session-key",
                request_id="expired-session-request",
            )

        age_credential = "not-verified-fixture"
        indeterminate_credential = "indeterminate-fixture"
        age = MockAgeAssuranceProvider(
            fixture_statuses={
                MockAgeAssuranceProvider.fixture_credential_key(age_credential): "not_verified",
                MockAgeAssuranceProvider.fixture_credential_key(
                    indeterminate_credential
                ): "indeterminate",
            }
        )
        age_service = build_service(sessions, RecordingSmsProvider(), age_provider=age)
        not_verified = await age_service.record_age_assurance(
            user_id=user_id,
            credential=age_credential,
            idempotency_key="not-verified-key",
            request_id="not-verified-request",
        )
        indeterminate = await age_service.record_age_assurance(
            user_id=user_id,
            credential=indeterminate_credential,
            idempotency_key="indeterminate-key",
            request_id="indeterminate-request",
        )
        assert not not_verified.activated and not indeterminate.activated
        failed_age = FailOnceAgeProvider()
        failed_age_service = build_service(
            sessions, RecordingSmsProvider(), age_provider=failed_age
        )
        with pytest.raises(AuthFailure):
            await failed_age_service.record_age_assurance(
                user_id=failure_user_id,
                credential="retry-age-credential",
                idempotency_key="retry-age-key",
                request_id="retry-age-request",
            )
        async with sessions() as session:
            failed_age_state = await session.scalar(
                text(
                    "SELECT state FROM idempotency_records "
                    "WHERE scope = 'auth.age_assurance' AND key_hash = :key_hash"
                ),
                {"key_hash": failed_age_service._idempotency_key("retry-age-key")},
            )
            age_evidence_count = await session.scalar(
                text("SELECT count(*) FROM age_assurance_records WHERE user_id = :user_id"),
                {"user_id": failure_user_id},
            )
            assert failed_age_state == "failed"
            assert age_evidence_count == 0
        retried_age = await failed_age_service.record_age_assurance(
            user_id=failure_user_id,
            credential="retry-age-credential",
            idempotency_key="retry-age-key",
            request_id="retry-age-retry-request",
        )
        assert retried_age.result == "verified"
        async with sessions() as session:
            persisted_user = await session.get(User, user_id)
            assert persisted_user is not None and persisted_user.status == "pending"
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        await engine.dispose()
