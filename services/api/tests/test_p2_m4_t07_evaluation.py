from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from mirror_api.synthetic_dataset import TransformDirection


def _module() -> ModuleType:
    path = Path(__file__).parents[3] / "scripts" / "research" / "run_p2_m4_t07_evaluation.py"
    specification = importlib.util.spec_from_file_location("p2_m4_t07_evaluation", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


evaluation = _module()


def _landmarks() -> list[tuple[float, float, float]]:
    values = [(0.5, 0.5, 0.0) for _ in range(478)]
    values[10] = (0.5, 0.1, 0.0)
    values[152] = (0.5, 0.9, 0.0)
    values[234] = (0.2, 0.5, 0.0)
    values[454] = (0.8, 0.5, 0.0)
    values[98] = (0.45, 0.5, 0.0)
    values[327] = (0.55, 0.5, 0.0)
    values[133] = (0.4, 0.4, 0.0)
    values[362] = (0.6, 0.4, 0.0)
    values[33] = (0.3, 0.4, 0.0)
    values[263] = (0.7, 0.4, 0.0)
    return values


def test_split_digest_matches_preregistration() -> None:
    assert (
        evaluation.split_digest(
            cohort="calibration",
            asset_sha256=[
                "71fc0fadc69841664664cd912132edb2d64adc227a78755be38dedf5113add1e",
                "3532d0f7e30d64916a81059c24e6e0ea33f3c9fa5fff66600f7131a6728c9a05",
            ],
        )
        == "bd51d39d8db0072739fd1e8976a226701aca80f7b203acb76b75cace507a844e"
    )


def test_private_manifest_rejects_calibration_holdout_overlap(tmp_path: Path) -> None:
    calibration = ["a" * 64, "b" * 64]
    document = {
        "schema": "mirror.p2-m4.t07-private-inputs/v1",
        "platform": "test",
        "expected_runtime_manifest_digest": "c" * 64,
        "calibration_asset_sha256": calibration,
        "calibration_split_digest": evaluation.split_digest(
            cohort="calibration", asset_sha256=calibration
        ),
        "holdout_split_digest": evaluation.split_digest(
            cohort="holdout", asset_sha256=["a" * 64, "d" * 64]
        ),
        "entries": [{"source_sha256": "a" * 64}, {"source_sha256": "d" * 64}],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="calibration and holdout overlap"):
        evaluation._manifest(path)


def test_measurement_vector_uses_preregistered_normalization() -> None:
    assert evaluation.measurement_vector(_landmarks()) == pytest.approx(
        {
            "jaw_width": 0.75,
            "nose_width": 0.125,
            "eye_spacing": 0.25,
            "right_eye_width": 0.125,
            "left_eye_width": 0.125,
        }
    )


def test_control_points_use_admission_floor_and_bidirectional_anchors() -> None:
    increase = evaluation.build_control_points(_landmarks(), TransformDirection.INCREASE)
    decrease = evaluation.build_control_points(_landmarks(), TransformDirection.DECREASE)
    assert len(increase) == 468
    assert {point.confidence_ppm for point in increase} == {500_000}
    assert increase[234].destination_x < increase[234].source_x
    assert increase[454].destination_x > increase[454].source_x
    assert decrease[234].destination_x > decrease[234].source_x
    assert decrease[454].destination_x < decrease[454].source_x


def test_topology_uses_ordered_edge_triples_without_clique_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evaluation, "EXPECTED_TRIANGLE_COUNT", 2)
    monkeypatch.setattr(evaluation, "PLAN_LANDMARK_COUNT", 4)
    topology = tmp_path / "topology.py"
    topology.write_text(
        "FACEMESH_TESSELATION = frozenset([(0, 1), (1, 2), (2, 0),(1, 2), (2, 3), (3, 1)])\n",
        encoding="utf-8",
    )
    triangles = evaluation.load_triangles(topology)
    assert [set(item.landmark_codes) for item in triangles] == [
        {"mp-000", "mp-001", "mp-002"},
        {"mp-001", "mp-002", "mp-003"},
    ]


def test_landmark_parser_rejects_nonfinite_or_incomplete_payload() -> None:
    with pytest.raises(ValueError, match="unexpected landmark count"):
        evaluation.parse_landmarks("face_0_landmarks=0.5,0.5,0.0")
    payload = ";".join("0.5,0.5,0.0" for _ in range(477)) + ";nan,0.5,0.0"
    with pytest.raises(ValueError, match="finite"):
        evaluation.parse_landmarks(f"face_0_landmarks={payload}")


def test_committed_evidence_is_redacted_and_directionally_consistent() -> None:
    path = Path(__file__).parents[3] / "docs" / "research" / "P2_M4_T07_EVALUATION_EVIDENCE.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(document, sort_keys=True)
    assert re.search(r"[A-Za-z]:\\\\", serialized) is None
    assert all(token not in serialized for token in ("/workspace/", "/stage-", ".jpg", ".rgb"))
    assert all(
        forbidden not in serialized
        for forbidden in ("raw_landmarks", "image_bytes", "object_key", "private_path")
    )
    assert len(document["rows"]) == 4
    assert document["aggregate"] == {
        "all_cross_platform_outputs_equal": True,
        "all_same_platform_replays_equal": True,
        "all_target_directions_correct": True,
        "maximum_absolute_control_relative_delta": 0.011420225249709091,
        "maximum_cross_platform_measurement_absolute_difference": 0.000011863707220088893,
        "maximum_repeat_measurement_span": 0.0,
    }
    for row in document["rows"]:
        expected_positive = row["direction"] == "INCREASE"
        assert (row["windows_relative_delta"]["jaw_width"] > 0.0) is expected_positive
        assert (row["linux_relative_delta"]["jaw_width"] > 0.0) is expected_positive
