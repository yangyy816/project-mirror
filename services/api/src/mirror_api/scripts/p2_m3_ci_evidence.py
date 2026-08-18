from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

SCHEMA_VERSION = "mirror.p2-m3.ci-evidence/v1"
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_INPUT_BYTES = 4 * 1024 * 1024
_V01_EVIDENCE_SCHEMA = "mirror.p2-m3.v01-normalization-redacted-evidence/v1"
_V01_CORRECTION_SCHEMA = "mirror.p2-m3.v01-migration-head-correction/v1"
_V01_FROZEN_MIGRATION_HEAD = "0011_offline_synth_source"
_REQUIRED_CHECKS = {
    "database_authority": (
        "test_normalization_qa_and_identity_authority_is_monotonic_and_non_bypassable"
    ),
    "append_only_evidence": "test_m3_evidence_and_lineage_are_append_only",
    "offline_source_authority": (
        "test_offline_source_xor_metadata_binding_and_normalization_authority"
    ),
    "deterministic_normalization": (
        "test_normalization_is_deterministic_private_and_concurrency_idempotent"
    ),
    "normalized_storage_tamper": (
        "test_local_normalized_storage_detects_payload_and_metadata_tamper"
    ),
    "required_evidence_fail_closed": "test_required_unknown_or_unmeasured_evidence_fails_closed",
    "hard_gate_non_override": "test_hard_measurement_failure_cannot_be_overridden_by_review",
    "normalized_vision_zero_network": (
        "test_normalized_vision_port_rejects_raw_style_and_is_zero_network_deterministic"
    ),
    "postgresql_policy_binding": (
        "test_real_postgresql_service_finalization_uses_bound_policy_only"
    ),
    "identity_concurrency": (
        "test_identity_registration_is_concurrent_idempotent_and_lease_guarded"
    ),
    "reference_only_worker": "test_m3_task_contracts_are_closed_and_reference_only",
    "reconciliation": "test_reconciliation_recovers_passed_qa_before_identity_registration",
}


class EvidenceError(ValueError):
    """Raised when mandatory P2-M3 evidence is absent, unsafe or inconsistent."""


def _required_bytes(path: Path, *, label: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"{label} is unavailable") from exc
    if not content:
        raise EvidenceError(f"{label} is empty")
    if len(content) > _MAX_INPUT_BYTES:
        raise EvidenceError(f"{label} exceeds the size limit")
    return content


def _migration_head(path: Path, *, expected: str) -> str:
    content = _required_bytes(path, label="migration head evidence").decode("utf-8")
    heads = [line.split()[0] for line in content.splitlines() if line.strip()]
    if heads != [expected]:
        raise EvidenceError("migration head evidence must contain the single expected head")
    return heads[0]


def _openapi_digest(path: Path) -> str:
    content = _required_bytes(path, label="OpenAPI contract")
    try:
        document = cast(object, json.loads(content))
    except json.JSONDecodeError as exc:
        raise EvidenceError("OpenAPI contract is not valid JSON") from exc
    if not isinstance(document, dict) or not isinstance(document.get("openapi"), str):
        raise EvidenceError("OpenAPI contract is missing its version")
    if not isinstance(document.get("paths"), dict):
        raise EvidenceError("OpenAPI contract is missing paths")
    return hashlib.sha256(content).hexdigest()


def _test_evidence(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    content = _required_bytes(path, label="P2-M3 test results")
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise EvidenceError("P2-M3 test results contain forbidden declarations")
    try:
        root = ET.fromstring(content)  # noqa: S314 - bounded CI-generated JUnit without DTD
    except ET.ParseError as exc:
        raise EvidenceError("P2-M3 test results are invalid XML") from exc
    cases = root.findall(".//testcase")
    if not cases:
        raise EvidenceError("P2-M3 test results contain no test cases")

    test_names = {case.attrib.get("name", "") for case in cases}
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    if failures or errors or skipped:
        raise EvidenceError("P2-M3 test results are not a zero-skip pass")

    missing = [
        check
        for check in _REQUIRED_CHECKS.values()
        if not any(name == check or name.startswith(f"{check}[") for name in test_names)
    ]
    if missing:
        raise EvidenceError("required P2-M3 checks are absent")

    duration = 0.0
    for case in cases:
        try:
            duration += float(case.attrib.get("time", "0"))
        except ValueError as exc:
            raise EvidenceError("P2-M3 test duration is invalid") from exc
    return (
        {
            "tests": len(cases),
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "duration_seconds": round(duration, 6),
            "status": "passed",
        },
        {
            "checks": len(_REQUIRED_CHECKS),
            "status": "passed",
            **{name: "passed" for name in _REQUIRED_CHECKS},
        },
    )


def _redacted_document(path: Path, *, label: str, schema_version: str) -> dict[str, object]:
    content = _required_bytes(path, label=label)
    try:
        value = cast(object, json.loads(content))
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict) or value.get("schema_version") != schema_version:
        raise EvidenceError(f"{label} has an unsupported schema")
    claimed_digest = value.get("document_digest")
    if not isinstance(claimed_digest, str) or _SHA256.fullmatch(claimed_digest) is None:
        raise EvidenceError(f"{label} has no valid document digest")
    digest_input = dict(value)
    digest_input.pop("document_digest")
    canonical = json.dumps(
        digest_input,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != claimed_digest:
        raise EvidenceError(f"{label} document digest does not match")
    return cast(dict[str, object], value)


def _qualification_evidence(
    *, holdout_path: Path, authority_path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    holdout = _redacted_document(
        holdout_path,
        label="V03 holdout evidence",
        schema_version="mirror.p2-m3.v03-holdout-redacted-evidence/v1",
    )
    authority = _redacted_document(
        authority_path,
        label="V03 PostgreSQL authority evidence",
        schema_version="mirror.p2-m3.v03-authority-redacted-evidence/v1",
    )
    if (
        holdout.get("outcome") != "PASS_PRIVATE_SYNTHETIC_ONLY"
        or holdout.get("candidate_reference") != "mediapipe-v0.10.35-source-built-r21"
        or holdout.get("official_mediapipe_wheels_status") != "REJECTED_FOR_P2_M3_RUNTIME"
        or holdout.get("model_disposition") != "PRIVATE_RESEARCH_ONLY"
        or holdout.get("distribution_approved") is not False
        or holdout.get("production_vision_enabled") is not False
        or holdout.get("real_user_facial_processing_enabled") is not False
    ):
        raise EvidenceError("V03 holdout evidence violates the approved boundary")
    holdout_digest = holdout.get("document_digest")
    policy_digest = holdout.get("qa_policy_content_digest")
    if (
        not isinstance(holdout_digest, str)
        or _SHA256.fullmatch(holdout_digest) is None
        or not isinstance(policy_digest, str)
        or _SHA256.fullmatch(policy_digest) is None
    ):
        raise EvidenceError("V03 holdout evidence is incomplete")

    counts = authority.get("authority_counts")
    idempotency = authority.get("idempotency")
    limitations = authority.get("limitations")
    if (
        authority.get("qa_policy_content_digest") != policy_digest
        or authority.get("holdout_evidence_digest") != holdout_digest
        or not isinstance(counts, dict)
        or counts
        != {
            "approved_qa_policies": 1,
            "passed_qa_runs": 4,
            "measurements": 36,
            "review_decisions": 24,
            "canonical_identities": 4,
            "identity_registered_records": 4,
            "unchanged_calibration_records": 4,
        }
        or not isinstance(idempotency, dict)
        or idempotency.get("successful_replay") is not True
        or idempotency.get("replay_created_new_identity") is not False
        or idempotency.get("additional_rows_after_replay") != 0
        or not isinstance(limitations, dict)
        or limitations.get("distribution_approved") is not False
        or limitations.get("production_vision_enabled") is not False
        or limitations.get("real_user_facial_processing_enabled") is not False
        or limitations.get("question_bank_release_authorized") is not False
    ):
        raise EvidenceError("V03 PostgreSQL authority evidence violates the approved boundary")
    authority_digest = authority.get("document_digest")
    binding_digest = authority.get("authority_binding_digest")
    if (
        not isinstance(authority_digest, str)
        or _SHA256.fullmatch(authority_digest) is None
        or not isinstance(binding_digest, str)
        or _SHA256.fullmatch(binding_digest) is None
    ):
        raise EvidenceError("V03 PostgreSQL authority evidence is incomplete")

    vision = {
        "status": "approved_for_private_synthetic_m3",
        "candidate_reference": holdout.get("candidate_reference"),
        "holdout_evidence_sha256": holdout_digest,
        "official_mediapipe_wheels_status": "rejected_for_p2_m3_runtime",
        "model_disposition": "private_research_only",
        "distribution_approved": False,
        "production_vision_enabled": False,
        "real_user_facial_processing_enabled": False,
    }
    postgres = {
        "status": "passed",
        "authority_evidence_sha256": authority_digest,
        "authority_binding_sha256": binding_digest,
        "qa_policy_content_sha256": policy_digest,
        "passed_qa_runs": counts["passed_qa_runs"],
        "measurements": counts["measurements"],
        "review_decisions": counts["review_decisions"],
        "canonical_identities": counts["canonical_identities"],
        "idempotent_replay": True,
        "question_bank_release_authorized": False,
    }
    return vision, postgres


def _v01_migration_correction(
    *,
    original_path: Path,
    correction_path: Path,
) -> dict[str, object]:
    original_content = _required_bytes(original_path, label="V01 normalization evidence")
    try:
        original = cast(object, json.loads(original_content))
    except json.JSONDecodeError as exc:
        raise EvidenceError("V01 normalization evidence is not valid JSON") from exc
    if not isinstance(original, dict) or original.get("schema_version") != _V01_EVIDENCE_SCHEMA:
        raise EvidenceError("V01 normalization evidence has an unsupported schema")

    correction = _redacted_document(
        correction_path,
        label="V01 migration-head correction evidence",
        schema_version=_V01_CORRECTION_SCHEMA,
    )
    original_sha256 = hashlib.sha256(original_content).hexdigest()
    item_digest = original.get("item_evidence_digest")
    descriptive_name = original.get("migration_head")
    if (
        correction.get("correction_id") != "P2-M3-R26"
        or correction.get("status") != "FORWARD_CORRECTION"
        or correction.get("original_evidence_reference") != original_path.name
        or correction.get("original_evidence_sha256") != original_sha256
        or not isinstance(item_digest, str)
        or _SHA256.fullmatch(item_digest) is None
        or correction.get("original_item_evidence_digest") != item_digest
        or correction.get("actual_alembic_revision") != _V01_FROZEN_MIGRATION_HEAD
        or correction.get("actual_migration_head") != _V01_FROZEN_MIGRATION_HEAD
        or not isinstance(descriptive_name, str)
        or correction.get("descriptive_migration_name") != descriptive_name
        or descriptive_name == _V01_FROZEN_MIGRATION_HEAD
    ):
        raise EvidenceError("V01 migration-head correction evidence is inconsistent")
    correction_digest = correction.get("document_digest")
    if not isinstance(correction_digest, str) or _SHA256.fullmatch(correction_digest) is None:
        raise EvidenceError("V01 migration-head correction evidence is incomplete")
    return {
        "status": "forward_corrected",
        "original_evidence_sha256": original_sha256,
        "original_item_evidence_sha256": item_digest,
        "correction_evidence_sha256": correction_digest,
        "actual_alembic_revision": _V01_FROZEN_MIGRATION_HEAD,
        "descriptive_migration_name": descriptive_name,
    }


def generate_evidence(
    *,
    commit_sha: str,
    migration_head_path: Path,
    expected_migration_head: str,
    openapi_path: Path,
    test_results_path: Path,
    holdout_evidence_path: Path,
    authority_evidence_path: Path,
    v01_evidence_path: Path,
    v01_correction_path: Path,
) -> dict[str, object]:
    normalized_sha = commit_sha.strip().lower()
    if _COMMIT_SHA.fullmatch(normalized_sha) is None:
        raise EvidenceError("commit SHA must be a full lowercase hexadecimal SHA")
    if not expected_migration_head.strip():
        raise EvidenceError("expected migration head is required")
    tests, checks = _test_evidence(test_results_path)
    vision, postgres = _qualification_evidence(
        holdout_path=holdout_evidence_path,
        authority_path=authority_evidence_path,
    )
    v01_correction = _v01_migration_correction(
        original_path=v01_evidence_path,
        correction_path=v01_correction_path,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "commit_sha": normalized_sha,
        "migration_head": _migration_head(
            migration_head_path,
            expected=expected_migration_head,
        ),
        "openapi_sha256": _openapi_digest(openapi_path),
        "m3_tests": tests,
        "deterministic_checks": checks,
        "private_synthetic_vision": vision,
        "postgresql_authority": postgres,
        "v01_migration_correction": v01_correction,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate allowlisted P2-M3 CI evidence")
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--migration-head-file", type=Path, required=True)
    parser.add_argument("--expected-migration-head", required=True)
    parser.add_argument("--openapi", type=Path, required=True)
    parser.add_argument("--test-results", type=Path, required=True)
    parser.add_argument("--holdout-evidence", type=Path, required=True)
    parser.add_argument("--authority-evidence", type=Path, required=True)
    parser.add_argument("--v01-evidence", type=Path, required=True)
    parser.add_argument("--v01-correction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evidence = generate_evidence(
            commit_sha=cast(str, args.commit_sha),
            migration_head_path=cast(Path, args.migration_head_file),
            expected_migration_head=cast(str, args.expected_migration_head),
            openapi_path=cast(Path, args.openapi),
            test_results_path=cast(Path, args.test_results),
            holdout_evidence_path=cast(Path, args.holdout_evidence),
            authority_evidence_path=cast(Path, args.authority_evidence),
            v01_evidence_path=cast(Path, args.v01_evidence),
            v01_correction_path=cast(Path, args.v01_correction),
        )
        output = cast(Path, args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    except (EvidenceError, OSError) as exc:
        print(f"P2-M3 evidence generation failed: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
