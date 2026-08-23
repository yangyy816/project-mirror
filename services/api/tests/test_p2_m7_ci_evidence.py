from __future__ import annotations

import json
from pathlib import Path

import pytest

from mirror_api.scripts.p2_m7_ci_evidence import EvidenceError, generate_evidence, run

COMMIT_SHA = "d" * 40
MIGRATION_HEAD = "0014_m5_eval_authority"
REQUIRED_TESTS = (
    "test_dataset_cli_never_echoes_invalid_or_unknown_argument_values",
    "test_every_operation_kind_rejects_production_before_backend_dispatch[batch_status]",
    "test_every_operation_kind_is_unavailable_without_an_accepted_backend[batch_status]",
    "test_operation_contract_redacts_backend_failure_and_mismatch",
    "test_m7_modules_have_no_direct_network_database_provider_or_public_api_import",
    "test_m7_is_absent_from_the_public_openapi_contract",
    "test_postgresql_cost_read_model_is_read_only_and_preserves_cost_categories",
    "test_postgresql_cancelled_lease_cannot_resume_after_worker_crash_recovery",
)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    migration = tmp_path / "migration-head.txt"
    migration.write_text(f"{MIGRATION_HEAD} (head)\n", encoding="utf-8")
    openapi = tmp_path / "openapi.json"
    openapi.write_text(
        json.dumps({"openapi": "3.1.0", "paths": {"/health/live": {}}}) + "\n",
        encoding="utf-8",
    )
    cases = "".join(
        f'<testcase classname="p2_m7" name="{name}" time="0.25" />' for name in REQUIRED_TESTS
    )
    results = tmp_path / "p2-m7-results.xml"
    results.write_text(
        '<testsuites><testsuite tests="8" failures="0" errors="0" skipped="0">'
        f"{cases}</testsuite></testsuites>",
        encoding="utf-8",
    )
    return migration, openapi, results


def test_generates_allowlisted_p2_m7_evidence(tmp_path: Path) -> None:
    migration, openapi, results = _fixture(tmp_path)

    evidence = generate_evidence(
        commit_sha=COMMIT_SHA,
        migration_head_path=migration,
        expected_migration_head=MIGRATION_HEAD,
        openapi_path=openapi,
        test_results_path=results,
    )

    assert set(evidence) == {
        "schema_version",
        "commit_sha",
        "migration_head",
        "openapi_sha256",
        "m7_tests",
        "operation_boundary_checks",
    }
    assert evidence["commit_sha"] == COMMIT_SHA
    assert evidence["migration_head"] == MIGRATION_HEAD
    tests = evidence["m7_tests"]
    checks = evidence["operation_boundary_checks"]
    assert isinstance(tests, dict)
    assert isinstance(checks, dict)
    assert tests == {
        "tests": 8,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 2.0,
        "status": "passed",
    }
    assert checks["checks"] == 8
    assert checks["status"] == "passed"
    assert not any("path" in key for key in evidence)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("wrong_sha", "commit SHA"),
        ("multiple_heads", "single expected head"),
        ("failed_test", "zero-skip pass"),
        ("skipped_test", "zero-skip pass"),
        ("missing_check", "checks are absent"),
        ("invalid_openapi", "missing its version"),
    ],
)
def test_rejects_incomplete_or_failed_p2_m7_evidence(
    tmp_path: Path,
    mutation: str,
    error: str,
) -> None:
    migration, openapi, results = _fixture(tmp_path)
    commit_sha = COMMIT_SHA
    if mutation == "wrong_sha":
        commit_sha = "short"
    elif mutation == "multiple_heads":
        migration.write_text(
            f"{MIGRATION_HEAD} (head)\n0015_unexpected (head)\n",
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
            '<testsuite><testcase name="test_unrelated" /></testsuite>', encoding="utf-8"
        )
    elif mutation == "invalid_openapi":
        openapi.write_text('{"paths": {}}\n', encoding="utf-8")

    with pytest.raises(EvidenceError, match=error):
        generate_evidence(
            commit_sha=commit_sha,
            migration_head_path=migration,
            expected_migration_head=MIGRATION_HEAD,
            openapi_path=openapi,
            test_results_path=results,
        )


def test_cli_fails_closed_when_required_input_is_missing(tmp_path: Path) -> None:
    migration, openapi, _ = _fixture(tmp_path)
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
            str(tmp_path / "missing.xml"),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 1
    assert not output.exists()
