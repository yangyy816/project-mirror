from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

SCHEMA_VERSION = "mirror.phase1.ci-evidence/v1"
EXPECTED_VERTICAL_TEST = "test_phase1_vertical_lifecycle_and_recovery_is_owner_bound"
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
_MAX_JUNIT_BYTES = 1024 * 1024


class EvidenceError(ValueError):
    """Raised when required Phase 1 evidence is absent or invalid."""


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


def _openapi_evidence(path: Path) -> dict[str, object]:
    content = _required_bytes(path, label="OpenAPI contract")
    try:
        document = cast(object, json.loads(content))
    except json.JSONDecodeError as exc:
        raise EvidenceError("OpenAPI contract is not valid JSON") from exc
    if not isinstance(document, dict) or not isinstance(document.get("openapi"), str):
        raise EvidenceError("OpenAPI contract is missing its version")
    if not isinstance(document.get("paths"), dict):
        raise EvidenceError("OpenAPI contract is missing paths")
    return {
        "path": path.as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _integration_evidence(path: Path) -> dict[str, object]:
    content = _required_bytes(path, label="Phase 1 integration test results")
    if len(content) > _MAX_JUNIT_BYTES:
        raise EvidenceError("Phase 1 integration test results exceed the size limit")
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise EvidenceError("Phase 1 integration test results contain forbidden declarations")
    try:
        root = ET.fromstring(content)  # noqa: S314 - bounded CI-generated JUnit without DTD
    except ET.ParseError as exc:
        raise EvidenceError("Phase 1 integration test results are invalid XML") from exc
    cases = root.findall(".//testcase")
    if not cases:
        raise EvidenceError("Phase 1 integration test results contain no test cases")

    test_names = [case.attrib.get("name", "") for case in cases]
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    if EXPECTED_VERTICAL_TEST not in test_names:
        raise EvidenceError("required Phase 1 vertical test is absent")
    if failures or errors or skipped:
        raise EvidenceError("Phase 1 integration test results are not a zero-skip pass")

    duration = 0.0
    for case in cases:
        try:
            duration += float(case.attrib.get("time", "0"))
        except ValueError as exc:
            raise EvidenceError("Phase 1 integration test duration is invalid") from exc
    return {
        "expected_test": EXPECTED_VERTICAL_TEST,
        "tests": len(cases),
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "duration_seconds": round(duration, 6),
        "status": "passed",
    }


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
    return {
        "schema_version": SCHEMA_VERSION,
        "commit_sha": normalized_sha,
        "migration_head": _migration_head(
            migration_head_path,
            expected=expected_migration_head,
        ),
        "openapi": _openapi_evidence(openapi_path),
        "phase1_integration": _integration_evidence(test_results_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate allowlisted Phase 1 CI evidence")
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
        print(f"phase1 evidence generation failed: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
