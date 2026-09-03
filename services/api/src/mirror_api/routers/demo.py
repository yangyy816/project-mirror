from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, NoReturn, cast

from fastapi import APIRouter, Depends, Header, Request, Response, status

from mirror_api.demo_analysis_coordinator import DemoAnalysisCoordinator
from mirror_api.demo_analysis_dependencies import (
    get_demo_analysis_coordinator,
    get_demo_job_service,
)
from mirror_api.demo_analysis_service import (
    CreateDemoAnalysis,
    CreateDemoSessionAnalysis,
    DemoAnalysisAuthorityCorruption,
    DemoAnalysisInputError,
    DemoAnalysisPayloadConflict,
    DemoAnalysisUnavailable,
)
from mirror_api.demo_context_coordinator import DemoContextCoordinator
from mirror_api.demo_context_dependencies import get_demo_context_coordinator
from mirror_api.demo_context_queue_service import (
    CreateDemoContextCompilation,
    DemoContextQueueAuthorityCorruption,
    DemoContextQueueConflict,
    DemoContextQueueInputError,
    DemoContextQueueUnavailable,
)
from mirror_api.demo_dependencies import get_demo_actor, get_demo_session_service
from mirror_api.demo_editing_commands import (
    CreateDemoEditingSession,
    CreateDemoEditPlan,
    DemoEditingCommandAuthorityCorruption,
    DemoEditingCommandInputError,
    DemoEditingCommandUnavailable,
    ExecuteDemoEditPlan,
    RestoreDemoImageVersion,
)
from mirror_api.demo_editing_coordinator import DemoEditingCoordinator
from mirror_api.demo_editing_dependencies import get_demo_editing_coordinator
from mirror_api.demo_idempotency import (
    DemoIdempotencyAuthorityCorruption,
    DemoIdempotencyInputError,
    DemoIdempotencyPayloadConflict,
)
from mirror_api.demo_image_feedback_dependencies import (
    get_demo_image_feedback_service,
)
from mirror_api.demo_image_feedback_service import (
    CreateDemoImageFeedback,
    DemoImageFeedbackAuthorityCorruption,
    DemoImageFeedbackConflict,
    DemoImageFeedbackInputError,
    DemoImageFeedbackService,
    DemoImageFeedbackUnavailable,
)
from mirror_api.demo_job_service import (
    DemoJobAuthorityCorruption,
    DemoJobInputError,
    DemoJobService,
    DemoJobSnapshot,
    DemoJobStateConflict,
    DemoJobStatus,
    DemoJobUnavailable,
)
from mirror_api.demo_memory_coordinator import DemoMemoryCoordinator
from mirror_api.demo_memory_dependencies import (
    get_demo_memory_coordinator,
    get_demo_memory_service,
)
from mirror_api.demo_memory_service import (
    DemoMemoryAuthorityCorruption,
    DemoMemoryConflict,
    DemoMemoryInputError,
    DemoMemoryService,
    DemoMemoryUnavailable,
    RebuildDemoAestheticProfile,
)
from mirror_api.demo_models import DemoActor
from mirror_api.demo_operation_graph import OperationType
from mirror_api.demo_posterior import PairwiseChoice
from mirror_api.demo_preference_ledger import (
    DemoPreferenceActorUnavailable,
    DemoPreferenceLedgerCorruption,
    DemoPreferenceLedgerInputError,
    DemoPreferenceSessionUnavailable,
)
from mirror_api.demo_profile_commands import (
    CreateDemoConstraints,
    CreateDemoProfileCompilation,
    CreateDemoStyleFeedback,
    DemoConstraintLockCommand,
    DemoProfileCommandAuthorityCorruption,
    DemoProfileCommandInputError,
    DemoProfileCommandService,
    DemoProfileCommandUnavailable,
)
from mirror_api.demo_profile_coordinator import DemoProfileCoordinator
from mirror_api.demo_profile_dependencies import (
    get_demo_profile_commands,
    get_demo_profile_coordinator,
)
from mirror_api.demo_questionnaire_dependencies import (
    get_demo_questionnaire_media_service,
    get_demo_questionnaire_service,
)
from mirror_api.demo_questionnaire_media import (
    DemoQuestionnaireMediaAuthorityCorruption,
    DemoQuestionnaireMediaBytesUnavailable,
    DemoQuestionnaireMediaInputError,
    DemoQuestionnaireMediaService,
    DemoQuestionnaireMediaUnavailable,
)
from mirror_api.demo_questionnaire_service import (
    CreateDemoAnalysisQuestionnaireRun,
    CreateDemoQuestionnaireResponse,
    CreateDemoQuestionnaireRun,
    DemoQuestionnaireAuthorityCorruption,
    DemoQuestionnaireCompleted,
    DemoQuestionnaireConflict,
    DemoQuestionnaireInputError,
    DemoQuestionnaireNext,
    DemoQuestionnairePayloadConflict,
    DemoQuestionnaireService,
    DemoQuestionnaireUnavailable,
)
from mirror_api.demo_reference_profile_coordinator import DemoReferenceProfileCoordinator
from mirror_api.demo_reference_profile_dependencies import (
    get_demo_reference_profile_coordinator,
    get_demo_reference_profile_service,
)
from mirror_api.demo_reference_profile_service import (
    CreateDemoReferenceProfileCompilation,
    DemoReferenceProfileAuthorityCorruption,
    DemoReferenceProfileConflict,
    DemoReferenceProfileInputError,
    DemoReferenceProfileService,
    DemoReferenceProfileUnavailable,
)
from mirror_api.demo_schemas import (
    DemoActiveProfilesResponse,
    DemoActiveReferenceProfilesResponse,
    DemoAnalysisCreateRequest,
    DemoAnalysisResponse,
    DemoCapabilitiesResponse,
    DemoCapability,
    DemoConstraintsCreateRequest,
    DemoContextCompileRequest,
    DemoContextResponse,
    DemoEditingSessionCreateRequest,
    DemoEditPlanCreateRequest,
    DemoEditPlanExecuteRequest,
    DemoId,
    DemoIdentityConstraintsResponse,
    DemoIdentityListResponse,
    DemoIdentityResponse,
    DemoImageFeedbackRequest,
    DemoJobAcceptedResponse,
    DemoJobCancelRequest,
    DemoJobResponse,
    DemoPreferenceEventResponse,
    DemoProfileCompileRequest,
    DemoProfileRebuildRequest,
    DemoProfileResponse,
    DemoQuestionCompletedResponse,
    DemoQuestionnaireNextResponse,
    DemoQuestionnaireRunCreateRequest,
    DemoQuestionnaireStepResponse,
    DemoQuestionNextResponse,
    DemoQuestionResponseRequest,
    DemoQuestionSideResponse,
    DemoReferenceProfileCompileRequest,
    DemoReferenceProfileResponse,
    DemoRestoreRequest,
    DemoRoutingComponents,
    DemoSessionCreateRequest,
    DemoSessionResponse,
    DemoStyleFeedbackRequest,
    DemoToolRunResponse,
    DemoTraceResponse,
)
from mirror_api.demo_self_transfer_service import DemoReferenceSource
from mirror_api.demo_session_service import (
    CreateDemoSession,
    DemoSessionActorUnavailable,
    DemoSessionAuthorityUnavailable,
    DemoSessionInputError,
    DemoSessionPayloadConflict,
    DemoSessionService,
    DemoSyntheticIdentityUnavailable,
)
from mirror_api.errors import APIError, ErrorEnvelope

router = APIRouter(
    prefix="/api/v1/demo",
    tags=["demo-prototype"],
    dependencies=[Depends(get_demo_actor)],
)
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[!-~]{8,128}$",
    ),
]
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


def _raise_session_error(error: Exception, *, identity_read: bool = False) -> NoReturn:
    if isinstance(error, DemoSessionPayloadConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的 Demo 会话请求。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoSessionInputError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_SESSION_REQUEST_INVALID",
            message="Demo 会话请求不符合约束。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoSessionActorUnavailable):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="demo_authentication_failed",
            message="Demo 凭据无效或已失效。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoSyntheticIdentityUnavailable):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_SYNTHETIC_IDENTITY_UNAVAILABLE",
            message="指定的合成身份当前不可用于 Demo。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoSessionAuthorityUnavailable):
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=(
                "DEMO_SYNTHETIC_IDENTITY_AUTHORITY_UNAVAILABLE"
                if identity_read
                else "DEMO_SESSION_AUTHORITY_UNAVAILABLE"
            ),
            message="Demo 会话 authority 当前不可用。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise error


def _job_target(snapshot: DemoJobSnapshot) -> dict[str, str]:
    return {
        "target_type": snapshot.target.target_type,
        "target_id": snapshot.target.target_id,
        "authority_digest": snapshot.target.authority_digest,
    }


def _job_response(snapshot: DemoJobSnapshot) -> DemoJobResponse:
    return DemoJobResponse(
        job_id=snapshot.job_id,
        status=snapshot.status,
        capability=snapshot.capability,
        job_binding_digest=snapshot.job_binding_digest,
        target=_job_target(snapshot),
        result_code=snapshot.result_code,
        finalized_at=snapshot.finalized_at,
    )


def _job_accepted(snapshot: DemoJobSnapshot) -> DemoJobAcceptedResponse:
    return DemoJobAcceptedResponse(
        job_id=snapshot.job_id,
        status="PENDING",
        capability=snapshot.capability,
        job_binding_digest=snapshot.job_binding_digest,
        target=_job_target(snapshot),
    )


def _raise_analysis_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoAnalysisPayloadConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的分析请求。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoAnalysisInputError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_ANALYSIS_REQUEST_INVALID",
            message="分析请求不符合 Demo authority 约束。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoAnalysisUnavailable):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_ANALYSIS_UNAVAILABLE",
            message="分析任务不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_ANALYSIS_AUTHORITY_UNAVAILABLE",
        message="分析 authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_job_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoIdempotencyPayloadConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的 Job 命令。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoJobStateConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="DEMO_JOB_STATE_CONFLICT",
            message="Job 当前状态不允许该操作。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoJobInputError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_JOB_REQUEST_INVALID",
            message="Job 命令不符合 Demo contract。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoJobUnavailable):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_JOB_UNAVAILABLE",
            message="Job 不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_JOB_AUTHORITY_UNAVAILABLE",
        message="Job authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_questionnaire_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoQuestionnairePayloadConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的问卷请求。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoQuestionnaireConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="DEMO_QUESTIONNAIRE_STATE_CONFLICT",
            message="问卷状态已变化，不能应用当前操作。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoQuestionnaireInputError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_QUESTIONNAIRE_REQUEST_INVALID",
            message="问卷请求不符合 Demo authority 约束。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoQuestionnaireUnavailable):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_QUESTIONNAIRE_UNAVAILABLE",
            message="问卷资源不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_QUESTIONNAIRE_AUTHORITY_UNAVAILABLE",
        message="问卷 authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_questionnaire_media_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoQuestionnaireMediaInputError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_QUESTIONNAIRE_MEDIA_REQUEST_INVALID",
            message="问卷图片请求不符合 Demo contract。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoQuestionnaireMediaUnavailable):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_QUESTIONNAIRE_MEDIA_UNAVAILABLE",
            message="问卷图片不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_QUESTIONNAIRE_MEDIA_AUTHORITY_UNAVAILABLE",
        message="问卷图片 authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_profile_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoIdempotencyPayloadConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的 Profile 命令。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(
        error,
        (
            DemoProfileCommandInputError,
            DemoIdempotencyInputError,
            DemoPreferenceLedgerInputError,
        ),
    ):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_PROFILE_REQUEST_INVALID",
            message="Profile 命令不符合 Demo authority 约束。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(
        error,
        (
            DemoProfileCommandUnavailable,
            DemoPreferenceActorUnavailable,
            DemoPreferenceSessionUnavailable,
            DemoJobUnavailable,
        ),
    ):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_PROFILE_AUTHORITY_UNAVAILABLE",
            message="Profile authority 不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_PROFILE_AUTHORITY_CORRUPT",
        message="Profile authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_reference_profile_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoReferenceProfileConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code=error.code,
            message="Reference Profile 请求与既有不可变 authority 冲突。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoReferenceProfileInputError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=error.code,
            message="Reference Profile 请求不符合 Demo contract。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, (DemoReferenceProfileUnavailable, DemoJobUnavailable)):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_REFERENCE_PROFILE_UNAVAILABLE",
            message="Reference Profile authority 不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_REFERENCE_PROFILE_AUTHORITY_CORRUPT",
        message="Reference Profile authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_memory_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoMemoryConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的 Profile rebuild 请求。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, (DemoMemoryInputError, DemoIdempotencyInputError)):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_MEMORY_REQUEST_INVALID",
            message="Memory rebuild 请求不符合 Demo authority 约束。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, (DemoMemoryUnavailable, DemoJobUnavailable)):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_MEMORY_AUTHORITY_UNAVAILABLE",
            message="Memory authority 不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_MEMORY_AUTHORITY_CORRUPT",
        message="Memory authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_context_queue_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoContextQueueConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code=error.code,
            message="Context 编译请求与既有不可变 authority 冲突。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoContextQueueInputError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=error.code,
            message="Context 编译请求不符合 Demo contract。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, (DemoContextQueueUnavailable, DemoJobUnavailable)):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_CONTEXT_AUTHORITY_UNAVAILABLE",
            message="Context authority 不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, (DemoContextQueueAuthorityCorruption, DemoJobAuthorityCorruption)):
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DEMO_CONTEXT_AUTHORITY_CORRUPT",
            message="Context authority 无法安全读取。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise error


def _raise_editing_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoIdempotencyPayloadConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的编辑命令。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, (DemoEditingCommandInputError, DemoIdempotencyInputError)):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_EDITING_REQUEST_INVALID",
            message="编辑命令不符合 Demo authority 约束。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, (DemoEditingCommandUnavailable, DemoJobUnavailable)):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_EDITING_AUTHORITY_UNAVAILABLE",
            message="编辑 authority 不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_EDITING_AUTHORITY_CORRUPT",
        message="编辑 authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _raise_image_feedback_error(error: Exception) -> NoReturn:
    if isinstance(error, DemoIdempotencyPayloadConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
            message="幂等键已绑定到不同的图片反馈命令。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(error, DemoImageFeedbackConflict):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="DEMO_IMAGE_FEEDBACK_STATE_CONFLICT",
            message="当前图片版本状态不允许该反馈操作。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(
        error,
        (
            DemoImageFeedbackInputError,
            DemoIdempotencyInputError,
            DemoPreferenceLedgerInputError,
        ),
    ):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="DEMO_IMAGE_FEEDBACK_REQUEST_INVALID",
            message="图片反馈请求不符合 Demo authority 约束。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    if isinstance(
        error,
        (
            DemoImageFeedbackUnavailable,
            DemoPreferenceActorUnavailable,
            DemoPreferenceSessionUnavailable,
        ),
    ):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DEMO_IMAGE_VERSION_UNAVAILABLE",
            message="图片版本不存在或当前 actor 无权访问。",
            details={"track": "DEMO_PROTOTYPE"},
        ) from error
    raise APIError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DEMO_IMAGE_FEEDBACK_AUTHORITY_CORRUPT",
        message="图片反馈 authority 无法安全读取。",
        details={"track": "DEMO_PROTOTYPE"},
    ) from error


def _questionnaire_next_response(
    result: DemoQuestionnaireNext | DemoQuestionnaireCompleted,
) -> DemoQuestionnaireNextResponse:
    if isinstance(result, DemoQuestionnaireCompleted):
        return DemoQuestionCompletedResponse(
            kind="COMPLETED",
            run_id=result.questionnaire_run_id,
            completed_at=result.completed_at,
        )
    presentation = result.presentation
    return DemoQuestionNextResponse(
        kind="QUESTION",
        step_id=result.snapshot.step_id,
        question_pair_id=result.question_pair_id,
        question_pair_digest=presentation.question_pair_digest,
        dimension_key=result.dimension_key,
        magnitude_ppm=result.magnitude_ppm,
        source_identity_id=result.source_identity_id,
        source_asset_id=presentation.source_asset_id,
        source_checksum=presentation.source_checksum,
        left=DemoQuestionSideResponse(
            result_asset_id=presentation.left.result_asset_id,
            result_checksum=presentation.left.result_checksum,
            result_lineage_digest=presentation.left.result_lineage_digest,
            requested_direction=presentation.left.requested_direction,
            measured_delta_ppm=presentation.left.measured_delta_ppm,
        ),
        right=DemoQuestionSideResponse(
            result_asset_id=presentation.right.result_asset_id,
            result_checksum=presentation.right.result_checksum,
            result_lineage_digest=presentation.right.result_lineage_digest,
            requested_direction=presentation.right.requested_direction,
            measured_delta_ppm=presentation.right.measured_delta_ppm,
        ),
        routing_score_ppm=result.routing_score_ppm,
        routing_components=DemoRoutingComponents(**dict(result.routing_components)),
        routing_evidence_digest=result.routing_evidence_digest,
        step_sequence=result.snapshot.step_sequence,
        run_version=result.snapshot.run_version,
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
            DemoCapability(code="P5_COMPILER", status="AVAILABLE"),
            DemoCapability(code="P5_REFERENCE_PROFILE", status="AVAILABLE"),
            DemoCapability(code="P6_DETERMINISTIC_RASTER", status="NOT_IMPLEMENTED"),
            DemoCapability(code="P6_GEOMETRY", status="NOT_IMPLEMENTED"),
            DemoCapability(
                code="P6_MAKEUP",
                status="DEFERRED_WITH_EXPLICIT_REASON",
                reason="Makeup transfer remains deferred pending its dedicated research gate.",
            ),
            DemoCapability(code="P6_GENERATIVE_EDITOR", status="CAPABILITY_UNAVAILABLE"),
            DemoCapability(code="P7_PREFERENCE_MEMORY", status="AVAILABLE"),
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
    payload: DemoSessionCreateRequest,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    service: DemoSessionService = Depends(get_demo_session_service),
) -> DemoSessionResponse:
    try:
        snapshot = await service.create(
            CreateDemoSession(
                demo_actor_id=actor.id,
                synthetic_identity_id=payload.synthetic_identity_id,
                context_seed=payload.context_seed,
                idempotency_key=idempotency_key,
            )
        )
    except (
        DemoSessionActorUnavailable,
        DemoSessionAuthorityUnavailable,
        DemoSessionInputError,
        DemoSessionPayloadConflict,
        DemoSyntheticIdentityUnavailable,
    ) as exc:
        _raise_session_error(exc)
    return DemoSessionResponse(
        session_id=snapshot.session_id,
        synthetic_identity_id=snapshot.synthetic_identity_id,
        status=snapshot.status,
        expires_at=snapshot.expires_at,
    )


@router.get(
    "/sessions/{session_id}/context",
    response_model=DemoContextResponse,
    operation_id="demoGetSessionContext",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_session_context(
    session_id: DemoId,
    recall_at: datetime,
    actor: DemoActor = Depends(get_demo_actor),
    memory: DemoMemoryService = Depends(get_demo_memory_service),
) -> DemoContextResponse:
    try:
        recalled = await memory.recall_context(
            demo_actor_id=actor.id,
            demo_session_id=session_id,
            recall_at=recall_at,
        )
    except (
        DemoMemoryInputError,
        DemoMemoryUnavailable,
        DemoMemoryAuthorityCorruption,
    ) as exc:
        _raise_memory_error(exc)
    return DemoContextResponse(
        session_id=session_id,
        profile_id=recalled.aesthetic_profile_id,
        compilation_digest=recalled.context_digest,
        expires_at=recalled.expires_at,
    )


@router.post(
    "/sessions/{session_id}/context/compile",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCompileSessionContext",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def compile_session_context(
    session_id: DemoId,
    payload: DemoContextCompileRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoContextCoordinator = Depends(get_demo_context_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create(
            CreateDemoContextCompilation(
                demo_actor_id=actor.id,
                demo_session_id=session_id,
                aesthetic_profile_id=payload.aesthetic_profile_id,
                current_instruction_digest=payload.current_instruction_digest,
                context_as_of_time=payload.context_as_of_time,
                compiler_version=payload.compiler_version,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoContextQueueInputError,
        DemoContextQueueUnavailable,
        DemoContextQueueConflict,
        DemoContextQueueAuthorityCorruption,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_context_queue_error(exc)
    return _job_accepted(result.job)


@router.get(
    "/identities",
    response_model=DemoIdentityListResponse,
    operation_id="demoListIdentities",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def list_identities(
    actor: DemoActor = Depends(get_demo_actor),
    service: DemoSessionService = Depends(get_demo_session_service),
) -> DemoIdentityListResponse:
    try:
        identities = await service.list_identities(demo_actor_id=actor.id)
    except (
        DemoSessionActorUnavailable,
        DemoSessionAuthorityUnavailable,
        DemoSessionInputError,
        DemoSyntheticIdentityUnavailable,
    ) as exc:
        _raise_session_error(exc, identity_read=True)
    return DemoIdentityListResponse(
        identities=[
            DemoIdentityResponse(
                identity_id=item.identity_id,
                canonical_asset_digest=item.canonical_asset_digest,
                admission_status=item.admission_status,
            )
            for item in identities
        ]
    )


@router.post(
    "/analyses",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateAnalysis",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_analysis(
    payload: DemoAnalysisCreateRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoAnalysisCoordinator = Depends(get_demo_analysis_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create(
            CreateDemoAnalysis(
                demo_actor_id=actor.id,
                demo_session_id=payload.session_id,
                source_asset_id=payload.source_asset_id,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoAnalysisInputError,
        DemoAnalysisPayloadConflict,
        DemoAnalysisUnavailable,
        DemoAnalysisAuthorityCorruption,
    ) as exc:
        _raise_analysis_error(exc)
    return _job_accepted(result.job)


@router.post(
    "/sessions/{session_id}/analysis",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateSessionAnalysis",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_session_analysis(
    session_id: DemoId,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoAnalysisCoordinator = Depends(get_demo_analysis_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create_for_session(
            CreateDemoSessionAnalysis(
                demo_actor_id=actor.id,
                demo_session_id=session_id,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoAnalysisInputError,
        DemoAnalysisPayloadConflict,
        DemoAnalysisUnavailable,
        DemoAnalysisAuthorityCorruption,
    ) as exc:
        _raise_analysis_error(exc)
    return _job_accepted(result.job)


@router.get(
    "/analyses/{analysis_id}",
    response_model=DemoAnalysisResponse,
    operation_id="demoGetAnalysis",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_analysis(
    analysis_id: DemoId,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoAnalysisCoordinator = Depends(get_demo_analysis_coordinator),
) -> DemoAnalysisResponse:
    try:
        job, observation_id, observation_digest, self_state_id = await coordinator.snapshot(
            demo_actor_id=actor.id,
            analysis_run_id=analysis_id,
        )
    except (
        DemoAnalysisInputError,
        DemoAnalysisUnavailable,
        DemoAnalysisAuthorityCorruption,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        if isinstance(exc, (DemoJobUnavailable, DemoJobAuthorityCorruption)):
            _raise_job_error(exc)
        _raise_analysis_error(exc)
    if job.status in {"PENDING", "RUNNING"}:
        return DemoAnalysisResponse(
            analysis_id=analysis_id,
            session_id=job.demo_session_id,
            state="PENDING",
            self_state_id=None,
        )
    if job.status == "COMPLETED":
        if (
            job.result_code not in {"SUPPORTED", "UNSUPPORTED"}
            or observation_id is None
            or observation_digest is None
            or self_state_id is None
            or job.demo_session_id is None
        ):
            _raise_analysis_error(
                DemoAnalysisAuthorityCorruption(
                    "completed analysis lacks final observation authority"
                )
            )
        return DemoAnalysisResponse(
            analysis_id=analysis_id,
            session_id=job.demo_session_id,
            state=job.result_code,
            observation_digest=observation_digest,
            self_state_id=self_state_id,
        )
    raise APIError(
        status_code=status.HTTP_409_CONFLICT,
        code=f"DEMO_ANALYSIS_{job.status}",
        message="分析任务已终止，未产生可发布 observation。",
        details={
            "track": "DEMO_PROTOTYPE",
            "job_id": job.job_id,
            "result_code": job.result_code,
        },
    )


@router.post(
    "/analyses/{analysis_id}/questionnaire",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateAnalysisQuestionnaire",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_analysis_questionnaire(
    analysis_id: DemoId,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    questionnaires: DemoQuestionnaireService = Depends(get_demo_questionnaire_service),
    jobs: DemoJobService = Depends(get_demo_job_service),
) -> DemoJobAcceptedResponse:
    try:
        accepted = await questionnaires.create_for_analysis(
            CreateDemoAnalysisQuestionnaireRun(
                demo_actor_id=actor.id,
                analysis_run_id=analysis_id,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
        job = await jobs.get(demo_actor_id=actor.id, job_id=accepted.job_id)
    except (
        DemoQuestionnaireInputError,
        DemoQuestionnaireUnavailable,
        DemoQuestionnaireConflict,
        DemoQuestionnairePayloadConflict,
        DemoQuestionnaireAuthorityCorruption,
    ) as exc:
        _raise_questionnaire_error(exc)
    except (DemoJobUnavailable, DemoJobAuthorityCorruption) as exc:
        _raise_job_error(exc)
    return _job_accepted(job)


@router.post(
    "/questionnaires/runs",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateQuestionnaireRun",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_questionnaire_run(
    payload: DemoQuestionnaireRunCreateRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    questionnaires: DemoQuestionnaireService = Depends(get_demo_questionnaire_service),
    jobs: DemoJobService = Depends(get_demo_job_service),
) -> DemoJobAcceptedResponse:
    try:
        accepted = await questionnaires.create(
            CreateDemoQuestionnaireRun(
                demo_actor_id=actor.id,
                demo_session_id=payload.session_id,
                self_state_id=payload.self_state_id,
                question_bank_version=payload.question_bank_version,
                max_questions=payload.max_questions,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
        job = await jobs.get(demo_actor_id=actor.id, job_id=accepted.job_id)
    except (
        DemoQuestionnaireInputError,
        DemoQuestionnaireUnavailable,
        DemoQuestionnaireConflict,
        DemoQuestionnairePayloadConflict,
        DemoQuestionnaireAuthorityCorruption,
    ) as exc:
        _raise_questionnaire_error(exc)
    except (DemoJobUnavailable, DemoJobAuthorityCorruption) as exc:
        _raise_job_error(exc)
    return _job_accepted(job)


@router.get(
    "/questionnaires/runs/{run_id}/next",
    response_model=DemoQuestionnaireNextResponse,
    operation_id="demoGetQuestionnaireNext",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_questionnaire_next(
    run_id: DemoId,
    actor: DemoActor = Depends(get_demo_actor),
    questionnaires: DemoQuestionnaireService = Depends(get_demo_questionnaire_service),
) -> DemoQuestionnaireNextResponse:
    try:
        return _questionnaire_next_response(
            await questionnaires.next(
                demo_actor_id=actor.id,
                questionnaire_run_id=run_id,
            )
        )
    except (
        DemoQuestionnaireInputError,
        DemoQuestionnaireUnavailable,
        DemoQuestionnaireConflict,
        DemoQuestionnaireAuthorityCorruption,
    ) as exc:
        _raise_questionnaire_error(exc)


@router.get(
    "/questionnaires/runs/{run_id}/presentation-media/{side}",
    response_class=Response,
    operation_id="demoGetQuestionnairePresentationMedia",
    openapi_extra=DEMO_OPENAPI,
    responses={
        **DEMO_ERRORS,
        200: {
            "description": "Current owner-bound synthetic questionnaire side.",
            "content": {
                "image/jpeg": {
                    "schema": {"type": "string", "format": "binary"},
                }
            },
        },
    },
)
async def get_questionnaire_presentation_media(
    run_id: DemoId,
    side: Literal["LEFT", "RIGHT"],
    actor: DemoActor = Depends(get_demo_actor),
    media_service: DemoQuestionnaireMediaService = Depends(get_demo_questionnaire_media_service),
) -> Response:
    try:
        media = await media_service.load(
            demo_actor_id=actor.id,
            questionnaire_run_id=run_id,
            side=side,
        )
    except (
        DemoQuestionnaireMediaInputError,
        DemoQuestionnaireMediaUnavailable,
        DemoQuestionnaireMediaAuthorityCorruption,
        DemoQuestionnaireMediaBytesUnavailable,
    ) as exc:
        _raise_questionnaire_media_error(exc)
    return Response(
        content=media.content,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/questionnaires/runs/{run_id}/responses",
    status_code=201,
    response_model=DemoQuestionnaireStepResponse,
    operation_id="demoCreateQuestionnaireResponse",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_questionnaire_response(
    run_id: DemoId,
    payload: DemoQuestionResponseRequest,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    questionnaires: DemoQuestionnaireService = Depends(get_demo_questionnaire_service),
) -> DemoQuestionnaireStepResponse:
    try:
        result = await questionnaires.respond(
            CreateDemoQuestionnaireResponse(
                demo_actor_id=actor.id,
                questionnaire_run_id=run_id,
                selected_side=PairwiseChoice(payload.selected_side),
                expected_step_sequence=payload.expected_step_sequence,
                expected_run_version=payload.expected_run_version,
                response_latency_ms=payload.response_latency_ms,
                idempotency_key=idempotency_key,
            )
        )
    except (
        DemoQuestionnaireInputError,
        DemoQuestionnaireUnavailable,
        DemoQuestionnaireConflict,
        DemoQuestionnairePayloadConflict,
        DemoQuestionnaireAuthorityCorruption,
    ) as exc:
        _raise_questionnaire_error(exc)
    return DemoQuestionnaireStepResponse(
        step_id=result.step_id,
        run_id=result.questionnaire_run_id,
        event_type=result.event_type,
        step_number=result.step_number,
        step_sequence=result.step_sequence,
        run_version=result.run_version,
    )


@router.post(
    "/profiles/compile",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCompileProfile",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def compile_profile(
    payload: DemoProfileCompileRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoProfileCoordinator = Depends(get_demo_profile_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create(
            CreateDemoProfileCompilation(
                demo_actor_id=actor.id,
                demo_session_id=payload.session_id,
                compiler_version=payload.compiler_version,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoProfileCommandInputError,
        DemoProfileCommandUnavailable,
        DemoProfileCommandAuthorityCorruption,
        DemoIdempotencyPayloadConflict,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_profile_error(exc)
    return _job_accepted(result.job)


@router.get(
    "/profiles/active",
    response_model=DemoActiveProfilesResponse,
    operation_id="demoGetActiveProfiles",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_active_profiles(
    actor: DemoActor = Depends(get_demo_actor),
    commands: DemoProfileCommandService = Depends(get_demo_profile_commands),
) -> DemoActiveProfilesResponse:
    try:
        profiles = await commands.active_profiles(demo_actor_id=actor.id)
    except (
        DemoProfileCommandInputError,
        DemoProfileCommandUnavailable,
        DemoProfileCommandAuthorityCorruption,
    ) as exc:
        _raise_profile_error(exc)
    return DemoActiveProfilesResponse(
        profiles=[
            DemoProfileResponse(
                profile_id=item.profile_id,
                generation=item.generation,
                compilation_watermark=item.compilation_watermark,
                learning_enabled=item.learning_enabled,
            )
            for item in profiles
        ]
    )


@router.post(
    "/reference-profiles/compile",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCompileReferenceProfile",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def compile_reference_profile(
    payload: DemoReferenceProfileCompileRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoReferenceProfileCoordinator = Depends(get_demo_reference_profile_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create(
            CreateDemoReferenceProfileCompilation(
                demo_actor_id=actor.id,
                demo_session_id=payload.session_id,
                desired_delta_profile_id=payload.desired_delta_profile_id,
                style_profile_id=payload.style_profile_id,
                identity_constraints_id=payload.identity_constraints_id,
                sources=tuple(
                    DemoReferenceSource(item.asset_id, item.view) for item in payload.sources
                ),
                compiler_version=payload.compiler_version,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoReferenceProfileInputError,
        DemoReferenceProfileUnavailable,
        DemoReferenceProfileConflict,
        DemoReferenceProfileAuthorityCorruption,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_reference_profile_error(exc)
    return _job_accepted(result.job)


@router.get(
    "/reference-profiles/active",
    response_model=DemoActiveReferenceProfilesResponse,
    operation_id="demoGetActiveReferenceProfiles",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_active_reference_profiles(
    actor: DemoActor = Depends(get_demo_actor),
    service: DemoReferenceProfileService = Depends(get_demo_reference_profile_service),
) -> DemoActiveReferenceProfilesResponse:
    try:
        profiles = await service.active_profiles(demo_actor_id=actor.id)
    except (
        DemoReferenceProfileInputError,
        DemoReferenceProfileUnavailable,
        DemoReferenceProfileAuthorityCorruption,
    ) as exc:
        _raise_reference_profile_error(exc)
    return DemoActiveReferenceProfilesResponse(
        profiles=[
            DemoReferenceProfileResponse(
                reference_profile_id=item.reference_profile_id,
                version=item.version,
                content_digest=item.content_digest,
                source_count=item.source_count,
            )
            for item in profiles
        ]
    )


@router.post(
    "/style-feedback",
    status_code=201,
    response_model=DemoPreferenceEventResponse,
    operation_id="demoCreateStyleFeedback",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_style_feedback(
    payload: DemoStyleFeedbackRequest,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    commands: DemoProfileCommandService = Depends(get_demo_profile_commands),
) -> DemoPreferenceEventResponse:
    command = (
        CreateDemoStyleFeedback(
            demo_actor_id=actor.id,
            demo_session_id=payload.session_id,
            event_type="EXPLICIT_STYLE_SELECTION",
            idempotency_key=idempotency_key,
            style_key=payload.style_key,
        )
        if payload.event_type == "EXPLICIT_STYLE_SELECTION"
        else CreateDemoStyleFeedback(
            demo_actor_id=actor.id,
            demo_session_id=payload.session_id,
            event_type="MAXIMUM_INTENSITY_CHANGED",
            idempotency_key=idempotency_key,
            target_key=payload.target_key,
            maximum_intensity_ppm=payload.maximum_intensity_ppm,
        )
    )
    try:
        result = await commands.create_style_feedback(command)
    except (
        DemoProfileCommandInputError,
        DemoProfileCommandUnavailable,
        DemoProfileCommandAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoIdempotencyPayloadConflict,
        DemoIdempotencyAuthorityCorruption,
        DemoPreferenceLedgerInputError,
        DemoPreferenceActorUnavailable,
        DemoPreferenceSessionUnavailable,
        DemoPreferenceLedgerCorruption,
    ) as exc:
        _raise_profile_error(exc)
    return DemoPreferenceEventResponse(
        event_id=result.event_id,
        event_type=result.event_type,
        event_digest=result.event_digest,
    )


@router.post(
    "/constraints",
    status_code=201,
    response_model=DemoIdentityConstraintsResponse,
    operation_id="demoCreateConstraints",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_constraints(
    payload: DemoConstraintsCreateRequest,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    commands: DemoProfileCommandService = Depends(get_demo_profile_commands),
) -> DemoIdentityConstraintsResponse:
    try:
        result = await commands.create_constraints(
            CreateDemoConstraints(
                demo_actor_id=actor.id,
                demo_session_id=payload.session_id,
                scope=payload.scope,
                locks=tuple(
                    DemoConstraintLockCommand(
                        dimension_key=item.dimension_key,
                        lock=item.lock,
                        minimum_ppm=item.minimum_ppm,
                        maximum_ppm=item.maximum_ppm,
                    )
                    for item in payload.locks
                ),
                prohibited_operations=tuple(payload.prohibited_operations),
                idempotency_key=idempotency_key,
            )
        )
    except (
        DemoProfileCommandInputError,
        DemoProfileCommandUnavailable,
        DemoProfileCommandAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoIdempotencyPayloadConflict,
        DemoIdempotencyAuthorityCorruption,
        DemoPreferenceLedgerInputError,
        DemoPreferenceActorUnavailable,
        DemoPreferenceSessionUnavailable,
        DemoPreferenceLedgerCorruption,
    ) as exc:
        _raise_profile_error(exc)
    return DemoIdentityConstraintsResponse(
        constraints_id=result.constraints_id,
        version=result.version,
        scope=result.scope,
    )


@router.post(
    "/editing-sessions",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateEditingSession",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_editing_session(
    payload: DemoEditingSessionCreateRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoEditingCoordinator = Depends(get_demo_editing_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create_editing_session(
            CreateDemoEditingSession(
                demo_actor_id=actor.id,
                demo_session_id=payload.session_id,
                source_asset_id=payload.source_asset_id,
                source_image_version_id=payload.source_image_version_id,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoEditingCommandInputError,
        DemoEditingCommandUnavailable,
        DemoEditingCommandAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoIdempotencyPayloadConflict,
        DemoIdempotencyAuthorityCorruption,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_editing_error(exc)
    return _job_accepted(result.job)


@router.post(
    "/editing-sessions/{editing_session_id}/plans",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoCreateEditPlan",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_edit_plan(
    editing_session_id: DemoId,
    payload: DemoEditPlanCreateRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoEditingCoordinator = Depends(get_demo_editing_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create_edit_plan(
            CreateDemoEditPlan(
                demo_actor_id=actor.id,
                editing_session_id=editing_session_id,
                operation=OperationType(payload.operation),
                value_ppm=payload.value_ppm,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoEditingCommandInputError,
        DemoEditingCommandUnavailable,
        DemoEditingCommandAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoIdempotencyPayloadConflict,
        DemoIdempotencyAuthorityCorruption,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_editing_error(exc)
    return _job_accepted(result.job)


@router.post(
    "/edit-plans/{edit_plan_id}/executions",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoExecuteEditPlan",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def execute_edit_plan(
    edit_plan_id: DemoId,
    payload: DemoEditPlanExecuteRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoEditingCoordinator = Depends(get_demo_editing_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.execute_edit_plan(
            ExecuteDemoEditPlan(
                demo_actor_id=actor.id,
                edit_plan_id=edit_plan_id,
                execution_mode=payload.execution_mode,
                expected_plan_digest=payload.expected_plan_digest,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoEditingCommandInputError,
        DemoEditingCommandUnavailable,
        DemoEditingCommandAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoIdempotencyPayloadConflict,
        DemoIdempotencyAuthorityCorruption,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_editing_error(exc)
    return _job_accepted(result.job)


@router.get(
    "/tool-runs/{tool_run_id}",
    response_model=DemoToolRunResponse,
    operation_id="demoGetToolRun",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_tool_run(
    tool_run_id: DemoId,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoEditingCoordinator = Depends(get_demo_editing_coordinator),
) -> DemoToolRunResponse:
    try:
        result = await coordinator.get_tool_run(
            demo_actor_id=actor.id,
            tool_run_id=tool_run_id,
        )
    except (
        DemoEditingCommandInputError,
        DemoEditingCommandUnavailable,
        DemoEditingCommandAuthorityCorruption,
    ) as exc:
        _raise_editing_error(exc)
    return DemoToolRunResponse(
        tool_run_id=result.tool_run_id,
        tool_name=result.tool_name,
        status=cast(DemoJobStatus, result.job_status),
        output_digest=result.output_digest,
    )


@router.post(
    "/image-versions/{image_version_id}/feedback",
    status_code=201,
    response_model=DemoPreferenceEventResponse,
    operation_id="demoCreateImageVersionFeedback",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def create_image_version_feedback(
    image_version_id: DemoId,
    payload: DemoImageFeedbackRequest,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    service: DemoImageFeedbackService = Depends(get_demo_image_feedback_service),
) -> DemoPreferenceEventResponse:
    try:
        result = await service.create(
            CreateDemoImageFeedback(
                demo_actor_id=actor.id,
                image_version_id=image_version_id,
                feedback=payload.feedback,
                acceptance_kind=payload.acceptance_kind,
                intensity_ppm=payload.intensity_ppm,
                idempotency_key=idempotency_key,
            )
        )
    except (
        DemoImageFeedbackInputError,
        DemoImageFeedbackUnavailable,
        DemoImageFeedbackConflict,
        DemoImageFeedbackAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoIdempotencyPayloadConflict,
        DemoIdempotencyAuthorityCorruption,
        DemoPreferenceLedgerInputError,
        DemoPreferenceActorUnavailable,
        DemoPreferenceSessionUnavailable,
        DemoPreferenceLedgerCorruption,
    ) as exc:
        _raise_image_feedback_error(exc)
    return DemoPreferenceEventResponse(
        event_id=result.event_id,
        event_type=result.event_type,
        event_digest=result.event_digest,
    )


@router.post(
    "/image-versions/{image_version_id}/restore",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoRestoreImageVersion",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def restore_image_version(
    image_version_id: DemoId,
    payload: DemoRestoreRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoEditingCoordinator = Depends(get_demo_editing_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.restore_image_version(
            RestoreDemoImageVersion(
                demo_actor_id=actor.id,
                target_image_version_id=image_version_id,
                expected_current_image_version_id=payload.expected_current_image_version_id,
                expected_current_image_version_digest=payload.expected_current_image_version_digest,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoEditingCommandInputError,
        DemoEditingCommandUnavailable,
        DemoEditingCommandAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoIdempotencyPayloadConflict,
        DemoIdempotencyAuthorityCorruption,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_editing_error(exc)
    return _job_accepted(result.job)


@router.post(
    "/profiles/rebuild",
    status_code=202,
    response_model=DemoJobAcceptedResponse,
    operation_id="demoRebuildProfiles",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def rebuild_profiles(
    payload: DemoProfileRebuildRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    coordinator: DemoMemoryCoordinator = Depends(get_demo_memory_coordinator),
) -> DemoJobAcceptedResponse:
    try:
        result = await coordinator.create(
            RebuildDemoAestheticProfile(
                demo_actor_id=actor.id,
                reason=payload.reason,
                idempotency_key=idempotency_key,
                request_id=str(request.state.request_id),
            )
        )
    except (
        DemoMemoryInputError,
        DemoMemoryUnavailable,
        DemoMemoryConflict,
        DemoMemoryAuthorityCorruption,
        DemoIdempotencyInputError,
        DemoJobUnavailable,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_memory_error(exc)
    return _job_accepted(result.job)


@router.get(
    "/traces/{session_id}",
    response_model=DemoTraceResponse,
    operation_id="demoGetTrace",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_trace(
    session_id: DemoId,
    recall_at: datetime,
    actor: DemoActor = Depends(get_demo_actor),
    memory: DemoMemoryService = Depends(get_demo_memory_service),
) -> DemoTraceResponse:
    try:
        recalled = await memory.recall_context(
            demo_actor_id=actor.id,
            demo_session_id=session_id,
            recall_at=recall_at,
        )
    except (
        DemoMemoryInputError,
        DemoMemoryUnavailable,
        DemoMemoryAuthorityCorruption,
    ) as exc:
        _raise_memory_error(exc)
    return DemoTraceResponse(
        session_id=session_id,
        evidence_digest=recalled.context_digest,
        context_compilation_id=recalled.context_compilation_id,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=DemoJobResponse,
    operation_id="demoGetJob",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def get_job(
    job_id: DemoId,
    actor: DemoActor = Depends(get_demo_actor),
    jobs: DemoJobService = Depends(get_demo_job_service),
) -> DemoJobResponse:
    try:
        return _job_response(await jobs.get(demo_actor_id=actor.id, job_id=job_id))
    except (DemoJobInputError, DemoJobUnavailable, DemoJobAuthorityCorruption) as exc:
        _raise_job_error(exc)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=DemoJobResponse,
    operation_id="demoCancelJob",
    openapi_extra=DEMO_OPENAPI,
    responses=DEMO_ERRORS,
)
async def cancel_job(
    job_id: DemoId,
    payload: DemoJobCancelRequest,
    idempotency_key: IdempotencyKey,
    actor: DemoActor = Depends(get_demo_actor),
    jobs: DemoJobService = Depends(get_demo_job_service),
) -> DemoJobResponse:
    try:
        snapshot = await jobs.cancel(
            demo_actor_id=actor.id,
            job_id=job_id,
            expected_status=payload.expected_status,
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
    except (
        DemoIdempotencyPayloadConflict,
        DemoJobInputError,
        DemoJobUnavailable,
        DemoJobStateConflict,
        DemoJobAuthorityCorruption,
    ) as exc:
        _raise_job_error(exc)
    return _job_response(snapshot)
