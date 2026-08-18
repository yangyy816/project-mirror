from __future__ import annotations

import argparse
import hashlib
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


def _source(identity: str, asset: str, sha256: str) -> dict[str, str]:
    return {
        "identity_reference": identity,
        "asset_reference": asset,
        "normalized_sha256": sha256,
    }


def _manifest_document(
    calibration: list[dict[str, str]], holdout: list[dict[str, str]]
) -> dict[str, object]:
    return {
        "schema": evaluation.INPUT_SCHEMA,
        "platform": "windows",
        "expected_runtime_manifest_digest": "c" * 64,
        "calibration_sources": calibration,
        "calibration_split_digest": evaluation.split_digest(
            cohort="calibration", sources=calibration
        ),
        "holdout_split_digest": evaluation.split_digest(cohort="holdout", sources=holdout),
        "entries": [
            {
                "source_identity_reference": source["identity_reference"],
                "source_asset_reference": source["asset_reference"],
                "source_sha256": source["normalized_sha256"],
            }
            for source in holdout
        ],
    }


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
    calibration = [
        _source(
            "1dd1786221d34bae9863df77c9d531e6",
            "7c14195846924ad19d762080a626ab54",
            "71fc0fadc69841664664cd912132edb2d64adc227a78755be38dedf5113add1e",
        ),
        _source(
            "a959c8c392bb44f6a9120385ef16949c",
            "d714a022dc2249edadef524ebb25f623",
            "3532d0f7e30d64916a81059c24e6e0ea33f3c9fa5fff66600f7131a6728c9a05",
        ),
    ]
    assert (
        evaluation.split_digest(cohort="calibration", sources=calibration)
        == "5f1f9c4b14e416d1a07360c2916d3b6b43536a3f5f963411264b74ddacd78d02"
    )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("identity_reference", "identity overlap"),
        ("asset_reference", "Asset overlap"),
        ("normalized_sha256", "normalized SHA-256 overlap"),
    ],
)
def test_private_manifest_rejects_each_calibration_holdout_overlap(
    tmp_path: Path, field: str, message: str
) -> None:
    calibration = [_source("i-a", "a-a", "a" * 64), _source("i-b", "a-b", "b" * 64)]
    holdout = [_source("i-c", "a-c", "c" * 64), _source("i-d", "a-d", "d" * 64)]
    holdout[0][field] = calibration[0][field]
    document = _manifest_document(calibration, holdout)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        evaluation._manifest(path)


def test_private_manifest_accepts_disjoint_identity_asset_and_sha(tmp_path: Path) -> None:
    calibration = [_source("i-a", "a-a", "a" * 64), _source("i-b", "a-b", "b" * 64)]
    holdout = [_source("i-c", "a-c", "c" * 64), _source("i-d", "a-d", "d" * 64)]
    document = _manifest_document(calibration, holdout)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert evaluation._manifest(path) == document


@pytest.mark.parametrize(
    ("mutated", "message"),
    [
        ("vision_executable", "Vision runtime artifact checksum mismatch: executable"),
        ("topology", "topology checksum mismatch"),
    ],
)
def test_frozen_vision_and_topology_inputs_fail_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutated: str,
    message: str,
) -> None:
    vision = tmp_path / "vision-runtime"
    model = tmp_path / "model.task"
    topology = tmp_path / "topology.py"
    vision.write_bytes(b"qualified-vision")
    model.write_bytes(b"qualified-model")
    topology.write_bytes(b"qualified-topology")
    monkeypatch.setitem(
        evaluation.VISION_RUNTIME_ARTIFACT_SHA256_BY_PLATFORM,
        "test",
        {"executable": hashlib.sha256(vision.read_bytes()).hexdigest()},
    )
    monkeypatch.setattr(evaluation, "MODEL_SHA256", hashlib.sha256(model.read_bytes()).hexdigest())
    monkeypatch.setattr(
        evaluation, "TOPOLOGY_SHA256", hashlib.sha256(topology.read_bytes()).hexdigest()
    )
    (vision if mutated == "vision_executable" else topology).write_bytes(b"wrong")
    args = argparse.Namespace(vision_executable=vision, model=model, topology=topology)
    with pytest.raises(RuntimeError, match=message):
        evaluation._verify_frozen_inputs(args, {"platform": "test"})


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


def test_forward_repair_evidence_is_redacted_and_preserves_t07_results() -> None:
    repo = Path(__file__).parents[3]
    original = json.loads(
        (repo / "docs/research/P2_M4_T07_EVALUATION_EVIDENCE.json").read_text(encoding="utf-8")
    )
    repair = json.loads(
        (repo / "docs/research/P2_M4_T08_REPAIR_EVIDENCE.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(repair, sort_keys=True)
    assert repair["schema"] == "mirror.p2-m4.t08-forward-repair-evidence/v1"
    assert repair["split_authority"]["schema"] == evaluation.INPUT_SCHEMA
    assert repair["interpretation"] == "FURTHER_RESEARCH_FOR_M5_ISOLATION"
    assert re.search(r"[A-Za-z]:\\\\", serialized) is None
    assert all(token not in serialized for token in ("/workspace/", "/stage-", ".jpg", ".rgb"))
    assert all(
        forbidden not in serialized
        for forbidden in (
            "raw_landmarks",
            "image_bytes",
            "object_key",
            "private_path",
            "source_path",
            "source_landmark_log",
        )
    )
    assert repair["result_output_sha256"] == [row["output_sha256"] for row in original["rows"]]
    assert (
        repair["aggregate"]["maximum_absolute_control_relative_delta"]
        == original["aggregate"]["maximum_absolute_control_relative_delta"]
    )
    assert (
        repair["aggregate"]["maximum_cross_platform_measurement_absolute_difference"]
        == original["aggregate"]["maximum_cross_platform_measurement_absolute_difference"]
    )

    calibration = repair["split_authority"]["calibration"]
    holdout = repair["split_authority"]["holdout"]
    assert (
        evaluation.split_digest(cohort="calibration", sources=calibration)
        == repair["split_authority"]["calibration_split_digest"]
    )
    assert (
        evaluation.split_digest(cohort="holdout", sources=holdout)
        == repair["split_authority"]["holdout_split_digest"]
    )

    for platform in ("windows", "linux"):
        assert set(repair["vision_authority"][platform]) == {
            "wrapper_sha256",
            "main_sha256",
            "opencv_core_sha256",
            "opencv_imgproc_sha256",
        }
        assert all(
            re.fullmatch(r"[0-9a-f]{64}", value)
            for value in repair["vision_authority"][platform].values()
        )
