from __future__ import annotations

import json
from pathlib import Path

import pytest

from mirror_api.scripts.phase1_ci_evidence import EvidenceError, generate_evidence, run

COMMIT_SHA = "a" * 40
MIGRATION_HEAD = "0007_account_quarantine_evidence"


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    migration = tmp_path / "migration-head.txt"
    migration.write_text(f"{MIGRATION_HEAD} (head)\n", encoding="utf-8")
    openapi = tmp_path / "openapi.json"
    openapi.write_text(
        json.dumps({"openapi": "3.1.0", "paths": {"/health/live": {}}}) + "\n",
        encoding="utf-8",
    )
    results = tmp_path / "phase1-integration-results.xml"
    results.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="phase1" '
        'name="test_phase1_vertical_lifecycle_and_recovery_is_owner_bound" '
        'time="1.25" /></testsuite></testsuites>',
        encoding="utf-8",
    )
    return migration, openapi, results


def test_generates_allowlisted_evidence(tmp_path: Path) -> None:
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
        "openapi",
        "phase1_integration",
    }
    integration = evidence["phase1_integration"]
    assert isinstance(integration, dict)
    assert integration["status"] == "passed"
    assert integration["skipped"] == 0


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("wrong_sha", "commit SHA"),
        ("multiple_heads", "single expected head"),
        ("failed_test", "zero-skip pass"),
        ("skipped_test", "zero-skip pass"),
        ("missing_vertical", "vertical test is absent"),
        ("invalid_openapi", "missing its version"),
    ],
)
def test_rejects_incomplete_or_failed_evidence(
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
            f"{MIGRATION_HEAD} (head)\n0008_unexpected (head)\n",
            encoding="utf-8",
        )
    elif mutation == "failed_test":
        results.write_text(
            "<testsuite><testcase "
            'name="test_phase1_vertical_lifecycle_and_recovery_is_owner_bound">'
            "<failure /></testcase></testsuite>",
            encoding="utf-8",
        )
    elif mutation == "skipped_test":
        results.write_text(
            "<testsuite><testcase "
            'name="test_phase1_vertical_lifecycle_and_recovery_is_owner_bound">'
            "<skipped /></testcase></testsuite>",
            encoding="utf-8",
        )
    elif mutation == "missing_vertical":
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
