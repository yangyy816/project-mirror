from __future__ import annotations

from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Depends, Header, status

from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_schemas import (
    DemoActiveProfilesResponse,
    DemoAnalysisCreateRequest,
    DemoAnalysisResponse,
    DemoCapabilitiesResponse,
    DemoCapability,
    DemoConstraintsCreateRequest,
    DemoContextResponse,
    DemoEditingSessionCreateRequest,
    DemoEditPlanCreateRequest,
    DemoEditPlanExecuteRequest,
    DemoId,
    DemoIdentityConstraintsResponse,
    DemoIdentityListResponse,
    DemoImageFeedbackRequest,
    DemoJobAcceptedResponse,
    DemoJobCancelRequest,
    DemoJobResponse,
    DemoPreferenceEventResponse,
    DemoProfileCompileRequest,
    DemoProfileRebuildRequest,
    DemoQuestionnaireNextResponse,
    DemoQuestionnaireRunCreateRequest,
    DemoQuestionnaireStepResponse,
    DemoQuestionResponseRequest,
    DemoRestoreRequest,
    DemoSessionCreateRequest,
    DemoSessionResponse,
    DemoStyleFeedbackRequest,
    DemoToolRunResponse,
    DemoTraceResponse,
)
from mirror_api.errors import APIError, ErrorEnvelope

router = APIRouter(
    prefix="/api/v1/demo",
    tags=["demo-prototype"],
    dependencies=[Depends(get_demo_actor)],
)
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
DEMO_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    501: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
}
DEMO_OPENAPI = {"x-demo-only": True}


def _not_implemented(capability: str, owner_task: str) -> NoReturn:
    raise APIError(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        code="CAPABILITY_NOT_IMPLEMENTED",
        message="Demo 原型能力尚未实现。",
        details={
            "track": "DEMO_PROTOTYPE",
            "capability": capability,
            "owner_task": owner_task,
        },
    )


@router.get(
    "/capabilities",
    response_model=DemoCapabilitiesResponse,
    operation_id="demoGetCapabilities",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_capabilities() -> DemoCapabilitiesResponse:
    return DemoCapabilitiesResponse(
        capabilities=[
            DemoCapability(code="P3_FACE_ANALYSIS", status="NOT_IMPLEMENTED"),
            DemoCapability(code="P4_QUESTIONNAIRE", status="NOT_IMPLEMENTED"),
            DemoCapability(code="P5_COMPILER", status="NOT_IMPLEMENTED"),
            DemoCapability(code="P6_DETERMINISTIC_RASTER", status="NOT_IMPLEMENTED"),
            DemoCapability(code="P6_GEOMETRY", status="NOT_IMPLEMENTED"),
            DemoCapability(
                code="P6_MAKEUP",
                status="DEFERRED_WITH_EXPLICIT_REASON",
                reason="Makeup transfer remains deferred pending its dedicated research gate.",
            ),
            DemoCapability(code="P6_GENERATIVE_EDITOR", status="CAPABILITY_UNAVAILABLE"),
            DemoCapability(code="P7_PREFERENCE_MEMORY", status="NOT_IMPLEMENTED"),
        ]
    )


@router.post(
    "/sessions",
    status_code=201,
    response_model=DemoSessionResponse,
    operation_id="demoCreateSession",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_session(
    payload: DemoSessionCreateRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("demo_session", "D02")


@router.get(
    "/sessions/{session_id}/context",
    response_model=DemoContextResponse,
    operation_id="demoGetSessionContext",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_session_context(session_id: DemoId) -> NoReturn:
    del session_id
    _not_implemented("context_compile", "D10")


@router.get(
    "/identities",
    response_model=DemoIdentityListResponse,
    operation_id="demoListIdentities",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def list_identities() -> NoReturn:
    _not_implemented("synthetic_identity", "D02")


@router.post(
    "/analyses",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateAnalysis",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_analysis(
    payload: DemoAnalysisCreateRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("face_analysis", "D03")


@router.get(
    "/analyses/{analysis_id}",
    response_model=DemoAnalysisResponse,
    operation_id="demoGetAnalysis",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_analysis(analysis_id: DemoId) -> NoReturn:
    del analysis_id
    _not_implemented("face_analysis", "D03")


@router.post(
    "/questionnaires/runs",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateQuestionnaireRun",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_questionnaire_run(
    payload: DemoQuestionnaireRunCreateRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("questionnaire", "D04")


@router.get(
    "/questionnaires/runs/{run_id}/next",
    response_model=DemoQuestionnaireNextResponse,
    operation_id="demoGetQuestionnaireNext",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_questionnaire_next(run_id: DemoId) -> NoReturn:
    del run_id
    _not_implemented("questionnaire", "D04")


@router.post(
    "/questionnaires/runs/{run_id}/responses",
    status_code=201,
    response_model=DemoQuestionnaireStepResponse,
    operation_id="demoCreateQuestionnaireResponse",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_questionnaire_response(
    run_id: DemoId, payload: DemoQuestionResponseRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del run_id, payload, idempotency_key
    _not_implemented("questionnaire", "D04")


@router.post(
    "/profiles/compile",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCompileProfile",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def compile_profile(
    payload: DemoProfileCompileRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("profile_compile", "D05")


@router.get(
    "/profiles/active",
    response_model=DemoActiveProfilesResponse,
    operation_id="demoGetActiveProfiles",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_active_profiles() -> NoReturn:
    _not_implemented("profile_compile", "D05")


@router.post(
    "/style-feedback",
    status_code=201,
    response_model=DemoPreferenceEventResponse,
    operation_id="demoCreateStyleFeedback",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_style_feedback(
    payload: DemoStyleFeedbackRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("preference_memory", "D09")


@router.post(
    "/constraints",
    status_code=201,
    response_model=DemoIdentityConstraintsResponse,
    operation_id="demoCreateConstraints",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_constraints(
    payload: DemoConstraintsCreateRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("identity_constraints", "D05")


@router.post(
    "/editing-sessions",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateEditingSession",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_editing_session(
    payload: DemoEditingSessionCreateRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("editing_session", "D07")


@router.post(
    "/editing-sessions/{editing_session_id}/plans",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateEditPlan",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_edit_plan(
    editing_session_id: DemoId, payload: DemoEditPlanCreateRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del editing_session_id, payload, idempotency_key
    _not_implemented("edit_plan", "D07")


@router.post(
    "/edit-plans/{edit_plan_id}/executions",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoExecuteEditPlan",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def execute_edit_plan(
    edit_plan_id: DemoId, payload: DemoEditPlanExecuteRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del edit_plan_id, payload, idempotency_key
    _not_implemented("edit_execution", "D07")


@router.get(
    "/tool-runs/{tool_run_id}",
    response_model=DemoToolRunResponse,
    operation_id="demoGetToolRun",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_tool_run(tool_run_id: DemoId) -> NoReturn:
    del tool_run_id
    _not_implemented("tool_run", "D07")


@router.post(
    "/image-versions/{image_version_id}/feedback",
    status_code=201,
    response_model=DemoPreferenceEventResponse,
    operation_id="demoCreateImageVersionFeedback",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_image_version_feedback(
    image_version_id: DemoId, payload: DemoImageFeedbackRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del image_version_id, payload, idempotency_key
    _not_implemented("image_feedback", "D09")


@router.post(
    "/image-versions/{image_version_id}/restore",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoRestoreImageVersion",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def restore_image_version(
    image_version_id: DemoId, payload: DemoRestoreRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del image_version_id, payload, idempotency_key
    _not_implemented("image_restore", "D07")


@router.post(
    "/profiles/rebuild",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoRebuildProfiles",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def rebuild_profiles(
    payload: DemoProfileRebuildRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del payload, idempotency_key
    _not_implemented("profile_rebuild", "D10")


@router.get(
    "/traces/{session_id}",
    response_model=DemoTraceResponse,
    operation_id="demoGetTrace",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_trace(session_id: DemoId) -> NoReturn:
    del session_id
    _not_implemented("context_trace", "D10")


@router.get(
    "/jobs/{job_id}",
    response_model=DemoJobResponse,
    operation_id="demoGetJob",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_job(job_id: DemoId) -> NoReturn:
    del job_id
    _not_implemented("job_status", "D01-C")


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=DemoJobResponse,
    operation_id="demoCancelJob",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def cancel_job(
    job_id: DemoId, payload: DemoJobCancelRequest, idempotency_key: IdempotencyKey
) -> NoReturn:
    del job_id, payload, idempotency_key
    _not_implemented("job_cancel", "D01-C")
