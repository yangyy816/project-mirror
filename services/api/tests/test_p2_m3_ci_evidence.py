from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mirror_api.scripts.p2_m3_ci_evidence import EvidenceError, generate_evidence, run

COMMIT_SHA = "d" * 40
MIGRATION_HEAD = "0011_offline_synth_source"
POLICY_DIGEST = "8" * 64
HOLDOUT_DIGEST = "7" * 64
REQUIRED_TESTS = (
    "test_normalization_qa_and_identity_authority_is_monotonic_and_non_bypassable",
    "test_m3_evidence_and_lineage_are_append_only",
    "test_offline_source_xor_metadata_binding_and_normalization_authority",
    "test_normalization_is_deterministic_private_and_concurrency_idempotent",
    "test_local_normalized_storage_detects_payload_and_metadata_tamper",
    "test_required_unknown_or_unmeasured_evidence_fails_closed",
    "test_hard_measurement_failure_cannot_be_overridden_by_review",
    "test_normalized_vision_port_rejects_raw_style_and_is_zero_network_deterministic",
    "test_real_postgresql_service_finalization_uses_bound_policy_only",
    "test_identity_registration_is_concurrent_idempotent_and_lease_guarded",
    "test_m3_task_contracts_are_closed_and_reference_only",
    "test_reconciliation_recovers_passed_qa_before_identity_registration",
)


def _write_redacted(path: Path, value: dict[str, object]) -> None:
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    value["document_digest"] = hashlib.sha256(canonical).hexdigest()
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    migration = tmp_path / "migration-head.txt"
    migration.write_text(f"{MIGRATION_HEAD} (head)\n", encoding="utf-8")
    openapi = tmp_path / "openapi.json"
    openapi.write_text(
        json.dumps({"openapi": "3.1.0", "paths": {"/health/live": {}}}) + "\n",
        encoding="utf-8",
    )
    cases = "".join(
        f'<testcase classname="p2_m3" name="{name}" time="0.25" />' for name in REQUIRED_TESTS
    )
    results = tmp_path / "p2-m3-results.xml"
    results.write_text(
        '<testsuites><testsuite tests="12" failures="0" errors="0" skipped="0">'
        f"{cases}</testsuite></testsuites>",
        encoding="utf-8",
    )
    holdout = tmp_path / "holdout.json"
    _write_redacted(
        holdout,
        {
            "schema_version": "mirror.p2-m3.v03-holdout-redacted-evidence/v1",
            "candidate_reference": "mediapipe-v0.10.35-source-built-r21",
            "qa_policy_content_digest": POLICY_DIGEST,
            "outcome": "PASS_PRIVATE_SYNTHETIC_ONLY",
            "official_mediapipe_wheels_status": "REJECTED_FOR_P2_M3_RUNTIME",
            "model_disposition": "PRIVATE_RESEARCH_ONLY",
            "distribution_approved": False,
            "production_vision_enabled": False,
            "real_user_facial_processing_enabled": False,
        },
    )
    holdout_value = json.loads(holdout.read_text(encoding="utf-8"))
    authority = tmp_path / "authority.json"
    _write_redacted(
        authority,
        {
            "schema_version": "mirror.p2-m3.v03-authority-redacted-evidence/v1",
            "qa_policy_content_digest": POLICY_DIGEST,
            "holdout_evidence_digest": holdout_value["document_digest"],
            "authority_binding_digest": "6" * 64,
            "authority_counts": {
                "approved_qa_policies": 1,
                "passed_qa_runs": 4,
                "measurements": 36,
                "review_decisions": 24,
                "canonical_identities": 4,
                "identity_registered_records": 4,
                "unchanged_calibration_records": 4,
            },
            "idempotency": {
                "successful_replay": True,
                "replay_created_new_identity": False,
                "additional_rows_after_replay": 0,
            },
            "limitations": {
                "distribution_approved": False,
                "production_vision_enabled": False,
                "real_user_facial_processing_enabled": False,
                "question_bank_release_authorized": False,
            },
        },
    )
    return migration, openapi, results, holdout, authority


def test_generates_allowlisted_p2_m3_evidence(tmp_path: Path) -> None:
    migration, openapi, results, holdout, authority = _fixture(tmp_path)
    evidence = generate_evidence(
        commit_sha=COMMIT_SHA,
        migration_head_path=migration,
        expected_migration_head=MIGRATION_HEAD,
        openapi_path=openapi,
        test_results_path=results,
        holdout_evidence_path=holdout,
        authority_evidence_path=authority,
    )

    assert set(evidence) == {
        "schema_version",
        "commit_sha",
        "migration_head",
        "openapi_sha256",
        "m3_tests",
        "deterministic_checks",
        "private_synthetic_vision",
        "postgresql_authority",
    }
    assert evidence["schema_version"] == "mirror.p2-m3.ci-evidence/v1"
    assert evidence["commit_sha"] == COMMIT_SHA
    assert evidence["migration_head"] == MIGRATION_HEAD
    tests = evidence["m3_tests"]
    checks = evidence["deterministic_checks"]
    vision = evidence["private_synthetic_vision"]
    postgres = evidence["postgresql_authority"]
    assert isinstance(tests, dict) and tests["skipped"] == 0
    assert isinstance(checks, dict) and checks["checks"] == 12
    assert isinstance(vision, dict)
    assert vision["status"] == "approved_for_private_synthetic_m3"
    assert vision["production_vision_enabled"] is False
    assert isinstance(postgres, dict)
    assert postgres["canonical_identities"] == 4
    assert postgres["question_bank_release_authorized"] is False
    assert not any("path" in key or "database_name" in key for key in evidence)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("wrong_sha", "commit SHA"),
        ("multiple_heads", "single expected head"),
        ("failed_test", "zero-skip pass"),
        ("skipped_test", "zero-skip pass"),
        ("missing_check", "checks are absent"),
        ("holdout_tamper", "document digest does not match"),
        ("production_enabled", "approved boundary"),
        ("authority_count", "approved boundary"),
    ],
)
def test_rejects_incomplete_failed_or_boundary_violating_evidence(
    tmp_path: Path,
    mutation: str,
    error: str,
) -> None:
    migration, openapi, results, holdout, authority = _fixture(tmp_path)
    commit_sha = COMMIT_SHA
    if mutation == "wrong_sha":
        commit_sha = "short"
    elif mutation == "multiple_heads":
        migration.write_text(
            f"{MIGRATION_HEAD} (head)\n0012_unexpected (head)\n",
            encoding="utf-8",
        )
    elif mutation == "failed_test":
        results.write_text(
            '<testsuite><testcase name="test_unrelated"><failure /></testcase></testsuite>',
            encoding="utf-8",
        )
    elif mutation == "skipped_test":
        results.write_text(
            '<testsuite><testcase name="test_unrelated"><skipped /></testcase></testsuite>',
            encoding="utf-8",
        )
    elif mutation == "missing_check":
        results.write_text(
            '<testsuite><testcase name="test_unrelated" /></testsuite>',
            encoding="utf-8",
        )
    elif mutation == "holdout_tamper":
        value = json.loads(holdout.read_text(encoding="utf-8"))
        value["candidate_reference"] = "tampered"
        holdout.write_text(json.dumps(value), encoding="utf-8")
    elif mutation == "production_enabled":
        value = json.loads(holdout.read_text(encoding="utf-8"))
        value.pop("document_digest")
        value["production_vision_enabled"] = True
        _write_redacted(holdout, value)
    elif mutation == "authority_count":
        value = json.loads(authority.read_text(encoding="utf-8"))
        value.pop("document_digest")
        value["authority_counts"]["canonical_identities"] = 5
        _write_redacted(authority, value)

    with pytest.raises(EvidenceError, match=error):
        generate_evidence(
            commit_sha=commit_sha,
            migration_head_path=migration,
            expected_migration_head=MIGRATION_HEAD,
            openapi_path=openapi,
            test_results_path=results,
            holdout_evidence_path=holdout,
            authority_evidence_path=authority,
        )


def test_cli_fails_closed_when_required_input_is_missing(tmp_path: Path) -> None:
    migration, openapi, results, holdout, _ = _fixture(tmp_path)
    output = tmp_path / "evidence.json"
    exit_code = run(
        [
            "--commit-sha",
            COMMIT_SHA,
            "--migration-head-file",
            str(migration),
            "--expected-migration-head",
            MIGRATION_HEAD,
            "--openapi",
            str(openapi),
            "--test-results",
            str(results),
            "--holdout-evidence",
            str(holdout),
            "--authority-evidence",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
        ]
    )
    assert exit_code == 1
    assert not output.exists()
