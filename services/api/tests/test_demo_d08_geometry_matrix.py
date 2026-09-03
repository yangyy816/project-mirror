from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

from mirror_api.demo_d08_geometry_adapter import (
    D08_VERIFIER_POLICY_VERSION,
    TARGETED_REPAIR_ALGORITHM_VERSION,
)
from mirror_api.demo_d08_geometry_matrix import (
    GEOMETRY_MATRIX_QUALIFICATION_SCHEMA,
    GeometryMatrixQualification,
    GeometryMatrixQualificationInputError,
    GeometryTerminalVerification,
    qualify_geometry_matrix,
)
from mirror_api.demo_d08_geometry_verifier import (
    D08_GEOMETRY_METRICS_SCHEMA,
    D08_GEOMETRY_THRESHOLDS_SCHEMA,
)
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION


def _digest(index: int) -> str:
    return f"{index:064x}"


def _identifier(index: int) -> str:
    return f"{index:032x}"


_SELECTED_DIMENSIONS = ("jaw_width", "eye_spacing")
_SELECTED_PAIR_MANIFEST_DIGEST = _digest(140_000)


def _terminal(
    source: int, dimension: str, direction: str, magnitude: int
) -> GeometryTerminalVerification:
    dimensions = ("jaw_width", "chin_height", "eye_spacing")
    directions = ("DECREASE", "INCREASE")
    magnitude_index = (15_000, 30_000).index(magnitude)
    ordinal = (
        1
        + (source - 1) * 12
        + dimensions.index(dimension) * 4
        + directions.index(direction) * 2
        + magnitude_index
    )
    sign = 1 if direction == "INCREASE" else -1
    delta = sign * (100 if magnitude == 15_000 else 200)
    control_dimensions = [
        item
        for item in (
            "cheekbone_width",
            "chin_height",
            "eye_spacing",
            "jaw_width",
            "mouth_width",
            "nose_width",
        )
        if item != dimension
    ]
    controls = [1, 2, 3, 4, 5]
    repeats = []
    for repeat in range(1, 4):
        base = ordinal * 100 + repeat * 10
        repeats.append(
            {
                "control_drift_passed": True,
                "control_dimensions": control_dimensions,
                "control_drifts_ppm": controls,
                "direction_passed": True,
                "observation_passed": True,
                "repeat_index": repeat,
                "max_control_dimension_key": control_dimensions[-1],
                "max_control_drift_ppm": 5,
                "result_landmark_digest": _digest(ordinal * 100 + 1),
                "result_measurements_fixed18": ["0.100000000000000000"] * 6,
                "result_observation_digest": _digest(base + 2),
                "result_output_digest": _digest(base + 3),
                "result_receipt_digest": _digest(base + 4),
                "signed_target_delta_ppm": delta,
                "source_landmark_digest": _digest(ordinal * 100 + 5),
                "source_measurements_fixed18": ["0.100000000000000000"] * 6,
                "source_observation_digest": _digest(base + 6),
                "source_output_digest": _digest(base + 7),
                "source_receipt_digest": _digest(base + 8),
                "target_maximum_passed": True,
                "target_minimum_passed": True,
            }
        )
    source_sha = _digest(90_000 + source)
    metrics = {
        "schema_version": D08_GEOMETRY_METRICS_SCHEMA,
        "authority_digest": _digest(10_000 + ordinal),
        "stable_core_digest": _digest(20_000 + ordinal),
        "attempt_receipt_digest": _digest(30_000 + ordinal),
        "operation_id": _identifier(40_000 + ordinal),
        "operation_authority_digest": _digest(50_000 + ordinal),
        "operation_spec_digest": _digest(60_000 + ordinal),
        "case_id": _identifier(70_000 + ordinal),
        "case_ordinal": ordinal,
        "source_ordinal": source,
        "source_asset_id": _identifier(80_000 + source),
        "result_sha256": _digest(100_000 + ordinal),
        "source_sha256": source_sha,
        "dimension_key": dimension,
        "direction": direction,
        "magnitude_ppm": magnitude,
        "source_result_digest_distinct": True,
        "source_digest_after_verification": source_sha,
        "original_immutability_passed": True,
        "decode_passed": True,
        "artifact_passed": True,
        "runtime_identity": {
            "recipe_digest": _digest(1),
            "runtime_manifest_digest": _digest(2),
            "m3_algorithm_version": "m3-v1",
            "m4_algorithm_version": ALGORITHM_VERSION,
            "model_identity_digest": _digest(3),
            "model_config_digest": _digest(4),
            "weights_digest_or_no_weights": "NO_WEIGHTS",
            "topology_digest": _digest(5),
            "measurement_config_digest": _digest(6),
            "network_policy": "NETWORK_DENIED",
        },
        "d08_verifier_policy_version": D08_VERIFIER_POLICY_VERSION,
        "measurement_dimension_order": [
            "cheekbone_width",
            "chin_height",
            "eye_spacing",
            "jaw_width",
            "mouth_width",
            "nose_width",
        ],
        "repeats": repeats,
        "repeat_gate_passed": True,
        "repeat_group_validation": {
            "repeat_indexes_complete": True,
            "source_receipts_fresh": True,
            "result_receipts_fresh": True,
            "source_outputs_fresh": True,
            "result_outputs_fresh": True,
            "source_landmarks_stable": True,
            "result_landmarks_stable": True,
        },
        "max_non_target_drift_ppm": 5,
        "max_non_target_dimension_key": control_dimensions[-1],
        "max_non_target_repeat_index": 1,
    }
    thresholds = {
        "schema_version": D08_GEOMETRY_THRESHOLDS_SCHEMA,
        "policy_digest": _digest(120_000 + ordinal),
        "repeat_count": 3,
        "target_min_abs_ppm": 10,
        "target_max_abs_ppm": 60_000,
        "max_control_drift_ppm": 20_000,
        "d08_verifier_policy_version": D08_VERIFIER_POLICY_VERSION,
    }
    return GeometryTerminalVerification(_digest(130_000 + ordinal), metrics, thresholds)


def _matrix() -> list[GeometryTerminalVerification]:
    return [
        _terminal(source, dimension, direction, magnitude)
        for source in range(1, 5)
        for dimension in _SELECTED_DIMENSIONS
        for direction in ("DECREASE", "INCREASE")
        for magnitude in (15_000, 30_000)
    ]


def _qualify(
    terminals: list[GeometryTerminalVerification],
) -> GeometryMatrixQualification:
    return qualify_geometry_matrix(
        terminals,
        selected_dimensions=_SELECTED_DIMENSIONS,
        selected_pair_manifest_digest=_SELECTED_PAIR_MANIFEST_DIGEST,
    )


def _replace(
    terminal: GeometryTerminalVerification,
    *,
    metrics: dict[str, object] | None = None,
    thresholds: dict[str, object] | None = None,
    digest: str | None = None,
) -> GeometryTerminalVerification:
    return GeometryTerminalVerification(
        digest or terminal.verification_digest,
        metrics or deepcopy(dict(terminal.metrics)),
        thresholds or deepcopy(dict(terminal.thresholds)),
    )


def test_complete_matrix_has_canonical_pass_evidence() -> None:
    result = _qualify(list(reversed(_matrix())))
    assert result.status == "PASS"
    assert result.evidence["schema_version"] == GEOMETRY_MATRIX_QUALIFICATION_SCHEMA
    assert result.evidence["selected_dimension_keys"] == list(_SELECTED_DIMENSIONS)
    assert result.evidence["selected_pair_manifest_digest"] == (_SELECTED_PAIR_MANIFEST_DIGEST)
    assert len(result.evidence["ordered_terminal_verifications"]) == 32
    assert len(result.evidence["ordered_repeat_deltas"]) == 96
    assert len(result.evidence["monotonic_comparisons"]) == 48
    assert result.evidence["cross_case_digest"] == result.cross_case_digest


def test_case_25_targeted_successor_identity_is_qualified_without_global_uniformity() -> None:
    terminals = _matrix()
    target_index = next(
        index for index, terminal in enumerate(terminals) if terminal.metrics["case_ordinal"] == 25
    )
    metrics = deepcopy(dict(terminals[target_index].metrics))
    runtime_identity = cast(dict[str, object], metrics["runtime_identity"])
    runtime_identity["m4_algorithm_version"] = TARGETED_REPAIR_ALGORITHM_VERSION
    runtime_identity["recipe_digest"] = _digest(99)
    terminals[target_index] = _replace(terminals[target_index], metrics=metrics)

    result = _qualify(terminals)

    assert result.status == "PASS"


def test_targeted_successor_identity_outside_case_25_fails_closed() -> None:
    terminals = _matrix()
    metrics = deepcopy(dict(terminals[0].metrics))
    runtime_identity = cast(dict[str, object], metrics["runtime_identity"])
    runtime_identity["m4_algorithm_version"] = TARGETED_REPAIR_ALGORITHM_VERSION
    runtime_identity["recipe_digest"] = _digest(99)
    terminals[0] = _replace(terminals[0], metrics=metrics)

    with pytest.raises(GeometryMatrixQualificationInputError, match="exact D08 allowlist"):
        _qualify(terminals)


@pytest.mark.parametrize(
    ("dimensions", "digest"),
    [
        (("jaw_width", "chin_height", "eye_spacing"), _SELECTED_PAIR_MANIFEST_DIGEST),
        (_SELECTED_DIMENSIONS, "not-a-digest"),
    ],
)
def test_selected_question_bank_authority_is_required(
    dimensions: tuple[str, ...], digest: str
) -> None:
    with pytest.raises(GeometryMatrixQualificationInputError):
        qualify_geometry_matrix(
            _matrix(),
            selected_dimensions=dimensions,
            selected_pair_manifest_digest=digest,
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "cross_source", "digest", "threshold", "schema"]
)
def test_invalid_matrix_inputs_fail_closed(mutation: str) -> None:
    terminals = _matrix()
    if mutation == "missing":
        terminals.pop()
    elif mutation == "duplicate":
        terminals[-1] = _replace(terminals[-1], digest=terminals[0].verification_digest)
    elif mutation == "cross_source":
        metrics = deepcopy(dict(terminals[-1].metrics))
        metrics["source_asset_id"] = terminals[0].metrics["source_asset_id"]
        terminals[-1] = _replace(terminals[-1], metrics=metrics)
    elif mutation == "digest":
        terminals[0] = _replace(terminals[0], digest="bad")
    elif mutation == "threshold":
        thresholds = deepcopy(dict(terminals[0].thresholds))
        thresholds["target_max_abs_ppm"] = 60_001
        terminals[0] = _replace(terminals[0], thresholds=thresholds)
    else:
        metrics = deepcopy(dict(terminals[0].metrics))
        metrics["schema_version"] = "wrong"
        terminals[0] = _replace(terminals[0], metrics=metrics)
    with pytest.raises(GeometryMatrixQualificationInputError):
        _qualify(terminals)


@pytest.mark.parametrize("mutation", ["repeat", "direction", "range", "monotonic"])
def test_gate_failures_return_fail_evidence(mutation: str) -> None:
    terminals = _matrix()
    if mutation == "repeat":
        metrics = deepcopy(dict(terminals[0].metrics))
        metrics["repeats"][0]["observation_passed"] = False
        terminals[0] = _replace(terminals[0], metrics=metrics)
    elif mutation == "direction":
        metrics = deepcopy(dict(terminals[0].metrics))
        metrics["repeats"][0]["signed_target_delta_ppm"] = 100
        terminals[0] = _replace(terminals[0], metrics=metrics)
    elif mutation == "range":
        metrics = deepcopy(dict(terminals[0].metrics))
        metrics["repeats"][0]["signed_target_delta_ppm"] = 60_001
        terminals[0] = _replace(terminals[0], metrics=metrics)
    else:
        high = terminals[1]
        metrics = deepcopy(dict(high.metrics))
        metrics["repeats"][1]["signed_target_delta_ppm"] = 99
        terminals[1] = _replace(high, metrics=metrics)
    result = _qualify(terminals)
    assert result.status == "FAIL"
