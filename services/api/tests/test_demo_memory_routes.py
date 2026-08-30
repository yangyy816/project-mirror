from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_job_service import DemoJobSnapshot, DemoJobTargetSnapshot
from mirror_api.demo_memory_coordinator import DemoMemoryCoordinator, DemoMemoryCreateResult
from mirror_api.demo_memory_dependencies import (
    get_demo_memory_coordinator,
    get_demo_memory_service,
)
from mirror_api.demo_memory_service import (
    DemoContextRecall,
    DemoMemoryAuthorityCorruption,
    DemoMemoryConflict,
    DemoMemoryInputError,
    DemoMemoryService,
    DemoMemoryUnavailable,
    RebuildDemoAestheticProfile,
)
from mirror_api.demo_models import DemoActor
from mirror_api.errors import APIError, api_error_handler, validation_error_handler
from mirror_api.middleware import RequestIDMiddleware
from mirror_api.routers.demo import router

_ACTOR_ID = "a" * 32
_JOB_ID = "b" * 32
_DIGEST = "c" * 64
_SESSION_ID = "1" * 32
_PROFILE_ID = "2" * 32
_CONTEXT_ID = "3" * 32
_RECALL_AT = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2026, 8, 31, 12, 30, tzinfo=UTC)


def _job() -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id=_JOB_ID,
        demo_actor_id=_ACTOR_ID,
        demo_session_id=None,
        status="PENDING",
        capability="P7_PROFILE_REBUILD",
        job_binding_digest=_DIGEST,
        target=DemoJobTargetSnapshot(
            target_type="DEMO_ACTOR",
            target_id=_ACTOR_ID,
            authority_digest="d" * 64,
        ),
        result_code=None,
        finalized_at=None,
    )


@dataclass
class _Coordinator:
    failure: Exception | None = None
    command: RebuildDemoAestheticProfile | None = None

    async def create(self, command: RebuildDemoAestheticProfile) -> DemoMemoryCreateResult:
        if self.failure is not None:
            raise self.failure
        self.command = command
        return DemoMemoryCreateResult(job=_job(), replayed=False)


@dataclass
class _Service:
    failure: Exception | None = None
    calls: list[tuple[str, str, datetime]] = field(default_factory=list)

    async def recall_context(
        self,
        *,
        demo_actor_id: str,
        demo_session_id: str,
        recall_at: datetime,
    ) -> DemoContextRecall:
        if self.failure is not None:
            raise self.failure
        self.calls.append((demo_actor_id, demo_session_id, recall_at))
        return DemoContextRecall(
            context_compilation_id=_CONTEXT_ID,
            aesthetic_profile_id=_PROFILE_ID,
            context_digest=_DIGEST,
            expires_at=_EXPIRES_AT,
        )


def _actor() -> DemoActor:
    return DemoActor(
        id=_ACTOR_ID,
        schema_version="mirror.demo/Actor/v1",
        canonical_payload={},
        content_digest="e" * 64,
        actor_kind="LOCAL_SINGLE_USER",
        credential_key_id="local",
        authority_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def _client(coordinator: _Coordinator, service: _Service | None = None) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_memory_coordinator] = lambda: cast(
        DemoMemoryCoordinator, coordinator
    )
    if service is not None:
        app.dependency_overrides[get_demo_memory_service] = lambda: cast(DemoMemoryService, service)
    return TestClient(app)


def test_profile_rebuild_route_admits_owner_bound_pending_job() -> None:
    coordinator = _Coordinator()

    response = _client(coordinator).post(
        "/api/v1/demo/profiles/rebuild",
        headers={
            "Idempotency-Key": "memory-rebuild-key",
            "X-Request-ID": "memory-route-request",
        },
        json={"reason": "ROLLBACK"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": _JOB_ID,
        "status": "PENDING",
        "capability": "P7_PROFILE_REBUILD",
        "job_binding_digest": _DIGEST,
        "target": {
            "target_type": "DEMO_ACTOR",
            "target_id": _ACTOR_ID,
            "authority_digest": "d" * 64,
        },
    }
    assert coordinator.command == RebuildDemoAestheticProfile(
        demo_actor_id=_ACTOR_ID,
        reason="ROLLBACK",
        idempotency_key="memory-rebuild-key",
        request_id="memory-route-request",
    )


@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        (
            DemoMemoryConflict("different payload"),
            409,
            "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
        ),
        (DemoMemoryInputError("invalid request"), 422, "DEMO_MEMORY_REQUEST_INVALID"),
        (DemoMemoryUnavailable("missing actor"), 404, "DEMO_MEMORY_AUTHORITY_UNAVAILABLE"),
        (
            DemoMemoryAuthorityCorruption("invalid authority"),
            503,
            "DEMO_MEMORY_AUTHORITY_CORRUPT",
        ),
    ],
)
def test_profile_rebuild_route_maps_application_failures(
    failure: Exception, status_code: int, code: str
) -> None:
    response = _client(_Coordinator(failure=failure)).post(
        "/api/v1/demo/profiles/rebuild",
        headers={"Idempotency-Key": "memory-rebuild-key"},
        json={"reason": "USER_REQUEST"},
    )

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert response.json()["details"] == {"track": "DEMO_PROTOTYPE"}


def test_context_and_trace_routes_recall_same_explicit_owner_bound_context() -> None:
    service = _Service()
    client = _client(_Coordinator(), service)
    params = {"recall_at": _RECALL_AT.isoformat()}

    context = client.get(
        f"/api/v1/demo/sessions/{_SESSION_ID}/context",
        params=params,
    )
    trace = client.get(f"/api/v1/demo/traces/{_SESSION_ID}", params=params)

    assert context.status_code == 200
    assert context.json() == {
        "session_id": _SESSION_ID,
        "profile_id": _PROFILE_ID,
        "compilation_digest": _DIGEST,
        "expires_at": _EXPIRES_AT.isoformat().replace("+00:00", "Z"),
    }
    assert trace.status_code == 200
    assert trace.json() == {
        "session_id": _SESSION_ID,
        "evidence_digest": _DIGEST,
        "context_compilation_id": _CONTEXT_ID,
    }
    assert service.calls == [
        (_ACTOR_ID, _SESSION_ID, _RECALL_AT),
        (_ACTOR_ID, _SESSION_ID, _RECALL_AT),
    ]


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/demo/sessions/{_SESSION_ID}/context",
        f"/api/v1/demo/traces/{_SESSION_ID}",
    ],
)
def test_context_and_trace_routes_require_explicit_valid_recall_at(path: str) -> None:
    service = _Service()
    client = _client(_Coordinator(), service)

    missing = client.get(path)
    malformed = client.get(path, params={"recall_at": "not-a-timestamp"})

    assert (missing.status_code, missing.json()["code"]) == (
        422,
        "request_validation_failed",
    )
    assert (malformed.status_code, malformed.json()["code"]) == (
        422,
        "request_validation_failed",
    )
    assert service.calls == []


@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        (DemoMemoryInputError("naive recall"), 422, "DEMO_MEMORY_REQUEST_INVALID"),
        (
            DemoMemoryUnavailable("expired context"),
            404,
            "DEMO_MEMORY_AUTHORITY_UNAVAILABLE",
        ),
        (
            DemoMemoryAuthorityCorruption("invalid digest"),
            503,
            "DEMO_MEMORY_AUTHORITY_CORRUPT",
        ),
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/demo/sessions/{_SESSION_ID}/context",
        f"/api/v1/demo/traces/{_SESSION_ID}",
    ],
)
def test_context_and_trace_routes_map_recall_failures(
    failure: Exception, status_code: int, code: str, path: str
) -> None:
    response = _client(_Coordinator(), _Service(failure=failure)).get(
        path,
        params={"recall_at": _RECALL_AT.isoformat()},
    )

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert response.json()["details"] == {"track": "DEMO_PROTOTYPE"}
