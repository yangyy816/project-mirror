from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class HealthResponse(BaseModel):
    status: Literal["live", "ready", "limited"]
    service: str = "mirror-api"
    version: str
    dependencies: dict[str, Literal["available", "unavailable", "not_checked"]]


class VersionResponse(BaseModel):
    service: str = "mirror-api"
    version: str
    api_version: str = "v1"


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlaceholderRequest(BaseModel):
    intent: str | None = None


class SmsChallengeRequest(StrictContractModel):
    phone: SecretStr = Field(min_length=1, max_length=32)
    invite_code: SecretStr | None = Field(default=None, min_length=1, max_length=128)


class SmsChallengeResponse(StrictContractModel):
    challenge_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    expires_at: datetime


class SessionRequest(StrictContractModel):
    challenge_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    otp: SecretStr = Field(min_length=1, max_length=16)


class AccessTokenResponse(StrictContractModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105
    scope: Literal["pending", "active"]


class CurrentUserResponse(StrictContractModel):
    user_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["pending", "active"]
    scope: Literal["pending", "active"]
    onboarding_requirements: list[Literal["age_assurance", "policy_acceptance"]]


class AgeAssuranceRequest(StrictContractModel):
    credential: SecretStr = Field(min_length=1, max_length=4_096)


class AgeAssuranceResponse(StrictContractModel):
    record_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    result: Literal["verified", "not_verified", "indeterminate"]
    activated: bool


class PolicyAcceptanceRequest(StrictContractModel):
    document_code: str = Field(min_length=1, max_length=64)
    document_version: str = Field(min_length=1, max_length=64)
    document_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class PolicyAcceptanceResponse(StrictContractModel):
    activated: bool


class PurposeConsentRequirementResponse(StrictContractModel):
    consent_type: Literal["facial_data_processing"]
    purpose_code: str
    purpose_version: str
    policy_code: str
    policy_version: str
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operations: list[Literal["private_upload", "security_validation"]]


class PurposeConsentStateResponse(StrictContractModel):
    status: Literal["granted", "withdrawn", "missing"]
    requirement: PurposeConsentRequirementResponse
    grant_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    missing_reason: Literal["absent", "expired", "version_mismatch"] | None = None


class PurposeConsentGrantResponse(StrictContractModel):
    grant_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    granted_at: datetime
    expires_at: datetime | None


class PurposeConsentWithdrawalResponse(StrictContractModel):
    withdrawal_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    grant_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    withdrawn_at: datetime


class UploadIntentCreateRequest(StrictContractModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    byte_size: int = Field(gt=0, le=20 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class UploadIntentResponse(StrictContractModel):
    intent_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal[
        "awaiting_upload",
        "uploaded_unverified",
        "processing",
        "promoted",
        "rejected",
        "cancelled",
        "expired",
    ]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    byte_size: int
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    grant_expires_at: datetime
    uploaded_at: datetime | None
    cancelled_at: datetime | None
    expired_at: datetime | None


class PrivateUploadGrantResponse(StrictContractModel):
    method: Literal["PUT"]
    url: str
    required_headers: dict[str, str]
    expires_at: datetime


class UploadIntentCreationResponse(StrictContractModel):
    intent: UploadIntentResponse
    upload: PrivateUploadGrantResponse | None


class IngestionJobResponse(StrictContractModel):
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["pending", "leased", "promoted", "rejected", "cancelled"]
    result_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{2,63}$")
    asset_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    finalized_at: datetime | None = None


class AssetResponse(StrictContractModel):
    asset_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    asset_role: Literal["original", "derived", "synthetic"]
    mime_type: Literal["image/jpeg"]
    byte_size: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    created_at: datetime


class AssetListResponse(StrictContractModel):
    assets: list[AssetResponse]


class PrivateDownloadGrantResponse(StrictContractModel):
    method: Literal["GET"]
    url: str
    required_headers: dict[str, str]
    expires_at: datetime


class AssetDeletionResponse(StrictContractModel):
    deletion_request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["requested", "processing", "completed", "failed"]


class DataExportResponse(StrictContractModel):
    export_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["requested", "processing", "ready", "failed", "expired"]
    schema_version: Literal["mirror-data-export-v1"]
    requested_at: datetime
    ready_at: datetime | None = None
    expires_at: datetime | None = None


class AccountDeletionResponse(StrictContractModel):
    deletion_request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["requested", "processing", "completed", "failed"]
    requested_at: datetime
    completed_at: datetime | None = None


class SelfStateContract(StrictContractModel):
    id: str
    version: int = Field(gt=0)
    baseline_face_model_id: str
    state_schema_version: str
    reliable_dimensions: list[str]
    unreliable_dimensions: list[str]


class DesiredDeltaDimensionContract(StrictContractModel):
    dimension_key: str
    direction: Literal[-1, 0, 1]
    magnitude: float = Field(ge=0)
    preference_confidence: float = Field(ge=0, le=1)
    generalization_confidence: float = Field(ge=0, le=1)
    transfer_confidence: float = Field(ge=0, le=1)
    user_lock: Literal["none", "preserve"]


class DesiredDeltaProfileContract(StrictContractModel):
    id: str
    version: int = Field(gt=0)
    self_state_version_id: str
    inference_algorithm_version: str
    evidence_fusion_version: str
    dimensions: list[DesiredDeltaDimensionContract]


class QuestionnaireRunContextContract(StrictContractModel):
    baseline_face_model_id: str
    self_state_version_id: str
    question_bank_version: str
    routing_algorithm_version: str
    route_seed: str
    measurement_normalization_version: str
    morphology_descriptor_version: str
    neighborhood_metric_version: str
    stimulus_generator_version: str


FOUNDATION_CONTRACT_MODELS: tuple[type[BaseModel], ...] = (
    SelfStateContract,
    DesiredDeltaDimensionContract,
    DesiredDeltaProfileContract,
    QuestionnaireRunContextContract,
)


def add_foundation_contract_schemas(openapi_schema: dict[str, Any]) -> None:
    """Publish inactive Phase 0 domain schemas without exposing fake business endpoints."""
    components = openapi_schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for model in FOUNDATION_CONTRACT_MODELS:
        generated = model.model_json_schema(ref_template="#/components/schemas/{model}")
        definitions = generated.pop("$defs", {})
        schemas.update(definitions)
        schemas[model.__name__] = generated
