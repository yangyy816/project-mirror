from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from mirror_api.config import Settings
from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_models import DemoActor
from mirror_api.demo_schemas import (
    DemoCapability,
    DemoEditPlanExecuteRequest,
    DemoImageFeedbackRequest,
    DemoJobAcceptedResponse,
    DemoJobCancelRequest,
    DemoJobResponse,
    DemoQuestionNextResponse,
    DemoQuestionResponseRequest,
    DemoRestoreRequest,
    DemoSessionCreateRequest,
    DemoStyleFeedbackRequest,
    DemoToolRunResponse,
)
from mirror_api.errors import APIError, api_error_handler, validation_error_handler
from mirror_api.main import create_app
from mirror_api.routers.demo import IdempotencyKey, router


def _app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    return app


def test_demo_router_has_exact_frozen_operation_matrix_and_security() -> None:
    app = _app()
    schema = app.openapi()
    paths = {
        path: value for path, value in schema["paths"].items() if path.startswith("/api/v1/demo")
    }
    operations = [operation for item in paths.values() for operation in item.values()]
    operation_matrix = {
        (method.upper(), path, operation["operationId"])
        for path, item in paths.items()
        for method, operation in item.items()
    }
    assert operation_matrix == {
        ("GET", "/api/v1/demo/analyses/{analysis_id}", "demoGetAnalysis"),
        ("GET", "/api/v1/demo/capabilities", "demoGetCapabilities"),
        (
            "GET",
            "/api/v1/demo/edit-plans/execution-jobs/{job_id}/media/{side}",
            "demoGetEditExecutionMedia",
        ),
        (
            "GET",
            "/api/v1/demo/edit-plans/execution-jobs/{job_id}/result",
            "demoGetEditExecutionResultByJob",
        ),
        ("GET", "/api/v1/demo/identities", "demoListIdentities"),
        ("GET", "/api/v1/demo/jobs/{job_id}", "demoGetJob"),
        ("GET", "/api/v1/demo/profiles/active", "demoGetActiveProfiles"),
        (
            "GET",
            "/api/v1/demo/profiles/compilation-jobs/{job_id}/result",
            "demoGetProfileCompilationResultByJob",
        ),
        (
            "GET",
            "/api/v1/demo/questionnaires/runs/{run_id}/next",
            "demoGetQuestionnaireNext",
        ),
        (
            "GET",
            "/api/v1/demo/questionnaires/runs/{run_id}/presentation-media/{side}",
            "demoGetQuestionnairePresentationMedia",
        ),
        (
            "GET",
            "/api/v1/demo/reference-profiles/compilation-jobs/{job_id}/result",
            "demoGetReferenceProfileCompilationResultByJob",
        ),
        (
            "GET",
            "/api/v1/demo/reference-profiles/active",
            "demoGetActiveReferenceProfiles",
        ),
        (
            "GET",
            "/api/v1/demo/sessions/{session_id}/context",
            "demoGetSessionContext",
        ),
        ("GET", "/api/v1/demo/tool-runs/{tool_run_id}", "demoGetToolRun"),
        ("GET", "/api/v1/demo/traces/{session_id}", "demoGetTrace"),
        ("POST", "/api/v1/demo/analyses", "demoCreateAnalysis"),
        (
            "POST",
            "/api/v1/demo/analyses/{analysis_id}/questionnaire",
            "demoCreateAnalysisQuestionnaire",
        ),
        ("POST", "/api/v1/demo/constraints", "demoCreateConstraints"),
        (
            "POST",
            "/api/v1/demo/edit-plans/execution-jobs/{job_id}/accept-as-reference",
            "demoAcceptEditExecutionAsReference",
        ),
        (
            "POST",
            "/api/v1/demo/edit-plans/{edit_plan_id}/executions",
            "demoExecuteEditPlan",
        ),
        ("POST", "/api/v1/demo/editing-sessions", "demoCreateEditingSession"),
        (
            "POST",
            "/api/v1/demo/editing-sessions/{editing_session_id}/profile-geometry-plans",
            "demoCreateProfileGeometryPlan",
        ),
        (
            "POST",
            "/api/v1/demo/editing-sessions/{editing_session_id}/plans",
            "demoCreateEditPlan",
        ),
        (
            "POST",
            "/api/v1/demo/image-versions/{image_version_id}/feedback",
            "demoCreateImageVersionFeedback",
        ),
        (
            "POST",
            "/api/v1/demo/image-versions/{image_version_id}/restore",
            "demoRestoreImageVersion",
        ),
        ("POST", "/api/v1/demo/jobs/{job_id}/cancel", "demoCancelJob"),
        ("POST", "/api/v1/demo/profiles/compile", "demoCompileProfile"),
        ("POST", "/api/v1/demo/profiles/rebuild", "demoRebuildProfiles"),
        (
            "POST",
            "/api/v1/demo/questionnaires/runs",
            "demoCreateQuestionnaireRun",
        ),
        (
            "POST",
            "/api/v1/demo/questionnaires/runs/{run_id}/responses",
            "demoCreateQuestionnaireResponse",
        ),
        (
            "POST",
            "/api/v1/demo/reference-profiles/compile",
            "demoCompileReferenceProfile",
        ),
        ("POST", "/api/v1/demo/sessions", "demoCreateSession"),
        (
            "POST",
            "/api/v1/demo/sessions/{session_id}/analysis",
            "demoCreateSessionAnalysis",
        ),
        (
            "POST",
            "/api/v1/demo/sessions/{session_id}/context/compile",
            "demoCompileSessionContext",
        ),
        ("POST", "/api/v1/demo/style-feedback", "demoCreateStyleFeedback"),
    }
    assert len(operations) == 35
    assert sum(operation["operationId"].startswith("demo") for operation in operations) == 35
    assert all(operation["x-demo-only"] is True for operation in operations)
    posts = [
        operation
        for operation in operations
        if operation["operationId"]
        in {
            "demoCreateSession",
            "demoCreateAnalysis",
            "demoCreateAnalysisQuestionnaire",
            "demoCreateSessionAnalysis",
            "demoCreateQuestionnaireRun",
            "demoCreateQuestionnaireResponse",
            "demoCompileProfile",
            "demoCompileReferenceProfile",
            "demoCompileSessionContext",
            "demoCreateStyleFeedback",
            "demoCreateConstraints",
            "demoCreateEditingSession",
            "demoCreateEditPlan",
            "demoCreateProfileGeometryPlan",
            "demoExecuteEditPlan",
            "demoAcceptEditExecutionAsReference",
            "demoCreateImageVersionFeedback",
            "demoRestoreImageVersion",
            "demoRebuildProfiles",
            "demoCancelJob",
        }
    ]
    assert len(posts) == 20
    assert all("DemoBearerAuth" in operation["security"][0] for operation in operations)
    idempotency_headers = [
        next(
            parameter
            for parameter in operation["parameters"]
            if parameter["name"] == "Idempotency-Key"
        )
        for operation in posts
    ]
    assert all(parameter["required"] is True for parameter in idempotency_headers)
    assert all(
        parameter["schema"]
        == {
            "type": "string",
            "minLength": 8,
            "maxLength": 128,
            "pattern": "^[!-~]{8,128}$",
            "title": "Idempotency-Key",
        }
        for parameter in idempotency_headers
    )
    profile_result = paths["/api/v1/demo/profiles/compilation-jobs/{job_id}/result"]["get"]
    assert "requestBody" not in profile_result
    assert {parameter["name"] for parameter in profile_result["parameters"]} == {"job_id"}
    assert profile_result["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DemoProfileCompilationJobResultResponse"
    }
    profile_result_schema = schema["components"]["schemas"][
        "DemoProfileCompilationJobResultResponse"
    ]
    assert set(profile_result_schema["required"]) == {
        "status",
        "job_id",
        "session_id",
        "profile_id",
        "job_binding_digest",
        "compilation_digest",
    }
    edit_result = paths["/api/v1/demo/edit-plans/execution-jobs/{job_id}/result"]["get"]
    assert "requestBody" not in edit_result
    assert {parameter["name"] for parameter in edit_result["parameters"]} == {"job_id"}
    assert edit_result["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DemoEditExecutionResultResponse"
    }
    edit_media = paths["/api/v1/demo/edit-plans/execution-jobs/{job_id}/media/{side}"]["get"]
    assert "requestBody" not in edit_media
    assert {parameter["name"] for parameter in edit_media["parameters"]} == {
        "job_id",
        "side",
    }
    assert edit_media["responses"]["200"]["content"]["image/jpeg"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    profile_geometry = paths[
        "/api/v1/demo/editing-sessions/{editing_session_id}/profile-geometry-plans"
    ]["post"]
    assert profile_geometry["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DemoProfileGeometryPlanRequest"
    }
    accept_reference = paths["/api/v1/demo/edit-plans/execution-jobs/{job_id}/accept-as-reference"][
        "post"
    ]
    assert accept_reference["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DemoAcceptEditExecutionAsReferenceRequest"
    }
    reference_result = paths["/api/v1/demo/reference-profiles/compilation-jobs/{job_id}/result"][
        "get"
    ]
    assert "requestBody" not in reference_result
    assert reference_result["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DemoReferenceProfileCompilationJobResultResponse"
    }
    editing_request = schema["components"]["schemas"]["DemoEditingSessionCreateRequest"]
    assert editing_request["properties"]["source_selector"]["anyOf"] == [
        {"type": "string", "const": "SESSION_CANONICAL_ASSET"},
        {"type": "null"},
    ]

    accepted_job = schema["components"]["schemas"]["DemoJobAcceptedResponse"]
    job = schema["components"]["schemas"]["DemoJobResponse"]
    target = schema["components"]["schemas"]["DemoJobTargetResponse"]
    assert {"job_id", "status", "capability", "job_binding_digest", "target"}.issubset(
        accepted_job["required"]
    )
    assert {
        "job_id",
        "status",
        "capability",
        "job_binding_digest",
        "target",
    }.issubset(job["required"])
    assert {"result_code", "finalized_at"}.issubset(job["properties"])
    assert {"target_type", "target_id", "authority_digest"} == set(target["required"])
    assert "REFERENCE_PROFILE_REQUEST" in target["properties"]["target_type"]["enum"]


def test_capabilities_report_available_and_deferred_boundaries() -> None:
    app = _app()
    app.dependency_overrides[get_demo_actor] = lambda: DemoActor(
        id="0" * 32,
        schema_version="mirror.demo/Actor/v1",
        canonical_payload={},
        content_digest="0" * 64,
        actor_kind="LOCAL_SINGLE_USER",
        credential_key_id="local",
        authority_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    client = TestClient(app)
    capabilities = client.get("/api/v1/demo/capabilities")
    assert capabilities.status_code == 200
    assert {item["status"] for item in capabilities.json()["capabilities"]} == {
        "AVAILABLE",
        "NOT_IMPLEMENTED",
        "DEFERRED_WITH_EXPLICIT_REASON",
        "CAPABILITY_UNAVAILABLE",
    }
    assert {
        item["code"]
        for item in capabilities.json()["capabilities"]
        if item["status"] == "AVAILABLE"
    } >= {
        "P3_FACE_ANALYSIS",
        "P4_QUESTIONNAIRE",
        "P5_COMPILER",
        "P5_REFERENCE_PROFILE",
        "P7_PREFERENCE_MEMORY",
    }
    with pytest.raises(ValidationError):
        DemoSessionCreateRequest.model_validate(
            {
                "synthetic_identity_id": "1" * 32,
                "context_seed": "2" * 64,
                "actor_id": "3" * 32,
            }
        )


def test_idempotency_key_rejects_non_visible_ascii_before_application_logic() -> None:
    adapter = TypeAdapter(IdempotencyKey)
    for invalid_key in ("bad key!", "abc\tdefg", "中文abcdef"):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid_key)
    assert adapter.validate_python("visible-key-~") == "visible-key-~"


def test_demo_router_denies_missing_bearer_credentials() -> None:
    client = TestClient(_app())
    response = client.get("/api/v1/demo/capabilities")
    assert response.status_code == 401
    assert response.json()["code"] == "demo_authentication_failed"


def test_frozen_demo_contracts_include_concurrency_and_quantized_authority() -> None:
    response = DemoQuestionResponseRequest(
        selected_side="INDISTINGUISHABLE",
        expected_step_sequence=3,
        expected_run_version=7,
        response_latency_ms=250,
    )
    assert response.selected_side == "INDISTINGUISHABLE"
    with pytest.raises(ValidationError):
        DemoQuestionResponseRequest.model_validate(
            {
                "selected_side": "LEFT",
                "response_latency_ms": 250,
            }
        )

    next_question = DemoQuestionNextResponse(
        kind="QUESTION",
        run_id="e" * 32,
        step_id="1" * 32,
        question_pair_id="2" * 32,
        question_pair_digest="3" * 64,
        dimension_key="jaw_width",
        magnitude_ppm=15_000,
        source_identity_id="4" * 32,
        source_asset_id="5" * 32,
        source_checksum="6" * 64,
        left={
            "result_asset_id": "7" * 32,
            "result_checksum": "8" * 64,
            "result_lineage_digest": "9" * 64,
            "requested_direction": "NEGATIVE",
            "measured_delta_ppm": -14_500,
        },
        right={
            "result_asset_id": "a" * 32,
            "result_checksum": "b" * 64,
            "result_lineage_digest": "c" * 64,
            "requested_direction": "POSITIVE",
            "measured_delta_ppm": 14_700,
        },
        routing_score_ppm=600_000,
        routing_components={
            "posterior_uncertainty_ppm": 800_000,
            "self_state_reliability_ppm": 900_000,
            "coverage_need_ppm": 1_000_000,
            "expected_fisher_information_ppm": 700_000,
            "morphology_neighborhood_compatibility_ppm": 750_000,
            "pair_quality_ppm": 950_000,
            "contradiction_priority_ppm": 500_000,
        },
        routing_evidence_digest="d" * 64,
        step_sequence=3,
        run_version=7,
    )
    assert next_question.routing_components.morphology_neighborhood_compatibility_ppm == 750_000

    assert DemoCapability(code="P3_FACE_ANALYSIS", status="AVAILABLE").status == "AVAILABLE"
    assert (
        DemoToolRunResponse(
            tool_run_id="e" * 32,
            tool_name="contrast",
            status="COMPLETED",
            output_digest="f" * 64,
        ).status
        == "COMPLETED"
    )


def test_frozen_demo_mutation_contracts_require_explicit_intent_and_preconditions() -> None:
    style_adapter = TypeAdapter[DemoStyleFeedbackRequest](DemoStyleFeedbackRequest)
    explicit_style = style_adapter.validate_python(
        {
            "event_type": "EXPLICIT_STYLE_SELECTION",
            "session_id": "1" * 32,
            "style_key": "natural",
        }
    )
    maximum_intensity = style_adapter.validate_python(
        {
            "event_type": "MAXIMUM_INTENSITY_CHANGED",
            "target_key": "geometry",
            "maximum_intensity_ppm": 300_000,
        }
    )
    assert explicit_style.event_type == "EXPLICIT_STYLE_SELECTION"
    assert maximum_intensity.event_type == "MAXIMUM_INTENSITY_CHANGED"
    with pytest.raises(ValidationError):
        style_adapter.validate_python(
            {
                "event_type": "EXPLICIT_STYLE_SELECTION",
                "style_key": "natural",
                "maximum_intensity_ppm": 300_000,
            }
        )

    assert (
        DemoImageFeedbackRequest(feedback="ACCEPT", acceptance_kind="EVENT_ONLY").acceptance_kind
        == "EVENT_ONLY"
    )
    assert (
        DemoImageFeedbackRequest(feedback="ACCEPT", acceptance_kind="FINAL_SAVE").acceptance_kind
        == "FINAL_SAVE"
    )
    assert DemoImageFeedbackRequest(feedback="REJECT").intensity_ppm is None
    assert (
        DemoImageFeedbackRequest(feedback="ADJUST", intensity_ppm=250_000).intensity_ppm == 250_000
    )
    invalid_image_feedback = (
        {"feedback": "ACCEPT"},
        {"feedback": "ACCEPT", "acceptance_kind": "FINAL_SAVE", "intensity_ppm": 1},
        {"feedback": "REJECT", "acceptance_kind": "EVENT_ONLY"},
        {"feedback": "REJECT", "intensity_ppm": 1},
        {"feedback": "ADJUST"},
        {"feedback": "ADJUST", "acceptance_kind": "EVENT_ONLY", "intensity_ppm": 1},
    )
    for invalid_payload in invalid_image_feedback:
        with pytest.raises(ValidationError):
            DemoImageFeedbackRequest.model_validate(invalid_payload)

    assert DemoJobCancelRequest(expected_status="RUNNING").reason == "USER_REQUEST"
    assert (
        DemoEditPlanExecuteRequest(
            execution_mode="GEOMETRY", expected_plan_digest="2" * 64
        ).expected_plan_digest
        == "2" * 64
    )
    restored = DemoRestoreRequest(
        expected_current_image_version_id="3" * 32,
        expected_current_image_version_digest="4" * 64,
    )
    assert restored.expected_current_image_version_id == "3" * 32

    target = {
        "target_type": "EDIT_PLAN",
        "target_id": "5" * 32,
        "authority_digest": "6" * 64,
    }
    accepted = DemoJobAcceptedResponse(
        job_id="7" * 32,
        status="PENDING",
        capability="edit_plan",
        job_binding_digest="8" * 64,
        target=target,
    )
    completed = DemoJobResponse(
        job_id=accepted.job_id,
        status="COMPLETED",
        capability=accepted.capability,
        job_binding_digest=accepted.job_binding_digest,
        target=target,
    )
    assert completed.target.target_id == accepted.target.target_id
    assert completed.target.authority_digest == "6" * 64


def test_main_application_exposes_the_complete_demo_contract() -> None:
    schema = create_app().openapi()
    paths = [path for path in schema["paths"] if path.startswith("/api/v1/demo")]
    assert len(paths) == 35
    assert schema["paths"]["/api/v1/demo/jobs/{job_id}/cancel"]["post"]["requestBody"]
    assert schema["paths"]["/api/v1/demo/reference-profiles/compile"]["post"]["requestBody"]
    assert schema["paths"]["/api/v1/demo/sessions/{session_id}/context/compile"]["post"][
        "requestBody"
    ]
    assert (
        "requestBody" not in schema["paths"]["/api/v1/demo/sessions/{session_id}/analysis"]["post"]
    )
    assert (
        "requestBody"
        not in schema["paths"]["/api/v1/demo/analyses/{analysis_id}/questionnaire"]["post"]
    )
    media = schema["paths"]["/api/v1/demo/questionnaires/runs/{run_id}/presentation-media/{side}"][
        "get"
    ]
    assert media["responses"]["200"]["content"]["image/jpeg"]["schema"] == {
        "type": "string",
        "format": "binary",
    }


def test_demo_bearer_keyring_rejects_ambiguous_digest_authority() -> None:
    with pytest.raises(ValidationError, match="digests must be unique"):
        Settings(
            demo_bearer_token_sha256_by_key_id={
                "first": "1" * 64,
                "second": "1" * 64,
            }
        )
