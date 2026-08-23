from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from mirror_api.schemas import StrictContractModel

DemoId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
DemoDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Ppm = Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
UnitPpm = Annotated[int, Field(ge=0, le=1_000_000)]
JobState = Literal["PENDING", "RUNNING", "COMPLETED", "REJECTED", "FAILED", "CANCELLED"]


class DemoSessionCreateRequest(StrictContractModel):
    synthetic_identity_id: DemoId
    context_seed: DemoDigest


class DemoSessionResponse(StrictContractModel):
    session_id: DemoId
    synthetic_identity_id: DemoId
    status: Literal["ACTIVE", "CLOSED", "TOMBSTONED"]
    expires_at: datetime


class DemoContextResponse(StrictContractModel):
    session_id: DemoId
    profile_id: DemoId
    compilation_digest: DemoDigest
    expires_at: datetime


class DemoIdentityResponse(StrictContractModel):
    identity_id: DemoId
    canonical_asset_digest: DemoDigest
    admission_status: Literal["ADMITTED", "REVOKED"]


class DemoIdentityListResponse(StrictContractModel):
    identities: list[DemoIdentityResponse]


class DemoJobAcceptedResponse(StrictContractModel):
    job_id: DemoId
    status: Literal["PENDING"] = "PENDING"
    capability: str = Field(min_length=1, max_length=64)


class DemoJobResponse(StrictContractModel):
    job_id: DemoId
    status: JobState
    result_code: str | None = Field(default=None, min_length=1, max_length=64)
    finalized_at: datetime | None = None


class DemoJobCancelRequest(StrictContractModel):
    expected_status: Literal["PENDING", "RUNNING"]
    reason: Literal["USER_REQUEST"] = "USER_REQUEST"


class DemoAnalysisCreateRequest(StrictContractModel):
    session_id: DemoId
    source_asset_id: DemoId


class DemoAnalysisResponse(StrictContractModel):
    analysis_id: DemoId
    session_id: DemoId
    state: Literal["SUPPORTED", "UNSUPPORTED", "PENDING"]
    observation_digest: DemoDigest | None = None


class DemoQuestionnaireRunCreateRequest(StrictContractModel):
    session_id: DemoId
    self_state_id: DemoId
    question_bank_version: str = Field(min_length=1, max_length=64)
    max_questions: int = Field(ge=12, le=16)


class DemoQuestionResponseRequest(StrictContractModel):
    selected_side: Literal["LEFT", "RIGHT", "INDISTINGUISHABLE", "SKIP"]
    expected_step_sequence: int = Field(ge=1)
    expected_run_version: int = Field(ge=1)
    response_latency_ms: int = Field(ge=0, le=3_600_000)


class DemoQuestionnaireStepResponse(StrictContractModel):
    step_id: DemoId
    run_id: DemoId
    event_type: Literal["PRESENTED", "RESPONDED", "STOPPED", "INVALIDATED"]
    step_number: int | None = Field(default=None, ge=1)
    step_sequence: int = Field(ge=1)
    run_version: int = Field(ge=1)


class DemoQuestionSideResponse(StrictContractModel):
    result_asset_id: DemoId
    result_checksum: DemoDigest
    result_lineage_digest: DemoDigest
    requested_direction: Literal["NEGATIVE", "POSITIVE"]
    measured_delta_ppm: Ppm


class DemoRoutingComponents(StrictContractModel):
    posterior_uncertainty_ppm: UnitPpm
    self_state_reliability_ppm: UnitPpm
    coverage_need_ppm: UnitPpm
    expected_fisher_information_ppm: UnitPpm
    morphology_neighborhood_compatibility_ppm: UnitPpm
    pair_quality_ppm: UnitPpm
    contradiction_priority_ppm: UnitPpm


class DemoQuestionNextResponse(StrictContractModel):
    kind: Literal["QUESTION"]
    step_id: DemoId
    question_pair_id: DemoId
    question_pair_digest: DemoDigest
    dimension_key: str = Field(min_length=1, max_length=48)
    magnitude_ppm: UnitPpm
    source_identity_id: DemoId
    source_asset_id: DemoId
    source_checksum: DemoDigest
    left: DemoQuestionSideResponse
    right: DemoQuestionSideResponse
    routing_score_ppm: UnitPpm
    routing_components: DemoRoutingComponents
    routing_evidence_digest: DemoDigest
    step_sequence: int = Field(ge=1)
    run_version: int = Field(ge=1)


class DemoQuestionCompletedResponse(StrictContractModel):
    kind: Literal["COMPLETED"]
    run_id: DemoId
    completed_at: datetime


DemoQuestionnaireNextResponse = Annotated[
    DemoQuestionNextResponse | DemoQuestionCompletedResponse,
    Field(discriminator="kind"),
]


class DemoProfileCompileRequest(StrictContractModel):
    session_id: DemoId
    compiler_version: str = Field(min_length=1, max_length=64)


class DemoProfileResponse(StrictContractModel):
    profile_id: DemoId
    generation: int = Field(ge=1)
    compilation_watermark: DemoDigest
    learning_enabled: bool


class DemoActiveProfilesResponse(StrictContractModel):
    profiles: list[DemoProfileResponse]


class DemoExplicitStyleSelectionRequest(StrictContractModel):
    event_type: Literal["EXPLICIT_STYLE_SELECTION"]
    session_id: DemoId | None = None
    style_key: str = Field(min_length=1, max_length=64)


class DemoMaximumIntensityChangedRequest(StrictContractModel):
    event_type: Literal["MAXIMUM_INTENSITY_CHANGED"]
    session_id: DemoId | None = None
    target_key: str = Field(min_length=1, max_length=64)
    maximum_intensity_ppm: UnitPpm


DemoStyleFeedbackRequest = Annotated[
    DemoExplicitStyleSelectionRequest | DemoMaximumIntensityChangedRequest,
    Field(discriminator="event_type"),
]


class DemoPreferenceEventResponse(StrictContractModel):
    event_id: DemoId
    event_type: Literal[
        "EXPLICIT_STYLE_SELECTION",
        "MAXIMUM_INTENSITY_CHANGED",
        "IMAGE_ACCEPTED",
        "IMAGE_REJECTED",
        "IMAGE_ADJUSTED",
    ]
    event_digest: DemoDigest


class DemoLockRequest(StrictContractModel):
    dimension_key: str = Field(min_length=1, max_length=48)
    lock: Literal["PRESERVE", "UNLOCK"]
    minimum_ppm: Ppm | None = None
    maximum_ppm: Ppm | None = None


class DemoConstraintsCreateRequest(StrictContractModel):
    session_id: DemoId | None = None
    scope: Literal["PERSISTENT", "SESSION_OVERRIDE"]
    locks: list[DemoLockRequest] = Field(min_length=1, max_length=64)
    prohibited_operations: list[
        Literal[
            "CROP",
            "ROTATE",
            "EXPOSURE",
            "CONTRAST",
            "SATURATION",
            "TEMPERATURE",
            "GEOMETRY",
            "MAKEUP",
            "GENERATIVE",
        ]
    ] = Field(default_factory=list)


class DemoIdentityConstraintsResponse(StrictContractModel):
    constraints_id: DemoId
    version: int = Field(ge=1)
    scope: Literal["PERSISTENT", "SESSION_OVERRIDE"]


class DemoEditingSessionCreateRequest(StrictContractModel):
    session_id: DemoId
    source_image_version_id: DemoId


class DemoEditPlanCreateRequest(StrictContractModel):
    operation: Literal[
        "CROP",
        "ROTATE",
        "EXPOSURE",
        "CONTRAST",
        "SATURATION",
        "TEMPERATURE",
        "GEOMETRY",
        "MAKEUP",
        "GENERATIVE",
    ]
    value_ppm: Ppm


class DemoEditPlanExecuteRequest(StrictContractModel):
    execution_mode: Literal["DETERMINISTIC_RASTER", "GEOMETRY", "MAKEUP", "GENERATIVE"]
    expected_plan_digest: DemoDigest


class DemoToolRunResponse(StrictContractModel):
    tool_run_id: DemoId
    tool_name: str = Field(min_length=1, max_length=64)
    status: JobState
    output_digest: DemoDigest | None = None


class DemoImageFeedbackRequest(StrictContractModel):
    feedback: Literal["ACCEPT", "REJECT", "ADJUST"]
    intensity_ppm: Annotated[int, Field(ge=0, le=1_000_000)] | None = None


class DemoRestoreRequest(StrictContractModel):
    expected_current_image_version_id: DemoId
    expected_current_image_version_digest: DemoDigest


class DemoProfileRebuildRequest(StrictContractModel):
    reason: Literal["USER_REQUEST", "RESET", "ROLLBACK", "TOMBSTONE_PROPAGATION"]


class DemoExecutionEvidenceResponse(StrictContractModel):
    session_id: DemoId
    evidence_digest: DemoDigest
    context_compilation_id: DemoId


DemoTraceResponse = DemoExecutionEvidenceResponse


class DemoCapability(StrictContractModel):
    code: Literal[
        "P3_FACE_ANALYSIS",
        "P4_QUESTIONNAIRE",
        "P5_COMPILER",
        "P6_DETERMINISTIC_RASTER",
        "P6_GEOMETRY",
        "P6_MAKEUP",
        "P6_GENERATIVE_EDITOR",
        "P7_PREFERENCE_MEMORY",
    ]
    status: Literal[
        "AVAILABLE",
        "NOT_IMPLEMENTED",
        "DEFERRED_WITH_EXPLICIT_REASON",
        "CAPABILITY_UNAVAILABLE",
    ]
    reason: str | None = Field(default=None, min_length=1, max_length=256)


class DemoCapabilitiesResponse(StrictContractModel):
    track: Literal["DEMO_PROTOTYPE"] = "DEMO_PROTOTYPE"
    capabilities: list[DemoCapability]
