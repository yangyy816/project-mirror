from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

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


def test_unimplemented_boundary_uses_error_envelope(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/sms-challenges",
        headers={"Idempotency-Key": "auth-test-0001"},
        json={"intent": "test"},
    )
    body = response.json()
    assert response.status_code == 501
    assert body["code"] == "capability_not_implemented"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["details"]["capability"] == "phone_authentication"


def test_protected_boundary_rejects_unauthorized_access(client: TestClient) -> None:
    response = client.post(
        "/api/v1/assets",
        headers={"Idempotency-Key": "upload-test-0001"},
        json={},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


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
