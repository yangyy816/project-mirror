from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA = "mirror.p2-m5/CC01CCandidateManifest/v1"
EXPECTED_CANDIDATES = {
    "cheekbone_width",
    "chin_height",
    "eye_spacing",
    "jaw_width",
    "mouth_width",
    "nose_width",
}


def _document() -> dict[str, object]:
    path = Path(__file__).parents[3] / "docs" / "research" / "P2_M5_CC01C_CANDIDATE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _content_digest(document: dict[str, object]) -> str:
    facts = {key: value for key, value in document.items() if key != "manifest_content_digest"}
    canonical = json.dumps(
        facts,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(f"{SCHEMA}\n{canonical}".encode()).hexdigest()


def test_cc01c_candidate_manifest_is_complete_and_content_addressed() -> None:
    document = _document()
    assert document["schema_version"] == SCHEMA
    assert document["status"] == "PREREGISTERED_NOT_EXECUTED"
    assert document["manifest_content_digest"] == _content_digest(document)

    candidates = document["candidate_dimensions"]
    assert isinstance(candidates, list)
    assert {item["dimension_key"] for item in candidates} == EXPECTED_CANDIDATES
    assert {item["region_group"] for item in candidates} == {
        "central_face",
        "lower_face",
        "periocular",
        "perioral",
    }
    for candidate in candidates:
        assert set(candidate["control_dimensions"]) == EXPECTED_CANDIDATES - {
            candidate["dimension_key"]
        }
        assert all(0 <= index < 468 for index in candidate["anchors"])

    by_key = {item["dimension_key"]: item for item in candidates}
    assert by_key["jaw_width"]["plan_builder_version"] == "p2-m4-t07-jaw-local-field-v1"
    assert by_key["jaw_width"]["sigma_x_formula"] == "0.12*(source_x(454)-source_x(234))"
    assert document["evaluation_contract"]["magnitude_grid_ppm"] == [15000, 30000]
    assert document["evaluation_contract"]["repeat_count_per_platform_direction_magnitude"] == 3
    resources = document["resource_envelope"]
    assert resources["maximum_transform_vision_rows"] == (
        resources["identity_count"]
        * resources["candidate_count"]
        * resources["direction_count"]
        * resources["magnitude_count"]
        * resources["platform_count"]
        * resources["repeat_count"]
    )
    assert resources["retry_attempts"] == 0
    assert resources["concurrency_per_platform"] == 1
    assert (
        "direction_sign times maximum displacement"
        not in document["plan_rules"]["single_vertical_gaussian"]
    )


def test_cc01c_candidate_manifest_is_premeasurement_and_redacted() -> None:
    document = _document()
    serialized = json.dumps(document, allow_nan=False, sort_keys=True)
    assert re.search(r"[A-Za-z]:\\\\", serialized) is None
    assert all(
        forbidden not in serialized
        for forbidden in (
            ".local-storage",
            "/workspace/",
            "image_bytes",
            "object_key",
            "private_path",
            "prompt_text",
            "raw_landmarks",
        )
    )
    assert document["evaluation_contract"]["threshold_rule"].startswith(
        "CALIBRATION_DISTRIBUTIONS_ONLY"
    )
    assert document["duplicate_calibration"]["stage_c_threshold"] is None
    assert document["failure_interpretation"]["dimension_ready_in_stage_c"] is False
    assert document["boundaries"] == {
        "automatic_age_estimation": False,
        "beauty_score_or_rank": False,
        "network_during_execution": False,
        "production_geometry": False,
        "public_api_change": False,
        "question_bank_release": False,
        "real_user_processing": False,
        "sensitive_classification": False,
        "synthetic_only": True,
    }
