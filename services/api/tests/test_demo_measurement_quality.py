from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest

from mirror_api.demo_idempotency import canonical_json_bytes as accepted_canonical_json_bytes
from mirror_api.demo_measurement_quality import (
    IMPORT_CONFIG_DIGEST,
    MEASUREMENT_CONFIG_DIGEST,
    MEASUREMENT_OBSERVATION_SCHEMA,
    RESULT_M3_RECORD_ID_SCHEMA,
    RESULT_M3_REPEAT_RECORD_SCHEMA,
    RESULT_SUBJECT_SCHEMA,
    SOURCE_CERTIFICATE_SCHEMA,
    SOURCE_SUBJECT_SCHEMA,
    AuthorityBindings,
    JsonValue,
    MeasurementQualityError,
    build_measurement_observation,
    build_result_repeat_certification,
    build_source_repeat_certification,
    canonical_json_bytes,
    default_authority_bindings,
    derive_result_m3_record_id,
    fixed18,
    mirror_demo_digest,
    parse_raw_decimal_token,
    ppm_from_fixed18,
    replay_import_config_digest,
    replay_measurement_config_digest,
    require_replayed_import_config_digest,
    require_replayed_measurement_config_digest,
)

_ID = "a" * 32
_OTHER_ID = "b" * 32
_DIGEST = "c" * 64
_OTHER_DIGEST = "d" * 64
_MANDATORY_GATES = {
    "GEOMETRIC_OBSERVABILITY_CENTER_REFERENCE": "test_geometric_observability_center_reference",
    "GEOMETRIC_OBSERVABILITY_BOUNDARY_MONOTONICITY": "test_geometric_observability_boundary_monotonicity",  # noqa: E501
    "GEOMETRIC_OBSERVABILITY_REQUIRED_ANCHOR_SET": "test_geometric_observability_required_anchor_set",  # noqa: E501
    "MISSING_NONFINITE_OUT_OF_RANGE_FAILS_CLOSED": "test_missing_nonfinite_out_of_range_fails_closed",  # noqa: E501
    "FIXED18_HALF_EVEN_REFERENCE": "test_fixed18_half_even_reference",
    "PPM_HALF_EVEN_REFERENCE": "test_ppm_half_even_reference",
    "NEGATIVE_ZERO_NORMALIZED": "test_negative_zero_normalized",
    "NO_BINARY_FLOAT_CANONICAL_AUTHORITY": "test_no_binary_float_canonical_authority",
    "DIFFERENT_GEOMETRY_CHANGES_CONFIDENCE": "test_different_geometry_changes_confidence",
    "NO_MODEL_CONFIDENCE_CLAIM": "test_no_model_confidence_claim",
    "NO_SENSITIVE_INPUT_FIELD": "test_no_sensitive_input_field",
    "MEASUREMENT_OBSERVATION_EXACT_KEYS_AND_DIGEST": "test_measurement_observation_exact_keys_and_digest",  # noqa: E501
    "OBSERVATION_DIGEST_EXCLUDES_REPEAT_LOCAL_FIELDS": "test_observation_digest_excludes_repeat_local_fields",  # noqa: E501
    "SUPPORTED_AND_UNSUPPORTED_OBSERVATION_UNIONS": "test_supported_and_unsupported_observation_unions",  # noqa: E501
    "MEASUREMENT_CONFIG_DIGEST_REPLAY": "test_measurement_config_digest_replay",
    "IMPORT_CONFIG_DIGEST_REPLAY": "test_import_config_digest_replay",
    "THREE_REPEAT_EXACT_DIGEST_CERTIFICATION": "test_three_repeat_exact_digest_certification",
    "SOURCE_AND_RESULT_CERTIFICATE_PREIMAGE": "test_source_and_result_certificate_preimage",
    "RESULT_M3_ID_PREIMAGE_ACYCLIC": "test_result_m3_record_id_preimage_is_acyclic_and_enforced",
    "GROUP_CERTIFICATE_VS_DIMENSION_UNSUPPORTED_SEMANTICS": "test_group_certificate_vs_dimension_unsupported_semantics",  # noqa: E501
    "ANY_SOURCE_REPEAT_DIGEST_MISMATCH_STOPS_BEFORE_M4": "test_any_source_repeat_digest_mismatch_stops_before_m4",  # noqa: E501
    "ANY_RESULT_REPEAT_DIGEST_MISMATCH_STOPS_REPORT": "test_any_result_repeat_digest_mismatch_stops_report",  # noqa: E501
    "STRUCTURAL_PRECONDITION_FAILURE_CREATES_NO_CERTIFICATE": "test_structural_precondition_failure_creates_no_certificate",  # noqa: E501
    "DETERMINISTIC_REPLAY_BYTE_IDENTICAL": "test_deterministic_replay_byte_identical",
}


def _source_subject() -> dict[str, str]:
    return {
        "schema_version": SOURCE_SUBJECT_SCHEMA,
        "source_output_id": _ID,
        "source_asset_id": _OTHER_ID,
        "source_asset_sha256": _DIGEST,
    }


def _result_subject() -> dict[str, str]:
    return {
        "schema_version": RESULT_SUBJECT_SCHEMA,
        "case_id": _ID,
        "case_specification_digest": _DIGEST,
        "result_output_id": _OTHER_ID,
        "result_sha256": _OTHER_DIGEST,
    }


def test_source_and_result_subjects_accept_opaque_registry_output_ids() -> None:
    landmarks = _landmarks()
    source = _source_subject()
    source["source_output_id"] = "D00-M3-ASSET-v01-category-a-02"
    source_observation = build_measurement_observation(
        observation_role="SOURCE",
        subject=source,
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[landmarks, landmarks, landmarks],
    )
    assert source_observation["subject"] == source

    result = _result_subject()
    result["result_output_id"] = "D02-M4-RESULT.case-001.replay-1"
    result_observation = build_measurement_observation(
        observation_role="RESULT",
        subject=result,
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[landmarks, landmarks, landmarks],
    )
    assert result_observation["subject"] == result
    assert derive_result_m3_record_id(
        case_id=result["case_id"],
        case_specification_digest=result["case_specification_digest"],
        result_output_id=result["result_output_id"],
        result_sha256=result["result_sha256"],
        repeat_index=1,
        bindings=default_authority_bindings(),
    )


@pytest.mark.parametrize(
    "invalid_output_id",
    ["../private", "D:/private", "file://private", "has space", "a" * 129],
)
def test_subjects_reject_non_opaque_output_ids(invalid_output_id: str) -> None:
    source = _source_subject()
    source["source_output_id"] = invalid_output_id
    with pytest.raises(MeasurementQualityError, match="opaque output ID"):
        build_source_repeat_certification(
            subject=source,
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=[_source_binding(index) for index in (1, 2, 3)],
        )


def _landmarks() -> dict[int, dict[str, str]]:
    coordinates = {
        10: ("0.500", "0.100"),
        152: ("0.500", "0.900"),
        17: ("0.500", "0.800"),
        123: ("0.250", "0.400"),
        352: ("0.750", "0.400"),
        133: ("0.400", "0.400"),
        362: ("0.600", "0.400"),
        234: ("0.200", "0.600"),
        454: ("0.800", "0.600"),
        61: ("0.400", "0.700"),
        291: ("0.600", "0.700"),
        98: ("0.450", "0.550"),
        327: ("0.550", "0.550"),
    }
    return {index: {"x": x, "y": y} for index, (x, y) in coordinates.items()}


def _observation(*, role: Literal["SOURCE", "RESULT"] = "SOURCE") -> dict[str, JsonValue]:
    subject = _source_subject() if role == "SOURCE" else _result_subject()
    landmarks = _landmarks()
    return build_measurement_observation(
        observation_role=role,
        subject=subject,
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )


def _source_binding(index: int, *, digest: str = _DIGEST) -> dict[str, object]:
    return {
        "repeat_index": index,
        "execution_receipt_digest": _OTHER_DIGEST,
        "canonical_output_digest": digest,
        "landmark_digest": _OTHER_DIGEST,
        "measurement_observation_digest": _DIGEST,
        "face_count": 1,
        "landmark_count": 478,
        "coordinates_finite": True,
        "coordinates_in_bounds": True,
        "repeat_gate_passed": True,
    }


def _result_binding(index: int) -> dict[str, JsonValue]:
    observation = _observation(role="RESULT")
    result_m3_record_id = derive_result_m3_record_id(
        case_id=_ID,
        case_specification_digest=_DIGEST,
        result_output_id=_OTHER_ID,
        result_sha256=_OTHER_DIGEST,
        repeat_index=index,
        bindings=default_authority_bindings(),
    )
    record: dict[str, JsonValue] = {
        "schema_version": RESULT_M3_REPEAT_RECORD_SCHEMA,
        "result_m3_record_id": result_m3_record_id,
        "case_id": _ID,
        "case_specification_digest": _DIGEST,
        "result_output_id": _OTHER_ID,
        "result_sha256": _OTHER_DIGEST,
        "repeat_index": index,
        "execution_receipt_digest": _OTHER_DIGEST,
        "vision_model_manifest_digest": default_authority_bindings().vision_model_manifest_digest,
        "runtime_manifest_digest": default_authority_bindings().runtime_manifest_digest,
        "topology_digest": default_authority_bindings().topology_digest,
        "canonical_output_digest": _DIGEST,
        "landmark_digest": _OTHER_DIGEST,
        "measurement_observation": observation,
        "measurement_observation_digest": observation["measurement_observation_digest"],
        "face_count": 1,
        "landmark_count": 478,
        "coordinates_finite": True,
        "coordinates_in_bounds": True,
        "observation_state": "SUPPORTED",
        "repeat_gate_passed": True,
    }
    _resign_result_record(record)
    return record


def _resign_result_record(record: dict[str, JsonValue]) -> None:
    record["record_digest"] = mirror_demo_digest(
        RESULT_M3_REPEAT_RECORD_SCHEMA,
        {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def _set_result_observation(
    record: dict[str, JsonValue], observation: dict[str, JsonValue]
) -> None:
    record["measurement_observation"] = observation
    record["measurement_observation_digest"] = observation["measurement_observation_digest"]
    entries = [_json_object(entry) for entry in _json_array(observation["ordered_measurements"])]
    record["observation_state"] = (
        "UNSUPPORTED_EXPLICIT"
        if any(entry["support_state"] == "UNSUPPORTED" for entry in entries)
        else "SUPPORTED"
    )
    _resign_result_record(record)


def _result_observation_with_runtime_unsupported() -> dict[str, JsonValue]:
    landmarks = _landmarks()
    return build_measurement_observation(
        observation_role="RESULT",
        subject=_result_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
        runtime_unsupported_dimensions=["jaw_width"],
    )


def _different_result_observation() -> dict[str, JsonValue]:
    landmarks = _landmarks()
    landmarks[123]["x"] = "0.251"
    return build_measurement_observation(
        observation_role="RESULT",
        subject=_result_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )


def _json_array(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


def _json_object(value: JsonValue) -> dict[str, JsonValue]:
    assert isinstance(value, dict)
    return value


def _entry(observation: dict[str, JsonValue], index: int) -> dict[str, JsonValue]:
    return _json_object(_json_array(observation["ordered_measurements"])[index])


def _fixed18_value(value: JsonValue) -> str:
    assert isinstance(value, str)
    return value


def _authority_manifest() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "research"
        / ("P3_P7_D02_MEASUREMENT_QUALITY_AUTHORITY_MANIFEST.json")
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_observation_is_six_dimension_canonical_and_digest_deterministic() -> None:
    first = _observation()
    second = _observation()

    assert first == second
    assert first["schema_version"] == MEASUREMENT_OBSERVATION_SCHEMA
    entries = [_json_object(entry) for entry in _json_array(first["ordered_measurements"])]
    assert [entry["dimension_key"] for entry in entries] == [
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    ]
    assert first["measurement_observation_digest"] == mirror_demo_digest(
        MEASUREMENT_OBSERVATION_SCHEMA,
        {
            key: value
            for key, value in first.items()
            if key not in {"schema_version", "measurement_observation_digest"}
        },
    )
    assert all(entry["support_state"] == "SUPPORTED" for entry in entries)


@pytest.mark.parametrize("token", [0.1, float("nan"), float("inf"), "NaN", "Infinity", " 0.1"])
def test_raw_float_and_nonfinite_tokens_fail_closed(token: object) -> None:
    with pytest.raises(MeasurementQualityError):
        parse_raw_decimal_token(token)


def test_fixed18_rounding_clamping_and_negative_zero() -> None:
    assert fixed18(Decimal("-0.0000000000000000004")) == "0.000000000000000000"
    assert fixed18(Decimal("0.0000000000000000005")) == "0.000000000000000000"
    assert fixed18(Decimal("0.0000000000000000015")) == "0.000000000000000002"
    assert ppm_from_fixed18("0.000000500000000000") == 0
    assert ppm_from_fixed18("1.100000000000000000") == 1_000_000


def test_observation_fails_closed_for_missing_anchor_invalid_runtime_and_low_confidence() -> None:
    landmarks = _landmarks()
    del landmarks[352]
    missing = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )
    missing_entries = [
        _json_object(entry) for entry in _json_array(missing["ordered_measurements"])
    ]
    assert missing_entries[0]["unsupported_reason"] == "MISSING_MEASUREMENT"
    low = _landmarks()
    low[10] = {"x": "0.0000004", "y": "0.100"}
    observation = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=low,
        ordered_observability_repeats=[deepcopy(low) for _ in range(3)],
        runtime_unsupported_dimensions=["jaw_width"],
    )
    observation_entries = [
        _json_object(entry) for entry in _json_array(observation["ordered_measurements"])
    ]
    assert observation_entries[0]["unsupported_reason"] == "LOW_CONFIDENCE"
    assert observation_entries[3]["unsupported_reason"] == "RUNTIME_UNSUPPORTED"
    bad = AuthorityBindings(
        runtime_manifest_digest="e" * 64,
        vision_model_manifest_digest="f" * 64,
        topology_digest="0" * 64,
    )
    with pytest.raises(MeasurementQualityError, match="authority bindings"):
        build_measurement_observation(
            observation_role="SOURCE",
            subject=_source_subject(),
            canonical_output_digest=_DIGEST,
            landmark_digest=_OTHER_DIGEST,
            bindings=bad,
            measurement_landmarks=_landmarks(),
            ordered_observability_repeats=[_landmarks() for _ in range(3)],
        )


def test_source_certificate_has_only_pre_admission_exact_keys_and_no_placeholder() -> None:
    certificate = build_source_repeat_certification(
        subject=_source_subject(),
        bindings=default_authority_bindings(),
        ordered_repeat_bindings=[_source_binding(index) for index in (1, 2, 3)],
    )
    assert certificate["schema_version"] == SOURCE_CERTIFICATE_SCHEMA
    assert set(certificate) == {
        "schema_version",
        "subject",
        "runtime_manifest_digest",
        "vision_model_manifest_digest",
        "topology_digest",
        "measurement_config_digest",
        "measurement_quality_config_digest",
        "measurement_quality_manifest_content_digest",
        "reliability_kind",
        "repeat_count",
        "ordered_repeat_bindings",
        "certification_state",
        "certified_raw_reliability_fixed18",
        "certified_reliability_ppm",
        "source_repeat_certification_digest",
    }
    assert "source_m3_record_id" not in certificate
    assert "source_manifest_digest" not in certificate
    assert "source_authority_key" not in certificate
    assert certificate["certification_state"] == "CERTIFIED_EXACT_REPEAT"
    assert certificate["certified_reliability_ppm"] == 1_000_000
    contaminated = _source_subject() | {"source_m3_record_id": _ID}
    with pytest.raises(MeasurementQualityError, match="exact keys"):
        build_source_repeat_certification(
            subject=contaminated,
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=[_source_binding(index) for index in (1, 2, 3)],
        )


def test_repeat_certification_rejects_mismatch_and_structural_failure() -> None:
    mismatched = [_source_binding(index) for index in (1, 2, 3)]
    mismatched[2]["canonical_output_digest"] = _OTHER_DIGEST
    with pytest.raises(MeasurementQualityError, match="disagreement"):
        build_source_repeat_certification(
            subject=_source_subject(),
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=mismatched,
        )
    invalid = [_result_binding(index) for index in (1, 2, 3)]
    invalid[0]["coordinates_in_bounds"] = False
    _resign_result_record(invalid[0])
    with pytest.raises(MeasurementQualityError, match="structural"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=invalid,
        )


def test_result_certificate_is_separate_and_requires_existing_result_record_id() -> None:
    bindings = [_result_binding(index) for index in (1, 2, 3)]
    assert len({str(binding["result_m3_record_id"]) for binding in bindings}) == 3
    certificate = build_result_repeat_certification(
        subject=_result_subject(),
        bindings=default_authority_bindings(),
        result_m3_records=bindings,
    )
    assert "result_repeat_certification_digest" in certificate
    invalid = [_result_binding(index) for index in (1, 2, 3)]
    invalid[0]["result_m3_record_id"] = "not-an-id"
    with pytest.raises(MeasurementQualityError):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=invalid,
        )
    duplicate = [_result_binding(index) for index in (1, 2, 3)]
    duplicate[2]["result_m3_record_id"] = duplicate[1]["result_m3_record_id"]
    _resign_result_record(duplicate[2])
    with pytest.raises(MeasurementQualityError, match="id preimage"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=duplicate,
        )


def test_result_certificate_rejects_id_only_or_missing_records() -> None:
    id_only_records: list[dict[str, object]] = []
    for index in (1, 2, 3):
        binding = _source_binding(index)
        binding.update(
            {
                "result_m3_record_id": f"{index:032x}",
                "observation_state": "SUPPORTED",
            }
        )
        id_only_records.append(binding)
    with pytest.raises(MeasurementQualityError, match="exact keys"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=id_only_records,
        )
    with pytest.raises(MeasurementQualityError, match="exactly three"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=[_result_binding(index) for index in (1, 2)],
        )


def test_result_record_authority_crosslinks_fail_closed() -> None:
    stale_digest = [_result_binding(index) for index in (1, 2, 3)]
    stale_digest[0]["face_count"] = 0
    with pytest.raises(MeasurementQualityError, match="record digest"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=stale_digest,
        )

    wrong_subject = [_result_binding(index) for index in (1, 2, 3)]
    wrong_subject[0]["result_output_id"] = _ID
    _resign_result_record(wrong_subject[0])
    with pytest.raises(MeasurementQualityError, match="certificate subject"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=wrong_subject,
        )

    wrong_runtime = [_result_binding(index) for index in (1, 2, 3)]
    wrong_runtime[0]["runtime_manifest_digest"] = "e" * 64
    _resign_result_record(wrong_runtime[0])
    with pytest.raises(MeasurementQualityError, match="runtime authority"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=wrong_runtime,
        )

    wrong_observation = [_result_binding(index) for index in (1, 2, 3)]
    wrong_observation[0]["measurement_observation_digest"] = _OTHER_DIGEST
    _resign_result_record(wrong_observation[0])
    with pytest.raises(MeasurementQualityError, match="embedded observation digest"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=wrong_observation,
        )


def test_result_m3_record_id_preimage_is_acyclic_and_enforced() -> None:
    record = _result_binding(1)
    expected_preimage: dict[str, JsonValue] = {
        "case_id": _ID,
        "case_specification_digest": _DIGEST,
        "result_output_id": _OTHER_ID,
        "result_sha256": _OTHER_DIGEST,
        "repeat_index": 1,
        "vision_model_manifest_digest": default_authority_bindings().vision_model_manifest_digest,
        "runtime_manifest_digest": default_authority_bindings().runtime_manifest_digest,
        "topology_digest": default_authority_bindings().topology_digest,
    }
    assert (
        record["result_m3_record_id"]
        == mirror_demo_digest(RESULT_M3_RECORD_ID_SCHEMA, expected_preimage)[:32]
    )
    original_id = record["result_m3_record_id"]
    _set_result_observation(record, _different_result_observation())
    assert record["result_m3_record_id"] == original_id

    invalid = [_result_binding(index) for index in (1, 2, 3)]
    invalid[0]["result_m3_record_id"] = "f" * 32
    _resign_result_record(invalid[0])
    with pytest.raises(MeasurementQualityError, match="id preimage"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=invalid,
        )


def test_mandatory_gate_mapping_is_complete() -> None:
    assert len(_MANDATORY_GATES) == 24
    assert all(name in globals() for name in _MANDATORY_GATES.values())


def test_geometric_observability_center_reference() -> None:
    assert _entry(_observation(), 0)["raw_observability_fixed18"] == "0.200000000000000000"


def test_geometric_observability_boundary_monotonicity() -> None:
    interior = _fixed18_value(_entry(_observation(), 0)["raw_observability_fixed18"])
    boundary = _landmarks()
    boundary[123]["x"] = "0.010"
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=boundary,
        ordered_observability_repeats=[deepcopy(boundary) for _ in range(3)],
    )
    assert _fixed18_value(_entry(observed, 0)["raw_observability_fixed18"]) < interior


def test_geometric_observability_required_anchor_set() -> None:
    landmarks = _landmarks()
    del landmarks[123]
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )
    assert _entry(observed, 0)["unsupported_reason"] == "MISSING_MEASUREMENT"
    assert _entry(observed, 1)["support_state"] == "SUPPORTED"


@pytest.mark.parametrize("coordinate", ["NaN", "1.01", "-0.01"])
def test_missing_nonfinite_out_of_range_fails_closed(coordinate: str) -> None:
    landmarks = _landmarks()
    landmarks[123]["x"] = coordinate
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )
    assert _entry(observed, 0)["unsupported_reason"] == "OUT_OF_BOUNDS"


def test_unsupported_reason_precedence_is_order_independent() -> None:
    measurement = _landmarks()
    measurement[123]["x"] = "1.01"
    missing = _landmarks()
    del missing[123]
    valid = _landmarks()

    def observe(repeats: list[dict[int, dict[str, str]]]) -> dict[str, JsonValue]:
        return build_measurement_observation(
            observation_role="SOURCE",
            subject=_source_subject(),
            canonical_output_digest=_DIGEST,
            landmark_digest=_OTHER_DIGEST,
            bindings=default_authority_bindings(),
            measurement_landmarks=measurement,
            ordered_observability_repeats=repeats,
        )

    later_missing = observe([deepcopy(valid), deepcopy(valid), deepcopy(missing)])
    earlier_missing = observe([deepcopy(missing), deepcopy(valid), deepcopy(valid)])
    assert _entry(later_missing, 0)["unsupported_reason"] == "MISSING_MEASUREMENT"
    assert _entry(earlier_missing, 0)["unsupported_reason"] == "MISSING_MEASUREMENT"
    assert _entry(later_missing, 0) == _entry(earlier_missing, 0)

    runtime_unsupported = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=measurement,
        ordered_observability_repeats=[deepcopy(missing) for _ in range(3)],
        runtime_unsupported_dimensions=["cheekbone_width"],
    )
    assert _entry(runtime_unsupported, 0)["unsupported_reason"] == "RUNTIME_UNSUPPORTED"


def test_fixed18_half_even_reference() -> None:
    assert fixed18(Decimal("0.0000000000000000015")) == "0.000000000000000002"


def test_ppm_half_even_reference() -> None:
    assert ppm_from_fixed18("0.000000500000000000") == 0
    assert ppm_from_fixed18("0.000001500000000000") == 2


def test_negative_zero_normalized() -> None:
    assert fixed18(Decimal("-0.0000000000000000004")) == "0.000000000000000000"


def test_no_binary_float_canonical_authority() -> None:
    landmarks = _landmarks()
    landmarks[123]["x"] = 0.25  # type: ignore[assignment]
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )
    assert _entry(observed, 0)["support_state"] == "UNSUPPORTED"


def test_different_geometry_changes_confidence() -> None:
    baseline = _entry(_observation(), 0)["raw_observability_fixed18"]
    landmarks = _landmarks()
    landmarks[123]["x"] = "0.025"
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )
    assert _entry(observed, 0)["raw_observability_fixed18"] != baseline


def test_no_model_confidence_claim() -> None:
    observed = _observation()
    assert observed["confidence_kind"] == "DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE"
    assert "model_confidence" not in observed


def test_no_sensitive_input_field() -> None:
    landmarks = _landmarks()
    landmarks[123]["race"] = "forbidden"
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )
    assert _entry(observed, 0)["unsupported_reason"] == "MISSING_MEASUREMENT"


def test_measurement_observation_exact_keys_and_digest() -> None:
    observed = _observation()
    assert set(observed) == {
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


def test_observation_digest_excludes_repeat_local_fields() -> None:
    observed = _observation()
    preimage = {
        key: value
        for key, value in observed.items()
        if key not in {"schema_version", "measurement_observation_digest"}
    }
    assert "repeat_index" not in preimage
    assert (
        mirror_demo_digest(MEASUREMENT_OBSERVATION_SCHEMA, preimage)
        == observed["measurement_observation_digest"]
    )


def test_supported_and_unsupported_observation_unions() -> None:
    supported = _entry(_observation(), 0)
    assert supported["raw_value_fixed18"] is not None and supported["unsupported_reason"] is None
    low = _landmarks()
    low[123]["x"] = "0.0000004"
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=low,
        ordered_observability_repeats=[deepcopy(low) for _ in range(3)],
    )
    unsupported = _entry(observed, 0)
    assert unsupported["raw_value_fixed18"] is None
    assert unsupported["observability_state"] == "COMPUTED"
    assert unsupported["unsupported_reason"] == "LOW_CONFIDENCE"


def test_measurement_config_digest_replay() -> None:
    config = _authority_manifest()["measurement_execution_config"]
    assert isinstance(config, dict)
    assert replay_measurement_config_digest(config) == MEASUREMENT_CONFIG_DIGEST
    require_replayed_measurement_config_digest(config, MEASUREMENT_CONFIG_DIGEST)
    malformed = dict(config)
    malformed["extra"] = "forbidden"
    with pytest.raises(MeasurementQualityError):
        replay_measurement_config_digest(malformed)
    malformed = dict(config)
    malformed["decimal_precision"] = 50.0
    with pytest.raises(MeasurementQualityError):
        replay_measurement_config_digest(malformed)
    malformed = dict(config)
    malformed["schema_version"] = "mirror.demo/wrong"
    with pytest.raises(MeasurementQualityError):
        replay_measurement_config_digest(malformed)
    with pytest.raises(MeasurementQualityError):
        require_replayed_measurement_config_digest(config, _DIGEST)


def test_import_config_digest_replay() -> None:
    config = _authority_manifest()["identity_import_config"]
    assert isinstance(config, dict)
    assert replay_import_config_digest(config) == IMPORT_CONFIG_DIGEST
    require_replayed_import_config_digest(config, IMPORT_CONFIG_DIGEST)
    malformed = dict(config)
    malformed.pop("schema_version")
    with pytest.raises(MeasurementQualityError):
        replay_import_config_digest(malformed)
    malformed = dict(config)
    malformed["importer_version"] = Decimal("1")
    with pytest.raises(MeasurementQualityError):
        replay_import_config_digest(malformed)


def test_three_repeat_exact_digest_certification() -> None:
    certificate = build_source_repeat_certification(
        subject=_source_subject(),
        bindings=default_authority_bindings(),
        ordered_repeat_bindings=[_source_binding(index) for index in (1, 2, 3)],
    )
    assert certificate["repeat_count"] == 3
    assert certificate["certified_raw_reliability_fixed18"] == "1.000000000000000000"


def test_source_and_result_certificate_preimage() -> None:
    source = build_source_repeat_certification(
        subject=_source_subject(),
        bindings=default_authority_bindings(),
        ordered_repeat_bindings=[_source_binding(index) for index in (1, 2, 3)],
    )
    result = build_result_repeat_certification(
        subject=_result_subject(),
        bindings=default_authority_bindings(),
        result_m3_records=[_result_binding(index) for index in (1, 2, 3)],
    )
    source_payload = {
        key: value
        for key, value in source.items()
        if key not in {"schema_version", "source_repeat_certification_digest"}
    }
    result_payload = {
        key: value
        for key, value in result.items()
        if key not in {"schema_version", "result_repeat_certification_digest"}
    }
    assert (
        mirror_demo_digest(SOURCE_CERTIFICATE_SCHEMA, source_payload)
        == source["source_repeat_certification_digest"]
    )
    assert (
        mirror_demo_digest("mirror.demo/D02ResultRepeatDeterminismCertification/v1", result_payload)
        == result["result_repeat_certification_digest"]
    )


def test_group_certificate_vs_dimension_unsupported_semantics() -> None:
    low = _landmarks()
    low[123]["x"] = "0.0000004"
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=low,
        ordered_observability_repeats=[deepcopy(low) for _ in range(3)],
    )
    assert _entry(observed, 0)["unsupported_reason"] == "LOW_CONFIDENCE"
    certificate = build_source_repeat_certification(
        subject=_source_subject(),
        bindings=default_authority_bindings(),
        ordered_repeat_bindings=[_source_binding(index) for index in (1, 2, 3)],
    )
    assert certificate["certified_reliability_ppm"] == 1_000_000


def test_any_source_repeat_digest_mismatch_stops_before_m4() -> None:
    bindings = [_source_binding(index) for index in (1, 2, 3)]
    bindings[1]["landmark_digest"] = _DIGEST
    with pytest.raises(MeasurementQualityError, match="disagreement"):
        build_source_repeat_certification(
            subject=_source_subject(),
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=bindings,
        )


def test_any_result_repeat_digest_mismatch_stops_report() -> None:
    bindings = [_result_binding(index) for index in (1, 2, 3)]
    _set_result_observation(bindings[1], _different_result_observation())
    with pytest.raises(MeasurementQualityError, match="disagreement"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=bindings,
        )


def test_structural_precondition_failure_creates_no_certificate() -> None:
    bindings = [_source_binding(index) for index in (1, 2, 3)]
    bindings[0]["face_count"] = 0
    with pytest.raises(MeasurementQualityError, match="structural"):
        build_source_repeat_certification(
            subject=_source_subject(),
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=bindings,
        )


def test_deterministic_replay_byte_identical() -> None:
    assert _observation() == _observation()
    assert build_result_repeat_certification(
        subject=_result_subject(),
        bindings=default_authority_bindings(),
        result_m3_records=[_result_binding(index) for index in (1, 2, 3)],
    ) == build_result_repeat_certification(
        subject=_result_subject(),
        bindings=default_authority_bindings(),
        result_m3_records=[_result_binding(index) for index in (1, 2, 3)],
    )


def test_zero_normalizer_is_out_of_bounds() -> None:
    landmarks = _landmarks()
    landmarks[152] = deepcopy(landmarks[10])
    observed = build_measurement_observation(
        observation_role="SOURCE",
        subject=_source_subject(),
        canonical_output_digest=_DIGEST,
        landmark_digest=_OTHER_DIGEST,
        bindings=default_authority_bindings(),
        measurement_landmarks=landmarks,
        ordered_observability_repeats=[deepcopy(landmarks) for _ in range(3)],
    )
    assert _entry(observed, 0)["unsupported_reason"] == "OUT_OF_BOUNDS"


def test_result_unsupported_explicit_token_and_mixed_state_fail_closed() -> None:
    bindings = [_result_binding(index) for index in (1, 2, 3)]
    for binding in bindings:
        _set_result_observation(binding, _result_observation_with_runtime_unsupported())
    certificate = build_result_repeat_certification(
        subject=_result_subject(),
        bindings=default_authority_bindings(),
        result_m3_records=bindings,
    )
    assert certificate["certification_state"] == "CERTIFIED_EXACT_REPEAT"
    mixed = [_result_binding(index) for index in (1, 2, 3)]
    mixed[1]["observation_state"] = "UNSUPPORTED_EXPLICIT"
    _resign_result_record(mixed[1])
    with pytest.raises(MeasurementQualityError, match="state does not match"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=mixed,
        )
    invalid = [_result_binding(index) for index in (1, 2, 3)]
    invalid[0]["observation_state"] = "UNSUPPORTED"
    _resign_result_record(invalid[0])
    with pytest.raises(MeasurementQualityError, match="state does not match"):
        build_result_repeat_certification(
            subject=_result_subject(),
            bindings=default_authority_bindings(),
            result_m3_records=invalid,
        )


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "source_m3_record_id",
        "source_m3_record_digest",
        "source_manifest_digest",
        "source_admission_event_id",
        "source_admission_content_digest",
        "identity_content_digest",
        "source_fact_snapshot_digest",
        "source_authority_manifest_entry_digest",
        "report_digest",
        "source_authority_key",
        "placeholder_post_admission_id",
    ],
)
def test_source_certificate_forbids_every_post_admission_authority(forbidden_key: str) -> None:
    bindings = [_source_binding(index) for index in (1, 2, 3)]
    bindings[0][forbidden_key] = _DIGEST
    with pytest.raises(MeasurementQualityError, match="exact keys"):
        build_source_repeat_certification(
            subject=_source_subject(),
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=bindings,
        )
    with pytest.raises(MeasurementQualityError, match="exact keys"):
        build_source_repeat_certification(
            subject=_source_subject() | {forbidden_key: _DIGEST},
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=[_source_binding(index) for index in (1, 2, 3)],
        )


def test_canonical_json_bytes_parity_with_accepted_primitive() -> None:
    payload: dict[str, JsonValue] = {
        "z": ["汉字", {"b": 2, "a": None}],
        "a": {"nested": [True, "é", 7], "ordered": "first"},
    }
    assert canonical_json_bytes(payload) == accepted_canonical_json_bytes(payload)
    assert canonical_json_bytes(payload) == (
        b'{"a":{"nested":[true,"\xc3\xa9",7],"ordered":"first"},'
        b'"z":["\xe6\xb1\x89\xe5\xad\x97",{"a":null,"b":2}]}'
    )


def test_fresh_interpreter_import_has_no_application_or_database_modules() -> None:
    source_path = Path(__file__).resolve().parents[1] / "src"
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(source_path)!r}); "
        "import mirror_api.demo_measurement_quality; "
        "forbidden={'sqlalchemy','mirror_api.demo_models','mirror_api.models'}; "
        "assert not forbidden.intersection(sys.modules), "
        "sorted(forbidden.intersection(sys.modules))"
    )
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", script], check=False, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr


def test_measurement_quality_source_import_allowlist() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "src" / "mirror_api" / "demo_measurement_quality.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "demo_idempotency",
        "demo_models",
        "from mirror_api.models",
        "sqlalchemy",
        "fastapi",
        "celery",
    )
    assert not any(token in source for token in forbidden)
