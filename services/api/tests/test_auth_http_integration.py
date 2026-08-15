from __future__ import annotations

import os
import uuid

import httpx
import pytest
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import mirror_api.auth.service as auth_service_module
from mirror_api.auth import AuthService, PolicyRequirement
from mirror_api.auth_dependencies import CSRF_COOKIE_NAME, get_auth_service
from mirror_api.config import RequiredPolicySetting, Settings, get_settings
from mirror_api.main import create_app
from mirror_api.models import InviteCode, new_id
from mirror_api.providers.mock import MockAgeAssuranceProvider
from mirror_api.rate_limit import RedisRateLimiter

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


@pytest.mark.asyncio
async def test_http_auth_onboarding_refresh_and_logout_vertical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    redis_url = os.getenv("TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL and TEST_REDIS_URL are required")

    origin = "http://127.0.0.1:3000"
    policy = PolicyRequirement("privacy", "v1", "d" * 64)
    settings = Settings(
        app_env="test",
        database_url=database_url,
        redis_url=redis_url,
        cors_origins=[origin],
        rate_limiter_backend="redis",
        auth_required_policies=[
            RequiredPolicySetting(
                document_code=policy.document_code,
                document_version=policy.document_version,
                document_digest=policy.document_digest,
            )
        ],
    )
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    redis_client = redis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
    redis_prefix = f"mirror:test-http-auth:{uuid.uuid4().hex}"
    sms = RecordingSmsProvider()
    credential = "synthetic-age-credential"
    age_provider = MockAgeAssuranceProvider(
        fixture_statuses={
            MockAgeAssuranceProvider.fixture_credential_key(credential): "verified",
        }
    )
    service = AuthService(
        session_factory=sessions,
        sms_provider=sms,
        age_provider=age_provider,
        rate_limiter=RedisRateLimiter(redis_client, prefix=redis_prefix),
        hmac_keyring=settings.auth_hmac_keyring,
        hmac_active_kid=settings.auth_hmac_active_kid,
        jwt_keyring=settings.auth_jwt_keyring,
        jwt_active_kid=settings.auth_jwt_active_kid,
        jwt_issuer=settings.auth_jwt_issuer,
        jwt_audience=settings.auth_jwt_audience,
        required_policies=(policy,),
        allow_new_registrations=True,
    )
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(
        auth_service_module,
        "normalize_china_phone",
        lambda _: "+86synthetic-http-fixture",
    )
    try:
        await redis_client.ping()
    except Exception as exc:
        await engine.dispose()
        await redis_client.aclose()
        pytest.skip(f"NOT VERIFIED LOCALLY: Redis is unavailable ({type(exc).__name__})")

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
                        code_hash=service._hmac("synthetic-invite", "invite"),
                    )
                )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=origin) as client:
            challenge_response = await client.post(
                "/api/v1/auth/sms-challenges",
                headers={
                    "Idempotency-Key": "http-challenge-key-0001",
                    "X-Device-ID": "synthetic-device",
                },
                json={"phone": "synthetic-phone-fixture", "invite_code": "synthetic-invite"},
            )
            assert challenge_response.status_code == 202
            assert set(challenge_response.json()) == {"challenge_id", "expires_at"}
            assert sms.codes and sms.codes[0] not in challenge_response.text

            session_response = await client.post(
                "/api/v1/auth/sessions",
                headers={"Idempotency-Key": "http-session-key-0001"},
                json={
                    "challenge_id": challenge_response.json()["challenge_id"],
                    "otp": sms.codes[0],
                },
            )
            assert session_response.status_code == 201
            pending_access = session_response.json()["access_token"]
            assert session_response.json()["scope"] == "pending"
            assert "refresh" not in session_response.text
            assert client.cookies.get(settings.auth_refresh_cookie_name) is not None
            csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
            assert csrf_token is not None

            pending_me = await client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {pending_access}"}
            )
            assert pending_me.status_code == 200
            assert pending_me.json()["status"] == "pending"

            age_response = await client.post(
                "/api/v1/users/me/age-assurances",
                headers={
                    "Authorization": f"Bearer {pending_access}",
                    "Idempotency-Key": "http-age-key-0001",
                },
                json={"credential": credential},
            )
            assert age_response.status_code == 201
            assert age_response.json()["activated"] is False
            assert credential not in age_response.text

            policy_response = await client.post(
                "/api/v1/users/me/policy-acceptances",
                headers={
                    "Authorization": f"Bearer {pending_access}",
                    "Idempotency-Key": "http-policy-key-0001",
                },
                json={
                    "document_code": policy.document_code,
                    "document_version": policy.document_version,
                    "document_digest": policy.document_digest,
                },
            )
            assert policy_response.status_code == 201
            assert policy_response.json() == {"activated": True}

            stale_pending = await client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {pending_access}"}
            )
            assert stale_pending.status_code == 401

            refresh_response = await client.post(
                "/api/v1/auth/token/refresh",
                headers={
                    "Idempotency-Key": "http-refresh-key-0001",
                    "Origin": origin,
                    "X-CSRF-Token": csrf_token,
                },
            )
            assert refresh_response.status_code == 200
            assert refresh_response.json()["scope"] == "active"
            assert "refresh" not in refresh_response.text
            active_access = refresh_response.json()["access_token"]
            rotated_csrf = client.cookies.get(CSRF_COOKIE_NAME)
            assert rotated_csrf is not None and rotated_csrf != csrf_token

            active_me = await client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {active_access}"}
            )
            assert active_me.status_code == 200
            assert active_me.json()["status"] == "active"

            logout_response = await client.delete(
                "/api/v1/auth/sessions/current",
                headers={
                    "Authorization": f"Bearer {active_access}",
                    "Origin": origin,
                    "X-CSRF-Token": rotated_csrf,
                },
            )
            assert logout_response.status_code == 204
            rejected_after_logout = await client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {active_access}"}
            )
            assert rejected_after_logout.status_code == 401

        async with sessions() as session:
            persisted = await session.execute(
                text(
                    "SELECT phone_hash, code_hash FROM phone_verification_challenges "
                    "UNION ALL SELECT provider_reference_hash, provider_reference_hash "
                    "FROM age_assurance_records"
                )
            )
            persisted_text = str(persisted.all())
            assert "synthetic-phone-fixture" not in persisted_text
            assert "synthetic-invite" not in persisted_text
            assert credential not in persisted_text
            assert sms.codes[0] not in persisted_text
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                    "invite_codes CASCADE"
                )
            )
        keys = await redis_client.keys(f"{redis_prefix}:*")
        if keys:
            await redis_client.delete(*keys)
        await engine.dispose()
        await redis_client.aclose()
        await app.state.auth_infrastructure.engine.dispose()
        app.dependency_overrides.clear()
        get_settings.cache_clear()
