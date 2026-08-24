"""Pure Candidate 3 graph coverage; fixtures are structural, never private evidence."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, cast

import pytest

import mirror_api.demo_d02_authority as d02_authority
from mirror_api.demo_d02_authority import (
    EMPTY_LOCK_POLICY_DIGEST,
    REPORT_GROUPS,
    SCREENING_POLICY_DIGEST,
    D02AuthorityError,
    build_decode_structure_record,
    build_dimension_eligibility_evidence,
    build_exact_duplicate_evidence,
    build_facts,
    build_identity_row,
    build_image_authority_evidence,
    build_m4_execution_record,
    build_manual_artifact_decision,
    build_measurement_gate,
    build_morphology_projection,
    build_ordered_case_manifest,
    build_pair_screening_evidence,
    build_phash_observation_evidence,
    build_raw_measurement_authority,
    build_report_row,
    build_result_m3_record,
    build_schema_and_policy_binding,
    build_selected_pair_manifest,
    build_selection_trace,
    build_source_m3_record,
    build_source_manifest_entry,
    derive_asset_variant_id,
    derive_imported_asset_id,
    derive_local_source_authority_key,
    derive_source_m3_record_id,
    digest_facts,
    digest_morphology_projection,
    digest_raw_measurement_authority,
    digest_source_manifest,
    validate_admit_revoke_copy,
    validate_case_manifest_entry,
    validate_complete_source_graph,
    validate_decode_structure_evidence,
    validate_decode_structure_record,
    validate_dimension_eligibility_evidence,
    validate_exact_duplicate_evidence,
    validate_facts,
    validate_identity_row,
    validate_image_authority_evidence,
    validate_m4_execution_record,
    validate_m4_repeat_evidence,
    validate_manual_artifact_decision,
    validate_manual_review_evidence,
    validate_measurement_gate,
    validate_measurement_observation,
    validate_network_runtime_boundary,
    validate_ordered_case_manifest,
    validate_phash_observation_evidence,
    validate_report_row,
    validate_result_certificate,
    validate_result_m3_gate_cross_graph,
    validate_result_m3_record,
    validate_schema_and_policy_binding,
    validate_selection_trace,
    validate_source_certificate,
    validate_source_m3_record,
    validate_source_manifest_entry,
)
from mirror_api.demo_measurement_quality import (
    CONFIDENCE_KIND,
    IMPORT_CONFIG_DIGEST,
    MEASUREMENT_CONFIG_DIGEST,
    QUALITY_CONFIG_DIGEST,
    QUALITY_MANIFEST_DIGEST,
    RELIABILITY_KIND,
    RUNTIME_MANIFEST_DIGEST,
    TOPOLOGY_DIGEST,
    VISION_MODEL_MANIFEST_DIGEST,
    AuthorityBindings,
    build_measurement_observation,
    build_result_repeat_certification,
    build_source_repeat_certification,
    default_authority_bindings,
    derive_result_m3_record_id,
    mirror_demo_digest,
)

_ACCEPTED_SOURCE_P2_MANIFEST_DIGEST = (
    "eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4"
)
_ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST = (
    "d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a"
)
_ACCEPTED_GEOMETRY_ONTOLOGY_DIGEST = (
    "d902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9"
)


def _digest(char: str) -> str:
    return char * 64


def _identifier(char: str) -> str:
    return char * 32


def _result_asset_id(m4_record: dict[str, Any]) -> str:
    return derive_imported_asset_id(
        asset_role="synthetic",
        semantic_role="SELECTED_RESULT",
        sha256=m4_record["result_sha256"],
        byte_size=m4_record["result_byte_size"],
        mime_type=m4_record["result_mime_type"],
        width=m4_record["result_width"],
        height=m4_record["result_height"],
    )


def _result_variant_binding(case: dict[str, Any], m4_record: dict[str, Any]) -> dict[str, str]:
    result_asset_id = _result_asset_id(m4_record)
    return {
        "source_asset_id": case["source_asset_id"],
        "source_asset_sha256": case["source_asset_sha256"],
        "result_asset_id": result_asset_id,
        "result_asset_sha256": m4_record["result_sha256"],
        "asset_variant_id": derive_asset_variant_id(
            variant_type="demo_p3_p7_geometry_v1",
            source_asset_id=case["source_asset_id"],
            source_asset_sha256=case["source_asset_sha256"],
            result_asset_id=result_asset_id,
            result_asset_sha256=m4_record["result_sha256"],
            case_specification_digest=case["case_specification_digest"],
        ),
        "asset_variant_type": "demo_p3_p7_geometry_v1",
        "case_specification_digest": case["case_specification_digest"],
    }


def _fixed18(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000000000000000001")), "f")


def _resign_identity(row: dict[str, Any]) -> None:
    canonical = {
        key: value
        for key, value in row.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    row["canonical_payload"] = canonical
    row["content_digest"] = mirror_demo_digest("mirror.demo/DemoSyntheticIdentity/v3", canonical)
    row["id"] = mirror_demo_digest(
        "mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2",
        {
            "source_authority_kind": row["source_authority_kind"],
            "source_authority_key": row["source_authority_key"],
            "admission_sequence": row["admission_sequence"],
            "admission_action": row["admission_action"],
            "supersedes_id": row["supersedes_id"],
            "admission_config_digest": row["admission_config_digest"],
            "canonical_payload_digest": row["content_digest"],
        },
    )[:32]


def _resign_source_entry(entry: dict[str, Any]) -> None:
    payload = {
        key: value for key, value in entry.items() if key not in {"schema_version", "record_digest"}
    }
    entry["record_digest"] = mirror_demo_digest(
        "mirror.demo/D02SourceAuthorityManifestEntry/v3", payload
    )


def _resign_source_certificate(certificate: dict[str, Any]) -> None:
    payload = {
        key: value
        for key, value in certificate.items()
        if key not in {"schema_version", "source_repeat_certification_digest"}
    }
    certificate["source_repeat_certification_digest"] = mirror_demo_digest(
        "mirror.demo/D02SourceRepeatDeterminismCertification/v1", payload
    )


def _resign_source_m3_record(record: dict[str, Any]) -> None:
    payload = {
        key: value
        for key, value in record.items()
        if key not in {"schema_version", "record_digest"}
    }
    record["record_digest"] = mirror_demo_digest("mirror.demo/D02SourceM3RepeatRecord/v2", payload)


def _ordered_source_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        deepcopy(entries),
        key=lambda entry: (entry["source_authority_key"], entry["source_admission_event_id"]),
    )
    for ordinal, entry in enumerate(ordered, start=1):
        entry["source_ordinal"] = ordinal
        _resign_source_entry(entry)
    return ordered


def _source_manifest_digest_oracle(entries: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        entries,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(b"mirror.demo/D02SourceAuthorityManifest/v1\n" + canonical).hexdigest()


def _resign_gate(gate: dict[str, Any]) -> None:
    gate["record_digest"] = mirror_demo_digest(
        "mirror.demo/D02MeasurementGateRecord/v4",
        {
            key: value
            for key, value in gate.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def _resign_observation(observation: dict[str, Any]) -> None:
    observation["measurement_observation_digest"] = mirror_demo_digest(
        "mirror.demo/D02MeasurementObservation/v1",
        {
            key: value
            for key, value in observation.items()
            if key not in {"schema_version", "measurement_observation_digest"}
        },
    )


def _landmarks() -> dict[int, dict[str, str]]:
    coordinates = {
        10: ("0.300000000000000000", "0.300000000000000000"),
        17: ("0.450000000000000000", "0.450000000000000000"),
        61: ("0.400000000000000000", "0.500000000000000000"),
        98: ("0.450000000000000000", "0.400000000000000000"),
        123: ("0.400000000000000000", "0.400000000000000000"),
        133: ("0.450000000000000000", "0.500000000000000000"),
        152: ("0.700000000000000000", "0.700000000000000000"),
        234: ("0.400000000000000000", "0.600000000000000000"),
        291: ("0.600000000000000000", "0.500000000000000000"),
        327: ("0.550000000000000000", "0.400000000000000000"),
        352: ("0.600000000000000000", "0.400000000000000000"),
        362: ("0.550000000000000000", "0.500000000000000000"),
        454: ("0.600000000000000000", "0.600000000000000000"),
    }
    return {index: {"x": x, "y": y} for index, (x, y) in coordinates.items()}


def _source_observation(
    *,
    source_output_id: str = _identifier("a"),
    source_asset_id: str = _identifier("b"),
    source_asset_sha256: str = _digest("c"),
    canonical_output_digest: str = _digest("d"),
    landmark_digest: str = _digest("e"),
) -> dict[str, Any]:
    subject: dict[str, object] = {
        "schema_version": "mirror.demo/D02SourceObservationSubject/v1",
        "source_output_id": source_output_id,
        "source_asset_id": source_asset_id,
        "source_asset_sha256": source_asset_sha256,
    }
    landmarks = _landmarks()
    return cast(
        dict[str, Any],
        build_measurement_observation(
            observation_role="SOURCE",
            subject=subject,
            canonical_output_digest=canonical_output_digest,
            landmark_digest=landmark_digest,
            bindings=default_authority_bindings(),
            measurement_landmarks=landmarks,
            ordered_observability_repeats=[landmarks, landmarks, landmarks],
        ),
    )


def _source_certificate(
    observation: dict[str, Any], *, execution_receipt_digest: str = _digest("f")
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        build_source_repeat_certification(
            subject=cast(dict[str, object], observation["subject"]),
            bindings=default_authority_bindings(),
            ordered_repeat_bindings=[
                {
                    "repeat_index": index,
                    "execution_receipt_digest": execution_receipt_digest,
                    "canonical_output_digest": observation["canonical_output_digest"],
                    "landmark_digest": observation["landmark_digest"],
                    "measurement_observation_digest": observation["measurement_observation_digest"],
                    "face_count": 1,
                    "landmark_count": 478,
                    "coordinates_finite": True,
                    "coordinates_in_bounds": True,
                    "repeat_gate_passed": True,
                }
                for index in (1, 2, 3)
            ],
        ),
    )


def _source_m3_records(
    manifest_digest: str | None = None,
    *,
    source_manifest_entries: list[dict[str, Any]] | None = None,
    observation: dict[str, Any] | None = None,
    certificate: dict[str, Any] | None = None,
    source_entry: dict[str, Any] | None = None,
    use_authority_builder: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], str]:
    if source_entry is None and use_authority_builder:
        chains = _independent_source_chains()
        source_manifest_entries = [entry for _, _, entry in chains]
        facts, _, source_entry = chains[0]
        manifest_digest = digest_source_manifest(source_manifest_entries)
        observation = observation or cast(dict[str, Any], facts["source_measurement_observation"])
        certificate = certificate or cast(dict[str, Any], facts["source_repeat_certification"])
    elif source_entry is None:
        facts, _, source_entry = _facts_identity_manifest()
        observation = observation or cast(dict[str, Any], facts["source_measurement_observation"])
        certificate = certificate or cast(dict[str, Any], facts["source_repeat_certification"])
    else:
        observation = observation or _source_observation()
        certificate = certificate or _source_certificate(observation)
    if manifest_digest is None:
        raise AssertionError("source M3 test authority requires a manifest digest")
    source = source_entry
    records: list[dict[str, Any]] = []
    for binding in cast(list[dict[str, Any]], certificate["ordered_repeat_bindings"]):
        index = int(binding["repeat_index"])
        fields: dict[str, Any] = {
            "source_m3_record_id": derive_source_m3_record_id(
                source_manifest_digest=manifest_digest,
                source_authority_key=source["source_authority_key"],
                source_admission_event_id=source["source_admission_event_id"],
                source_asset_id=source["source_asset_id"],
                source_asset_sha256=source["source_asset_sha256"],
                repeat_index=index,
            ),
            "source_ordinal": source["source_ordinal"],
            "source_authority_key": source["source_authority_key"],
            "source_admission_event_id": source["source_admission_event_id"],
            "source_asset_id": source["source_asset_id"],
            "source_asset_sha256": source["source_asset_sha256"],
            "repeat_index": index,
            "execution_receipt_digest": binding["execution_receipt_digest"],
            "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
            "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
            "topology_digest": TOPOLOGY_DIGEST,
            "canonical_output_digest": binding["canonical_output_digest"],
            "landmark_digest": binding["landmark_digest"],
            "measurement_observation": observation,
            "measurement_observation_digest": observation["measurement_observation_digest"],
            "face_count": 1,
            "landmark_count": 478,
            "coordinates_finite": True,
            "coordinates_in_bounds": True,
            "repeat_gate_passed": True,
        }
        if use_authority_builder:
            if source_manifest_entries is None:
                raise AssertionError(
                    "SourceM3 builder tests require all four source-manifest entries"
                )
            record = cast(
                dict[str, Any],
                build_source_m3_record(
                    fields,
                    source_manifest_entries=source_manifest_entries,
                    source_entry=source,
                    certificate=certificate,
                    facts_observation=observation,
                    source_manifest_digest=manifest_digest,
                ),
            )
        else:
            record = {
                "schema_version": "mirror.demo/D02SourceM3RepeatRecord/v2",
                **fields,
            }
            _resign_source_m3_record(record)
        records.append(record)
    return observation, certificate, records, manifest_digest


def _result_m3_records() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    subject: dict[str, object] = {
        "schema_version": "mirror.demo/D02ResultObservationSubject/v1",
        "case_id": _identifier("a"),
        "case_specification_digest": _digest("b"),
        "result_output_id": _identifier("c"),
        "result_sha256": _digest("d"),
    }
    landmarks = _landmarks()
    observation = cast(
        dict[str, Any],
        build_measurement_observation(
            observation_role="RESULT",
            subject=subject,
            canonical_output_digest=_digest("e"),
            landmark_digest=_digest("f"),
            bindings=default_authority_bindings(),
            measurement_landmarks=landmarks,
            ordered_observability_repeats=[landmarks, landmarks, landmarks],
        ),
    )
    records: list[dict[str, Any]] = []
    for index in (1, 2, 3):
        record_id = derive_result_m3_record_id(
            case_id=subject["case_id"],
            case_specification_digest=subject["case_specification_digest"],
            result_output_id=subject["result_output_id"],
            result_sha256=subject["result_sha256"],
            repeat_index=index,
            bindings=default_authority_bindings(),
        )
        records.append(
            cast(
                dict[str, Any],
                build_result_m3_record(
                    {
                        "result_m3_record_id": record_id,
                        "case_id": subject["case_id"],
                        "case_specification_digest": subject["case_specification_digest"],
                        "result_output_id": subject["result_output_id"],
                        "result_sha256": subject["result_sha256"],
                        "repeat_index": index,
                        "execution_receipt_digest": _digest("1"),
                        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
                        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
                        "topology_digest": TOPOLOGY_DIGEST,
                        "canonical_output_digest": observation["canonical_output_digest"],
                        "landmark_digest": observation["landmark_digest"],
                        "measurement_observation": observation,
                        "measurement_observation_digest": observation[
                            "measurement_observation_digest"
                        ],
                        "face_count": 1,
                        "landmark_count": 478,
                        "coordinates_finite": True,
                        "coordinates_in_bounds": True,
                        "observation_state": "SUPPORTED",
                        "repeat_gate_passed": True,
                    }
                ),
            )
        )
    return observation, records


def _gate_from_records(
    observation: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    """A fully re-signed supported Gate v4 with zero deltas (therefore FAIL)."""
    source_observation = _source_observation()
    source_certificate = _source_certificate(source_observation)
    raw = build_raw_measurement_authority(
        source_observation,
        source_certificate,
        source_p2_candidate_manifest_content_digest=_digest("1"),
        dimension_authority_manifest_content_digest=_digest("2"),
    )
    projection = build_morphology_projection(raw)
    supported = [
        {
            "schema_version": "mirror.demo/D02SupportedSourceMeasurement/v1",
            "dimension_key": raw_entry["dimension_key"],
            "raw_value_fixed18": raw_entry["raw_value_fixed18"],
            "raw_confidence_fixed18": raw_entry["raw_confidence_fixed18"],
            "raw_reliability_fixed18": raw_entry["raw_reliability_fixed18"],
            "value_ppm": projection_entry["value_ppm"],
            "confidence_ppm": projection_entry["confidence_ppm"],
            "reliability_ppm": projection_entry["reliability_ppm"],
            "unit": "FACE_HEIGHT_PPM",
        }
        for raw_entry, projection_entry in zip(
            cast(list[dict[str, Any]], raw["ordered_entries"]),
            cast(list[dict[str, Any]], projection["ordered_entries"]),
            strict=True,
        )
    ]
    target = supported[0]
    controls = supported[1:]
    result_measurements = [
        {
            "schema_version": "mirror.demo/D02SupportedResultMeasurement/v1",
            "repeat_index": record["repeat_index"],
            "result_m3_record_digest": record["record_digest"],
            "raw_result_target_fixed18": target["raw_value_fixed18"],
            "raw_signed_target_delta_fixed18": "0.000000000000000000",
            "raw_target_absolute_delta_fixed18": "0.000000000000000000",
            "ordered_control_deltas": [
                {
                    "schema_version": "mirror.demo/D02ControlDelta/v1",
                    "control_ordinal": ordinal,
                    "dimension_key": control["dimension_key"],
                    "raw_source_value_fixed18": control["raw_value_fixed18"],
                    "raw_result_value_fixed18": control["raw_value_fixed18"],
                    "raw_absolute_delta_fixed18": "0.000000000000000000",
                    "drift_ppm": 0,
                }
                for ordinal, control in enumerate(controls, start=1)
            ],
            "winning_control_ordinal": 1,
            "max_control_dimension_key": controls[0]["dimension_key"],
            "raw_max_control_drift_fixed18": "0.000000000000000000",
            "measured_signed_delta_ppm": 0,
            "target_absolute_delta_ppm": 0,
            "drift_ppm": 0,
            "direction_gate_passed": False,
            "target_min_gate_passed": False,
            "target_max_gate_passed": True,
            "control_drift_gate_passed": True,
        }
        for record in records
    ]
    certificate = build_result_repeat_certification(
        subject=cast(dict[str, object], observation["subject"]),
        bindings=default_authority_bindings(),
        result_m3_records=records,
    )
    return cast(
        dict[str, Any],
        build_measurement_gate(
            {
                "case_id": observation["subject"]["case_id"],
                "case_specification_digest": observation["subject"]["case_specification_digest"],
                "dimension_key": "cheekbone_width",
                "requested_direction": "INCREASE",
                "requested_magnitude_ppm": 15_000,
                "monotonicity_peer_case_id": _identifier("e"),
                "source_target_measurement": target,
                "ordered_source_control_measurements": controls,
                "ordered_result_repeat_measurements": result_measurements,
                "measurement_evaluation_state": "SUPPORTED_EVALUATED",
                "gate_evaluation": {
                    "schema_version": "mirror.demo/D02SupportedMeasurementGateEvaluation/v1",
                    "direction_gate_passed": False,
                    "target_min_gate_passed": False,
                    "target_max_gate_passed": True,
                    "control_drift_gate_passed": True,
                    "magnitude_monotonicity_gate_passed": True,
                    "measurement_gate_passed": False,
                },
                "result_repeat_certification": certificate,
                "result_repeat_certification_digest": certificate[
                    "result_repeat_certification_digest"
                ],
            }
        ),
    )


def _facts_identity_manifest(
    *,
    source_ordinal: int = 1,
    source_marker: str | None = None,
    source_p2_manifest_digest: str = _ACCEPTED_SOURCE_P2_MANIFEST_DIGEST,
    dimension_authority_manifest_digest: str = _ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_output_id = _identifier("a") if source_marker is None else _identifier(source_marker)
    source_asset_sha256 = _digest("c") if source_marker is None else _digest(source_marker)
    source_asset_id = derive_imported_asset_id(
        asset_role="synthetic",
        semantic_role="SOURCE",
        sha256=source_asset_sha256,
        byte_size=1,
        mime_type="image/jpeg",
        width=1,
        height=1,
    )
    canonical_output_digest = _digest("d") if source_marker is None else _digest(source_marker)
    landmark_digest = _digest("e") if source_marker is None else _digest(source_marker)
    receipt_digest = _digest("f") if source_marker is None else _digest(source_marker)
    metadata_digest = _digest("1") if source_marker is None else _digest(source_marker)
    source_authority_key = derive_local_source_authority_key(
        source_output_id=source_output_id,
        source_asset_id=source_asset_id,
        source_asset_sha256=source_asset_sha256,
        source_receipt_digest=metadata_digest,
    )
    observation = _source_observation(
        source_output_id=source_output_id,
        source_asset_id=source_asset_id,
        source_asset_sha256=source_asset_sha256,
        canonical_output_digest=canonical_output_digest,
        landmark_digest=landmark_digest,
    )
    certificate = _source_certificate(observation, execution_receipt_digest=receipt_digest)
    raw = build_raw_measurement_authority(
        observation,
        certificate,
        source_p2_candidate_manifest_content_digest=source_p2_manifest_digest,
        dimension_authority_manifest_content_digest=dimension_authority_manifest_digest,
    )
    projection = build_morphology_projection(raw)
    subject = cast(dict[str, Any], observation["subject"])
    facts = cast(
        dict[str, Any],
        build_facts(
            {
                "source_output_id": subject["source_output_id"],
                "source_asset_sha256": subject["source_asset_sha256"],
                "source_asset_byte_size": 1,
                "source_asset_mime_type": "image/jpeg",
                "source_asset_width": 1,
                "source_asset_height": 1,
                "source_receipt_digest": metadata_digest,
                "source_authority_digest": metadata_digest,
                "qa_policy_digest": metadata_digest,
                "source_qa_snapshot_digest": metadata_digest,
                "source_landmark_digest": observation["landmark_digest"],
                "source_measurement_digest": observation["measurement_observation_digest"],
                "source_provenance_digest": metadata_digest,
                "source_measurement_projection": projection,
                "source_measurement_projection_digest": digest_morphology_projection(projection),
                "raw_measurement_authority": raw,
                "raw_measurement_authority_digest": digest_raw_measurement_authority(raw),
                "adult_synthetic_attested": True,
                "original_formal_identity_id_status": "UNKNOWN_REDACTED_NOT_RECOVERED",
                "measurement_projection_version": projection["measurement_projection_version"],
                "measurement_quantization_version": projection["measurement_quantization_version"],
                "source_p2_candidate_manifest_content_digest": raw[
                    "source_p2_candidate_manifest_content_digest"
                ],
                "dimension_authority_manifest_content_digest": raw[
                    "dimension_authority_manifest_content_digest"
                ],
                "source_measurement_observation": observation,
                "source_measurement_observation_digest": observation[
                    "measurement_observation_digest"
                ],
                "source_repeat_certification": certificate,
                "source_repeat_certification_digest": certificate[
                    "source_repeat_certification_digest"
                ],
            }
        ),
    )
    identity = cast(
        dict[str, Any],
        build_identity_row(
            {
                "created_at": "2026-08-24T00:00:00Z",
                "formal_synthetic_identity_id": None,
                "formal_canonical_asset_id": source_asset_id,
                "formal_canonical_asset_sha256": source_asset_sha256,
                "formal_accepted_qa_run_id": None,
                "formal_accepted_qa_snapshot_digest": None,
                "admission_sequence": 1,
                "admission_action": "ADMIT",
                "admission_config_digest": metadata_digest,
                "supersedes_id": None,
                "source_output_id": facts["source_output_id"],
                "source_receipt_digest": facts["source_receipt_digest"],
                "source_authority_digest": facts["source_authority_digest"],
                "source_qa_snapshot_digest": facts["source_qa_snapshot_digest"],
                "source_landmark_digest": facts["source_landmark_digest"],
                "source_measurement_digest": facts["source_measurement_digest"],
                "source_provenance_digest": facts["source_provenance_digest"],
                "source_fact_snapshot": facts,
                "source_fact_snapshot_digest": digest_facts(facts),
                "source_measurement_projection": projection,
                "source_measurement_projection_digest": digest_morphology_projection(projection),
                "original_formal_identity_id_status": facts["original_formal_identity_id_status"],
                "adult_synthetic_attested": True,
                "importer_version": "demo-d02-identity-importer-v3",
                "import_config_digest": IMPORT_CONFIG_DIGEST,
                "source_authority_kind": "DEMO_LOCAL_IMPORTED_COPY",
                "source_authority_key": source_authority_key,
            },
            facts=facts,
        ),
    )
    supported = [
        {
            "schema_version": "mirror.demo/D02SupportedSourceMeasurement/v1",
            "dimension_key": raw_entry["dimension_key"],
            "raw_value_fixed18": raw_entry["raw_value_fixed18"],
            "raw_confidence_fixed18": raw_entry["raw_confidence_fixed18"],
            "raw_reliability_fixed18": raw_entry["raw_reliability_fixed18"],
            "value_ppm": projection_entry["value_ppm"],
            "confidence_ppm": projection_entry["confidence_ppm"],
            "reliability_ppm": projection_entry["reliability_ppm"],
            "unit": "FACE_HEIGHT_PPM",
        }
        for raw_entry, projection_entry in zip(
            cast(list[dict[str, Any]], raw["ordered_entries"]),
            cast(list[dict[str, Any]], projection["ordered_entries"]),
            strict=True,
        )
    ]
    entry_fields: dict[str, Any] = {
        "source_ordinal": source_ordinal,
        "source_authority_kind": identity["source_authority_kind"],
        "source_authority_key": identity["source_authority_key"],
        "source_admission_event_id": identity["id"],
        "source_admission_content_digest": identity["content_digest"],
        "source_output_id": facts["source_output_id"],
        "source_asset_id": subject["source_asset_id"],
        "source_asset_sha256": facts["source_asset_sha256"],
        "source_asset_byte_size": facts["source_asset_byte_size"],
        "source_asset_mime_type": facts["source_asset_mime_type"],
        "source_asset_width": facts["source_asset_width"],
        "source_asset_height": facts["source_asset_height"],
        "source_receipt_digest": facts["source_receipt_digest"],
        "source_authority_digest": facts["source_authority_digest"],
        "source_qa_snapshot_digest": facts["source_qa_snapshot_digest"],
        "source_landmark_digest": facts["source_landmark_digest"],
        "source_measurement_digest": facts["source_measurement_digest"],
        "source_provenance_digest": facts["source_provenance_digest"],
        "source_fact_snapshot_digest": digest_facts(facts),
        "raw_measurement_authority_digest": digest_raw_measurement_authority(raw),
        "source_measurement_projection_digest": digest_morphology_projection(projection),
        "adult_synthetic_attested": True,
        "original_formal_identity_id_status": facts["original_formal_identity_id_status"],
        "source_p2_candidate_manifest_content_digest": raw[
            "source_p2_candidate_manifest_content_digest"
        ],
        "dimension_authority_manifest_content_digest": raw[
            "dimension_authority_manifest_content_digest"
        ],
        "measurement_config_digest": raw["measurement_config_digest"],
        "measurement_quality_config_digest": raw["measurement_quality_config_digest"],
        "measurement_quality_manifest_content_digest": raw[
            "measurement_quality_manifest_content_digest"
        ],
        "confidence_kind": raw["confidence_kind"],
        "reliability_kind": raw["reliability_kind"],
        "runtime_manifest_digest": raw["runtime_manifest_digest"],
        "vision_model_manifest_digest": raw["vision_model_manifest_digest"],
        "topology_digest": raw["topology_digest"],
        "source_repeat_certification_digest": certificate["source_repeat_certification_digest"],
        "import_config_digest": identity["import_config_digest"],
        "ordered_supported_measurements": supported,
    }
    entry = cast(dict[str, Any], build_source_manifest_entry(entry_fields))
    return facts, identity, entry


def _source_m3_builder_input() -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    str,
    dict[str, Any],
]:
    chains = _independent_source_chains()
    source_manifest_entries = [entry for _, _, entry in chains]
    facts, _, source_entry = chains[0]
    observation = cast(dict[str, Any], facts["source_measurement_observation"])
    certificate = cast(dict[str, Any], facts["source_repeat_certification"])
    source_manifest_digest = digest_source_manifest(source_manifest_entries)
    _, _, records, _ = _source_m3_records(
        source_manifest_digest,
        source_manifest_entries=source_manifest_entries,
        observation=observation,
        certificate=certificate,
        source_entry=source_entry,
    )
    fields = {
        key: deepcopy(value)
        for key, value in records[0].items()
        if key not in {"schema_version", "record_digest"}
    }
    return (
        observation,
        certificate,
        source_manifest_entries,
        source_entry,
        source_manifest_digest,
        fields,
    )


def test_source_certificate_exact_keys_no_post_admission_id_and_dag() -> None:
    observation = _source_observation()
    certificate = _source_certificate(observation)
    validate_measurement_observation(observation, role="SOURCE")
    validate_source_certificate(certificate)
    assert "source_m3_record_id" not in certificate
    assert "source_manifest_digest" not in certificate
    record_id = derive_source_m3_record_id(
        source_manifest_digest=_digest("0"),
        source_authority_key=_digest("9"),
        source_admission_event_id=_identifier("1"),
        source_asset_id=_identifier("b"),
        source_asset_sha256=_digest("c"),
        repeat_index=1,
    )
    assert len(record_id) == 32


@pytest.mark.parametrize(
    "forbidden",
    [
        "source_m3_record_id",
        "source_m3_record_digest",
        "source_manifest_digest",
        "source_admission_event_id",
        "source_fact_snapshot_digest",
        "source_authority_key",
    ],
)
def test_source_certificate_post_admission_aliases_fail_closed(forbidden: str) -> None:
    certificate = _source_certificate(_source_observation())
    certificate[forbidden] = "placeholder"
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_source_certificate(certificate)


def test_raw_v2_projection_v2_digest_and_observation_separation() -> None:
    observation = _source_observation()
    certificate = _source_certificate(observation)
    raw = build_raw_measurement_authority(
        observation,
        certificate,
        source_p2_candidate_manifest_content_digest=_digest("1"),
        dimension_authority_manifest_content_digest=_digest("2"),
    )
    projection = cast(dict[str, Any], build_morphology_projection(raw))
    assert digest_raw_measurement_authority(raw) != observation["measurement_observation_digest"]
    assert digest_morphology_projection(projection) != digest_raw_measurement_authority(raw)
    assert projection["ordered_entries"][0]["confidence_ppm"] == 600000


def test_supported_source_measurement_uses_frozen_schema_literal() -> None:
    _, _, entry = _facts_identity_manifest()
    measurements = cast(list[dict[str, Any]], entry["ordered_supported_measurements"])
    assert all(
        item["schema_version"] == "mirror.demo/D02SupportedSourceMeasurement/v1"
        for item in measurements
    )
    validate_source_manifest_entry(entry)

    renamed_alias = deepcopy(entry)
    renamed_measurements = cast(
        list[dict[str, Any]], renamed_alias["ordered_supported_measurements"]
    )
    renamed_measurements[0]["schema_version"] = "mirror.demo/D02SourceSupportedMeasurement/v1"
    _resign_source_entry(renamed_alias)
    with pytest.raises(D02AuthorityError, match="supported measurement schema"):
        validate_source_manifest_entry(renamed_alias)


@pytest.mark.parametrize(
    ("raw_field", "ppm_field"),
    [
        ("raw_value_fixed18", "value_ppm"),
        ("raw_confidence_fixed18", "confidence_ppm"),
        ("raw_reliability_fixed18", "reliability_ppm"),
    ],
)
def test_supported_source_measurement_rejects_resigned_zero_ppm(
    raw_field: str, ppm_field: str
) -> None:
    _, _, entry = _facts_identity_manifest()
    measurements = cast(list[dict[str, Any]], entry["ordered_supported_measurements"])
    measurements[0][raw_field] = "0.000000000000000000"
    measurements[0][ppm_field] = 0
    _resign_source_entry(entry)

    with pytest.raises(D02AuthorityError, match="raw/ppm projection"):
        validate_source_manifest_entry(entry)


@pytest.mark.parametrize(
    ("raw_field", "ppm_field"),
    [
        ("raw_value_fixed18", "value_ppm"),
        ("raw_confidence_fixed18", "confidence_ppm"),
        ("raw_reliability_fixed18", "reliability_ppm"),
    ],
)
def test_supported_projection_rejects_values_that_quantize_to_zero(
    raw_field: str, ppm_field: str
) -> None:
    observation = _source_observation()
    certificate = _source_certificate(observation)
    raw = cast(
        dict[str, Any],
        build_raw_measurement_authority(
            observation,
            certificate,
            source_p2_candidate_manifest_content_digest=_digest("1"),
            dimension_authority_manifest_content_digest=_digest("2"),
        ),
    )
    projection = cast(dict[str, Any], build_morphology_projection(raw))
    raw_entries = cast(list[dict[str, Any]], raw["ordered_entries"])
    projection_entries = cast(list[dict[str, Any]], projection["ordered_entries"])
    raw_entries[0][raw_field] = "0.000000400000000000"
    projection_entries[0][ppm_field] = 0

    with pytest.raises(D02AuthorityError, match="supported projection union"):
        d02_authority.validate_morphology_projection(projection, raw=raw)


_SOURCE_ENTRY_DIGEST_FIELDS = (
    "source_authority_key",
    "source_admission_content_digest",
    "source_asset_sha256",
    "source_receipt_digest",
    "source_authority_digest",
    "source_qa_snapshot_digest",
    "source_landmark_digest",
    "source_measurement_digest",
    "source_provenance_digest",
    "source_fact_snapshot_digest",
    "raw_measurement_authority_digest",
    "source_measurement_projection_digest",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
    "measurement_config_digest",
    "measurement_quality_config_digest",
    "measurement_quality_manifest_content_digest",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "source_repeat_certification_digest",
    "import_config_digest",
)


@pytest.mark.parametrize("field", _SOURCE_ENTRY_DIGEST_FIELDS)
def test_source_manifest_rejects_fully_resigned_malformed_digest(field: str) -> None:
    _, _, entry = _facts_identity_manifest()
    entry[field] = "not-a-digest"
    _resign_source_entry(entry)

    with pytest.raises(D02AuthorityError, match="lowercase SHA-256 digest"):
        validate_source_manifest_entry(entry)


@pytest.mark.parametrize("field", ["source_admission_event_id", "source_asset_id"])
def test_source_manifest_rejects_fully_resigned_malformed_id(field: str) -> None:
    _, _, entry = _facts_identity_manifest()
    entry[field] = "not-an-id"
    _resign_source_entry(entry)

    with pytest.raises(D02AuthorityError, match="lowercase hexadecimal ID"):
        validate_source_manifest_entry(entry)


@pytest.mark.parametrize("invalid", [0, 5, True, 2_147_483_648])
def test_source_manifest_rejects_invalid_source_ordinal(invalid: object) -> None:
    _, _, entry = _facts_identity_manifest()
    entry["source_ordinal"] = invalid
    _resign_source_entry(entry)

    with pytest.raises(
        D02AuthorityError, match=r"ordinal must be an integer|unlisted persisted Boolean"
    ):
        validate_source_manifest_entry(entry)


def test_source_manifest_builder_and_aggregate_reject_malformed_scalar_authority() -> None:
    _, _, entry = _facts_identity_manifest()
    fields = {
        key: deepcopy(value)
        for key, value in entry.items()
        if key not in {"schema_version", "record_digest"}
    }
    fields["source_authority_digest"] = "not-a-digest"
    with pytest.raises(D02AuthorityError, match="lowercase SHA-256 digest"):
        build_source_manifest_entry(fields)

    entries = [entry]
    for ordinal, marker in enumerate(("2", "3", "4"), start=2):
        _, _, peer = _facts_identity_manifest(source_ordinal=ordinal, source_marker=marker)
        entries.append(peer)
    entries = _ordered_source_entries(entries)
    entries[0]["source_authority_digest"] = "not-a-digest"
    _resign_source_entry(entries[0])
    with pytest.raises(D02AuthorityError, match="lowercase SHA-256 digest"):
        digest_source_manifest(entries)


_SOURCE_M3_DIGEST_FIELDS = (
    "source_authority_key",
    "source_asset_sha256",
    "execution_receipt_digest",
    "vision_model_manifest_digest",
    "runtime_manifest_digest",
    "topology_digest",
    "canonical_output_digest",
    "landmark_digest",
    "measurement_observation_digest",
)


def _build_source_m3_from_test_input(
    *,
    observation: dict[str, Any],
    certificate: dict[str, Any],
    source_manifest_entries: list[dict[str, Any]],
    source_entry: dict[str, Any],
    source_manifest_digest: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        build_source_m3_record(
            fields,
            source_manifest_entries=source_manifest_entries,
            source_entry=source_entry,
            certificate=certificate,
            facts_observation=observation,
            source_manifest_digest=source_manifest_digest,
        ),
    )


@pytest.mark.parametrize(
    "field", ["source_m3_record_id", "source_admission_event_id", "source_asset_id"]
)
def test_source_m3_builder_rejects_malformed_id(field: str) -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    fields[field] = "not-an-id"

    with pytest.raises(D02AuthorityError, match="lowercase hexadecimal ID"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


@pytest.mark.parametrize("field", _SOURCE_M3_DIGEST_FIELDS)
def test_source_m3_builder_rejects_malformed_digest(field: str) -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    fields[field] = "not-a-digest"

    with pytest.raises(D02AuthorityError, match="lowercase SHA-256 digest"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("source_ordinal", 0),
        ("source_ordinal", 5),
        ("source_ordinal", True),
        ("source_ordinal", 2_147_483_648),
        ("repeat_index", 0),
        ("repeat_index", 4),
        ("repeat_index", True),
        ("face_count", -1),
        ("face_count", True),
        ("face_count", 2_147_483_648),
        ("landmark_count", -1),
        ("landmark_count", True),
        ("landmark_count", 2_147_483_648),
    ],
)
def test_source_m3_builder_rejects_invalid_integer_domain(field: str, invalid: object) -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    fields[field] = invalid

    with pytest.raises(D02AuthorityError):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        (field, invalid)
        for field in ("coordinates_finite", "coordinates_in_bounds", "repeat_gate_passed")
        for invalid in ("true", 1, None)
    ],
)
def test_source_m3_builder_rejects_non_boolean_flag(field: str, invalid: object) -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    fields[field] = invalid

    with pytest.raises(D02AuthorityError, match=r"must be a (?:literal )?Boolean"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


@pytest.mark.parametrize(
    "field", ["runtime_manifest_digest", "vision_model_manifest_digest", "topology_digest"]
)
def test_source_m3_builder_rejects_well_formed_unauthorized_runtime(field: str) -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    fields[field] = _digest("9") if fields[field] != _digest("9") else _digest("8")

    with pytest.raises(D02AuthorityError, match="runtime authority does not match observation"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


@pytest.mark.parametrize(
    "field", ["canonical_output_digest", "landmark_digest", "measurement_observation_digest"]
)
def test_source_m3_builder_rejects_well_formed_output_lineage_drift(field: str) -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    fields[field] = _digest("9") if fields[field] != _digest("9") else _digest("8")

    with pytest.raises(D02AuthorityError):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


def test_source_m3_builder_rejects_wrong_embedded_observation() -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    subject = cast(dict[str, Any], observation["subject"])
    fields["measurement_observation"] = _source_observation(
        source_output_id=cast(str, subject["source_output_id"]),
        source_asset_id=cast(str, subject["source_asset_id"]),
        source_asset_sha256=cast(str, subject["source_asset_sha256"]),
        canonical_output_digest=_digest("9"),
        landmark_digest=_digest("8"),
    )

    with pytest.raises(D02AuthorityError, match="embedded observation cross-link"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_ordinal", 2),
        ("source_authority_key", _digest("f")),
        ("source_admission_event_id", _identifier("f")),
        ("source_asset_id", _identifier("f")),
        ("source_asset_sha256", _digest("f")),
    ],
)
def test_source_m3_builder_rejects_source_manifest_authority_drift(
    field: str, replacement: object
) -> None:
    observation, certificate, manifest_entries, source_entry, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    fields[field] = replacement
    fields["source_m3_record_id"] = derive_source_m3_record_id(
        source_manifest_digest=manifest_digest,
        source_authority_key=cast(str, fields["source_authority_key"]),
        source_admission_event_id=cast(str, fields["source_admission_event_id"]),
        source_asset_id=cast(str, fields["source_asset_id"]),
        source_asset_sha256=cast(str, fields["source_asset_sha256"]),
        repeat_index=cast(int, fields["repeat_index"]),
    )

    with pytest.raises(D02AuthorityError):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


def test_source_m3_builder_rejects_valid_source_entry_outside_aggregate_manifest() -> None:
    observation, certificate, manifest_entries, _, manifest_digest, fields = (
        _source_m3_builder_input()
    )
    _, _, foreign_entry = _facts_identity_manifest(source_ordinal=1, source_marker="f")
    for key in (
        "source_ordinal",
        "source_authority_key",
        "source_admission_event_id",
        "source_asset_id",
        "source_asset_sha256",
    ):
        fields[key] = foreign_entry[key]
    fields["source_m3_record_id"] = derive_source_m3_record_id(
        source_manifest_digest=manifest_digest,
        source_authority_key=cast(str, fields["source_authority_key"]),
        source_admission_event_id=cast(str, fields["source_admission_event_id"]),
        source_asset_id=cast(str, fields["source_asset_id"]),
        source_asset_sha256=cast(str, fields["source_asset_sha256"]),
        repeat_index=cast(int, fields["repeat_index"]),
    )

    with pytest.raises(D02AuthorityError, match="exact aggregate-manifest member"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=foreign_entry,
            source_manifest_digest=manifest_digest,
            fields=fields,
        )


def test_source_m3_builder_rejects_malformed_manifest_digest() -> None:
    observation, certificate, manifest_entries, source_entry, _, fields = _source_m3_builder_input()

    with pytest.raises(D02AuthorityError, match="lowercase SHA-256 digest"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest="not-a-digest",
            fields=fields,
        )


def test_source_m3_builder_rejects_fully_resigned_wrong_aggregate_manifest_digest() -> None:
    observation, certificate, manifest_entries, source_entry, _, fields = _source_m3_builder_input()
    replacement = _digest("f")
    fields["source_m3_record_id"] = derive_source_m3_record_id(
        source_manifest_digest=replacement,
        source_authority_key=cast(str, fields["source_authority_key"]),
        source_admission_event_id=cast(str, fields["source_admission_event_id"]),
        source_asset_id=cast(str, fields["source_asset_id"]),
        source_asset_sha256=cast(str, fields["source_asset_sha256"]),
        repeat_index=cast(int, fields["repeat_index"]),
    )

    with pytest.raises(D02AuthorityError, match="aggregate source-manifest digest"):
        _build_source_m3_from_test_input(
            observation=observation,
            certificate=certificate,
            source_manifest_entries=manifest_entries,
            source_entry=source_entry,
            source_manifest_digest=replacement,
            fields=fields,
        )


@pytest.mark.parametrize("field", _SOURCE_M3_DIGEST_FIELDS)
def test_source_m3_rejects_fully_resigned_malformed_digest(field: str) -> None:
    observation, certificate, records, manifest_digest = _source_m3_records()
    records[0][field] = "not-a-digest"
    _resign_source_m3_record(records[0])

    with pytest.raises(D02AuthorityError, match="lowercase SHA-256 digest"):
        validate_source_m3_record(
            records[0],
            certificate=certificate,
            facts_observation=observation,
            source_manifest_digest=manifest_digest,
        )


@pytest.mark.parametrize(
    "field", ["source_m3_record_id", "source_admission_event_id", "source_asset_id"]
)
def test_source_m3_rejects_fully_resigned_malformed_id(field: str) -> None:
    observation, certificate, records, manifest_digest = _source_m3_records()
    records[0][field] = "not-an-id"
    _resign_source_m3_record(records[0])

    with pytest.raises(D02AuthorityError, match="lowercase hexadecimal ID"):
        validate_source_m3_record(
            records[0],
            certificate=certificate,
            facts_observation=observation,
            source_manifest_digest=manifest_digest,
        )


@pytest.mark.parametrize("invalid", [0, 5, True, 2_147_483_648])
def test_source_m3_rejects_invalid_source_ordinal(invalid: object) -> None:
    observation, certificate, records, manifest_digest = _source_m3_records()
    records[0]["source_ordinal"] = invalid
    _resign_source_m3_record(records[0])

    with pytest.raises(
        D02AuthorityError, match=r"ordinal must be an integer|unlisted persisted Boolean"
    ):
        validate_source_m3_record(
            records[0],
            certificate=certificate,
            facts_observation=observation,
            source_manifest_digest=manifest_digest,
        )


def test_source_m3_certificate_repeat_and_observation_crosslinks() -> None:
    observation, certificate, records, manifest_digest = _source_m3_records()
    for record in records:
        validate_source_m3_record(
            record,
            certificate=certificate,
            facts_observation=observation,
            source_manifest_digest=manifest_digest,
        )
    forged = deepcopy(records[1])
    forged["repeat_index"] = 1
    with pytest.raises(D02AuthorityError, match="record ID"):
        validate_source_m3_record(
            forged,
            certificate=certificate,
            facts_observation=observation,
            source_manifest_digest=manifest_digest,
        )


def test_facts_v3_exact_keys_digest_and_complete_source_graph() -> None:
    facts, identity, entry = _facts_identity_manifest()
    validate_facts(facts)
    validate_identity_row(identity, facts=facts)
    validate_source_manifest_entry(entry)
    manifest_entries = [entry]
    for ordinal, char in enumerate(("2", "3", "4"), start=2):
        _, _, peer = _facts_identity_manifest(source_ordinal=ordinal, source_marker=char)
        manifest_entries.append(peer)
    manifest_entries = _ordered_source_entries(manifest_entries)
    entry = next(
        item
        for item in manifest_entries
        if item["source_authority_key"] == identity["source_authority_key"]
    )
    manifest_digest = digest_source_manifest(manifest_entries)
    assert manifest_digest == _source_manifest_digest_oracle(manifest_entries)
    observation = cast(dict[str, Any], facts["source_measurement_observation"])
    certificate = cast(dict[str, Any], facts["source_repeat_certification"])
    _, _, records, _ = _source_m3_records(
        manifest_digest,
        source_manifest_entries=manifest_entries,
        observation=observation,
        certificate=certificate,
        source_entry=entry,
    )
    validate_complete_source_graph(
        facts=facts,
        identity_row=identity,
        source_entry=entry,
        source_manifest_digest=manifest_digest,
        source_records=records,
    )
    assert facts["source_measurement_digest"] == observation["measurement_observation_digest"]
    assert facts["source_measurement_digest"] != facts["raw_measurement_authority_digest"]
    assert (
        certificate["source_repeat_certification_digest"]
        == facts["source_repeat_certification_digest"]
    )


@pytest.mark.parametrize("field", ["canonical_output_digest", "landmark_digest"])
def test_source_certificate_observation_digest_lineage_fails_closed(field: str) -> None:
    observation = _source_observation()
    certificate = _source_certificate(observation)
    for binding in cast(list[dict[str, Any]], certificate["ordered_repeat_bindings"]):
        binding[field] = _digest("9")
    _resign_source_certificate(certificate)

    with pytest.raises(D02AuthorityError, match="digest lineage does not match observation"):
        build_raw_measurement_authority(
            observation,
            certificate,
            source_p2_candidate_manifest_content_digest=_digest("1"),
            dimension_authority_manifest_content_digest=_digest("2"),
        )


@pytest.mark.parametrize("field", ["repeat_index", "face_count"])
def test_source_certificate_integer_fields_reject_boolean_coercion(field: str) -> None:
    certificate = _source_certificate(_source_observation())
    bindings = cast(list[dict[str, Any]], certificate["ordered_repeat_bindings"])
    bindings[0][field] = True
    _resign_source_certificate(certificate)

    with pytest.raises(
        D02AuthorityError, match=r"structural precondition|unlisted persisted Boolean"
    ):
        validate_source_certificate(certificate)


@pytest.mark.parametrize("field", ["canonical_output_digest", "landmark_digest"])
def test_complete_source_graph_rejects_fully_resigned_certificate_observation_split(
    field: str,
) -> None:
    entries, packets, _, _ = _complete_source_packets()
    packet = deepcopy(packets[0])
    facts = cast(dict[str, Any], packet["facts"])
    identity = cast(dict[str, Any], packet["identity_row"])
    entry = cast(dict[str, Any], packet["source_entry"])
    observation = cast(dict[str, Any], facts["source_measurement_observation"])
    certificate = cast(dict[str, Any], facts["source_repeat_certification"])
    for binding in cast(list[dict[str, Any]], certificate["ordered_repeat_bindings"]):
        binding[field] = _digest("9")
    _resign_source_certificate(certificate)

    raw = cast(dict[str, Any], facts["raw_measurement_authority"])
    projection = cast(dict[str, Any], facts["source_measurement_projection"])
    raw["source_repeat_certification_digest"] = certificate["source_repeat_certification_digest"]
    projection["source_repeat_certification_digest"] = certificate[
        "source_repeat_certification_digest"
    ]
    raw_digest = digest_raw_measurement_authority(raw)
    projection_digest = digest_morphology_projection(projection)
    facts["source_repeat_certification_digest"] = certificate["source_repeat_certification_digest"]
    facts["raw_measurement_authority_digest"] = raw_digest
    facts["source_measurement_projection_digest"] = projection_digest
    facts_digest = mirror_demo_digest("mirror.demo/RecoveredSyntheticIdentityFacts/v3", facts)

    identity["source_fact_snapshot"] = facts
    identity["source_fact_snapshot_digest"] = facts_digest
    identity["source_measurement_projection"] = projection
    identity["source_measurement_projection_digest"] = projection_digest
    _resign_identity(identity)
    entry["source_admission_event_id"] = identity["id"]
    entry["source_admission_content_digest"] = identity["content_digest"]
    entry["source_fact_snapshot_digest"] = facts_digest
    entry["raw_measurement_authority_digest"] = raw_digest
    entry["source_measurement_projection_digest"] = projection_digest
    entry["source_repeat_certification_digest"] = certificate["source_repeat_certification_digest"]
    _resign_source_entry(entry)

    mutated_entries = [
        entry if item["source_authority_key"] == entry["source_authority_key"] else item
        for item in deepcopy(entries)
    ]
    mutated_entries = _ordered_source_entries(mutated_entries)
    entry = next(
        item
        for item in mutated_entries
        if item["source_authority_key"] == identity["source_authority_key"]
    )
    manifest_digest = digest_source_manifest(mutated_entries)
    _, _, records, _ = _source_m3_records(
        manifest_digest,
        observation=observation,
        certificate=certificate,
        source_entry=entry,
        use_authority_builder=False,
    )
    with pytest.raises(D02AuthorityError, match="digest lineage does not match observation"):
        validate_complete_source_graph(
            facts=facts,
            identity_row=identity,
            source_entry=entry,
            source_manifest_digest=manifest_digest,
            source_records=records,
        )


@pytest.mark.parametrize(
    "field",
    ["runtime_manifest_digest", "vision_model_manifest_digest", "topology_digest"],
)
def test_complete_source_graph_rejects_fully_resigned_source_m3_runtime_drift(
    field: str,
) -> None:
    _, packets, _, _ = _complete_source_packets()
    packet = packets[0]
    records = deepcopy(cast(list[dict[str, Any]], packet["source_records"]))
    records[0][field] = _digest("9")
    _resign_source_m3_record(records[0])

    with pytest.raises(D02AuthorityError, match="runtime authority does not match observation"):
        validate_complete_source_graph(
            facts=cast(dict[str, Any], packet["facts"]),
            identity_row=cast(dict[str, Any], packet["identity_row"]),
            source_entry=cast(dict[str, Any], packet["source_entry"]),
            source_manifest_digest=cast(str, packet["source_manifest_digest"]),
            source_records=records,
        )


@pytest.mark.parametrize(
    ("admission_sequence", "admission_action"),
    [(2, "REVOKE"), (3, "ADMIT")],
)
def test_complete_source_graph_rejects_resigned_noninitial_admission_event(
    admission_sequence: int, admission_action: str
) -> None:
    facts, identity, entry = _facts_identity_manifest()
    forged_identity = deepcopy(identity)
    forged_identity["admission_sequence"] = admission_sequence
    forged_identity["admission_action"] = admission_action
    forged_identity["supersedes_id"] = _identifier("9")
    _resign_identity(forged_identity)
    forged_entry = deepcopy(entry)
    forged_entry["source_admission_event_id"] = forged_identity["id"]
    forged_entry["source_admission_content_digest"] = forged_identity["content_digest"]
    _resign_source_entry(forged_entry)
    manifest_entries = [forged_entry]
    for ordinal, marker in enumerate(("2", "3", "4"), start=2):
        _, _, peer = _facts_identity_manifest(source_ordinal=ordinal, source_marker=marker)
        manifest_entries.append(peer)
    manifest_entries = _ordered_source_entries(manifest_entries)
    forged_entry = next(
        item
        for item in manifest_entries
        if item["source_authority_key"] == forged_identity["source_authority_key"]
    )
    manifest_digest = digest_source_manifest(manifest_entries)
    _, _, records, _ = _source_m3_records(
        manifest_digest,
        source_manifest_entries=manifest_entries,
        observation=cast(dict[str, Any], facts["source_measurement_observation"]),
        certificate=cast(dict[str, Any], facts["source_repeat_certification"]),
        source_entry=forged_entry,
    )
    with pytest.raises(D02AuthorityError, match="self-contained first ADMIT"):
        validate_complete_source_graph(
            facts=facts,
            identity_row=forged_identity,
            source_entry=forged_entry,
            source_manifest_digest=manifest_digest,
            source_records=records,
        )


def test_facts_identity_manifest_exact_key_alias_and_null_matrix_fail_closed() -> None:
    facts, identity, entry = _facts_identity_manifest()
    facts_tampered = deepcopy(facts)
    facts_tampered["source_measurement_observation_alias"] = facts_tampered[
        "source_measurement_observation_digest"
    ]
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_facts(facts_tampered)
    identity_tampered = deepcopy(identity)
    identity_tampered["formal_synthetic_identity_id"] = _identifier("9")
    _resign_identity(identity_tampered)
    with pytest.raises(D02AuthorityError, match="null matrix"):
        validate_identity_row(identity_tampered, facts=facts)
    entry_tampered = deepcopy(entry)
    entry_tampered["measurement_observation_digest"] = facts[
        "source_measurement_observation_digest"
    ]
    _resign_source_entry(entry_tampered)
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_source_manifest_entry(entry_tampered)


@pytest.mark.parametrize("mutation", ["missing", "extra", "renamed"])
def test_facts_v3_exact_keys_reject_recomputed_outer_digest(mutation: str) -> None:
    facts, _, _ = _facts_identity_manifest()
    tampered = deepcopy(facts)
    if mutation == "missing":
        tampered.pop("source_repeat_certification_digest")
    elif mutation == "extra":
        tampered["unfrozen_alias"] = _digest("9")
    else:
        tampered["renamed_source_measurement_digest"] = tampered.pop("source_measurement_digest")
    with pytest.raises(D02AuthorityError, match="exact keys"):
        digest_facts(tampered)


@pytest.mark.parametrize("mutation", ["missing", "extra", "renamed"])
def test_source_manifest_v3_exact_keys_reject_resigned_entry_and_manifest(
    mutation: str,
) -> None:
    _, _, entry = _facts_identity_manifest()
    tampered = deepcopy(entry)
    if mutation == "missing":
        tampered.pop("source_repeat_certification_digest")
    elif mutation == "extra":
        tampered["unfrozen_alias"] = _digest("9")
    else:
        tampered["renamed_source_measurement_digest"] = tampered.pop("source_measurement_digest")
    _resign_source_entry(tampered)
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_source_manifest_entry(tampered)


def test_source_manifest_digest_matches_array_authority_and_rejects_invalid_order() -> None:
    entries = [entry for _, _, entry in _independent_source_chains()]
    assert digest_source_manifest(entries) == _source_manifest_digest_oracle(entries)

    reversed_entries = list(reversed(deepcopy(entries)))
    for ordinal, entry in enumerate(reversed_entries, start=1):
        entry["source_ordinal"] = ordinal
        _resign_source_entry(entry)
    with pytest.raises(D02AuthorityError, match="strictly ascending"):
        digest_source_manifest(reversed_entries)

    duplicate_key_entries = deepcopy(entries)
    duplicate_key_entries[1] = deepcopy(duplicate_key_entries[0])
    duplicate_key_entries[1]["source_admission_event_id"] = _identifier("f")
    duplicate_key_entries[1]["source_admission_content_digest"] = _digest("f")
    duplicate_key_entries = _ordered_source_entries(duplicate_key_entries)
    with pytest.raises(D02AuthorityError, match="duplicate source authority key"):
        digest_source_manifest(duplicate_key_entries)


def test_pure_legacy_nonmutation_mixed_version_and_admit_revoke_copy() -> None:
    facts, admit, entry = _facts_identity_manifest()
    legacy_snapshot = {"schema_version": "mirror.demo/DemoSyntheticIdentity/v2", "payload": [1]}
    before = deepcopy(legacy_snapshot)
    validate_facts(facts)
    assert legacy_snapshot == before  # Pure evidence only; not a database claim.
    mixed = deepcopy(admit)
    mixed["schema_version"] = "mirror.demo/DemoSyntheticIdentity/v2"
    _resign_identity(mixed)
    with pytest.raises(D02AuthorityError, match="schema"):
        validate_identity_row(mixed, facts=facts)
    revoke_fields = {
        key: value
        for key, value in admit.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest"}
    }
    revoke_fields["admission_action"] = "REVOKE"
    revoke_fields["admission_sequence"] = 2
    revoke_fields["supersedes_id"] = admit["id"]
    revoke = build_identity_row(revoke_fields, facts=facts)
    validate_admit_revoke_copy(admit, revoke)
    tampered = deepcopy(revoke)
    tampered["source_measurement_digest"] = _digest("9")
    _resign_identity(tampered)
    with pytest.raises(D02AuthorityError, match="copy"):
        validate_admit_revoke_copy(admit, tampered)
    assert entry["schema_version"] == "mirror.demo/D02SourceAuthorityManifestEntry/v3"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("string_sequence", "positive integer"),
        ("oversized_sequence", "positive integer"),
        ("invalid_action", "action is invalid"),
        ("first_revoke", "first identity admission event"),
        ("first_supersedes", "first identity admission event"),
        ("later_missing_supersedes", "must supersede a predecessor"),
        ("later_invalid_supersedes", "predecessor ID"),
    ],
)
def test_identity_admission_shape_rejects_resigned_invalid_event(
    mutation: str, expected: str
) -> None:
    facts, admit, _ = _facts_identity_manifest()
    tampered = deepcopy(admit)
    if mutation == "string_sequence":
        tampered["admission_sequence"] = "1"
    elif mutation == "oversized_sequence":
        tampered["admission_sequence"] = 2_147_483_648
    elif mutation == "invalid_action":
        tampered["admission_action"] = "INVALID_ACTION"
    elif mutation == "first_revoke":
        tampered["admission_action"] = "REVOKE"
    elif mutation == "first_supersedes":
        tampered["supersedes_id"] = _identifier("9")
    elif mutation == "later_missing_supersedes":
        tampered["admission_sequence"] = 2
        tampered["admission_action"] = "REVOKE"
    else:
        tampered["admission_sequence"] = 2
        tampered["admission_action"] = "REVOKE"
        tampered["supersedes_id"] = "not-an-id"
    _resign_identity(tampered)
    with pytest.raises(D02AuthorityError, match=expected):
        validate_identity_row(tampered, facts=facts)


@pytest.mark.parametrize("mutation", ["sequence_gap", "wrong_predecessor"])
def test_admit_revoke_copy_rejects_resigned_broken_predecessor_link(mutation: str) -> None:
    facts, admit, _ = _facts_identity_manifest()
    revoke_fields = {
        key: value
        for key, value in admit.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest"}
    }
    revoke_fields["admission_action"] = "REVOKE"
    revoke_fields["admission_sequence"] = 2
    revoke_fields["supersedes_id"] = admit["id"]
    revoke = cast(dict[str, Any], build_identity_row(revoke_fields, facts=facts))
    if mutation == "sequence_gap":
        revoke["admission_sequence"] = 3
    else:
        revoke["supersedes_id"] = _identifier("9")
    _resign_identity(revoke)
    validate_identity_row(revoke, facts=facts)
    with pytest.raises(D02AuthorityError, match="immediate alternating successor"):
        validate_admit_revoke_copy(admit, revoke)


def test_result_m3_certificate_gate_and_acyclic_record_ids() -> None:
    observation, records = _result_m3_records()
    source_authority = _facts_identity_manifest()[2]
    for record in records:
        validate_result_m3_record(record)
    forged = deepcopy(records[0])
    forged["result_m3_record_id"] = _identifier("9")
    with pytest.raises(D02AuthorityError, match="ID preimage"):
        validate_result_m3_record(forged)
    certificate = build_result_repeat_certification(
        subject=cast(dict[str, object], observation["subject"]),
        bindings=default_authority_bindings(),
        result_m3_records=records,
    )
    validate_result_certificate(certificate, records)
    drift = deepcopy(records)
    drift_fields = {
        key: value
        for key, value in drift[0].items()
        if key not in {"schema_version", "record_digest"}
    }
    drift_fields["execution_receipt_digest"] = _digest("8")
    drift[0] = cast(dict[str, Any], build_result_m3_record(drift_fields))
    with pytest.raises(D02AuthorityError, match="semantic tuple"):
        validate_result_certificate(certificate, drift)
    gate = _gate_from_records(observation, records)
    validate_measurement_gate(
        gate, result_records=records, source_measurement_authority=source_authority
    )
    invalid_direction = deepcopy(gate)
    invalid_direction["requested_direction"] = "WIDEN"
    _resign_gate(invalid_direction)
    with pytest.raises(D02AuthorityError, match="requested direction"):
        validate_measurement_gate(
            invalid_direction, result_records=records, source_measurement_authority=source_authority
        )
    tampered = deepcopy(gate)
    measurements = cast(list[dict[str, Any]], tampered["ordered_result_repeat_measurements"])
    measurements[0]["result_m3_record_digest"] = _digest("9")
    with pytest.raises(D02AuthorityError, match="record binding"):
        validate_measurement_gate(
            tampered, result_records=records, source_measurement_authority=source_authority
        )


def test_report_v2_exact_groups_and_digest_content_separation() -> None:
    report, packets, variant_bindings = _complete_report_fixture(passing=True)
    validate_report_row(
        report,
        source_graph_packets=packets,
        result_variant_bindings=variant_bindings,
    )
    assert report["report_digest"] != report["content_digest"]
    assert set(report["report_payload"]) == set(REPORT_GROUPS)
    assert report["status"] == "PASSED"
    assert report["selected_pair_count"] == 16


def test_report_payload_self_authority_and_failed_nullability_fail_closed() -> None:
    report, packets, variant_bindings = _complete_report_fixture(passing=False)
    report["report_payload"]["report_digest"] = _digest("c")
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_report_row(
            report,
            source_graph_packets=packets,
            result_variant_bindings=variant_bindings,
        )
    clean, packets, variant_bindings = _complete_report_fixture(passing=True)
    fields = {
        key: deepcopy(value)
        for key, value in clean.items()
        if key
        not in {"id", "schema_version", "canonical_payload", "content_digest", "report_digest"}
    }
    cast(dict[str, Any], fields["report_payload"])["pair_quality_evidence"] = []
    with pytest.raises(D02AuthorityError, match="empty evidence"):
        build_report_row(
            fields,
            source_graph_packets=packets,
            result_variant_bindings=variant_bindings,
        )
    passed, packets, variant_bindings = _complete_report_fixture(passing=True)
    invalid = deepcopy(passed)
    invalid["selected_pair_manifest_digest"] = None
    with pytest.raises(D02AuthorityError):
        validate_report_row(
            invalid,
            source_graph_packets=packets,
            result_variant_bindings=variant_bindings,
        )


def test_resigned_false_green_inner_shapes_and_observation_unions_fail_closed() -> None:
    observation, records = _result_m3_records()
    source_authority = _facts_identity_manifest()[2]
    gate = _gate_from_records(observation, records)
    malformed = deepcopy(gate)
    del malformed["ordered_result_repeat_measurements"][0]["winning_control_ordinal"]
    _resign_gate(malformed)
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_measurement_gate(
            malformed, result_records=records, source_measurement_authority=source_authority
        )

    unsupported = _source_observation()
    entry = unsupported["ordered_measurements"][0]
    entry["support_state"] = "UNSUPPORTED"
    entry["raw_value_fixed18"] = "0.100000000000000000"
    entry["observability_state"] = "NOT_COMPUTABLE"
    entry["raw_observability_fixed18"] = None
    entry["unsupported_reason"] = "MISSING_MEASUREMENT"
    _resign_observation(unsupported)
    with pytest.raises(D02AuthorityError, match="unsupported observation union"):
        validate_measurement_observation(unsupported)


def test_resigned_raw_and_source_graph_semantic_drift_fail_closed() -> None:
    observation = _source_observation()
    certificate = _source_certificate(observation)
    raw = build_raw_measurement_authority(
        observation,
        certificate,
        source_p2_candidate_manifest_content_digest=_digest("1"),
        dimension_authority_manifest_content_digest=_digest("2"),
    )
    raw_entries = cast(list[dict[str, Any]], raw["ordered_entries"])
    raw_entries[0]["raw_value_fixed18"] = "1.000001000000000000"
    with pytest.raises(D02AuthorityError, match="exceeds one"):
        validate_facts(_facts_identity_manifest()[0] | {"raw_measurement_authority": raw})
    raw_unsupported = deepcopy(
        build_raw_measurement_authority(
            observation,
            certificate,
            source_p2_candidate_manifest_content_digest=_digest("1"),
            dimension_authority_manifest_content_digest=_digest("2"),
        )
    )
    raw_unsupported_entries = cast(list[dict[str, Any]], raw_unsupported["ordered_entries"])
    raw_unsupported_entries[0] = {
        "dimension_key": "cheekbone_width",
        "support_state": "UNSUPPORTED",
        "raw_value_fixed18": None,
        "raw_confidence_fixed18": None,
        "raw_reliability_fixed18": None,
        "unsupported_reason": None,
    }
    with pytest.raises(D02AuthorityError, match="unsupported raw authority union"):
        validate_facts(
            _facts_identity_manifest()[0] | {"raw_measurement_authority": raw_unsupported}
        )

    facts, identity, entry = _facts_identity_manifest()
    entries = [entry]
    for ordinal, char in enumerate(("2", "3", "4"), start=2):
        _, _, peer = _facts_identity_manifest(source_ordinal=ordinal, source_marker=char)
        entries.append(peer)
    entries = _ordered_source_entries(entries)
    entry = next(
        item for item in entries if item["source_authority_key"] == identity["source_authority_key"]
    )
    manifest_digest = digest_source_manifest(entries)
    _, _, records, _ = _source_m3_records(
        manifest_digest,
        source_manifest_entries=entries,
        observation=cast(dict[str, Any], facts["source_measurement_observation"]),
        certificate=cast(dict[str, Any], facts["source_repeat_certification"]),
        source_entry=entry,
    )
    drift = deepcopy(entry)
    drift["source_receipt_digest"] = _digest("9")
    _resign_source_entry(drift)
    with pytest.raises(D02AuthorityError, match=r"local authority shape|scalar authority equality"):
        validate_complete_source_graph(
            facts=facts,
            identity_row=identity,
            source_entry=drift,
            source_manifest_digest=manifest_digest,
            source_records=records,
        )


def test_report_rejects_one_empty_group_after_outer_digest_replay() -> None:
    report, packets, variant_bindings = _complete_report_fixture(passing=True)
    fields = {
        key: deepcopy(value)
        for key, value in report.items()
        if key
        not in {"id", "schema_version", "canonical_payload", "content_digest", "report_digest"}
    }
    cast(dict[str, Any], fields["report_payload"])["pair_quality_evidence"] = []
    with pytest.raises(D02AuthorityError, match="empty evidence"):
        build_report_row(
            fields,
            source_graph_packets=packets,
            result_variant_bindings=variant_bindings,
        )


def test_schema_policy_rejects_empty_measurement_config() -> None:
    binding = {
        "schema_version": "mirror.demo/D02SchemaAndPolicyBinding/v2",
        "source_manifest_digest": _digest("1"),
        "case_manifest_digest": _digest("2"),
        "screening_policy_digest": SCREENING_POLICY_DIGEST,
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
        "measurement_execution_config": {},
        "measurement_config_digest": MEASUREMENT_CONFIG_DIGEST,
        "measurement_quality_config_digest": QUALITY_CONFIG_DIGEST,
        "measurement_quality_manifest_content_digest": QUALITY_MANIFEST_DIGEST,
        "confidence_kind": CONFIDENCE_KIND,
        "reliability_kind": RELIABILITY_KIND,
        "manual_review_policy_digest": _digest("4"),
        "duplicate_policy_digest": _digest("5"),
        "phash_implementation_digest": _digest("6"),
    }
    with pytest.raises(D02AuthorityError, match="exact measurement execution config"):
        validate_schema_and_policy_binding(binding)


@pytest.mark.parametrize("mutation", ["missing", "extra", "renamed"])
def test_exact_key_missing_extra_renamed_fails_closed(mutation: str) -> None:
    observation = _source_observation()
    if mutation == "missing":
        observation.pop("landmark_digest")
    elif mutation == "extra":
        observation["alias"] = "no"
    else:
        observation["renamed_landmark_digest"] = observation.pop("landmark_digest")
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_measurement_observation(observation)


def test_canonical_authority_rejects_float_decimal_bytes_and_negative_zero() -> None:
    observation = _source_observation()
    observation["ordered_measurements"][0]["raw_value_fixed18"] = "-0.000000000000000000"
    with pytest.raises(D02AuthorityError):
        validate_measurement_observation(observation)
    bindings = AuthorityBindings(
        runtime_manifest_digest="0" * 64,
        vision_model_manifest_digest="1" * 64,
        topology_digest="2" * 64,
    )
    assert bindings != default_authority_bindings()


def _independent_source_chains(
    *,
    source_p2_manifest_digest: str = _ACCEPTED_SOURCE_P2_MANIFEST_DIGEST,
    dimension_authority_manifest_digest: str = _ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST,
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """Build independent source DAGs, then assign ordinals by the frozen authority order."""
    provisional = [
        _facts_identity_manifest(
            source_ordinal=1,
            source_marker=marker,
            source_p2_manifest_digest=source_p2_manifest_digest,
            dimension_authority_manifest_digest=dimension_authority_manifest_digest,
        )
        for marker in ("a", "b", "c", "d")
    ]
    authority_by_key = {
        entry["source_authority_key"]: (facts, identity) for facts, identity, entry in provisional
    }
    ordered_entries = _ordered_source_entries([entry for _, _, entry in provisional])
    return [(*authority_by_key[entry["source_authority_key"]], entry) for entry in ordered_entries]


def _case_sources(
    *,
    source_p2_manifest_digest: str = _ACCEPTED_SOURCE_P2_MANIFEST_DIGEST,
    dimension_authority_manifest_digest: str = _ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST,
) -> list[dict[str, Any]]:
    return [
        entry
        for _, _, entry in _independent_source_chains(
            source_p2_manifest_digest=source_p2_manifest_digest,
            dimension_authority_manifest_digest=dimension_authority_manifest_digest,
        )
    ]


def _complete_case_sources(
    *,
    source_p2_manifest_digest: str = _ACCEPTED_SOURCE_P2_MANIFEST_DIGEST,
    dimension_authority_manifest_digest: str = _ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST,
) -> tuple[list[dict[str, Any]], str]:
    entries, _, _, manifest_digest = _complete_source_packets(
        source_p2_manifest_digest=source_p2_manifest_digest,
        dimension_authority_manifest_digest=dimension_authority_manifest_digest,
    )
    return entries, manifest_digest


def _complete_source_packets(
    *,
    source_p2_manifest_digest: str = _ACCEPTED_SOURCE_P2_MANIFEST_DIGEST,
    dimension_authority_manifest_digest: str = _ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
]:
    chains = _independent_source_chains(
        source_p2_manifest_digest=source_p2_manifest_digest,
        dimension_authority_manifest_digest=dimension_authority_manifest_digest,
    )
    entries = [entry for _, _, entry in chains]
    manifest_digest = digest_source_manifest(entries)
    packets: list[dict[str, Any]] = []
    all_records: list[dict[str, Any]] = []
    for facts, identity, entry in chains:
        observation = cast(dict[str, Any], facts["source_measurement_observation"])
        certificate = cast(dict[str, Any], facts["source_repeat_certification"])
        _, _, records, _ = _source_m3_records(
            manifest_digest,
            source_manifest_entries=entries,
            observation=observation,
            certificate=certificate,
            source_entry=entry,
        )
        validate_complete_source_graph(
            facts=facts,
            identity_row=identity,
            source_entry=entry,
            source_manifest_digest=manifest_digest,
            source_records=records,
        )
        packets.append(
            {
                "facts": facts,
                "identity_row": identity,
                "source_entry": entry,
                "source_manifest_digest": manifest_digest,
                "source_records": records,
            }
        )
        all_records.extend(records)
    return entries, packets, all_records, manifest_digest


def _case_execution_authority() -> dict[str, str]:
    return {
        "screening_policy_digest": SCREENING_POLICY_DIGEST,
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
        "measurement_config_digest": MEASUREMENT_CONFIG_DIGEST,
        "manual_review_policy_digest": _digest("2"),
        "duplicate_policy_digest": _digest("3"),
        "phash_implementation_digest": _digest("4"),
    }


def _case_geometry_fields(
    *, geometry_ontology_digest: str = _ACCEPTED_GEOMETRY_ONTOLOGY_DIGEST
) -> dict[str, object]:
    return {
        "geometry_ontology_version_digest": geometry_ontology_digest,
        "warp_plan_digest": _digest("6"),
        "geometry_algorithm_version": "geometry-v1",
        "runtime_config_digest": _digest("7"),
        "output_policy_version": "output-v1",
        "output_width": 1024,
        "output_height": 1024,
        "determinism_level": "STRICT",
    }


def _case_manifest() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    sources = _case_sources()
    authority = _case_execution_authority()
    return (
        build_ordered_case_manifest(
            sources, execution_authority=authority, geometry_fields=_case_geometry_fields()
        ),
        sources,
        authority,
    )


def _resign_case_entry(entry: dict[str, Any]) -> None:
    entry["record_digest"] = mirror_demo_digest(
        "mirror.demo/D02GeometryCaseManifestEntry/v3",
        {
            key: value
            for key, value in entry.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def test_ordered_case_manifest_builds_the_real_frozen_48_case_matrix() -> None:
    entries, sources, authority = _case_manifest()
    digest = validate_ordered_case_manifest(
        entries, source_entries=sources, execution_authority=authority
    )
    assert len(entries) == 48
    assert len({entry["case_id"] for entry in entries}) == 48
    assert entries[0]["case_ordinal"] == 1
    assert entries[-1]["case_ordinal"] == 48
    assert entries[0]["dimension_key"] == "jaw_width"
    assert entries[0]["direction"] == "DECREASE"
    assert entries[0]["magnitude_ppm"] == 15_000
    assert entries[-1]["dimension_key"] == "eye_spacing"
    assert entries[-1]["direction"] == "INCREASE"
    assert entries[-1]["magnitude_ppm"] == 30_000
    assert len(digest) == 64
    validate_ordered_case_manifest(
        entries, source_entries=sources, execution_authority=authority, expected_digest=digest
    )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("order", "natural order"),
        ("duplicate", "ID preimage"),
        ("id", "ID preimage"),
        ("spec", "specification digest"),
        ("record", "record_digest does not replay"),
        ("index", "priority index"),
        ("controls", "control dimensions"),
        ("execution", "execution configuration"),
    ],
)
def test_ordered_case_manifest_resigned_inner_mutations_fail_closed(
    mutation: str, match: str
) -> None:
    entries, sources, authority = _case_manifest()
    forged = deepcopy(entries)
    if mutation == "order":
        forged[0], forged[1] = forged[1], forged[0]
    elif mutation == "duplicate":
        forged[1]["case_id"] = forged[0]["case_id"]
        _resign_case_entry(forged[1])
    elif mutation == "id":
        forged[0]["source_authority_key"] = _digest("f")
        _resign_case_entry(forged[0])
    elif mutation == "spec":
        forged[0]["warp_plan_digest"] = _digest("9")
        _resign_case_entry(forged[0])
    elif mutation == "record":
        forged[0]["record_digest"] = _digest("f")
    elif mutation == "index":
        forged[0]["priority_index"] = 2
        _resign_case_entry(forged[0])
    elif mutation == "controls":
        forged[0]["ordered_control_dimensions"] = ["jaw_width"] * 5
        _resign_case_entry(forged[0])
    else:
        forged[0]["runtime_config_digest"] = _digest("e")
        _resign_case_entry(forged[0])
    with pytest.raises(D02AuthorityError, match=match):
        validate_ordered_case_manifest(
            forged, source_entries=sources, execution_authority=authority
        )


def test_case_manifest_missing_cartesian_item_and_outer_digest_fail_closed() -> None:
    entries, sources, authority = _case_manifest()
    missing = entries[:-1]
    with pytest.raises(D02AuthorityError, match="exactly 48"):
        validate_ordered_case_manifest(
            missing, source_entries=sources, execution_authority=authority
        )
    digest = validate_ordered_case_manifest(
        entries, source_entries=sources, execution_authority=authority
    )
    with pytest.raises(D02AuthorityError, match="manifest digest"):
        validate_ordered_case_manifest(
            entries,
            source_entries=sources,
            execution_authority=authority,
            expected_digest=_digest("0") if digest != _digest("0") else _digest("1"),
        )


def test_case_manifest_entry_exact_v3_keys_fail_closed_after_resigning() -> None:
    entries, _, authority = _case_manifest()
    forged = deepcopy(entries[0])
    forged["alias"] = _digest("a")
    _resign_case_entry(forged)
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_case_manifest_entry(forged, execution_authority=authority)


def _m4_fields(
    case: dict[str, Any], replay_index: int, *, source_entry: dict[str, Any]
) -> dict[str, object]:
    ordinal = case["case_ordinal"]
    return {
        "replay_index": replay_index,
        "source_output_id": source_entry["source_output_id"],
        "result_output_id": mirror_demo_digest("fixture-result-output/v1", {"case": ordinal})[:32],
        "result_sha256": mirror_demo_digest("fixture-result/v1", {"case": ordinal}),
        "result_byte_size": 1024 + ordinal,
        "result_mime_type": "image/jpeg",
        "result_width": 1024,
        "result_height": 1024,
        "changed_pixel_count": ordinal,
        "execution_receipt_digest": mirror_demo_digest(
            "fixture-m4-receipt/v1", {"case": ordinal, "replay": replay_index}
        ),
        "execution_succeeded": True,
    }


def _m4_evidence() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    cases, sources, authority = _case_manifest()
    records: list[dict[str, Any]] = []
    for case in cases:
        source_entry = sources[int(case["source_ordinal"]) - 1]
        for replay_index in (1, 2):
            records.append(
                build_m4_execution_record(
                    _m4_fields(case, replay_index, source_entry=source_entry),
                    case_entry=case,
                    execution_authority=authority,
                )
            )
    return records, cases, sources, authority


def _result_records_for_case(
    case: dict[str, Any],
    m4_first: dict[str, Any],
    *,
    source_entry: dict[str, Any] | None = None,
    passing: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    subject: dict[str, object] = {
        "schema_version": "mirror.demo/D02ResultObservationSubject/v1",
        "case_id": case["case_id"],
        "case_specification_digest": case["case_specification_digest"],
        "result_output_id": m4_first["result_output_id"],
        "result_sha256": m4_first["result_sha256"],
    }
    landmarks = _landmarks()
    observation = cast(
        dict[str, Any],
        build_measurement_observation(
            observation_role="RESULT",
            subject=subject,
            canonical_output_digest=mirror_demo_digest(
                "fixture-result-canonical/v1", {"case_id": case["case_id"]}
            ),
            landmark_digest=mirror_demo_digest(
                "fixture-result-landmarks/v1", {"case_id": case["case_id"]}
            ),
            bindings=default_authority_bindings(),
            measurement_landmarks=landmarks,
            ordered_observability_repeats=[landmarks, landmarks, landmarks],
        ),
    )
    if passing:
        if source_entry is None:
            raise AssertionError("passing result fixture requires source authority")
        result_entries = cast(list[dict[str, Any]], observation["ordered_measurements"])
        source_entries = cast(list[dict[str, Any]], source_entry["ordered_supported_measurements"])
        for result_entry, source_measurement in zip(result_entries, source_entries, strict=True):
            result_entry["raw_value_fixed18"] = source_measurement["raw_value_fixed18"]
        target = next(
            item for item in result_entries if item["dimension_key"] == case["dimension_key"]
        )
        delta = Decimal(case["magnitude_ppm"]) / Decimal(1_000_000)
        if case["direction"] == "DECREASE":
            delta = -delta
        target["raw_value_fixed18"] = _fixed18(
            Decimal(cast(str, target["raw_value_fixed18"])) + delta
        )
        _resign_observation(observation)
    records: list[dict[str, Any]] = []
    for repeat_index in (1, 2, 3):
        records.append(
            cast(
                dict[str, Any],
                build_result_m3_record(
                    {
                        "result_m3_record_id": derive_result_m3_record_id(
                            case_id=subject["case_id"],
                            case_specification_digest=subject["case_specification_digest"],
                            result_output_id=subject["result_output_id"],
                            result_sha256=subject["result_sha256"],
                            repeat_index=repeat_index,
                            bindings=default_authority_bindings(),
                        ),
                        "case_id": subject["case_id"],
                        "case_specification_digest": subject["case_specification_digest"],
                        "result_output_id": subject["result_output_id"],
                        "result_sha256": subject["result_sha256"],
                        "repeat_index": repeat_index,
                        "execution_receipt_digest": mirror_demo_digest(
                            "fixture-result-m3-receipt/v1",
                            {"case_id": case["case_id"], "repeat_index": repeat_index},
                        ),
                        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
                        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
                        "topology_digest": TOPOLOGY_DIGEST,
                        "canonical_output_digest": observation["canonical_output_digest"],
                        "landmark_digest": observation["landmark_digest"],
                        "measurement_observation": observation,
                        "measurement_observation_digest": observation[
                            "measurement_observation_digest"
                        ],
                        "face_count": 1,
                        "landmark_count": 478,
                        "coordinates_finite": True,
                        "coordinates_in_bounds": True,
                        "observation_state": "SUPPORTED",
                        "repeat_gate_passed": True,
                    }
                ),
            )
        )
    return observation, records


def _gate_for_case(
    *,
    case: dict[str, Any],
    peer_case: dict[str, Any],
    source_entry: dict[str, Any],
    observation: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    source_measurements = cast(list[dict[str, Any]], source_entry["ordered_supported_measurements"])
    dimension = cast(str, case["dimension_key"])
    target = deepcopy(
        next(item for item in source_measurements if item["dimension_key"] == dimension)
    )
    controls = [
        deepcopy(item) for item in source_measurements if item["dimension_key"] != dimension
    ]
    result_entries = cast(list[dict[str, Any]], observation["ordered_measurements"])
    result_by_dimension = {item["dimension_key"]: item for item in result_entries}
    result_measurements: list[dict[str, Any]] = []
    for record in records:
        result_target = result_by_dimension[dimension]
        source_target = Decimal(cast(str, target["raw_value_fixed18"]))
        result_target_value = Decimal(cast(str, result_target["raw_value_fixed18"]))
        signed_delta = result_target_value - source_target
        absolute_delta = abs(signed_delta)
        direction_gate = signed_delta > 0 if case["direction"] == "INCREASE" else signed_delta < 0
        target_min_gate = absolute_delta >= Decimal("0.000010000000000000")
        target_max_gate = absolute_delta <= Decimal("0.060000000000000000")
        measured_signed_ppm = int(
            (signed_delta * Decimal(1_000_000)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
        )
        target_absolute_ppm = int(
            (absolute_delta * Decimal(1_000_000)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
        )
        result_measurements.append(
            {
                "schema_version": "mirror.demo/D02SupportedResultMeasurement/v1",
                "repeat_index": record["repeat_index"],
                "result_m3_record_digest": record["record_digest"],
                "raw_result_target_fixed18": result_target["raw_value_fixed18"],
                "raw_signed_target_delta_fixed18": _fixed18(signed_delta),
                "raw_target_absolute_delta_fixed18": _fixed18(absolute_delta),
                "ordered_control_deltas": [
                    {
                        "schema_version": "mirror.demo/D02ControlDelta/v1",
                        "control_ordinal": ordinal,
                        "dimension_key": control["dimension_key"],
                        "raw_source_value_fixed18": control["raw_value_fixed18"],
                        "raw_result_value_fixed18": result_by_dimension[control["dimension_key"]][
                            "raw_value_fixed18"
                        ],
                        "raw_absolute_delta_fixed18": "0.000000000000000000",
                        "drift_ppm": 0,
                    }
                    for ordinal, control in enumerate(controls, start=1)
                ],
                "winning_control_ordinal": 1,
                "max_control_dimension_key": controls[0]["dimension_key"],
                "raw_max_control_drift_fixed18": "0.000000000000000000",
                "measured_signed_delta_ppm": measured_signed_ppm,
                "target_absolute_delta_ppm": target_absolute_ppm,
                "drift_ppm": 0,
                "direction_gate_passed": direction_gate,
                "target_min_gate_passed": target_min_gate,
                "target_max_gate_passed": target_max_gate,
                "control_drift_gate_passed": True,
            }
        )
    certificate = build_result_repeat_certification(
        subject=cast(dict[str, object], observation["subject"]),
        bindings=default_authority_bindings(),
        result_m3_records=records,
    )
    return cast(
        dict[str, Any],
        build_measurement_gate(
            {
                "case_id": case["case_id"],
                "case_specification_digest": case["case_specification_digest"],
                "dimension_key": dimension,
                "requested_direction": case["direction"],
                "requested_magnitude_ppm": case["magnitude_ppm"],
                "monotonicity_peer_case_id": peer_case["case_id"],
                "source_target_measurement": target,
                "ordered_source_control_measurements": controls,
                "ordered_result_repeat_measurements": result_measurements,
                "measurement_evaluation_state": "SUPPORTED_EVALUATED",
                "gate_evaluation": {
                    "schema_version": "mirror.demo/D02SupportedMeasurementGateEvaluation/v1",
                    "direction_gate_passed": all(
                        item["direction_gate_passed"] for item in result_measurements
                    ),
                    "target_min_gate_passed": all(
                        item["target_min_gate_passed"] for item in result_measurements
                    ),
                    "target_max_gate_passed": all(
                        item["target_max_gate_passed"] for item in result_measurements
                    ),
                    "control_drift_gate_passed": True,
                    "magnitude_monotonicity_gate_passed": True,
                    "measurement_gate_passed": all(
                        item["direction_gate_passed"]
                        and item["target_min_gate_passed"]
                        and item["target_max_gate_passed"]
                        and item["control_drift_gate_passed"]
                        for item in result_measurements
                    ),
                },
                "result_repeat_certification": certificate,
                "result_repeat_certification_digest": certificate[
                    "result_repeat_certification_digest"
                ],
            }
        ),
    )


def _resign_result_record(record: dict[str, Any]) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        build_result_m3_record(
            {
                key: value
                for key, value in record.items()
                if key not in {"schema_version", "record_digest"}
            }
        ),
    )


def _resign_gate_for_records(gate: dict[str, Any], records: list[dict[str, Any]]) -> None:
    certificate = build_result_repeat_certification(
        subject=cast(dict[str, object], records[0]["measurement_observation"]["subject"]),
        bindings=default_authority_bindings(),
        result_m3_records=records,
    )
    gate["result_repeat_certification"] = certificate
    gate["result_repeat_certification_digest"] = certificate["result_repeat_certification_digest"]
    measurements = cast(list[dict[str, Any]], gate["ordered_result_repeat_measurements"])
    for measurement, record in zip(measurements, records, strict=True):
        measurement["result_m3_record_digest"] = record["record_digest"]
    _resign_gate(gate)


def _resign_gate_with_unchecked_result_certificate(
    gate: dict[str, Any], records: list[dict[str, Any]]
) -> None:
    """Model a re-signing attacker without using the validating certificate builder."""
    certificate = deepcopy(cast(dict[str, Any], gate["result_repeat_certification"]))
    certificate["ordered_repeat_bindings"] = [
        {
            key: record[key]
            for key in (
                "result_m3_record_id",
                "repeat_index",
                "execution_receipt_digest",
                "canonical_output_digest",
                "landmark_digest",
                "measurement_observation_digest",
                "face_count",
                "landmark_count",
                "coordinates_finite",
                "coordinates_in_bounds",
                "observation_state",
                "repeat_gate_passed",
            )
        }
        for record in records
    ]
    certificate["result_repeat_certification_digest"] = mirror_demo_digest(
        "mirror.demo/D02ResultRepeatDeterminismCertification/v1",
        {
            key: value
            for key, value in certificate.items()
            if key not in {"schema_version", "result_repeat_certification_digest"}
        },
    )
    gate["result_repeat_certification"] = certificate
    gate["result_repeat_certification_digest"] = certificate["result_repeat_certification_digest"]
    measurements = cast(list[dict[str, Any]], gate["ordered_result_repeat_measurements"])
    for measurement, record in zip(measurements, records, strict=True):
        measurement["result_m3_record_digest"] = record["record_digest"]
    _resign_gate(gate)


def _unsupported_case_records_and_gate(
    *,
    case: dict[str, Any],
    records: list[dict[str, Any]],
    gate: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    observation = deepcopy(cast(dict[str, Any], records[0]["measurement_observation"]))
    measurements = cast(list[dict[str, Any]], observation["ordered_measurements"])
    target = next(item for item in measurements if item["dimension_key"] == case["dimension_key"])
    target.update(
        {
            "support_state": "UNSUPPORTED",
            "raw_value_fixed18": None,
            "observability_state": "NOT_COMPUTABLE",
            "raw_observability_fixed18": None,
            "unsupported_reason": "RUNTIME_UNSUPPORTED",
        }
    )
    _resign_observation(observation)

    unsupported_records: list[dict[str, Any]] = []
    for original in records:
        fields = {
            key: deepcopy(value)
            for key, value in original.items()
            if key not in {"schema_version", "record_digest"}
        }
        fields["measurement_observation"] = deepcopy(observation)
        fields["measurement_observation_digest"] = observation["measurement_observation_digest"]
        fields["observation_state"] = "UNSUPPORTED_EXPLICIT"
        fields["repeat_gate_passed"] = False
        unsupported_records.append(cast(dict[str, Any], build_result_m3_record(fields)))

    unsupported_gate = deepcopy(gate)
    unsupported_gate["ordered_result_repeat_measurements"] = [
        {
            "schema_version": "mirror.demo/D02UnsupportedResultMeasurement/v1",
            "repeat_index": record["repeat_index"],
            "result_m3_record_digest": record["record_digest"],
            "unsupported_dimension_key": case["dimension_key"],
            "unsupported_reason": "RUNTIME_UNSUPPORTED",
            "measurement_gate_passed": False,
        }
        for record in unsupported_records
    ]
    unsupported_gate["measurement_evaluation_state"] = "UNSUPPORTED_EXPLICIT"
    unsupported_gate["gate_evaluation"] = {
        "schema_version": "mirror.demo/D02UnsupportedMeasurementGateEvaluation/v1",
        "unsupported_repeat_indexes": [1, 2, 3],
        "ordered_unsupported_reasons": ["RUNTIME_UNSUPPORTED"] * 3,
        "measurement_gate_passed": False,
    }
    _resign_gate_with_unchecked_result_certificate(unsupported_gate, unsupported_records)
    return unsupported_records, unsupported_gate


def _supported_case_records_and_gate_for_delta(
    *,
    case: dict[str, Any],
    peer_case: dict[str, Any],
    source_entry: dict[str, Any],
    records: list[dict[str, Any]],
    gate: dict[str, Any],
    absolute_delta: Decimal,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    observation = deepcopy(cast(dict[str, Any], records[0]["measurement_observation"]))
    measurements = cast(list[dict[str, Any]], observation["ordered_measurements"])
    result_target = next(
        item for item in measurements if item["dimension_key"] == case["dimension_key"]
    )
    source_target = cast(dict[str, Any], gate["source_target_measurement"])
    signed_delta = absolute_delta if case["direction"] == "INCREASE" else -absolute_delta
    result_target["raw_value_fixed18"] = _fixed18(
        Decimal(cast(str, source_target["raw_value_fixed18"])) + signed_delta
    )
    _resign_observation(observation)

    rewritten_records: list[dict[str, Any]] = []
    for original in records:
        fields = {
            key: deepcopy(value)
            for key, value in original.items()
            if key not in {"schema_version", "record_digest"}
        }
        fields["measurement_observation"] = deepcopy(observation)
        fields["measurement_observation_digest"] = observation["measurement_observation_digest"]
        rewritten_records.append(cast(dict[str, Any], build_result_m3_record(fields)))
    rewritten_gate = _gate_for_case(
        case=case,
        peer_case=peer_case,
        source_entry=source_entry,
        observation=observation,
        records=rewritten_records,
    )
    return rewritten_records, rewritten_gate


def _set_supported_gate_monotonicity(gate: dict[str, Any], value: bool) -> None:
    evaluation = cast(dict[str, Any], gate["gate_evaluation"])
    evaluation["magnitude_monotonicity_gate_passed"] = value
    evaluation["measurement_gate_passed"] = value and all(
        cast(bool, evaluation[key])
        for key in (
            "direction_gate_passed",
            "target_min_gate_passed",
            "target_max_gate_passed",
            "control_drift_gate_passed",
        )
    )
    _resign_gate(gate)


def _drift_result_records(
    records: list[dict[str, Any]], *, field: str, value: str, observation_field: bool
) -> list[dict[str, Any]]:
    drifted: list[dict[str, Any]] = []
    for record in records:
        replacement = deepcopy(record)
        if observation_field:
            observation = cast(dict[str, Any], replacement["measurement_observation"])
            subject = cast(dict[str, Any], observation["subject"])
            subject[field] = value
            _resign_observation(observation)
            replacement["measurement_observation_digest"] = observation[
                "measurement_observation_digest"
            ]
            replacement["canonical_output_digest"] = observation["canonical_output_digest"]
            replacement["landmark_digest"] = observation["landmark_digest"]
        replacement[field] = value
        replacement["result_m3_record_id"] = derive_result_m3_record_id(
            case_id=replacement["case_id"],
            case_specification_digest=replacement["case_specification_digest"],
            result_output_id=replacement["result_output_id"],
            result_sha256=replacement["result_sha256"],
            repeat_index=replacement["repeat_index"],
            bindings=default_authority_bindings(),
        )
        drifted.append(_resign_result_record(replacement))
    return drifted


def _full_result_m3_gate_graph() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    return _full_result_m3_gate_graph_with_state(passing=False, duplicate_result_sha=False)


def _full_result_m3_gate_graph_with_state(
    *,
    passing: bool,
    duplicate_result_sha: bool,
    unsupported_case_ordinals: frozenset[int] = frozenset(),
    source_p2_manifest_digest: str = _ACCEPTED_SOURCE_P2_MANIFEST_DIGEST,
    dimension_authority_manifest_digest: str = _ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST,
    geometry_ontology_digest: str = _ACCEPTED_GEOMETRY_ONTOLOGY_DIGEST,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    sources, _ = _complete_case_sources(
        source_p2_manifest_digest=source_p2_manifest_digest,
        dimension_authority_manifest_digest=dimension_authority_manifest_digest,
    )
    authority = _case_execution_authority()
    cases = cast(
        list[dict[str, Any]],
        build_ordered_case_manifest(
            sources,
            execution_authority=authority,
            geometry_fields=_case_geometry_fields(
                geometry_ontology_digest=geometry_ontology_digest
            ),
        ),
    )
    m4_records: list[dict[str, Any]] = []
    first_result_sha: str | None = None
    for case_index, case in enumerate(cases):
        source_entry = sources[int(case["source_ordinal"]) - 1]
        for replay_index in (1, 2):
            fields = _m4_fields(case, replay_index, source_entry=source_entry)
            if duplicate_result_sha and case_index == 1:
                if first_result_sha is None:
                    raise AssertionError("first result SHA fixture is missing")
                fields["result_sha256"] = first_result_sha
            m4_records.append(
                cast(
                    dict[str, Any],
                    build_m4_execution_record(
                        fields,
                        case_entry=case,
                        execution_authority=authority,
                    ),
                )
            )
        if case_index == 0:
            first_result_sha = cast(str, m4_records[0]["result_sha256"])
    result_records: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases):
        source_entry = sources[int(case["source_ordinal"]) - 1]
        observation, records = _result_records_for_case(
            case,
            m4_records[case_index * 2],
            source_entry=source_entry,
            passing=passing,
        )
        result_records.extend(records)
        peer_index = case_index + 1 if case["magnitude_ppm"] == 15_000 else case_index - 1
        gates.append(
            _gate_for_case(
                case=case,
                peer_case=cases[peer_index],
                source_entry=source_entry,
                observation=observation,
                records=records,
            )
        )
    if any(
        type(ordinal) is not int or ordinal < 1 or ordinal > 48
        for ordinal in unsupported_case_ordinals
    ):
        raise AssertionError("unsupported case ordinals must be within the frozen 48-case manifest")
    for ordinal in sorted(unsupported_case_ordinals):
        case_index = ordinal - 1
        replacement_records, replacement_gate = _unsupported_case_records_and_gate(
            case=cases[case_index],
            records=result_records[case_index * 3 : case_index * 3 + 3],
            gate=gates[case_index],
        )
        result_records[case_index * 3 : case_index * 3 + 3] = replacement_records
        gates[case_index] = replacement_gate
    for lower_index in range(0, 48, 2):
        lower_supported = (
            gates[lower_index]["measurement_evaluation_state"] == "SUPPORTED_EVALUATED"
        )
        upper_supported = (
            gates[lower_index + 1]["measurement_evaluation_state"] == "SUPPORTED_EVALUATED"
        )
        if lower_supported != upper_supported:
            supported_gate = gates[lower_index] if lower_supported else gates[lower_index + 1]
            _set_supported_gate_monotonicity(supported_gate, False)
    return sources, cases, m4_records, result_records, gates, authority


def _validate_full_result_m3_gate_graph(
    sources: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    m4_records: list[dict[str, Any]],
    result_records: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    authority: dict[str, str],
) -> None:
    validate_result_m3_gate_cross_graph(
        case_manifest=cases,
        source_entries=sources,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        execution_authority=authority,
    )


def _resign_m4_record(record: dict[str, Any]) -> None:
    record["record_digest"] = mirror_demo_digest(
        "mirror.demo/D02M4ExecutionRecord/v1",
        {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def test_m4_repeat_evidence_derives_the_real_96_record_matrix() -> None:
    records, cases, sources, authority = _m4_evidence()
    validate_m4_repeat_evidence(
        records,
        case_manifest=cases,
        source_entries=sources,
        execution_authority=authority,
    )
    assert len(records) == 96
    assert len({record["m4_execution_record_id"] for record in records}) == 96
    assert records[0]["replay_index"] == 1
    assert records[-1]["replay_index"] == 2


def test_result_m3_gate_cross_graph_accepts_full_independent_positive_fixture() -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    _validate_full_result_m3_gate_graph(
        sources, cases, m4_records, result_records, gates, authority
    )
    assert len(digest_source_manifest(sources)) == 64
    assert len(sources) == 4
    assert len(cases) == 48
    assert len(m4_records) == 96
    assert len(result_records) == 144
    assert len(gates) == 48


@pytest.mark.parametrize(
    ("unsupported_case_ordinal", "supported_case_ordinal"),
    [(1, 2), (2, 1)],
)
def test_result_m3_gate_cross_graph_accepts_both_revision9_mixed_peer_directions(
    unsupported_case_ordinal: int, supported_case_ordinal: int
) -> None:
    sources, cases, m4_records, result_records, gates, authority = (
        _full_result_m3_gate_graph_with_state(
            passing=True,
            duplicate_result_sha=False,
            unsupported_case_ordinals=frozenset({unsupported_case_ordinal}),
        )
    )
    _validate_full_result_m3_gate_graph(
        sources, cases, m4_records, result_records, gates, authority
    )
    unsupported_gate = gates[unsupported_case_ordinal - 1]
    supported_gate = gates[supported_case_ordinal - 1]
    assert unsupported_gate["measurement_evaluation_state"] == "UNSUPPORTED_EXPLICIT"
    assert supported_gate["measurement_evaluation_state"] == "SUPPORTED_EVALUATED"
    assert unsupported_gate["gate_evaluation"] == {
        "schema_version": "mirror.demo/D02UnsupportedMeasurementGateEvaluation/v1",
        "unsupported_repeat_indexes": [1, 2, 3],
        "ordered_unsupported_reasons": ["RUNTIME_UNSUPPORTED"] * 3,
        "measurement_gate_passed": False,
    }
    assert all(
        binding["observation_state"] == "UNSUPPORTED_EXPLICIT"
        and binding["repeat_gate_passed"] is False
        for binding in unsupported_gate["result_repeat_certification"]["ordered_repeat_bindings"]
    )
    assert supported_gate["gate_evaluation"]["magnitude_monotonicity_gate_passed"] is False
    assert supported_gate["gate_evaluation"]["measurement_gate_passed"] is False


@pytest.mark.parametrize(
    ("unsupported_fixture", "forged_state", "forged_repeat_gate"),
    [(False, "UNSUPPORTED_EXPLICIT", False), (True, "SUPPORTED", True)],
)
def test_result_m3_state_must_project_the_embedded_observation_union(
    unsupported_fixture: bool, forged_state: str, forged_repeat_gate: bool
) -> None:
    _, _, _, result_records, _, _ = _full_result_m3_gate_graph_with_state(
        passing=True,
        duplicate_result_sha=False,
        unsupported_case_ordinals=frozenset({1}) if unsupported_fixture else frozenset(),
    )
    forged = deepcopy(result_records[0])
    forged["observation_state"] = forged_state
    forged["repeat_gate_passed"] = forged_repeat_gate
    resigned = _resign_result_record(forged)
    with pytest.raises(D02AuthorityError, match="structural state"):
        validate_result_m3_record(resigned)


@pytest.mark.parametrize("attack", ["true_monotonicity", "fabricated_delta", "wrong_peer"])
def test_revision9_mixed_peer_attacks_fail_closed_after_resigning(attack: str) -> None:
    sources, cases, m4_records, result_records, gates, authority = (
        _full_result_m3_gate_graph_with_state(
            passing=True,
            duplicate_result_sha=False,
            unsupported_case_ordinals=frozenset({2}),
        )
    )
    if attack == "true_monotonicity":
        _set_supported_gate_monotonicity(gates[0], True)
    elif attack == "fabricated_delta":
        unsupported_measurement = gates[1]["ordered_result_repeat_measurements"][0]
        unsupported_measurement["raw_target_absolute_delta_fixed18"] = "0.030000000000000000"
        _resign_gate(gates[1])
    else:
        gates[0]["monotonicity_peer_case_id"] = cases[2]["case_id"]
        _resign_gate(gates[0])
    with pytest.raises(D02AuthorityError):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


def test_revision9_raw_fixed18_monotonicity_precedes_equal_ppm_projection() -> None:
    sources, cases, m4_records, result_records, gates, authority = (
        _full_result_m3_gate_graph_with_state(passing=True, duplicate_result_sha=False)
    )
    deltas = (Decimal("0.015000400000000000"), Decimal("0.015000300000000000"))
    for case_index, delta in enumerate(deltas):
        rewritten_records, rewritten_gate = _supported_case_records_and_gate_for_delta(
            case=cases[case_index],
            peer_case=cases[1 - case_index],
            source_entry=sources[0],
            records=result_records[case_index * 3 : case_index * 3 + 3],
            gate=gates[case_index],
            absolute_delta=delta,
        )
        result_records[case_index * 3 : case_index * 3 + 3] = rewritten_records
        gates[case_index] = rewritten_gate
        _set_supported_gate_monotonicity(gates[case_index], False)
    _validate_full_result_m3_gate_graph(
        sources, cases, m4_records, result_records, gates, authority
    )
    assert {
        measurement["target_absolute_delta_ppm"]
        for gate in gates[:2]
        for measurement in gate["ordered_result_repeat_measurements"]
    } == {15_000}
    assert all(
        gate["gate_evaluation"]["magnitude_monotonicity_gate_passed"] is False for gate in gates[:2]
    )

    forged_gates = deepcopy(gates)
    _set_supported_gate_monotonicity(forged_gates[0], True)
    with pytest.raises(D02AuthorityError, match="monotonicity"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, forged_gates, authority
        )


@pytest.mark.parametrize(
    ("array_name", "operation"),
    [
        ("result", "missing"),
        ("result", "extra"),
        ("gate", "missing"),
        ("gate", "extra"),
        ("m4", "missing"),
        ("m4", "extra"),
        ("source", "missing"),
        ("source", "extra"),
    ],
)
def test_result_m3_gate_cross_graph_rejects_full_array_cardinality_drift(
    array_name: str, operation: str
) -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    arrays: dict[str, list[dict[str, Any]]] = {
        "result": result_records,
        "gate": gates,
        "m4": m4_records,
        "source": sources,
    }
    target = arrays[array_name]
    if operation == "missing":
        target.pop()
    else:
        target.append(deepcopy(target[-1]))
    with pytest.raises(D02AuthorityError, match=r"requires|exactly"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


@pytest.mark.parametrize(
    "attack",
    ["duplicate_valid_record", "reorder_repeat", "cross_case_record"],
)
def test_result_m3_gate_cross_graph_rejects_resigned_result_record_array_attacks(
    attack: str,
) -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    if attack == "duplicate_valid_record":
        result_records[1] = deepcopy(result_records[0])
    elif attack == "reorder_repeat":
        result_records[0], result_records[1] = result_records[1], result_records[0]
        _resign_gate_with_unchecked_result_certificate(gates[0], result_records[:3])
    else:
        result_records[3] = deepcopy(result_records[0])
        _resign_gate_with_unchecked_result_certificate(gates[1], result_records[3:6])
    if attack == "duplicate_valid_record":
        _resign_gate_with_unchecked_result_certificate(gates[0], result_records[:3])
    with pytest.raises(D02AuthorityError, match=r"repeat order|M4/case/execution|semantic tuple"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


@pytest.mark.parametrize("attack", ["reorder", "cross_case", "wrong_peer"])
def test_result_m3_gate_cross_graph_rejects_resigned_gate_array_attacks(attack: str) -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    if attack == "reorder":
        gates[0], gates[1] = gates[1], gates[0]
    elif attack == "cross_case":
        gates[2] = deepcopy(gates[0])
    else:
        gates[0]["monotonicity_peer_case_id"] = cases[2]["case_id"]
        _resign_gate(gates[0])
    with pytest.raises(D02AuthorityError, match=r"gate/case/peer|case binding|semantic tuple"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


@pytest.mark.parametrize("field", ["result_output_id", "result_sha256"])
def test_result_m3_gate_cross_graph_rejects_m4_bound_result_drift_after_resigning(
    field: str,
) -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    value = _identifier("f") if field == "result_output_id" else _digest("f")
    replacement = _drift_result_records(
        result_records[:3], field=field, value=value, observation_field=True
    )
    result_records[:3] = replacement
    _resign_gate_for_records(gates[0], replacement)
    with pytest.raises(D02AuthorityError, match="M4/case/execution binding"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


@pytest.mark.parametrize(
    "field", ["runtime_manifest_digest", "vision_model_manifest_digest", "topology_digest"]
)
def test_result_m3_gate_cross_graph_rejects_resigned_runtime_authority_drift(field: str) -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    replacement = _drift_result_records(
        result_records[:3], field=field, value=_digest("f"), observation_field=False
    )
    result_records[:3] = replacement
    _resign_gate_with_unchecked_result_certificate(gates[0], replacement)
    with pytest.raises(D02AuthorityError, match="runtime binding"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


@pytest.mark.parametrize("attack", ["target", "controls"])
def test_result_m3_gate_cross_graph_rejects_resigned_source_measurement_drift(attack: str) -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    gate = gates[0]
    if attack == "target":
        target = cast(dict[str, Any], gate["source_target_measurement"])
        target["raw_value_fixed18"] = "0.310000000000000000"
        target["value_ppm"] = 310_000
    else:
        controls = cast(list[dict[str, Any]], gate["ordered_source_control_measurements"])
        controls[0], controls[1] = controls[1], controls[0]
    _resign_gate(gate)
    with pytest.raises(
        D02AuthorityError,
        match=r"target does not project|controls do not project|supported measurement schema",
    ):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


def test_result_m3_gate_cross_graph_rejects_resigned_embedded_observation_projection_drift() -> (
    None
):
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    replacement: list[dict[str, Any]] = []
    for record in result_records[:3]:
        drifted = deepcopy(record)
        observation = cast(dict[str, Any], drifted["measurement_observation"])
        entries = cast(list[dict[str, Any]], observation["ordered_measurements"])
        target_index = next(
            index
            for index, entry in enumerate(entries)
            if entry["dimension_key"] == cases[0]["dimension_key"]
        )
        entries[target_index]["raw_value_fixed18"] = "0.310000000000000000"
        _resign_observation(observation)
        drifted["measurement_observation_digest"] = observation["measurement_observation_digest"]
        replacement.append(_resign_result_record(drifted))
    result_records[:3] = replacement
    _resign_gate_for_records(gates[0], replacement)
    with pytest.raises(D02AuthorityError, match="target delta does not replay"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


@pytest.mark.parametrize("attack", ["result_digest", "certificate", "case_spec"])
def test_result_m3_gate_cross_graph_rejects_resigned_gate_binding_drift(attack: str) -> None:
    sources, cases, m4_records, result_records, gates, authority = _full_result_m3_gate_graph()
    gate = gates[0]
    if attack == "result_digest":
        gate["ordered_result_repeat_measurements"][0]["result_m3_record_digest"] = _digest("f")
    elif attack == "certificate":
        gate["result_repeat_certification"] = deepcopy(gates[1]["result_repeat_certification"])
        gate["result_repeat_certification_digest"] = gate["result_repeat_certification"][
            "result_repeat_certification_digest"
        ]
    else:
        gate["case_specification_digest"] = _digest("f")
    _resign_gate(gate)
    with pytest.raises(D02AuthorityError, match=r"record binding|semantic tuple|case binding"):
        _validate_full_result_m3_gate_graph(
            sources, cases, m4_records, result_records, gates, authority
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("missing", "exactly 96"),
        ("duplicate", "natural replay order"),
        ("reorder", "ID preimage|natural replay order"),
        ("case", "case authority binding"),
        ("source", "source output lineage"),
        ("sha", "byte/dimension deterministic"),
        ("dimension", "byte/dimension deterministic"),
        ("mime", "MIME type"),
        ("pixels", "byte/dimension deterministic"),
        ("id", "ID preimage"),
        ("digest", "record_digest does not replay"),
        ("replay", "ID preimage"),
        ("execution", "case authority binding"),
    ],
)
def test_m4_repeat_evidence_resigned_mutations_fail_closed(mutation: str, match: str) -> None:
    records, cases, sources, authority = _m4_evidence()
    forged = deepcopy(records)
    if mutation == "missing":
        forged.pop()
    elif mutation == "duplicate":
        forged[1] = deepcopy(forged[0])
    elif mutation == "reorder":
        forged[0], forged[1] = forged[1], forged[0]
    elif mutation == "case":
        forged[0]["case_id"] = _identifier("f")
        _resign_m4_record(forged[0])
    elif mutation == "source":
        for record in forged[:2]:
            record["source_output_id"] = "resigned-source-output"
            _resign_m4_record(record)
    elif mutation == "sha":
        forged[1]["result_sha256"] = _digest("f")
        _resign_m4_record(forged[1])
    elif mutation == "dimension":
        forged[1]["result_width"] = 63
        _resign_m4_record(forged[1])
    elif mutation == "mime":
        forged[1]["result_mime_type"] = "image/png"
        _resign_m4_record(forged[1])
    elif mutation == "pixels":
        forged[1]["changed_pixel_count"] = 2
        _resign_m4_record(forged[1])
    elif mutation == "id":
        forged[0]["m4_execution_record_id"] = _identifier("f")
        _resign_m4_record(forged[0])
    elif mutation == "digest":
        forged[0]["record_digest"] = _digest("f")
    elif mutation == "replay":
        forged[0]["replay_index"] = 2
        _resign_m4_record(forged[0])
    else:
        forged[0]["runtime_config_digest"] = _digest("e")
        _resign_m4_record(forged[0])
    with pytest.raises(D02AuthorityError, match=match):
        validate_m4_repeat_evidence(
            forged,
            case_manifest=cases,
            source_entries=sources,
            execution_authority=authority,
        )


def test_m4_single_record_exact_keys_fail_closed_after_resigning() -> None:
    records, cases, _, authority = _m4_evidence()
    forged = deepcopy(records[0])
    forged["locator"] = "forbidden"
    _resign_m4_record(forged)
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_m4_execution_record(forged, case_entry=cases[0], execution_authority=authority)


def _structure_manual_evidence() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    m4_records, cases, sources, authority = _m4_evidence()
    structures = [
        build_decode_structure_record(
            {
                "result_image_record_id": mirror_demo_digest("fixture-image/v1", {"case": index})[
                    :32
                ]
            },
            case_entry=case,
            m4_first=m4_records[index * 2],
            m4_second=m4_records[index * 2 + 1],
            execution_authority=authority,
        )
        for index, case in enumerate(cases)
    ]
    positions = {case["case_id"]: index for index, case in enumerate(cases)}
    manuals = [
        build_manual_artifact_decision(
            {
                "manual_review_version": "manual-v1",
                "decision_sequence": sequence,
                "background_seam": False,
                "disconnected_contour": False,
                "duplicated_feature": False,
                "warp_tear": False,
                "review_authority_digest": _digest("a"),
            },
            case_entry=case,
            m4_first=m4_records[positions[case["case_id"]] * 2],
            execution_authority=authority,
        )
        for sequence, case in enumerate(sorted(cases, key=lambda entry: entry["case_id"]), start=1)
    ]
    return structures, manuals, cases, sources, m4_records, authority


def _resign_structure(record: dict[str, Any]) -> None:
    record["record_digest"] = mirror_demo_digest(
        "mirror.demo/D02DecodeStructureImmutabilityRecord/v1",
        {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def _resign_manual(record: dict[str, Any]) -> None:
    record["manual_decision_digest"] = mirror_demo_digest(
        "mirror.demo/D02ManualArtifactDecision/v1",
        {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "manual_decision_digest"}
        },
    )


def test_structure_and_manual_evidence_derive_complete_48_record_arrays() -> None:
    structures, manuals, cases, sources, m4_records, authority = _structure_manual_evidence()
    validate_decode_structure_evidence(
        structures,
        case_manifest=cases,
        source_entries=sources,
        m4_records=m4_records,
        execution_authority=authority,
    )
    validate_manual_review_evidence(
        manuals,
        case_manifest=cases,
        source_entries=sources,
        m4_records=m4_records,
        execution_authority=authority,
    )
    assert len(structures) == len(manuals) == 48
    assert all(record["structure_gate_passed"] for record in structures)
    assert all(record["verdict"] == "PASS" for record in manuals)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "reorder",
        "m4",
        "dimensions",
        "replay",
        "pixels",
        "lineage",
        "gate",
        "digest",
    ],
)
def test_structure_evidence_resigned_mutations_fail_closed(mutation: str) -> None:
    structures, _, cases, sources, m4_records, authority = _structure_manual_evidence()
    forged = deepcopy(structures)
    if mutation == "missing":
        forged.pop()
    elif mutation == "duplicate":
        forged[1] = deepcopy(forged[0])
    elif mutation == "reorder":
        forged[0], forged[1] = forged[1], forged[0]
    elif mutation == "m4":
        forged[0]["m4_execution_record_digests"][0] = _digest("f")
        _resign_structure(forged[0])
    elif mutation == "dimensions":
        forged[0]["bounded_dimensions_passed"] = False
        _resign_structure(forged[0])
    elif mutation == "replay":
        forged[0]["m4_replay_bytes_equal"] = False
        _resign_structure(forged[0])
    elif mutation == "pixels":
        forged[0]["changed_pixel_count_positive"] = False
        _resign_structure(forged[0])
    elif mutation == "lineage":
        forged[0]["exact_lineage_passed"] = False
        _resign_structure(forged[0])
    elif mutation == "gate":
        forged[0]["structure_gate_passed"] = False
        _resign_structure(forged[0])
    else:
        forged[0]["record_digest"] = _digest("f")
    with pytest.raises(D02AuthorityError):
        validate_decode_structure_evidence(
            forged,
            case_manifest=cases,
            source_entries=sources,
            m4_records=m4_records,
            execution_authority=authority,
        )


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "reorder", "case", "sha", "sequence", "policy", "verdict", "artifact", "digest"],
)
def test_manual_evidence_resigned_mutations_fail_closed(mutation: str) -> None:
    _, manuals, cases, sources, m4_records, authority = _structure_manual_evidence()
    forged = deepcopy(manuals)
    if mutation == "duplicate":
        forged[1] = deepcopy(forged[0])
    elif mutation == "reorder":
        forged[0], forged[1] = forged[1], forged[0]
    elif mutation == "case":
        forged[0]["case_id"] = _identifier("f")
        _resign_manual(forged[0])
    elif mutation == "sha":
        forged[0]["result_sha256"] = _digest("f")
        _resign_manual(forged[0])
    elif mutation == "sequence":
        forged[0]["decision_sequence"] = 2
        _resign_manual(forged[0])
    elif mutation == "policy":
        forged[0]["manual_review_policy_digest"] = _digest("f")
        _resign_manual(forged[0])
    elif mutation == "verdict":
        forged[0]["verdict"] = "FAIL"
        _resign_manual(forged[0])
    elif mutation == "artifact":
        forged[0]["warp_tear"] = True
        _resign_manual(forged[0])
    else:
        forged[0]["manual_decision_digest"] = _digest("f")
    with pytest.raises(D02AuthorityError):
        validate_manual_review_evidence(
            forged,
            case_manifest=cases,
            source_entries=sources,
            m4_records=m4_records,
            execution_authority=authority,
        )


def test_structure_and_manual_exact_keys_fail_closed_after_resigning() -> None:
    structures, manuals, cases, _, m4_records, authority = _structure_manual_evidence()
    malformed_structure = deepcopy(structures[0])
    malformed_structure["locator"] = "forbidden"
    _resign_structure(malformed_structure)
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_decode_structure_record(
            malformed_structure,
            case_entry=cases[0],
            m4_first=m4_records[0],
            m4_second=m4_records[1],
            execution_authority=authority,
        )
    malformed_manual = deepcopy(manuals[0])
    malformed_manual["wall_clock"] = "forbidden"
    _resign_manual(malformed_manual)
    target_index = next(
        index for index, case in enumerate(cases) if case["case_id"] == manuals[0]["case_id"]
    )
    with pytest.raises(D02AuthorityError, match="exact keys"):
        validate_manual_artifact_decision(
            malformed_manual,
            case_entry=cases[target_index],
            m4_first=m4_records[target_index * 2],
            execution_authority=authority,
        )


def _image_phash_graph() -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
    dict[str, str],
]:
    sources, cases, m4_records, _, _, authority = _full_result_m3_gate_graph()
    result_asset_ids = {
        case["case_id"]: _result_asset_id(m4_records[index * 2]) for index, case in enumerate(cases)
    }
    images = cast(
        list[dict[str, Any]],
        build_image_authority_evidence(
            source_entries=sources,
            case_manifest=cases,
            m4_records=m4_records,
            execution_authority=authority,
            result_asset_ids=result_asset_ids,
        ),
    )
    evidence = cast(
        dict[str, Any],
        build_phash_observation_evidence(
            image_records=images,
            image_phashes={
                record["image_record_id"]: mirror_demo_digest(
                    "fixture-phash/v1", {"image_record_id": record["image_record_id"]}
                )[:16]
                for record in images
            },
            execution_authority=authority,
        ),
    )
    return images, evidence, sources, cases, m4_records, authority, result_asset_ids


def _measurement_execution_config() -> dict[str, Any]:
    manifest_path = (
        Path(__file__).parents[3]
        / "docs"
        / "research"
        / "P3_P7_D02_MEASUREMENT_QUALITY_AUTHORITY_MANIFEST.json"
    )
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    return cast(dict[str, Any], manifest["measurement_execution_config"])


def _complete_report_fixture(
    *,
    passing: bool,
    duplicate_result_sha: bool = False,
    unsupported_case_ordinals: frozenset[int] = frozenset(),
    source_p2_manifest_digest: str = _ACCEPTED_SOURCE_P2_MANIFEST_DIGEST,
    dimension_authority_manifest_digest: str = _ACCEPTED_DIMENSION_AUTHORITY_MANIFEST_DIGEST,
    geometry_ontology_digest: str = _ACCEPTED_GEOMETRY_ONTOLOGY_DIGEST,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, object]]:
    packet_sources, packets, source_records, source_manifest_digest = _complete_source_packets(
        source_p2_manifest_digest=source_p2_manifest_digest,
        dimension_authority_manifest_digest=dimension_authority_manifest_digest,
    )
    sources, cases, m4_records, result_records, gates, authority = (
        _full_result_m3_gate_graph_with_state(
            passing=passing,
            duplicate_result_sha=duplicate_result_sha,
            unsupported_case_ordinals=unsupported_case_ordinals,
            source_p2_manifest_digest=source_p2_manifest_digest,
            dimension_authority_manifest_digest=dimension_authority_manifest_digest,
            geometry_ontology_digest=geometry_ontology_digest,
        )
    )
    assert sources == packet_sources
    result_asset_ids = {
        case["case_id"]: _result_asset_id(m4_records[index * 2]) for index, case in enumerate(cases)
    }
    images = cast(
        list[dict[str, Any]],
        build_image_authority_evidence(
            source_entries=sources,
            case_manifest=cases,
            m4_records=m4_records,
            execution_authority=authority,
            result_asset_ids=result_asset_ids,
        ),
    )
    result_image_by_case = {
        image["case_id"]: image for image in images if image["authority_role"] == "RESULT"
    }
    structures = [
        build_decode_structure_record(
            {"result_image_record_id": result_image_by_case[case["case_id"]]["image_record_id"]},
            case_entry=case,
            m4_first=m4_records[index * 2],
            m4_second=m4_records[index * 2 + 1],
            execution_authority=authority,
        )
        for index, case in enumerate(cases)
    ]
    case_positions = {case["case_id"]: index for index, case in enumerate(cases)}
    manuals = [
        build_manual_artifact_decision(
            {
                "manual_review_version": "manual-v1",
                "decision_sequence": sequence,
                "background_seam": False,
                "disconnected_contour": False,
                "duplicated_feature": False,
                "warp_tear": False,
                "review_authority_digest": _digest("a"),
            },
            case_entry=case,
            m4_first=m4_records[case_positions[case["case_id"]] * 2],
            execution_authority=authority,
        )
        for sequence, case in enumerate(sorted(cases, key=lambda item: item["case_id"]), start=1)
    ]
    exact_duplicate = build_exact_duplicate_evidence(
        image_records=images,
        source_entries=sources,
        case_manifest=cases,
        m4_records=m4_records,
        execution_authority=authority,
        result_asset_ids=result_asset_ids,
    )
    phash = build_phash_observation_evidence(
        image_records=images,
        image_phashes={
            image["image_record_id"]: mirror_demo_digest(
                "fixture-phash/v1", {"image_record_id": image["image_record_id"]}
            )[:16]
            for image in images
        },
        execution_authority=authority,
    )
    variant_bindings: dict[str, object] = {
        case["case_id"]: _result_variant_binding(case, m4_records[index * 2])
        for index, case in enumerate(cases)
    }
    pairs = build_pair_screening_evidence(
        case_manifest=cases,
        source_entries=sources,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        structure_records=structures,
        manual_records=manuals,
        image_records=images,
        execution_authority=authority,
        result_variant_bindings=variant_bindings,
    )
    dimensions = build_dimension_eligibility_evidence(
        pairs,
        exact_sha_gate_passed=cast(bool, exact_duplicate["exact_sha_gate_passed"]),
    )
    selection, eligible_keys, selected_keys, status = build_selection_trace(dimensions)
    selected_manifest, selected_manifest_digest = build_selected_pair_manifest(
        pairs, selected_dimension_keys=selected_keys
    )
    case_manifest_digest = validate_ordered_case_manifest(
        cases,
        source_entries=sources,
        execution_authority=authority,
    )
    binding = build_schema_and_policy_binding(
        {
            "source_manifest_digest": source_manifest_digest,
            "case_manifest_digest": case_manifest_digest,
            **authority,
            "measurement_execution_config": _measurement_execution_config(),
            "measurement_quality_config_digest": QUALITY_CONFIG_DIGEST,
            "measurement_quality_manifest_content_digest": QUALITY_MANIFEST_DIGEST,
            "confidence_kind": CONFIDENCE_KIND,
            "reliability_kind": RELIABILITY_KIND,
        }
    )
    payload: dict[str, object] = {
        "schema_and_policy": binding,
        "ordered_source_manifest": sources,
        "ordered_case_manifest": cases,
        "source_m3_repeat_evidence": source_records,
        "m4_repeat_evidence": m4_records,
        "result_m3_repeat_evidence": result_records,
        "measurement_gate_evidence": gates,
        "decode_structure_immutability_evidence": structures,
        "manual_review_evidence": manuals,
        "exact_duplicate_evidence": exact_duplicate,
        "phash_observation_evidence": phash,
        "pair_quality_evidence": pairs,
        "dimension_eligibility": dimensions,
        "fixed_priority_selection_trace": selection,
        "selected_pair_manifest": selected_manifest,
        "network_and_runtime_boundary": {
            "schema_version": "mirror.demo/D02NetworkRuntimeBoundary/v2",
            "public_internet_egress": "DENIED",
            "localhost_and_docker_internal_network": True,
            "proxy_environment_present": False,
            "production_provider_calls": 0,
            "runtime_generation_calls": 0,
            "boundary_receipt_digest": _digest("f"),
        },
    }
    fields: dict[str, object] = {
        "created_at": "2026-08-24T00:00:00Z",
        "source_manifest_digest": source_manifest_digest,
        "case_manifest_digest": case_manifest_digest,
        **authority,
        "report_payload": payload,
        "status": status,
        "source_count": 4,
        "case_count": 48,
        "source_m3_repeat_count": 12,
        "m4_execution_count": 96,
        "result_m3_repeat_count": 144,
        "manual_decision_count": 48,
        "exact_sha_record_count": 52,
        "phash_comparison_count": 1326,
        "candidate_pair_count": 24,
        "selected_pair_count": 16 if status == "PASSED" else 0,
        "selected_result_side_count": 32 if status == "PASSED" else 0,
        "eligible_dimension_keys": eligible_keys,
        "selected_dimension_keys": selected_keys,
        "selected_pair_manifest_digest": selected_manifest_digest,
    }
    report = cast(
        dict[str, Any],
        build_report_row(
            fields,
            source_graph_packets=packets,
            result_variant_bindings=variant_bindings,
        ),
    )
    return report, packets, variant_bindings


def _resign_report_row(report: dict[str, Any]) -> None:
    report["report_digest"] = mirror_demo_digest(
        "mirror.demo/D02PairScreeningReport/v2", report["report_payload"]
    )
    report["id"] = mirror_demo_digest(
        "mirror.demo/D02PairScreeningReportId/v1",
        {"report_digest": report["report_digest"]},
    )[:32]
    canonical = {
        key: value
        for key, value in report.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    if report["status"] == "FAILED":
        canonical.pop("selected_pair_manifest_digest")
    report["canonical_payload"] = canonical
    report["content_digest"] = mirror_demo_digest(
        "mirror.demo/D02PairScreeningReport/v2", canonical
    )


def _resign_pair_wrapper(wrapper: dict[str, Any], *, recompute_id: bool = False) -> None:
    payload = cast(dict[str, Any], wrapper["pair_screening_record_payload"])
    if recompute_id:
        payload["pair_record_id"] = mirror_demo_digest(
            "mirror.demo/D02PairScreeningRecordId/v1",
            {
                "source_authority_key": payload["source_authority_key"],
                "source_admission_event_id": payload["source_admission_event_id"],
                "source_asset_sha256": payload["source_asset_sha256"],
                "dimension_key": payload["dimension_key"],
                "priority_index": payload["priority_index"],
                "magnitude_ppm": payload["magnitude_ppm"],
                "left_case_id": payload["left"]["case_id"],
                "right_case_id": payload["right"]["case_id"],
                "screening_policy_digest": payload["screening_policy_digest"],
                "lock_policy_digest": payload["lock_policy_digest"],
            },
        )[:32]
    wrapper["pair_screening_record_digest"] = mirror_demo_digest(
        "mirror.demo/D02PairScreeningRecord/v3", payload
    )


def _rebuild_report_outcomes(report: dict[str, Any]) -> None:
    payload = cast(dict[str, Any], report["report_payload"])
    pairs = cast(list[dict[str, Any]], payload["pair_quality_evidence"])
    exact = cast(dict[str, Any], payload["exact_duplicate_evidence"])
    dimensions = build_dimension_eligibility_evidence(
        pairs, exact_sha_gate_passed=cast(bool, exact["exact_sha_gate_passed"])
    )
    selection, eligible_keys, selected_keys, status = build_selection_trace(dimensions)
    selected_manifest, selected_digest = build_selected_pair_manifest(
        pairs, selected_dimension_keys=selected_keys
    )
    payload["dimension_eligibility"] = dimensions
    payload["fixed_priority_selection_trace"] = selection
    payload["selected_pair_manifest"] = selected_manifest
    report["status"] = status
    report["eligible_dimension_keys"] = eligible_keys
    report["selected_dimension_keys"] = selected_keys
    report["selected_pair_manifest_digest"] = selected_digest
    report["selected_pair_count"] = 16 if status == "PASSED" else 0
    report["selected_result_side_count"] = 32 if status == "PASSED" else 0
    _resign_report_row(report)


def _resign_dimension_record(record: dict[str, Any]) -> None:
    record["record_digest"] = mirror_demo_digest(
        "mirror.demo/D02DimensionEligibilityRecord/v3",
        {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def _resign_selection_record(record: dict[str, Any]) -> None:
    record["record_digest"] = mirror_demo_digest(
        "mirror.demo/D02SelectionTraceRecord/v2",
        {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def _resign_image_authority_record(record: dict[str, Any]) -> None:
    id_keys: tuple[str, ...]
    if record["authority_role"] == "SOURCE":
        domain = "mirror.demo/D02SourceImageAuthorityRecordId/v1"
        id_keys = (
            "authority_role",
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "sha256",
        )
        schema = "mirror.demo/D02SourceImageAuthorityRecord/v2"
    else:
        domain = "mirror.demo/D02ResultImageAuthorityRecordId/v1"
        id_keys = (
            "authority_role",
            "source_authority_key",
            "source_admission_event_id",
            "case_id",
            "case_specification_digest",
            "result_output_id",
            "deterministic_result_asset_id",
            "sha256",
        )
        schema = "mirror.demo/D02ResultImageAuthorityRecord/v2"
    record["image_record_id"] = mirror_demo_digest(domain, {key: record[key] for key in id_keys})[
        :32
    ]
    record["image_record_digest"] = mirror_demo_digest(
        schema,
        {
            key: value
            for key, value in record.items()
            if key not in {"schema_version", "image_record_digest"}
        },
    )


def test_image_and_phash_authority_replays_complete_observation_only_universe() -> None:
    images, evidence, sources, cases, m4_records, authority, result_asset_ids = _image_phash_graph()
    assert validate_image_authority_evidence(
        images,
        source_entries=sources,
        case_manifest=cases,
        m4_records=m4_records,
        execution_authority=authority,
        result_asset_ids=result_asset_ids,
    )
    validate_phash_observation_evidence(
        evidence,
        image_records=images,
        execution_authority=authority,
    )
    assert len(images) == len(evidence["ordered_record_signatures"]) == 52
    assert len(evidence["comparisons"]) == 1326
    assert evidence["threshold_policy"] == "OBSERVATION_ONLY_NO_THRESHOLD"
    assert [record["image_record_ordinal"] for record in images] == list(range(1, 53))
    source = next(record for record in images if record["authority_role"] == "SOURCE")
    result = next(record for record in images if record["authority_role"] == "RESULT")
    for record in (source, result):
        replay = deepcopy(record)
        _resign_image_authority_record(replay)
        assert replay["image_record_id"] == record["image_record_id"]
        assert replay["image_record_digest"] == record["image_record_digest"]
    assert result["deterministic_result_asset_id"] != result["result_output_id"]


def test_exact_sha_duplicate_is_a_gate_failure_not_a_phash_cardinality_escape() -> None:
    _images, _, sources, cases, m4_records, authority, result_asset_ids = _image_phash_graph()
    duplicate = deepcopy(m4_records)
    for record in duplicate[2:4]:
        record["result_sha256"] = duplicate[0]["result_sha256"]
        _resign_m4_record(record)
    duplicate_images = cast(
        list[dict[str, Any]],
        build_image_authority_evidence(
            source_entries=sources,
            case_manifest=cases,
            m4_records=duplicate,
            execution_authority=authority,
            result_asset_ids=result_asset_ids,
        ),
    )
    assert not validate_image_authority_evidence(
        duplicate_images,
        source_entries=sources,
        case_manifest=cases,
        m4_records=duplicate,
        execution_authority=authority,
        result_asset_ids=result_asset_ids,
    )
    duplicate_evidence = cast(
        dict[str, Any],
        build_phash_observation_evidence(
            image_records=duplicate_images,
            image_phashes={record["image_record_id"]: "0" * 16 for record in duplicate_images},
            execution_authority=authority,
        ),
    )
    validate_phash_observation_evidence(
        duplicate_evidence,
        image_records=duplicate_images,
        execution_authority=authority,
    )
    assert len(duplicate_evidence["comparisons"]) == 1326


def test_phash_observation_cannot_change_exact_sha_gate_semantics() -> None:
    images, evidence, sources, cases, m4_records, authority, result_asset_ids = _image_phash_graph()
    exact_sha_gate = validate_image_authority_evidence(
        images,
        source_entries=sources,
        case_manifest=cases,
        m4_records=m4_records,
        execution_authority=authority,
        result_asset_ids=result_asset_ids,
    )
    altered = build_phash_observation_evidence(
        image_records=images,
        image_phashes={record["image_record_id"]: "f" * 16 for record in images},
        execution_authority=authority,
    )
    validate_phash_observation_evidence(
        evidence, image_records=images, execution_authority=authority
    )
    validate_phash_observation_evidence(
        altered, image_records=images, execution_authority=authority
    )
    assert exact_sha_gate == validate_image_authority_evidence(
        images,
        source_entries=sources,
        case_manifest=cases,
        m4_records=m4_records,
        execution_authority=authority,
        result_asset_ids=result_asset_ids,
    )


@pytest.mark.parametrize(
    "attack",
    [
        "missing_signature",
        "extra_signature",
        "duplicate_signature",
        "reorder_signature",
        "wrong_signature_binding",
        "wrong_hex_width",
        "wrong_threshold",
        "wrong_bit_width",
        "wrong_implementation",
        "missing_comparison",
        "extra_comparison",
        "reversed_comparison",
        "wrong_hamming",
        "wrong_comparison_digest",
        "boolean_signature_ordinal",
        "boolean_comparison_ordinal",
        "boolean_comparison_side_ordinal",
    ],
)
def test_phash_evidence_resigned_adversarial_matrix_fails_closed(attack: str) -> None:
    images, evidence, _, _, _, authority, _ = _image_phash_graph()
    forged = deepcopy(evidence)
    signatures = cast(list[dict[str, Any]], forged["ordered_record_signatures"])
    comparisons = cast(list[dict[str, Any]], forged["comparisons"])
    if attack == "missing_signature":
        signatures.pop()
    elif attack == "extra_signature":
        signatures.append(deepcopy(signatures[0]))
    elif attack == "duplicate_signature":
        signatures[1] = deepcopy(signatures[0])
    elif attack == "reorder_signature":
        signatures[0], signatures[1] = signatures[1], signatures[0]
    elif attack == "wrong_signature_binding":
        signatures[0]["image_sha256"] = _digest("f")
        signatures[0]["signature_digest"] = mirror_demo_digest(
            "mirror.demo/D02PHashSignatureRecord/v1",
            {
                key: value
                for key, value in signatures[0].items()
                if key not in {"schema_version", "signature_digest"}
            },
        )
    elif attack == "wrong_hex_width":
        signatures[0]["phash_hex"] = "0" * 15
        signatures[0]["signature_digest"] = mirror_demo_digest(
            "mirror.demo/D02PHashSignatureRecord/v1",
            {
                key: value
                for key, value in signatures[0].items()
                if key not in {"schema_version", "signature_digest"}
            },
        )
    elif attack == "wrong_threshold":
        forged["threshold_policy"] = None
    elif attack == "wrong_bit_width":
        forged["bit_width"] = 63
    elif attack == "wrong_implementation":
        forged["implementation_digest"] = _digest("f")
    elif attack == "missing_comparison":
        comparisons.pop()
    elif attack == "extra_comparison":
        comparisons.append(deepcopy(comparisons[0]))
    elif attack == "reversed_comparison":
        comparison = comparisons[0]
        for left_key, right_key in (
            ("left_image_record_ordinal", "right_image_record_ordinal"),
            ("left_image_record_id", "right_image_record_id"),
            ("left_signature_digest", "right_signature_digest"),
        ):
            comparison[left_key], comparison[right_key] = (
                comparison[right_key],
                comparison[left_key],
            )
        comparison["comparison_digest"] = mirror_demo_digest(
            "mirror.demo/D02PHashComparisonRecord/v1",
            {
                key: value
                for key, value in comparison.items()
                if key not in {"schema_version", "comparison_digest"}
            },
        )
    elif attack == "wrong_hamming":
        comparisons[0]["hamming_distance"] = 65
        comparisons[0]["comparison_digest"] = mirror_demo_digest(
            "mirror.demo/D02PHashComparisonRecord/v1",
            {
                key: value
                for key, value in comparisons[0].items()
                if key not in {"schema_version", "comparison_digest"}
            },
        )
    elif attack == "wrong_comparison_digest":
        comparisons[0]["comparison_digest"] = _digest("f")
    elif attack == "boolean_signature_ordinal":
        signatures[0]["image_record_ordinal"] = True
        signatures[0]["signature_digest"] = mirror_demo_digest(
            "mirror.demo/D02PHashSignatureRecord/v1",
            {
                key: value
                for key, value in signatures[0].items()
                if key not in {"schema_version", "signature_digest"}
            },
        )
    elif attack == "boolean_comparison_ordinal":
        comparisons[0]["comparison_ordinal"] = True
        comparisons[0]["comparison_digest"] = mirror_demo_digest(
            "mirror.demo/D02PHashComparisonRecord/v1",
            {
                key: value
                for key, value in comparisons[0].items()
                if key not in {"schema_version", "comparison_digest"}
            },
        )
    else:
        comparisons[0]["left_image_record_ordinal"] = True
        comparisons[0]["comparison_digest"] = mirror_demo_digest(
            "mirror.demo/D02PHashComparisonRecord/v1",
            {
                key: value
                for key, value in comparisons[0].items()
                if key not in {"schema_version", "comparison_digest"}
            },
        )
    with pytest.raises(D02AuthorityError):
        validate_phash_observation_evidence(
            forged,
            image_records=images,
            execution_authority=authority,
        )


def test_image_source_and_m4_lineage_drift_fail_closed_after_resigning() -> None:
    images, _, sources, cases, m4_records, authority, result_asset_ids = _image_phash_graph()
    forged = deepcopy(images)
    target_index = next(
        index for index, record in enumerate(forged) if record["authority_role"] == "SOURCE"
    )
    forged[target_index]["source_authority_key"] = "resigned-drift"
    _resign_image_authority_record(forged[target_index])
    with pytest.raises(D02AuthorityError, match=r"source authority key|does not replay"):
        validate_image_authority_evidence(
            forged,
            source_entries=sources,
            case_manifest=cases,
            m4_records=m4_records,
            execution_authority=authority,
            result_asset_ids=result_asset_ids,
        )


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("sha256", _digest("f")),
        ("result_output_id", _identifier("e")),
        ("case_specification_digest", _digest("e")),
        ("deterministic_result_asset_id", _identifier("f")),
        ("source_authority_key", "resigned-result-drift"),
        ("source_ordinal", 4),
    ],
)
def test_result_image_checksum_and_lineage_drift_fail_closed_after_resigning(
    field: str, replacement: object
) -> None:
    images, _, sources, cases, m4_records, authority, result_asset_ids = _image_phash_graph()
    forged = deepcopy(images)
    target_index = next(
        index for index, record in enumerate(forged) if record["authority_role"] == "RESULT"
    )
    forged[target_index][field] = replacement
    _resign_image_authority_record(forged[target_index])
    with pytest.raises(D02AuthorityError, match=r"source authority key|does not replay"):
        validate_image_authority_evidence(
            forged,
            source_entries=sources,
            case_manifest=cases,
            m4_records=m4_records,
            execution_authority=authority,
            result_asset_ids=result_asset_ids,
        )


def test_revision9_policy_roots_are_embedded_and_caller_cannot_replace_them() -> None:
    assert SCREENING_POLICY_DIGEST == (
        "4b18fd2543abd8e2a86c2dfc339aefbd9ed0e9d53d5a8e18b49ba21252e9488e"
    )
    assert EMPTY_LOCK_POLICY_DIGEST == (
        "3e61fff06db1b624845f806ef200bf2f74358477e3ea155d345a0c2d1abcacd7"
    )
    authority = _case_execution_authority()
    authority["screening_policy_digest"] = _digest("f")
    with pytest.raises(D02AuthorityError, match="accepted Revision 9"):
        build_ordered_case_manifest(
            _case_sources(),
            execution_authority=authority,
            geometry_fields=_case_geometry_fields(),
        )


def test_pair_dimension_selection_and_selected_manifest_replay_full_passed_universe() -> None:
    report, packets, variant_bindings = _complete_report_fixture(passing=True)
    payload = cast(dict[str, Any], report["report_payload"])
    pairs = cast(list[dict[str, Any]], payload["pair_quality_evidence"])
    dimensions = cast(list[dict[str, Any]], payload["dimension_eligibility"])
    selection = cast(list[dict[str, Any]], payload["fixed_priority_selection_trace"])
    selected = cast(list[dict[str, Any]], payload["selected_pair_manifest"])
    assert len(pairs) == 24
    assert len(dimensions) == len(selection) == 3
    assert len(selected) == 16
    assert all(pair["pair_screening_record_payload"]["pair_gate_passed"] for pair in pairs)
    assert all(
        pair["pair_screening_record_payload"]["pair_quality_ppm"] == 1_000_000 for pair in pairs
    )
    assert report["eligible_dimension_keys"] == ["jaw_width", "chin_height", "eye_spacing"]
    assert report["selected_dimension_keys"] == ["jaw_width", "chin_height"]
    assert selection[2]["selection_decision"] == "ELIGIBLE_NOT_SELECTED_CAPACITY"
    validate_report_row(
        report,
        source_graph_packets=packets,
        result_variant_bindings=variant_bindings,
    )


@pytest.mark.parametrize("unsupported_case_ordinal", [1, 2])
def test_mixed_peer_report_preserves_exact_unsupported_side_and_fallback_selection(
    unsupported_case_ordinal: int,
) -> None:
    report, packets, variant_bindings = _complete_report_fixture(
        passing=True,
        unsupported_case_ordinals=frozenset({unsupported_case_ordinal}),
    )
    payload = cast(dict[str, Any], report["report_payload"])
    unsupported_case = payload["ordered_case_manifest"][unsupported_case_ordinal - 1]
    pair_payload = next(
        wrapper["pair_screening_record_payload"]
        for wrapper in payload["pair_quality_evidence"]
        if unsupported_case["case_id"]
        in {
            wrapper["pair_screening_record_payload"]["left"]["case_id"],
            wrapper["pair_screening_record_payload"]["right"]["case_id"],
        }
    )
    unsupported_side = next(
        side
        for side in (pair_payload["left"], pair_payload["right"])
        if side["case_id"] == unsupported_case["case_id"]
    )
    assert unsupported_side["schema_version"] == "mirror.demo/D02UnsupportedPairSide/v3"
    assert unsupported_side["measurement_evaluation_state"] == "UNSUPPORTED_EXPLICIT"
    assert unsupported_side["unsupported_repeat_indexes"] == [1, 2, 3]
    assert unsupported_side["ordered_unsupported_reasons"] == ["RUNTIME_UNSUPPORTED"] * 3
    assert "raw_signed_target_delta_fixed18" not in unsupported_side
    assert "magnitude_monotonicity_gate_passed" not in unsupported_side
    assert unsupported_side["automated_gate_passed"] is False
    assert unsupported_side["side_gate_passed"] is False
    assert unsupported_side["side_quality_component_ppm"] == 0
    assert pair_payload["pair_gate_passed"] is False
    assert pair_payload["pair_quality_state"] == "NOT_COMPUTED_GATE_FAILED"
    assert pair_payload["pair_quality_ppm"] == 0
    assert report["status"] == "PASSED"
    assert report["eligible_dimension_keys"] == ["chin_height", "eye_spacing"]
    assert report["selected_dimension_keys"] == ["chin_height", "eye_spacing"]
    validate_report_row(
        report,
        source_graph_packets=packets,
        result_variant_bindings=variant_bindings,
    )


def test_complete_report_replay_is_byte_identical() -> None:
    first, first_packets, first_variants = _complete_report_fixture(passing=True)
    second, second_packets, second_variants = _complete_report_fixture(passing=True)

    def canonical(value: object) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )

    assert canonical(first) == canonical(second)
    assert canonical(first_packets) == canonical(second_packets)
    assert canonical(first_variants) == canonical(second_variants)


def test_exact_sha_duplicate_is_full_cardinality_failed_outcome_with_complete_phash() -> None:
    report, packets, variant_bindings = _complete_report_fixture(
        passing=True, duplicate_result_sha=True
    )
    payload = cast(dict[str, Any], report["report_payload"])
    exact = cast(dict[str, Any], payload["exact_duplicate_evidence"])
    phash = cast(dict[str, Any], payload["phash_observation_evidence"])
    pairs = cast(list[dict[str, Any]], payload["pair_quality_evidence"])
    dimensions = cast(list[dict[str, Any]], payload["dimension_eligibility"])
    assert report["status"] == "FAILED"
    assert exact["exact_sha_gate_passed"] is False
    assert len(exact["image_records"]) == len(phash["ordered_record_signatures"]) == 52
    assert len(phash["comparisons"]) == 1326
    assert all(pair["pair_screening_record_payload"]["pair_gate_passed"] for pair in pairs)
    assert all(not record["eligible"] for record in dimensions)
    assert all("GLOBAL_EXACT_SHA_GATE_FAILED" in record["failure_reasons"] for record in dimensions)
    validate_report_row(
        report,
        source_graph_packets=packets,
        result_variant_bindings=variant_bindings,
    )


def test_pair_resigned_direction_quality_and_lock_root_attacks_fail_closed() -> None:
    passed, passed_packets, passed_variants = _complete_report_fixture(passing=True)
    failed, failed_packets, failed_variants = _complete_report_fixture(passing=False)

    wrong_direction = deepcopy(passed)
    pair = wrong_direction["report_payload"]["pair_quality_evidence"][0]
    pair["pair_screening_record_payload"]["left"]["requested_direction"] = "INCREASE"
    _resign_pair_wrapper(pair)
    _rebuild_report_outcomes(wrong_direction)
    with pytest.raises(D02AuthorityError, match="pair screening record"):
        validate_report_row(
            wrong_direction,
            source_graph_packets=passed_packets,
            result_variant_bindings=passed_variants,
        )

    invalid_quality = deepcopy(failed)
    pair = invalid_quality["report_payload"]["pair_quality_evidence"][0]
    pair["pair_screening_record_payload"]["left"]["side_quality_component_ppm"] = 1
    _resign_pair_wrapper(pair)
    _rebuild_report_outcomes(invalid_quality)
    with pytest.raises(D02AuthorityError, match="pair screening record"):
        validate_report_row(
            invalid_quality,
            source_graph_packets=failed_packets,
            result_variant_bindings=failed_variants,
        )

    wrong_lock = deepcopy(passed)
    pair = wrong_lock["report_payload"]["pair_quality_evidence"][0]
    pair["pair_screening_record_payload"]["lock_policy_digest"] = _digest("f")
    _resign_pair_wrapper(pair, recompute_id=True)
    _rebuild_report_outcomes(wrong_lock)
    with pytest.raises(D02AuthorityError, match="pair screening record"):
        validate_report_row(
            wrong_lock,
            source_graph_packets=passed_packets,
            result_variant_bindings=passed_variants,
        )


def test_selection_trace_covers_all_eight_eligibility_states_and_rejects_stale_rank() -> None:
    report, _, _ = _complete_report_fixture(passing=True)
    base_dimensions = cast(list[dict[str, Any]], report["report_payload"]["dimension_eligibility"])
    selected_by_state = {
        (False, False, False): [],
        (True, False, False): [],
        (False, True, False): [],
        (False, False, True): [],
        (True, True, False): ["jaw_width", "chin_height"],
        (True, False, True): ["jaw_width", "eye_spacing"],
        (False, True, True): ["chin_height", "eye_spacing"],
        (True, True, True): ["jaw_width", "chin_height"],
    }
    for bits, expected_selected in selected_by_state.items():
        dimensions = deepcopy(base_dimensions)
        for record, eligible in zip(dimensions, bits, strict=True):
            record["eligible"] = eligible
            _resign_dimension_record(record)
        trace, eligible_keys, selected_keys, status = build_selection_trace(dimensions)
        assert selected_keys == expected_selected
        assert eligible_keys == [
            dimension
            for dimension, eligible in zip(
                ("jaw_width", "chin_height", "eye_spacing"), bits, strict=True
            )
            if eligible
        ]
        assert status == ("PASSED" if sum(bits) >= 2 else "FAILED")
        validate_selection_trace(trace, dimension_records=dimensions)
        if sum(bits) == 1:
            assert next(item for item in trace if item["eligible"])["selection_decision"] == (
                "ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET"
            )
        if bits == (True, True, True):
            assert trace[2]["selection_decision"] == "ELIGIBLE_NOT_SELECTED_CAPACITY"
    dimensions = deepcopy(base_dimensions)
    trace, _, _, _ = build_selection_trace(dimensions)
    trace[0]["eligible_rank"] = 2
    _resign_selection_record(trace[0])
    with pytest.raises(D02AuthorityError, match="selection trace record"):
        validate_selection_trace(trace, dimension_records=dimensions)


def test_full_report_rejects_isolated_source_placeholder_swaps_and_stale_projections() -> None:
    report, packets, variant_bindings = _complete_report_fixture(passing=True)

    isolated = deepcopy(packets)
    isolated[0]["facts"] = deepcopy(isolated[1]["facts"])
    with pytest.raises(D02AuthorityError):
        validate_report_row(
            report,
            source_graph_packets=isolated,
            result_variant_bindings=variant_bindings,
        )

    attacks: list[dict[str, Any]] = []
    placeholder = deepcopy(report)
    placeholder["report_payload"]["pair_quality_evidence"] = [{}]
    attacks.append(placeholder)
    stale_count = deepcopy(report)
    stale_count["candidate_pair_count"] = 23
    attacks.append(stale_count)
    swapped_structure = deepcopy(report)
    structures = swapped_structure["report_payload"]["decode_structure_immutability_evidence"]
    structures[0], structures[1] = structures[1], structures[0]
    attacks.append(swapped_structure)
    swapped_selected = deepcopy(report)
    selected = swapped_selected["report_payload"]["selected_pair_manifest"]
    selected[0], selected[1] = selected[1], selected[0]
    attacks.append(swapped_selected)
    substituted_selected = deepcopy(report)
    substituted_pairs = cast(
        list[dict[str, Any]], substituted_selected["report_payload"]["pair_quality_evidence"]
    )
    substituted_manifest, substituted_digest = build_selected_pair_manifest(
        substituted_pairs,
        selected_dimension_keys=["jaw_width", "eye_spacing"],
    )
    substituted_selected["report_payload"]["selected_pair_manifest"] = substituted_manifest
    substituted_selected["selected_pair_manifest_digest"] = substituted_digest
    attacks.append(substituted_selected)
    wrong_exact = deepcopy(report)
    wrong_exact["report_payload"]["exact_duplicate_evidence"]["exact_sha_gate_passed"] = False
    attacks.append(wrong_exact)
    for forged in attacks:
        _resign_report_row(forged)
        with pytest.raises(D02AuthorityError):
            validate_report_row(
                forged,
                source_graph_packets=packets,
                result_variant_bindings=variant_bindings,
            )


def test_observability_support_union_uses_exact_raw_fixed18_floor() -> None:
    at_floor = _source_observation()
    at_floor_entry = cast(list[dict[str, Any]], at_floor["ordered_measurements"])[0]
    at_floor_entry["raw_observability_fixed18"] = "0.000001000000000000"
    _resign_observation(at_floor)
    validate_measurement_observation(at_floor, role="SOURCE")

    ppm_collision = _source_observation()
    collision_entry = cast(list[dict[str, Any]], ppm_collision["ordered_measurements"])[0]
    collision_entry["raw_observability_fixed18"] = "0.000000999999999999"
    _resign_observation(ppm_collision)
    with pytest.raises(D02AuthorityError, match="supported observation union"):
        validate_measurement_observation(ppm_collision, role="SOURCE")

    low_confidence = deepcopy(ppm_collision)
    low_entry = cast(list[dict[str, Any]], low_confidence["ordered_measurements"])[0]
    low_entry["support_state"] = "UNSUPPORTED"
    low_entry["raw_value_fixed18"] = None
    low_entry["unsupported_reason"] = "LOW_CONFIDENCE"
    _resign_observation(low_confidence)
    validate_measurement_observation(low_confidence, role="SOURCE")

    low_at_floor = deepcopy(low_confidence)
    cast(list[dict[str, Any]], low_at_floor["ordered_measurements"])[0][
        "raw_observability_fixed18"
    ] = "0.000001000000000000"
    _resign_observation(low_at_floor)
    with pytest.raises(D02AuthorityError, match="low-confidence observation union"):
        validate_measurement_observation(low_at_floor, role="SOURCE")


def test_complete_case_manifest_rejects_boolean_priority_after_full_resign() -> None:
    entries, sources, authority = _case_manifest()
    forged = deepcopy(entries)
    entry = forged[0]
    entry["priority_index"] = True
    entry["case_specification_digest"] = mirror_demo_digest(
        "mirror.demo/D02GeometryCaseSpecification/v1",
        {
            key: value
            for key, value in entry.items()
            if key
            not in {
                "schema_version",
                "case_ordinal",
                "case_id",
                "record_digest",
                "case_specification_digest",
            }
        },
    )
    _resign_case_entry(entry)
    with pytest.raises(D02AuthorityError, match="unlisted persisted Boolean"):
        validate_ordered_case_manifest(
            forged,
            source_entries=sources,
            execution_authority=authority,
        )


def test_complete_source_graph_rejects_resigned_split_asset_authority() -> None:
    facts, identity, entry = _facts_identity_manifest()
    split_observation = deepcopy(cast(dict[str, Any], facts["source_measurement_observation"]))
    split_subject = cast(dict[str, Any], split_observation["subject"])
    split_subject["source_asset_id"] = _identifier("f")
    split_subject["source_asset_sha256"] = _digest("f")
    _resign_observation(split_observation)
    original_certificate = cast(dict[str, Any], facts["source_repeat_certification"])
    original_binding = cast(list[dict[str, Any]], original_certificate["ordered_repeat_bindings"])[
        0
    ]
    split_certificate = _source_certificate(
        split_observation,
        execution_receipt_digest=cast(str, original_binding["execution_receipt_digest"]),
    )
    split_raw = cast(
        dict[str, Any],
        build_raw_measurement_authority(
            split_observation,
            split_certificate,
            source_p2_candidate_manifest_content_digest=cast(
                str, facts["source_p2_candidate_manifest_content_digest"]
            ),
            dimension_authority_manifest_content_digest=cast(
                str, facts["dimension_authority_manifest_content_digest"]
            ),
        ),
    )
    split_projection = cast(dict[str, Any], build_morphology_projection(split_raw))
    split_facts_fields = deepcopy(facts)
    split_facts_fields.update(
        {
            "source_measurement_digest": split_observation["measurement_observation_digest"],
            "source_measurement_projection": split_projection,
            "source_measurement_projection_digest": digest_morphology_projection(split_projection),
            "raw_measurement_authority": split_raw,
            "raw_measurement_authority_digest": digest_raw_measurement_authority(split_raw),
            "source_measurement_observation": split_observation,
            "source_measurement_observation_digest": split_observation[
                "measurement_observation_digest"
            ],
            "source_repeat_certification": split_certificate,
            "source_repeat_certification_digest": split_certificate[
                "source_repeat_certification_digest"
            ],
        }
    )
    split_facts = cast(dict[str, Any], build_facts(split_facts_fields))
    split_identity = deepcopy(identity)
    split_identity.update(
        {
            "source_measurement_digest": split_facts["source_measurement_digest"],
            "source_fact_snapshot": split_facts,
            "source_fact_snapshot_digest": digest_facts(split_facts),
            "source_measurement_projection": split_projection,
            "source_measurement_projection_digest": digest_morphology_projection(split_projection),
        }
    )
    _resign_identity(split_identity)
    split_entry = deepcopy(entry)
    raw_entries = cast(list[dict[str, Any]], split_raw["ordered_entries"])
    projection_entries = cast(list[dict[str, Any]], split_projection["ordered_entries"])
    split_entry.update(
        {
            "source_admission_event_id": split_identity["id"],
            "source_admission_content_digest": split_identity["content_digest"],
            "source_measurement_digest": split_facts["source_measurement_digest"],
            "source_fact_snapshot_digest": digest_facts(split_facts),
            "raw_measurement_authority_digest": digest_raw_measurement_authority(split_raw),
            "source_measurement_projection_digest": digest_morphology_projection(split_projection),
            "source_repeat_certification_digest": split_certificate[
                "source_repeat_certification_digest"
            ],
            "ordered_supported_measurements": [
                {
                    "schema_version": "mirror.demo/D02SupportedSourceMeasurement/v1",
                    "dimension_key": raw_entry["dimension_key"],
                    "raw_value_fixed18": raw_entry["raw_value_fixed18"],
                    "raw_confidence_fixed18": raw_entry["raw_confidence_fixed18"],
                    "raw_reliability_fixed18": raw_entry["raw_reliability_fixed18"],
                    "value_ppm": projection_entry["value_ppm"],
                    "confidence_ppm": projection_entry["confidence_ppm"],
                    "reliability_ppm": projection_entry["reliability_ppm"],
                    "unit": "FACE_HEIGHT_PPM",
                }
                for raw_entry, projection_entry in zip(raw_entries, projection_entries, strict=True)
            ],
        }
    )
    _resign_source_entry(split_entry)
    peer_entries = [split_entry]
    for ordinal, marker in enumerate(("2", "3", "4"), start=2):
        _, _, peer_entry = _facts_identity_manifest(source_ordinal=ordinal, source_marker=marker)
        peer_entries.append(peer_entry)
    peer_entries = _ordered_source_entries(peer_entries)
    split_entry = next(
        item
        for item in peer_entries
        if item["source_authority_key"] == split_identity["source_authority_key"]
    )
    manifest_digest = digest_source_manifest(peer_entries)
    record_source = deepcopy(split_entry)
    record_source["source_asset_id"] = split_subject["source_asset_id"]
    record_source["source_asset_sha256"] = split_subject["source_asset_sha256"]
    _, _, split_records, _ = _source_m3_records(
        manifest_digest,
        observation=split_observation,
        certificate=split_certificate,
        source_entry=record_source,
        use_authority_builder=False,
    )
    with pytest.raises(
        D02AuthorityError,
        match=r"identity/facts canonical row equality|observation/source Asset authority",
    ):
        validate_complete_source_graph(
            facts=split_facts,
            identity_row=split_identity,
            source_entry=split_entry,
            source_manifest_digest=manifest_digest,
            source_records=split_records,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_asset_id", _identifier("f")),
        ("source_asset_sha256", _digest("f")),
        ("result_asset_id", _identifier("f")),
        ("result_asset_sha256", _digest("f")),
        ("asset_variant_id", _identifier("f")),
        ("asset_variant_type", "demo_p3_p7_geometry_v2"),
        ("case_specification_digest", _digest("f")),
    ],
)
def test_report_rejects_caller_selected_or_drifted_variant_authority(
    field: str, replacement: str
) -> None:
    report, packets, variant_bindings = _complete_report_fixture(passing=True)
    forged_bindings = deepcopy(variant_bindings)
    first_case_id = cast(str, report["report_payload"]["ordered_case_manifest"][0]["case_id"])
    cast(dict[str, Any], forged_bindings[first_case_id])[field] = replacement
    with pytest.raises(D02AuthorityError, match="typed authority binding"):
        validate_report_row(
            report,
            source_graph_packets=packets,
            result_variant_bindings=forged_bindings,
        )


def test_demo_local_identity_fixture_replays_frozen_asset_and_source_key_authority() -> None:
    facts, identity, entry = _facts_identity_manifest()
    observation = cast(dict[str, Any], facts["source_measurement_observation"])
    subject = cast(dict[str, Any], observation["subject"])
    expected_key = mirror_demo_digest(
        "mirror.demo/SourceAuthorityKey/v1",
        {
            "source_authority_kind": "DEMO_LOCAL_IMPORTED_COPY",
            "source_output_id": facts["source_output_id"],
            "formal_canonical_asset_id": subject["source_asset_id"],
            "source_asset_sha256": facts["source_asset_sha256"],
            "source_receipt_digest": facts["source_receipt_digest"],
        },
    )

    assert identity["formal_synthetic_identity_id"] is None
    assert identity["formal_accepted_qa_run_id"] is None
    assert identity["formal_accepted_qa_snapshot_digest"] is None
    assert identity["admission_sequence"] == 1
    assert identity["admission_action"] == "ADMIT"
    assert identity["supersedes_id"] is None
    assert identity["formal_canonical_asset_id"] == subject["source_asset_id"]
    assert identity["formal_canonical_asset_sha256"] == facts["source_asset_sha256"]
    assert identity["source_authority_kind"] == "DEMO_LOCAL_IMPORTED_COPY"
    assert identity["source_authority_key"] == expected_key == entry["source_authority_key"]
    assert identity["original_formal_identity_id_status"] == "UNKNOWN_REDACTED_NOT_RECOVERED"
    assert facts["source_asset_mime_type"] == entry["source_asset_mime_type"] == "image/jpeg"
    validate_identity_row(identity, facts=facts)
    validate_source_manifest_entry(entry)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("formal_canonical_asset_id", None),
        ("formal_canonical_asset_sha256", None),
        ("formal_canonical_asset_id", _identifier("f")),
        ("formal_canonical_asset_sha256", _digest("f")),
        ("source_authority_kind", "LOCAL_SYNTHETIC"),
        ("source_authority_key", _digest("f")),
        ("original_formal_identity_id_status", "NONE"),
    ],
)
def test_demo_local_identity_rejects_resigned_shape_or_generated_key_drift(
    field: str, replacement: object
) -> None:
    facts, identity, _ = _facts_identity_manifest()
    forged = deepcopy(identity)
    forged[field] = replacement
    _resign_identity(forged)
    with pytest.raises(D02AuthorityError, match=r"null matrix|canonical row equality"):
        validate_identity_row(forged, facts=facts)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_asset_mime_type", "image/png"),
        ("original_formal_identity_id_status", "NONE"),
    ],
)
def test_recovered_facts_reject_frozen_local_literal_drift(field: str, replacement: object) -> None:
    facts, _, _ = _facts_identity_manifest()
    forged = deepcopy(facts)
    forged[field] = replacement
    with pytest.raises(D02AuthorityError, match="asset or attestation"):
        validate_facts(forged)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_asset_byte_size", 9_223_372_036_854_775_808),
        ("source_asset_width", 2_147_483_648),
        ("source_asset_height", 2_147_483_648),
    ],
)
def test_recovered_facts_reject_values_outside_postgresql_integer_ranges(
    field: str, replacement: int
) -> None:
    facts, _, _ = _facts_identity_manifest()
    forged = deepcopy(facts)
    forged[field] = replacement
    with pytest.raises(D02AuthorityError, match="asset or attestation"):
        validate_facts(forged)


def test_local_source_authority_key_uses_opaque_output_id_and_exact_preimage() -> None:
    expected = mirror_demo_digest(
        "mirror.demo/SourceAuthorityKey/v1",
        {
            "source_authority_kind": "DEMO_LOCAL_IMPORTED_COPY",
            "source_output_id": "registry.output-01",
            "formal_canonical_asset_id": _identifier("a"),
            "source_asset_sha256": _digest("b"),
            "source_receipt_digest": _digest("c"),
        },
    )
    assert (
        derive_local_source_authority_key(
            source_output_id="registry.output-01",
            source_asset_id=_identifier("a"),
            source_asset_sha256=_digest("b"),
            source_receipt_digest=_digest("c"),
        )
        == expected
    )
    for forbidden in ("../registry", "C:\\private", "https://example.com", "has space"):
        with pytest.raises(D02AuthorityError, match="opaque output ID"):
            derive_local_source_authority_key(
                source_output_id=forbidden,
                source_asset_id=_identifier("a"),
                source_asset_sha256=_digest("b"),
                source_receipt_digest=_digest("c"),
            )


def test_complete_source_graph_rejects_resigned_fact_snapshot_digest_split() -> None:
    facts, identity, entry = _facts_identity_manifest()
    forged = deepcopy(entry)
    forged["source_fact_snapshot_digest"] = _digest("9")
    _resign_source_entry(forged)
    entries = [forged]
    for ordinal, marker in enumerate(("2", "3", "4"), start=2):
        _, _, peer = _facts_identity_manifest(source_ordinal=ordinal, source_marker=marker)
        entries.append(peer)
    entries = _ordered_source_entries(entries)
    forged = next(
        item for item in entries if item["source_authority_key"] == identity["source_authority_key"]
    )
    manifest_digest = digest_source_manifest(entries)
    _, _, records, _ = _source_m3_records(
        manifest_digest,
        source_manifest_entries=entries,
        observation=cast(dict[str, Any], facts["source_measurement_observation"]),
        certificate=cast(dict[str, Any], facts["source_repeat_certification"]),
        source_entry=forged,
    )
    with pytest.raises(D02AuthorityError, match="scalar authority equality"):
        validate_complete_source_graph(
            facts=facts,
            identity_row=identity,
            source_entry=forged,
            source_manifest_digest=manifest_digest,
            source_records=records,
        )


def test_complete_source_graph_rejects_resigned_import_config_split() -> None:
    facts, identity, entry = _facts_identity_manifest()
    forged = deepcopy(entry)
    forged["import_config_digest"] = _digest("9")
    _resign_source_entry(forged)
    entries = [forged]
    for ordinal, marker in enumerate(("2", "3", "4"), start=2):
        _, _, peer = _facts_identity_manifest(source_ordinal=ordinal, source_marker=marker)
        entries.append(peer)
    entries = _ordered_source_entries(entries)
    forged = next(
        item for item in entries if item["source_authority_key"] == identity["source_authority_key"]
    )
    manifest_digest = _source_manifest_digest_oracle(entries)
    _, _, records, _ = _source_m3_records(
        manifest_digest,
        observation=cast(dict[str, Any], facts["source_measurement_observation"]),
        certificate=cast(dict[str, Any], facts["source_repeat_certification"]),
        source_entry=forged,
        use_authority_builder=False,
    )
    with pytest.raises(D02AuthorityError, match="local authority shape"):
        validate_complete_source_graph(
            facts=facts,
            identity_row=identity,
            source_entry=forged,
            source_manifest_digest=manifest_digest,
            source_records=records,
        )


_BOOLEAN_COERCIONS: tuple[object, ...] = ("true", 1, None)
_REVISION_9_BOOLEAN_FIELDS = frozenset(
    {
        "adult_synthetic_attested",
        "coordinates_finite",
        "coordinates_in_bounds",
        "repeat_gate_passed",
        "execution_succeeded",
        "direction_gate_passed",
        "target_min_gate_passed",
        "target_max_gate_passed",
        "control_drift_gate_passed",
        "magnitude_monotonicity_gate_passed",
        "measurement_gate_passed",
        "source_decode_valid",
        "result_decode_valid",
        "bounded_dimensions_passed",
        "source_checksum_unchanged",
        "m4_replay_bytes_equal",
        "m4_replay_dimensions_equal",
        "changed_pixel_count_equal",
        "changed_pixel_count_positive",
        "immutable_result_binding_passed",
        "exact_lineage_passed",
        "target_and_controls_complete",
        "structure_gate_passed",
        "background_seam",
        "disconnected_contour",
        "duplicated_feature",
        "warp_tear",
        "all_record_sha_unique",
        "source_sha_unique",
        "result_sha_unique",
        "source_result_sha_disjoint",
        "exact_sha_gate_passed",
        "automated_gate_passed",
        "manual_gate_passed",
        "side_gate_passed",
        "same_source_gate_passed",
        "opposed_direction_gate_passed",
        "equal_magnitude_gate_passed",
        "pair_side_gates_passed",
        "empty_lock_policy_gate_passed",
        "pair_gate_passed",
        "all_sixteen_side_gates_passed",
        "all_eight_pair_gates_passed",
        "all_manual_gates_passed",
        "global_exact_sha_gate_passed",
        "eligible",
        "selected",
        "localhost_and_docker_internal_network",
        "proxy_environment_present",
    }
)


def test_revision9_boolean_field_set_and_array_are_exhaustively_type_closed() -> None:
    assert d02_authority._PERSISTED_BOOLEAN_FIELDS == _REVISION_9_BOOLEAN_FIELDS
    assert d02_authority._PERSISTED_BOOLEAN_ARRAY_FIELDS == frozenset(
        {"result_m3_repeat_gate_results"}
    )
    for field in sorted(_REVISION_9_BOOLEAN_FIELDS):
        d02_authority._validate_persisted_boolean_closure({field: True})
        for replacement in _BOOLEAN_COERCIONS:
            with pytest.raises(D02AuthorityError, match="literal Boolean"):
                d02_authority._validate_persisted_boolean_closure({field: replacement})
    d02_authority._validate_persisted_boolean_closure(
        {"result_m3_repeat_gate_results": [True, True, True]}
    )
    for replacement in ("true", 1, None, [True, 1, True]):
        with pytest.raises(D02AuthorityError, match="Boolean array"):
            d02_authority._validate_persisted_boolean_closure(
                {"result_m3_repeat_gate_results": replacement}
            )


def test_revision9_resigned_execution_and_manual_boolean_coercions_fail_closed() -> None:
    m4_records, cases, _, authority = _m4_evidence()
    for replacement in (*_BOOLEAN_COERCIONS, False):
        forged_m4 = deepcopy(m4_records[0])
        forged_m4["execution_succeeded"] = replacement
        _resign_m4_record(forged_m4)
        with pytest.raises(D02AuthorityError, match=r"Boolean|execution"):
            validate_m4_execution_record(
                forged_m4, case_entry=cases[0], execution_authority=authority
            )

    structures, manuals, manual_cases, _, manual_m4, manual_authority = _structure_manual_evidence()
    manual_case_index = next(
        index for index, case in enumerate(manual_cases) if case["case_id"] == manuals[0]["case_id"]
    )
    for field in ("background_seam", "disconnected_contour", "duplicated_feature", "warp_tear"):
        for replacement in _BOOLEAN_COERCIONS:
            forged_manual = deepcopy(manuals[0])
            forged_manual[field] = replacement
            _resign_manual(forged_manual)
            with pytest.raises(D02AuthorityError, match="literal Boolean"):
                validate_manual_artifact_decision(
                    forged_manual,
                    case_entry=manual_cases[manual_case_index],
                    m4_first=manual_m4[manual_case_index * 2],
                    execution_authority=manual_authority,
                )
    for field in ("source_checksum_unchanged", "target_and_controls_complete"):
        for replacement in _BOOLEAN_COERCIONS:
            forged_structure = deepcopy(structures[0])
            forged_structure[field] = replacement
            _resign_structure(forged_structure)
            with pytest.raises(D02AuthorityError, match="literal Boolean"):
                validate_decode_structure_record(
                    forged_structure,
                    case_entry=manual_cases[0],
                    m4_first=manual_m4[0],
                    m4_second=manual_m4[1],
                    execution_authority=manual_authority,
                )


def test_revision9_exact_selection_and_network_boolean_coercions_fail_closed() -> None:
    images, _, sources, cases, m4_records, authority, result_asset_ids = _image_phash_graph()
    exact = cast(
        dict[str, Any],
        build_exact_duplicate_evidence(
            image_records=images,
            source_entries=sources,
            case_manifest=cases,
            m4_records=m4_records,
            execution_authority=authority,
            result_asset_ids=result_asset_ids,
        ),
    )
    for field in (
        "all_record_sha_unique",
        "source_sha_unique",
        "result_sha_unique",
        "source_result_sha_disjoint",
        "exact_sha_gate_passed",
    ):
        for replacement in _BOOLEAN_COERCIONS:
            forged_exact = deepcopy(exact)
            forged_exact[field] = replacement
            with pytest.raises(D02AuthorityError, match="literal Boolean"):
                validate_exact_duplicate_evidence(
                    forged_exact,
                    source_entries=sources,
                    case_manifest=cases,
                    m4_records=m4_records,
                    execution_authority=authority,
                    result_asset_ids=result_asset_ids,
                )

    report, _, _ = _complete_report_fixture(passing=True)
    payload = cast(dict[str, Any], report["report_payload"])
    pairs = cast(list[dict[str, Any]], payload["pair_quality_evidence"])
    dimensions = cast(list[dict[str, Any]], payload["dimension_eligibility"])
    selection = cast(list[dict[str, Any]], payload["fixed_priority_selection_trace"])
    for replacement in _BOOLEAN_COERCIONS:
        forged_dimensions = deepcopy(dimensions)
        forged_dimensions[0]["eligible"] = replacement
        _resign_dimension_record(forged_dimensions[0])
        with pytest.raises(D02AuthorityError, match="literal Boolean"):
            validate_dimension_eligibility_evidence(
                forged_dimensions,
                pair_records=pairs,
                exact_sha_gate_passed=True,
            )

        forged_selection = deepcopy(selection)
        forged_selection[0]["selected"] = replacement
        _resign_selection_record(forged_selection[0])
        with pytest.raises(D02AuthorityError, match="literal Boolean"):
            validate_selection_trace(forged_selection, dimension_records=dimensions)

    boundary: dict[str, Any] = {
        "schema_version": "mirror.demo/D02NetworkRuntimeBoundary/v2",
        "public_internet_egress": "DENIED",
        "localhost_and_docker_internal_network": True,
        "proxy_environment_present": False,
        "production_provider_calls": 0,
        "runtime_generation_calls": 0,
        "boundary_receipt_digest": _digest("a"),
    }
    validate_network_runtime_boundary(boundary)
    for field in ("localhost_and_docker_internal_network", "proxy_environment_present"):
        for replacement in _BOOLEAN_COERCIONS:
            forged_boundary = deepcopy(boundary)
            forged_boundary[field] = replacement
            with pytest.raises(D02AuthorityError, match="literal Boolean"):
                validate_network_runtime_boundary(forged_boundary)
    for field, wrong_literal in (
        ("localhost_and_docker_internal_network", False),
        ("proxy_environment_present", True),
    ):
        forged_boundary = deepcopy(boundary)
        forged_boundary[field] = wrong_literal
        with pytest.raises(D02AuthorityError, match="network and runtime boundary"):
            validate_network_runtime_boundary(forged_boundary)
