"""Pure public-evidence qualification for the D08 fixed Geometry matrix."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from mirror_api.demo_d08_geometry_adapter import D08_VERIFIER_POLICY_VERSION
from mirror_api.demo_d08_geometry_verifier import (
    D08_GEOMETRY_METRICS_SCHEMA,
    D08_GEOMETRY_THRESHOLDS_SCHEMA,
)
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest

GEOMETRY_MATRIX_QUALIFICATION_SCHEMA: Final = "mirror.demo/GeometryMatrixQualification/v1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")
_FIXED18 = re.compile(r"-?(?:0|[1-9][0-9]*)\.\d{18}\Z")
_SOURCES: Final = (1, 2, 3, 4)
_DIMENSIONS: Final = ("jaw_width", "chin_height", "eye_spacing")
_DIRECTIONS: Final = ("DECREASE", "INCREASE")
_MAGNITUDES: Final = (15_000, 30_000)
_REPEATS: Final = (1, 2, 3)
_MEASUREMENT_DIMENSIONS: Final = (
    "cheekbone_width",
    "chin_height",
    "eye_spacing",
    "jaw_width",
    "mouth_width",
    "nose_width",
)
_REPEAT_GROUP_KEYS: Final = frozenset(
    {
        "repeat_indexes_complete",
        "source_receipts_fresh",
        "result_receipts_fresh",
        "source_outputs_fresh",
        "result_outputs_fresh",
        "source_landmarks_stable",
        "result_landmarks_stable",
    }
)


class GeometryMatrixQualificationInputError(ValueError):
    """Raised when public terminal evidence is not the frozen verifier schema."""


@dataclass(frozen=True, slots=True)
class GeometryTerminalVerification:
    verification_digest: str
    metrics: Mapping[str, object]
    thresholds: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class GeometryMatrixQualification:
    status: str
    evidence: Mapping[str, object]
    cross_case_digest: str


def qualify_geometry_matrix(
    terminal_verifications: Sequence[GeometryTerminalVerification],
) -> GeometryMatrixQualification:
    """Qualify the complete 4 x 3 x 2 x 2 public D08 Geometry matrix."""

    if len(terminal_verifications) != 48:
        raise GeometryMatrixQualificationInputError("matrix must contain exactly 48 terminals")
    normalized = tuple(_normalize_terminal(item) for item in terminal_verifications)
    _validate_matrix_membership(normalized)
    ordered = tuple(
        sorted(normalized, key=lambda item: cast(tuple[int, int, int, int], item["sort_key"]))
    )
    terminal_records: list[dict[str, object]] = []
    ordered_deltas: list[dict[str, object]] = []
    all_terminal_gates = True
    by_pair: dict[tuple[int, str, str], dict[int, dict[int, int]]] = {}
    for terminal in ordered:
        metrics = cast(dict[str, object], terminal["metrics"])
        terminal_gate = _terminal_gate(metrics)
        all_terminal_gates = all_terminal_gates and terminal_gate
        terminal_records.append(
            {
                "case_id": cast(str, metrics["case_id"]),
                "case_ordinal": cast(int, metrics["case_ordinal"]),
                "terminal_gate_passed": terminal_gate,
                "verification_digest": terminal["verification_digest"],
            }
        )
        pair = (
            cast(int, metrics["source_ordinal"]),
            cast(str, metrics["dimension_key"]),
            cast(str, metrics["direction"]),
        )
        deltas = by_pair.setdefault(pair, {})
        for repeat_record in cast(list[dict[str, object]], metrics["repeats"]):
            repeat_index = cast(int, repeat_record["repeat_index"])
            delta = cast(int, repeat_record["signed_target_delta_ppm"])
            deltas.setdefault(repeat_index, {})[cast(int, metrics["magnitude_ppm"])] = delta
            ordered_deltas.append(
                {
                    "case_id": cast(str, metrics["case_id"]),
                    "case_ordinal": cast(int, metrics["case_ordinal"]),
                    "dimension_key": cast(str, metrics["dimension_key"]),
                    "direction": cast(str, metrics["direction"]),
                    "magnitude_ppm": cast(int, metrics["magnitude_ppm"]),
                    "repeat_index": repeat_index,
                    "signed_target_delta_ppm": delta,
                    "source_ordinal": cast(int, metrics["source_ordinal"]),
                }
            )
    comparisons: list[dict[str, object]] = []
    monotonic_passed = True
    for source in _SOURCES:
        for dimension in _DIMENSIONS:
            for direction in _DIRECTIONS:
                values = by_pair[(source, dimension, direction)]
                for repeat in _REPEATS:
                    low, high = values[repeat][15_000], values[repeat][30_000]
                    passed = abs(high) >= abs(low)
                    monotonic_passed = monotonic_passed and passed
                    comparisons.append(
                        {
                            "abs_15000_delta_ppm": abs(low),
                            "abs_30000_delta_ppm": abs(high),
                            "dimension_key": dimension,
                            "direction": direction,
                            "monotonic_passed": passed,
                            "repeat_index": repeat,
                            "source_ordinal": source,
                        }
                    )
    status = "PASS" if all_terminal_gates and monotonic_passed else "FAIL"
    payload: dict[str, object] = {
        "schema_version": GEOMETRY_MATRIX_QUALIFICATION_SCHEMA,
        "status": status,
        "policy_version": D08_VERIFIER_POLICY_VERSION,
        "ordered_terminal_verifications": terminal_records,
        "ordered_repeat_deltas": ordered_deltas,
        "monotonic_comparisons": comparisons,
    }
    digest = mirror_demo_digest(
        GEOMETRY_MATRIX_QUALIFICATION_SCHEMA, cast(Mapping[str, JsonValue], payload)
    )
    evidence = {**payload, "cross_case_digest": digest}
    return GeometryMatrixQualification(status=status, evidence=evidence, cross_case_digest=digest)


def _normalize_terminal(value: GeometryTerminalVerification) -> dict[str, object]:
    if not isinstance(value, GeometryTerminalVerification):
        raise GeometryMatrixQualificationInputError("terminal must be GeometryTerminalVerification")
    _require_digest(value.verification_digest, "verification digest")
    metrics = _normalize_metrics(value.metrics)
    _validate_thresholds(value.thresholds)
    return {
        "metrics": metrics,
        "verification_digest": value.verification_digest,
        "sort_key": (
            metrics["source_ordinal"],
            _DIMENSIONS.index(metrics["dimension_key"]),
            _DIRECTIONS.index(metrics["direction"]),
            _MAGNITUDES.index(metrics["magnitude_ppm"]),
        ),
    }


def _normalize_metrics(value: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version",
        "authority_digest",
        "stable_core_digest",
        "attempt_receipt_digest",
        "operation_id",
        "operation_authority_digest",
        "operation_spec_digest",
        "case_id",
        "case_ordinal",
        "source_ordinal",
        "source_asset_id",
        "result_sha256",
        "source_sha256",
        "dimension_key",
        "direction",
        "magnitude_ppm",
        "source_result_digest_distinct",
        "source_digest_after_verification",
        "original_immutability_passed",
        "decode_passed",
        "artifact_passed",
        "runtime_identity",
        "d08_verifier_policy_version",
        "measurement_dimension_order",
        "repeats",
        "repeat_gate_passed",
        "repeat_group_validation",
        "max_non_target_drift_ppm",
        "max_non_target_dimension_key",
        "max_non_target_repeat_index",
    }
    _require_exact_keys(value, expected, "metrics")
    if value["schema_version"] != D08_GEOMETRY_METRICS_SCHEMA:
        raise GeometryMatrixQualificationInputError("metrics schema mismatch")
    for key in (
        "authority_digest",
        "stable_core_digest",
        "attempt_receipt_digest",
        "operation_authority_digest",
        "operation_spec_digest",
        "result_sha256",
        "source_sha256",
        "source_digest_after_verification",
    ):
        _require_digest(value[key], key)
    for key in ("operation_id", "case_id", "source_asset_id"):
        _require_id(value[key], key)
    if not isinstance(value["case_ordinal"], int) or isinstance(value["case_ordinal"], bool):
        raise GeometryMatrixQualificationInputError("case ordinal must be an integer")
    if value["source_ordinal"] not in _SOURCES:
        raise GeometryMatrixQualificationInputError("source ordinal is invalid")
    if value["dimension_key"] not in _DIMENSIONS or value["direction"] not in _DIRECTIONS:
        raise GeometryMatrixQualificationInputError("matrix dimension or direction is invalid")
    if value["magnitude_ppm"] not in _MAGNITUDES:
        raise GeometryMatrixQualificationInputError("matrix magnitude is invalid")
    if value["d08_verifier_policy_version"] != D08_VERIFIER_POLICY_VERSION:
        raise GeometryMatrixQualificationInputError("D08 verifier policy version mismatch")
    if value["measurement_dimension_order"] != list(_MEASUREMENT_DIMENSIONS):
        raise GeometryMatrixQualificationInputError("measurement dimension order mismatch")
    if value["source_digest_after_verification"] != value["source_sha256"]:
        raise GeometryMatrixQualificationInputError("source digest changed during verification")
    _validate_runtime_identity(value["runtime_identity"])
    repeats = _normalize_repeats(value["repeats"], value["dimension_key"])
    repeat_group = value["repeat_group_validation"]
    if not isinstance(repeat_group, Mapping):
        raise GeometryMatrixQualificationInputError("repeat group validation is invalid")
    _require_exact_keys(repeat_group, _REPEAT_GROUP_KEYS, "repeat group validation")
    if any(not isinstance(item, bool) for item in repeat_group.values()):
        raise GeometryMatrixQualificationInputError("repeat group flags must be bool")
    if dict(repeat_group) != _replay_repeat_group(repeats):
        raise GeometryMatrixQualificationInputError("repeat group flags do not replay")
    for key in (
        "source_result_digest_distinct",
        "original_immutability_passed",
        "decode_passed",
        "artifact_passed",
        "repeat_gate_passed",
    ):
        if not isinstance(value[key], bool):
            raise GeometryMatrixQualificationInputError(f"{key} must be bool")
    controls = tuple(
        (
            cast(int, repeat["repeat_index"]),
            cast(str, dimension),
            cast(int, drift),
        )
        for repeat in repeats
        for dimension, drift in zip(
            cast(list[object], repeat["control_dimensions"]),
            cast(list[object], repeat["control_drifts_ppm"]),
            strict=True,
        )
    )
    maximum = max((item[2] for item in controls), default=-1)
    winner = next((item for item in controls if item[2] == maximum), None)
    if value["max_non_target_drift_ppm"] != maximum:
        raise GeometryMatrixQualificationInputError("maximum control drift does not match repeats")
    if (
        winner is None
        or value["max_non_target_repeat_index"] != winner[0]
        or value["max_non_target_dimension_key"] != winner[1]
    ):
        raise GeometryMatrixQualificationInputError("maximum control winner does not replay")
    return {**value, "repeats": repeats, "repeat_group_validation": dict(repeat_group)}


def _normalize_repeats(value: object, target_dimension: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or len(value) != 3:
        raise GeometryMatrixQualificationInputError("repeats must have exactly three items")
    expected = {
        "control_drift_passed",
        "control_dimensions",
        "control_drifts_ppm",
        "direction_passed",
        "observation_passed",
        "repeat_index",
        "max_control_dimension_key",
        "max_control_drift_ppm",
        "result_landmark_digest",
        "result_measurements_fixed18",
        "result_observation_digest",
        "result_output_digest",
        "result_receipt_digest",
        "signed_target_delta_ppm",
        "source_landmark_digest",
        "source_measurements_fixed18",
        "source_observation_digest",
        "source_output_digest",
        "source_receipt_digest",
        "target_maximum_passed",
        "target_minimum_passed",
    }
    normalized: list[dict[str, object]] = []
    for index, repeat in enumerate(value, start=1):
        if not isinstance(repeat, Mapping):
            raise GeometryMatrixQualificationInputError("repeat is invalid")
        _require_exact_keys(repeat, expected, "repeat")
        if repeat["repeat_index"] != index:
            raise GeometryMatrixQualificationInputError("repeat indexes must be 1, 2, 3")
        for key in (
            "result_landmark_digest",
            "result_observation_digest",
            "result_output_digest",
            "result_receipt_digest",
            "source_landmark_digest",
            "source_observation_digest",
            "source_output_digest",
            "source_receipt_digest",
        ):
            _require_digest(repeat[key], key)
        if not isinstance(repeat["signed_target_delta_ppm"], int) or isinstance(
            repeat["signed_target_delta_ppm"], bool
        ):
            raise GeometryMatrixQualificationInputError("signed target delta must be an integer")
        if not isinstance(repeat["max_control_drift_ppm"], int) or isinstance(
            repeat["max_control_drift_ppm"], bool
        ):
            raise GeometryMatrixQualificationInputError("maximum control drift must be an integer")
        if repeat["max_control_dimension_key"] not in _MEASUREMENT_DIMENSIONS:
            raise GeometryMatrixQualificationInputError(
                "repeat maximum control dimension is invalid"
            )
        target_dimensions = repeat["control_dimensions"]
        drifts = repeat["control_drifts_ppm"]
        if (
            not isinstance(target_dimensions, list)
            or not isinstance(drifts, list)
            or len(target_dimensions) != 5
            or len(drifts) != 5
        ):
            raise GeometryMatrixQualificationInputError("repeat controls are invalid")
        if (
            any(item not in _MEASUREMENT_DIMENSIONS for item in target_dimensions)
            or len(set(target_dimensions)) != 5
        ):
            raise GeometryMatrixQualificationInputError("repeat control dimensions are invalid")
        if target_dimensions != [
            item for item in _MEASUREMENT_DIMENSIONS if item != target_dimension
        ]:
            raise GeometryMatrixQualificationInputError(
                "repeat controls do not exclude target dimension"
            )
        if any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in drifts):
            raise GeometryMatrixQualificationInputError("repeat control drifts are invalid")
        if repeat["max_control_drift_ppm"] != max(drifts):
            raise GeometryMatrixQualificationInputError("repeat maximum control drift mismatch")
        winning_index = drifts.index(max(drifts))
        if repeat["max_control_dimension_key"] != target_dimensions[winning_index]:
            raise GeometryMatrixQualificationInputError("repeat maximum control dimension mismatch")
        for field in ("source_measurements_fixed18", "result_measurements_fixed18"):
            entries = repeat[field]
            if (
                not isinstance(entries, list)
                or len(entries) != 6
                or any(
                    not isinstance(item, str) or _FIXED18.fullmatch(item) is None
                    for item in entries
                )
            ):
                raise GeometryMatrixQualificationInputError(f"{field} is invalid")
        for field in (
            "control_drift_passed",
            "direction_passed",
            "observation_passed",
            "target_maximum_passed",
            "target_minimum_passed",
        ):
            if not isinstance(repeat[field], bool):
                raise GeometryMatrixQualificationInputError(f"{field} must be bool")
        normalized.append(dict(repeat))
    return normalized


def _replay_repeat_group(repeats: Sequence[Mapping[str, object]]) -> dict[str, bool]:
    source_receipts = tuple(item["source_receipt_digest"] for item in repeats)
    result_receipts = tuple(item["result_receipt_digest"] for item in repeats)
    source_outputs = tuple(item["source_output_digest"] for item in repeats)
    result_outputs = tuple(item["result_output_digest"] for item in repeats)
    source_landmarks = tuple(item["source_landmark_digest"] for item in repeats)
    result_landmarks = tuple(item["result_landmark_digest"] for item in repeats)
    return {
        "repeat_indexes_complete": tuple(item["repeat_index"] for item in repeats) == _REPEATS,
        "source_receipts_fresh": len(set(source_receipts)) == 3,
        "result_receipts_fresh": len(set(result_receipts)) == 3,
        "source_outputs_fresh": len(set(source_outputs)) == 3,
        "result_outputs_fresh": len(set(result_outputs)) == 3,
        "source_landmarks_stable": len(set(source_landmarks)) == 1,
        "result_landmarks_stable": len(set(result_landmarks)) == 1,
    }


def _validate_thresholds(value: Mapping[str, object]) -> None:
    expected = {
        "schema_version",
        "policy_digest",
        "repeat_count",
        "target_min_abs_ppm",
        "target_max_abs_ppm",
        "max_control_drift_ppm",
        "d08_verifier_policy_version",
    }
    _require_exact_keys(value, expected, "thresholds")
    if (
        value["schema_version"] != D08_GEOMETRY_THRESHOLDS_SCHEMA
        or value["d08_verifier_policy_version"] != D08_VERIFIER_POLICY_VERSION
    ):
        raise GeometryMatrixQualificationInputError("threshold schema or policy version mismatch")
    _require_digest(value["policy_digest"], "policy digest")
    if (
        value["repeat_count"],
        value["target_min_abs_ppm"],
        value["target_max_abs_ppm"],
        value["max_control_drift_ppm"],
    ) != (3, 10, 60_000, 20_000):
        raise GeometryMatrixQualificationInputError("threshold values do not match D08 policy")


def _validate_runtime_identity(value: object) -> None:
    if not isinstance(value, Mapping):
        raise GeometryMatrixQualificationInputError("runtime identity is invalid")
    expected = {
        "recipe_digest",
        "runtime_manifest_digest",
        "m3_algorithm_version",
        "m4_algorithm_version",
        "model_identity_digest",
        "model_config_digest",
        "weights_digest_or_no_weights",
        "topology_digest",
        "measurement_config_digest",
        "network_policy",
    }
    _require_exact_keys(value, expected, "runtime identity")
    for key in (
        "recipe_digest",
        "runtime_manifest_digest",
        "model_identity_digest",
        "model_config_digest",
        "topology_digest",
        "measurement_config_digest",
    ):
        _require_digest(value[key], key)
    if any(
        not isinstance(value[key], str) or not value[key]
        for key in (
            "m3_algorithm_version",
            "m4_algorithm_version",
            "weights_digest_or_no_weights",
            "network_policy",
        )
    ):
        raise GeometryMatrixQualificationInputError("runtime identity value is invalid")


def _validate_matrix_membership(terminals: Sequence[dict[str, object]]) -> None:
    case_ids = [cast(dict[str, object], item["metrics"])["case_id"] for item in terminals]
    digests = [item["verification_digest"] for item in terminals]
    if len(set(case_ids)) != 48 or len(set(digests)) != 48:
        raise GeometryMatrixQualificationInputError(
            "case ids and verification digests must be unique"
        )
    sources: dict[int, str] = {}
    source_ordinals: dict[str, int] = {}
    runtime_identity: Mapping[str, object] | None = None
    expected_keys = {
        (source, dimension, direction, magnitude)
        for source in _SOURCES
        for dimension in _DIMENSIONS
        for direction in _DIRECTIONS
        for magnitude in _MAGNITUDES
    }
    observed: set[tuple[int, str, str, int]] = set()
    ordinals: set[int] = set()
    for item in terminals:
        metrics = cast(dict[str, object], item["metrics"])
        source = cast(int, metrics["source_ordinal"])
        source_id = cast(str, metrics["source_asset_id"])
        if sources.setdefault(source, source_id) != source_id:
            raise GeometryMatrixQualificationInputError(
                "source ordinal maps to multiple source assets"
            )
        if source_ordinals.setdefault(source_id, source) != source:
            raise GeometryMatrixQualificationInputError(
                "source asset maps to multiple source ordinals"
            )
        current_runtime = cast(Mapping[str, object], metrics["runtime_identity"])
        if runtime_identity is None:
            runtime_identity = current_runtime
        elif current_runtime != runtime_identity:
            raise GeometryMatrixQualificationInputError(
                "runtime identity differs across matrix cases"
            )
        key = (
            source,
            cast(str, metrics["dimension_key"]),
            cast(str, metrics["direction"]),
            cast(int, metrics["magnitude_ppm"]),
        )
        observed.add(key)
        ordinal = cast(int, metrics["case_ordinal"])
        expected_ordinal = (
            1
            + _SOURCES.index(source) * 12
            + _DIMENSIONS.index(key[1]) * 4
            + _DIRECTIONS.index(key[2]) * 2
            + _MAGNITUDES.index(key[3])
        )
        if ordinal != expected_ordinal:
            raise GeometryMatrixQualificationInputError(
                "case ordinal does not match canonical matrix order"
            )
        ordinals.add(ordinal)
    if observed != expected_keys or set(sources) != set(_SOURCES) or len(ordinals) != 48:
        raise GeometryMatrixQualificationInputError("matrix case coverage is not exact")


def _terminal_gate(metrics: Mapping[str, object]) -> bool:
    if not all(
        metrics[key] is True
        for key in (
            "source_result_digest_distinct",
            "original_immutability_passed",
            "decode_passed",
            "artifact_passed",
            "repeat_gate_passed",
        )
    ):
        return False
    repeat_group = cast(Mapping[str, object], metrics["repeat_group_validation"])
    if not all(item is True for item in repeat_group.values()):
        return False
    for repeat in cast(list[dict[str, object]], metrics["repeats"]):
        delta = cast(int, repeat["signed_target_delta_ppm"])
        direction = cast(str, metrics["direction"])
        directional = (direction == "INCREASE" and delta > 0) or (
            direction == "DECREASE" and delta < 0
        )
        if (
            not directional
            or not 10 <= abs(delta) <= 60_000
            or cast(int, repeat["max_control_drift_ppm"]) > 20_000
        ):
            return False
        if not all(
            repeat[key] is True
            for key in (
                "direction_passed",
                "target_minimum_passed",
                "target_maximum_passed",
                "control_drift_passed",
                "observation_passed",
            )
        ):
            return False
    return True


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str] | frozenset[str], description: str
) -> None:
    if set(value) != expected:
        raise GeometryMatrixQualificationInputError(f"{description} exact keys do not match")


def _require_digest(value: object, description: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GeometryMatrixQualificationInputError(
            f"{description} must be a lowercase SHA-256 digest"
        )


def _require_id(value: object, description: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise GeometryMatrixQualificationInputError(
            f"{description} must be a lowercase hexadecimal ID"
        )
