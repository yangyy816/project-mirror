"""CC02-A diagnosis-only failure taxonomy and report validators.

This module deliberately has no private-input, image, runtime, subprocess, or network
entry point.  CC02-B/C must provide their separately accepted authorities before a
private replay can use these pure, fail-closed helpers.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

from mirror_api.synthetic_dataset.domain import DomainValidationError, ReasonCode
from mirror_api.synthetic_dataset.similarity import SimilarityReasonCode, SimilarityValidationError

HARNESS_VERSION = "p2-m5-cc02-diagnostic-harness-v1"
TAXONOMY_VERSION = "p2-m5-cc02-terminal-taxonomy-v1"
PRIVATE_REPORT_SCHEMA = "mirror.p2-m5/CC02-private-platform-diagnostic-report/v1"
ACCEPTED_ALGORITHM_VERSION = "opencv-piecewise-affine-v1"

STAGES = (
    "SOURCE_ADMISSION",
    "SPECIFICATION",
    "CONTROL_POINT_BUILD",
    "WARP_PLAN_AUTHORITY",
    "TRANSFORM",
    "RESULT_VISION_QA",
    "MEASUREMENT_DIRECTION",
    "RESULT_SIGNATURE",
)
PLATFORMS = frozenset({"windows_x86_64", "linux_x86_64_network_none"})
CANDIDATES = frozenset(
    {"cheekbone_width", "chin_height", "eye_spacing", "jaw_width", "mouth_width", "nose_width"}
)
DIRECTIONS = frozenset({"INCREASE", "DECREASE"})
MAGNITUDES = frozenset({15000, 30000})
SHA256 = re.compile(r"[0-9a-f]{64}\Z")

GENERIC_REASONS: Mapping[str, frozenset[str]] = {
    "SOURCE_ADMISSION": frozenset(
        {
            "SOURCE_CHECKSUM_MISMATCH",
            "SOURCE_LANDMARK_EVIDENCE_MISMATCH",
            "SOURCE_ADMISSION_REJECTED",
        }
    ),
    "SPECIFICATION": frozenset({"SPECIFICATION_VALUE_REJECTED"}),
    "CONTROL_POINT_BUILD": frozenset({"CONTROL_POINT_VALUE_REJECTED"}),
    "WARP_PLAN_AUTHORITY": frozenset({"WARP_PLAN_VALUE_REJECTED"}),
    "TRANSFORM": frozenset(
        {"TRANSFORM_RUNTIME_REJECTED", "SAME_PLATFORM_NONDETERMINISM", "SOURCE_RESULT_IDENTICAL"}
    ),
    "RESULT_VISION_QA": frozenset({"RESULT_QA_FAILED", "RESULT_VISION_QA_REJECTED"}),
    "MEASUREMENT_DIRECTION": frozenset(
        {
            "MEASUREMENT_VALUE_REJECTED",
            "TARGET_DIRECTION_MISMATCH",
            "TARGET_DIRECTION_STABLE_MISMATCH",
            "MEASUREMENT_SIGN_UNSTABLE",
        }
    ),
    "RESULT_SIGNATURE": frozenset({"RESULT_SIGNATURE_VALUE_REJECTED"}),
}
DOMAIN_REASONS: Mapping[str, frozenset[ReasonCode]] = {
    "SOURCE_ADMISSION": frozenset(
        {
            ReasonCode.CHECKSUM_MISMATCH,
            ReasonCode.SYNTHETIC_ORIGIN_REQUIRED,
            ReasonCode.TRANSFORM_OUTPUT_INVALID,
            ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT,
            ReasonCode.INVALID_WARP_PLAN,
        }
    ),
    "SPECIFICATION": frozenset(
        {
            ReasonCode.UNKNOWN_GEOMETRY_DIMENSION,
            ReasonCode.UNSUPPORTED_DIMENSION,
            ReasonCode.REQUIRES_3D_RESEARCH,
            ReasonCode.STYLE_ONLY_DIMENSION,
            ReasonCode.INVALID_VARIANT_SPECIFICATION,
            ReasonCode.INVALID_DETERMINISM_CLAIM,
            ReasonCode.INVALID_RELATIVE_MAGNITUDE,
            ReasonCode.CONTROL_DIMENSION_REQUIRED,
            ReasonCode.TARGET_CONTROL_CONFLICT,
        }
    ),
    "CONTROL_POINT_BUILD": frozenset(
        {
            ReasonCode.INVALID_WARP_PLAN,
            ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT,
            ReasonCode.INSUFFICIENT_LANDMARK_CONFIDENCE,
        }
    ),
    "WARP_PLAN_AUTHORITY": frozenset(
        {
            ReasonCode.INVALID_WARP_PLAN,
            ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT,
            ReasonCode.INSUFFICIENT_LANDMARK_CONFIDENCE,
        }
    ),
    "TRANSFORM": frozenset(
        {
            ReasonCode.INVALID_WARP_PLAN,
            ReasonCode.SYNTHETIC_ORIGIN_REQUIRED,
            ReasonCode.CHECKSUM_MISMATCH,
            ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT,
            ReasonCode.INSUFFICIENT_LANDMARK_CONFIDENCE,
            ReasonCode.FOLDOVER_REJECTED,
            ReasonCode.TRANSFORM_RUNTIME_MISMATCH,
            ReasonCode.TRANSFORM_OUTPUT_INVALID,
            ReasonCode.SOURCE_RESULT_IDENTICAL,
        }
    ),
}
SIMILARITY_REASONS = frozenset(SimilarityReasonCode)

TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "harness_version",
        "taxonomy_version",
        "platform",
        "diagnostic_manifest_digest",
        "candidate_manifest_digest",
        "legacy_report_sha256",
        "legacy_report_digest",
        "cohort_digest",
        "case_set_digest",
        "runtime_manifest_digest",
        "model_sha256",
        "topology_sha256",
        "algorithm_version",
        "resource_usage",
        "resource_outcome",
        "terminal_failure_cases",
        "legacy_success_repeats",
        "direction_measurements",
        "report_digest",
    }
)
RESOURCE_KEYS = frozenset(
    {
        "identity_count",
        "candidate_count",
        "logical_case_count",
        "platform_case_count",
        "transform_execution_count",
        "vision_execution_count",
        "generation_attempt_count",
        "retry_count",
        "download_count",
        "max_concurrency",
        "execution_mode",
        "wall_clock_seconds",
        "private_output_bytes",
        "started_at_utc",
        "ended_at_utc",
    }
)
TERMINAL_KEYS = frozenset(
    {
        "case_digest",
        "candidate",
        "direction",
        "magnitude_ppm",
        "platform",
        "terminal_stage",
        "diagnostic_reason",
        "source_reason_family",
        "source_reason_code",
        "source_sha256",
        "result_sha256",
        "runtime_manifest_digest",
        "model_sha256",
        "topology_sha256",
        "plan_digest",
        "algorithm_version",
        "harness_version",
        "taxonomy_version",
        "signed_target_delta",
    }
)
REPEAT_KEYS = frozenset(
    {
        "case_digest",
        "candidate",
        "direction",
        "magnitude_ppm",
        "platform",
        "repeat_index",
        "source_sha256",
        "accepted_result_sha256",
        "recomputed_result_sha256",
        "legacy_row_digest",
        "runtime_manifest_digest",
        "model_sha256",
        "topology_sha256",
        "plan_digest",
        "algorithm_version",
    }
)
MEASUREMENT_KEYS = frozenset(
    {
        "case_digest",
        "candidate",
        "direction",
        "magnitude_ppm",
        "platform",
        "measurement_index",
        "source_sha256",
        "plan_digest",
        "recomputed_result_sha256",
        "signed_target_delta",
        "runtime_manifest_digest",
        "model_sha256",
        "topology_sha256",
        "algorithm_version",
        "harness_version",
        "taxonomy_version",
    }
)


class DiagnosticValidationError(ValueError):
    """A safe local validation error; callers must not serialize its text."""


class UnclassifiedTerminalFailure(DiagnosticValidationError):
    """A taxonomy breach that prevents construction of an accepted report."""


def _fail() -> NoReturn:
    raise DiagnosticValidationError("diagnostic validation failed")


def _unclassified() -> NoReturn:
    raise UnclassifiedTerminalFailure("UNCLASSIFIED_TERMINAL_FAILURE")


def _is_int(value: object) -> bool:
    return type(value) is int


def _sha(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _exact_keys(value: object, keys: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _fail()
    return value


def canonical_digest(schema: str, document: Mapping[str, Any], omitted: str) -> str:
    """Compute the contract's schema-prefixed canonical SHA-256 digest."""
    if not isinstance(schema, str) or not isinstance(omitted, str):
        _fail()
    facts = {key: value for key, value in document.items() if key != omitted}
    try:
        canonical = json.dumps(
            facts, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )
    except (TypeError, ValueError):
        _fail()
    return hashlib.sha256(f"{schema}\n{canonical}".encode()).hexdigest()


def legacy_row_digest(row: Mapping[str, Any]) -> str:
    try:
        canonical = json.dumps(
            dict(row), allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )
    except (TypeError, ValueError):
        _fail()
    return hashlib.sha256(
        f"mirror.p2-m5/CC01C-private-platform-report/v2#row\n{canonical}".encode()
    ).hexdigest()


def classify_exception(
    stage: str, exception: Exception, *, generic_reason: str | None = None
) -> tuple[str, str | None, str | None]:
    """Return only an allowlisted reason/family/code or hard-stop unclassified."""
    if stage not in STAGES:
        _unclassified()
    if isinstance(exception, DomainValidationError):
        code = exception.reason_code
        if code not in DOMAIN_REASONS.get(stage, frozenset()):
            _unclassified()
        return code.value, "DOMAIN", code.value
    if isinstance(exception, SimilarityValidationError):
        if stage != "RESULT_SIGNATURE" or exception.reason_code not in SIMILARITY_REASONS:
            _unclassified()
        return exception.reason_code.value, "SIMILARITY", exception.reason_code.value
    if type(exception) in {ValueError, RuntimeError}:
        if generic_reason not in GENERIC_REASONS[stage]:
            _unclassified()
        return generic_reason, None, None
    _unclassified()


def run_stage[T](
    stage: str, operation: Callable[[], T], *, generic_reason: str | None = None
) -> tuple[T | None, tuple[str, str | None, str | None] | None]:
    """Execute one explicit stage boundary without exposing exception content."""
    if stage not in STAGES:
        _unclassified()
    try:
        return operation(), None
    except (DomainValidationError, SimilarityValidationError, ValueError, RuntimeError) as error:
        return None, classify_exception(stage, error, generic_reason=generic_reason)
    except Exception:
        _unclassified()


def classify_direction_measurements(direction: str, values: Sequence[float]) -> str:
    """Classify the three frozen direction measurements without a tolerance."""
    if direction not in DIRECTIONS or len(values) != 3:
        _unclassified()
    if any(type(value) not in {int, float} or not math.isfinite(value) for value in values):
        _unclassified()
    signs = {1 if value > 0 else -1 if value < 0 else 0 for value in values}
    expected = 1 if direction == "INCREASE" else -1
    if signs == {-expected}:
        return "TARGET_DIRECTION_STABLE_MISMATCH"
    if signs == {expected}:
        _unclassified()
    return "MEASUREMENT_SIGN_UNSTABLE"


def validate_admission_counts(
    *,
    identity_count: object,
    candidate_count: object,
    logical_case_count: object,
    platform_case_count: object,
) -> None:
    """Reject a malformed non-private envelope before any external operation is possible."""
    if (
        type(identity_count) is not int
        or type(candidate_count) is not int
        or type(logical_case_count) is not int
        or type(platform_case_count) is not int
        or (identity_count, candidate_count, logical_case_count, platform_case_count)
        != (12, 6, 288, 576)
    ):
        _fail()


@dataclass
class ResourceCounter:
    """Fail-closed global operation counters for a serial diagnostic pair."""

    transform_execution_count: int = 0
    vision_execution_count: int = 0
    generation_attempt_count: int = 0
    retry_count: int = 0
    download_count: int = 0
    max_concurrency: int = 1
    execution_mode: str = "SERIAL"

    def validate_static(self) -> None:
        for value, ceiling in (
            (self.transform_execution_count, 576),
            (self.vision_execution_count, 604),
            (self.generation_attempt_count, 0),
            (self.retry_count, 0),
            (self.download_count, 0),
            (self.max_concurrency, 1),
        ):
            if type(value) is not int or value < 0 or value > ceiling:
                _fail()
        if (
            self.generation_attempt_count != 0
            or self.retry_count != 0
            or self.download_count != 0
            or self.max_concurrency != 1
            or self.execution_mode != "SERIAL"
        ):
            _fail()

    def reserve_transform(self) -> None:
        self.validate_static()
        if self.transform_execution_count >= 576:
            _fail()
        self.transform_execution_count += 1

    def reserve_vision(self) -> None:
        self.validate_static()
        if self.vision_execution_count >= 604:
            _fail()
        self.vision_execution_count += 1


@dataclass(frozen=True)
class ExpectedPlatformAuthority:
    """The explicit CC02-B authority required by every public validation path."""

    platform: str
    diagnostic_manifest_digest: str
    candidate_manifest_digest: str
    legacy_report_sha256: str
    legacy_report_digest: str
    cohort_digest: str
    case_set_digest: str
    runtime_manifest_digest: str
    model_sha256: str
    topology_sha256: str
    algorithm_version: str
    cases: tuple[ExpectedCaseAuthority, ...]


@dataclass(frozen=True)
class ExpectedCaseAuthority:
    case_digest: str
    candidate: str
    direction: str
    magnitude_ppm: int
    legacy_outcome: str
    direction_diagnostic: bool


@dataclass(frozen=True)
class OperationCounts:
    transform_execution_count: int
    vision_execution_count: int


def _expected_case_map(authority: ExpectedPlatformAuthority) -> dict[str, ExpectedCaseAuthority]:
    if type(authority) is not ExpectedPlatformAuthority or type(authority.cases) is not tuple:
        _fail()
    if (
        authority.platform not in PLATFORMS
        or authority.algorithm_version != ACCEPTED_ALGORITHM_VERSION
    ):
        _fail()
    if len(authority.cases) != 288:
        _fail()
    for case in authority.cases:
        if type(case) is not ExpectedCaseAuthority:
            _fail()
        if (
            not _sha(case.case_digest)
            or case.candidate not in CANDIDATES
            or case.direction not in DIRECTIONS
            or case.magnitude_ppm not in MAGNITUDES
            or case.legacy_outcome not in {"TERMINAL_FAILURE", "LEGACY_SUCCESS"}
            or type(case.direction_diagnostic) is not bool
            or (case.direction_diagnostic and case.legacy_outcome != "TERMINAL_FAILURE")
        ):
            _fail()
    mapped = {case.case_digest: case for case in authority.cases}
    if len(mapped) != 288:
        _fail()
    return mapped


def validate_resource_usage(
    usage: object, *, direction_case_count: int, operation_counts: OperationCounts
) -> dict[str, Any]:
    value = _exact_keys(usage, RESOURCE_KEYS)
    if (
        type(operation_counts) is not OperationCounts
        or not _is_int(direction_case_count)
        or not 0 <= direction_case_count <= 14
    ):
        _fail()
    exact = {
        "identity_count": 12,
        "candidate_count": 6,
        "logical_case_count": 288,
        "platform_case_count": 288,
        "generation_attempt_count": 0,
        "retry_count": 0,
        "download_count": 0,
        "max_concurrency": 1,
    }
    if any(
        value.get(key) != expected or type(value.get(key)) is not int
        for key, expected in exact.items()
    ):
        _fail()
    if (
        type(operation_counts.transform_execution_count) is not int
        or type(operation_counts.vision_execution_count) is not int
        or operation_counts.transform_execution_count < direction_case_count
        or operation_counts.vision_execution_count < 3 * direction_case_count
        or value["transform_execution_count"] != operation_counts.transform_execution_count
        or value["vision_execution_count"] != operation_counts.vision_execution_count
    ):
        _fail()
    if value.get("execution_mode") != "SERIAL":
        _fail()
    bounds = (
        ("transform_execution_count", 0, 288),
        ("vision_execution_count", 0, 288 + 2 * direction_case_count),
        ("wall_clock_seconds", 0, 7200),
        ("private_output_bytes", 0, 4_294_967_296),
    )
    if any(
        not _is_int(value.get(key)) or not lower <= value[key] <= upper
        for key, lower, upper in bounds
    ):
        _fail()
    timestamps: list[int] = []
    for key in ("started_at_utc", "ended_at_utc"):
        raw = value.get(key)
        if (
            not isinstance(raw, str)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw) is None
        ):
            _fail()
        try:
            from datetime import datetime

            timestamps.append(int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()))
        except ValueError:
            _fail()
    if timestamps[1] - timestamps[0] != value["wall_clock_seconds"]:
        _fail()
    return value


def _validate_case_identity(row: Mapping[str, Any], platform: str) -> None:
    if (
        not _sha(row.get("case_digest"))
        or row.get("candidate") not in CANDIDATES
        or row.get("direction") not in DIRECTIONS
        or row.get("magnitude_ppm") not in MAGNITUDES
        or row.get("platform") != platform
    ):
        _fail()


def _validate_authority(row: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    for key in ("runtime_manifest_digest", "model_sha256", "topology_sha256", "algorithm_version"):
        if row.get(key) != report.get(key):
            _fail()


def _nullable_sha(value: object) -> bool:
    return value is None or _sha(value)


def _validate_terminal(row: object, report: Mapping[str, Any]) -> dict[str, Any]:
    value = _exact_keys(row, TERMINAL_KEYS)
    _validate_case_identity(value, report["platform"])
    _validate_authority(value, report)
    stage = value.get("terminal_stage")
    reason = value.get("diagnostic_reason")
    if (
        not isinstance(stage, str)
        or stage not in STAGES
        or not isinstance(reason, str)
        or value.get("harness_version") != HARNESS_VERSION
        or value.get("taxonomy_version") != TAXONOMY_VERSION
    ):
        _fail()
    family, code = value.get("source_reason_family"), value.get("source_reason_code")
    if family is None and code is None:
        if reason not in GENERIC_REASONS[stage]:
            _fail()
    elif family == "DOMAIN" and isinstance(code, str):
        try:
            source_code = ReasonCode(code)
        except ValueError:
            _fail()
        if source_code not in DOMAIN_REASONS.get(stage, frozenset()) or reason != code:
            _fail()
    elif family == "SIMILARITY" and isinstance(code, str):
        try:
            similarity_code = SimilarityReasonCode(code)
        except ValueError:
            _fail()
        if (
            stage != "RESULT_SIGNATURE"
            or similarity_code not in SIMILARITY_REASONS
            or reason != code
        ):
            _fail()
    else:
        _fail()
    if (
        not _nullable_sha(value.get("source_sha256"))
        or not _nullable_sha(value.get("plan_digest"))
        or not _nullable_sha(value.get("result_sha256"))
    ):
        _fail()
    stage_index = STAGES.index(stage)
    if value["source_sha256"] is None and stage != "SOURCE_ADMISSION":
        _fail()
    if value["plan_digest"] is None and stage_index > STAGES.index("WARP_PLAN_AUTHORITY"):
        _fail()
    if value["result_sha256"] is None and stage_index > STAGES.index("TRANSFORM"):
        _fail()
    if value["signed_target_delta"] is not None:
        _fail()
    return value


def _validate_repeat(row: object, report: Mapping[str, Any]) -> dict[str, Any]:
    value = _exact_keys(row, REPEAT_KEYS)
    _validate_case_identity(value, report["platform"])
    _validate_authority(value, report)
    if value.get("repeat_index") not in {1, 2, 3}:
        _fail()
    for key in (
        "source_sha256",
        "accepted_result_sha256",
        "recomputed_result_sha256",
        "legacy_row_digest",
        "plan_digest",
    ):
        if not _sha(value.get(key)):
            _fail()
    if value["accepted_result_sha256"] != value["recomputed_result_sha256"]:
        raise DiagnosticValidationError("TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT")
    return value


def _validate_measurement(row: object, report: Mapping[str, Any]) -> dict[str, Any]:
    value = _exact_keys(row, MEASUREMENT_KEYS)
    _validate_case_identity(value, report["platform"])
    _validate_authority(value, report)
    if (
        value.get("measurement_index") not in {1, 2, 3}
        or value.get("harness_version") != HARNESS_VERSION
        or value.get("taxonomy_version") != TAXONOMY_VERSION
    ):
        _fail()
    for key in ("source_sha256", "plan_digest", "recomputed_result_sha256"):
        if not _sha(value.get(key)):
            _fail()
    delta = value.get("signed_target_delta")
    if type(delta) not in {int, float} or not math.isfinite(cast(float, delta)):
        _fail()
    return value


def validate_legacy_bindings(
    repeats: Iterable[Mapping[str, Any]], accepted_rows: Iterable[Mapping[str, Any]]
) -> None:
    """Prove each repeat binds exactly one supplied accepted legacy row, without I/O."""
    repeat_rows = list(repeats)
    accepted = list(accepted_rows)
    index: dict[str, list[Mapping[str, Any]]] = {}
    for row in accepted:
        index.setdefault(legacy_row_digest(row), []).append(row)
    for repeat in repeat_rows:
        matches = index.get(str(repeat.get("legacy_row_digest")), [])
        if len(matches) != 1:
            _fail()
        source = matches[0]
        fields = (
            "case_digest",
            "candidate",
            "direction",
            "magnitude_ppm",
            "source_sha256",
            "plan_digest",
        )
        if (
            any(source.get(field) != repeat.get(field) for field in fields)
            or source.get("repeat") != repeat.get("repeat_index")
            or source.get("result_sha256") != repeat.get("accepted_result_sha256")
        ):
            _fail()
    if sum(len(matches) for matches in index.values()) != len(repeat_rows):
        _fail()


def validate_legacy_report_bytes(
    repeats: Iterable[Mapping[str, Any]],
    report: Mapping[str, Any],
    legacy_report_bytes: bytes,
    expected: ExpectedPlatformAuthority,
) -> None:
    """Bind supplied accepted legacy-report bytes without opening a private path.

    A later authorized caller supplies already-admitted bytes.  This helper validates
    their byte SHA, report digest, report-level authority and per-row projections.
    """
    if type(legacy_report_bytes) is not bytes:
        _fail()
    if hashlib.sha256(legacy_report_bytes).hexdigest() != report.get("legacy_report_sha256"):
        _fail()
    try:
        legacy_report = json.loads(legacy_report_bytes)
    except (TypeError, ValueError, json.JSONDecodeError):
        _fail()
    if (
        not isinstance(legacy_report, dict)
        or legacy_report.get("schema") != "mirror.p2-m5/CC01C-private-platform-report/v2"
        or legacy_report.get("report_digest") != report.get("legacy_report_digest")
        or legacy_report.get("report_digest")
        != canonical_digest(
            "mirror.p2-m5/CC01C-private-platform-report/v2", legacy_report, "report_digest"
        )
    ):
        _fail()
    for key in (
        "platform",
        "runtime_manifest_digest",
        "model_sha256",
        "topology_sha256",
        "candidate_manifest_digest",
        "cohort_digest",
        "case_set_digest",
    ):
        if legacy_report.get(key) != report.get(key):
            _fail()
    rows = legacy_report.get("rows")
    cases = legacy_report.get("cases")
    expected_cases = _expected_case_map(expected)
    if not isinstance(rows, list) or not isinstance(cases, list) or len(cases) != 288:
        _fail()
    legacy_cases = {case.get("case_digest"): case for case in cases if isinstance(case, dict)}
    if len(legacy_cases) != 288 or set(legacy_cases) != set(expected_cases):
        _fail()
    for digest, authority_case in expected_cases.items():
        legacy_case = legacy_cases[digest]
        if (
            legacy_case.get("candidate"),
            legacy_case.get("direction"),
            legacy_case.get("magnitude_ppm"),
        ) != (authority_case.candidate, authority_case.direction, authority_case.magnitude_ppm):
            _fail()
        status = legacy_case.get("status")
        if status not in {"FAILED", "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW"}:
            _fail()
        is_terminal = status == "FAILED"
        is_direction = (
            legacy_case.get("failure_stage") == "MEASUREMENT"
            and legacy_case.get("failure_code") == "TARGET_DIRECTION_MISMATCH"
        )
        if (
            is_terminal != (authority_case.legacy_outcome == "TERMINAL_FAILURE")
            or is_direction != authority_case.direction_diagnostic
        ):
            _fail()
    validate_legacy_bindings(repeats, cast(list[Mapping[str, Any]], rows))


def _validate_report(
    report: object, *, expected: ExpectedPlatformAuthority, operation_counts: OperationCounts
) -> dict[str, Any]:
    """Validate one fully assembled diagnostic report before any output is created."""
    value = _exact_keys(report, TOP_LEVEL_KEYS)
    expected_cases = _expected_case_map(expected)
    if (
        value.get("schema") != PRIVATE_REPORT_SCHEMA
        or value.get("harness_version") != HARNESS_VERSION
        or value.get("taxonomy_version") != TAXONOMY_VERSION
        or value.get("platform") not in PLATFORMS
    ):
        _fail()
    for key in (
        "diagnostic_manifest_digest",
        "candidate_manifest_digest",
        "legacy_report_sha256",
        "legacy_report_digest",
        "cohort_digest",
        "case_set_digest",
        "runtime_manifest_digest",
        "model_sha256",
        "topology_sha256",
    ):
        if not _sha(value.get(key)):
            _fail()
    if value.get("algorithm_version") != ACCEPTED_ALGORITHM_VERSION:
        _fail()
    for key in (
        "platform",
        "diagnostic_manifest_digest",
        "candidate_manifest_digest",
        "legacy_report_sha256",
        "legacy_report_digest",
        "cohort_digest",
        "case_set_digest",
        "runtime_manifest_digest",
        "model_sha256",
        "topology_sha256",
        "algorithm_version",
    ):
        if value.get(key) != getattr(expected, key):
            _fail()
    terminals = value.get("terminal_failure_cases")
    repeats = value.get("legacy_success_repeats")
    measurements = value.get("direction_measurements")
    if not all(isinstance(rows, list) for rows in (terminals, repeats, measurements)):
        _fail()
    terminal_rows = cast(list[dict[str, Any]], terminals)
    repeat_rows = cast(list[dict[str, Any]], repeats)
    measurement_rows = cast(list[dict[str, Any]], measurements)
    checked_terminals = [_validate_terminal(row, value) for row in terminal_rows]
    checked_repeats = [_validate_repeat(row, value) for row in repeat_rows]
    checked_measurements = [_validate_measurement(row, value) for row in measurement_rows]
    if terminal_rows != sorted(terminal_rows, key=lambda row: row["case_digest"]):
        _fail()
    if repeat_rows != sorted(
        repeat_rows, key=lambda row: (row["case_digest"], row["repeat_index"])
    ):
        _fail()
    if measurement_rows != sorted(
        measurement_rows, key=lambda row: (row["case_digest"], row["measurement_index"])
    ):
        _fail()
    terminal_by_case = {cast(str, row["case_digest"]): row for row in checked_terminals}
    if len(terminal_by_case) != len(checked_terminals):
        _fail()
    terminal_cases = set(terminal_by_case)
    repeat_cases = {cast(str, row["case_digest"]) for row in checked_repeats}
    if len(terminal_cases | repeat_cases) != 288 or terminal_cases & repeat_cases:
        _fail()
    for digest, row in terminal_by_case.items():
        authority_case = expected_cases.get(digest)
        if authority_case is None or authority_case.legacy_outcome != "TERMINAL_FAILURE":
            _fail()
        if (row["candidate"], row["direction"], row["magnitude_ppm"]) != (
            authority_case.candidate,
            authority_case.direction,
            authority_case.magnitude_ppm,
        ):
            _fail()
    for digest in repeat_cases:
        authority_case = expected_cases.get(digest)
        if authority_case is None or authority_case.legacy_outcome != "LEGACY_SUCCESS":
            _fail()
    grouped_repeats: dict[str, list[dict[str, Any]]] = {}
    for row in checked_repeats:
        grouped_repeats.setdefault(row["case_digest"], []).append(row)
    if any(
        {row["repeat_index"] for row in group} != {1, 2, 3} or len(group) != 3
        for group in grouped_repeats.values()
    ):
        _fail()
    for group in grouped_repeats.values():
        authority_case = expected_cases.get(group[0]["case_digest"])
        if authority_case is None or (
            group[0]["candidate"],
            group[0]["direction"],
            group[0]["magnitude_ppm"],
        ) != (authority_case.candidate, authority_case.direction, authority_case.magnitude_ppm):
            _fail()
        for key in (
            "case_digest",
            "candidate",
            "direction",
            "magnitude_ppm",
            "platform",
            "source_sha256",
            "plan_digest",
            "accepted_result_sha256",
            "recomputed_result_sha256",
        ):
            if len({row[key] for row in group}) != 1:
                _fail()
    grouped_measurements: dict[str, list[dict[str, Any]]] = {}
    for row in checked_measurements:
        grouped_measurements.setdefault(row["case_digest"], []).append(row)
    direction_terminals = {
        row["case_digest"]
        for row in checked_terminals
        if row["terminal_stage"] == "MEASUREMENT_DIRECTION"
    }
    expected_direction = {
        digest for digest, case in expected_cases.items() if case.direction_diagnostic
    }
    if (
        len(grouped_measurements) > 14
        or set(grouped_measurements) != direction_terminals
        or direction_terminals != expected_direction
    ):
        _fail()
    for digest, group in grouped_measurements.items():
        terminal = terminal_by_case.get(digest)
        if terminal is None:
            _fail()
        if (
            terminal["terminal_stage"] != "MEASUREMENT_DIRECTION"
            or len(group) != 3
            or {row["measurement_index"] for row in group} != {1, 2, 3}
        ):
            _fail()
        shared = {
            key: {row[key] for row in group}
            for key in ("source_sha256", "plan_digest", "recomputed_result_sha256")
        }
        if (
            any(len(values) != 1 for values in shared.values())
            or terminal["source_sha256"] not in shared["source_sha256"]
            or terminal["plan_digest"] not in shared["plan_digest"]
            or terminal["result_sha256"] not in shared["recomputed_result_sha256"]
        ):
            _fail()
        for key in ("candidate", "direction", "magnitude_ppm", "platform"):
            if any(row[key] != terminal[key] for row in group):
                _fail()
        if terminal["diagnostic_reason"] != classify_direction_measurements(
            terminal["direction"], [row["signed_target_delta"] for row in group]
        ):
            _fail()
    validate_resource_usage(
        value["resource_usage"],
        direction_case_count=len(grouped_measurements),
        operation_counts=operation_counts,
    )
    if value.get("resource_outcome") != "WITHIN_ENVELOPE" or value.get(
        "report_digest"
    ) != canonical_digest(PRIVATE_REPORT_SCHEMA, value, "report_digest"):
        _fail()
    return value


def validate_report_pair(
    left: object,
    right: object,
    *,
    expected_authorities: Mapping[str, ExpectedPlatformAuthority],
    legacy_report_bytes: Mapping[str, bytes],
    operation_counts: Mapping[str, OperationCounts],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the frozen two-platform cardinalities and non-overlapping serial windows."""
    if (
        not isinstance(expected_authorities, Mapping)
        or not isinstance(legacy_report_bytes, Mapping)
        or not isinstance(operation_counts, Mapping)
        or set(expected_authorities) != PLATFORMS
        or set(legacy_report_bytes) != PLATFORMS
        or set(operation_counts) != PLATFORMS
    ):
        _fail()
    if any(
        type(value) is not ExpectedPlatformAuthority for value in expected_authorities.values()
    ) or any(type(value) is not OperationCounts for value in operation_counts.values()):
        _fail()
    reports = (
        _validate_report(
            left,
            expected=expected_authorities["windows_x86_64"],
            operation_counts=operation_counts["windows_x86_64"],
        ),
        _validate_report(
            right,
            expected=expected_authorities["linux_x86_64_network_none"],
            operation_counts=operation_counts["linux_x86_64_network_none"],
        ),
    )
    if {report["platform"] for report in reports} != PLATFORMS:
        _fail()
    expected_maps = {
        platform: _expected_case_map(authority)
        for platform, authority in expected_authorities.items()
    }
    if set(expected_maps["windows_x86_64"]) != set(expected_maps["linux_x86_64_network_none"]):
        _fail()
    for digest, left_case in expected_maps["windows_x86_64"].items():
        right_case = expected_maps["linux_x86_64_network_none"][digest]
        if (left_case.candidate, left_case.direction, left_case.magnitude_ppm) != (
            right_case.candidate,
            right_case.direction,
            right_case.magnitude_ppm,
        ):
            _fail()
    for key in (
        "diagnostic_manifest_digest",
        "candidate_manifest_digest",
        "cohort_digest",
        "case_set_digest",
        "model_sha256",
        "topology_sha256",
        "algorithm_version",
    ):
        if reports[0][key] != reports[1][key]:
            _fail()
    all_terminals = [row for report in reports for row in report["terminal_failure_cases"]]
    all_repeat_cases = {
        row["case_digest"] for report in reports for row in report["legacy_success_repeats"]
    }
    all_repeats = [row for report in reports for row in report["legacy_success_repeats"]]
    all_measurements = [row for report in reports for row in report["direction_measurements"]]
    if (
        len(all_terminals) != 232
        or len(all_repeat_cases) != 172
        or len(all_repeats) != 1032
        or len(all_measurements) != 42
    ):
        _fail()
    if (
        sum(
            case.legacy_outcome == "TERMINAL_FAILURE"
            for cases in expected_maps.values()
            for case in cases.values()
        )
        != 232
        or sum(
            case.legacy_outcome == "LEGACY_SUCCESS"
            for cases in expected_maps.values()
            for case in cases.values()
        )
        != 344
        or sum(
            case.direction_diagnostic for cases in expected_maps.values() for case in cases.values()
        )
        != 14
    ):
        _fail()
    if (
        sum(
            row["terminal_stage"] == "MEASUREMENT_DIRECTION"
            for report in reports
            for row in report["terminal_failure_cases"]
        )
        != 14
    ):
        _fail()
    logical: dict[str, set[str]] = {}
    for report in reports:
        cases = {row["case_digest"] for row in report["terminal_failure_cases"]} | {
            row["case_digest"] for row in report["legacy_success_repeats"]
        }
        for digest in cases:
            logical.setdefault(digest, set()).add(report["platform"])
    if len(logical) != 288 or any(platforms != PLATFORMS for platforms in logical.values()):
        _fail()
    descriptors: dict[str, set[tuple[Any, ...]]] = {}
    for report in reports:
        for collection in ("terminal_failure_cases", "legacy_success_repeats"):
            for row in report[collection]:
                descriptors.setdefault(row["case_digest"], set()).add(
                    (row["candidate"], row["direction"], row["magnitude_ppm"])
                )
    if any(len(values) != 1 for values in descriptors.values()):
        _fail()
    intervals = []
    for report in reports:
        usage = report["resource_usage"]
        from datetime import datetime

        intervals.append(
            (
                datetime.fromisoformat(usage["started_at_utc"].replace("Z", "+00:00")),
                datetime.fromisoformat(usage["ended_at_utc"].replace("Z", "+00:00")),
            )
        )
    if max(start for start, _ in intervals) < min(end for _, end in intervals):
        _fail()
    if (
        sum(report["resource_usage"]["wall_clock_seconds"] for report in reports) > 14400
        or sum(report["resource_usage"]["transform_execution_count"] for report in reports) > 576
        or sum(report["resource_usage"]["vision_execution_count"] for report in reports) > 604
    ):
        _fail()
    for report in reports:
        validate_legacy_report_bytes(
            report["legacy_success_repeats"],
            report,
            legacy_report_bytes[report["platform"]],
            expected_authorities[report["platform"]],
        )
    return reports


def write_report_pair_once(
    left: object,
    right: object,
    *,
    expected_authorities: Mapping[str, ExpectedPlatformAuthority],
    legacy_report_bytes: Mapping[str, bytes],
    operation_counts: Mapping[str, OperationCounts],
    output_root: Path,
) -> None:
    """Create a root only after complete pair, authority and legacy-byte validation."""
    checked = validate_report_pair(
        left,
        right,
        expected_authorities=expected_authorities,
        legacy_report_bytes=legacy_report_bytes,
        operation_counts=operation_counts,
    )
    if output_root.exists():
        _fail()
    output_root.mkdir(parents=True, exist_ok=False)
    for report in checked:
        output = output_root / f"{report['platform']}.json"
        payload = (
            json.dumps(report, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        )
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
