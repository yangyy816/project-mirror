from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from mirror_api.demo_dependencies import get_demo_actor, get_demo_session_service
from mirror_api.demo_models import DemoActor
from mirror_api.demo_session_service import (
    CreateDemoSession,
    DemoIdentitySnapshot,
    DemoSessionAuthorityUnavailable,
    DemoSessionService,
    DemoSessionSnapshot,
    DemoSyntheticIdentityUnavailable,
)
from mirror_api.main import create_app

ACTOR_ID = "1" * 32
IDENTITY_ID = "2" * 32
SESSION_ID = "3" * 32
NOW = datetime(2026, 9, 3, 12, tzinfo=UTC)


@dataclass
class _SessionService:
    list_error: Exception | None = None
    create_error: Exception | None = None
    created: CreateDemoSession | None = None

    async def list_identities(self, *, demo_actor_id: str) -> tuple[DemoIdentitySnapshot, ...]:
        assert demo_actor_id == ACTOR_ID
        if self.list_error is not None:
            raise self.list_error
        return (
            DemoIdentitySnapshot(
                identity_id=IDENTITY_ID,
                canonical_asset_digest="a" * 64,
            ),
        )

    async def create(self, command: CreateDemoSession) -> DemoSessionSnapshot:
        self.created = command
        if self.create_error is not None:
            raise self.create_error
        return DemoSessionSnapshot(
            session_id=SESSION_ID,
            synthetic_identity_id=command.synthetic_identity_id,
            status="ACTIVE",
            expires_at=NOW,
        )


def _actor() -> DemoActor:
    return DemoActor(
        id=ACTOR_ID,
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload={},
        content_digest="b" * 64,
        actor_kind="AUTOMATED_TEST",
        credential_key_id="test",
        authority_at=NOW,
    )


def _client(service: _SessionService) -> tuple[TestClient, object]:
    app = create_app()
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_session_service] = lambda: cast(DemoSessionService, service)
    return TestClient(app), app


def test_identity_and_session_routes_activate_existing_contracts() -> None:
    service = _SessionService()
    client, app = _client(service)
    with client:
        identities = client.get("/api/v1/demo/identities")
        assert identities.status_code == 200
        assert identities.json() == {
            "identities": [
                {
                    "identity_id": IDENTITY_ID,
                    "canonical_asset_digest": "a" * 64,
                    "admission_status": "ADMITTED",
                }
            ]
        }

        created = client.post(
            "/api/v1/demo/sessions",
            headers={"Idempotency-Key": "d11-route-session"},
            json={
                "synthetic_identity_id": IDENTITY_ID,
                "context_seed": "c" * 64,
            },
        )
        assert created.status_code == 201
        assert created.json() == {
            "session_id": SESSION_ID,
            "synthetic_identity_id": IDENTITY_ID,
            "status": "ACTIVE",
            "expires_at": "2026-09-03T12:00:00Z",
        }
        assert service.created == CreateDemoSession(
            demo_actor_id=ACTOR_ID,
            synthetic_identity_id=IDENTITY_ID,
            context_seed="c" * 64,
            idempotency_key="d11-route-session",
        )
    app.dependency_overrides.clear()


def test_identity_and_session_route_failures_are_redacted() -> None:
    service = _SessionService(list_error=DemoSessionAuthorityUnavailable("private detail"))
    client, app = _client(service)
    with client:
        identities = client.get("/api/v1/demo/identities")
        assert identities.status_code == 503
        assert identities.json()["code"] == ("DEMO_SYNTHETIC_IDENTITY_AUTHORITY_UNAVAILABLE")
        assert "private detail" not in identities.text

        service.create_error = DemoSyntheticIdentityUnavailable("private detail")
        created = client.post(
            "/api/v1/demo/sessions",
            headers={"Idempotency-Key": "d11-route-session"},
            json={
                "synthetic_identity_id": IDENTITY_ID,
                "context_seed": "c" * 64,
            },
        )
        assert created.status_code == 404
        assert created.json()["code"] == "DEMO_SYNTHETIC_IDENTITY_UNAVAILABLE"
        assert "private detail" not in created.text
    app.dependency_overrides.clear()
