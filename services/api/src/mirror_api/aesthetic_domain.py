from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum


class EvidencePriority(IntEnum):
    POPULATION_PRIOR = 0
    SYNTHETIC_QUESTIONNAIRE = 10
    ACCEPTED_PRODUCTION_EDIT = 20
    ACCEPTED_SELF_TRANSFER = 30
    MANUAL_CORRECTION = 40
    EXPLICIT_INSTRUCTION = 50


@dataclass(frozen=True)
class DeltaEvidence:
    source: EvidencePriority
    direction: int
    magnitude: float
    preference_confidence: float
    generalized: bool = False
    transferred: bool = False

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction must be -1, 0, or 1")
        if self.magnitude < 0:
            raise ValueError("magnitude must be non-negative")
        if not 0 <= self.preference_confidence <= 1:
            raise ValueError("preference confidence must be in [0, 1]")


@dataclass(frozen=True)
class DesiredDelta:
    direction: int
    magnitude: float
    preference_confidence: float
    generalization_confidence: float
    transfer_confidence: float
    uncertainty: float
    source: EvidencePriority | None
    preserve_lock: bool = False

    @property
    def signed_value(self) -> float:
        if self.preserve_lock:
            return 0.0
        return self.direction * self.magnitude


def infer_desired_delta(
    evidence: Sequence[DeltaEvidence], *, preserve_lock: bool = False
) -> DesiredDelta:
    """Fuse evidence by semantic precedence without a hidden population target."""
    if preserve_lock:
        return DesiredDelta(0, 0.0, 1.0, 1.0, 1.0, 0.0, None, preserve_lock=True)

    user_evidence = [item for item in evidence if item.source != EvidencePriority.POPULATION_PRIOR]
    if not user_evidence:
        return DesiredDelta(0, 0.0, 0.0, 0.0, 0.0, 1.0, None)

    highest_priority = max(item.source for item in user_evidence)
    selected = [item for item in user_evidence if item.source == highest_priority]
    weight_sum = sum(item.preference_confidence for item in selected)
    if weight_sum == 0:
        return DesiredDelta(0, 0.0, 0.0, 0.0, 0.0, 1.0, highest_priority)

    signed_delta = (
        sum(item.direction * item.magnitude * item.preference_confidence for item in selected)
        / weight_sum
    )
    confidence = min(1.0, weight_sum / len(selected))
    generalized = [item.preference_confidence for item in selected if item.generalized]
    transferred = [item.preference_confidence for item in selected if item.transferred]
    return DesiredDelta(
        direction=1 if signed_delta > 0 else -1 if signed_delta < 0 else 0,
        magnitude=abs(signed_delta),
        preference_confidence=confidence,
        generalization_confidence=sum(generalized) / len(generalized) if generalized else 0.0,
        transfer_confidence=sum(transferred) / len(transferred) if transferred else 0.0,
        uncertainty=1.0 - confidence,
        source=highest_priority,
    )


def compute_relative_target(
    baseline: Mapping[str, float], deltas: Mapping[str, DesiredDelta]
) -> dict[str, float]:
    """Apply deltas to each user's own reference frame, never to a global target."""
    return {
        dimension: value + deltas.get(dimension, DesiredDelta(0, 0, 0, 0, 0, 1, None)).signed_value
        for dimension, value in baseline.items()
    }


@dataclass(frozen=True)
class RouteVersions:
    routing_algorithm_version: str
    question_bank_version: str
    self_state_version_id: str
    baseline_face_model_id: str
    analysis_schema_version: str
    measurement_normalization_version: str
    morphology_descriptor_version: str
    neighborhood_metric_version: str
    stimulus_generator_version: str
    route_seed: str


@dataclass(frozen=True)
class RoutingTemplate:
    template_id: str
    target_dimension: str


@dataclass(frozen=True)
class QuestionnaireRouteResult:
    selected_template_ids: tuple[str, ...]
    dimension_priorities: Mapping[str, float]
    metadata: Mapping[str, str]


def route_questionnaire(
    *,
    self_state: Mapping[str, float],
    reliability: Mapping[str, float],
    uncertainty: Mapping[str, float],
    templates: Sequence[RoutingTemplate],
    versions: RouteVersions,
    limit: int,
) -> QuestionnaireRouteResult:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    dimensions = {template.target_dimension for template in templates}
    priorities = {
        dimension: round(
            uncertainty.get(dimension, 1.0)
            + (1.0 - reliability.get(dimension, 0.0))
            + abs(self_state.get(dimension, 0.0)) * 0.25,
            8,
        )
        for dimension in dimensions
    }

    def ordering(template: RoutingTemplate) -> tuple[float, str]:
        tie_breaker = hashlib.sha256(
            f"{versions.route_seed}:{template.template_id}".encode()
        ).hexdigest()
        return (-priorities[template.target_dimension], tie_breaker)

    selected = tuple(template.template_id for template in sorted(templates, key=ordering)[:limit])
    metadata = {
        "routing_algorithm_version": versions.routing_algorithm_version,
        "question_bank_version": versions.question_bank_version,
        "self_state_version_id": versions.self_state_version_id,
        "baseline_face_model_id": versions.baseline_face_model_id,
        "analysis_schema_version": versions.analysis_schema_version,
        "measurement_normalization_version": versions.measurement_normalization_version,
        "morphology_descriptor_version": versions.morphology_descriptor_version,
        "neighborhood_metric_version": versions.neighborhood_metric_version,
        "stimulus_generator_version": versions.stimulus_generator_version,
        "route_seed": versions.route_seed,
    }
    return QuestionnaireRouteResult(selected, priorities, metadata)


@dataclass(frozen=True)
class IsolationResult:
    target_delta: float
    non_target_max_error: float
    isolation_threshold: float
    validation_status: str


def validate_variable_isolation(
    before: Mapping[str, float],
    after: Mapping[str, float],
    *,
    target_dimension: str,
    isolation_threshold: float,
) -> IsolationResult:
    if target_dimension not in before or target_dimension not in after:
        raise ValueError("target dimension must exist in both fixtures")
    shared_non_target = (before.keys() & after.keys()) - {target_dimension}
    non_target_error = max(
        (abs(after[key] - before[key]) for key in shared_non_target), default=0.0
    )
    target_delta = after[target_dimension] - before[target_dimension]
    status = "pass" if target_delta != 0 and non_target_error <= isolation_threshold else "fail"
    return IsolationResult(target_delta, non_target_error, isolation_threshold, status)
