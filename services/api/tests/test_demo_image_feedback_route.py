from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi.testclient import TestClient

from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_idempotency import DemoIdempotencyPayloadConflict
from mirror_api.demo_image_feedback_dependencies import (
    get_demo_image_feedback_service,
)
from mirror_api.demo_image_feedback_service import (
    CreateDemoImageFeedback,
    DemoImageFeedbackAuthorityCorruption,
    DemoImageFeedbackConflict,
    DemoImageFeedbackResult,
    DemoImageFeedbackUnavailable,
)
from mirror_api.main import create_app

ACTOR_ID = "a" * 32
IMAGE_ID = "b" * 32
EVENT_ID = "c" * 32
EVENT_DIGEST = "d" * 64


@dataclass
class _RouteService:
    error: Exception | None = None
    received: CreateDemoImageFeedback | None = None

    async def create(self, command: CreateDemoImageFeedback) -> DemoImageFeedbackResult:
        self.received = command
        if self.error is not None:
            raise self.error
        return DemoImageFeedbackResult(
            event_id=EVENT_ID,
            event_type="IMAGE_ACCEPTED",
            event_digest=EVENT_DIGEST,
            final_save=command.acceptance_kind == "FINAL_SAVE",
            replayed=False,
        )


def _actor() -> object:
    return type("RouteActor", (), {"id": ACTOR_ID})()


def _service_override(service: _RouteService) -> Callable[[], object]:
    def dependency() -> object:
        return service

    return dependency


def test_image_feedback_route_preserves_explicit_intent_and_actor_ownership() -> None:
    app = create_app()
    service = _RouteService()
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_image_feedback_service] = _service_override(service)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/demo/image-versions/{IMAGE_ID}/feedback",
            headers={"Idempotency-Key": "feedback-route-key"},
            json={"feedback": "ACCEPT", "acceptance_kind": "FINAL_SAVE"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "event_id": EVENT_ID,
        "event_type": "IMAGE_ACCEPTED",
        "event_digest": EVENT_DIGEST,
    }
    assert service.received == CreateDemoImageFeedback(
        demo_actor_id=ACTOR_ID,
        image_version_id=IMAGE_ID,
        feedback="ACCEPT",
        acceptance_kind="FINAL_SAVE",
        intensity_ppm=None,
        idempotency_key="feedback-route-key",
    )


def test_image_feedback_route_rejects_ambiguous_accept_before_service() -> None:
    app = create_app()
    service = _RouteService()
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_image_feedback_service] = _service_override(service)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/demo/image-versions/{IMAGE_ID}/feedback",
            headers={"Idempotency-Key": "feedback-route-key"},
            json={"feedback": "ACCEPT"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_failed"
    assert service.received is None


def test_image_feedback_route_maps_conflict_unavailable_and_corruption() -> None:
    cases = (
        (
            DemoIdempotencyPayloadConflict(),
            409,
            "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
        ),
        (
            DemoImageFeedbackConflict("invalid state"),
            409,
            "DEMO_IMAGE_FEEDBACK_STATE_CONFLICT",
        ),
        (
            DemoImageFeedbackUnavailable("foreign image"),
            404,
            "DEMO_IMAGE_VERSION_UNAVAILABLE",
        ),
        (
            DemoImageFeedbackAuthorityCorruption("bad digest"),
            503,
            "DEMO_IMAGE_FEEDBACK_AUTHORITY_CORRUPT",
        ),
    )
    for error, expected_status, expected_code in cases:
        app = create_app()
        service = _RouteService(error=error)
        app.dependency_overrides[get_demo_actor] = _actor
        app.dependency_overrides[get_demo_image_feedback_service] = _service_override(service)
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/demo/image-versions/{IMAGE_ID}/feedback",
                headers={"Idempotency-Key": "feedback-route-key"},
                json={"feedback": "REJECT"},
            )
        app.dependency_overrides.clear()

        assert response.status_code == expected_status
        assert response.json()["code"] == expected_code
