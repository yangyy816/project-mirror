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
