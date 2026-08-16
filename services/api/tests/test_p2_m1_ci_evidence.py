from __future__ import annotations

import json
from pathlib import Path

import pytest

from mirror_api.scripts.p2_m1_ci_evidence import EvidenceError, generate_evidence, run

COMMIT_SHA = "b" * 40
MIGRATION_HEAD = "0008_synth_dataset_foundation"
REQUIRED_TESTS = (
    "test_fixture_manifest_admits_only_checksum_bound_non_human_numeric_json",
    "test_repository_has_no_unapproved_p2_dependency_model_or_face_fixture",
    "test_p2_source_has_no_external_url_sdk_import_or_sensitive_logging_path",
    "test_p2_production_capabilities_fail_closed[override0]",
    "test_public_openapi_is_unchanged_by_internal_p2_contracts",
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
        f'<testcase classname="p2_m1" name="{name}" time="0.25" />' for name in REQUIRED_TESTS
    )
    results = tmp_path / "p2-m1-results.xml"
    results.write_text(
        '<testsuites><testsuite tests="5" failures="0" errors="0" skipped="0">'
        f"{cases}</testsuite></testsuites>",
        encoding="utf-8",
    )
    return migration, openapi, results


def test_generates_allowlisted_p2_m1_evidence(tmp_path: Path) -> None:
    migration, openapi, results = _fixture(tmp_path)

    evidence = generate_evidence(
        commit_sha=COMMIT_SHA,
        migration_head_path=migration,
        expected_migration_head=MIGRATION_HEAD,
        openapi_path=openapi,
        test_results_path=results,
    )

    assert evidence["commit_sha"] == COMMIT_SHA
    assert evidence["migration_head"] == MIGRATION_HEAD
    assert set(evidence) == {
        "schema_version",
        "commit_sha",
        "migration_head",
        "openapi_sha256",
        "m1_tests",
        "boundary_scans",
    }
    tests = evidence["m1_tests"]
    scans = evidence["boundary_scans"]
    assert isinstance(tests, dict)
    assert isinstance(scans, dict)
    assert tests["tests"] == 5
    assert tests["skipped"] == 0
    assert scans["status"] == "passed"
    assert scans["checks"] == 5
    assert not any("path" in key for key in evidence)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("wrong_sha", "commit SHA"),
        ("multiple_heads", "single expected head"),
        ("failed_test", "zero-skip pass"),
        ("skipped_test", "zero-skip pass"),
        ("missing_boundary", "boundary checks are absent"),
        ("invalid_openapi", "missing its version"),
    ],
)
def test_rejects_incomplete_or_failed_p2_m1_evidence(
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
            f"{MIGRATION_HEAD} (head)\n0009_unexpected (head)\n",
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
    elif mutation == "missing_boundary":
        results.write_text(
            '<testsuite><testcase name="test_unrelated" /></testsuite>',
            encoding="utf-8",
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
