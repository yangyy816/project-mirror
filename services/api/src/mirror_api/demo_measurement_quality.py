"""Pure, fail-closed D02 measurement-observation and repeat-certification authority.

This module deliberately has no database, provider, asset, or private-runtime
dependency.  Callers supply original normalized XY *string tokens* only.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Final, Literal

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type ObservationRole = Literal["SOURCE", "RESULT"]

MEASUREMENT_OBSERVATION_SCHEMA: Final = "mirror.demo/D02MeasurementObservation/v1"
OBSERVATION_ENTRY_SCHEMA: Final = "mirror.demo/D02MeasurementObservationEntry/v1"
SOURCE_SUBJECT_SCHEMA: Final = "mirror.demo/D02SourceObservationSubject/v1"
RESULT_SUBJECT_SCHEMA: Final = "mirror.demo/D02ResultObservationSubject/v1"
SOURCE_CERTIFICATE_SCHEMA: Final = "mirror.demo/D02SourceRepeatDeterminismCertification/v1"
RESULT_CERTIFICATE_SCHEMA: Final = "mirror.demo/D02ResultRepeatDeterminismCertification/v1"
RESULT_M3_RECORD_ID_SCHEMA: Final = "mirror.demo/D02ResultM3RecordId/v1"
RESULT_M3_REPEAT_RECORD_SCHEMA: Final = "mirror.demo/D02ResultM3RepeatRecord/v2"
CONFIDENCE_KIND: Final = "DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE"
RELIABILITY_KIND: Final = "EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY"
MEASUREMENT_CONFIG_DIGEST: Final = (
    "ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3"
)
IMPORT_CONFIG_DIGEST: Final = "3cb5043028bec1c25e95822432db69a84b1eae9af3788201fafffe53f40acec2"
QUALITY_CONFIG_DIGEST: Final = "ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47"
QUALITY_MANIFEST_DIGEST: Final = "ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74"
RUNTIME_MANIFEST_DIGEST: Final = "6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed"
VISION_MODEL_MANIFEST_DIGEST: Final = (
    "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
)
TOPOLOGY_DIGEST: Final = "85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63"

_DECIMAL_TOKEN = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")
_DIGEST = re.compile(r"[0-9a-f]{64}$")
_ID = re.compile(r"[0-9a-f]{32}$")
_FIXED18_QUANTUM: Final = Decimal("0.000000000000000001")
_SUPPORTED_FLOOR: Final = Decimal("0.000001000000000000")
_ZERO: Final = Decimal("0")
_ONE: Final = Decimal("1")
_DIMENSION_ORDER: Final = (
    "cheekbone_width",
    "chin_height",
    "eye_spacing",
    "jaw_width",
    "mouth_width",
    "nose_width",
)
_DIMENSION_ANCHORS: Final[dict[str, tuple[tuple[int, int], tuple[int, ...]]]] = {
    "cheekbone_width": ((123, 352), (10, 123, 152, 352)),
    "chin_height": ((17, 152), (10, 17, 152)),
    "eye_spacing": ((133, 362), (10, 133, 152, 362)),
    "jaw_width": ((234, 454), (10, 152, 234, 454)),
    "mouth_width": ((61, 291), (10, 61, 152, 291)),
    "nose_width": ((98, 327), (10, 98, 152, 327)),
}
_MEASUREMENT_CONFIG_KEYS: Final = {
    "schema_version",
    "measurement_algorithm_version",
    "decimal_serialization_version",
    "measurement_projection_version",
    "measurement_quantization_version",
    "confidence_algorithm_version",
    "confidence_kind",
    "reliability_algorithm_version",
    "reliability_kind",
    "coordinate_system",
    "decimal_precision",
    "rounding",
    "repeat_count",
    "required_face_count",
    "required_landmark_count",
    "supported_raw_min_fixed18",
    "supported_ppm_min",
    "supported_ppm_max",
    "unsupported_reason_precedence",
    "unsupported_projection_policy_version",
    "source_repeat_failure_policy_version",
    "result_repeat_failure_policy_version",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
    "geometry_ontology_version_digest",
    "measurement_quality_config_digest",
    "d02_execution_runtime_set_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "measurement_observation_schema_version",
    "source_repeat_certification_schema_version",
    "result_repeat_certification_schema_version",
    "source_m3_repeat_record_schema_version",
    "result_m3_repeat_record_schema_version",
    "measurement_gate_record_schema_version",
}
_IMPORT_CONFIG_KEYS: Final = {
    "schema_version",
    "importer_version",
    "identity_schema_version",
    "source_fact_schema_version",
    "raw_measurement_authority_schema_version",
    "morphology_projection_schema_version",
    "measurement_observation_schema_version",
    "source_repeat_certification_schema_version",
    "measurement_config_digest",
    "measurement_quality_config_digest",
    "d02_execution_runtime_set_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
}


class MeasurementQualityError(ValueError):
    """A candidate-three authority precondition or exact-key contract failed."""


@dataclass(frozen=True)
class AuthorityBindings:
    runtime_manifest_digest: str
    vision_model_manifest_digest: str
    topology_digest: str
    measurement_config_digest: str = MEASUREMENT_CONFIG_DIGEST
    measurement_quality_config_digest: str = QUALITY_CONFIG_DIGEST
    measurement_quality_manifest_content_digest: str = QUALITY_MANIFEST_DIGEST


def default_authority_bindings() -> AuthorityBindings:
    return AuthorityBindings(
        runtime_manifest_digest=RUNTIME_MANIFEST_DIGEST,
        vision_model_manifest_digest=VISION_MODEL_MANIFEST_DIGEST,
        topology_digest=TOPOLOGY_DIGEST,
    )


def parse_raw_decimal_token(token: object) -> Decimal:
    """Parse one original JSON numeric token without admitting binary floats."""

    if not isinstance(token, str) or _DECIMAL_TOKEN.fullmatch(token) is None:
        raise MeasurementQualityError("raw coordinate must be a JSON decimal token string")
    try:
        value = Decimal(token)
    except InvalidOperation as error:  # Defensive: the lexical rule already excludes this.
        raise MeasurementQualityError("raw coordinate token is invalid") from error
    if not value.is_finite():
        raise MeasurementQualityError("raw coordinate token must be finite")
    return value


def fixed18(value: Decimal) -> str:
    """Return the sole canonical fixed18 string, normalizing negative zero."""

    if not isinstance(value, Decimal) or not value.is_finite():
        raise MeasurementQualityError("fixed18 input must be a finite Decimal")
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        rounded = value.quantize(_FIXED18_QUANTUM)
    if rounded == _ZERO:
        rounded = _ZERO
    return format(rounded, ".18f")


def ppm_from_fixed18(value: str) -> int:
    decimal_value = _parse_fixed18(value)
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        ppm = int((decimal_value * Decimal(1_000_000)).to_integral_value())
    return max(0, min(1_000_000, ppm))


def mirror_demo_digest(schema_version: str, payload: Mapping[str, JsonValue]) -> str:
    """Return the Candidate 3 schema-domain digest over canonical JSON bytes."""

    if not isinstance(schema_version, str) or not schema_version:
        raise MeasurementQualityError("schema version must be a non-empty string")
    canonical = canonical_json_bytes(payload)
    return hashlib.sha256(schema_version.encode("utf-8") + b"\n" + canonical).hexdigest()


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """Implement the frozen demo-canonical-json-v1 without application imports."""

    try:
        normalized = _json_object(value)
        return json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:  # Defensive around stdlib serialization.
        raise MeasurementQualityError("payload is not canonical JSON") from error


def replay_measurement_config_digest(envelope: Mapping[str, object]) -> str:
    """Replay the frozen v1 measurement config digest from its exact envelope."""

    return _replay_config_digest(
        envelope,
        schema_version="mirror.demo/D02MeasurementExecutionConfig/v1",
        expected_keys=_MEASUREMENT_CONFIG_KEYS,
    )


def replay_import_config_digest(envelope: Mapping[str, object]) -> str:
    """Replay the frozen v3 identity-import config digest from its exact envelope."""

    return _replay_config_digest(
        envelope,
        schema_version="mirror.demo/D02IdentityImportConfiguration/v3",
        expected_keys=_IMPORT_CONFIG_KEYS,
    )


def require_replayed_measurement_config_digest(
    envelope: Mapping[str, object], claimed_digest: object
) -> None:
    _require_digest(claimed_digest, "claimed measurement config digest")
    if replay_measurement_config_digest(envelope) != claimed_digest:
        raise MeasurementQualityError("measurement config digest replay does not match claim")


def require_replayed_import_config_digest(
    envelope: Mapping[str, object], claimed_digest: object
) -> None:
    _require_digest(claimed_digest, "claimed import config digest")
    if replay_import_config_digest(envelope) != claimed_digest:
        raise MeasurementQualityError("import config digest replay does not match claim")


def build_measurement_observation(
    *,
    observation_role: ObservationRole,
    subject: Mapping[str, object],
    canonical_output_digest: str,
    landmark_digest: str,
    bindings: AuthorityBindings,
    measurement_landmarks: Mapping[int, Mapping[str, object]],
    ordered_observability_repeats: Sequence[Mapping[int, Mapping[str, object]]],
    runtime_unsupported_dimensions: Sequence[str] = (),
) -> dict[str, JsonValue]:
    """Build one six-dimensional observation using its repeat-group observability.

    ``measurement_landmarks`` supplies this observation's XY tokens.  The three
    ordered repeat maps only establish the group-level observability proxy.
    """

    _validate_role_and_subject(observation_role, subject)
    _require_digest(canonical_output_digest, "canonical output digest")
    _require_digest(landmark_digest, "landmark digest")
    _validate_bindings(bindings)
    if len(ordered_observability_repeats) != 3:
        raise MeasurementQualityError("exactly three ordered observability repeats are required")
    unsupported_runtime = set(runtime_unsupported_dimensions)
    if any(key not in _DIMENSION_ORDER for key in unsupported_runtime):
        raise MeasurementQualityError("runtime dimension key is not allowlisted")
    entries: list[JsonValue] = [
        _observation_entry(
            dimension_key=dimension_key,
            measurement_landmarks=measurement_landmarks,
            observability_repeats=ordered_observability_repeats,
            runtime_unsupported=dimension_key in unsupported_runtime,
        )
        for dimension_key in _DIMENSION_ORDER
    ]
    preimage: dict[str, JsonValue] = {
        "observation_role": observation_role,
        "subject": _json_object(subject),
        "canonical_output_digest": canonical_output_digest,
        "landmark_digest": landmark_digest,
        "runtime_manifest_digest": bindings.runtime_manifest_digest,
        "vision_model_manifest_digest": bindings.vision_model_manifest_digest,
        "topology_digest": bindings.topology_digest,
        "measurement_config_digest": bindings.measurement_config_digest,
        "measurement_quality_config_digest": bindings.measurement_quality_config_digest,
        "measurement_quality_manifest_content_digest": (
            bindings.measurement_quality_manifest_content_digest
        ),
        "confidence_kind": CONFIDENCE_KIND,
        "ordered_measurements": entries,
    }
    digest = mirror_demo_digest(MEASUREMENT_OBSERVATION_SCHEMA, preimage)
    return {
        "schema_version": MEASUREMENT_OBSERVATION_SCHEMA,
        **preimage,
        "measurement_observation_digest": digest,
    }


def build_source_repeat_certification(
    *,
    subject: Mapping[str, object],
    bindings: AuthorityBindings,
    ordered_repeat_bindings: Sequence[Mapping[str, object]],
) -> dict[str, JsonValue]:
    _validate_subject("SOURCE", subject)
    normalized = _validate_repeat_bindings("SOURCE", ordered_repeat_bindings)
    return _build_repeat_certification(
        schema_version=SOURCE_CERTIFICATE_SCHEMA,
        digest_key="source_repeat_certification_digest",
        subject=subject,
        bindings=bindings,
        ordered_bindings=normalized,
    )


def build_result_repeat_certification(
    *,
    subject: Mapping[str, object],
    bindings: AuthorityBindings,
    result_m3_records: Sequence[Mapping[str, object]],
) -> dict[str, JsonValue]:
    """Certify only three complete, existing ResultM3 v2 record authorities."""

    _validate_subject("RESULT", subject)
    normalized = _result_record_bindings(subject, bindings, result_m3_records)
    return _build_repeat_certification(
        schema_version=RESULT_CERTIFICATE_SCHEMA,
        digest_key="result_repeat_certification_digest",
        subject=subject,
        bindings=bindings,
        ordered_bindings=normalized,
    )


def derive_result_m3_record_id(
    *,
    case_id: object,
    case_specification_digest: object,
    result_output_id: object,
    result_sha256: object,
    repeat_index: object,
    bindings: AuthorityBindings,
) -> str:
    """Derive the frozen acyclic ResultM3 record identifier."""

    _require_id(case_id, "case id")
    _require_digest(case_specification_digest, "case specification digest")
    _require_id(result_output_id, "result output id")
    _require_digest(result_sha256, "result SHA-256")
    if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
        raise MeasurementQualityError("ResultM3 repeat index must be 1, 2, or 3")
    _validate_bindings(bindings)
    preimage: dict[str, object] = {
        "case_id": case_id,
        "case_specification_digest": case_specification_digest,
        "result_output_id": result_output_id,
        "result_sha256": result_sha256,
        "repeat_index": repeat_index,
        "vision_model_manifest_digest": bindings.vision_model_manifest_digest,
        "runtime_manifest_digest": bindings.runtime_manifest_digest,
        "topology_digest": bindings.topology_digest,
    }
    return mirror_demo_digest(RESULT_M3_RECORD_ID_SCHEMA, _json_object(preimage))[:32]


def _observation_entry(
    *,
    dimension_key: str,
    measurement_landmarks: Mapping[int, Mapping[str, object]],
    observability_repeats: Sequence[Mapping[int, Mapping[str, object]]],
    runtime_unsupported: bool,
) -> dict[str, JsonValue]:
    if runtime_unsupported:
        return _not_computable_entry(dimension_key, "RUNTIME_UNSUPPORTED")
    pair, required = _DIMENSION_ANCHORS[dimension_key]
    parsed_measurement, measurement_failure = _parse_required_landmarks(
        measurement_landmarks, required
    )
    parsed_repeats: list[dict[int, tuple[Decimal, Decimal]]] = []
    failures: list[str] = []
    if measurement_failure is not None:
        failures.append(measurement_failure)
    for repeat in observability_repeats:
        parsed, failure = _parse_required_landmarks(repeat, required)
        parsed_repeats.append(parsed)
        if failure is not None:
            failures.append(failure)
    if failures:
        return _not_computable_entry(dimension_key, _highest_unsupported_reason(failures))
    assert parsed_measurement is not None
    assert all(parsed is not None for parsed in parsed_repeats)
    normalizer = _distance(parsed_measurement[10], parsed_measurement[152])
    if normalizer <= _ZERO:
        return _not_computable_entry(dimension_key, "OUT_OF_BOUNDS")
    raw_value = _distance(parsed_measurement[pair[0]], parsed_measurement[pair[1]]) / normalizer
    if raw_value < _SUPPORTED_FLOOR or raw_value > _ONE:
        return _not_computable_entry(dimension_key, "OUT_OF_BOUNDS")
    observability = min(_repeat_observability(parsed, required) for parsed in parsed_repeats)
    canonical_observability = fixed18(observability)
    if observability < _SUPPORTED_FLOOR or ppm_from_fixed18(canonical_observability) < 1:
        return {
            "schema_version": OBSERVATION_ENTRY_SCHEMA,
            "dimension_key": dimension_key,
            "support_state": "UNSUPPORTED",
            "raw_value_fixed18": None,
            "observability_state": "COMPUTED",
            "raw_observability_fixed18": canonical_observability,
            "unsupported_reason": "LOW_CONFIDENCE",
        }
    return {
        "schema_version": OBSERVATION_ENTRY_SCHEMA,
        "dimension_key": dimension_key,
        "support_state": "SUPPORTED",
        "raw_value_fixed18": fixed18(raw_value),
        "observability_state": "COMPUTED",
        "raw_observability_fixed18": canonical_observability,
        "unsupported_reason": None,
    }


def _parse_required_landmarks(
    landmarks: Mapping[int, Mapping[str, object]], required: tuple[int, ...]
) -> tuple[dict[int, tuple[Decimal, Decimal]], str | None]:
    parsed: dict[int, tuple[Decimal, Decimal]] = {}
    failures: list[str] = []
    for index in required:
        value = landmarks.get(index)
        if not isinstance(value, Mapping) or set(value) != {"x", "y"}:
            failures.append("MISSING_MEASUREMENT")
            continue
        x_raw = value["x"]
        y_raw = value["y"]
        try:
            x = parse_raw_decimal_token(x_raw)
            y = parse_raw_decimal_token(y_raw)
        except MeasurementQualityError:
            failures.append("OUT_OF_BOUNDS")
            continue
        if x < _ZERO or x > _ONE or y < _ZERO or y > _ONE:
            failures.append("OUT_OF_BOUNDS")
            continue
        parsed[index] = (x, y)
    return parsed, _highest_unsupported_reason(failures) if failures else None


def _repeat_observability(
    landmarks: Mapping[int, tuple[Decimal, Decimal]], required: tuple[int, ...]
) -> Decimal:
    margins = [min(x, _ONE - x, y, _ONE - y) for x, y in (landmarks[index] for index in required)]
    return max(_ZERO, min(_ONE, Decimal(2) * min(margins)))


def _distance(left: tuple[Decimal, Decimal], right: tuple[Decimal, Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        return ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2).sqrt()


def _not_computable_entry(dimension_key: str, reason: str) -> dict[str, JsonValue]:
    return {
        "schema_version": OBSERVATION_ENTRY_SCHEMA,
        "dimension_key": dimension_key,
        "support_state": "UNSUPPORTED",
        "raw_value_fixed18": None,
        "observability_state": "NOT_COMPUTABLE",
        "raw_observability_fixed18": None,
        "unsupported_reason": reason,
    }


def _build_repeat_certification(
    *,
    schema_version: str,
    digest_key: str,
    subject: Mapping[str, object],
    bindings: AuthorityBindings,
    ordered_bindings: list[dict[str, JsonValue]],
) -> dict[str, JsonValue]:
    _validate_bindings(bindings)
    preimage: dict[str, JsonValue] = {
        "subject": _json_object(subject),
        "runtime_manifest_digest": bindings.runtime_manifest_digest,
        "vision_model_manifest_digest": bindings.vision_model_manifest_digest,
        "topology_digest": bindings.topology_digest,
        "measurement_config_digest": bindings.measurement_config_digest,
        "measurement_quality_config_digest": bindings.measurement_quality_config_digest,
        "measurement_quality_manifest_content_digest": (
            bindings.measurement_quality_manifest_content_digest
        ),
        "reliability_kind": RELIABILITY_KIND,
        "repeat_count": 3,
        "ordered_repeat_bindings": list(ordered_bindings),
        "certification_state": "CERTIFIED_EXACT_REPEAT",
        "certified_raw_reliability_fixed18": "1.000000000000000000",
        "certified_reliability_ppm": 1_000_000,
    }
    return {
        "schema_version": schema_version,
        **preimage,
        digest_key: mirror_demo_digest(schema_version, preimage),
    }


def _validate_repeat_bindings(
    role: ObservationRole, bindings: Sequence[Mapping[str, object]]
) -> list[dict[str, JsonValue]]:
    if len(bindings) != 3:
        raise MeasurementQualityError("repeat certification requires exactly three bindings")
    expected = _source_binding_keys() if role == "SOURCE" else _result_binding_keys()
    normalized: list[dict[str, JsonValue]] = []
    for expected_index, binding in enumerate(bindings, start=1):
        _require_exact_keys(binding, expected, "repeat binding")
        if binding["repeat_index"] != expected_index:
            raise MeasurementQualityError("repeat bindings must be ordered indexes 1, 2, 3")
        _require_digest(binding["execution_receipt_digest"], "execution receipt digest")
        for key in ("canonical_output_digest", "landmark_digest", "measurement_observation_digest"):
            _require_digest(binding[key], key)
        if role == "RESULT":
            _require_id(binding["result_m3_record_id"], "result M3 record id")
            if binding["observation_state"] not in {"SUPPORTED", "UNSUPPORTED_EXPLICIT"}:
                raise MeasurementQualityError("result observation state is invalid")
        if (
            binding["face_count"] != 1
            or binding["landmark_count"] != 478
            or binding["coordinates_finite"] is not True
            or binding["coordinates_in_bounds"] is not True
            or binding["repeat_gate_passed"] is not True
        ):
            raise MeasurementQualityError("repeat structural precondition failed")
        normalized.append(_json_object(binding))
    for key in ("canonical_output_digest", "landmark_digest", "measurement_observation_digest"):
        if len({str(binding[key]) for binding in normalized}) != 1:
            raise MeasurementQualityError("repeat digest disagreement prevents certification")
    if role == "RESULT" and len({str(binding["observation_state"]) for binding in normalized}) != 1:
        raise MeasurementQualityError("result repeat observation states must be semantically equal")
    if (
        role == "RESULT"
        and len({str(binding["result_m3_record_id"]) for binding in normalized}) != 3
    ):
        raise MeasurementQualityError(
            "result repeat bindings must reference three distinct records"
        )
    return normalized


def _result_record_bindings(
    subject: Mapping[str, object],
    bindings: AuthorityBindings,
    records: Sequence[Mapping[str, object]],
) -> list[dict[str, JsonValue]]:
    if len(records) != 3:
        raise MeasurementQualityError(
            "result certification requires exactly three ResultM3 v2 records"
        )
    expected = _result_record_keys()
    derived: list[dict[str, object]] = []
    for expected_index, record in enumerate(records, start=1):
        _require_exact_keys(record, expected, "ResultM3 v2 record")
        if record["schema_version"] != RESULT_M3_REPEAT_RECORD_SCHEMA:
            raise MeasurementQualityError("ResultM3 record schema is invalid")
        record_payload = {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "record_digest"}
        }
        _require_digest(record["record_digest"], "ResultM3 record digest")
        if (
            mirror_demo_digest(RESULT_M3_REPEAT_RECORD_SCHEMA, _json_object(record_payload))
            != record["record_digest"]
        ):
            raise MeasurementQualityError("ResultM3 record digest does not match")
        _validate_result_record_subject(record, subject)
        _validate_result_record_authority(record, bindings)
        _validate_embedded_result_observation(record, subject, bindings)
        if record["repeat_index"] != expected_index:
            raise MeasurementQualityError("ResultM3 records must be ordered indexes 1, 2, 3")
        derived.append(
            {
                "repeat_index": record["repeat_index"],
                "result_m3_record_id": record["result_m3_record_id"],
                "execution_receipt_digest": record["execution_receipt_digest"],
                "canonical_output_digest": record["canonical_output_digest"],
                "landmark_digest": record["landmark_digest"],
                "measurement_observation_digest": record["measurement_observation_digest"],
                "face_count": record["face_count"],
                "landmark_count": record["landmark_count"],
                "coordinates_finite": record["coordinates_finite"],
                "coordinates_in_bounds": record["coordinates_in_bounds"],
                "observation_state": record["observation_state"],
                "repeat_gate_passed": record["repeat_gate_passed"],
            }
        )
    return _validate_repeat_bindings("RESULT", derived)


def _validate_result_record_subject(
    record: Mapping[str, object], subject: Mapping[str, object]
) -> None:
    for key in ("case_id", "case_specification_digest", "result_output_id", "result_sha256"):
        if record[key] != subject[key]:
            raise MeasurementQualityError(
                "ResultM3 record subject does not match certificate subject"
            )


def _validate_result_record_authority(
    record: Mapping[str, object], bindings: AuthorityBindings
) -> None:
    _require_id(record["result_m3_record_id"], "result M3 record id")
    for key in (
        "case_specification_digest",
        "result_sha256",
        "execution_receipt_digest",
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation_digest",
    ):
        _require_digest(record[key], key)
    expected = {
        "runtime_manifest_digest": bindings.runtime_manifest_digest,
        "vision_model_manifest_digest": bindings.vision_model_manifest_digest,
        "topology_digest": bindings.topology_digest,
    }
    if any(record[key] != value for key, value in expected.items()):
        raise MeasurementQualityError("ResultM3 record runtime authority does not match")
    expected_record_id = derive_result_m3_record_id(
        case_id=record["case_id"],
        case_specification_digest=record["case_specification_digest"],
        result_output_id=record["result_output_id"],
        result_sha256=record["result_sha256"],
        repeat_index=record["repeat_index"],
        bindings=bindings,
    )
    if record["result_m3_record_id"] != expected_record_id:
        raise MeasurementQualityError("ResultM3 record id preimage does not match")


def _validate_embedded_result_observation(
    record: Mapping[str, object], subject: Mapping[str, object], bindings: AuthorityBindings
) -> None:
    observation = record["measurement_observation"]
    if not isinstance(observation, Mapping):
        raise MeasurementQualityError("ResultM3 embedded observation is invalid")
    _require_exact_keys(observation, _observation_keys(), "embedded observation")
    if (
        observation["schema_version"] != MEASUREMENT_OBSERVATION_SCHEMA
        or observation["observation_role"] != "RESULT"
    ):
        raise MeasurementQualityError("embedded observation schema or role is invalid")
    observation_payload = {
        key: value
        for key, value in observation.items()
        if key not in {"schema_version", "measurement_observation_digest"}
    }
    if (
        mirror_demo_digest(MEASUREMENT_OBSERVATION_SCHEMA, _json_object(observation_payload))
        != observation["measurement_observation_digest"]
    ):
        raise MeasurementQualityError("embedded observation digest does not match")
    if observation["measurement_observation_digest"] != record["measurement_observation_digest"]:
        raise MeasurementQualityError("embedded observation digest does not match ResultM3 record")
    if observation["subject"] != _json_object(subject):
        raise MeasurementQualityError("embedded observation subject does not match ResultM3 record")
    expected = {
        "canonical_output_digest": record["canonical_output_digest"],
        "landmark_digest": record["landmark_digest"],
        "runtime_manifest_digest": bindings.runtime_manifest_digest,
        "vision_model_manifest_digest": bindings.vision_model_manifest_digest,
        "topology_digest": bindings.topology_digest,
        "measurement_config_digest": bindings.measurement_config_digest,
        "measurement_quality_config_digest": bindings.measurement_quality_config_digest,
        "measurement_quality_manifest_content_digest": (
            bindings.measurement_quality_manifest_content_digest
        ),
        "confidence_kind": CONFIDENCE_KIND,
    }
    if any(observation[key] != value for key, value in expected.items()):
        raise MeasurementQualityError(
            "embedded observation authority does not match ResultM3 record"
        )
    expected_state = _validate_result_observation_entries(observation["ordered_measurements"])
    if record["observation_state"] != expected_state:
        raise MeasurementQualityError(
            "ResultM3 observation state does not match embedded observation"
        )


def _validate_result_observation_entries(value: object) -> str:
    if not isinstance(value, list) or len(value) != len(_DIMENSION_ORDER):
        raise MeasurementQualityError("embedded observation entries are invalid")
    unsupported = False
    for dimension_key, entry in zip(_DIMENSION_ORDER, value, strict=True):
        if not isinstance(entry, Mapping):
            raise MeasurementQualityError("embedded observation entry is invalid")
        _require_exact_keys(entry, _observation_entry_keys(), "embedded observation entry")
        if (
            entry["schema_version"] != OBSERVATION_ENTRY_SCHEMA
            or entry["dimension_key"] != dimension_key
        ):
            raise MeasurementQualityError(
                "embedded observation entry schema or dimension is invalid"
            )
        if entry["support_state"] == "SUPPORTED":
            if (
                not isinstance(entry["raw_value_fixed18"], str)
                or entry["observability_state"] != "COMPUTED"
                or not isinstance(entry["raw_observability_fixed18"], str)
                or entry["unsupported_reason"] is not None
            ):
                raise MeasurementQualityError("supported embedded observation union is invalid")
            raw_value = _parse_fixed18(entry["raw_value_fixed18"])
            raw_observability = _parse_fixed18(entry["raw_observability_fixed18"])
            if (
                raw_value < _SUPPORTED_FLOOR
                or raw_value > _ONE
                or raw_observability < _SUPPORTED_FLOOR
                or raw_observability > _ONE
                or ppm_from_fixed18(entry["raw_observability_fixed18"]) < 1
            ):
                raise MeasurementQualityError("supported embedded observation value is invalid")
        elif entry["support_state"] == "UNSUPPORTED":
            unsupported = True
            reason = entry["unsupported_reason"]
            if (
                reason
                not in {
                    "RUNTIME_UNSUPPORTED",
                    "MISSING_MEASUREMENT",
                    "OUT_OF_BOUNDS",
                    "LOW_CONFIDENCE",
                }
                or entry["raw_value_fixed18"] is not None
            ):
                raise MeasurementQualityError("unsupported embedded observation union is invalid")
            if reason == "LOW_CONFIDENCE":
                raw_observability_value = entry["raw_observability_fixed18"]
                if (
                    entry["observability_state"] != "COMPUTED"
                    or not isinstance(raw_observability_value, str)
                    or (
                        _parse_fixed18(raw_observability_value) >= _SUPPORTED_FLOOR
                        and ppm_from_fixed18(raw_observability_value) >= 1
                    )
                ):
                    raise MeasurementQualityError(
                        "low-confidence embedded observation union is invalid"
                    )
            elif (
                entry["observability_state"] != "NOT_COMPUTABLE"
                or entry["raw_observability_fixed18"] is not None
            ):
                raise MeasurementQualityError(
                    "not-computable embedded observation union is invalid"
                )
        else:
            raise MeasurementQualityError("embedded observation support state is invalid")
    return "UNSUPPORTED_EXPLICIT" if unsupported else "SUPPORTED"


def _highest_unsupported_reason(reasons: Sequence[str]) -> str:
    precedence = ("RUNTIME_UNSUPPORTED", "MISSING_MEASUREMENT", "OUT_OF_BOUNDS", "LOW_CONFIDENCE")
    for reason in precedence:
        if reason in reasons:
            return reason
    raise MeasurementQualityError("unsupported reason is not allowlisted")


def _validate_role_and_subject(role: ObservationRole, subject: Mapping[str, object]) -> None:
    if role not in {"SOURCE", "RESULT"}:
        raise MeasurementQualityError("observation role is invalid")
    _validate_subject(role, subject)


def _validate_subject(role: ObservationRole, subject: Mapping[str, object]) -> None:
    if role == "SOURCE":
        _require_exact_keys(
            subject,
            {"schema_version", "source_output_id", "source_asset_id", "source_asset_sha256"},
            "source subject",
        )
        if subject["schema_version"] != SOURCE_SUBJECT_SCHEMA:
            raise MeasurementQualityError("source subject schema is invalid")
        _require_id(subject["source_output_id"], "source output id")
        _require_id(subject["source_asset_id"], "source asset id")
        _require_digest(subject["source_asset_sha256"], "source asset SHA-256")
        return
    _require_exact_keys(
        subject,
        {
            "schema_version",
            "case_id",
            "case_specification_digest",
            "result_output_id",
            "result_sha256",
        },
        "result subject",
    )
    if subject["schema_version"] != RESULT_SUBJECT_SCHEMA:
        raise MeasurementQualityError("result subject schema is invalid")
    _require_id(subject["case_id"], "case id")
    _require_digest(subject["case_specification_digest"], "case specification digest")
    _require_id(subject["result_output_id"], "result output id")
    _require_digest(subject["result_sha256"], "result SHA-256")


def _validate_bindings(bindings: AuthorityBindings) -> None:
    expected = default_authority_bindings()
    if bindings != expected:
        raise MeasurementQualityError(
            "runtime/model/topology/config authority bindings do not match"
        )


def _replay_config_digest(
    envelope: Mapping[str, object], *, schema_version: str, expected_keys: set[str]
) -> str:
    _require_exact_keys(envelope, expected_keys, "config envelope")
    if envelope["schema_version"] != schema_version:
        raise MeasurementQualityError("config envelope schema is invalid")
    payload = _json_object(
        {key: value for key, value in envelope.items() if key != "schema_version"}
    )
    return mirror_demo_digest(schema_version, payload)


def _parse_fixed18(value: str) -> Decimal:
    if not isinstance(value, str) or re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{18}", value) is None:
        raise MeasurementQualityError("fixed18 value is not canonical")
    return Decimal(value)


def _require_digest(value: object, description: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise MeasurementQualityError(f"{description} must be a lowercase SHA-256 digest")


def _require_id(value: object, description: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise MeasurementQualityError(f"{description} must be a lowercase hexadecimal ID")


def _require_exact_keys(value: Mapping[str, object], expected: set[str], description: str) -> None:
    if set(value) != expected:
        raise MeasurementQualityError(f"{description} exact keys do not match")


def _json_object(value: Mapping[str, object]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise MeasurementQualityError("canonical object key must be a string")
        result[key] = _json_value(item)
    return result


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, (float, Decimal, bytes, bytearray)):
        raise MeasurementQualityError(
            "canonical authority forbids float, Decimal, and bytes leaves"
        )
    if isinstance(value, Mapping):
        return _json_object(value)
    if isinstance(value, Sequence):
        return [_json_value(item) for item in value]
    raise MeasurementQualityError("canonical authority contains a non-JSON value")


def _source_binding_keys() -> set[str]:
    return {
        "repeat_index",
        "execution_receipt_digest",
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation_digest",
        "face_count",
        "landmark_count",
        "coordinates_finite",
        "coordinates_in_bounds",
        "repeat_gate_passed",
    }


def _result_binding_keys() -> set[str]:
    return _source_binding_keys() | {"result_m3_record_id", "observation_state"}


def _observation_keys() -> set[str]:
    return {
        "schema_version",
        "observation_role",
        "subject",
        "canonical_output_digest",
        "landmark_digest",
        "runtime_manifest_digest",
        "vision_model_manifest_digest",
        "topology_digest",
        "measurement_config_digest",
        "measurement_quality_config_digest",
        "measurement_quality_manifest_content_digest",
        "confidence_kind",
        "ordered_measurements",
        "measurement_observation_digest",
    }


def _observation_entry_keys() -> set[str]:
    return {
        "schema_version",
        "dimension_key",
        "support_state",
        "raw_value_fixed18",
        "observability_state",
        "raw_observability_fixed18",
        "unsupported_reason",
    }


def _result_record_keys() -> set[str]:
    return {
        "schema_version",
        "result_m3_record_id",
        "case_id",
        "case_specification_digest",
        "result_output_id",
        "result_sha256",
        "repeat_index",
        "execution_receipt_digest",
        "vision_model_manifest_digest",
        "runtime_manifest_digest",
        "topology_digest",
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation",
        "measurement_observation_digest",
        "face_count",
        "landmark_count",
        "coordinates_finite",
        "coordinates_in_bounds",
        "observation_state",
        "repeat_gate_passed",
        "record_digest",
    }
