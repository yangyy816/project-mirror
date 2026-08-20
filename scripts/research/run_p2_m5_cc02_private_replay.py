"""Fail-closed orchestration for the accepted CC02-C private replay.

This module deliberately has no command-line entry point and no filesystem, network,
subprocess, image, runtime, or private-input discovery code.  The Principal supplies
task-scoped, already-authorized ports only after this tracked driver receives its
separate pre-read Gate.  Ordinary CI exercises the deterministic in-memory seams.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, NoReturn, Protocol

import build_p2_m5_cc02_manifest as manifest_builder
import run_p2_m5_cc02_diagnostic as diagnostic

DRIVER_VERSION = "p2-m5-cc02-private-replay-v1"
MANIFEST_DIGEST = "5a0479a21556498d259572a050d659a0e3617429f83e5fd313c842a35591e0a3"
PLATFORM_ORDER = ("linux_x86_64_network_none", "windows_x86_64")
MAX_TRANSFORMS = 576
MAX_VISION_CALLS = 604
MAX_SECONDS_PER_PLATFORM = 7200
MAX_TOTAL_SECONDS = 14400
MAX_PRIVATE_OUTPUT_BYTES_PER_PLATFORM = 4_294_967_296
CONTAINMENT_OUTCOME_ESTABLISHED = "ESTABLISHED"
_SHA256_LENGTH = 64


class ReplayStopCode(StrEnum):
    """Allowlisted stop outcomes; raw exception data is never returned."""

    UNCLASSIFIED_TERMINAL_FAILURE = "UNCLASSIFIED_TERMINAL_FAILURE"
    TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT = "TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT"
    FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE = "FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE"
    RESOURCE_ENVELOPE_BREACH = "RESOURCE_ENVELOPE_BREACH"
    CONTAINMENT_NOT_ESTABLISHED = "CONTAINMENT_NOT_ESTABLISHED"
    OUTPUT_PUBLICATION_REJECTED = "OUTPUT_PUBLICATION_REJECTED"


class ReplayDriverError(ValueError):
    """Safe failure carrying only a frozen stop code."""

    def __init__(self, stop_code: ReplayStopCode) -> None:
        super().__init__(stop_code.value)
        self.stop_code = stop_code


class GenericStageFailure(ValueError):
    """A typed, allowlisted generic replay failure with no raw exception detail."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__("generic stage failure")
        self.stage = stage
        self.reason = reason


def _stop(stop_code: ReplayStopCode) -> NoReturn:
    raise ReplayDriverError(stop_code)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError):
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)


def _required_sha(value: Mapping[str, Any], key: str) -> str:
    candidate = value.get(key)
    if not _is_sha256(candidate):
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    assert isinstance(candidate, str)
    return candidate


def _utc_timestamp(seconds: int) -> str:
    if type(seconds) is not int or seconds < 0:
        _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class CaseBinding:
    """One opaque manifest case, with no path, identity, image, or Prompt field."""

    case_digest: str
    candidate: str
    direction: str
    magnitude_ppm: int
    legacy_outcome: str
    direction_diagnostic: bool


@dataclass(frozen=True)
class PlatformAuthority:
    """The manifest-only authority required before a platform session is opened."""

    platform: str
    expected: diagnostic.ExpectedPlatformAuthority
    cases: tuple[CaseBinding, ...]
    repeat_bindings: Mapping[str, tuple[Mapping[str, Any], ...]]
    direction_case_digests: frozenset[str]


@dataclass(frozen=True)
class StageEvidence:
    """Opaque evidence passed between frozen stages; result bytes stay task-scoped."""

    source_sha256: str | None = None
    plan_digest: str | None = None
    result_bytes: bytes | None = None
    first_direction_measurement: float | None = None


@dataclass(frozen=True)
class PlatformWindow:
    """A driver-measured, monotonic platform interval supplied by a clock port."""

    started_seconds: int
    ended_seconds: int


class ReplaySession(Protocol):
    """Principal-owned private capability; implementation workers never instantiate it."""

    def read_legacy_report(self) -> bytes:
        """Read the one held legacy report after admission and containment only."""

    def run_stage(self, case: CaseBinding, stage: str, evidence: StageEvidence) -> StageEvidence:
        """Execute one frozen stage or raise an accepted typed/generic exception."""

    def additional_direction_measurement(self, case: CaseBinding, result_bytes: bytes) -> float:
        """Return one of the two additional independent Vision measurements."""

    def window(self) -> PlatformWindow:
        """Return the closed platform window without exposing a path or process detail."""


class ReplayPort(Protocol):
    """A task-scoped source/runtime/model capability gated by the Principal."""

    def open_platform(self, authority: PlatformAuthority) -> ReplaySession:
        """Open exactly one serial platform after its containment Gate is established."""


class CustodyGate(Protocol):
    """Principal-only authority and containment verification surface."""

    def validate_registered_inputs(self, authorities: Mapping[str, PlatformAuthority]) -> bool:
        """Verify registry/custody metadata without returning a locator or private bytes."""

    def establish_containment(self, platform: str) -> bool:
        """Prove Linux network-none or Windows runner-and-child outbound deny."""


class PrivateReportSink(Protocol):
    """Principal-owned create-once sink; it must reject an existing output root."""

    def create_pair_once(self, reports: Mapping[str, Mapping[str, Any]]) -> None:
        """Publish both complete private reports atomically or raise a safe exception."""


@dataclass(frozen=True)
class ReplayResult:
    """No report bytes, exception details, private locators, or per-case output escape."""

    status: str
    stop_code: ReplayStopCode | None
    receipt_projection: Mapping[str, Any] | None


@dataclass
class _PlatformMeter:
    transform_count: int = 0
    vision_count: int = 0
    private_output_bytes: int = 0
    accounted_result_cases: set[str] = field(default_factory=set)

    def reserve_transform(self) -> None:
        if self.transform_count >= MAX_TRANSFORMS:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        self.transform_count += 1

    def reserve_vision(self) -> None:
        if self.vision_count >= MAX_VISION_CALLS:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        self.vision_count += 1

    def account_recomputed_result_once(self, case_digest: str, result_bytes: bytes) -> None:
        """Count each recomputed transform result exactly once, before retaining it."""
        if (
            not _is_sha256(case_digest)
            or type(result_bytes) is not bytes
            or not result_bytes
            or case_digest in self.accounted_result_cases
            or self.private_output_bytes + len(result_bytes) > MAX_PRIVATE_OUTPUT_BYTES_PER_PLATFORM
        ):
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        self.accounted_result_cases.add(case_digest)
        self.private_output_bytes += len(result_bytes)


@dataclass
class _GlobalMeter:
    transform_count: int = 0
    vision_count: int = 0
    active_platform: str | None = None
    completed_platforms: list[str] = field(default_factory=list)

    def start(self, platform: str) -> None:
        if self.active_platform is not None or platform in self.completed_platforms:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        if tuple(self.completed_platforms) != PLATFORM_ORDER[: len(self.completed_platforms)]:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        self.active_platform = platform

    def finish(self, platform: str, meter: _PlatformMeter) -> None:
        if self.active_platform != platform:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        if self.transform_count + meter.transform_count > MAX_TRANSFORMS:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        if self.vision_count + meter.vision_count > MAX_VISION_CALLS:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        self.transform_count += meter.transform_count
        self.vision_count += meter.vision_count
        self.active_platform = None
        self.completed_platforms.append(platform)


def _stage[T](
    stage: str,
    operation: Callable[[], T],
) -> tuple[T | None, tuple[str, str | None, str | None] | None]:
    """Map only accepted stage errors and remove all raw exception text."""
    try:
        return operation(), None
    except GenericStageFailure as error:
        if error.stage != stage or error.reason not in diagnostic.GENERIC_REASONS.get(
            stage, frozenset()
        ):
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
        return None, (error.reason, None, None)
    except diagnostic.UnclassifiedTerminalFailure:
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    except Exception as error:
        try:
            return None, diagnostic.classify_exception(stage, error)
        except diagnostic.UnclassifiedTerminalFailure:
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)


def _require_evidence(value: StageEvidence, *, source: bool, plan: bool, result: bool) -> None:
    if (
        type(value) is not StageEvidence
        or (source and not _is_sha256(value.source_sha256))
        or (plan and not _is_sha256(value.plan_digest))
        or (result and (type(value.result_bytes) is not bytes or not value.result_bytes))
    ):
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)


def _terminal_row(
    *,
    case: CaseBinding,
    platform: str,
    stage: str,
    reason: tuple[str, str | None, str | None],
    evidence: StageEvidence,
    authority: PlatformAuthority,
) -> dict[str, Any]:
    stage_index = diagnostic.STAGES.index(stage)
    source = evidence.source_sha256
    plan = evidence.plan_digest
    result = _sha256(evidence.result_bytes) if evidence.result_bytes is not None else None
    if (
        (stage != "SOURCE_ADMISSION" and not _is_sha256(source))
        or (stage_index > diagnostic.STAGES.index("WARP_PLAN_AUTHORITY") and not _is_sha256(plan))
        or (stage_index > diagnostic.STAGES.index("TRANSFORM") and not _is_sha256(result))
    ):
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    return {
        "case_digest": case.case_digest,
        "candidate": case.candidate,
        "direction": case.direction,
        "magnitude_ppm": case.magnitude_ppm,
        "platform": platform,
        "terminal_stage": stage,
        "diagnostic_reason": reason[0],
        "source_reason_family": reason[1],
        "source_reason_code": reason[2],
        "source_sha256": source,
        "result_sha256": result,
        "runtime_manifest_digest": authority.expected.runtime_manifest_digest,
        "model_sha256": authority.expected.model_sha256,
        "topology_sha256": authority.expected.topology_sha256,
        "plan_digest": plan,
        "algorithm_version": authority.expected.algorithm_version,
        "harness_version": diagnostic.HARNESS_VERSION,
        "taxonomy_version": diagnostic.TAXONOMY_VERSION,
        "signed_target_delta": None,
    }


def _repeat_rows(
    case: CaseBinding, evidence: StageEvidence, authority: PlatformAuthority
) -> list[dict[str, Any]]:
    _require_evidence(evidence, source=True, plan=True, result=True)
    assert evidence.result_bytes is not None
    result_sha256 = _sha256(evidence.result_bytes)
    bindings = authority.repeat_bindings.get(case.case_digest)
    if bindings is None or len(bindings) != 3:
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    assert bindings is not None
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        if (
            binding.get("accepted_result_sha256") != result_sha256
            or binding.get("source_sha256") != evidence.source_sha256
            or binding.get("plan_digest") != evidence.plan_digest
        ):
            _stop(ReplayStopCode.TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT)
        repeat_index = binding.get("repeat_index")
        if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
            _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
        rows.append(
            {
                "case_digest": case.case_digest,
                "candidate": case.candidate,
                "direction": case.direction,
                "magnitude_ppm": case.magnitude_ppm,
                "platform": authority.platform,
                "repeat_index": repeat_index,
                "source_sha256": evidence.source_sha256,
                "accepted_result_sha256": binding["accepted_result_sha256"],
                "recomputed_result_sha256": result_sha256,
                "legacy_row_digest": binding["legacy_row_digest"],
                "runtime_manifest_digest": authority.expected.runtime_manifest_digest,
                "model_sha256": authority.expected.model_sha256,
                "topology_sha256": authority.expected.topology_sha256,
                "plan_digest": evidence.plan_digest,
                "algorithm_version": authority.expected.algorithm_version,
            }
        )
    return rows


def _direction_rows(
    *,
    session: ReplaySession,
    case: CaseBinding,
    evidence: StageEvidence,
    authority: PlatformAuthority,
    meter: _PlatformMeter,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _require_evidence(evidence, source=True, plan=True, result=True)
    first_measurement = evidence.first_direction_measurement
    if type(first_measurement) not in {int, float}:
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    assert first_measurement is not None
    if not math.isfinite(float(first_measurement)):
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    assert evidence.result_bytes is not None
    result_bytes = evidence.result_bytes
    values: list[float] = [float(first_measurement)]
    for _ in range(2):
        meter.reserve_vision()
        measured, reason = _stage(
            "MEASUREMENT_DIRECTION",
            lambda: session.additional_direction_measurement(case, result_bytes),
        )
        if reason is not None or type(measured) not in {int, float}:
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
        assert measured is not None
        if not math.isfinite(float(measured)):
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
        values.append(float(measured))
    try:
        diagnostic_reason = diagnostic.classify_direction_measurements(case.direction, values)
    except diagnostic.UnclassifiedTerminalFailure:
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    result_sha256 = _sha256(evidence.result_bytes)
    terminal = _terminal_row(
        case=case,
        platform=authority.platform,
        stage="MEASUREMENT_DIRECTION",
        reason=(diagnostic_reason, None, None),
        evidence=evidence,
        authority=authority,
    )
    measurement_rows = [
        {
            "case_digest": case.case_digest,
            "candidate": case.candidate,
            "direction": case.direction,
            "magnitude_ppm": case.magnitude_ppm,
            "platform": authority.platform,
            "measurement_index": index,
            "source_sha256": evidence.source_sha256,
            "plan_digest": evidence.plan_digest,
            "recomputed_result_sha256": result_sha256,
            "signed_target_delta": value,
            "runtime_manifest_digest": authority.expected.runtime_manifest_digest,
            "model_sha256": authority.expected.model_sha256,
            "topology_sha256": authority.expected.topology_sha256,
            "algorithm_version": authority.expected.algorithm_version,
            "harness_version": diagnostic.HARNESS_VERSION,
            "taxonomy_version": diagnostic.TAXONOMY_VERSION,
        }
        for index, value in enumerate(values, start=1)
    ]
    return terminal, measurement_rows


def _execute_case(
    *,
    session: ReplaySession,
    case: CaseBinding,
    authority: PlatformAuthority,
    meter: _PlatformMeter,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    evidence = StageEvidence()
    for stage in diagnostic.STAGES:
        if stage == "TRANSFORM":
            meter.reserve_transform()
        if stage == "RESULT_VISION_QA":
            meter.reserve_vision()
        if stage == "MEASUREMENT_DIRECTION" and case.direction_diagnostic:
            terminal, measurements = _direction_rows(
                session=session, case=case, evidence=evidence, authority=authority, meter=meter
            )
            return terminal, [], measurements
        if stage == "MEASUREMENT_DIRECTION":
            continue

        def operation(stage: str = stage, evidence: StageEvidence = evidence) -> StageEvidence:
            return session.run_stage(case, stage, evidence)

        observed, reason = _stage(stage, operation)
        if reason is not None:
            if case.legacy_outcome != "TERMINAL_FAILURE" or case.direction_diagnostic:
                _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
            return (
                _terminal_row(
                    case=case,
                    platform=authority.platform,
                    stage=stage,
                    reason=reason,
                    evidence=evidence,
                    authority=authority,
                ),
                [],
                [],
            )
        if type(observed) is not StageEvidence:
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
        assert observed is not None
        if stage == "TRANSFORM":
            if type(observed.result_bytes) is not bytes or not observed.result_bytes:
                _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
            meter.account_recomputed_result_once(case.case_digest, observed.result_bytes)
        evidence = observed
    if case.legacy_outcome != "LEGACY_SUCCESS":
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    return None, _repeat_rows(case, evidence, authority), []


def _build_authorities(manifest: Mapping[str, Any]) -> dict[str, PlatformAuthority]:
    authority_doc = manifest.get("authority")
    report_bindings = manifest.get("platform_report_bindings")
    case_bindings = manifest.get("platform_case_bindings")
    repeat_bindings = manifest.get("legacy_success_repeat_bindings")
    direction_bindings = manifest.get("direction_diagnostic_bindings")
    if not isinstance(authority_doc, Mapping) or not all(
        isinstance(value, list)
        for value in (report_bindings, case_bindings, repeat_bindings, direction_bindings)
    ):
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    assert isinstance(authority_doc, Mapping)
    assert isinstance(report_bindings, list)
    assert isinstance(case_bindings, list)
    assert isinstance(repeat_bindings, list)
    assert isinstance(direction_bindings, list)
    reports = {item.get("platform"): item for item in report_bindings if isinstance(item, Mapping)}
    algorithm_version = authority_doc.get("algorithm_version")
    if algorithm_version != diagnostic.ACCEPTED_ALGORITHM_VERSION:
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    assert isinstance(algorithm_version, str)
    built: dict[str, PlatformAuthority] = {}
    for platform in PLATFORM_ORDER:
        report = reports.get(platform)
        platform_cases = [
            item
            for item in case_bindings
            if isinstance(item, Mapping) and item.get("platform") == platform
        ]
        if not isinstance(report, Mapping) or len(platform_cases) != 288:
            _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
        cases: list[CaseBinding] = []
        for item in platform_cases:
            candidate = item.get("candidate")
            direction = item.get("direction")
            magnitude = item.get("magnitude_ppm")
            legacy_outcome = item.get("legacy_outcome")
            diagnostic_case = item.get("direction_diagnostic")
            digest = item.get("case_digest")
            if (
                not _is_sha256(digest)
                or not isinstance(candidate, str)
                or candidate not in diagnostic.CANDIDATES
                or not isinstance(direction, str)
                or direction not in diagnostic.DIRECTIONS
                or type(magnitude) is not int
                or magnitude not in diagnostic.MAGNITUDES
                or not isinstance(legacy_outcome, str)
                or legacy_outcome not in {"TERMINAL_FAILURE", "LEGACY_SUCCESS"}
                or type(diagnostic_case) is not bool
            ):
                _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
            assert isinstance(digest, str)
            assert isinstance(candidate, str)
            assert isinstance(direction, str)
            assert type(magnitude) is int
            assert isinstance(legacy_outcome, str)
            assert type(diagnostic_case) is bool
            cases.append(
                CaseBinding(
                    digest, candidate, direction, magnitude, legacy_outcome, diagnostic_case
                )
            )
        if len({case.case_digest for case in cases}) != 288:
            _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
        expected_cases = tuple(
            diagnostic.ExpectedCaseAuthority(
                case_digest=case.case_digest,
                candidate=case.candidate,
                direction=case.direction,
                magnitude_ppm=case.magnitude_ppm,
                legacy_outcome=case.legacy_outcome,
                direction_diagnostic=case.direction_diagnostic,
            )
            for case in cases
        )
        expected = diagnostic.ExpectedPlatformAuthority(
            platform=platform,
            diagnostic_manifest_digest=MANIFEST_DIGEST,
            candidate_manifest_digest=_required_sha(authority_doc, "candidate_manifest_digest"),
            legacy_report_sha256=_required_sha(report, "legacy_report_sha256"),
            legacy_report_digest=_required_sha(report, "legacy_report_digest"),
            cohort_digest=_required_sha(authority_doc, "cohort_digest"),
            case_set_digest=_required_sha(authority_doc, "case_set_digest"),
            runtime_manifest_digest=_required_sha(report, "runtime_manifest_digest"),
            model_sha256=_required_sha(authority_doc, "vision_model_sha256"),
            topology_sha256=_required_sha(authority_doc, "topology_sha256"),
            algorithm_version=algorithm_version,
            cases=expected_cases,
        )
        grouped_repeats: dict[str, list[Mapping[str, Any]]] = {}
        for item in repeat_bindings:
            if isinstance(item, Mapping) and item.get("platform") == platform:
                digest = item.get("case_digest")
                if not isinstance(digest, str):
                    _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
                grouped_repeats.setdefault(digest, []).append(item)
        grouped_direction_values: set[str] = set()
        for item in direction_bindings:
            if isinstance(item, Mapping) and item.get("platform") == platform:
                digest = item.get("case_digest")
                if item.get("measurement_count") != 3 or not _is_sha256(digest):
                    _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
                assert isinstance(digest, str)
                grouped_direction_values.add(digest)
        grouped_directions = frozenset(grouped_direction_values)
        expected_direction = frozenset(
            case.case_digest for case in cases if case.direction_diagnostic
        )
        if grouped_directions != expected_direction:
            _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
        built[platform] = PlatformAuthority(
            platform=platform,
            expected=expected,
            cases=tuple(sorted(cases, key=lambda case: case.case_digest)),
            repeat_bindings={
                key: tuple(sorted(value, key=lambda row: int(row["repeat_index"])))
                for key, value in grouped_repeats.items()
            },
            direction_case_digests=grouped_directions,
        )
    return built


def _validate_admission(
    manifest_bytes: bytes, preregistration_bytes: bytes
) -> dict[str, PlatformAuthority]:
    if type(manifest_bytes) is not bytes or type(preregistration_bytes) is not bytes:
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    try:
        manifest_builder.validate_manifest_bytes(manifest_bytes, preregistration_bytes)
        manifest = json.loads(manifest_bytes)
    except (ValueError, TypeError, json.JSONDecodeError):
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    if not isinstance(manifest, dict):
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    if (
        manifest.get("manifest_content_digest") != MANIFEST_DIGEST
        or diagnostic.canonical_digest(
            manifest_builder.MANIFEST_SCHEMA, manifest, "manifest_content_digest"
        )
        != MANIFEST_DIGEST
    ):
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    return _build_authorities(manifest)


def _platform_report(
    *,
    authority: PlatformAuthority,
    terminal_rows: list[dict[str, Any]],
    repeat_rows: list[dict[str, Any]],
    measurement_rows: list[dict[str, Any]],
    meter: _PlatformMeter,
    window: PlatformWindow,
) -> dict[str, Any]:
    if (
        type(window) is not PlatformWindow
        or type(window.started_seconds) is not int
        or type(window.ended_seconds) is not int
        or window.ended_seconds < window.started_seconds
        or window.ended_seconds - window.started_seconds > MAX_SECONDS_PER_PLATFORM
    ):
        _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
    report: dict[str, Any] = {
        "schema": diagnostic.PRIVATE_REPORT_SCHEMA,
        "harness_version": diagnostic.HARNESS_VERSION,
        "taxonomy_version": diagnostic.TAXONOMY_VERSION,
        "platform": authority.platform,
        "diagnostic_manifest_digest": MANIFEST_DIGEST,
        "candidate_manifest_digest": authority.expected.candidate_manifest_digest,
        "legacy_report_sha256": authority.expected.legacy_report_sha256,
        "legacy_report_digest": authority.expected.legacy_report_digest,
        "cohort_digest": authority.expected.cohort_digest,
        "case_set_digest": authority.expected.case_set_digest,
        "runtime_manifest_digest": authority.expected.runtime_manifest_digest,
        "model_sha256": authority.expected.model_sha256,
        "topology_sha256": authority.expected.topology_sha256,
        "algorithm_version": authority.expected.algorithm_version,
        "resource_usage": {
            "identity_count": 12,
            "candidate_count": 6,
            "logical_case_count": 288,
            "platform_case_count": 288,
            "transform_execution_count": meter.transform_count,
            "vision_execution_count": meter.vision_count,
            "generation_attempt_count": 0,
            "retry_count": 0,
            "download_count": 0,
            "max_concurrency": 1,
            "execution_mode": "SERIAL",
            "wall_clock_seconds": window.ended_seconds - window.started_seconds,
            "private_output_bytes": 0,
            "started_at_utc": _utc_timestamp(window.started_seconds),
            "ended_at_utc": _utc_timestamp(window.ended_seconds),
        },
        "resource_outcome": "WITHIN_ENVELOPE",
        "terminal_failure_cases": sorted(terminal_rows, key=lambda row: row["case_digest"]),
        "legacy_success_repeats": sorted(
            repeat_rows, key=lambda row: (row["case_digest"], row["repeat_index"])
        ),
        "direction_measurements": sorted(
            measurement_rows, key=lambda row: (row["case_digest"], row["measurement_index"])
        ),
    }
    if meter.private_output_bytes > MAX_PRIVATE_OUTPUT_BYTES_PER_PLATFORM:
        _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
    report["resource_usage"]["private_output_bytes"] = meter.private_output_bytes
    report["report_digest"] = diagnostic.canonical_digest(
        diagnostic.PRIVATE_REPORT_SCHEMA, report, "report_digest"
    )
    return report


def _execute_platform(
    *, authority: PlatformAuthority, session: ReplaySession, global_meter: _GlobalMeter
) -> tuple[dict[str, Any], bytes, diagnostic.OperationCounts]:
    legacy_report_bytes = session.read_legacy_report()
    if (
        type(legacy_report_bytes) is not bytes
        or _sha256(legacy_report_bytes) != authority.expected.legacy_report_sha256
    ):
        _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
    meter = _PlatformMeter()
    terminal_rows: list[dict[str, Any]] = []
    repeat_rows: list[dict[str, Any]] = []
    measurement_rows: list[dict[str, Any]] = []
    for case in authority.cases:
        terminal, repeats, measurements = _execute_case(
            session=session, case=case, authority=authority, meter=meter
        )
        if terminal is not None:
            terminal_rows.append(terminal)
        repeat_rows.extend(repeats)
        measurement_rows.extend(measurements)
    report = _platform_report(
        authority=authority,
        terminal_rows=terminal_rows,
        repeat_rows=repeat_rows,
        measurement_rows=measurement_rows,
        meter=meter,
        window=session.window(),
    )
    global_meter.finish(authority.platform, meter)
    return (
        report,
        legacy_report_bytes,
        diagnostic.OperationCounts(meter.transform_count, meter.vision_count),
    )


def redacted_receipt_projection(
    reports: Mapping[str, Mapping[str, Any]],
    *,
    containment_outcomes: Mapping[str, object],
) -> dict[str, Any]:
    """Return the sole allowed tracked projection after a fully accepted private pair."""
    if set(reports) != set(PLATFORM_ORDER):
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    if set(containment_outcomes) != set(PLATFORM_ORDER):
        _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
    projection_reports: list[dict[str, Any]] = []
    for platform in PLATFORM_ORDER:
        report = reports.get(platform)
        if not isinstance(report, Mapping):
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
        containment_outcome = containment_outcomes.get(platform)
        if (
            type(containment_outcome) is not str
            or containment_outcome != CONTAINMENT_OUTCOME_ESTABLISHED
        ):
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
        digest = report.get("report_digest")
        usage = report.get("resource_usage")
        if not _is_sha256(digest) or not isinstance(usage, Mapping):
            _stop(ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE)
        projection_reports.append(
            {
                "platform": platform,
                "report_digest": digest,
                "transform_execution_count": usage.get("transform_execution_count"),
                "vision_execution_count": usage.get("vision_execution_count"),
                "wall_clock_seconds": usage.get("wall_clock_seconds"),
                "private_output_bytes": usage.get("private_output_bytes"),
                "resource_outcome": report.get("resource_outcome"),
                "containment_outcome": containment_outcome,
            }
        )
    return {
        "schema": "mirror.p2-m5/CC02-redacted-replay-receipt/v1",
        "driver_version": DRIVER_VERSION,
        "diagnostic_manifest_digest": MANIFEST_DIGEST,
        "platform_reports": projection_reports,
        "outcome": "REPLAY_COMPLETE_READY_FOR_SEPARATE_CC02_D_CONTRACT",
    }


def run_replay(
    *,
    manifest_bytes: bytes,
    preregistration_bytes: bytes,
    custody_gate: CustodyGate,
    replay_port: ReplayPort,
    report_sink: PrivateReportSink,
) -> ReplayResult:
    """Run exactly one serial pair after all non-private admission gates pass.

    Any error returns only an allowlisted stop code.  Reports are held in memory until
    both platforms validate together; no partial output or tracked receipt is created.
    """
    try:
        authorities = _validate_admission(manifest_bytes, preregistration_bytes)
        if not custody_gate.validate_registered_inputs(authorities):
            _stop(ReplayStopCode.FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE)
        global_meter = _GlobalMeter()
        reports: dict[str, dict[str, Any]] = {}
        legacy_bytes: dict[str, bytes] = {}
        counts: dict[str, diagnostic.OperationCounts] = {}
        containment_outcomes: dict[str, str] = {}
        for platform in PLATFORM_ORDER:
            if not custody_gate.establish_containment(platform):
                _stop(ReplayStopCode.CONTAINMENT_NOT_ESTABLISHED)
            containment_outcomes[platform] = CONTAINMENT_OUTCOME_ESTABLISHED
            authority = authorities[platform]
            global_meter.start(platform)
            report, platform_legacy, operation_counts = _execute_platform(
                authority=authority,
                session=replay_port.open_platform(authority),
                global_meter=global_meter,
            )
            reports[platform] = report
            legacy_bytes[platform] = platform_legacy
            counts[platform] = operation_counts
        if tuple(global_meter.completed_platforms) != PLATFORM_ORDER:
            _stop(ReplayStopCode.RESOURCE_ENVELOPE_BREACH)
        diagnostic.validate_report_pair(
            reports["windows_x86_64"],
            reports["linux_x86_64_network_none"],
            expected_authorities={
                platform: authorities[platform].expected for platform in PLATFORM_ORDER
            },
            legacy_report_bytes=legacy_bytes,
            operation_counts=counts,
        )
        receipt_projection = redacted_receipt_projection(
            reports, containment_outcomes=containment_outcomes
        )
        try:
            report_sink.create_pair_once(reports)
        except Exception:
            _stop(ReplayStopCode.OUTPUT_PUBLICATION_REJECTED)
        return ReplayResult("COMPLETE", None, receipt_projection)
    except ReplayDriverError as error:
        return ReplayResult("STOPPED", error.stop_code, None)
    except Exception:
        return ReplayResult("STOPPED", ReplayStopCode.UNCLASSIFIED_TERMINAL_FAILURE, None)
