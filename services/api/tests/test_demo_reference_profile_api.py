from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_job_service import (
    DemoJobSnapshot,
    DemoJobStatus,
    DemoJobTargetSnapshot,
)
from mirror_api.demo_models import DemoActor
from mirror_api.demo_reference_profile_coordinator import (
    DemoReferenceProfileCoordinator,
    DemoReferenceProfileCreateResult,
)
from mirror_api.demo_reference_profile_dependencies import (
    get_demo_reference_profile_coordinator,
    get_demo_reference_profile_service,
)
from mirror_api.demo_reference_profile_service import (
    CreateDemoReferenceProfileCompilation,
    DemoReferenceProfileConflict,
    DemoReferenceProfileSnapshot,
)
from mirror_api.main import create_app

ACTOR_ID = "1" * 32
SESSION_ID = "2" * 32
DESIRED_DELTA_ID = "3" * 32
STYLE_ID = "4" * 32
CONSTRAINTS_ID = "5" * 32
ASSET_ID = "6" * 32
JOB_ID = "7" * 32
REQUEST_ID = "8" * 32


def _actor() -> DemoActor:
    return DemoActor(
        id=ACTOR_ID,
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload={},
        content_digest="a" * 64,
        actor_kind="AUTOMATED_TEST",
        credential_key_id="test",
        authority_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def _job() -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id=JOB_ID,
        demo_actor_id=ACTOR_ID,
        demo_session_id=SESSION_ID,
        status=cast(DemoJobStatus, "PENDING"),
        capability="P5_REFERENCE_PROFILE",
        job_binding_digest="b" * 64,
        target=DemoJobTargetSnapshot(
            target_type="REFERENCE_PROFILE_REQUEST",
            target_id=REQUEST_ID,
            authority_digest="c" * 64,
        ),
        result_code=None,
        finalized_at=None,
    )


@dataclass
class _Coordinator:
    command: CreateDemoReferenceProfileCompilation | None = None
    failure: Exception | None = None

    async def create(
        self, command: CreateDemoReferenceProfileCompilation
    ) -> DemoReferenceProfileCreateResult:
        self.command = command
        if self.failure is not None:
            raise self.failure
        return DemoReferenceProfileCreateResult(job=_job(), replayed=False)


@dataclass
class _Profiles:
    async def active_profiles(
        self, *, demo_actor_id: str
    ) -> tuple[DemoReferenceProfileSnapshot, ...]:
        assert demo_actor_id == ACTOR_ID
        return (DemoReferenceProfileSnapshot("d" * 32, 2, "e" * 64, 1),)


def _client(coordinator: _Coordinator, profiles: _Profiles) -> tuple[TestClient, object]:
    app = create_app()
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_reference_profile_coordinator] = lambda: cast(
        DemoReferenceProfileCoordinator, coordinator
    )
    app.dependency_overrides[get_demo_reference_profile_service] = lambda: profiles
    return TestClient(app), app


def test_compile_returns_202_owner_bound_job_and_opaque_command() -> None:
    coordinator = _Coordinator()
    client, app = _client(coordinator, _Profiles())
    try:
        with client:
            response = client.post(
                "/api/v1/demo/reference-profiles/compile",
                headers={"Idempotency-Key": "d06-api-idempotency-key"},
                json={
                    "session_id": SESSION_ID,
                    "desired_delta_profile_id": DESIRED_DELTA_ID,
                    "style_profile_id": STYLE_ID,
                    "identity_constraints_id": CONSTRAINTS_ID,
                    "sources": [{"asset_id": ASSET_ID, "view": "FRONT"}],
                },
            )
        assert response.status_code == 202
        assert response.json() == {
            "job_id": JOB_ID,
            "status": "PENDING",
            "capability": "P5_REFERENCE_PROFILE",
            "job_binding_digest": "b" * 64,
            "target": {
                "target_type": "REFERENCE_PROFILE_REQUEST",
                "target_id": REQUEST_ID,
                "authority_digest": "c" * 64,
            },
        }
        assert coordinator.command is not None
        assert coordinator.command.demo_actor_id == ACTOR_ID
        assert coordinator.command.idempotency_key == "d06-api-idempotency-key"
        assert coordinator.command.sources[0].asset_id == ASSET_ID
    finally:
        app.dependency_overrides.clear()


def test_active_read_and_conflict_use_safe_public_envelopes() -> None:
    coordinator = _Coordinator(
        failure=DemoReferenceProfileConflict(
            "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD", "opaque"
        )
    )
    client, app = _client(coordinator, _Profiles())
    try:
        with client:
            active = client.get("/api/v1/demo/reference-profiles/active")
            conflict = client.post(
                "/api/v1/demo/reference-profiles/compile",
                headers={"Idempotency-Key": "d06-api-conflict-key"},
                json={
                    "session_id": SESSION_ID,
                    "desired_delta_profile_id": DESIRED_DELTA_ID,
                    "sources": [{"asset_id": ASSET_ID, "view": "FRONT"}],
                },
            )
        assert active.status_code == 200
        assert active.json() == {
            "profiles": [
                {
                    "reference_profile_id": "d" * 32,
                    "version": 2,
                    "content_digest": "e" * 64,
                    "source_count": 1,
                }
            ]
        }
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
        assert "opaque" not in conflict.text
    finally:
        app.dependency_overrides.clear()
