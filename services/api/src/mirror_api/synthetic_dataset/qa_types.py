"""Typed, fail-closed QA evidence and evaluation semantics for ADR-027."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, cast

_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_REFERENCE = re.compile(r"^[a-z][a-z0-9._:/-]{2,127}$")
_ALGORITHM_VERSION = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_POLICY_SCHEMA_VERSION = "mirror.synthetic-dataset/QAPolicyDefinition/v1"
_MAX_REQUIREMENTS = 64


class QAOutcome(StrEnum):
    PASSED = "PASSED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ThresholdOutcome(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReviewDecision(StrEnum):
    PASSED = "PASSED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class QARequirement:
    code: str
    evidence_type: Literal["measurement", "review"]
    hard_gate: bool
    algorithm_reference: str | None = None
    algorithm_version: str | None = None
    threshold_rule_reference: str | None = None
    review_rule_reference: str | None = None

    def __post_init__(self) -> None:
        if _CODE.fullmatch(self.code) is None:
            raise ValueError("QA requirement code is invalid")
        if self.evidence_type == "measurement":
            if (
                self.algorithm_reference is None
                or self.algorithm_version is None
                or self.threshold_rule_reference is None
                or self.review_rule_reference is not None
                or _REFERENCE.fullmatch(self.algorithm_reference) is None
                or _ALGORITHM_VERSION.fullmatch(self.algorithm_version) is None
                or _REFERENCE.fullmatch(self.threshold_rule_reference) is None
            ):
                raise ValueError("QA measurement requirement is invalid")
        elif (
            self.algorithm_reference is not None
            or self.algorithm_version is not None
            or self.threshold_rule_reference is not None
            or self.review_rule_reference is None
            or _REFERENCE.fullmatch(self.review_rule_reference) is None
        ):
            raise ValueError("QA review requirement is invalid")


@dataclass(frozen=True)
class QAPolicyDefinition:
    """A closed, versioned policy grammar for persisted `SyntheticQAPolicy.content`."""

    requirements: tuple[QARequirement, ...]

    @classmethod
    def parse(cls, content: dict[str, object]) -> QAPolicyDefinition:
        if set(content) != {"schema_version", "requirements"}:
            raise ValueError("QA policy content schema is unsupported")
        if content.get("schema_version") != _POLICY_SCHEMA_VERSION:
            raise ValueError("QA policy content schema is unsupported")
        raw_requirements = content.get("requirements")
        if (
            not isinstance(raw_requirements, list)
            or not raw_requirements
            or len(raw_requirements) > _MAX_REQUIREMENTS
        ):
            raise ValueError("QA policy requirements are invalid")
        requirements = tuple(_parse_requirement(item) for item in raw_requirements)
        if len({item.code for item in requirements}) != len(requirements):
            raise ValueError("QA policy requirements must be unique")
        return cls(requirements=requirements)


@dataclass(frozen=True)
class QAMeasurementEvidence:
    measurement_kind: str
    measurement_code: str
    payload: dict[str, object]
    algorithm_reference: str
    algorithm_version: str
    confidence: float | None
    hard_gate: bool
    threshold_outcome: ThresholdOutcome
    reason_code: str

    def __post_init__(self) -> None:
        for value in (self.measurement_kind, self.measurement_code, self.reason_code):
            if _CODE.fullmatch(value) is None:
                raise ValueError("QA measurement code is invalid")
        if (
            _REFERENCE.fullmatch(self.algorithm_reference) is None
            or _ALGORITHM_VERSION.fullmatch(self.algorithm_version) is None
        ):
            raise ValueError("QA algorithm reference is invalid")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("QA confidence must be between zero and one")
        _canonical_json_bytes(self.payload)

    @property
    def payload_digest(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()


@dataclass(frozen=True)
class QAReviewEvidence:
    review_kind: str
    decision: ReviewDecision
    reason_code: str
    actor_reference: str

    def __post_init__(self) -> None:
        if _CODE.fullmatch(self.review_kind) is None or _CODE.fullmatch(self.reason_code) is None:
            raise ValueError("QA review code is invalid")
        if _REFERENCE.fullmatch(self.actor_reference) is None:
            raise ValueError("QA review actor reference is invalid")


@dataclass(frozen=True)
class QAEvaluation:
    outcome: QAOutcome
    reason_code: str | None
    unresolved_requirements: tuple[str, ...]


def evaluate_qa(
    *,
    requirements: tuple[QARequirement, ...],
    measurements: tuple[QAMeasurementEvidence, ...],
    reviews: tuple[QAReviewEvidence, ...],
) -> QAEvaluation:
    """Evaluate supplied evidence without accepting unsupported or missing hard gates."""
    if not requirements or len({item.code for item in requirements}) != len(requirements):
        raise ValueError("QA requirements must be unique")
    if len({item.measurement_code for item in measurements}) != len(measurements):
        raise ValueError("QA measurement codes must be unique")
    if len({item.review_kind for item in reviews}) != len(reviews):
        raise ValueError("QA review kinds must be unique")

    failed_measurements = tuple(
        item.measurement_code
        for item in measurements
        if item.hard_gate and item.threshold_outcome is ThresholdOutcome.FAILED
    )
    if failed_measurements:
        return QAEvaluation(QAOutcome.REJECTED, "hard_measurement_failed", failed_measurements)

    measurements_by_code = {item.measurement_code: item for item in measurements}
    reviews_by_kind = {item.review_kind: item for item in reviews}
    unresolved: list[str] = []
    for requirement in requirements:
        if not requirement.hard_gate:
            continue
        if requirement.evidence_type == "measurement":
            measurement = measurements_by_code.get(requirement.code)
            if (
                measurement is None
                or measurement.threshold_outcome is not ThresholdOutcome.PASSED
                or measurement.hard_gate is not requirement.hard_gate
                or measurement.algorithm_reference != requirement.algorithm_reference
                or measurement.algorithm_version != requirement.algorithm_version
            ):
                unresolved.append(requirement.code)
        else:
            review = reviews_by_kind.get(requirement.code)
            if review is None or review.decision is not ReviewDecision.PASSED:
                unresolved.append(requirement.code)
    if unresolved:
        return QAEvaluation(QAOutcome.REJECTED, "required_evidence_unresolved", tuple(unresolved))
    return QAEvaluation(QAOutcome.PASSED, None, ())


def _parse_requirement(value: object) -> QARequirement:
    if not isinstance(value, dict):
        raise ValueError("QA policy requirement is invalid")
    evidence_type = value.get("evidence_type")
    if evidence_type == "measurement":
        expected = {
            "code",
            "evidence_type",
            "hard_gate",
            "algorithm_reference",
            "algorithm_version",
            "threshold_rule_reference",
        }
        if set(value) != expected or type(value.get("hard_gate")) is not bool:
            raise ValueError("QA policy measurement requirement is invalid")
        return QARequirement(
            code=_string(value, "code"),
            evidence_type="measurement",
            hard_gate=cast(bool, value["hard_gate"]),
            algorithm_reference=_string(value, "algorithm_reference"),
            algorithm_version=_string(value, "algorithm_version"),
            threshold_rule_reference=_string(value, "threshold_rule_reference"),
        )
    if evidence_type == "review":
        expected = {"code", "evidence_type", "hard_gate", "review_rule_reference"}
        if set(value) != expected or type(value.get("hard_gate")) is not bool:
            raise ValueError("QA policy review requirement is invalid")
        return QARequirement(
            code=_string(value, "code"),
            evidence_type="review",
            hard_gate=cast(bool, value["hard_gate"]),
            review_rule_reference=_string(value, "review_rule_reference"),
        )
    raise ValueError("QA policy requirement is invalid")


def _string(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise ValueError("QA policy requirement is invalid")
    return result


def _canonical_json_bytes(value: object) -> bytes:
    """Validate JSON recursively before hashing/persisting; no Python-only payload values."""
    try:
        encoded = json.dumps(
            value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
    except (TypeError, ValueError):
        raise ValueError("QA evidence payload must be canonical JSON") from None
    decoded = json.loads(encoded)
    if decoded != value:
        raise ValueError("QA evidence payload must be canonical JSON")
    return encoded
