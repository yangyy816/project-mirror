from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import get_current_actor
from mirror_api.main import app
from mirror_api.providers.base import PrivateUploadGrant
from mirror_api.upload_control import (
    ConsentGrantResult,
    ConsentRequirement,
    ConsentState,
    ConsentWithdrawalResult,
    UploadCancellationResult,
    UploadCompletionResult,
    UploadDeclaration,
    UploadIntentCreationResult,
    UploadIntentFailure,
    UploadIntentView,
)
from mirror_api.upload_control_dependencies import (
    get_consent_service,
    get_upload_intent_service,
)

NOW = datetime(2026, 8, 16, 10, tzinfo=UTC)
ACTOR = AuthenticatedActor(
    user_id="a" * 32,
    session_id="b" * 32,
    status="active",
    scope="active",
)
REQUIREMENT = ConsentRequirement(
    consent_type="facial_data_processing",
    purpose_code="personal_aesthetic_baseline",
    purpose_version="purpose-v1",
    policy_code="facial-data-policy",
    policy_version="privacy-v1",
    policy_digest="c" * 64,
    operations=("private_upload", "security_validation"),
)


class _ConsentService:
    async def current_state(self, *, user_id: str) -> ConsentState:
        assert user_id == ACTOR.user_id
        return ConsentState(status="missing", requirement=REQUIREMENT, missing_reason="absent")

    async def grant(self, **_: str) -> ConsentGrantResult:
        return ConsentGrantResult("c" * 32, NOW, None, True)

    async def withdraw(self, **_: str) -> ConsentWithdrawalResult:
        return ConsentWithdrawalResult("d" * 32, "c" * 32, NOW, True)


class _UploadService:
    def __init__(self) -> None:
        self.fail_get = False
        self.view = UploadIntentView(
            intent_id="e" * 32,
            status="awaiting_upload",
            declaration=UploadDeclaration("image/png", 128, "f" * 64),
            grant_expires_at=NOW + timedelta(minutes=5),
            uploaded_at=None,
            cancelled_at=None,
            expired_at=None,
        )

    async def create(self, **_: object) -> UploadIntentCreationResult:
        return UploadIntentCreationResult(
            intent=self.view,
            grant=PrivateUploadGrant(
                method="PUT",
                url="http://127.0.0.1:8000/_local/private-upload/opaque-fixture",
                required_headers=MappingProxyType(
                    {
                        "Content-Type": "image/png",
                        "Content-Length": "128",
                        "X-Content-SHA256": "f" * 64,
                        "X-Mirror-Upload-Authorization": "ephemeral-fixture",
                    }
                ),
                expires_at=self.view.grant_expires_at,
            ),
            created=True,
        )

    async def get(self, **_: str) -> UploadIntentView:
        if self.fail_get:
            raise UploadIntentFailure()
        return self.view

    async def complete(self, **_: str) -> UploadCompletionResult:
        completed = UploadIntentView(
            intent_id=self.view.intent_id,
            status="uploaded_unverified",
            declaration=self.view.declaration,
            grant_expires_at=self.view.grant_expires_at,
            uploaded_at=NOW,
            cancelled_at=None,
            expired_at=None,
        )
        return UploadCompletionResult(completed, True)

    async def cancel(self, **_: str) -> UploadCancellationResult:
        return UploadCancellationResult(self.view.intent_id, True, "deleted")


def _install(client: TestClient) -> _UploadService:
    upload = _UploadService()
    test_app = cast(FastAPI, client.app)
    test_app.dependency_overrides[get_current_actor] = lambda: ACTOR
    test_app.dependency_overrides[get_consent_service] = lambda: _ConsentService()
    test_app.dependency_overrides[get_upload_intent_service] = lambda: upload
    return upload


def test_consent_and_upload_control_routes_expose_only_public_shapes(
    client: TestClient,
) -> None:
    _install(client)
    auth = {"Authorization": "Bearer fixture-access", "Idempotency-Key": "fixture-key-0001"}
    state = client.get("/api/v1/users/me/consents", headers=auth)
    assert state.status_code == 200
    assert state.json()["status"] == "missing"
    assert state.json()["requirement"]["policy_digest"] == "c" * 64

    grant = client.post("/api/v1/users/me/consents", headers=auth)
    assert grant.status_code == 201
    assert grant.json()["grant_id"] == "c" * 32
    withdrawal = client.post(
        f"/api/v1/users/me/consents/{'c' * 32}/withdrawals",
        headers=auth,
    )
    assert withdrawal.status_code == 201
    assert withdrawal.json()["withdrawal_id"] == "d" * 32

    created = client.post(
        "/api/v1/assets/upload-intents",
        headers=auth,
        json={"content_type": "image/png", "byte_size": 128, "sha256": "f" * 64},
    )
    assert created.status_code == 201
    assert created.json()["upload"]["method"] == "PUT"
    assert "private-upload" in created.json()["upload"]["url"]
    assert "object_key" not in created.text

    fetched = client.get(
        f"/api/v1/assets/upload-intents/{'e' * 32}",
        headers={"Authorization": "Bearer fixture-access"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "awaiting_upload"
    assert "url" not in fetched.text and "object_key" not in fetched.text

    completed = client.post(
        f"/api/v1/assets/upload-intents/{'e' * 32}/complete",
        headers=auth,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "uploaded_unverified"
    cancelled = client.delete(
        f"/api/v1/assets/upload-intents/{'e' * 32}",
        headers={"Authorization": "Bearer fixture-access"},
    )
    assert cancelled.status_code == 204 and not cancelled.content


def test_upload_validation_and_owner_safe_failure_do_not_leak_inputs(client: TestClient) -> None:
    upload = _install(client)
    marker = "do-not-echo-client-path"
    invalid = client.post(
        "/api/v1/assets/upload-intents",
        headers={
            "Authorization": "Bearer fixture-access",
            "Idempotency-Key": "fixture-key-0002",
        },
        json={"content_type": "text/html", "byte_size": 1, "sha256": marker},
    )
    assert invalid.status_code == 422
    assert marker not in invalid.text

    upload.fail_get = True
    foreign_id = "9" * 32
    missing = client.get(
        f"/api/v1/assets/upload-intents/{foreign_id}",
        headers={"Authorization": "Bearer fixture-access"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "upload_intent_operation_rejected"
    assert foreign_id not in missing.text


def test_upload_control_openapi_has_all_endpoints_and_no_local_ingress() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    expected = {
        "/api/v1/users/me/consents": ("get", "post"),
        "/api/v1/users/me/consents/{grant_id}/withdrawals": ("post",),
        "/api/v1/assets/upload-intents": ("post",),
        "/api/v1/assets/upload-intents/{intent_id}": ("get", "delete"),
        "/api/v1/assets/upload-intents/{intent_id}/complete": ("post",),
    }
    for path, methods in expected.items():
        assert path in paths
        assert set(methods) <= set(paths[path])
    for path in paths:
        assert "_local/private-upload" not in path
    assert "/api/v1/assets" not in paths
    for path, methods in expected.items():
        for method in methods:
            if method == "post":
                operation = paths[path][method]
                assert any(
                    parameter["name"] == "Idempotency-Key"
                    and parameter["in"] == "header"
                    and parameter["required"]
                    for parameter in operation["parameters"]
                )
