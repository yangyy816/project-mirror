"""Concrete, offline-only adapters for the frozen D02-R2 screening runner.

The runner owns graph construction and authority serialization.  These adapters
derive only the opaque adapter fields from already admitted facts, ResultM3
observations, canonical JPEG bytes, and sealed Principal review decisions.
They deliberately have no filesystem, network, persistence, or provider code.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, NoReturn, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as authority
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest
from mirror_api.synthetic_dataset.similarity import (
    SimilarityValidationError,
    compute_similarity_signature,
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_FIXED_SCALE: Final = 1_000_000_000_000_000_000


class D02ScreeningAdapterError(ValueError):
    """Safe failure: never carries private bytes, paths, or payloads."""


def _fail() -> NoReturn:
    raise D02ScreeningAdapterError("D02 screening adapter rejected its input")


def _required_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail()
    return cast(Mapping[str, Any], value)


def _required_sha256(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail()
    return value


def _fixed18(units: int, *, signed: bool = False) -> str:
    if not signed and units < 0:
        _fail()
    sign = "-" if units < 0 else ""
    absolute = abs(units)
    return f"{sign}{absolute // _FIXED_SCALE}.{absolute % _FIXED_SCALE:018d}"


def _principal_decision_digest(fields: Mapping[str, object]) -> str:
    return mirror_demo_digest(
        "mirror.demo/D02PrincipalArtifactDecision/v1", cast(Mapping[str, JsonValue], fields)
    )


def _facts(source_packet: Mapping[str, object]) -> Mapping[str, Any]:
    raw = source_packet.get("facts")
    if not isinstance(raw, Mapping):
        source_input = source_packet.get("source_input")
        if isinstance(source_input, Mapping):
            raw = source_input.get("formal_facts")
    try:
        return authority.validate_r2_facts(raw)
    except (KeyError, TypeError, ValueError):
        _fail()


def _observation_entry(record: Mapping[str, object], dimension: str) -> Mapping[str, Any]:
    observation = _required_mapping(record.get("measurement_observation"))
    try:
        legacy.validate_measurement_observation(observation, role="RESULT")
        entries = observation["ordered_measurements"]
        if not isinstance(entries, list):
            _fail()
        entry = entries[legacy.DIMENSIONS.index(dimension)]
        parsed = _required_mapping(entry)
        if parsed.get("dimension_key") != dimension:
            _fail()
        return parsed
    except (KeyError, TypeError, ValueError):
        _fail()


def _source_measurements_from_facts(facts: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Rebuild the legacy source measurement projection without trusting its copy."""

    try:
        projection = _required_mapping(facts["source_measurement_projection"])
        projection_entries = projection["ordered_entries"]
        observation = legacy.validate_measurement_observation(
            facts["source_measurement_observation"], role="SOURCE"
        )
        observations = observation["ordered_measurements"]
        if not isinstance(projection_entries, list) or not isinstance(observations, list):
            _fail()
        result: dict[str, Mapping[str, Any]] = {}
        for dimension, projection_entry, observation_entry in zip(
            legacy.DIMENSIONS, projection_entries, observations, strict=True
        ):
            projected = _required_mapping(projection_entry)
            observed = _required_mapping(observation_entry)
            if (
                projected.get("dimension_key") != dimension
                or observed.get("dimension_key") != dimension
                or projected.get("support_state") != "SUPPORTED"
                or observed.get("support_state") != "SUPPORTED"
                or projected.get("unit") != "FACE_HEIGHT_PPM"
            ):
                _fail()
            value_ppm = projected.get("value_ppm")
            confidence_ppm = projected.get("confidence_ppm")
            reliability_ppm = projected.get("reliability_ppm")
            if any(
                type(value) is not int or isinstance(value, bool)
                for value in (value_ppm, confidence_ppm, reliability_ppm)
            ):
                _fail()
            entry: Mapping[str, Any] = {
                "schema_version": "mirror.demo/D02SupportedSourceMeasurement/v1",
                "dimension_key": dimension,
                "raw_value_fixed18": observed["raw_value_fixed18"],
                "raw_confidence_fixed18": _fixed18(cast(int, confidence_ppm) * 1_000_000_000_000),
                "raw_reliability_fixed18": _fixed18(cast(int, reliability_ppm) * 1_000_000_000_000),
                "value_ppm": value_ppm,
                "confidence_ppm": confidence_ppm,
                "reliability_ppm": reliability_ppm,
                "unit": "FACE_HEIGHT_PPM",
            }
            legacy._validate_supported_measurement(entry, dimension=dimension)
            result[dimension] = entry
        if len(result) != len(legacy.DIMENSIONS):
            _fail()
        return result
    except (KeyError, TypeError, ValueError):
        _fail()


class MeasurementGateAdapter:
    """Derive fixed18/ppm gate fields directly from trusted M3 observations.

    ``monotonicity_by_case_id`` is optional because the frozen runner asks for
    the lower magnitude before it has supplied its peer's ResultM3 records.
    Without it, the later report validator is the fail-closed cross-case
    authority; once a peer has been observed this adapter also rejects a local
    disagreement immediately.
    """

    def __init__(self, *, monotonicity_by_case_id: Mapping[str, bool] | None = None) -> None:
        if monotonicity_by_case_id is not None and any(
            not isinstance(case_id, str) or type(value) is not bool
            for case_id, value in monotonicity_by_case_id.items()
        ):
            _fail()
        self._declared_monotonicity = dict(monotonicity_by_case_id or {})
        self._absolute_delta_by_case: dict[str, int] = {}

    def evaluate(
        self,
        *,
        source_packet: Mapping[str, object],
        case_entry: Mapping[str, object],
        result_m3_records: Sequence[Mapping[str, object]],
        result_repeat_certification: Mapping[str, object],
    ) -> Mapping[str, object]:
        try:
            facts = _facts(source_packet)
            case_id = case_entry["case_id"]
            dimension = case_entry["dimension_key"]
            direction = case_entry["direction"]
            if not isinstance(case_id, str) or dimension not in legacy.DIMENSIONS:
                _fail()
            if direction not in {"INCREASE", "DECREASE"} or len(result_m3_records) != 3:
                _fail()
            authority._validate_r2_result_certificate(
                result_repeat_certification, result_m3_records
            )
            source_by_dimension = _source_measurements_from_facts(facts)
            target = source_by_dimension[dimension]
            controls = [
                source_by_dimension[item] for item in legacy.DIMENSIONS if item != dimension
            ]
            result_measurements = [
                self._result_measurement(
                    record=record,
                    target=target,
                    controls=controls,
                    dimension=dimension,
                    direction=direction,
                )
                for record in result_m3_records
            ]
            state, evaluation = self._evaluation(
                case_id=case_id,
                measurements=result_measurements,
            )
            return {
                "source_target_measurement": target,
                "ordered_source_control_measurements": controls,
                "ordered_result_repeat_measurements": result_measurements,
                "measurement_evaluation_state": state,
                "gate_evaluation": evaluation,
            }
        except (KeyError, TypeError, ValueError):
            _fail()

    def _result_measurement(
        self,
        *,
        record: Mapping[str, object],
        target: Mapping[str, Any],
        controls: Sequence[Mapping[str, Any]],
        dimension: str,
        direction: str,
    ) -> dict[str, object]:
        target_result = _observation_entry(record, dimension)
        repeat_index = record.get("repeat_index")
        digest = _required_sha256(record.get("record_digest"))
        if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
            _fail()
        if target_result.get("support_state") == "UNSUPPORTED":
            reason = target_result.get("unsupported_reason")
            if not isinstance(reason, str):
                _fail()
            return {
                "schema_version": "mirror.demo/D02UnsupportedResultMeasurement/v1",
                "repeat_index": repeat_index,
                "result_m3_record_digest": digest,
                "unsupported_dimension_key": dimension,
                "unsupported_reason": reason,
                "measurement_gate_passed": False,
            }
        if target_result.get("support_state") != "SUPPORTED":
            _fail()
        source_units = legacy._fixed18_units(target["raw_value_fixed18"], "source target")
        result_units = legacy._fixed18_units(target_result["raw_value_fixed18"], "result target")
        signed_units = result_units - source_units
        absolute_units = abs(signed_units)
        deltas: list[dict[str, object]] = []
        for ordinal, control in enumerate(controls, start=1):
            control_dimension = control["dimension_key"]
            result_control = _observation_entry(record, control_dimension)
            if result_control.get("support_state") != "SUPPORTED":
                _fail()
            source_control = legacy._fixed18_units(control["raw_value_fixed18"], "source control")
            result_control_units = legacy._fixed18_units(
                result_control["raw_value_fixed18"], "result control"
            )
            drift = abs(result_control_units - source_control)
            deltas.append(
                {
                    "schema_version": "mirror.demo/D02ControlDelta/v1",
                    "control_ordinal": ordinal,
                    "dimension_key": control_dimension,
                    "raw_source_value_fixed18": _fixed18(source_control),
                    "raw_result_value_fixed18": _fixed18(result_control_units),
                    "raw_absolute_delta_fixed18": _fixed18(drift),
                    "drift_ppm": legacy._ppm_from_units(drift),
                }
            )
        maximum = max(
            legacy._fixed18_units(item["raw_absolute_delta_fixed18"], "control drift")
            for item in deltas
        )
        winner = next(
            index
            for index, item in enumerate(deltas, start=1)
            if legacy._fixed18_units(item["raw_absolute_delta_fixed18"], "control drift") == maximum
        )
        winning = deltas[winner - 1]
        return {
            "schema_version": "mirror.demo/D02SupportedResultMeasurement/v1",
            "repeat_index": repeat_index,
            "result_m3_record_digest": digest,
            "raw_result_target_fixed18": _fixed18(result_units),
            "raw_signed_target_delta_fixed18": _fixed18(signed_units, signed=True),
            "raw_target_absolute_delta_fixed18": _fixed18(absolute_units),
            "ordered_control_deltas": deltas,
            "winning_control_ordinal": winner,
            "max_control_dimension_key": winning["dimension_key"],
            "raw_max_control_drift_fixed18": _fixed18(maximum),
            "measured_signed_delta_ppm": legacy._ppm_from_units(signed_units),
            "target_absolute_delta_ppm": legacy._ppm_from_units(absolute_units),
            "drift_ppm": winning["drift_ppm"],
            "direction_gate_passed": signed_units > 0
            if direction == "INCREASE"
            else signed_units < 0,
            "target_min_gate_passed": absolute_units >= 10_000_000_000_000,
            "target_max_gate_passed": absolute_units <= 60_000_000_000_000_000,
            "control_drift_gate_passed": maximum <= 20_000_000_000_000_000,
        }

    def _evaluation(
        self, *, case_id: str, measurements: Sequence[Mapping[str, object]]
    ) -> tuple[str, dict[str, object]]:
        unsupported = [
            item
            for item in measurements
            if item["schema_version"] == "mirror.demo/D02UnsupportedResultMeasurement/v1"
        ]
        if unsupported:
            return (
                "UNSUPPORTED_EXPLICIT",
                {
                    "schema_version": "mirror.demo/D02UnsupportedMeasurementGateEvaluation/v1",
                    "unsupported_repeat_indexes": [item["repeat_index"] for item in unsupported],
                    "ordered_unsupported_reasons": [
                        item["unsupported_reason"] for item in unsupported
                    ],
                    "measurement_gate_passed": False,
                },
            )
        supported = [cast(Mapping[str, Any], item) for item in measurements]
        aggregate = {
            key: all(item[key] is True for item in supported)
            for key in (
                "direction_gate_passed",
                "target_min_gate_passed",
                "target_max_gate_passed",
                "control_drift_gate_passed",
            )
        }
        average_delta = sum(
            legacy._fixed18_units(item["raw_target_absolute_delta_fixed18"], "target delta")
            for item in supported
        ) // len(supported)
        self._absolute_delta_by_case[case_id] = average_delta
        monotonicity = self._declared_monotonicity.get(case_id, True)
        if type(monotonicity) is not bool:
            _fail()
        aggregate["magnitude_monotonicity_gate_passed"] = monotonicity
        aggregate["measurement_gate_passed"] = all(aggregate.values())
        return "SUPPORTED_EVALUATED", {
            "schema_version": "mirror.demo/D02SupportedMeasurementGateEvaluation/v1",
            **aggregate,
        }


@dataclass(frozen=True, repr=False)
class PrincipalArtifactDecision:
    """A sealed, case-specific Principal review decision.

    The digest binds the human decision to one case, first M4 JPEG digest,
    decision order, manual policy and all four artifact observations.  The
    adapter accepts instances only; it cannot consume CLI-style bare booleans.
    """

    case_id: str
    result_sha256: str
    decision_sequence: int
    manual_review_version: str
    manual_review_policy_digest: str
    background_seam: bool
    disconnected_contour: bool
    duplicated_feature: bool
    warp_tear: bool
    review_authority_digest: str

    @classmethod
    def seal(
        cls,
        *,
        case_id: str,
        result_sha256: str,
        decision_sequence: int,
        manual_review_version: str,
        manual_review_policy_digest: str,
        background_seam: bool,
        disconnected_contour: bool,
        duplicated_feature: bool,
        warp_tear: bool,
    ) -> PrincipalArtifactDecision:
        fields: dict[str, object] = {
            "case_id": case_id,
            "result_sha256": result_sha256,
            "decision_sequence": decision_sequence,
            "manual_review_version": manual_review_version,
            "manual_review_policy_digest": manual_review_policy_digest,
            "background_seam": background_seam,
            "disconnected_contour": disconnected_contour,
            "duplicated_feature": duplicated_feature,
            "warp_tear": warp_tear,
        }
        return cls(
            case_id=case_id,
            result_sha256=result_sha256,
            decision_sequence=decision_sequence,
            manual_review_version=manual_review_version,
            manual_review_policy_digest=manual_review_policy_digest,
            background_seam=background_seam,
            disconnected_contour=disconnected_contour,
            duplicated_feature=duplicated_feature,
            warp_tear=warp_tear,
            review_authority_digest=_principal_decision_digest(fields),
        )

    def __post_init__(self) -> None:
        try:
            if (
                not isinstance(self.case_id, str)
                or not self.case_id
                or not isinstance(self.manual_review_version, str)
                or not legacy._VERSION.fullmatch(self.manual_review_version)
                or type(self.decision_sequence) is not int
                or not 1 <= self.decision_sequence <= 48
            ):
                _fail()
            _required_sha256(self.result_sha256)
            _required_sha256(self.manual_review_policy_digest)
            if any(
                type(value) is not bool
                for value in (
                    self.background_seam,
                    self.disconnected_contour,
                    self.duplicated_feature,
                    self.warp_tear,
                )
            ):
                _fail()
            expected = _principal_decision_digest(
                {
                    "case_id": self.case_id,
                    "result_sha256": self.result_sha256,
                    "decision_sequence": self.decision_sequence,
                    "manual_review_version": self.manual_review_version,
                    "manual_review_policy_digest": self.manual_review_policy_digest,
                    "background_seam": self.background_seam,
                    "disconnected_contour": self.disconnected_contour,
                    "duplicated_feature": self.duplicated_feature,
                    "warp_tear": self.warp_tear,
                }
            )
            if self.review_authority_digest != expected:
                _fail()
        except (KeyError, TypeError, ValueError):
            _fail()


class ManualReviewAdapter:
    """Expose only sealed Principal decisions that match the M4 case binding."""

    def __init__(self, decisions_by_case_id: Mapping[str, PrincipalArtifactDecision]) -> None:
        if not decisions_by_case_id or any(
            not isinstance(case_id, str)
            or not isinstance(decision, PrincipalArtifactDecision)
            or decision.case_id != case_id
            for case_id, decision in decisions_by_case_id.items()
        ):
            _fail()
        self._decisions = dict(decisions_by_case_id)

    def decision_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        case_entry: Mapping[str, object],
        m4_record: Mapping[str, object],
        decision_sequence: int,
        manual_review_policy_digest: str,
    ) -> Mapping[str, object]:
        del source_packet
        try:
            case_id = case_entry["case_id"]
            result_sha256 = m4_record["result_sha256"]
            if not isinstance(case_id, str) or not isinstance(result_sha256, str):
                _fail()
            decision = self._decisions.get(case_id)
            if (
                decision is None
                or decision.result_sha256 != result_sha256
                or decision.decision_sequence != decision_sequence
                or decision.manual_review_policy_digest != manual_review_policy_digest
            ):
                _fail()
            return {
                "manual_review_version": decision.manual_review_version,
                "decision_sequence": decision.decision_sequence,
                "background_seam": decision.background_seam,
                "disconnected_contour": decision.disconnected_contour,
                "duplicated_feature": decision.duplicated_feature,
                "warp_tear": decision.warp_tear,
                "review_authority_digest": decision.review_authority_digest,
            }
        except (KeyError, TypeError, ValueError):
            _fail()


class PHashAdapter:
    """Compute pHash only from checksum-bound canonical JPEG bytes in memory."""

    def __init__(self, canonical_jpeg_by_sha256: Mapping[str, bytes]) -> None:
        checked: dict[str, bytes] = {}
        for sha256, jpeg in canonical_jpeg_by_sha256.items():
            _required_sha256(sha256)
            if type(jpeg) is not bytes or not jpeg or hashlib.sha256(jpeg).hexdigest() != sha256:
                _fail()
            checked[sha256] = jpeg
        self._jpeg_by_sha256 = checked

    def phash_hex(self, *, image_record: Mapping[str, object]) -> str:
        try:
            sha256 = _required_sha256(image_record["sha256"])
            width = image_record["width"]
            height = image_record["height"]
            byte_size = image_record["byte_size"]
            if (
                image_record.get("mime_type") != "image/jpeg"
                or type(width) is not int
                or type(height) is not int
                or type(byte_size) is not int
                or byte_size < 1
            ):
                _fail()
            jpeg = self._jpeg_by_sha256.get(sha256)
            if jpeg is None or len(jpeg) != byte_size:
                _fail()
            return compute_similarity_signature(
                jpeg,
                expected_width=width,
                expected_height=height,
                expected_sha256=sha256,
            ).phash_hex
        except (KeyError, TypeError, ValueError, SimilarityValidationError):
            _fail()
