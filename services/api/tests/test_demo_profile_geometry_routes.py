from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from fastapi.testclient import TestClient

from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_editing_coordinator import (
    DemoEditingCoordinator,
    DemoProfileGuidedGeometryCreateResult,
)
from mirror_api.demo_editing_dependencies import (
    get_demo_editing_coordinator,
    get_demo_editing_media_service,
)
from mirror_api.demo_editing_media import DemoEditingMedia, DemoEditingMediaService
from mirror_api.demo_job_service import DemoJobSnapshot, DemoJobStatus, DemoJobTargetSnapshot
from mirror_api.demo_models import DemoActor
from mirror_api.demo_profile_geometry_acceptance import (
    AcceptProfileGeometryExecution,
    DemoProfileGeometryAcceptanceFacade,
    DemoProfileGeometryAcceptanceResult,
)
from mirror_api.demo_profile_geometry_dependencies import (
    get_demo_profile_geometry_acceptance_facade,
)
from mirror_api.demo_reference_profile_dependencies import get_demo_reference_profile_service
from mirror_api.demo_reference_profile_service import (
    DemoReferenceProfileCompletedResult,
    DemoReferenceProfileResultNotReady,
    DemoReferenceProfileService,
)
from mirror_api.main import create_app

_ACTOR_ID = "1" * 32
_SESSION_ID = "2" * 32
_EDITING_ID = "3" * 32
_PLAN_ID = "4" * 32
_EXECUTION_JOB_ID = "5" * 32
_REFERENCE_JOB_ID = "6" * 32
_PROFILE_ID = "7" * 32
_DIGEST = "a" * 64


def _actor() -> DemoActor:
    return DemoActor(
        id=_ACTOR_ID,
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload={},
        content_digest=_DIGEST,
        actor_kind="AUTOMATED_TEST",
        credential_key_id="test",
        authority_at=datetime(2026, 9, 4, tzinfo=UTC),
    )


def _job() -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id=_EXECUTION_JOB_ID,
        demo_actor_id=_ACTOR_ID,
        demo_session_id=_SESSION_ID,
        status=cast(DemoJobStatus, "PENDING"),
        capability="P6_GEOMETRY",
        job_binding_digest=_DIGEST,
        target=DemoJobTargetSnapshot(
            target_type="EDIT_PLAN",
            target_id=_PLAN_ID,
            authority_digest="b" * 64,
        ),
        result_code=None,
        finalized_at=None,
    )


@dataclass
class _Editing:
    command: object | None = None

    async def create_profile_guided_geometry_plan(
        self, command: object
    ) -> DemoProfileGuidedGeometryCreateResult:
        self.command = command
        return DemoProfileGuidedGeometryCreateResult(
            _job(),
            _PLAN_ID,
            "jaw_width",
            "INCREASE",
            15_000,
            "demo-profile-guided-d08-step-v1",
            False,
        )


@dataclass
class _Media:
    call: tuple[str, str, str] | None = None

    async def load(self, *, demo_actor_id: str, job_id: str, side: str) -> DemoEditingMedia:
        self.call = (demo_actor_id, job_id, side)
        return DemoEditingMedia(b"synthetic-jpeg")


@dataclass
class _Acceptance:
    command: AcceptProfileGeometryExecution | None = None

    async def accept(
        self, command: AcceptProfileGeometryExecution
    ) -> DemoProfileGeometryAcceptanceResult:
        self.command = command
        return DemoProfileGeometryAcceptanceResult(
            "REFERENCE_PROFILE_PENDING",
            _REFERENCE_JOB_ID,
            "PENDING",
        )


@dataclass
class _Reference:
    failure: Exception | None = None

    async def read_completed_result(self, **_: str) -> DemoReferenceProfileCompletedResult:
        if self.failure is not None:
            raise self.failure
        return DemoReferenceProfileCompletedResult(
            _REFERENCE_JOB_ID,
            _SESSION_ID,
            _PROFILE_ID,
            _DIGEST,
            "b" * 64,
            "c" * 64,
        )


def _client() -> tuple[TestClient, Any, _Editing, _Media, _Acceptance, _Reference]:
    app = create_app()
    editing, media, acceptance, reference = _Editing(), _Media(), _Acceptance(), _Reference()
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_editing_coordinator] = lambda: cast(
        DemoEditingCoordinator, editing
    )
    app.dependency_overrides[get_demo_editing_media_service] = lambda: cast(
        DemoEditingMediaService, media
    )
    app.dependency_overrides[get_demo_profile_geometry_acceptance_facade] = lambda: cast(
        DemoProfileGeometryAcceptanceFacade, acceptance
    )
    app.dependency_overrides[get_demo_reference_profile_service] = lambda: cast(
        DemoReferenceProfileService, reference
    )
    return TestClient(app), app, editing, media, acceptance, reference


def test_profile_geometry_plan_route_has_only_safe_preview() -> None:
    client, app, editing, _, _, _ = _client()
    try:
        response = client.post(
            f"/api/v1/demo/editing-sessions/{_EDITING_ID}/profile-geometry-plans",
            headers={"Idempotency-Key": "test-plan-key-00000000"},
            json={"selection_policy_version": "demo-profile-guided-d08-step-v1"},
        )
        assert response.status_code == 202
        assert response.json() == {
            "job_id": _EXECUTION_JOB_ID,
            "status": "PENDING",
            "capability": "P6_GEOMETRY",
            "job_binding_digest": _DIGEST,
            "target": {
                "target_type": "EDIT_PLAN",
                "target_id": _PLAN_ID,
                "authority_digest": "b" * 64,
            },
            "preview": {
                "dimension_key": "jaw_width",
                "direction": "INCREASE",
                "step_ppm": 15_000,
                "selection_policy_version": "demo-profile-guided-d08-step-v1",
            },
        }
        assert editing.command is not None
        invalid = client.post(
            f"/api/v1/demo/editing-sessions/{_EDITING_ID}/profile-geometry-plans",
            headers={"Idempotency-Key": "test-plan-key-00000001"},
            json={
                "selection_policy_version": "demo-profile-guided-d08-step-v1",
                "dimension_key": "jaw_width",
            },
        )
        assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_exact_execution_media_is_private_binary() -> None:
    client, app, _, media, _, _ = _client()
    try:
        response = client.get(
            f"/api/v1/demo/edit-plans/execution-jobs/{_EXECUTION_JOB_ID}/media/RESULT"
        )
        assert response.status_code == 200
        assert response.content == b"synthetic-jpeg"
        assert response.headers["content-type"].startswith("image/jpeg")
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert media.call == (_ACTOR_ID, _EXECUTION_JOB_ID, "RESULT")
        assert (
            client.get(
                f"/api/v1/demo/edit-plans/execution-jobs/{_EXECUTION_JOB_ID}/media/LEFT"
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.clear()


def test_accept_route_body_is_exact_and_response_is_safe() -> None:
    client, app, _, _, acceptance, _ = _client()
    try:
        response = client.post(
            f"/api/v1/demo/edit-plans/execution-jobs/{_EXECUTION_JOB_ID}/accept-as-reference",
            headers={"Idempotency-Key": "test-accept-key-00000000"},
            json={"outcome": "FINAL_SAVE_AND_USE_AS_REFERENCE"},
        )
        assert response.status_code == 202
        assert response.json() == {
            "status": "REFERENCE_PROFILE_PENDING",
            "reference_profile_job_id": _REFERENCE_JOB_ID,
            "queue_state": "PENDING",
        }
        assert acceptance.command == AcceptProfileGeometryExecution(
            _ACTOR_ID,
            _EXECUTION_JOB_ID,
            "test-accept-key-00000000",
            "FINAL_SAVE_AND_USE_AS_REFERENCE",
        )
        invalid = client.post(
            f"/api/v1/demo/edit-plans/execution-jobs/{_EXECUTION_JOB_ID}/accept-as-reference",
            headers={"Idempotency-Key": "test-accept-key-00000001"},
            json={
                "outcome": "FINAL_SAVE_AND_USE_AS_REFERENCE",
                "request_run_id": "f" * 32,
            },
        )
        assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_reference_result_is_exact_and_pending_is_conflict() -> None:
    client, app, _, _, _, reference = _client()
    try:
        response = client.get(
            f"/api/v1/demo/reference-profiles/compilation-jobs/{_REFERENCE_JOB_ID}/result"
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": "REFERENCE_PROFILE_READY",
            "job_id": _REFERENCE_JOB_ID,
            "session_id": _SESSION_ID,
            "reference_profile_id": _PROFILE_ID,
            "job_binding_digest": _DIGEST,
            "compilation_digest": "b" * 64,
            "profile_digest": "c" * 64,
        }
        reference.failure = DemoReferenceProfileResultNotReady("RESULT_NOT_READY", "not ready")
        pending = client.get(
            f"/api/v1/demo/reference-profiles/compilation-jobs/{_REFERENCE_JOB_ID}/result"
        )
        assert pending.status_code == 409
        assert pending.json()["code"] == "DEMO_REFERENCE_PROFILE_RESULT_NOT_READY"
    finally:
        app.dependency_overrides.clear()
