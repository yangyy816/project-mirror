from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import redis.asyncio as redis
from fastapi import Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mirror_api.auth import AuthFailure, AuthService, PolicyRequirement
from mirror_api.auth.types import AuthenticatedActor, SessionResult
from mirror_api.config import Settings, get_settings
from mirror_api.errors import APIError
from mirror_api.providers.base import AgeAssuranceProvider, SmsProvider
from mirror_api.providers.mock import MockAgeAssuranceProvider, MockSmsProvider
from mirror_api.providers.tencent import TencentAgeAssuranceCandidateProvider, TencentSmsProvider
from mirror_api.rate_limit import FakeRateLimiter, RateLimiter, RedisRateLimiter
from mirror_api.security import (
    generate_csrf_token,
    refresh_cookie_policy,
    validate_origin,
    verify_csrf_token,
)

CSRF_COOKIE_NAME = "mirror_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


@dataclass(frozen=True)
class AuthInfrastructure:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    service: AuthService
    rate_limiter: RateLimiter
    redis_client: Any | None


def create_auth_infrastructure(settings: Settings) -> AuthInfrastructure:
    """Create the application-owned adapters used by the HTTP authentication boundary."""
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sms_provider: SmsProvider = (
        MockSmsProvider() if settings.sms_provider == "mock" else TencentSmsProvider()
    )
    age_provider: AgeAssuranceProvider = (
        MockAgeAssuranceProvider()
        if settings.age_assurance_provider == "mock"
        else TencentAgeAssuranceCandidateProvider()
    )
    redis_client: Any | None = None
    limiter: RateLimiter
    if settings.rate_limiter_backend == "fake":
        limiter = FakeRateLimiter()
    else:
        redis_client = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
        limiter = RedisRateLimiter(redis_client)
    return AuthInfrastructure(
        engine=engine,
        sessions=sessions,
        rate_limiter=limiter,
        redis_client=redis_client,
        service=AuthService(
            session_factory=sessions,
            sms_provider=sms_provider,
            age_provider=age_provider,
            rate_limiter=limiter,
            hmac_keyring=settings.auth_hmac_keyring,
            hmac_active_kid=settings.auth_hmac_active_kid,
            jwt_keyring=settings.auth_jwt_keyring,
            jwt_active_kid=settings.auth_jwt_active_kid,
            jwt_issuer=settings.auth_jwt_issuer,
            jwt_audience=settings.auth_jwt_audience,
            required_policies=tuple(
                PolicyRequirement(
                    document_code=policy.document_code,
                    document_version=policy.document_version,
                    document_digest=policy.document_digest,
                )
                for policy in settings.auth_required_policies
            ),
            otp_ttl_seconds=settings.auth_otp_ttl_seconds,
            otp_attempt_limit=settings.auth_otp_attempt_limit,
            refresh_ttl_seconds=settings.auth_refresh_token_ttl_seconds,
            access_ttl_seconds=settings.auth_access_token_ttl_seconds,
            challenge_rate_window_seconds=settings.auth_rate_limit_window_seconds,
            challenge_phone_rate_limit=settings.auth_rate_limit_phone_limit,
            challenge_ip_rate_limit=settings.auth_rate_limit_ip_limit,
            challenge_device_rate_limit=settings.auth_rate_limit_device_limit,
            allow_new_registrations=(
                settings.app_env != "production" or settings.registration_enabled
            ),
        ),
    )


def get_auth_service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_infrastructure.service)


def _auth_failure(failure: AuthFailure) -> APIError:
    if failure.code == "idempotency_conflict":
        return APIError(
            status_code=status.HTTP_409_CONFLICT, code=failure.code, message="认证请求冲突。"
        )
    if failure.code == "authentication_throttled":
        return APIError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code=failure.code,
            message="认证请求过于频繁。",
        )
    return APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=failure.code,
        message="认证凭据无效或已失效。",
    )


async def get_current_actor(
    auth_service: AuthService = Depends(get_auth_service),
    authorization: str | None = Header(default=None),
) -> AuthenticatedActor:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _auth_failure(AuthFailure())
    try:
        return await auth_service.authenticate_access_token(access_token=token)
    except AuthFailure as exc:
        raise _auth_failure(exc) from exc


def _verify_csrf(
    request: Request, settings: Settings, *, require_refresh_cookie: bool
) -> str | None:
    try:
        validate_origin(request.headers.get("Origin"), settings.cors_origins)
    except ValueError as exc:
        raise _auth_failure(AuthFailure()) from exc
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(CSRF_HEADER_NAME)
    if csrf_cookie is None or not verify_csrf_token(csrf_header, csrf_cookie):
        raise _auth_failure(AuthFailure())
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if require_refresh_cookie and not refresh_token:
        raise _auth_failure(AuthFailure())
    return refresh_token


def require_refresh_request(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str:
    refresh_token = _verify_csrf(request, settings, require_refresh_cookie=True)
    assert refresh_token is not None
    return refresh_token


def require_logout_csrf(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _verify_csrf(request, settings, require_refresh_cookie=False)


def set_refresh_cookies(response: Response, result: SessionResult, settings: Settings) -> None:
    policy = refresh_cookie_policy(
        app_env=settings.app_env,
        name=settings.auth_refresh_cookie_name,
        ttl_seconds=settings.auth_refresh_token_ttl_seconds,
    )
    response.set_cookie(
        key=policy.name,
        value=result.refresh_token,
        max_age=policy.max_age_seconds,
        httponly=policy.httponly,
        secure=policy.secure,
        samesite=policy.samesite,
        path=policy.path,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        max_age=policy.max_age_seconds,
        httponly=False,
        secure=policy.secure,
        samesite=policy.samesite,
        path=policy.path,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    policy = refresh_cookie_policy(
        app_env=settings.app_env,
        name=settings.auth_refresh_cookie_name,
        ttl_seconds=settings.auth_refresh_token_ttl_seconds,
    )
    response.delete_cookie(
        key=policy.name,
        httponly=policy.httponly,
        secure=policy.secure,
        samesite=policy.samesite,
        path=policy.path,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        httponly=False,
        secure=policy.secure,
        samesite=policy.samesite,
        path=policy.path,
    )
