"""Pure domain contracts for P2-M5 variable-isolation evaluation.

The module has no ORM, image library, storage, task-runner, or provider imports. It
encodes the authority accepted by ADR-041 without selecting research thresholds.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

SYNTHETIC_EVALUATION_POLICY_SCHEMA_VERSION = "mirror.synthetic-dataset/SyntheticEvaluationPolicy/v1"
ISOLATION_REPORT_RESULT_SCHEMA_VERSION = "mirror.synthetic-dataset/IsolationReportResult/v1"
COHORT_STAGES = (24, 48, 96)
MAX_TOLERANCE_PPM = 1_000_000
MAX_ABSOLUTE_DELTA_PPM = 5_000_000
MAX_TARGET_ERROR_PPM = MAX_ABSOLUTE_DELTA_PPM * 2

_REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_VERSION_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*\Z")
_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_FORBIDDEN_REGION_TOKENS = frozenset(
    {
        "ancestry",
        "adult",
        "age",
        "attractiveness",
        "beauty",
        "ethnicity",
        "ideal",
        "minor",
        "nationality",
        "population",
        "race",
        "rank",
        "score",
        "sexual",
    }
)


class M5ReasonCode(StrEnum):
    INVALID_POLICY = "INVALID_POLICY"
    CONTENT_DIGEST_MISMATCH = "CONTENT_DIGEST_MISMATCH"
    UNKNOWN_DIMENSION = "UNKNOWN_DIMENSION"
    INVALID_REGION_GROUP = "INVALID_REGION_GROUP"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    INVALID_CHECKSUM = "INVALID_CHECKSUM"
    INVALID_MEASUREMENT = "INVALID_MEASUREMENT"
    MISSING_CONTROL_MEASUREMENT = "MISSING_CONTROL_MEASUREMENT"
    TARGET_CONTROL_CONFLICT = "TARGET_CONTROL_CONFLICT"
    SPLIT_LEAKAGE = "SPLIT_LEAKAGE"
    INVALID_COHORT_STAGE = "INVALID_COHORT_STAGE"
    TARGET_DIRECTION_MISMATCH = "TARGET_DIRECTION_MISMATCH"
    TARGET_ERROR_EXCEEDED = "TARGET_ERROR_EXCEEDED"
    CONTROL_DRIFT_EXCEEDED = "CONTROL_DRIFT_EXCEEDED"
    REPEAT_VARIANCE_EXCEEDED = "REPEAT_VARIANCE_EXCEEDED"
    PLATFORM_VARIANCE_EXCEEDED = "PLATFORM_VARIANCE_EXCEEDED"
    ARTIFACT_GATE_FAILED = "ARTIFACT_GATE_FAILED"
    RELIABILITY_GATE_FAILED = "RELIABILITY_GATE_FAILED"
    INVALID_OUTCOME = "INVALID_OUTCOME"


class M5ValidationError(ValueError):
    """Safe validation error that never echoes submitted references or measurements."""

    def __init__(self, reason_code: M5ReasonCode) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code.value)


class EvaluationSplit(StrEnum):
    CALIBRATION = "CALIBRATION"
    M4_SEEN = "M4_SEEN"
    HOLDOUT = "HOLDOUT"


class IsolationConclusion(StrEnum):
    PASSED = "PASSED"
    REJECTED = "REJECTED"


class TechnicalGateResult(StrEnum):
    PASS = "PASS"  # noqa: S105 - milestone result, not a credential
    FAIL = "FAIL"


class MvrResult(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    PASS = "PASS"  # noqa: S105 - research result, not a credential
    FURTHER_RESEARCH = "FURTHER_RESEARCH"
    FAIL = "FAIL"


@dataclass(frozen=True)
class EvaluationDimensionRule:
    """Versioned per-dimension thresholds; values are supplied only by preregistration."""

    dimension_key: str
    region_group: str
    control_dimensions: tuple[str, ...]
    target_error_tolerance_ppm: int
    control_drift_tolerance_ppm: int
    repeat_variance_tolerance_ppm: int
    platform_variance_tolerance_ppm: int

    def __post_init__(self) -> None:
        _require_key(self.dimension_key, M5ReasonCode.UNKNOWN_DIMENSION)
        _require_region_group(self.region_group)
        if not self.control_dimensions or self.control_dimensions != tuple(
            sorted(set(self.control_dimensions))
        ):
            raise M5ValidationError(M5ReasonCode.MISSING_CONTROL_MEASUREMENT)
        for control in self.control_dimensions:
            _require_key(control, M5ReasonCode.UNKNOWN_DIMENSION)
        if self.dimension_key in self.control_dimensions:
            raise M5ValidationError(M5ReasonCode.TARGET_CONTROL_CONFLICT)
        for tolerance in (
            self.target_error_tolerance_ppm,
            self.control_drift_tolerance_ppm,
            self.repeat_variance_tolerance_ppm,
            self.platform_variance_tolerance_ppm,
        ):
            _require_bounded_nonnegative_int(tolerance, M5ReasonCode.INVALID_POLICY)

    def canonical_facts(self) -> dict[str, object]:
        return {
            "control_dimensions": list(self.control_dimensions),
            "control_drift_tolerance_ppm": self.control_drift_tolerance_ppm,
            "dimension_key": self.dimension_key,
            "platform_variance_tolerance_ppm": self.platform_variance_tolerance_ppm,
            "region_group": self.region_group,
            "repeat_variance_tolerance_ppm": self.repeat_variance_tolerance_ppm,
            "target_error_tolerance_ppm": self.target_error_tolerance_ppm,
        }


@dataclass(frozen=True)
class SyntheticEvaluationPolicy:
    """Immutable M5 policy that cannot reinterpret an M4 tolerance reference."""

    version: str
    ontology_version: str
    ontology_digest: str
    measurement_policy_version: str
    isolation_algorithm_version: str
    duplicate_algorithm_version: str
    split_rule_version: str
    cohort_stages: tuple[int, ...]
    dimension_rules: tuple[EvaluationDimensionRule, ...]
    content_digest: str

    def __post_init__(self) -> None:
        for version in (
            self.version,
            self.ontology_version,
            self.measurement_policy_version,
            self.isolation_algorithm_version,
            self.duplicate_algorithm_version,
            self.split_rule_version,
        ):
            _require_version(version)
        _require_sha256(self.ontology_digest)
        if self.cohort_stages != COHORT_STAGES:
            raise M5ValidationError(M5ReasonCode.INVALID_COHORT_STAGE)
        if not all(isinstance(rule, EvaluationDimensionRule) for rule in self.dimension_rules):
            raise M5ValidationError(M5ReasonCode.INVALID_POLICY)
        keys = tuple(rule.dimension_key for rule in self.dimension_rules)
        if not keys or keys != tuple(sorted(set(keys))):
            raise M5ValidationError(M5ReasonCode.INVALID_POLICY)
        _require_sha256(self.content_digest)
        if self.content_digest != _digest(
            SYNTHETIC_EVALUATION_POLICY_SCHEMA_VERSION, self._canonical_facts()
        ):
            raise M5ValidationError(M5ReasonCode.CONTENT_DIGEST_MISMATCH)

    @classmethod
    def create(
        cls,
        *,
        version: str,
        ontology_version: str,
        ontology_digest: str,
        measurement_policy_version: str,
        isolation_algorithm_version: str,
        duplicate_algorithm_version: str,
        split_rule_version: str,
        dimension_rules: tuple[EvaluationDimensionRule, ...],
    ) -> SyntheticEvaluationPolicy:
        canonical_rules = tuple(sorted(dimension_rules, key=lambda rule: rule.dimension_key))
        facts = _policy_facts(
            version=version,
            ontology_version=ontology_version,
            ontology_digest=ontology_digest,
            measurement_policy_version=measurement_policy_version,
            isolation_algorithm_version=isolation_algorithm_version,
            duplicate_algorithm_version=duplicate_algorithm_version,
            split_rule_version=split_rule_version,
            dimension_rules=canonical_rules,
        )
        return cls(
            version=version,
            ontology_version=ontology_version,
            ontology_digest=ontology_digest,
            measurement_policy_version=measurement_policy_version,
            isolation_algorithm_version=isolation_algorithm_version,
            duplicate_algorithm_version=duplicate_algorithm_version,
            split_rule_version=split_rule_version,
            cohort_stages=COHORT_STAGES,
            dimension_rules=canonical_rules,
            content_digest=_digest(SYNTHETIC_EVALUATION_POLICY_SCHEMA_VERSION, facts),
        )

    def rule_for(self, dimension_key: str) -> EvaluationDimensionRule:
        for rule in self.dimension_rules:
            if rule.dimension_key == dimension_key:
                return rule
        raise M5ValidationError(M5ReasonCode.UNKNOWN_DIMENSION)

    def _canonical_facts(self) -> dict[str, object]:
        return _policy_facts(
            version=self.version,
            ontology_version=self.ontology_version,
            ontology_digest=self.ontology_digest,
            measurement_policy_version=self.measurement_policy_version,
            isolation_algorithm_version=self.isolation_algorithm_version,
            duplicate_algorithm_version=self.duplicate_algorithm_version,
            split_rule_version=self.split_rule_version,
            dimension_rules=self.dimension_rules,
        )


@dataclass(frozen=True)
class CohortAssignment:
    assignment_reference: str
    identity_reference: str
    source_asset_reference: str
    source_asset_sha256: str
    duplicate_cluster_reference: str | None
    split: EvaluationSplit
    dimension_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        for reference in (
            self.assignment_reference,
            self.identity_reference,
            self.source_asset_reference,
        ):
            _require_reference(reference)
        if self.duplicate_cluster_reference is not None:
            _require_reference(self.duplicate_cluster_reference)
        _require_sha256(self.source_asset_sha256)
        if not isinstance(self.split, EvaluationSplit):
            raise M5ValidationError(M5ReasonCode.INVALID_POLICY)
        if not self.dimension_keys or self.dimension_keys != tuple(
            sorted(set(self.dimension_keys))
        ):
            raise M5ValidationError(M5ReasonCode.UNKNOWN_DIMENSION)
        for dimension_key in self.dimension_keys:
            _require_key(dimension_key, M5ReasonCode.UNKNOWN_DIMENSION)


def validate_split_authority(assignments: Iterable[CohortAssignment]) -> None:
    """Reject identity, Asset, checksum, or duplicate-cluster leakage across splits."""
    split_by_key: dict[tuple[str, str], EvaluationSplit] = {}
    for assignment in assignments:
        keys = [
            ("identity", assignment.identity_reference),
            ("asset", assignment.source_asset_reference),
            ("sha256", assignment.source_asset_sha256),
        ]
        if assignment.duplicate_cluster_reference is not None:
            keys.append(("cluster", assignment.duplicate_cluster_reference))
        for key in keys:
            existing = split_by_key.setdefault(key, assignment.split)
            if existing is not assignment.split:
                raise M5ValidationError(M5ReasonCode.SPLIT_LEAKAGE)


def effective_holdout_count(assignments: Iterable[CohortAssignment], *, dimension_key: str) -> int:
    """Count holdout identities once per duplicate cluster for one dimension."""
    _require_key(dimension_key, M5ReasonCode.UNKNOWN_DIMENSION)
    materialized = tuple(assignments)
    validate_split_authority(materialized)
    effective_units: set[tuple[str, str]] = set()
    for assignment in materialized:
        if (
            assignment.split is EvaluationSplit.HOLDOUT
            and dimension_key in assignment.dimension_keys
        ):
            if assignment.duplicate_cluster_reference is None:
                effective_units.add(("identity", assignment.identity_reference))
            else:
                effective_units.add(("cluster", assignment.duplicate_cluster_reference))
    return len(effective_units)


def next_cohort_stage(effective_count: int) -> int | None:
    """Return the next preregistered 24→48→96 stage, then stop expansion."""
    if isinstance(effective_count, bool) or not isinstance(effective_count, int):
        raise M5ValidationError(M5ReasonCode.INVALID_COHORT_STAGE)
    if effective_count < 0:
        raise M5ValidationError(M5ReasonCode.INVALID_COHORT_STAGE)
    for stage in COHORT_STAGES:
        if effective_count < stage:
            return stage
    return None


@dataclass(frozen=True)
class ControlDelta:
    dimension_key: str
    absolute_delta_ppm: int

    def __post_init__(self) -> None:
        _require_key(self.dimension_key, M5ReasonCode.UNKNOWN_DIMENSION)
        _require_bounded_delta(self.absolute_delta_ppm, allow_negative=False)


@dataclass(frozen=True)
class IsolationObservation:
    transform_run_reference: str
    policy_version: str
    policy_digest: str
    target_dimension: str
    requested_delta_ppm: int
    measured_delta_ppm: int
    control_deltas: tuple[ControlDelta, ...]
    repeat_variance_ppm: int
    platform_variance_ppm: int
    artifact_gate_passed: bool
    reliability_gate_passed: bool

    def __post_init__(self) -> None:
        _require_reference(self.transform_run_reference)
        _require_version(self.policy_version)
        _require_sha256(self.policy_digest)
        _require_key(self.target_dimension, M5ReasonCode.UNKNOWN_DIMENSION)
        _require_bounded_delta(self.requested_delta_ppm, allow_negative=True)
        if self.requested_delta_ppm == 0:
            raise M5ValidationError(M5ReasonCode.INVALID_MEASUREMENT)
        _require_bounded_delta(self.measured_delta_ppm, allow_negative=True)
        keys = tuple(delta.dimension_key for delta in self.control_deltas)
        if not keys or keys != tuple(sorted(set(keys))):
            raise M5ValidationError(M5ReasonCode.MISSING_CONTROL_MEASUREMENT)
        if self.target_dimension in keys:
            raise M5ValidationError(M5ReasonCode.TARGET_CONTROL_CONFLICT)
        _require_bounded_delta(self.repeat_variance_ppm, allow_negative=False)
        _require_bounded_delta(self.platform_variance_ppm, allow_negative=False)
        if not isinstance(self.artifact_gate_passed, bool) or not isinstance(
            self.reliability_gate_passed, bool
        ):
            raise M5ValidationError(M5ReasonCode.INVALID_MEASUREMENT)


@dataclass(frozen=True)
class IsolationReportResult:
    transform_run_reference: str
    policy_version: str
    policy_digest: str
    target_dimension: str
    target_error_ppm: int
    non_target_drift_ppm: int
    conclusion: IsolationConclusion
    reason_codes: tuple[M5ReasonCode, ...]
    content_digest: str

    def __post_init__(self) -> None:
        _require_reference(self.transform_run_reference)
        _require_version(self.policy_version)
        _require_sha256(self.policy_digest)
        _require_key(self.target_dimension, M5ReasonCode.UNKNOWN_DIMENSION)
        _require_bounded_delta(
            self.target_error_ppm,
            allow_negative=False,
            maximum=MAX_TARGET_ERROR_PPM,
        )
        _require_bounded_delta(self.non_target_drift_ppm, allow_negative=False)
        if not isinstance(self.conclusion, IsolationConclusion):
            raise M5ValidationError(M5ReasonCode.INVALID_OUTCOME)
        if not all(isinstance(code, M5ReasonCode) for code in self.reason_codes):
            raise M5ValidationError(M5ReasonCode.INVALID_OUTCOME)
        if self.reason_codes != tuple(sorted(set(self.reason_codes), key=lambda code: code.value)):
            raise M5ValidationError(M5ReasonCode.INVALID_OUTCOME)
        if self.conclusion is IsolationConclusion.PASSED and self.reason_codes:
            raise M5ValidationError(M5ReasonCode.INVALID_OUTCOME)
        if self.conclusion is IsolationConclusion.REJECTED and not self.reason_codes:
            raise M5ValidationError(M5ReasonCode.INVALID_OUTCOME)
        _require_sha256(self.content_digest)
        if self.content_digest != _digest(
            ISOLATION_REPORT_RESULT_SCHEMA_VERSION, self._canonical_facts()
        ):
            raise M5ValidationError(M5ReasonCode.CONTENT_DIGEST_MISMATCH)

    def _canonical_facts(self) -> dict[str, object]:
        return {
            "conclusion": self.conclusion.value,
            "non_target_drift_ppm": self.non_target_drift_ppm,
            "policy_digest": self.policy_digest,
            "policy_version": self.policy_version,
            "reason_codes": [code.value for code in self.reason_codes],
            "target_dimension": self.target_dimension,
            "target_error_ppm": self.target_error_ppm,
            "transform_run_reference": self.transform_run_reference,
        }


def evaluate_isolation(
    *, policy: SyntheticEvaluationPolicy, observation: IsolationObservation
) -> IsolationReportResult:
    """Evaluate actual facts against a pre-existing immutable policy."""
    if (
        observation.policy_version != policy.version
        or observation.policy_digest != policy.content_digest
    ):
        raise M5ValidationError(M5ReasonCode.CONTENT_DIGEST_MISMATCH)
    rule = policy.rule_for(observation.target_dimension)
    observed_controls = tuple(delta.dimension_key for delta in observation.control_deltas)
    if observed_controls != rule.control_dimensions:
        raise M5ValidationError(M5ReasonCode.MISSING_CONTROL_MEASUREMENT)

    target_error_ppm = abs(observation.measured_delta_ppm - observation.requested_delta_ppm)
    non_target_drift_ppm = max(delta.absolute_delta_ppm for delta in observation.control_deltas)
    failures: list[M5ReasonCode] = []
    if (observation.requested_delta_ppm > 0) != (observation.measured_delta_ppm > 0):
        failures.append(M5ReasonCode.TARGET_DIRECTION_MISMATCH)
    if target_error_ppm > rule.target_error_tolerance_ppm:
        failures.append(M5ReasonCode.TARGET_ERROR_EXCEEDED)
    if non_target_drift_ppm > rule.control_drift_tolerance_ppm:
        failures.append(M5ReasonCode.CONTROL_DRIFT_EXCEEDED)
    if observation.repeat_variance_ppm > rule.repeat_variance_tolerance_ppm:
        failures.append(M5ReasonCode.REPEAT_VARIANCE_EXCEEDED)
    if observation.platform_variance_ppm > rule.platform_variance_tolerance_ppm:
        failures.append(M5ReasonCode.PLATFORM_VARIANCE_EXCEEDED)
    if not observation.artifact_gate_passed:
        failures.append(M5ReasonCode.ARTIFACT_GATE_FAILED)
    if not observation.reliability_gate_passed:
        failures.append(M5ReasonCode.RELIABILITY_GATE_FAILED)
    reason_codes = tuple(sorted(failures, key=lambda code: code.value))
    conclusion = IsolationConclusion.PASSED if not reason_codes else IsolationConclusion.REJECTED
    facts: dict[str, object] = {
        "conclusion": conclusion.value,
        "non_target_drift_ppm": non_target_drift_ppm,
        "policy_digest": policy.content_digest,
        "policy_version": policy.version,
        "reason_codes": [code.value for code in reason_codes],
        "target_dimension": observation.target_dimension,
        "target_error_ppm": target_error_ppm,
        "transform_run_reference": observation.transform_run_reference,
    }
    return IsolationReportResult(
        transform_run_reference=observation.transform_run_reference,
        policy_version=policy.version,
        policy_digest=policy.content_digest,
        target_dimension=observation.target_dimension,
        target_error_ppm=target_error_ppm,
        non_target_drift_ppm=non_target_drift_ppm,
        conclusion=conclusion,
        reason_codes=reason_codes,
        content_digest=_digest(ISOLATION_REPORT_RESULT_SCHEMA_VERSION, facts),
    )


@dataclass(frozen=True)
class M5Outcome:
    """Keep engineering correctness separate from research sufficiency."""

    technical_gate: TechnicalGateResult
    mvr_result: MvrResult

    def __post_init__(self) -> None:
        if not isinstance(self.technical_gate, TechnicalGateResult) or not isinstance(
            self.mvr_result, MvrResult
        ):
            raise M5ValidationError(M5ReasonCode.INVALID_OUTCOME)
        if self.technical_gate is TechnicalGateResult.FAIL and self.mvr_result is MvrResult.PASS:
            raise M5ValidationError(M5ReasonCode.INVALID_OUTCOME)


def _policy_facts(
    *,
    version: str,
    ontology_version: str,
    ontology_digest: str,
    measurement_policy_version: str,
    isolation_algorithm_version: str,
    duplicate_algorithm_version: str,
    split_rule_version: str,
    dimension_rules: tuple[EvaluationDimensionRule, ...],
) -> dict[str, object]:
    return {
        "cohort_stages": list(COHORT_STAGES),
        "dimension_rules": [rule.canonical_facts() for rule in dimension_rules],
        "duplicate_algorithm_version": duplicate_algorithm_version,
        "isolation_algorithm_version": isolation_algorithm_version,
        "measurement_policy_version": measurement_policy_version,
        "ontology_digest": ontology_digest,
        "ontology_version": ontology_version,
        "split_rule_version": split_rule_version,
        "version": version,
    }


def _digest(schema_version: str, facts: Mapping[str, object]) -> str:
    canonical = json.dumps(
        facts,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(f"{schema_version}\n{canonical}".encode()).hexdigest()


def _require_reference(value: str) -> None:
    if not isinstance(value, str) or _REFERENCE_PATTERN.fullmatch(value) is None:
        raise M5ValidationError(M5ReasonCode.INVALID_REFERENCE)


def _require_version(value: str) -> None:
    if not isinstance(value, str) or _VERSION_PATTERN.fullmatch(value) is None:
        raise M5ValidationError(M5ReasonCode.INVALID_POLICY)


def _require_key(value: str, reason_code: M5ReasonCode) -> None:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        raise M5ValidationError(reason_code)


def _require_region_group(value: str) -> None:
    _require_key(value, M5ReasonCode.INVALID_REGION_GROUP)
    if _FORBIDDEN_REGION_TOKENS & set(value.split("_")):
        raise M5ValidationError(M5ReasonCode.INVALID_REGION_GROUP)


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise M5ValidationError(M5ReasonCode.INVALID_CHECKSUM)


def _require_bounded_nonnegative_int(value: int, reason_code: M5ReasonCode) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_TOLERANCE_PPM:
        raise M5ValidationError(reason_code)


def _require_bounded_delta(
    value: int,
    *,
    allow_negative: bool,
    maximum: int = MAX_ABSOLUTE_DELTA_PPM,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M5ValidationError(M5ReasonCode.INVALID_MEASUREMENT)
    minimum = -maximum if allow_negative else 0
    if not minimum <= value <= maximum:
        raise M5ValidationError(M5ReasonCode.INVALID_MEASUREMENT)
