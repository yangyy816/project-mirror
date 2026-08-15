from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.auth.service import AuthService
from mirror_api.models import User, UserSession, new_id
from mirror_api.providers.mock import MockAgeAssuranceProvider, MockSmsProvider
from mirror_api.rate_limit import FakeRateLimiter


def make_service() -> AuthService:
    return AuthService(
        session_factory=cast(async_sessionmaker[AsyncSession], object()),
        sms_provider=MockSmsProvider(),
        age_provider=MockAgeAssuranceProvider(),
        rate_limiter=FakeRateLimiter(),
        hmac_keyring={"test-v1": "h" * 64},
        hmac_active_kid="test-v1",
        jwt_keyring={"test-v1": "j" * 64},
        jwt_active_kid="test-v1",
        jwt_issuer="mirror-test",
        jwt_audience="mirror-web",
        now=lambda: datetime(2026, 8, 15, tzinfo=UTC),
    )


def test_pending_session_result_uses_pending_scope_and_opaque_refresh_token() -> None:
    service = make_service()
    user = User(id=new_id(), phone_hash="test-phone-hmac", status="pending")
    refresh_hash = f"fixture-{new_id()}"
    session = UserSession(
        id=new_id(),
        user_id=user.id,
        family_id=new_id(),
        token_id=new_id(),
        refresh_token_hash=refresh_hash,
        refresh_key_id="test-v1",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    result = service._session_result(user, session)

    assert result.scope == "pending"
    assert result.access_token
    assert result.refresh_token.startswith("rt1.test-v1.")


def test_active_session_result_uses_active_scope() -> None:
    service = make_service()
    user = User(id=new_id(), phone_hash="test-phone-hmac-active", status="active")
    refresh_hash = f"fixture-{new_id()}"
    session = UserSession(
        id=new_id(),
        user_id=user.id,
        family_id=new_id(),
        token_id=new_id(),
        refresh_token_hash=refresh_hash,
        refresh_key_id="test-v1",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    assert service._session_result(user, session).scope == "active"
