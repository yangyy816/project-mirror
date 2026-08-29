from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import cast

from fastapi.testclient import TestClient

from mirror_api.demo_analysis_dependencies import get_demo_job_service
from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_job_service import (
    DemoJobService,
    DemoJobSnapshot,
    DemoJobTargetSnapshot,
)
from mirror_api.demo_models import DemoActor
from mirror_api.demo_questionnaire_bank import (
    QuestionPairPresentation,
    QuestionSidePresentation,
)
from mirror_api.demo_questionnaire_dependencies import get_demo_questionnaire_service
from mirror_api.demo_questionnaire_service import (
    CreateDemoQuestionnaireResponse,
    CreateDemoQuestionnaireRun,
    DemoQuestionnaireCompleted,
    DemoQuestionnaireConflict,
    DemoQuestionnaireNext,
    DemoQuestionnaireRunAccepted,
    DemoQuestionnaireService,
    DemoQuestionnaireStepSnapshot,
)
from mirror_api.main import create_app

ACTOR_ID = "1" * 32
SESSION_ID = "2" * 32
SELF_STATE_ID = "3" * 32
RUN_ID = "4" * 32
JOB_ID = "5" * 32
STEP_ID = "6" * 32
PAIR_ID = "7" * 32
SOURCE_IDENTITY_ID = "8" * 32
NOW = datetime(2026, 8, 30, tzinfo=UTC)


def _job() -> DemoJobSnapshot:
    return DemoJobSnapshot(
        job_id=JOB_ID,
        demo_actor_id=ACTOR_ID,
        demo_session_id=SESSION_ID,
        status="PENDING",
        capability="P4_QUESTIONNAIRE",
        job_binding_digest="9" * 64,
        target=DemoJobTargetSnapshot(
            target_type="QUESTIONNAIRE_RUN",
            target_id=RUN_ID,
            authority_digest="a" * 64,
        ),
        result_code=None,
        finalized_at=None,
    )


def _question() -> DemoQuestionnaireNext:
    presentation = QuestionPairPresentation(
        question_pair_digest="b" * 64,
        source_asset_id="c" * 32,
        source_checksum="d" * 64,
        left=QuestionSidePresentation(
            result_asset_id="e" * 32,
            result_checksum="f" * 64,
            result_lineage_digest="0" * 64,
            requested_direction="NEGATIVE",
            measured_delta_ppm=-15_000,
        ),
        right=QuestionSidePresentation(
            result_asset_id="a" * 32,
            result_checksum="1" * 64,
            result_lineage_digest="2" * 64,
            requested_direction="POSITIVE",
            measured_delta_ppm=15_000,
        ),
    )
    return DemoQuestionnaireNext(
        kind="QUESTION",
        snapshot=DemoQuestionnaireStepSnapshot(
            step_id=STEP_ID,
            questionnaire_run_id=RUN_ID,
            event_type="PRESENTED",
            step_number=1,
            step_sequence=1,
            run_version=1,
        ),
        question_pair_id=PAIR_ID,
        dimension_key="jaw_width",
        magnitude_ppm=15_000,
        source_identity_id=SOURCE_IDENTITY_ID,
        presentation=presentation,
        routing_score_ppm=500_000,
        routing_components=MappingProxyType(
            {
                "posterior_uncertainty_ppm": 1_000_000,
                "self_state_reliability_ppm": 900_000,
                "coverage_need_ppm": 1_000_000,
                "expected_fisher_information_ppm": 250_000,
                "morphology_neighborhood_compatibility_ppm": 800_000,
                "pair_quality_ppm": 900_000,
                "contradiction_priority_ppm": 500_000,
            }
        ),
        routing_evidence_digest="3" * 64,
    )


@dataclass
class _Questionnaires:
    next_result: DemoQuestionnaireNext | DemoQuestionnaireCompleted
    conflict: bool = False
    create_command: CreateDemoQuestionnaireRun | None = None
    response_command: CreateDemoQuestionnaireResponse | None = None

    async def create(self, command: CreateDemoQuestionnaireRun) -> DemoQuestionnaireRunAccepted:
        self.create_command = command
        return DemoQuestionnaireRunAccepted(JOB_ID, RUN_ID, SESSION_ID, False)

    async def next(
        self, *, demo_actor_id: str, questionnaire_run_id: str
    ) -> DemoQuestionnaireNext | DemoQuestionnaireCompleted:
        assert demo_actor_id == ACTOR_ID
        assert questionnaire_run_id == RUN_ID
        if self.conflict:
            raise DemoQuestionnaireConflict("terminal")
        return self.next_result

    async def respond(
        self, command: CreateDemoQuestionnaireResponse
    ) -> DemoQuestionnaireStepSnapshot:
        self.response_command = command
        return DemoQuestionnaireStepSnapshot(
            step_id="4" * 32,
            questionnaire_run_id=RUN_ID,
            event_type="RESPONDED",
            step_number=1,
            step_sequence=2,
            run_version=2,
        )


@dataclass
class _Jobs:
    async def get(self, *, demo_actor_id: str, job_id: str) -> DemoJobSnapshot:
        assert demo_actor_id == ACTOR_ID
        assert job_id == JOB_ID
        return _job()


def _actor() -> DemoActor:
    return DemoActor(
        id=ACTOR_ID,
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload={},
        content_digest="5" * 64,
        actor_kind="AUTOMATED_TEST",
        credential_key_id="test",
        authority_at=NOW,
    )


def test_questionnaire_routes_project_real_service_contracts() -> None:
    app = create_app()
    questionnaires = _Questionnaires(next_result=_question())
    jobs = _Jobs()
    app.dependency_overrides[get_demo_actor] = _actor
    app.dependency_overrides[get_demo_questionnaire_service] = lambda: cast(
        DemoQuestionnaireService, questionnaires
    )
    app.dependency_overrides[get_demo_job_service] = lambda: cast(DemoJobService, jobs)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/demo/questionnaires/runs",
            headers={"Idempotency-Key": "questionnaire-create-key"},
            json={
                "session_id": SESSION_ID,
                "self_state_id": SELF_STATE_ID,
                "question_bank_version": "d02-r2-v3",
                "max_questions": 12,
            },
        )
        assert created.status_code == 202
        assert created.json()["capability"] == "P4_QUESTIONNAIRE"
        assert created.json()["target"] == {
            "target_type": "QUESTIONNAIRE_RUN",
            "target_id": RUN_ID,
            "authority_digest": "a" * 64,
        }
        assert questionnaires.create_command is not None
        assert questionnaires.create_command.demo_actor_id == ACTOR_ID
        assert questionnaires.create_command.demo_session_id == SESSION_ID
        assert questionnaires.create_command.self_state_id == SELF_STATE_ID
        assert questionnaires.create_command.max_questions == 12
        assert questionnaires.create_command.idempotency_key == "questionnaire-create-key"

        question = client.get(f"/api/v1/demo/questionnaires/runs/{RUN_ID}/next")
        assert question.status_code == 200
        body = question.json()
        assert body["kind"] == "QUESTION"
        assert body["question_pair_id"] == PAIR_ID
        assert body["question_pair_digest"] == "b" * 64
        assert body["source_asset_id"] == "c" * 32
        assert body["left"]["requested_direction"] == "NEGATIVE"
        assert body["left"]["result_lineage_digest"] == "0" * 64
        assert body["right"]["requested_direction"] == "POSITIVE"
        assert body["right"]["result_lineage_digest"] == "2" * 64
        assert body["step_sequence"] == 1
        assert body["run_version"] == 1

        response = client.post(
            f"/api/v1/demo/questionnaires/runs/{RUN_ID}/responses",
            headers={"Idempotency-Key": "questionnaire-response-key"},
            json={
                "selected_side": "RIGHT",
                "expected_step_sequence": 1,
                "expected_run_version": 1,
                "response_latency_ms": 123,
            },
        )
        assert response.status_code == 201
        assert response.json() == {
            "step_id": "4" * 32,
            "run_id": RUN_ID,
            "event_type": "RESPONDED",
            "step_number": 1,
            "step_sequence": 2,
            "run_version": 2,
        }
        assert questionnaires.response_command is not None
        assert questionnaires.response_command.demo_actor_id == ACTOR_ID
        assert questionnaires.response_command.selected_side.value == "RIGHT"
        assert questionnaires.response_command.idempotency_key == "questionnaire-response-key"

        questionnaires.next_result = DemoQuestionnaireCompleted("COMPLETED", RUN_ID, NOW)
        completed = client.get(f"/api/v1/demo/questionnaires/runs/{RUN_ID}/next")
        assert completed.status_code == 200
        assert completed.json() == {
            "kind": "COMPLETED",
            "run_id": RUN_ID,
            "completed_at": "2026-08-30T00:00:00Z",
        }

        questionnaires.conflict = True
        conflict = client.get(f"/api/v1/demo/questionnaires/runs/{RUN_ID}/next")
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "DEMO_QUESTIONNAIRE_STATE_CONFLICT"

    app.dependency_overrides.clear()
