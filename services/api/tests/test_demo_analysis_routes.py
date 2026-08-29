from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from mirror_api.demo_analysis_coordinator import (
    DemoAnalysisCoordinator,
    DemoAnalysisCreateResult,
)
from mirror_api.demo_analysis_dependencies import (
    get_demo_analysis_coordinator,
    get_demo_job_service,
)
from mirror_api.demo_analysis_service import CreateDemoAnalysis
from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_job_service import (
    DemoJobService,
    DemoJobSnapshot,
    DemoJobStatus,
    DemoJobTargetSnapshot,
)
from mirror_api.demo_models import DemoActor
from mirror_api.main import create_app

ACTOR_ID = "1" * 32
SESSION_ID = "2" * 32
RUN_ID = "3" * 32
JOB_ID = "4" * 32
SOURCE_ID = "5" * 32
OBSERVATION_DIGEST = "6" * 64


def _job(*, status: str = "PENDING") -> DemoJobSnapshot:
    result_code = None
    finalized_at = None
    if status == "COMPLETED":
        result_code = "SUPPORTED"
        finalized_at = datetime(2026, 8, 29, tzinfo=UTC)
    elif status == "CANCELLED":
        result_code = "USER_REQUEST"
        finalized_at = datetime(2026, 8, 29, tzinfo=UTC)
    return DemoJobSnapshot(
        job_id=JOB_ID,
        demo_actor_id=ACTOR_ID,
        demo_session_id=SESSION_ID,
        status=cast(DemoJobStatus, status),
        capability="P3_FACE_ANALYSIS",
        job_binding_digest="7" * 64,
        target=DemoJobTargetSnapshot(
            target_type="ANALYSIS_RUN",
            target_id=RUN_ID,
            authority_digest="8" * 64,
        ),
        result_code=result_code,
        finalized_at=finalized_at,
    )


@dataclass
class _Coordinator:
    snapshot_job: DemoJobSnapshot
    created_command: CreateDemoAnalysis | None = None

    async def create(self, command: CreateDemoAnalysis) -> DemoAnalysisCreateResult:
        self.created_command = command
        return DemoAnalysisCreateResult(job=_job(), replayed=False)

    async def snapshot(
        self, *, demo_actor_id: str, analysis_run_id: str
    ) -> tuple[DemoJobSnapshot, str | None, str | None]:
        assert demo_actor_id == ACTOR_ID
        assert analysis_run_id == RUN_ID
        if self.snapshot_job.status == "COMPLETED":
            return self.snapshot_job, "9" * 32, OBSERVATION_DIGEST
        return self.snapshot_job, None, None


@dataclass
class _Jobs:
    snapshot: DemoJobSnapshot
    cancel_calls: int = 0

    async def get(self, *, demo_actor_id: str, job_id: str) -> DemoJobSnapshot:
        assert demo_actor_id == ACTOR_ID
        assert job_id == JOB_ID
        return self.snapshot

    async def cancel(
        self,
        *,
        demo_actor_id: str,
        job_id: str,
        expected_status: str,
        reason: str,
        idempotency_key: str,
    ) -> DemoJobSnapshot:
        assert demo_actor_id == ACTOR_ID
        assert job_id == JOB_ID
        assert expected_status == "PENDING"
        assert reason == "USER_REQUEST"
        assert idempotency_key == "cancel-job-key"
        self.cancel_calls += 1
        return replace(
            self.snapshot,
            status="CANCELLED",
            result_code="USER_REQUEST",
            finalized_at=datetime(2026, 8, 29, tzinfo=UTC),
        )


def _actor() -> DemoActor:
    return DemoActor(
        id=ACTOR_ID,
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload={},
        content_digest="a" * 64,
        actor_kind="AUTOMATED_TEST",
        credential_key_id="test",
        authority_at=datetime(2026, 8, 29, tzinfo=UTC),
    )


def test_d03_and_generic_job_routes_use_owner_bound_application_services() -> None:
    app = create_app()
    coordinator = _Coordinator(snapshot_job=_job())
    jobs = _Jobs(snapshot=_job())
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_analysis_coordinator] = lambda: cast(
        DemoAnalysisCoordinator, coordinator
    )
    app.dependency_overrides[get_demo_job_service] = lambda: cast(DemoJobService, jobs)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/demo/analyses",
            headers={"Idempotency-Key": "analysis-create-key"},
            json={"session_id": SESSION_ID, "source_asset_id": SOURCE_ID},
        )
        assert created.status_code == 202
        assert created.json() == {
            "job_id": JOB_ID,
            "status": "PENDING",
            "capability": "P3_FACE_ANALYSIS",
            "job_binding_digest": "7" * 64,
            "target": {
                "target_type": "ANALYSIS_RUN",
                "target_id": RUN_ID,
                "authority_digest": "8" * 64,
            },
        }
        assert coordinator.created_command is not None
        assert coordinator.created_command.demo_actor_id == ACTOR_ID
        assert coordinator.created_command.demo_session_id == SESSION_ID
        assert coordinator.created_command.source_asset_id == SOURCE_ID
        assert coordinator.created_command.idempotency_key == "analysis-create-key"

        pending = client.get(f"/api/v1/demo/analyses/{RUN_ID}")
        assert pending.status_code == 200
        assert pending.json() == {
            "analysis_id": RUN_ID,
            "session_id": SESSION_ID,
            "state": "PENDING",
            "observation_digest": None,
        }

        job = client.get(f"/api/v1/demo/jobs/{JOB_ID}")
        assert job.status_code == 200
        assert job.json()["status"] == "PENDING"

        cancelled = client.post(
            f"/api/v1/demo/jobs/{JOB_ID}/cancel",
            headers={"Idempotency-Key": "cancel-job-key"},
            json={"expected_status": "PENDING", "reason": "USER_REQUEST"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"
        assert cancelled.json()["result_code"] == "USER_REQUEST"
        assert jobs.cancel_calls == 1

        capability = client.get("/api/v1/demo/capabilities")
        face = next(
            item for item in capability.json()["capabilities"] if item["code"] == "P3_FACE_ANALYSIS"
        )
        assert face["status"] == "NOT_IMPLEMENTED"

    app.dependency_overrides.clear()


def test_completed_and_terminal_analysis_mapping_is_truthful() -> None:
    app = create_app()
    coordinator = _Coordinator(snapshot_job=_job(status="COMPLETED"))
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_analysis_coordinator] = lambda: cast(
        DemoAnalysisCoordinator, coordinator
    )

    with TestClient(app) as client:
        completed = client.get(f"/api/v1/demo/analyses/{RUN_ID}")
        assert completed.status_code == 200
        assert completed.json()["state"] == "SUPPORTED"
        assert completed.json()["observation_digest"] == OBSERVATION_DIGEST

        coordinator.snapshot_job = _job(status="CANCELLED")
        terminal = client.get(f"/api/v1/demo/analyses/{RUN_ID}")
        assert terminal.status_code == 409
        assert terminal.json()["code"] == "DEMO_ANALYSIS_CANCELLED"
        assert terminal.json()["details"]["result_code"] == "USER_REQUEST"

    app.dependency_overrides.clear()
