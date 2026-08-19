from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from mirror_api.synthetic_dataset import TransformDirection


def _module() -> ModuleType:
    path = Path(__file__).parents[3] / "scripts" / "research" / "run_p2_m5_cc01c_calibration.py"
    specification = importlib.util.spec_from_file_location("p2_m5_cc01c_calibration", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


calibration = _module()


def _candidate_manifest() -> dict[str, object]:
    path = Path(__file__).parents[3] / "docs" / "research" / "P2_M5_CC01C_CANDIDATE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _landmarks() -> list[tuple[float, float, float]]:
    values = [(0.5, 0.5, 0.0) for _ in range(478)]
    values[10], values[152], values[17] = (0.5, 0.1, 0.0), (0.5, 0.9, 0.0), (0.45, 0.65, 0.0)
    for left, right, y in (
        (234, 454, 0.55),
        (133, 362, 0.35),
        (98, 327, 0.5),
        (61, 291, 0.65),
        (123, 352, 0.42),
    ):
        values[left], values[right] = (0.3, y, 0.0), (0.7, y, 0.0)
    return values


def _platform_manifest(entries: list[dict[str, object]]) -> dict[str, object]:
    stage_b_path = (
        Path(__file__).parents[3] / "docs" / "research" / "P2_M5_CC01B_CALIBRATION_EVIDENCE.json"
    )
    return {
        "schema": calibration.INPUT_SCHEMA,
        "platform": "windows_x86_64",
        "expected_runtime_manifest_digest": _candidate_manifest()["runtime_authority"][
            "transform_runtime_manifest_digest"
        ]["windows_x86_64"],
        "accepted_candidate_sha": calibration.ACCEPTED_CANDIDATE_SHA,
        "accepted_candidate_run": calibration.ACCEPTED_CANDIDATE_RUN,
        "acceptance_checkpoint_sha": calibration.ACCEPTANCE_CHECKPOINT_SHA,
        "acceptance_checkpoint_run": calibration.ACCEPTANCE_CHECKPOINT_RUN,
        "stage_b_evidence_sha256": hashlib.sha256(stage_b_path.read_bytes()).hexdigest(),
        "cohort_digest": calibration._cohort_digest(entries),
        "entries": entries,
    }


def _entry(number: int) -> dict[str, object]:
    stage_b_path = (
        Path(__file__).parents[3] / "docs" / "research" / "P2_M5_CC01B_CALIBRATION_EVIDENCE.json"
    )
    item = json.loads(stage_b_path.read_text(encoding="utf-8"))["items"][number]
    return {
        "item_reference": item["item_reference"],
        "identity_reference": item["identity_id"],
        "asset_reference": item["normalized_asset_id"],
        "qa_run_reference": item["qa_run_id"],
        "normalized_sha256": item["normalized_sha256"],
        "source_path": f"C:/private/source-{number}.jpg",
        "source_landmark_log": f"C:/private/source-{number}.log",
        "source_landmark_log_sha256": f"{number + 1:064x}",
        "width": 512,
        "height": 512,
    }


def _report(platform: str, *, result_prefix: str = "a") -> dict[str, object]:
    rows: list[dict[str, object]] = []
    cases: list[dict[str, object]] = []
    dimensions = (
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    )
    for identity in range(12):
        for candidate in dimensions:
            for direction in ("INCREASE", "DECREASE"):
                for magnitude in (15000, 30000):
                    case = calibration._case_digest(
                        f"opaque-private-identity-{identity}", candidate, direction, magnitude
                    )
                    cases.append(
                        {
                            "case_digest": case,
                            "identity_reference": f"opaque-private-identity-{identity}",
                            "candidate": candidate,
                            "direction": direction,
                            "magnitude_ppm": magnitude,
                            "status": "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW",
                            "executed_repeat_count": 3,
                        }
                    )
                    for repeat in (1, 2, 3):
                        source = {key: 0.5 for key in dimensions}
                        result = dict(source)
                        result[candidate] += (
                            (1 if direction == "INCREASE" else -1) * magnitude / 1_000_000
                        )
                        rows.append(
                            {
                                "case_digest": case,
                                "identity_reference": f"opaque-private-identity-{identity}",
                                "candidate": candidate,
                                "direction": direction,
                                "magnitude_ppm": magnitude,
                                "repeat": repeat,
                                "status": "PASSED",
                                "source_sha256": f"{identity:064x}",
                                "result_sha256": f"{result_prefix}{identity:063x}",
                                "result_artifact": f"{case}-{repeat}.jpg",
                                "plan_digest": "b" * 64,
                                "source_measurements": source,
                                "result_measurements": result,
                                "vision_log_sha256": "c" * 64,
                                "vision_log_artifact": f"{case}-{repeat}.vision.log",
                                "phash_hex": f"{identity:016x}",
                                "changed_pixel_count": 100,
                            }
                        )
    case_set_digest = hashlib.sha256(
        "\n".join(sorted(item["case_digest"] for item in cases)).encode()
    ).hexdigest()
    report: dict[str, object] = {
        "schema": calibration.PRIVATE_REPORT_SCHEMA,
        "platform": platform,
        "runtime_manifest_digest": "d" * 64,
        "candidate_manifest_digest": calibration.EXPECTED_MANIFEST_DIGEST,
        "model_sha256": "e" * 64,
        "topology_sha256": "f" * 64,
        "triangle_count": 852,
        "stage_b_evidence_sha256": "1" * 64,
        "cohort_digest": "2" * 64,
        "input_manifest_digest": "3" * 64,
        "case_set_digest": case_set_digest,
        "cases": cases,
        "rows": rows,
    }
    report["report_digest"] = calibration._private_report_digest(report)
    return report


def _manual_review(windows: dict[str, object], linux: dict[str, object]) -> dict[str, object]:
    windows_rows = {row["case_digest"]: row for row in windows["rows"] if row["repeat"] == 1}
    linux_rows = {row["case_digest"]: row for row in linux["rows"] if row["repeat"] == 1}
    decisions = [
        {
            "case_digest": case,
            "windows_result_sha256": windows_rows[case]["result_sha256"],
            "linux_result_sha256": linux_rows[case]["result_sha256"],
            "criteria": {
                "background_seam": "PASS",
                "disconnected_contour": "PASS",
                "duplicated_feature": "PASS",
                "warp_tear": "PASS",
            },
            "outcome": "PASS",
        }
        for case in sorted(windows_rows)
    ]
    review: dict[str, object] = {
        "schema": calibration.MANUAL_REVIEW_SCHEMA,
        "status": "COMPLETE",
        "decisions": decisions,
    }
    review["content_digest"] = calibration._manual_review_digest(review)
    return review


def test_measurement_vector_contains_every_frozen_target_and_control_dimension() -> None:
    vector = calibration.measurement_vector(_landmarks(), _candidate_manifest())
    assert set(vector) == {
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    }
    assert vector["jaw_width"] == pytest.approx(0.5)
    assert vector["chin_height"] == pytest.approx(0.31868871959954903)


def test_paired_horizontal_plan_uses_source_anchor_span_and_direction() -> None:
    candidate = next(
        item
        for item in _candidate_manifest()["candidate_dimensions"]
        if item["dimension_key"] == "jaw_width"
    )
    increase = calibration.build_control_points(
        _landmarks(), candidate, TransformDirection.INCREASE, 30000, 500000
    )
    decrease = calibration.build_control_points(
        _landmarks(), candidate, TransformDirection.DECREASE, 30000, 500000
    )
    assert increase[234].destination_x < increase[234].source_x
    assert increase[454].destination_x > increase[454].source_x
    assert decrease[234].destination_x > decrease[234].source_x
    assert decrease[454].destination_x < decrease[454].source_x
    assert increase[234].destination_y == increase[234].source_y


def test_chin_plan_applies_the_signed_displacement_once_with_downward_y() -> None:
    candidate = next(
        item
        for item in _candidate_manifest()["candidate_dimensions"]
        if item["dimension_key"] == "chin_height"
    )
    points = _landmarks()
    increase = calibration.build_control_points(
        points, candidate, TransformDirection.INCREASE, 30000, 500000
    )
    decrease = calibration.build_control_points(
        points, candidate, TransformDirection.DECREASE, 30000, 500000
    )
    span = calibration._distance(points, 17, 152)
    assert increase[152].destination_y - increase[152].source_y == pytest.approx(span * 0.03)
    assert decrease[152].destination_y - decrease[152].source_y == pytest.approx(-span * 0.03)
    assert increase[152].destination_x == increase[152].source_x


def test_plan_and_landmark_failure_paths_fail_before_transform() -> None:
    candidate = next(
        item
        for item in _candidate_manifest()["candidate_dimensions"]
        if item["dimension_key"] == "jaw_width"
    )
    with pytest.raises(ValueError, match="magnitude"):
        calibration.build_control_points(
            _landmarks(), candidate, TransformDirection.INCREASE, 20000, 500000
        )
    invalid = _landmarks()
    invalid[0] = (float("nan"), 0.5, 0.0)
    with pytest.raises(ValueError, match="finite"):
        calibration.measurement_vector(invalid, _candidate_manifest())


def test_candidate_manifest_tamper_and_resource_envelope_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _candidate_manifest()
    document["candidate_dimensions"][0]["measurement_formula"] = "tampered"
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        calibration.load_candidate_manifest(path)

    document = _candidate_manifest()
    document["resource_envelope"]["retry_attempts"] = 1
    document["manifest_content_digest"] = calibration._canonical_digest(
        calibration.CANDIDATE_SCHEMA, document, "manifest_content_digest"
    )
    monkeypatch.setattr(
        calibration, "EXPECTED_MANIFEST_DIGEST", document["manifest_content_digest"]
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="resource envelope"):
        calibration.load_candidate_manifest(path)


def test_platform_manifest_rejects_duplicate_private_identity_and_bad_authority(
    tmp_path: Path,
) -> None:
    document = _platform_manifest([_entry(number) for number in range(12)])
    document["entries"][1]["identity_reference"] = document["entries"][0]["identity_reference"]
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        calibration.load_platform_manifest(
            path,
            _candidate_manifest(),
            Path(__file__).parents[3]
            / "docs"
            / "research"
            / "P2_M5_CC01B_CALIBRATION_EVIDENCE.json",
        )

    document = _platform_manifest([_entry(number) for number in range(12)])
    document["accepted_candidate_sha"] = "0" * 40
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="accepted candidate authority"):
        calibration.load_platform_manifest(
            path,
            _candidate_manifest(),
            Path(__file__).parents[3]
            / "docs"
            / "research"
            / "P2_M5_CC01B_CALIBRATION_EVIDENCE.json",
        )


def test_platform_manifest_rejects_fabricated_qa_reference_even_with_recomputed_digest(
    tmp_path: Path,
) -> None:
    entries = [_entry(number) for number in range(12)]
    entries[0]["qa_run_reference"] = "fabricated-qa-reference"
    document = _platform_manifest(entries)
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="accepted Stage B authority"):
        calibration.load_platform_manifest(
            path,
            _candidate_manifest(),
            Path(__file__).parents[3]
            / "docs"
            / "research"
            / "P2_M5_CC01B_CALIBRATION_EVIDENCE.json",
        )


def test_merge_is_complete_deterministic_and_never_leaks_private_values(tmp_path: Path) -> None:
    windows, linux = _report("windows_x86_64"), _report("linux_x86_64_network_none")
    windows_path, linux_path = tmp_path / "windows.json", tmp_path / "linux.json"
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")
    aggregate = calibration.merge_reports(windows_path, linux_path)
    serialized = json.dumps(aggregate, sort_keys=True)
    assert aggregate["transform_vision_row_count"] == 1728
    assert aggregate["unique_cross_platform_case_count"] == 288
    assert len(aggregate["candidate_outcomes"]) == 6
    assert aggregate["source_duplicate_evidence"] == {
        "comparison_pair_count": 132,
        "exact_duplicate_pair_count": 0,
        "phash_hamming": None,
    }
    assert all(
        item["variant_duplicate_evidence"]["comparison_pair_count"] == 528
        and item["variant_duplicate_evidence"]["exact_duplicate_pair_count"] == 0
        and item["variant_duplicate_evidence"]["phash_hamming"]["count"] == 528
        for item in aggregate["candidate_outcomes"]
    )
    assert all(
        item["ready_decision"] == "NOT_PERMITTED_IN_STAGE_C"
        for item in aggregate["candidate_outcomes"]
    )
    assert aggregate["stage_d_eligible_candidate_count"] == 0
    assert all(
        item["stage_d_consideration"] == "INELIGIBLE_MANUAL_REVIEW_PENDING"
        for item in aggregate["candidate_outcomes"]
    )
    assert "opaque-private" not in serialized
    assert "C:/private" not in serialized
    assert "source_measurements" not in serialized
    assert all(
        item["target_error"]["count"] > 0
        and item["maximum_normalized_control_drift"]["count"] > 0
        and item["cross_platform_measurement_variance"]["count"] > 0
        for item in aggregate["candidate_outcomes"]
    )


def test_merge_does_not_count_cross_platform_reproducibility_as_duplicates(
    tmp_path: Path,
) -> None:
    windows, linux = _report("windows_x86_64"), _report("linux_x86_64_network_none")
    windows_path, linux_path = tmp_path / "windows.json", tmp_path / "linux.json"
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")
    aggregate = calibration.merge_reports(windows_path, linux_path)
    assert all(
        item["variant_duplicate_evidence"]["exact_duplicate_pair_count"] == 0
        for item in aggregate["candidate_outcomes"]
    )

    for report in (windows, linux):
        for row in report["rows"]:
            if row["identity_reference"] == "opaque-private-identity-1":
                row["result_sha256"] = row["result_sha256"][:-1] + "0"
        report["report_digest"] = calibration._private_report_digest(report)
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")
    aggregate = calibration.merge_reports(windows_path, linux_path)
    assert all(
        item["variant_duplicate_evidence"]["exact_duplicate_pair_count"] == 8
        for item in aggregate["candidate_outcomes"]
    )


def test_merge_binds_complete_manual_review_without_overriding_failures(tmp_path: Path) -> None:
    windows, linux = _report("windows_x86_64"), _report("linux_x86_64_network_none")
    windows_path, linux_path = tmp_path / "windows.json", tmp_path / "linux.json"
    review_path = tmp_path / "review.json"
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")
    review = _manual_review(windows, linux)
    review_path.write_text(json.dumps(review), encoding="utf-8")
    aggregate = calibration.merge_reports(windows_path, linux_path, review_path)
    assert aggregate["status"] == "CALIBRATION_COMPLETE_NO_STAGE_D_DECISION"
    assert aggregate["manual_artifact_review"]["reviewed_cross_platform_case_count"] == 288
    assert aggregate["manual_artifact_review"]["reviewed_artifact_count"] == 576
    assert aggregate["stage_d_eligible_candidate_count"] == 6
    assert all(
        item["manual_artifact_review"]
        == {
            "status": "COMPLETE",
            "reviewed_case_count": 48,
            "passed_case_count": 48,
            "rejected_case_count": 0,
        }
        for item in aggregate["candidate_outcomes"]
    )
    assert all(
        item["stage_d_consideration"] == "ELIGIBLE_FOR_STAGE_D_PREREGISTRATION_ONLY"
        for item in aggregate["candidate_outcomes"]
    )

    review["decisions"][0]["windows_result_sha256"] = "0" * 64
    review["content_digest"] = calibration._manual_review_digest(review)
    review_path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="result checksum"):
        calibration.merge_reports(windows_path, linux_path, review_path)


def test_vision_runtime_preflight_fails_before_transform_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {"entries": [_entry(0)]}
    content = b"accepted-source"
    manifest["entries"][0]["normalized_sha256"] = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(Path, "read_bytes", lambda _path: content)
    calls: list[tuple[int, int]] = []

    def fail_vision(
        _executable: Path, _model: Path, _content: bytes, width: int, height: int
    ) -> tuple[list[tuple[float, float, float]], str]:
        calls.append((width, height))
        raise calibration.CalibrationFailure(
            calibration.FailureCode.RESULT_QA_FAILED, "RESULT_VISION_QA"
        )

    monkeypatch.setattr(calibration, "_run_vision", fail_vision)
    with pytest.raises(RuntimeError, match="preflight failed"):
        calibration._preflight_vision_runtime(Path("vision"), Path("model"), manifest)
    assert calls == [(512, 512)]


def test_merge_retains_one_failed_case_without_fabricating_repeat_rows(tmp_path: Path) -> None:
    windows, linux = _report("windows_x86_64"), _report("linux_x86_64_network_none")
    failed_case = windows["cases"][0]
    failed_case["status"] = "FAILED"
    failed_case["failure_stage"] = "PLAN_OR_TRANSFORM"
    failed_case["failure_code"] = "PLAN_BUILD_FAILED"
    failed_case["executed_repeat_count"] = 0
    windows["rows"] = [
        row for row in windows["rows"] if row["case_digest"] != failed_case["case_digest"]
    ]
    windows["report_digest"] = calibration._private_report_digest(windows)
    windows_path, linux_path = tmp_path / "windows.json", tmp_path / "linux.json"
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")
    aggregate = calibration.merge_reports(windows_path, linux_path)
    assert aggregate["transform_vision_row_count"] == 1725
    assert aggregate["failure_reason_counts"] == {"PLAN_BUILD_FAILED": 1}


def test_merge_rejects_incomplete_reports_and_cross_platform_cohort_mismatch(
    tmp_path: Path,
) -> None:
    windows, linux = _report("windows_x86_64"), _report("linux_x86_64_network_none")
    windows["rows"] = windows["rows"][:-1]
    windows["report_digest"] = calibration._private_report_digest(windows)
    windows_path, linux_path = tmp_path / "windows.json", tmp_path / "linux.json"
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")
    with pytest.raises(ValueError, match=r"row.*case execution"):
        calibration.merge_reports(windows_path, linux_path)

    windows, linux = _report("windows_x86_64"), _report("linux_x86_64_network_none")
    linux["cohort_digest"] = "9" * 64
    linux["report_digest"] = calibration._private_report_digest(linux)
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")
    with pytest.raises(ValueError, match="identical frozen cohort"):
        calibration.merge_reports(windows_path, linux_path)
