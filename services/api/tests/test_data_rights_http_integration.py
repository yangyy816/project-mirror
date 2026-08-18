from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from mirror_api.asset_deletion.coordinator import AssetDeletionCoordinator
from mirror_api.asset_deletion.dispatcher import RecoverableAssetDeletionDispatcher
from mirror_api.asset_deletion.service import AssetDeletionService
from mirror_api.asset_deletion_dependencies import AssetDeletionInfrastructure
from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import get_account_deletion_status_actor, get_current_actor
from mirror_api.config import get_settings
from mirror_api.data_rights.coordinator import DataRightsCoordinator
from mirror_api.data_rights.dispatcher import RecoverableDataRightsDispatcher
from mirror_api.data_rights_dependencies import DataRightsInfrastructure
from mirror_api.models import Asset, User, UserSession, new_id
from mirror_api.providers.local import LocalObjectStorageProvider, sanitized_object_key_for_job
from mirror_api.security import issue_access_token

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 16, 23, 30, tzinfo=UTC)


async def _body(payload: bytes) -> AsyncIterator[bytes]:
    yield payload


async def _asset(
    storage: LocalObjectStorageProvider, *, owner_user_id: str, payload: bytes
) -> Asset:
    key = sanitized_object_key_for_job(new_id())
    await storage.create_sanitized_object_if_absent(
        object_key=key,
        content_type="image/jpeg",
        content_length=len(payload),
        checksum_sha256=sha256(payload).hexdigest(),
        body=_body(payload),
    )
    return Asset(
        id=new_id(),
        owner_user_id=owner_user_id,
        asset_role="original",
        storage_key=key,
        mime_type="image/jpeg",
        byte_size=len(payload),
        width=64,
        height=64,
        sha256=sha256(payload).hexdigest(),
        synthetic=True,
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_data_rights_http_vertical_flow_is_owner_bound_and_idempotent(
    client: TestClient,
) -> None:
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    test_app = cast(FastAPI, client.app)
    infrastructure = test_app.state.auth_infrastructure
    configured_rights = cast(DataRightsInfrastructure, test_app.state.data_rights_infrastructure)
    rights = DataRightsInfrastructure(
        coordinator=DataRightsCoordinator(
            exports=configured_rights.coordinator.exports,
            account_deletions=configured_rights.coordinator.account_deletions,
            dispatcher=RecoverableDataRightsDispatcher(),
        )
    )
    # This test drives both jobs synchronously. Suppress duplicate Celery deliveries so
    # its TRUNCATE-based isolation cannot race a worker transaction after assertions.
    test_app.state.data_rights_infrastructure = rights
    storage = cast(LocalObjectStorageProvider, test_app.state.object_storage_provider)
    settings = get_settings()
    test_app.state.asset_deletion_infrastructure = AssetDeletionInfrastructure(
        coordinator=AssetDeletionCoordinator(
            service=AssetDeletionService(
                session_factory=infrastructure.sessions,
                storage=storage,
                hmac_keyring=dict(settings.auth_hmac_keyring),
                hmac_active_kid=settings.auth_hmac_active_kid,
            ),
            dispatcher=RecoverableAssetDeletionDispatcher(),
        )
    )
    session_expires_at = datetime.now(UTC) + timedelta(days=1)

    user = User(id=new_id(), phone_hash="a" * 128, status="active", created_at=NOW)
    outsider = User(id=new_id(), phone_hash="b" * 128, status="active", created_at=NOW)
    session_row = UserSession(
        id=new_id(),
        user_id=user.id,
        family_id=new_id(),
        token_id=sha256(b"synthetic-rights-session").hexdigest(),
        refresh_token_hash="c" * 128,
        refresh_key_id="fixture-v1",
        expires_at=session_expires_at,
        created_at=NOW,
    )
    export_asset = await _asset(
        storage,
        owner_user_id=user.id,
        payload=b"synthetic-export-http-asset",
    )
    deletion_asset = await _asset(
        storage,
        owner_user_id=user.id,
        payload=b"synthetic-delete-http-asset",
    )
    async with infrastructure.sessions() as session:
        await session.execute(text("TRUNCATE TABLE users CASCADE"))
        session.add_all([user, outsider])
        await session.commit()
        session.add_all([session_row, export_asset, deletion_asset])
        await session.commit()

    actor = [AuthenticatedActor(user.id, session_row.id, "active", "active")]
    test_app.dependency_overrides[get_current_actor] = lambda: actor[0]
    test_app.dependency_overrides[get_account_deletion_status_actor] = lambda: actor[0]
    auth = {"Authorization": "Bearer synthetic-access"}
    deletion_status_token = issue_access_token(
        subject=user.id,
        session_id=session_row.id,
        scope="active",
        keyring=settings.auth_jwt_keyring,
        active_key_id=settings.auth_jwt_active_kid,
        issuer=settings.auth_jwt_issuer,
        audience=settings.auth_jwt_audience,
    )

    listed = client.get("/api/v1/assets", headers=auth)
    assert listed.status_code == 200 and len(listed.json()["assets"]) == 2
    actor[0] = AuthenticatedActor(outsider.id, new_id(), "active", "active")
    hidden = client.get(f"/api/v1/assets/{export_asset.id}", headers=auth)
    assert hidden.status_code == 404 and export_asset.id not in hidden.text
    actor[0] = AuthenticatedActor(user.id, session_row.id, "active", "active")

    requested = client.post(
        "/api/v1/users/me/data-exports",
        headers={**auth, "Idempotency-Key": "vertical-export-once"},
    )
    replay = client.post(
        "/api/v1/users/me/data-exports",
        headers={**auth, "Idempotency-Key": "vertical-export-once"},
    )
    assert requested.status_code == 202
    assert replay.status_code == 202
    assert requested.json()["export_id"] == replay.json()["export_id"]
    ready = await rights.coordinator.exports.process(job_id=requested.json()["job_id"])
    assert ready is not None and ready.status == "ready"
    fetched = client.get(
        f"/api/v1/users/me/data-exports/{requested.json()['export_id']}",
        headers=auth,
    )
    assert fetched.status_code == 200 and fetched.json()["status"] == "ready"
    grant = client.post(
        f"/api/v1/users/me/data-exports/{requested.json()['export_id']}/download-grants",
        headers={**auth, "Idempotency-Key": "vertical-export-download"},
    )
    assert grant.status_code == 201
    local = client.get(
        grant.json()["url"].removeprefix("http://127.0.0.1:8000"),
        headers=grant.json()["required_headers"],
    )
    assert local.status_code == 200 and local.content.startswith(b"PK")

    deleted = client.delete(
        f"/api/v1/assets/{deletion_asset.id}",
        headers={**auth, "Idempotency-Key": "vertical-asset-delete"},
    )
    assert deleted.status_code == 202
    revoked = client.get(f"/api/v1/assets/{deletion_asset.id}", headers=auth)
    assert revoked.status_code == 404

    account = client.post(
        "/api/v1/users/me/deletion-requests",
        headers={**auth, "Idempotency-Key": "vertical-account-delete"},
    )
    assert account.status_code == 202
    completed = await rights.coordinator.account_deletions.process(job_id=account.json()["job_id"])
    assert completed is not None and completed.status == "completed"
    test_app.dependency_overrides.pop(get_current_actor)
    test_app.dependency_overrides.pop(get_account_deletion_status_actor)
    status_auth = {"Authorization": f"Bearer {deletion_status_token}"}
    current = client.get("/api/v1/users/me/deletion-requests/current", headers=status_auth)
    assert current.status_code == 200 and current.json()["status"] == "completed"
    ordinary = client.get("/api/v1/assets", headers=status_auth)
    assert ordinary.status_code == 401
    async with infrastructure.sessions() as session:
        deleted_user = await session.get(User, user.id)
        revoked_session = await session.get(UserSession, session_row.id)
        assert deleted_user is not None and deleted_user.status == "deleted"
        assert revoked_session is not None and revoked_session.revoked_at is not None
        await session.execute(text("TRUNCATE TABLE users CASCADE"))
        await session.commit()
