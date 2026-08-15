from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import mirror_api.dependencies as dependencies
from mirror_api.config import Settings
from mirror_api.main import app


def test_health_endpoints(client: TestClient) -> None:
    live = client.get("/health/live")
    ready = client.get("/health/ready")
    assert live.status_code == 200
    assert live.json() == {
        "status": "live",
        "service": "mirror-api",
        "version": "0.1.0",
        "dependencies": {"database": "not_checked", "redis": "not_checked"},
    }
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_version_is_explicit(client: TestClient) -> None:
    response = client.get("/version")
    assert response.json() == {"service": "mirror-api", "version": "0.1.0", "api_version": "v1"}


def test_request_id_is_preserved_when_safe(client: TestClient) -> None:
    request_id = "request-test-1234"
    response = client.get("/health/live", headers={"X-Request-ID": request_id})
    assert response.headers["X-Request-ID"] == request_id


def test_cors_allows_delete_for_current_session_logout(client: TestClient) -> None:
    response = client.options(
        "/api/v1/auth/sessions/current",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_cors_allows_private_upload_put_and_integrity_headers(client: TestClient) -> None:
    response = client.options(
        "/_local/private-upload/opaque-fixture",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": (
                "content-type,x-content-sha256,x-mirror-upload-authorization"
            ),
        },
    )
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "x-content-sha256" in allowed
    assert "x-mirror-upload-authorization" in allowed


def test_protected_boundary_rejects_unauthorized_access(client: TestClient) -> None:
    response = client.post(
        "/api/v1/assets/upload-intents",
        headers={"Idempotency-Key": "upload-test-0001"},
        json={
            "content_type": "image/png",
            "byte_size": 1,
            "sha256": "a" * 64,
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_failed"


def test_idempotency_key_is_required(client: TestClient) -> None:
    response = client.post("/api/v1/auth/sms-challenges", json={})
    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_failed"


def test_framework_errors_use_stable_envelope(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "http_error"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_committed_openapi_matches_application() -> None:
    contract = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "openapi.json"
    assert json.loads(contract.read_text(encoding="utf-8")) == app.openapi()


def test_openapi_contains_inactive_self_conditioned_domain_contracts() -> None:
    schema = app.openapi()
    models = schema["components"]["schemas"]
    assert {
        "SelfStateContract",
        "DesiredDeltaDimensionContract",
        "DesiredDeltaProfileContract",
        "QuestionnaireRunContextContract",
    } <= set(models)
    assert all("race" not in json.dumps(model).lower() for model in models.values())


def test_ready_openapi_has_no_public_settings_request_body() -> None:
    schema = app.openapi()
    ready_operation = schema["paths"]["/health/ready"]["get"]

    assert "requestBody" not in ready_operation
    assert "Settings" not in schema["components"]["schemas"]


@pytest.mark.asyncio
async def test_dependency_probe_accepts_explicit_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    async def available_redis(_: str) -> str:
        return "available"

    monkeypatch.setattr(dependencies, "_probe_database", lambda _: "available")
    monkeypatch.setattr(dependencies, "_probe_redis", available_redis)

    status = await dependencies.probe_dependencies(
        Settings(database_url="postgresql+psycopg://test", redis_url="redis://test")
    )

    assert status.ready
