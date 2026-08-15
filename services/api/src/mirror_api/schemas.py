from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["live", "ready", "limited"]
    service: str = "mirror-api"
    version: str
    dependencies: dict[str, Literal["available", "unavailable", "not_checked"]]


class VersionResponse(BaseModel):
    service: str = "mirror-api"
    version: str
    api_version: str = "v1"


class PlaceholderRequest(BaseModel):
    intent: str | None = None


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
