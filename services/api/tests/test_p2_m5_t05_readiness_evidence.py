from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_PATH = ROOT / "docs" / "research" / "P2_M5_T05_READINESS_EVIDENCE.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_t05_readiness_evidence_is_source_bound_and_fail_closed() -> None:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert evidence["schema_version"] == "mirror.p2-m5.t05-readiness-evidence/v1"
    for source in evidence["source_evidence"].values():
        assert _sha256(ROOT / source["path"]) == source["sha256"]

    split_authority = json.loads(
        (ROOT / "docs" / "research" / "P2_M4_T08_REPAIR_EVIDENCE.json").read_text(encoding="utf-8")
    )["split_authority"]
    expected = {
        (
            item["identity_reference"],
            item["asset_reference"],
            item["normalized_sha256"],
        )
        for source_group in ("calibration", "holdout")
        for item in split_authority[source_group]
    }
    assignments = evidence["current_authority"]["assignments"]
    actual = {
        (
            item["identity_reference"],
            item["asset_reference"],
            item["normalized_sha256"],
        )
        for item in assignments
    }
    assert actual == expected
    assert len(actual) == len(assignments) == 4
    assert {item["m5_split"] for item in assignments} == {"M4_SEEN"}
    assert evidence["current_authority"]["assignment_counts"] == {
        "CALIBRATION": 0,
        "HOLDOUT": 0,
        "M4_SEEN": 4,
    }
    assert evidence["current_authority"]["ready_dimension_count"] == 0
    assert evidence["current_authority"]["ready_region_group_count"] == 0
    assert evidence["current_authority"]["dimensions"] == [
        {
            "bidirectional_m4_evidence_identities": 4,
            "classification": "EXPERIMENTAL",
            "dimension_key": "jaw_width",
            "m5_holdout_effective_n": 0,
            "region_group": None,
        }
    ]

    decision = evidence["preregistration_decision"]
    assert decision["t05_outcome"] == "FURTHER_RESEARCH"
    assert decision["p2_mvr_v1_result"] == "NOT_EVALUATED"
    assert not any(
        decision[field]
        for field in (
            "evaluation_policy_created",
            "geometry_ontology_version_created",
            "thresholds_selected",
            "final_cohort_manifest_created",
            "holdout_accessed",
            "holdout_execution_authorized",
            "t06_entry_authorized",
        )
    )

    canonical = dict(evidence)
    expected_digest = canonical.pop("document_digest")
    payload = json.dumps(
        canonical,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    assert hashlib.sha256(payload).hexdigest() == expected_digest


def test_t05_readiness_evidence_contains_no_private_payload_or_false_authority() -> None:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(evidence, ensure_ascii=True, sort_keys=True).lower()

    for forbidden in (
        "image_bytes",
        "object_key",
        "signed_url",
        "prompt_text",
        "provider_payload",
        "beauty_score",
        "ethnicity",
        "ancestry",
        "nationality",
    ):
        assert forbidden not in serialized
    assert evidence["boundaries"] == {
        "downloads_performed": False,
        "new_dependencies_or_models": False,
        "new_images_generated": False,
        "production_geometry_enabled": False,
        "question_bank_release_authorized": False,
        "real_user_facial_processing_enabled": False,
        "synthetic_only": True,
    }
