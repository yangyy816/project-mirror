"""Synthetic/numeric golden tests for the CC02-A diagnosis-only harness."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from mirror_api.synthetic_dataset.domain import DomainValidationError, ReasonCode
from mirror_api.synthetic_dataset.similarity import SimilarityReasonCode, SimilarityValidationError

SCRIPT = Path(__file__).parents[3] / "scripts" / "research" / "run_p2_m5_cc02_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("cc02_diagnostic", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cc02 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cc02
SPEC.loader.exec_module(cc02)


def _digest(number: int) -> str:
    return f"{number:064x}"


def _terminal(case: int, platform: str, *, stage: str = "SOURCE_ADMISSION") -> dict[str, Any]:
    source = None if stage == "SOURCE_ADMISSION" else _digest(100_000 + case)
    plan = (
        None
        if cc02.STAGES.index(stage) <= cc02.STAGES.index("WARP_PLAN_AUTHORITY")
        else _digest(200_000 + case)
    )
    result = (
        None
        if cc02.STAGES.index(stage) <= cc02.STAGES.index("TRANSFORM")
        else _digest(300_000 + case)
    )
    return {
        "case_digest": _digest(case),
        "candidate": "cheekbone_width",
        "direction": "INCREASE",
        "magnitude_ppm": 15000,
        "platform": platform,
        "terminal_stage": stage,
        "diagnostic_reason": next(iter(cc02.GENERIC_REASONS[stage])),
        "source_reason_family": None,
        "source_reason_code": None,
        "source_sha256": source,
        "result_sha256": result,
        "runtime_manifest_digest": _digest(10),
        "model_sha256": _digest(11),
        "topology_sha256": _digest(12),
        "plan_digest": plan,
        "algorithm_version": "opencv-piecewise-affine-v1",
        "harness_version": cc02.HARNESS_VERSION,
        "taxonomy_version": cc02.TAXONOMY_VERSION,
        "signed_target_delta": None,
    }


def _repeat(case: int, platform: str, index: int) -> dict[str, Any]:
    result = _digest(400_000 + case)
    legacy = {
        "case_digest": _digest(case),
        "candidate": "cheekbone_width",
        "direction": "INCREASE",
        "magnitude_ppm": 15000,
        "repeat": index,
        "source_sha256": _digest(100_000 + case),
        "plan_digest": _digest(200_000 + case),
        "result_sha256": result,
    }
    return {
        "case_digest": _digest(case),
        "candidate": "cheekbone_width",
        "direction": "INCREASE",
        "magnitude_ppm": 15000,
        "platform": platform,
        "repeat_index": index,
        "source_sha256": legacy["source_sha256"],
        "accepted_result_sha256": result,
        "recomputed_result_sha256": result,
        "legacy_row_digest": cc02.legacy_row_digest(legacy),
        "runtime_manifest_digest": _digest(10),
        "model_sha256": _digest(11),
        "topology_sha256": _digest(12),
        "plan_digest": legacy["plan_digest"],
        "algorithm_version": "opencv-piecewise-affine-v1",
    }


def _measurement(case: int, platform: str, index: int) -> dict[str, Any]:
    return {
        "case_digest": _digest(case),
        "candidate": "cheekbone_width",
        "direction": "INCREASE",
        "magnitude_ppm": 15000,
        "platform": platform,
        "measurement_index": index,
        "source_sha256": _digest(100_000 + case),
        "plan_digest": _digest(200_000 + case),
        "recomputed_result_sha256": _digest(300_000 + case),
        "signed_target_delta": -0.01,
        "runtime_manifest_digest": _digest(10),
        "model_sha256": _digest(11),
        "topology_sha256": _digest(12),
        "algorithm_version": "opencv-piecewise-affine-v1",
        "harness_version": cc02.HARNESS_VERSION,
        "taxonomy_version": cc02.TAXONOMY_VERSION,
    }


def _report(platform: str, terminal_cases: range, direction_cases: set[int]) -> dict[str, Any]:
    terminals = [
        _terminal(
            case,
            platform,
            stage="MEASUREMENT_DIRECTION" if case in direction_cases else "SOURCE_ADMISSION",
        )
        for case in terminal_cases
    ]
    for row in terminals:
        if row["terminal_stage"] == "MEASUREMENT_DIRECTION":
            row.update(
                {
                    "diagnostic_reason": "TARGET_DIRECTION_STABLE_MISMATCH",
                    "source_sha256": _digest(100_000 + int(row["case_digest"], 16)),
                    "plan_digest": _digest(200_000 + int(row["case_digest"], 16)),
                    "result_sha256": _digest(300_000 + int(row["case_digest"], 16)),
                }
            )
    successes = [case for case in range(116, 288)]
    repeats = [_repeat(case, platform, index) for case in successes for index in (1, 2, 3)]
    measurements = [
        _measurement(case, platform, index)
        for case in sorted(direction_cases)
        for index in (1, 2, 3)
    ]
    report: dict[str, Any] = {
        "schema": cc02.PRIVATE_REPORT_SCHEMA,
        "harness_version": cc02.HARNESS_VERSION,
        "taxonomy_version": cc02.TAXONOMY_VERSION,
        "platform": platform,
        "diagnostic_manifest_digest": _digest(1),
        "candidate_manifest_digest": _digest(2),
        "legacy_report_sha256": _digest(3),
        "legacy_report_digest": _digest(4),
        "cohort_digest": _digest(5),
        "case_set_digest": _digest(6),
        "runtime_manifest_digest": _digest(10),
        "model_sha256": _digest(11),
        "topology_sha256": _digest(12),
        "algorithm_version": "opencv-piecewise-affine-v1",
        "resource_usage": {
            "identity_count": 12,
            "candidate_count": 6,
            "logical_case_count": 288,
            "platform_case_count": 288,
            "transform_execution_count": len(direction_cases),
            "vision_execution_count": 3 * len(direction_cases),
            "generation_attempt_count": 0,
            "retry_count": 0,
            "download_count": 0,
            "max_concurrency": 1,
            "execution_mode": "SERIAL",
            "wall_clock_seconds": 0,
            "private_output_bytes": 0,
            "started_at_utc": "2026-08-20T00:00:00Z"
            if platform.startswith("windows")
            else "2026-08-20T00:00:01Z",
            "ended_at_utc": "2026-08-20T00:00:00Z"
            if platform.startswith("windows")
            else "2026-08-20T00:00:01Z",
        },
        "resource_outcome": "WITHIN_ENVELOPE",
        "terminal_failure_cases": terminals,
        "legacy_success_repeats": repeats,
        "direction_measurements": measurements,
        "report_digest": "",
    }
    report["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, report, "report_digest"
    )
    return report


def _authority_and_legacy(report: dict[str, Any]) -> tuple[Any, bytes, Any]:
    terminal_digests = {row["case_digest"] for row in report["terminal_failure_cases"]}
    direction_digests = {
        row["case_digest"]
        for row in report["terminal_failure_cases"]
        if row["terminal_stage"] == "MEASUREMENT_DIRECTION"
    }
    cases = tuple(
        cc02.ExpectedCaseAuthority(
            case_digest=_digest(case),
            candidate="cheekbone_width",
            direction="INCREASE",
            magnitude_ppm=15000,
            legacy_outcome="TERMINAL_FAILURE"
            if _digest(case) in terminal_digests
            else "LEGACY_SUCCESS",
            direction_diagnostic=_digest(case) in direction_digests,
        )
        for case in range(288)
    )
    rows = [
        {
            "case_digest": row["case_digest"],
            "candidate": row["candidate"],
            "direction": row["direction"],
            "magnitude_ppm": row["magnitude_ppm"],
            "repeat": row["repeat_index"],
            "source_sha256": row["source_sha256"],
            "plan_digest": row["plan_digest"],
            "result_sha256": row["accepted_result_sha256"],
        }
        for row in report["legacy_success_repeats"]
    ]
    legacy = {
        "schema": "mirror.p2-m5/CC01C-private-platform-report/v2",
        "report_digest": "",
        "platform": report["platform"],
        "runtime_manifest_digest": report["runtime_manifest_digest"],
        "model_sha256": report["model_sha256"],
        "topology_sha256": report["topology_sha256"],
        "candidate_manifest_digest": report["candidate_manifest_digest"],
        "cohort_digest": report["cohort_digest"],
        "case_set_digest": report["case_set_digest"],
        "rows": rows,
        "cases": [
            {
                "case_digest": case.case_digest,
                "candidate": case.candidate,
                "direction": case.direction,
                "magnitude_ppm": case.magnitude_ppm,
                "status": "FAILED"
                if case.legacy_outcome == "TERMINAL_FAILURE"
                else "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW",
                "failure_stage": "MEASUREMENT" if case.direction_diagnostic else None,
                "failure_code": "TARGET_DIRECTION_MISMATCH" if case.direction_diagnostic else None,
            }
            for case in cases
        ],
    }
    legacy["report_digest"] = cc02.canonical_digest(
        "mirror.p2-m5/CC01C-private-platform-report/v2", legacy, "report_digest"
    )
    payload = json.dumps(legacy, sort_keys=True).encode()
    report["legacy_report_sha256"] = hashlib.sha256(payload).hexdigest()
    report["legacy_report_digest"] = legacy["report_digest"]
    report["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, report, "report_digest"
    )
    authority = cc02.ExpectedPlatformAuthority(
        platform=report["platform"],
        diagnostic_manifest_digest=report["diagnostic_manifest_digest"],
        candidate_manifest_digest=report["candidate_manifest_digest"],
        legacy_report_sha256=report["legacy_report_sha256"],
        legacy_report_digest=report["legacy_report_digest"],
        cohort_digest=report["cohort_digest"],
        case_set_digest=report["case_set_digest"],
        runtime_manifest_digest=report["runtime_manifest_digest"],
        model_sha256=report["model_sha256"],
        topology_sha256=report["topology_sha256"],
        algorithm_version=report["algorithm_version"],
        cases=cases,
    )
    counts = cc02.OperationCounts(
        report["resource_usage"]["transform_execution_count"],
        report["resource_usage"]["vision_execution_count"],
    )
    return authority, payload, counts


def _pair_inputs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_authority, left_bytes, left_counts = _authority_and_legacy(left)
    right_authority, right_bytes, right_counts = _authority_and_legacy(right)
    return {
        "expected_authorities": {
            left["platform"]: left_authority,
            right["platform"]: right_authority,
        },
        "legacy_report_bytes": {left["platform"]: left_bytes, right["platform"]: right_bytes},
        "operation_counts": {left["platform"]: left_counts, right["platform"]: right_counts},
    }


def _refresh_report_digest(report: dict[str, Any]) -> None:
    report["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, report, "report_digest"
    )


def _baseline_pair() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    left = _report("windows_x86_64", range(116), set(range(7)))
    right = _report("linux_x86_64_network_none", range(116), set(range(7, 14)))
    return left, right, _pair_inputs(left, right)


def _replace_legacy_payload(
    report: dict[str, Any], inputs: dict[str, Any], legacy_report: dict[str, Any]
) -> None:
    """Keep outer byte bindings coherent so the legacy validator sees the mutation."""
    legacy_report["report_digest"] = cc02.canonical_digest(
        "mirror.p2-m5/CC01C-private-platform-report/v2", legacy_report, "report_digest"
    )
    payload = json.dumps(legacy_report, sort_keys=True).encode()
    platform = report["platform"]
    report["legacy_report_sha256"] = hashlib.sha256(payload).hexdigest()
    report["legacy_report_digest"] = legacy_report["report_digest"]
    _refresh_report_digest(report)
    authority = inputs["expected_authorities"][platform]
    inputs["expected_authorities"][platform] = replace(
        authority,
        legacy_report_sha256=report["legacy_report_sha256"],
        legacy_report_digest=report["legacy_report_digest"],
    )
    inputs["legacy_report_bytes"][platform] = payload


def _assert_pair_rejected_before_output(
    tmp_path: Path,
    left: dict[str, Any],
    right: dict[str, Any],
    inputs: dict[str, Any],
) -> None:
    root = tmp_path / "must-not-exist"
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.write_report_pair_once(left, right, output_root=root, **inputs)
    assert not root.exists()


@pytest.mark.parametrize(
    "stage,generic",
    tuple(
        (stage, generic) for stage, reasons in cc02.GENERIC_REASONS.items() for generic in reasons
    ),
)
def test_every_generic_stage_boundary_is_allowlisted(stage: str, generic: str) -> None:
    assert cc02.classify_exception(
        stage, ValueError("private message"), generic_reason=generic
    ) == (
        generic,
        None,
        None,
    )


@pytest.mark.parametrize("stage,codes", tuple(cc02.DOMAIN_REASONS.items()))
def test_every_domain_stage_code_pair_is_lossless(stage: str, codes: frozenset[ReasonCode]) -> None:
    for code in codes:
        assert cc02.classify_exception(stage, DomainValidationError(code)) == (
            code.value,
            "DOMAIN",
            code.value,
        )


def test_similarity_reason_codes_only_map_at_result_signature() -> None:
    for code in SimilarityReasonCode:
        assert cc02.classify_exception("RESULT_SIGNATURE", SimilarityValidationError(code)) == (
            code.value,
            "SIMILARITY",
            code.value,
        )
        with pytest.raises(cc02.UnclassifiedTerminalFailure):
            cc02.classify_exception("TRANSFORM", SimilarityValidationError(code))


def test_unknown_wrong_and_unexpected_fail_closed_without_exception_text() -> None:
    with pytest.raises(cc02.UnclassifiedTerminalFailure):
        cc02.classify_exception(
            "NO_STAGE", ValueError("secret path"), generic_reason="SOURCE_ADMISSION_REJECTED"
        )
    with pytest.raises(cc02.UnclassifiedTerminalFailure):
        cc02.classify_exception(
            "SPECIFICATION", DomainValidationError(ReasonCode.FOLDOVER_REJECTED)
        )
    with pytest.raises(cc02.UnclassifiedTerminalFailure):
        cc02.classify_exception("SOURCE_ADMISSION", KeyError("private-image"))


def test_direction_classifier_is_closed_and_does_not_claim_success_drift() -> None:
    assert (
        cc02.classify_direction_measurements("INCREASE", [-0.1, -0.2, -0.3])
        == "TARGET_DIRECTION_STABLE_MISMATCH"
    )
    assert (
        cc02.classify_direction_measurements("DECREASE", [-0.1, 0.0, -0.3])
        == "MEASUREMENT_SIGN_UNSTABLE"
    )
    with pytest.raises(cc02.UnclassifiedTerminalFailure):
        cc02.classify_direction_measurements("INCREASE", [0.1, 0.2, 0.3])


def test_canonical_digest_is_order_stable_and_rejects_nan() -> None:
    assert cc02.canonical_digest("test/v1", {"b": 2, "a": 1}, "none") == cc02.canonical_digest(
        "test/v1", {"a": 1, "b": 2}, "none"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.canonical_digest("test/v1", {"a": float("nan")}, "none")


def test_complete_synthetic_pair_has_frozen_cardinalities_and_redacted_output(
    tmp_path: Path,
) -> None:
    left = _report("windows_x86_64", range(116), set(range(7)))
    right = _report("linux_x86_64_network_none", range(116), set(range(7, 14)))
    inputs = _pair_inputs(left, right)
    assert cc02.validate_report_pair(left, right, **inputs)[0]["platform"] == "windows_x86_64"
    root = tmp_path / "new-root"
    cc02.write_report_pair_once(left, right, output_root=root, **inputs)
    assert "private-image" not in (root / "windows_x86_64.json").read_text(encoding="utf-8")
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.write_report_pair_once(left, right, output_root=root, **inputs)


def test_report_rejects_nullability_cardinality_order_resource_and_redaction_breaches() -> None:
    report = _report("windows_x86_64", range(116), set(range(7)))
    authority, _, counts = _authority_and_legacy(report)
    broken = copy.deepcopy(report)
    broken["terminal_failure_cases"][0]["source_sha256"] = "private/path"
    broken["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, broken, "report_digest"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02._validate_report(broken, expected=authority, operation_counts=counts)
    broken = copy.deepcopy(report)
    broken["resource_usage"]["retry_count"] = 1
    broken["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, broken, "report_digest"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02._validate_report(broken, expected=authority, operation_counts=counts)
    broken = copy.deepcopy(report)
    broken["terminal_failure_cases"].append(copy.deepcopy(broken["terminal_failure_cases"][0]))
    broken["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, broken, "report_digest"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02._validate_report(broken, expected=authority, operation_counts=counts)


def test_resource_envelope_rejects_invalid_counts_before_any_operation() -> None:
    usage = _report("windows_x86_64", range(116), set(range(7)))["resource_usage"]
    for key, value in (
        ("identity_count", 11),
        ("candidate_count", 7),
        ("logical_case_count", 287),
        ("platform_case_count", 289),
        ("generation_attempt_count", 1),
        ("max_concurrency", 2),
    ):
        invalid = copy.deepcopy(usage)
        invalid[key] = value
        with pytest.raises(cc02.DiagnosticValidationError):
            cc02.validate_resource_usage(
                invalid, direction_case_count=0, operation_counts=cc02.OperationCounts(0, 0)
            )


def test_admission_and_global_resource_counters_fail_before_over_limit_operation() -> None:
    cc02.validate_admission_counts(
        identity_count=12, candidate_count=6, logical_case_count=288, platform_case_count=576
    )
    for identity_count, candidate_count, logical_case_count, platform_case_count in (
        (11, 6, 288, 576),
        (12, 5, 288, 576),
        (12, 6, 287, 576),
        (12, 6, 288, 575),
    ):
        with pytest.raises(cc02.DiagnosticValidationError):
            cc02.validate_admission_counts(
                identity_count=identity_count,
                candidate_count=candidate_count,
                logical_case_count=logical_case_count,
                platform_case_count=platform_case_count,
            )
    counter = cc02.ResourceCounter(transform_execution_count=576, vision_execution_count=604)
    with pytest.raises(cc02.DiagnosticValidationError):
        counter.reserve_transform()
    with pytest.raises(cc02.DiagnosticValidationError):
        counter.reserve_vision()
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.ResourceCounter(retry_count=1).reserve_transform()


def test_legacy_binding_is_exact_and_drift_is_not_accepted() -> None:
    repeat = _repeat(116, "windows_x86_64", 1)
    accepted = {
        "case_digest": repeat["case_digest"],
        "candidate": repeat["candidate"],
        "direction": repeat["direction"],
        "magnitude_ppm": repeat["magnitude_ppm"],
        "repeat": 1,
        "source_sha256": repeat["source_sha256"],
        "plan_digest": repeat["plan_digest"],
        "result_sha256": repeat["accepted_result_sha256"],
    }
    cc02.validate_legacy_bindings([repeat], [accepted])
    mismatched = copy.deepcopy(repeat)
    mismatched["accepted_result_sha256"] = _digest(999)
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_legacy_bindings([mismatched], [accepted])


def test_legacy_report_bytes_require_checksum_digest_and_report_authority() -> None:
    left = _report("windows_x86_64", range(116), set(range(7)))
    right = _report("linux_x86_64_network_none", range(116), set(range(7, 14)))
    inputs = _pair_inputs(left, right)
    inputs["legacy_report_bytes"]["windows_x86_64"] += b" "
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_report_pair(left, right, **inputs)


def test_authority_resource_and_orphan_direction_fail_before_output_root(tmp_path: Path) -> None:
    left = _report("windows_x86_64", range(116), set(range(7)))
    right = _report("linux_x86_64_network_none", range(116), set(range(7, 14)))
    inputs = _pair_inputs(left, right)
    broken = copy.deepcopy(inputs)
    broken["expected_authorities"]["windows_x86_64"] = cc02.ExpectedPlatformAuthority(
        **{
            **broken["expected_authorities"]["windows_x86_64"].__dict__,
            "model_sha256": _digest(999),
        }
    )
    root = tmp_path / "must-not-exist"
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.write_report_pair_once(left, right, output_root=root, **broken)
    assert not root.exists()
    broken = copy.deepcopy(inputs)
    broken["operation_counts"]["windows_x86_64"] = cc02.OperationCounts(6, 21)
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_report_pair(left, right, **broken)
    orphan = copy.deepcopy(left)
    orphan["direction_measurements"] = orphan["direction_measurements"][3:]
    orphan["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, orphan, "report_digest"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_report_pair(orphan, right, **inputs)


def test_frozen_contract_negative_matrix() -> None:
    left = _report("windows_x86_64", range(116), set(range(7)))
    right = _report("linux_x86_64_network_none", range(116), set(range(7, 14)))
    inputs = _pair_inputs(left, right)
    broken = copy.deepcopy(left)
    broken["legacy_success_repeats"][1]["accepted_result_sha256"] = _digest(987)
    broken["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, broken, "report_digest"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_report_pair(broken, right, **inputs)
    broken = copy.deepcopy(left)
    broken["direction_measurements"][0]["candidate"] = "jaw_width"
    broken["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, broken, "report_digest"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_report_pair(broken, right, **inputs)
    broken = copy.deepcopy(right)
    broken["terminal_failure_cases"][0]["candidate"] = "jaw_width"
    broken["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, broken, "report_digest"
    )
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_report_pair(left, broken, **inputs)
    broken = copy.deepcopy(right)
    broken["resource_usage"]["started_at_utc"] = "2026-08-20T00:00:00Z"
    broken["resource_usage"]["ended_at_utc"] = "2026-08-20T00:00:01Z"
    broken["resource_usage"]["wall_clock_seconds"] = 1
    broken["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, broken, "report_digest"
    )
    authority, payload, counts = _authority_and_legacy(broken)
    overlap_left = copy.deepcopy(left)
    overlap_left["resource_usage"]["ended_at_utc"] = "2026-08-20T00:00:01Z"
    overlap_left["resource_usage"]["wall_clock_seconds"] = 1
    overlap_left["report_digest"] = cc02.canonical_digest(
        cc02.PRIVATE_REPORT_SCHEMA, overlap_left, "report_digest"
    )
    left_authority, left_payload, left_counts = _authority_and_legacy(overlap_left)
    overlap_inputs = copy.deepcopy(inputs)
    overlap_inputs["expected_authorities"]["windows_x86_64"] = left_authority
    overlap_inputs["legacy_report_bytes"]["windows_x86_64"] = left_payload
    overlap_inputs["operation_counts"]["windows_x86_64"] = left_counts
    overlap_inputs["expected_authorities"]["linux_x86_64_network_none"] = authority
    overlap_inputs["legacy_report_bytes"]["linux_x86_64_network_none"] = payload
    overlap_inputs["operation_counts"]["linux_x86_64_network_none"] = counts
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_report_pair(overlap_left, broken, **overlap_inputs)


def test_synced_non_direction_terminal_candidate_and_digest_replacements_fail_closed(
    tmp_path: Path,
) -> None:
    left, right, inputs = _baseline_pair()
    for report in (left, right):
        next(row for row in report["terminal_failure_cases"] if row["case_digest"] == _digest(14))[
            "candidate"
        ] = "jaw_width"
        _refresh_report_digest(report)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)

    left, right, inputs = _baseline_pair()
    for report in (left, right):
        next(row for row in report["terminal_failure_cases"] if row["case_digest"] == _digest(14))[
            "case_digest"
        ] = _digest(999)
        _refresh_report_digest(report)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)


def test_direction_evidence_cannot_move_to_an_unauthorized_terminal_digest(tmp_path: Path) -> None:
    left, right, inputs = _baseline_pair()
    for report, direction_digest in ((left, _digest(0)), (right, _digest(7))):
        direction_terminal = next(
            row
            for row in report["terminal_failure_cases"]
            if row["case_digest"] == direction_digest
        )
        non_direction_terminal = next(
            row for row in report["terminal_failure_cases"] if row["case_digest"] == _digest(14)
        )
        direction_terminal["case_digest"], non_direction_terminal["case_digest"] = (
            non_direction_terminal["case_digest"],
            direction_terminal["case_digest"],
        )
        for row in report["direction_measurements"]:
            if row["case_digest"] == direction_digest:
                row["case_digest"] = _digest(14)
        _refresh_report_digest(report)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)


def test_terminal_success_partition_swap_fails_closed_before_output(tmp_path: Path) -> None:
    left, right, inputs = _baseline_pair()
    for report in (left, right):
        next(row for row in report["terminal_failure_cases"] if row["case_digest"] == _digest(115))[
            "case_digest"
        ] = _digest(116)
        for row in report["legacy_success_repeats"]:
            if row["case_digest"] == _digest(116):
                row["case_digest"] = _digest(115)
        _refresh_report_digest(report)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)


@pytest.mark.parametrize(
    "field,value",
    (
        ("transform_execution_count", True),
        ("transform_execution_count", 1.0),
        ("transform_execution_count", -1),
        ("transform_execution_count", 577),
    ),
)
def test_resource_counter_rejects_non_integer_negative_and_over_ceiling_values(
    field: str, value: object
) -> None:
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.ResourceCounter(**{field: value}).validate_static()


@pytest.mark.parametrize(
    "cases",
    (
        [],
        None,
        ({},) * 288,
        ("not-an-expected-case",) * 288,
    ),
)
def test_expected_authority_cases_require_tuple_of_expected_cases(
    tmp_path: Path, cases: object
) -> None:
    left, right, inputs = _baseline_pair()
    authority = inputs["expected_authorities"]["windows_x86_64"]
    inputs["expected_authorities"]["windows_x86_64"] = replace(authority, cases=cases)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)


@pytest.mark.parametrize("count", (True, 7.0, -1, "seven"))
def test_operation_counts_reject_bool_float_negative_and_wrong_type_before_output(
    tmp_path: Path, count: object
) -> None:
    left, right, inputs = _baseline_pair()
    inputs["operation_counts"]["windows_x86_64"] = cc02.OperationCounts(count, 21)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)


def test_resource_helper_rejects_wrong_operation_counts_object() -> None:
    usage = _report("windows_x86_64", range(116), set(range(7)))["resource_usage"]
    with pytest.raises(cc02.DiagnosticValidationError):
        cc02.validate_resource_usage(usage, direction_case_count=7, operation_counts=object())


@pytest.mark.parametrize(
    "mutation",
    (
        lambda legacy: legacy["cases"][0].__setitem__("status", "UNKNOWN"),
        lambda legacy: legacy["rows"].append(copy.deepcopy(legacy["rows"][0])),
        lambda legacy: legacy["rows"].pop(),
        lambda legacy: legacy["rows"].__setitem__(1, copy.deepcopy(legacy["rows"][0])),
        lambda legacy: legacy["rows"][0].__setitem__("case_digest", _digest(1)),
    ),
    ids=("unknown-status", "extra-row", "missing-row", "duplicate-row", "unreferenced-row"),
)
def test_legacy_status_and_row_sets_are_exact(tmp_path: Path, mutation: Any) -> None:
    left, right, inputs = _baseline_pair()
    legacy = json.loads(inputs["legacy_report_bytes"]["windows_x86_64"])
    mutation(legacy)
    _replace_legacy_payload(left, inputs, legacy)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)


@pytest.mark.parametrize(
    "field,value",
    (
        ("schema", "mirror.p2-m5/CC01C-private-platform-report/v1"),
        ("cohort_digest", _digest(991)),
        ("case_set_digest", _digest(992)),
    ),
)
def test_legacy_schema_and_frozen_digests_must_match(
    tmp_path: Path, field: str, value: str
) -> None:
    left, right, inputs = _baseline_pair()
    legacy = json.loads(inputs["legacy_report_bytes"]["windows_x86_64"])
    legacy[field] = value
    _replace_legacy_payload(left, inputs, legacy)
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)


def test_algorithm_version_is_constant_even_when_report_and_authority_agree(tmp_path: Path) -> None:
    left, right, inputs = _baseline_pair()
    left["algorithm_version"] = "arbitrary-algorithm-version"
    _refresh_report_digest(left)
    authority = inputs["expected_authorities"]["windows_x86_64"]
    inputs["expected_authorities"]["windows_x86_64"] = replace(
        authority, algorithm_version=left["algorithm_version"]
    )
    _assert_pair_rejected_before_output(tmp_path, left, right, inputs)
