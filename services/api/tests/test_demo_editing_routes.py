from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_editing_commands import DemoOwnedToolRun
from mirror_api.demo_editing_coordinator import DemoEditingCreateResult
from mirror_api.demo_editing_dependencies import get_demo_editing_coordinator
from mirror_api.demo_idempotency import DemoIdempotencyPayloadConflict
from mirror_api.demo_job_service import DemoJobSnapshot, DemoJobTargetSnapshot
from mirror_api.demo_models import DemoActor
from mirror_api.errors import APIError, api_error_handler, validation_error_handler
from mirror_api.middleware import RequestIDMiddleware
from mirror_api.routers.demo import router

_ACTOR_ID = "a" * 32
_SESSION_ID = "b" * 32
_TARGET_ID = "c" * 32
_JOB_ID = "d" * 32
_DIGEST = "e" * 64


class _Coordinator:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.commands: list[Any] = []

    async def _create(self, command: object, *, target_type: str) -> DemoEditingCreateResult:
        if self.failure is not None:
            raise self.failure
        self.commands.append(command)
        return DemoEditingCreateResult(
            job=DemoJobSnapshot(
                job_id=_JOB_ID,
                demo_actor_id=_ACTOR_ID,
                demo_session_id=_SESSION_ID,
                status="PENDING",
                capability="P6_EDITING",
                job_binding_digest=_DIGEST,
                target=DemoJobTargetSnapshot(
                    target_type=target_type,  # type: ignore[arg-type]
                    target_id=_TARGET_ID,
                    authority_digest=_DIGEST,
                ),
                result_code=None,
                finalized_at=None,
            ),
            target_id=_TARGET_ID,
            replayed=False,
        )

    async def create_editing_session(self, command: object) -> DemoEditingCreateResult:
        return await self._create(command, target_type="EDITING_SESSION")

    async def create_edit_plan(self, command: object) -> DemoEditingCreateResult:
        return await self._create(command, target_type="EDIT_PLAN")

    async def execute_edit_plan(self, command: object) -> DemoEditingCreateResult:
        return await self._create(command, target_type="EDIT_PLAN")

    async def restore_image_version(self, command: object) -> DemoEditingCreateResult:
        return await self._create(command, target_type="IMAGE_VERSION")

    async def get_tool_run(self, **_: str) -> DemoOwnedToolRun:
        if self.failure is not None:
            raise self.failure
        return DemoOwnedToolRun(_TARGET_ID, "contrast", _JOB_ID, "COMPLETED", _DIGEST)


def _actor() -> DemoActor:
    return DemoActor(
        id=_ACTOR_ID,
        schema_version="mirror.demo/Actor/v1",
        canonical_payload={},
        content_digest="f" * 64,
        actor_kind="LOCAL_SINGLE_USER",
        credential_key_id="local",
        authority_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def _client(coordinator: _Coordinator) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_editing_coordinator] = lambda: coordinator
    return TestClient(app)


def _post(client: TestClient, path: str, payload: dict[str, Any]) -> Any:
    return client.post(
        path,
        headers={"Idempotency-Key": "editing-idempotency-01", "X-Request-ID": "request-0001"},
        json=payload,
    )


def test_d07_create_routes_use_owner_bound_commands_without_session_in_target_requests() -> None:
    coordinator = _Coordinator()
    client = _client(coordinator)

    responses = (
        _post(
            client,
            "/api/v1/demo/editing-sessions",
            {"session_id": _SESSION_ID, "source_asset_id": "1" * 32},
        ),
        _post(
            client,
            f"/api/v1/demo/editing-sessions/{_TARGET_ID}/plans",
            {"operation": "CONTRAST", "value_ppm": 100_000},
        ),
        _post(
            client,
            f"/api/v1/demo/edit-plans/{_TARGET_ID}/executions",
            {"execution_mode": "DETERMINISTIC_RASTER", "expected_plan_digest": _DIGEST},
        ),
        _post(
            client,
            f"/api/v1/demo/image-versions/{_TARGET_ID}/restore",
            {
                "expected_current_image_version_id": "2" * 32,
                "expected_current_image_version_digest": _DIGEST,
            },
        ),
    )
    assert [response.status_code for response in responses] == [202, 202, 202, 202]
    assert all(response.json()["job_id"] == _JOB_ID for response in responses)
    assert len(coordinator.commands) == 4
    assert all(command.request_id == "request-0001" for command in coordinator.commands)
    assert not hasattr(coordinator.commands[1], "demo_session_id")
    assert not hasattr(coordinator.commands[2], "demo_session_id")
    assert not hasattr(coordinator.commands[3], "demo_session_id")


def test_d07_tool_run_is_owner_bound_and_returns_terminal_job_state() -> None:
    response = _client(_Coordinator()).get(f"/api/v1/demo/tool-runs/{_TARGET_ID}")
    assert response.status_code == 200
    assert response.json() == {
        "tool_run_id": _TARGET_ID,
        "tool_name": "contrast",
        "status": "COMPLETED",
        "output_digest": _DIGEST,
    }


def test_d07_routes_preserve_validation_and_idempotency_conflict_errors() -> None:
    invalid = _post(
        _client(_Coordinator()),
        "/api/v1/demo/editing-sessions",
        {
            "session_id": _SESSION_ID,
            "source_asset_id": "1" * 32,
            "source_image_version_id": "2" * 32,
        },
    )
    assert invalid.status_code == 422

    conflict = _post(
        _client(_Coordinator(failure=DemoIdempotencyPayloadConflict())),
        f"/api/v1/demo/edit-plans/{_TARGET_ID}/executions",
        {"execution_mode": "GEOMETRY", "expected_plan_digest": _DIGEST},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
