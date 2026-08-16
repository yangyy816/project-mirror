from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

SCHEMA_VERSION = "mirror.p2-m2.ci-evidence/v1"
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
_MAX_JUNIT_BYTES = 4 * 1024 * 1024
_REQUIRED_CHECKS = {
    "reference_only_task": "test_generation_task_message_is_exactly_reference_only",
    "zero_network_and_redacted_logging": (
        "test_m2_pipeline_has_no_network_sdk_url_or_sensitive_logging_path"
    ),
    "phase_and_public_contract_boundary": "test_m2_does_not_cross_into_m3_or_public_api_scope",
    "production_fail_closed": (
        "test_production_generation_pipeline_remains_disabled_and_fail_closed"
    ),
    "budget_and_retry": "test_reservation_concurrency_retry_cost_and_ephemeral_prompt",
    "raw_retention_and_orphan_cleanup": ("test_retention_and_failed_attempt_orphan_reconciliation"),
    "celery_postgresql_round_trip": (
        "test_linux_celery_postgresql_synthetic_generation_round_trip"
    ),
}


class EvidenceError(ValueError):
    """Raised when mandatory P2-M2 deterministic evidence is absent or invalid."""


def _required_bytes(path: Path, *, label: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"{label} is unavailable") from exc
    if not content:
        raise EvidenceError(f"{label} is empty")
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


def _m2_test_evidence(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    content = _required_bytes(path, label="P2-M2 test results")
    if len(content) > _MAX_JUNIT_BYTES:
        raise EvidenceError("P2-M2 test results exceed the size limit")
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise EvidenceError("P2-M2 test results contain forbidden declarations")
    try:
        root = ET.fromstring(content)  # noqa: S314 - bounded CI-generated JUnit without DTD
    except ET.ParseError as exc:
        raise EvidenceError("P2-M2 test results are invalid XML") from exc
    cases = root.findall(".//testcase")
    if not cases:
        raise EvidenceError("P2-M2 test results contain no test cases")

    test_names = {case.attrib.get("name", "") for case in cases}
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    if failures or errors or skipped:
        raise EvidenceError("P2-M2 test results are not a zero-skip pass")

    missing_checks = [
        check
        for check in _REQUIRED_CHECKS.values()
        if not any(name == check or name.startswith(f"{check}[") for name in test_names)
    ]
    if missing_checks:
        raise EvidenceError("required P2-M2 checks are absent")

    duration = 0.0
    for case in cases:
        try:
            duration += float(case.attrib.get("time", "0"))
        except ValueError as exc:
            raise EvidenceError("P2-M2 test duration is invalid") from exc

    summary: dict[str, object] = {
        "tests": len(cases),
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "duration_seconds": round(duration, 6),
        "status": "passed",
    }
    checks: dict[str, object] = {
        "checks": len(_REQUIRED_CHECKS),
        "status": "passed",
        **{name: "passed" for name in _REQUIRED_CHECKS},
    }
    return summary, checks


def generate_evidence(
    *,
    commit_sha: str,
    migration_head_path: Path,
    expected_migration_head: str,
    openapi_path: Path,
    test_results_path: Path,
) -> dict[str, object]:
    normalized_sha = commit_sha.strip().lower()
    if _COMMIT_SHA.fullmatch(normalized_sha) is None:
        raise EvidenceError("commit SHA must be a full lowercase hexadecimal SHA")
    if not expected_migration_head.strip():
        raise EvidenceError("expected migration head is required")
    tests, checks = _m2_test_evidence(test_results_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "commit_sha": normalized_sha,
        "migration_head": _migration_head(
            migration_head_path,
            expected=expected_migration_head,
        ),
        "openapi_sha256": _openapi_digest(openapi_path),
        "m2_tests": tests,
        "deterministic_checks": checks,
        "external_provider_gate": {
            "status": "external_validation_required",
            "production_approved": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate allowlisted P2-M2 CI evidence")
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--migration-head-file", type=Path, required=True)
    parser.add_argument("--expected-migration-head", required=True)
    parser.add_argument("--openapi", type=Path, required=True)
    parser.add_argument("--test-results", type=Path, required=True)
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
        )
        output = cast(Path, args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    except (EvidenceError, OSError) as exc:
        print(f"P2-M2 evidence generation failed: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
