from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import get_current_actor
from mirror_api.ingestion.types import IngestionFailure, IngestionJobResult, IngestionJobView
from mirror_api.ingestion_dependencies import get_ingestion_coordinator
from mirror_api.main import app

NOW = datetime(2026, 8, 16, 14, tzinfo=UTC)
ACTOR = AuthenticatedActor(
    user_id="a" * 32,
    session_id="b" * 32,
    status="active",
    scope="active",
)
INTENT_ID = "c" * 32
JOB_ID = "d" * 32
ASSET_ID = "e" * 32


class _Coordinator:
    def __init__(self) -> None:
        self.failure: str | None = None
        self.created_arguments: dict[str, str] = {}
        self.view = IngestionJobView(
            job_id=JOB_ID,
            status="pending",
            result_code=None,
            asset_id=None,
            finalized_at=None,
        )

    async def create(self, **arguments: str) -> IngestionJobResult:
        self.created_arguments = arguments
        if self.failure is not None:
            raise IngestionFailure(self.failure)
        return IngestionJobResult(job=self.view, created=True)

    async def get(self, *, user_id: str, job_id: str) -> IngestionJobView:
        assert user_id == ACTOR.user_id and job_id == JOB_ID
        if self.failure is not None:
            raise IngestionFailure(self.failure)
        return self.view


def _install(client: TestClient) -> _Coordinator:
    coordinator = _Coordinator()
    test_app = cast(FastAPI, client.app)
    test_app.dependency_overrides[get_current_actor] = lambda: ACTOR
    test_app.dependency_overrides[get_ingestion_coordinator] = lambda: coordinator
    return coordinator


def test_create_and_get_ingestion_job_expose_reference_only_shape(client: TestClient) -> None:
    coordinator = _install(client)
    created = client.post(
        f"/api/v1/assets/upload-intents/{INTENT_ID}/ingestion-jobs",
        headers={"Authorization": "Bearer fixture", "Idempotency-Key": "ingestion-key-1"},
    )
    assert created.status_code == 202
    assert created.json() == {
        "job_id": JOB_ID,
        "status": "pending",
        "result_code": None,
        "asset_id": None,
        "finalized_at": None,
    }
    assert coordinator.created_arguments["user_id"] == ACTOR.user_id
    assert coordinator.created_arguments["intent_id"] == INTENT_ID
    assert coordinator.created_arguments["idempotency_key"] == "ingestion-key-1"
    assert 8 <= len(coordinator.created_arguments["request_id"]) <= 128

    coordinator.view = IngestionJobView(
        job_id=JOB_ID,
        status="promoted",
        result_code="ingestion_promoted",
        asset_id=ASSET_ID,
        finalized_at=NOW,
    )
    fetched = client.get(f"/api/v1/jobs/{JOB_ID}", headers={"Authorization": "Bearer fixture"})
    assert fetched.status_code == 200
    assert fetched.json()["asset_id"] == ASSET_ID
    forbidden = ("object_key", "storage_key", "path", "bytes", "decoder", "provider")
    assert all(marker not in fetched.text for marker in forbidden)


def test_ingestion_failures_are_stable_and_owner_safe(client: TestClient) -> None:
    coordinator = _install(client)
    mapping = {
        "idempotency_conflict": 409,
        "upload_intent_not_ready": 409,
        "quarantine_retention_expired": 410,
        "authorization_revoked": 403,
        "ingestion_operation_rejected": 404,
    }
    for code, expected_status in mapping.items():
        coordinator.failure = code
        response = client.post(
            f"/api/v1/assets/upload-intents/{INTENT_ID}/ingestion-jobs",
            headers={
                "Authorization": "Bearer fixture",
                "Idempotency-Key": f"failure-{code}",
            },
        )
        assert response.status_code == expected_status
        assert response.json()["code"] == code
        assert INTENT_ID not in response.text

    malformed = client.get(
        "/api/v1/jobs/not-an-opaque-id", headers={"Authorization": "Bearer fixture"}
    )
    assert malformed.status_code == 422
    assert "not-an-opaque-id" not in malformed.text


def test_ingestion_openapi_contract_is_complete_and_strict() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    create = paths["/api/v1/assets/upload-intents/{intent_id}/ingestion-jobs"]["post"]
    assert "202" in create["responses"]
    assert any(
        parameter["name"] == "Idempotency-Key"
        and parameter["in"] == "header"
        and parameter["required"]
        for parameter in create["parameters"]
    )
    assert "/api/v1/jobs/{job_id}" in paths
    job_schema = schema["components"]["schemas"]["IngestionJobResponse"]
    assert job_schema["additionalProperties"] is False
    properties = set(job_schema["properties"])
    assert properties == {"job_id", "status", "result_code", "asset_id", "finalized_at"}
