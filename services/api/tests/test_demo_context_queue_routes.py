from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from mirror_api.demo_context_coordinator import DemoContextCoordinator, DemoContextCreateResult
from mirror_api.demo_context_dependencies import get_demo_context_coordinator
from mirror_api.demo_context_queue_service import (
    CreateDemoContextCompilation,
    DemoContextQueueConflict,
)
from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_job_service import DemoJobSnapshot, DemoJobStatus, DemoJobTargetSnapshot
from mirror_api.demo_models import DemoActor
from mirror_api.main import create_app

ACTOR_ID = "1" * 32
SESSION_ID = "2" * 32
PROFILE_ID = "3" * 32
JOB_ID = "4" * 32
AS_OF = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


def _actor() -> DemoActor:
    return DemoActor(
        id=ACTOR_ID,
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload={},
        content_digest="a" * 64,
        actor_kind="AUTOMATED_TEST",
        credential_key_id="test",
        authority_at=AS_OF,
    )


def _job() -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id=JOB_ID,
        demo_actor_id=ACTOR_ID,
        demo_session_id=SESSION_ID,
        status=cast(DemoJobStatus, "PENDING"),
        capability="P7_CONTEXT_COMPILER",
        job_binding_digest="b" * 64,
        target=DemoJobTargetSnapshot(
            target_type="DEMO_SESSION",
            target_id=SESSION_ID,
            authority_digest="c" * 64,
        ),
        result_code=None,
        finalized_at=None,
    )


@dataclass
class _Coordinator:
    command: CreateDemoContextCompilation | None = None
    failure: Exception | None = None

    async def create(self, command: CreateDemoContextCompilation) -> DemoContextCreateResult:
        self.command = command
        if self.failure is not None:
            raise self.failure
        return DemoContextCreateResult(job=_job(), replayed=False)


def _client(coordinator: _Coordinator) -> tuple[TestClient, object]:
    app = create_app()
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_context_coordinator] = lambda: cast(
        DemoContextCoordinator, coordinator
    )
    return TestClient(app), app


def test_context_compile_returns_owner_bound_pending_job() -> None:
    coordinator = _Coordinator()
    client, app = _client(coordinator)
    try:
        with client:
            response = client.post(
                f"/api/v1/demo/sessions/{SESSION_ID}/context/compile",
                headers={"Idempotency-Key": "d10-context-idempotency-key"},
                json={
                    "aesthetic_profile_id": PROFILE_ID,
                    "current_instruction_digest": "d" * 64,
                    "context_as_of_time": AS_OF.isoformat(),
                },
            )
        assert response.status_code == 202
        assert response.json() == {
            "job_id": JOB_ID,
            "status": "PENDING",
            "capability": "P7_CONTEXT_COMPILER",
            "job_binding_digest": "b" * 64,
            "target": {
                "target_type": "DEMO_SESSION",
                "target_id": SESSION_ID,
                "authority_digest": "c" * 64,
            },
        }
        assert coordinator.command is not None
        assert coordinator.command.demo_actor_id == ACTOR_ID
        assert coordinator.command.demo_session_id == SESSION_ID
        assert coordinator.command.aesthetic_profile_id == PROFILE_ID
        assert coordinator.command.context_as_of_time == AS_OF
        assert coordinator.command.idempotency_key == "d10-context-idempotency-key"
    finally:
        app.dependency_overrides.clear()


def test_context_compile_conflict_is_redacted_and_capability_is_available() -> None:
    coordinator = _Coordinator(
        failure=DemoContextQueueConflict("IMMUTABLE_CONTEXT_INPUT_EXISTS", "private detail")
    )
    client, app = _client(coordinator)
    try:
        with client:
            conflict = client.post(
                f"/api/v1/demo/sessions/{SESSION_ID}/context/compile",
                headers={"Idempotency-Key": "d10-context-conflict-key"},
                json={
                    "aesthetic_profile_id": PROFILE_ID,
                    "current_instruction_digest": "d" * 64,
                    "context_as_of_time": AS_OF.isoformat(),
                },
            )
            capabilities = client.get("/api/v1/demo/capabilities")
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IMMUTABLE_CONTEXT_INPUT_EXISTS"
        assert "private detail" not in conflict.text
        preference_memory = next(
            item
            for item in capabilities.json()["capabilities"]
            if item["code"] == "P7_PREFERENCE_MEMORY"
        )
        assert preference_memory["status"] == "AVAILABLE"
    finally:
        app.dependency_overrides.clear()
