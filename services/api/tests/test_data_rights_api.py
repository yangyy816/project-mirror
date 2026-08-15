from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mirror_api.account_deletion.service import (
    AccountDeletionFailure,
    AccountDeletionResult,
)
from mirror_api.asset_access.service import AssetAccessDenied
from mirror_api.asset_access.types import AssetDownloadGrantResult, AssetView
from mirror_api.asset_access_dependencies import get_asset_access_service
from mirror_api.asset_deletion.service import AssetDeletionFailure, AssetDeletionResult
from mirror_api.asset_deletion_dependencies import get_asset_deletion_coordinator
from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import get_account_deletion_status_actor, get_current_actor
from mirror_api.data_export.service import (
    DataExportAccessDenied,
    DataExportFailure,
    DataExportResult,
)
from mirror_api.data_rights_dependencies import get_data_rights_coordinator
from mirror_api.main import app
from mirror_api.providers.base import PrivateDownloadGrant
from mirror_api.providers.local import LocalDownloadRedemption

NOW = datetime(2026, 8, 16, 22, tzinfo=UTC)
ACTOR = AuthenticatedActor(
    user_id="a" * 32,
    session_id="b" * 32,
    status="active",
    scope="active",
)
ASSET_ID = "c" * 32
EXPORT_ID = "d" * 32
EXPORT_JOB = "e" * 32
ASSET_DELETE_JOB = "f" * 32
ACCOUNT_DELETE_JOB = "1" * 32


async def _body(payload: bytes) -> AsyncIterator[bytes]:
    yield payload


def _grant(path: str) -> PrivateDownloadGrant:
    return PrivateDownloadGrant(
        method="GET",
        url=f"http://127.0.0.1:8000/{path}/ephemeral-grant",
        required_headers=MappingProxyType({"X-Mirror-Download-Authorization": "ephemeral-proof"}),
        expires_at=NOW + timedelta(minutes=5),
    )


class _Assets:
    def __init__(self) -> None:
        self.denied = False
        self.view = AssetView(
            id=ASSET_ID,
            asset_role="original",
            mime_type="image/jpeg",
            byte_size=128,
            width=64,
            height=64,
            created_at=NOW,
        )

    async def list_assets(self, *, user_id: str) -> tuple[AssetView, ...]:
        assert user_id == ACTOR.user_id
        return (self.view,)

    async def get_asset(self, *, user_id: str, asset_id: str) -> AssetView:
        assert user_id == ACTOR.user_id and asset_id == ASSET_ID
        if self.denied:
            raise AssetAccessDenied()
        return self.view

    async def create_download_grant(self, **_: str) -> AssetDownloadGrantResult:
        if self.denied:
            raise AssetAccessDenied()
        return AssetDownloadGrantResult(
            asset=self.view,
            grant=_grant("_local/private-download"),
        )


class _AssetDeletions:
    def __init__(self) -> None:
        self.denied = False
        self.arguments: dict[str, str] = {}

    async def create(self, **arguments: str) -> AssetDeletionResult:
        self.arguments = arguments
        if self.denied:
            raise AssetDeletionFailure()
        return AssetDeletionResult(
            request_id="2" * 32,
            job_id=ASSET_DELETE_JOB,
            status="requested",
            created=True,
        )


class _Exports:
    def __init__(self) -> None:
        self.denied = False
        self.result = DataExportResult(
            export_id=EXPORT_ID,
            job_id=EXPORT_JOB,
            status="ready",
            schema_version="mirror-data-export-v1",
            requested_at=NOW,
            ready_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )

    async def get_export(self, **_: str) -> DataExportResult:
        if self.denied:
            raise DataExportAccessDenied()
        return self.result

    async def create_download_grant(self, **_: str) -> PrivateDownloadGrant:
        if self.denied:
            raise DataExportAccessDenied()
        return _grant("_local/private-export-download")

    async def redeem_local_download(self, **_: str) -> LocalDownloadRedemption:
        if self.denied:
            raise DataExportAccessDenied()
        payload = b"synthetic-private-export"
        return LocalDownloadRedemption(
            request_reference=EXPORT_ID,
            content_type="application/zip",
            content_length=len(payload),
            sha256="3" * 64,
            body=_body(payload),
        )


class _Accounts:
    def __init__(self) -> None:
        self.denied = False
        self.result = AccountDeletionResult(
            request_id="4" * 32,
            job_id=ACCOUNT_DELETE_JOB,
            status="requested",
            requested_at=NOW,
        )

    async def current(self, **_: str) -> AccountDeletionResult:
        if self.denied:
            raise AccountDeletionFailure()
        return self.result


class _Rights:
    def __init__(self) -> None:
        self.exports = _Exports()
        self.account_deletions = _Accounts()

    async def create_export(self, **_: str) -> DataExportResult:
        if self.exports.denied:
            raise DataExportFailure()
        return self.exports.result

    async def create_account_deletion(self, **_: str) -> AccountDeletionResult:
        if self.account_deletions.denied:
            raise AccountDeletionFailure()
        return self.account_deletions.result


def _install(client: TestClient) -> tuple[_Assets, _AssetDeletions, _Rights]:
    assets = _Assets()
    deletions = _AssetDeletions()
    rights = _Rights()
    test_app = cast(FastAPI, client.app)
    test_app.dependency_overrides[get_current_actor] = lambda: ACTOR
    test_app.dependency_overrides[get_account_deletion_status_actor] = lambda: ACTOR
    test_app.dependency_overrides[get_asset_access_service] = lambda: assets
    test_app.dependency_overrides[get_asset_deletion_coordinator] = lambda: deletions
    test_app.dependency_overrides[get_data_rights_coordinator] = lambda: rights
    return assets, deletions, rights


def test_asset_rights_routes_expose_owner_safe_public_shapes(client: TestClient) -> None:
    _, deletions, _ = _install(client)
    auth = {"Authorization": "Bearer fixture"}
    listed = client.get("/api/v1/assets", headers=auth)
    assert listed.status_code == 200
    assert listed.json()["assets"] == [
        {
            "asset_id": ASSET_ID,
            "asset_role": "original",
            "mime_type": "image/jpeg",
            "byte_size": 128,
            "width": 64,
            "height": 64,
            "created_at": NOW.isoformat().replace("+00:00", "Z"),
        }
    ]
    detail = client.get(f"/api/v1/assets/{ASSET_ID}", headers=auth)
    assert detail.status_code == 200 and detail.json()["asset_id"] == ASSET_ID
    grant = client.post(
        f"/api/v1/assets/{ASSET_ID}/download-grants",
        headers={**auth, "Idempotency-Key": "asset-download-grant"},
    )
    assert grant.status_code == 201
    assert "private-download" in grant.json()["url"]
    assert "object_key" not in grant.text and "storage_key" not in grant.text
    deleted = client.delete(
        f"/api/v1/assets/{ASSET_ID}",
        headers={**auth, "Idempotency-Key": "asset-delete-once"},
    )
    assert deleted.status_code == 202
    assert deleted.json()["job_id"] == ASSET_DELETE_JOB
    assert deletions.arguments["user_id"] == ACTOR.user_id


def test_export_and_account_deletion_routes_expose_reference_only_state(
    client: TestClient,
) -> None:
    _, _, rights = _install(client)
    auth = {"Authorization": "Bearer fixture"}
    created = client.post(
        "/api/v1/users/me/data-exports",
        headers={**auth, "Idempotency-Key": "data-export-once"},
    )
    assert created.status_code == 202 and created.json()["job_id"] == EXPORT_JOB
    fetched = client.get(f"/api/v1/users/me/data-exports/{EXPORT_ID}", headers=auth)
    assert fetched.status_code == 200 and fetched.json()["status"] == "ready"
    grant = client.post(
        f"/api/v1/users/me/data-exports/{EXPORT_ID}/download-grants",
        headers={**auth, "Idempotency-Key": "export-download-grant"},
    )
    assert grant.status_code == 201
    assert "private-export-download" in grant.json()["url"]
    assert all(
        marker not in created.text + fetched.text + grant.text
        for marker in ("storage_key", "sha256", "phone", "provider", "evidence")
    )

    current = client.get("/api/v1/users/me/deletion-requests/current", headers=auth)
    assert current.status_code == 200
    deleted = client.post(
        "/api/v1/users/me/deletion-requests",
        headers={**auth, "Idempotency-Key": "account-delete-once"},
    )
    assert deleted.status_code == 202
    assert deleted.json()["job_id"] == ACCOUNT_DELETE_JOB
    assert "mirror_refresh=" in deleted.headers.get("set-cookie", "")

    local = client.get(
        "/_local/private-export-download/ephemeral-grant",
        headers={"X-Mirror-Download-Authorization": "ephemeral-proof"},
    )
    assert local.status_code == 200
    assert local.content == b"synthetic-private-export"
    assert local.headers["cache-control"] == "private, no-store"
    assert "attachment" in local.headers["content-disposition"]
    assert rights.exports.result.export_id == EXPORT_ID


def test_data_rights_failures_and_validation_are_stable_and_redacted(
    client: TestClient,
) -> None:
    assets, deletions, rights = _install(client)
    auth = {"Authorization": "Bearer fixture"}
    assets.denied = True
    missing = client.get(f"/api/v1/assets/{ASSET_ID}", headers=auth)
    assert missing.status_code == 404 and missing.json()["code"] == "asset_not_found"
    assert ASSET_ID not in missing.text
    deletions.denied = True
    refused = client.delete(
        f"/api/v1/assets/{ASSET_ID}",
        headers={**auth, "Idempotency-Key": "asset-delete-refused"},
    )
    assert refused.status_code == 404 and refused.json()["code"] == "asset_not_found"
    rights.exports.denied = True
    export = client.get(f"/api/v1/users/me/data-exports/{EXPORT_ID}", headers=auth)
    assert export.status_code == 404 and export.json()["code"] == "data_export_not_found"
    rights.account_deletions.denied = True
    account = client.get("/api/v1/users/me/deletion-requests/current", headers=auth)
    assert account.status_code == 404

    marker = "not-an-opaque-secret-path"
    invalid = client.get(f"/api/v1/assets/{marker}", headers=auth)
    assert invalid.status_code == 422 and marker not in invalid.text
    missing_key = client.post(
        f"/api/v1/assets/{ASSET_ID}/download-grants",
        headers=auth,
    )
    assert missing_key.status_code == 422


def test_data_rights_openapi_is_strict_and_hides_local_downloads() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    expected = {
        "/api/v1/assets": ("get",),
        "/api/v1/assets/{asset_id}": ("get", "delete"),
        "/api/v1/assets/{asset_id}/download-grants": ("post",),
        "/api/v1/users/me/data-exports": ("post",),
        "/api/v1/users/me/data-exports/{export_id}": ("get",),
        "/api/v1/users/me/data-exports/{export_id}/download-grants": ("post",),
        "/api/v1/users/me/deletion-requests": ("post",),
        "/api/v1/users/me/deletion-requests/current": ("get",),
    }
    for path, methods in expected.items():
        assert path in paths and set(methods) <= set(paths[path])
    for path in paths:
        assert "_local/private-download" not in path
        assert "_local/private-export-download" not in path
    creating = (
        ("/api/v1/assets/{asset_id}", "delete"),
        ("/api/v1/assets/{asset_id}/download-grants", "post"),
        ("/api/v1/users/me/data-exports", "post"),
        ("/api/v1/users/me/data-exports/{export_id}/download-grants", "post"),
        ("/api/v1/users/me/deletion-requests", "post"),
    )
    for path, method in creating:
        assert any(
            item["name"] == "Idempotency-Key" and item["required"]
            for item in paths[path][method]["parameters"]
        )
    for name in (
        "AssetResponse",
        "AssetListResponse",
        "PrivateDownloadGrantResponse",
        "AssetDeletionResponse",
        "DataExportResponse",
        "AccountDeletionResponse",
    ):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False
