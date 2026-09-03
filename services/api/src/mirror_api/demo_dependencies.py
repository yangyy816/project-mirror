from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator
from typing import cast

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings, get_settings
from mirror_api.demo_models import DemoActor
from mirror_api.demo_session_service import DemoSessionService
from mirror_api.errors import APIError

demo_bearer_auth = HTTPBearer(scheme_name="DemoBearerAuth", bearerFormat="opaque", auto_error=False)


def _authentication_failed() -> APIError:
    return APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="demo_authentication_failed",
        message="Demo 凭据无效或已失效。",
        details={"track": "DEMO_PROTOTYPE"},
    )


def _resolve_credential_key_id(token: str, keyring: dict[str, str]) -> str | None:
    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    matched_key_id: str | None = None
    for key_id, configured_digest in keyring.items():
        if hmac.compare_digest(token_digest, configured_digest):
            matched_key_id = key_id
    return matched_key_id


async def _demo_session(request: Request) -> AsyncIterator[AsyncSession]:
    infrastructure = request.app.state.auth_infrastructure
    sessions = cast(async_sessionmaker[AsyncSession], infrastructure.sessions)
    async with sessions() as session:
        yield session


def get_demo_credential_key_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(demo_bearer_auth),
    settings: Settings = Depends(get_settings),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_failed()
    credential_key_id = _resolve_credential_key_id(
        credentials.credentials, settings.demo_bearer_token_sha256_by_key_id
    )
    if credential_key_id is None:
        raise _authentication_failed()
    return credential_key_id


async def get_demo_actor(
    credential_key_id: str = Depends(get_demo_credential_key_id),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_demo_session),
) -> DemoActor:
    actor = (
        await session.execute(
            select(DemoActor).where(
                DemoActor.credential_key_id == credential_key_id,
                DemoActor.tombstoned_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if actor is None:
        raise _authentication_failed()
    if actor.actor_kind == "AUTOMATED_TEST" and settings.app_env not in {"test", "ci"}:
        raise _authentication_failed()
    if actor.actor_kind != "LOCAL_SINGLE_USER" and actor.actor_kind != "AUTOMATED_TEST":
        raise _authentication_failed()
    return actor


def get_demo_session_service(request: Request) -> DemoSessionService:
    infrastructure = request.app.state.auth_infrastructure
    sessions = cast(async_sessionmaker[AsyncSession], infrastructure.sessions)
    return DemoSessionService(session_factory=sessions)
