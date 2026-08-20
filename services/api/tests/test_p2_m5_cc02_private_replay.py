"""Synthetic/numeric tests for the non-private CC02-C replay driver."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).parents[3] / "scripts" / "research"
_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(_SCRIPTS))
_SCRIPT = _SCRIPTS / "run_p2_m5_cc02_private_replay.py"
_SPEC = importlib.util.spec_from_file_location("cc02_private_replay", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
replay = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = replay
_SPEC.loader.exec_module(replay)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(number: int) -> str:
    return f"{number:064x}"


def _case(platform: str, *, direction: bool = False) -> replay.CaseBinding:
    return replay.CaseBinding(
        case_digest=_sha(1 if platform.startswith("linux") else 2),
        candidate="cheekbone_width",
        direction="INCREASE",
        magnitude_ppm=15000,
        legacy_outcome="TERMINAL_FAILURE" if direction else "LEGACY_SUCCESS",
        direction_diagnostic=direction,
    )


def _authority(
    platform: str, *, direction: bool = False, accepted_result: str | None = None
) -> replay.PlatformAuthority:
    case = _case(platform, direction=direction)
    legacy = f"legacy-{platform}".encode()
    expected = replay.diagnostic.ExpectedPlatformAuthority(
        platform=platform,
        diagnostic_manifest_digest=replay.MANIFEST_DIGEST,
        candidate_manifest_digest=_sha(10),
        legacy_report_sha256=_digest(legacy),
        legacy_report_digest=_sha(11),
        cohort_digest=_sha(12),
        case_set_digest=_sha(13),
        runtime_manifest_digest=_sha(14),
        model_sha256=_sha(15),
        topology_sha256=_sha(16),
        algorithm_version="opencv-piecewise-affine-v1",
        cases=(
            replay.diagnostic.ExpectedCaseAuthority(
                case_digest=case.case_digest,
                candidate=case.candidate,
                direction=case.direction,
                magnitude_ppm=case.magnitude_ppm,
                legacy_outcome=case.legacy_outcome,
                direction_diagnostic=case.direction_diagnostic,
            ),
        ),
    )
    result = _digest(b"result") if accepted_result is None else accepted_result
    repeats: dict[str, tuple[dict[str, Any], ...]] = {}
    if not direction:
        repeats[case.case_digest] = tuple(
            {
                "repeat_index": index,
                "accepted_result_sha256": result,
                "source_sha256": _sha(20),
                "plan_digest": _sha(21),
                "legacy_row_digest": _sha(30 + index),
            }
            for index in (1, 2, 3)
        )
    return replay.PlatformAuthority(
        platform=platform,
        expected=expected,
        cases=(case,),
        repeat_bindings=repeats,
        direction_case_digests=frozenset({case.case_digest} if direction else ()),
    )


class _Custody:
    def __init__(self, events: list[str], *, admitted: bool = True, contained: bool = True) -> None:
        self.events = events
        self.admitted = admitted
        self.contained = contained

    def validate_registered_inputs(self, authorities: object) -> bool:
        self.events.append("custody")
        return self.admitted

    def establish_containment(self, platform: str) -> bool:
        self.events.append(f"contain:{platform}")
        return self.contained


class _Session:
    def __init__(self, platform: str, events: list[str], *, crash: bool = False) -> None:
        self.platform = platform
        self.events = events
        self.crash = crash

    def read_legacy_report(self) -> bytes:
        self.events.append(f"read:{self.platform}")
        return f"legacy-{self.platform}".encode()

    def run_stage(
        self, case: replay.CaseBinding, stage: str, evidence: replay.StageEvidence
    ) -> replay.StageEvidence:
        self.events.append(f"{self.platform}:{stage}")
        if self.crash:
            raise KeyError("private-path-must-not-leak")
        result = b"result" if stage in {"TRANSFORM", "RESULT_VISION_QA"} else evidence.result_bytes
        return replay.StageEvidence(
            source_sha256=_sha(20) if stage != "SOURCE_ADMISSION" else evidence.source_sha256,
            plan_digest=_sha(21)
            if stage in {"WARP_PLAN_AUTHORITY", "TRANSFORM", "RESULT_VISION_QA", "RESULT_SIGNATURE"}
            else evidence.plan_digest,
            result_bytes=result,
            first_direction_measurement=-0.5
            if stage == "RESULT_VISION_QA" and case.direction_diagnostic
            else evidence.first_direction_measurement,
        )

    def additional_direction_measurement(
        self, case: replay.CaseBinding, result_bytes: bytes
    ) -> float:
        self.events.append(f"measure:{self.platform}")
        return -0.25

    def window(self) -> replay.PlatformWindow:
        offset = 10 if self.platform.startswith("linux") else 30
        return replay.PlatformWindow(offset, offset + 1)


class _Port:
    def __init__(self, events: list[str], *, crash: bool = False) -> None:
        self.events = events
        self.crash = crash

    def open_platform(self, authority: replay.PlatformAuthority) -> _Session:
        self.events.append(f"open:{authority.platform}")
        return _Session(authority.platform, self.events, crash=self.crash)


class _Sink:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = 0

    def create_pair_once(self, reports: object) -> None:
        self.calls += 1
        self.events.append("sink")


def _run_with(
    monkeypatch: pytest.MonkeyPatch,
    events: list[str],
    *,
    direction: bool = False,
    accepted_result: str | None = None,
    custody: _Custody | None = None,
    port: _Port | None = None,
) -> tuple[replay.ReplayResult, _Sink]:
    authorities = {
        "linux_x86_64_network_none": _authority(
            "linux_x86_64_network_none", direction=direction, accepted_result=accepted_result
        ),
        "windows_x86_64": _authority(
            "windows_x86_64", direction=direction, accepted_result=accepted_result
        ),
    }
    monkeypatch.setattr(replay, "_validate_admission", lambda *_: authorities)
    monkeypatch.setattr(replay.diagnostic, "validate_report_pair", lambda *args, **kwargs: None)
    sink = _Sink(events)
    result = replay.run_replay(
        manifest_bytes=b"tracked-manifest-placeholder",
        preregistration_bytes=b"tracked-preregistration-placeholder",
        custody_gate=custody if custody is not None else _Custody(events),
        replay_port=port if port is not None else _Port(events),
        report_sink=sink,
    )
    return result, sink


def test_admission_failure_has_no_private_read_runtime_transform_vision_or_output() -> None:
    events: list[str] = []
    result = replay.run_replay(
        manifest_bytes=b"wrong",
        preregistration_bytes=b"wrong",
        custody_gate=_Custody(events),
        replay_port=_Port(events),
        report_sink=_Sink(events),
    )
    assert result.stop_code is replay.ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE
    assert events == []


def test_tracked_manifest_admission_accepts_canonical_digest_without_effects() -> None:
    manifest_bytes = (_ROOT / "docs/research/P2_M5_CC02_DIAGNOSTIC_MANIFEST.json").read_bytes()
    preregistration_bytes = (
        _ROOT / "docs/research/P2_M5_CC02_DIAGNOSTIC_PREREGISTRATION.md"
    ).read_bytes()
    authorities = replay._validate_admission(manifest_bytes, preregistration_bytes)
    assert tuple(authorities) == replay.PLATFORM_ORDER
    assert all(len(authority.cases) == 288 for authority in authorities.values())
    assert (
        sum(
            len(bindings)
            for authority in authorities.values()
            for bindings in authority.repeat_bindings.values()
        )
        == 1032
    )
    assert sum(len(authority.direction_case_digests) for authority in authorities.values()) == 14


@pytest.mark.parametrize(
    "stage,reason",
    tuple(
        (stage, reason)
        for stage, reasons in replay.diagnostic.GENERIC_REASONS.items()
        for reason in reasons
    ),
)
def test_every_allowlisted_generic_stage_reason_maps_exactly(stage: str, reason: str) -> None:
    def operation() -> None:
        raise replay.GenericStageFailure(stage, reason)

    value, classified = replay._stage(stage, operation)
    assert value is None
    assert classified == (reason, None, None)


def test_wrong_generic_stage_reason_and_raw_value_error_fail_closed() -> None:
    with pytest.raises(replay.ReplayDriverError) as wrong_stage:
        replay._stage(
            "SOURCE_ADMISSION",
            lambda: (_ for _ in ()).throw(
                replay.GenericStageFailure("TRANSFORM", "TRANSFORM_RUNTIME_REJECTED")
            ),
        )
    assert wrong_stage.value.stop_code is replay.ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE
    with pytest.raises(replay.ReplayDriverError) as wrong_reason:
        replay._stage(
            "SOURCE_ADMISSION",
            lambda: (_ for _ in ()).throw(
                replay.GenericStageFailure("SOURCE_ADMISSION", "NOT_ALLOWLISTED")
            ),
        )
    assert wrong_reason.value.stop_code is replay.ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE
    with pytest.raises(replay.ReplayDriverError) as raw_error:
        replay._stage("SOURCE_ADMISSION", lambda: (_ for _ in ()).throw(ValueError("private")))
    assert raw_error.value.stop_code is replay.ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE


def test_custody_and_containment_fail_before_open_or_private_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    result, sink = _run_with(monkeypatch, events, custody=_Custody(events, admitted=False))
    assert result.stop_code is replay.ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE
    assert events == ["custody"]
    assert sink.calls == 0

    events.clear()
    result, sink = _run_with(monkeypatch, events, custody=_Custody(events, contained=False))
    assert result.stop_code is replay.ReplayStopCode.CONTAINMENT_NOT_ESTABLISHED
    assert events == ["custody", "contain:linux_x86_64_network_none"]
    assert sink.calls == 0


def test_serial_platform_order_no_retry_and_create_once_after_both_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    result, sink = _run_with(monkeypatch, events)
    assert result.status == "COMPLETE"
    assert sink.calls == 1
    assert (
        events.index("open:linux_x86_64_network_none")
        < events.index("open:windows_x86_64")
        < events.index("sink")
    )
    assert events.count("open:linux_x86_64_network_none") == 1
    assert events.count("open:windows_x86_64") == 1
    assert result.receipt_projection is not None
    assert result.receipt_projection["schema"] == "mirror.p2-m5/CC02-redacted-replay-receipt/v1"
    assert result.receipt_projection["driver_version"] == replay.DRIVER_VERSION
    assert result.receipt_projection["diagnostic_manifest_digest"] == replay.MANIFEST_DIGEST
    assert (
        result.receipt_projection["outcome"] == "REPLAY_COMPLETE_READY_FOR_SEPARATE_CC02_D_CONTRACT"
    )
    projection_reports = result.receipt_projection["platform_reports"]
    assert projection_reports == [
        {
            "platform": "linux_x86_64_network_none",
            "report_digest": projection_reports[0]["report_digest"],
            "transform_execution_count": 1,
            "vision_execution_count": 1,
            "wall_clock_seconds": 1,
            "private_output_bytes": len(b"result"),
            "resource_outcome": "WITHIN_ENVELOPE",
            "containment_outcome": "ESTABLISHED",
        },
        {
            "platform": "windows_x86_64",
            "report_digest": projection_reports[1]["report_digest"],
            "transform_execution_count": 1,
            "vision_execution_count": 1,
            "wall_clock_seconds": 1,
            "private_output_bytes": len(b"result"),
            "resource_outcome": "WITHIN_ENVELOPE",
            "containment_outcome": "ESTABLISHED",
        },
    ]
    assert all(
        isinstance(item["report_digest"], str) and len(item["report_digest"]) == 64
        for item in projection_reports
    )


def test_legacy_success_sha_mismatch_stops_without_partial_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    result, sink = _run_with(monkeypatch, events, accepted_result=_sha(999))
    assert result.stop_code is replay.ReplayStopCode.TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT
    assert sink.calls == 0
    assert "open:windows_x86_64" not in events


def test_unexpected_exception_is_redacted_and_stops_without_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    result, sink = _run_with(monkeypatch, events, port=_Port(events, crash=True))
    assert result.stop_code is replay.ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE
    assert sink.calls == 0
    assert "private-path-must-not-leak" not in str(result)


def test_direction_case_uses_exactly_three_finite_measurements_and_accepted_taxonomy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    result, sink = _run_with(monkeypatch, events, direction=True)
    assert result.status == "COMPLETE"
    assert sink.calls == 1
    assert events.count("measure:linux_x86_64_network_none") == 2
    assert events.count("measure:windows_x86_64") == 2
    assert events.count("linux_x86_64_network_none:RESULT_VISION_QA") == 1
    assert events.count("windows_x86_64:RESULT_VISION_QA") == 1


def test_resource_counters_are_derived_and_fail_closed_at_frozen_limits() -> None:
    local = replay._PlatformMeter(transform_count=replay.MAX_TRANSFORMS)
    with pytest.raises(replay.ReplayDriverError) as transform_error:
        local.reserve_transform()
    assert transform_error.value.stop_code is replay.ReplayStopCode.RESOURCE_ENVELOPE_BREACH
    local = replay._PlatformMeter(vision_count=replay.MAX_VISION_CALLS)
    with pytest.raises(replay.ReplayDriverError) as vision_error:
        local.reserve_vision()
    assert vision_error.value.stop_code is replay.ReplayStopCode.RESOURCE_ENVELOPE_BREACH
    global_meter = replay._GlobalMeter(transform_count=replay.MAX_TRANSFORMS)
    global_meter.start("linux_x86_64_network_none")
    with pytest.raises(replay.ReplayDriverError):
        global_meter.finish("linux_x86_64_network_none", replay._PlatformMeter(transform_count=1))


def test_recomputed_result_bytes_are_counted_once_and_bounded() -> None:
    meter = replay._PlatformMeter()
    case = _sha(701)
    meter.account_recomputed_result_once(case, b"numeric-result")
    assert meter.private_output_bytes == len(b"numeric-result")
    with pytest.raises(replay.ReplayDriverError) as duplicate:
        meter.account_recomputed_result_once(case, b"numeric-result")
    assert duplicate.value.stop_code is replay.ReplayStopCode.RESOURCE_ENVELOPE_BREACH
    meter = replay._PlatformMeter(private_output_bytes=replay.MAX_PRIVATE_OUTPUT_BYTES_PER_PLATFORM)
    with pytest.raises(replay.ReplayDriverError) as over_limit:
        meter.account_recomputed_result_once(_sha(702), b"x")
    assert over_limit.value.stop_code is replay.ReplayStopCode.RESOURCE_ENVELOPE_BREACH


def test_redacted_receipt_projection_has_no_row_exception_or_capability_fields() -> None:
    reports = {
        "linux_x86_64_network_none": {
            "report_digest": _sha(101),
            "resource_usage": {
                "transform_execution_count": 1,
                "vision_execution_count": 3,
                "wall_clock_seconds": 1,
                "private_output_bytes": 10,
            },
            "resource_outcome": "WITHIN_ENVELOPE",
            "private_path": "must-not-project",
            "terminal_failure_cases": [{"exception": "must-not-project"}],
        },
        "windows_x86_64": {
            "report_digest": _sha(102),
            "resource_usage": {
                "transform_execution_count": 1,
                "vision_execution_count": 3,
                "wall_clock_seconds": 1,
                "private_output_bytes": 11,
            },
            "resource_outcome": "WITHIN_ENVELOPE",
        },
    }
    receipt = replay.redacted_receipt_projection(
        reports,
        containment_outcomes={
            platform: replay.CONTAINMENT_OUTCOME_ESTABLISHED for platform in replay.PLATFORM_ORDER
        },
    )
    rendered = repr(receipt)
    assert "private_path" not in rendered
    assert "exception" not in rendered
    assert "must-not-project" not in rendered


@pytest.mark.parametrize(
    "containment_outcomes",
    [
        {},
        {"linux_x86_64_network_none": "ESTABLISHED"},
        {
            "linux_x86_64_network_none": "ESTABLISHED",
            "windows_x86_64": "UNKNOWN",
        },
        {
            "linux_x86_64_network_none": "ESTABLISHED",
            "windows_x86_64": "ESTABLISHED",
            "unexpected": "ESTABLISHED",
        },
    ],
)
def test_redacted_receipt_rejects_incomplete_or_unknown_containment(
    containment_outcomes: dict[str, str],
) -> None:
    reports = {
        platform: {
            "report_digest": _sha(index),
            "resource_usage": {
                "transform_execution_count": 1,
                "vision_execution_count": 1,
                "wall_clock_seconds": 1,
                "private_output_bytes": 1,
            },
            "resource_outcome": "WITHIN_ENVELOPE",
        }
        for index, platform in enumerate(replay.PLATFORM_ORDER, start=201)
    }
    with pytest.raises(replay.ReplayDriverError) as error:
        replay.redacted_receipt_projection(reports, containment_outcomes=containment_outcomes)
    assert error.value.stop_code is replay.ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE
