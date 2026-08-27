from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import cast

import pytest
from test_demo_d02_authority import _complete_report_fixture, _facts_identity_manifest

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as r2
from mirror_api.demo_d02_r2_authority import (
    R2_ADMISSION_CONFIG_DIGEST,
    R2_EVIDENCE_ROOT_ID,
    R2_GENERATION_RECEIPT_SCHEMA,
    R2_IDENTITY_ID_DOMAIN,
    R2_IDENTITY_SCHEMA,
    R2_RECORD_ID_DOMAIN,
    R2_SOURCE_AUTHORITY_KIND,
    R2_SOURCE_AUTHORITY_RECORD_SCHEMA,
    R2_SOURCE_AUTHORITY_SCHEMA,
    R2_SOURCE_ENTRY_SCHEMA,
    R2_SOURCE_QA_SCHEMA,
    D02R2AuthorityError,
    build_r2_case_manifest_entry,
    build_r2_decode_structure_record,
    build_r2_exact_duplicate_evidence,
    build_r2_image_authority_evidence,
    build_r2_m4_execution_record,
    build_r2_manual_artifact_decision,
    build_r2_measurement_gate,
    build_r2_network_runtime_boundary,
    build_r2_pair_screening_evidence,
    build_r2_phash_observation_evidence,
    build_r2_question_bank_row,
    build_r2_question_pair_row,
    build_r2_report_row,
    build_r2_result_m3_record,
    build_r2_source_m3_record,
    derive_r2_source_authority_key,
    digest_r2_facts,
    validate_r2_admission_packet,
    validate_r2_generation_receipt,
    validate_r2_question_bank_row,
    validate_r2_question_pair_row,
    validate_r2_report_row,
)
from mirror_api.demo_measurement_quality import (
    mirror_demo_digest,
    replay_measurement_config_digest,
)


def _digest(label: str) -> str:
    return mirror_demo_digest("mirror.demo/D02R2TestDigest/v1", {"label": label})


def _receipt() -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema_version": R2_GENERATION_RECEIPT_SCHEMA,
        "candidate_ordinal": 1,
        "producer_task_id": "P3_P7_D02_R2_SOURCE_COHORT_01",
        "dispatch_epoch": 1,
        "execution_contract_digest": _digest("contract"),
        "evidence_root_id": R2_EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": _digest("root"),
        "generation_preregistration_digest": _digest("preregistration"),
        "source_allocation_manifest_digest": _digest("allocation"),
        "source_producer_dispatch_digest": _digest("dispatch"),
        "source_output_id": "r2-source-0001",
        "output_name_receipt_digest": _digest("name"),
        "output_seal_receipt_digest": _digest("seal"),
        "registry_commit_receipt_digest": _digest("commit"),
        "generation_capability_authority_digest": _digest("capability"),
        "generation_request_policy_digest": _digest("request"),
        "generation_result_provenance_digest": _digest("provenance"),
        "source_provenance_output_id": "r2-provenance-0001",
        "source_provenance_name_receipt_digest": _digest("provenance-name"),
        "source_provenance_seal_receipt_digest": _digest("provenance-seal"),
        "source_provenance_registry_commit_receipt_digest": _digest("provenance-commit"),
        "source_asset_sha256": _digest("asset"),
        "source_asset_byte_size": 1024,
        "source_asset_mime_type": "image/jpeg",
        "source_asset_width": 32,
        "source_asset_height": 32,
        "synthetic_only_attested": True,
        "real_person_reference_used": False,
    }
    receipt["receipt_digest"] = mirror_demo_digest(R2_GENERATION_RECEIPT_SCHEMA, receipt)
    return receipt


def _resign(payload: dict[str, object], schema: str, digest_key: str) -> None:
    payload[digest_key] = mirror_demo_digest(
        schema, {key: value for key, value in payload.items() if key != digest_key}
    )


def _resign_legacy_typed(payload: dict[str, object], schema: str, digest_key: str) -> None:
    payload[digest_key] = mirror_demo_digest(
        schema,
        {key: value for key, value in payload.items() if key not in {"schema_version", digest_key}},
    )


def _resign_r2_record(payload: dict[str, object], schema: str) -> None:
    payload["record_digest"] = mirror_demo_digest(
        schema,
        {
            key: value
            for key, value in payload.items()
            if key not in {"schema_version", "record_digest"}
        },
    )


def _resign_result_chain(report: dict[str, object], case_index: int, repeat_index: int) -> None:
    """Re-sign ResultM3 -> certificate -> Gate after a raw observation mutation."""
    payload = cast(dict[str, object], report["report_payload"])
    record = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])[
        case_index * 3 + repeat_index
    ]
    observation = cast(dict[str, object], record["measurement_observation"])
    _resign_legacy_typed(
        observation,
        "mirror.demo/D02MeasurementObservation/v1",
        "measurement_observation_digest",
    )
    record["measurement_observation_digest"] = observation["measurement_observation_digest"]
    _resign_r2_record(record, "mirror.demo/D02ResultM3RepeatRecord/v3")
    gate = cast(list[dict[str, object]], payload["measurement_gate_evidence"])[case_index]
    measurement = cast(list[dict[str, object]], gate["ordered_result_repeat_measurements"])[
        repeat_index
    ]
    measurement["result_m3_record_digest"] = record["record_digest"]
    certificate = cast(dict[str, object], gate["result_repeat_certification"])
    binding = cast(list[dict[str, object]], certificate["ordered_repeat_bindings"])[repeat_index]
    binding["measurement_observation_digest"] = record["measurement_observation_digest"]
    _resign_legacy_typed(
        certificate,
        "mirror.demo/D02ResultRepeatDeterminismCertification/v1",
        "result_repeat_certification_digest",
    )
    gate["result_repeat_certification_digest"] = certificate["result_repeat_certification_digest"]
    _resign_r2_record(gate, "mirror.demo/D02MeasurementGateRecord/v5")


_RESULT_CERTIFICATE_BINDING_KEYS = (
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


def _fixed18_from_units(value: int) -> str:
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    return f"{sign}{magnitude // 10**18}.{magnitude % 10**18:018d}"


def _rebind_r2_gate_certificate(gate: dict[str, object], records: list[dict[str, object]]) -> None:
    certificate = deepcopy(cast(dict[str, object], gate["result_repeat_certification"]))
    certificate["ordered_repeat_bindings"] = [
        {key: record[key] for key in _RESULT_CERTIFICATE_BINDING_KEYS} for record in records
    ]
    _resign_legacy_typed(
        certificate,
        "mirror.demo/D02ResultRepeatDeterminismCertification/v1",
        "result_repeat_certification_digest",
    )
    gate["result_repeat_certification"] = certificate
    gate["result_repeat_certification_digest"] = certificate["result_repeat_certification_digest"]


def _resign_r2_report_envelope(report: dict[str, object]) -> None:
    report_digest = mirror_demo_digest(
        r2.R2_REPORT_SCHEMA, cast(dict[str, object], report["report_payload"])
    )
    report["report_digest"] = report_digest
    canonical = r2._report_canonical(report)
    report["canonical_payload"] = canonical
    report["content_digest"] = mirror_demo_digest(r2.R2_REPORT_SCHEMA, canonical)
    report["id"] = mirror_demo_digest(
        r2.R2_REPORT_ID_DOMAIN,
        {
            "report_digest": report_digest,
            "source_manifest_digest": report["source_manifest_digest"],
            "case_manifest_digest": report["case_manifest_digest"],
        },
    )[:32]


_R2_MANDATORY_DIGEST_MUTATIONS = (
    "json_null",
    "missing",
    "number",
    "boolean",
    "array",
    "object",
    "empty_string",
    "uppercase_hexadecimal",
    "wrong_length",
    "wrong_well_formed_digest",
    "cross_source_substitution",
)
_R2_MANDATORY_DIGEST_ATTACK_CASES = tuple(
    (record_group, leaf, mutation)
    for record_group, leaves in (
        ("source_m3_repeat_evidence", r2.R2_SOURCE_M3_MANDATORY_DIGEST_LEAVES),
        ("result_m3_repeat_evidence", r2.R2_RESULT_M3_MANDATORY_DIGEST_LEAVES),
    )
    for leaf in leaves
    for mutation in _R2_MANDATORY_DIGEST_MUTATIONS
)


def _mandatory_digest_attack_value(
    *, mutation: str, original: object, cross_source_digest: str
) -> object:
    if mutation == "json_null":
        return None
    if mutation == "number":
        return 7
    if mutation == "boolean":
        return True
    if mutation == "array":
        return [cross_source_digest]
    if mutation == "object":
        return {"digest": cross_source_digest}
    if mutation == "empty_string":
        return ""
    if mutation == "uppercase_hexadecimal":
        return "A" * 64
    if mutation == "wrong_length":
        return "0" * 63
    if mutation == "wrong_well_formed_digest":
        candidate = "0" * 64
        return candidate if candidate != original else "f" * 64
    if mutation == "cross_source_substitution":
        return cross_source_digest
    raise AssertionError(f"unsupported mandatory digest mutation: {mutation}")


@lru_cache(maxsize=1)
def _mandatory_digest_attack_template() -> tuple[dict[str, object], list[dict[str, object]]]:
    return _report()


def _build_fully_resigned_mandatory_digest_attack(
    *, record_group: str, leaf: str, mutation: str
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Build one outer-authority-resigned malformed SourceM3/ResultM3 attack."""

    report, packets = _mandatory_digest_attack_template()
    forged = dict(report)
    base_payload = cast(dict[str, object], report["report_payload"])
    payload = dict(base_payload)
    forged["report_payload"] = payload
    records = list(cast(list[dict[str, object]], base_payload[record_group]))
    payload[record_group] = records
    records[0] = deepcopy(records[0])
    target = records[0]
    donor_index = 3 if record_group == "source_m3_repeat_evidence" else 36
    donor = records[donor_index]
    donor_value = donor.get(leaf)
    fallback_key = (
        "source_asset_sha256" if record_group == "source_m3_repeat_evidence" else "result_sha256"
    )
    cross_source_digest = donor_value if isinstance(donor_value, str) else donor[fallback_key]
    if cross_source_digest == target.get(leaf):
        cross_source_digest = donor[fallback_key]
    assert isinstance(cross_source_digest, str)
    assert cross_source_digest != target.get(leaf)

    if mutation == "missing":
        target.pop(leaf)
    else:
        target[leaf] = _mandatory_digest_attack_value(
            mutation=mutation,
            original=target.get(leaf),
            cross_source_digest=cross_source_digest,
        )

    if leaf != "record_digest":
        _resign_r2_record(target, cast(str, target["schema_version"]))

    if record_group == "result_m3_repeat_evidence":
        gates = list(cast(list[dict[str, object]], base_payload["measurement_gate_evidence"]))
        gate = deepcopy(gates[0])
        gates[0] = gate
        payload["measurement_gate_evidence"] = gates
        measurement = cast(list[dict[str, object]], gate["ordered_result_repeat_measurements"])[0]
        if "record_digest" in target:
            measurement["result_m3_record_digest"] = target["record_digest"]
        else:
            measurement.pop("result_m3_record_digest", None)

        certificate = deepcopy(cast(dict[str, object], gate["result_repeat_certification"]))
        subject = cast(dict[str, object], certificate["subject"])
        if leaf in subject:
            if leaf in target:
                subject[leaf] = target[leaf]
            else:
                subject.pop(leaf, None)
        bindings = cast(list[dict[str, object]], certificate["ordered_repeat_bindings"])
        if leaf in _RESULT_CERTIFICATE_BINDING_KEYS:
            if leaf in target:
                bindings[0][leaf] = target[leaf]
            else:
                bindings[0].pop(leaf, None)
        _resign_legacy_typed(
            certificate,
            "mirror.demo/D02ResultRepeatDeterminismCertification/v1",
            "result_repeat_certification_digest",
        )
        gate["result_repeat_certification"] = certificate
        gate["result_repeat_certification_digest"] = certificate[
            "result_repeat_certification_digest"
        ]
        _resign_r2_record(gate, cast(str, gate["schema_version"]))

    _resign_r2_report_envelope(forged)
    return forged, list(packets)


def _resign_r2_image_record(record: dict[str, object]) -> None:
    schema = cast(str, record["schema_version"])
    record["image_record_id"] = r2._r2_image_record_id(schema, record)
    record["image_record_digest"] = r2._r2_image_record_digest(schema, record)


def _resign_r2_phash_matrix(evidence: dict[str, object]) -> None:
    signatures = cast(list[dict[str, object]], evidence["ordered_record_signatures"])
    for signature in signatures:
        signature["signature_digest"] = r2._r2_phash_signature_digest(signature)
    comparisons = cast(list[dict[str, object]], evidence["comparisons"])
    ordinal = 1
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index + 1 :]:
            comparison = comparisons[ordinal - 1]
            comparison.update(
                comparison_ordinal=ordinal,
                left_image_record_ordinal=left["image_record_ordinal"],
                left_image_record_id=left["image_record_id"],
                left_signature_digest=left["signature_digest"],
                right_image_record_ordinal=right["image_record_ordinal"],
                right_image_record_id=right["image_record_id"],
                right_signature_digest=right["signature_digest"],
                hamming_distance=(
                    int(cast(str, left["phash_hex"]), 16) ^ int(cast(str, right["phash_hex"]), 16)
                ).bit_count(),
            )
            comparison["comparison_digest"] = r2._r2_phash_comparison_digest(comparison)
            ordinal += 1


def _resign_r2_network_boundary(boundary: dict[str, object]) -> None:
    boundary["boundary_receipt_digest"] = mirror_demo_digest(
        r2.R2_NETWORK_BOUNDARY_RECEIPT_DOMAIN,
        {
            key: cast(r2.JsonValue, value)
            for key, value in boundary.items()
            if key not in {"schema_version", "boundary_receipt_digest"}
        },
    )


def _replace_r2_case_with_unsupported_evidence(
    report: dict[str, object], *, case_index: int
) -> None:
    payload = cast(dict[str, object], report["report_payload"])
    cases = cast(list[dict[str, object]], payload["ordered_case_manifest"])
    case = cases[case_index]
    result_evidence = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])
    original_records = result_evidence[case_index * 3 : case_index * 3 + 3]
    rewritten_records: list[dict[str, object]] = []
    for original in original_records:
        fields = {
            key: deepcopy(value)
            for key, value in original.items()
            if key not in {"schema_version", "result_m3_record_id", "record_digest"}
        }
        observation = cast(dict[str, object], fields["measurement_observation"])
        target = next(
            entry
            for entry in cast(list[dict[str, object]], observation["ordered_measurements"])
            if entry["dimension_key"] == case["dimension_key"]
        )
        target.update(
            support_state="UNSUPPORTED",
            raw_value_fixed18=None,
            observability_state="NOT_COMPUTABLE",
            raw_observability_fixed18=None,
            unsupported_reason="RUNTIME_UNSUPPORTED",
        )
        _resign_legacy_typed(
            observation,
            "mirror.demo/D02MeasurementObservation/v1",
            "measurement_observation_digest",
        )
        fields.update(
            measurement_observation_digest=observation["measurement_observation_digest"],
            observation_state="UNSUPPORTED_EXPLICIT",
            repeat_gate_passed=False,
        )
        rewritten_records.append(build_r2_result_m3_record(fields))
    result_evidence[case_index * 3 : case_index * 3 + 3] = rewritten_records

    gate_evidence = cast(list[dict[str, object]], payload["measurement_gate_evidence"])
    gate = deepcopy(gate_evidence[case_index])
    gate["ordered_result_repeat_measurements"] = [
        {
            "schema_version": "mirror.demo/D02UnsupportedResultMeasurement/v1",
            "repeat_index": record["repeat_index"],
            "result_m3_record_digest": record["record_digest"],
            "unsupported_dimension_key": case["dimension_key"],
            "unsupported_reason": "RUNTIME_UNSUPPORTED",
            "measurement_gate_passed": False,
        }
        for record in rewritten_records
    ]
    gate["measurement_evaluation_state"] = "UNSUPPORTED_EXPLICIT"
    gate["gate_evaluation"] = {
        "schema_version": "mirror.demo/D02UnsupportedMeasurementGateEvaluation/v1",
        "unsupported_repeat_indexes": [1, 2, 3],
        "ordered_unsupported_reasons": ["RUNTIME_UNSUPPORTED"] * 3,
        "measurement_gate_passed": False,
    }
    _rebind_r2_gate_certificate(gate, rewritten_records)
    gate_evidence[case_index] = build_r2_measurement_gate(
        {
            key: value
            for key, value in gate.items()
            if key not in {"schema_version", "record_digest"}
        }
    )
    _resign_r2_report_envelope(report)


def _replace_r2_case_with_supported_delta(
    report: dict[str, object], *, case_index: int, absolute_delta_units: int
) -> None:
    payload = cast(dict[str, object], report["report_payload"])
    cases = cast(list[dict[str, object]], payload["ordered_case_manifest"])
    case = cases[case_index]
    gate_evidence = cast(list[dict[str, object]], payload["measurement_gate_evidence"])
    original_gate = gate_evidence[case_index]
    source_units = legacy._fixed18_units(
        cast(dict[str, object], original_gate["source_target_measurement"])["raw_value_fixed18"],
        "test source target",
    )
    signed_delta_units = (
        absolute_delta_units if case["direction"] == "INCREASE" else -absolute_delta_units
    )
    result_units = source_units + signed_delta_units

    result_evidence = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])
    original_records = result_evidence[case_index * 3 : case_index * 3 + 3]
    rewritten_records: list[dict[str, object]] = []
    for original in original_records:
        fields = {
            key: deepcopy(value)
            for key, value in original.items()
            if key not in {"schema_version", "result_m3_record_id", "record_digest"}
        }
        observation = cast(dict[str, object], fields["measurement_observation"])
        target = next(
            entry
            for entry in cast(list[dict[str, object]], observation["ordered_measurements"])
            if entry["dimension_key"] == case["dimension_key"]
        )
        target["raw_value_fixed18"] = _fixed18_from_units(result_units)
        _resign_legacy_typed(
            observation,
            "mirror.demo/D02MeasurementObservation/v1",
            "measurement_observation_digest",
        )
        fields["measurement_observation_digest"] = observation["measurement_observation_digest"]
        rewritten_records.append(build_r2_result_m3_record(fields))
    result_evidence[case_index * 3 : case_index * 3 + 3] = rewritten_records

    gate = deepcopy(original_gate)
    measurements = cast(list[dict[str, object]], gate["ordered_result_repeat_measurements"])
    for measurement, record in zip(measurements, rewritten_records, strict=True):
        measurement.update(
            result_m3_record_digest=record["record_digest"],
            raw_result_target_fixed18=_fixed18_from_units(result_units),
            raw_signed_target_delta_fixed18=_fixed18_from_units(signed_delta_units),
            raw_target_absolute_delta_fixed18=_fixed18_from_units(absolute_delta_units),
            measured_signed_delta_ppm=legacy._ppm_from_units(signed_delta_units),
            target_absolute_delta_ppm=legacy._ppm_from_units(absolute_delta_units),
            direction_gate_passed=True,
            target_min_gate_passed=True,
            target_max_gate_passed=True,
            control_drift_gate_passed=True,
        )
    evaluation = cast(dict[str, object], gate["gate_evaluation"])
    evaluation.update(
        direction_gate_passed=True,
        target_min_gate_passed=True,
        target_max_gate_passed=True,
        control_drift_gate_passed=True,
        magnitude_monotonicity_gate_passed=True,
        measurement_gate_passed=True,
    )
    _rebind_r2_gate_certificate(gate, rewritten_records)
    gate_evidence[case_index] = build_r2_measurement_gate(
        {
            key: value
            for key, value in gate.items()
            if key not in {"schema_version", "record_digest"}
        }
    )
    _resign_r2_report_envelope(report)


def _packet(marker: str, *, source_ordinal: int = 1) -> dict[str, object]:
    """Construct a complete public G→A→Q→P→Facts→Identity→manifest replay."""
    facts, legacy_identity, legacy_entry = _facts_identity_manifest(
        source_marker=marker, source_ordinal=source_ordinal
    )
    receipt = _receipt()
    receipt.update(
        candidate_ordinal=source_ordinal,
        source_output_id=facts["source_output_id"],
        source_asset_sha256=facts["source_asset_sha256"],
        source_asset_byte_size=facts["source_asset_byte_size"],
        source_asset_mime_type=facts["source_asset_mime_type"],
        source_asset_width=facts["source_asset_width"],
        source_asset_height=facts["source_asset_height"],
        source_provenance_output_id=f"r2-provenance-{marker}",
        output_name_receipt_digest=_digest(f"output-name-{marker}"),
        output_seal_receipt_digest=_digest(f"output-seal-{marker}"),
        registry_commit_receipt_digest=_digest(f"registry-commit-{marker}"),
        source_provenance_name_receipt_digest=_digest(f"provenance-name-{marker}"),
        source_provenance_seal_receipt_digest=_digest(f"provenance-seal-{marker}"),
        source_provenance_registry_commit_receipt_digest=_digest(
            f"provenance-registry-commit-{marker}"
        ),
    )
    _resign(receipt, R2_GENERATION_RECEIPT_SCHEMA, "receipt_digest")

    authority: dict[str, object] = {
        "schema_version": R2_SOURCE_AUTHORITY_SCHEMA,
        "source_ordinal": receipt["candidate_ordinal"],
        "source_asset_id": legacy_identity["formal_canonical_asset_id"],
        "source_provenance_digest": receipt["generation_result_provenance_digest"],
        "authority_kind": R2_SOURCE_AUTHORITY_KIND,
    }
    for key in (
        "execution_contract_digest",
        "evidence_root_id",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_output_id",
        "source_asset_sha256",
        "source_asset_byte_size",
        "source_asset_mime_type",
        "source_asset_width",
        "source_asset_height",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "generation_request_policy_digest",
        "source_provenance_output_id",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
        "synthetic_only_attested",
        "real_person_reference_used",
    ):
        authority[key] = receipt[key]
    authority["source_generation_receipt_digest"] = receipt["receipt_digest"]
    _resign(authority, R2_SOURCE_AUTHORITY_SCHEMA, "authority_digest")

    source_key = derive_r2_source_authority_key(
        source_output_id=cast(str, authority["source_output_id"]),
        source_asset_id=cast(str, authority["source_asset_id"]),
        source_asset_sha256=cast(str, authority["source_asset_sha256"]),
        source_generation_receipt_digest=cast(str, authority["source_generation_receipt_digest"]),
        source_authority_digest=cast(str, authority["authority_digest"]),
    )
    qa: dict[str, object] = {
        "schema_version": R2_SOURCE_QA_SCHEMA,
        "source_authority_key": source_key,
        "source_authority_digest": authority["authority_digest"],
        "qa_policy_digest": _digest(f"qa-policy-{marker}"),
        "decode_record_digest": _digest(f"decode-{marker}"),
        "ordered_review_decision_digests": [
            _digest(f"review-{marker}-{index}") for index in range(6)
        ],
        "adult_synthetic_attested": True,
        "qa_state": "PASSED",
    }
    for key in (
        "source_ordinal",
        "execution_contract_digest",
        "evidence_root_id",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_output_id",
        "source_asset_id",
        "source_asset_sha256",
        "source_asset_byte_size",
        "source_asset_mime_type",
        "source_asset_width",
        "source_asset_height",
        "source_generation_receipt_digest",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "generation_request_policy_digest",
        "source_provenance_digest",
        "source_provenance_output_id",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
        "synthetic_only_attested",
        "real_person_reference_used",
    ):
        qa[key] = authority[key]
    _resign(qa, R2_SOURCE_QA_SCHEMA, "source_qa_snapshot_digest")

    supporting: dict[str, object] = {
        "schema_version": R2_SOURCE_AUTHORITY_RECORD_SCHEMA,
        "created_at": "2026-08-26T00:00:00Z",
        "source_qa_snapshot_digest": qa["source_qa_snapshot_digest"],
        "adult_synthetic_attested": True,
        "authority_state": "PRINCIPAL_ACCEPTED",
    }
    for key in (
        "execution_contract_digest",
        "evidence_root_id",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_ordinal",
        "source_output_id",
        "source_asset_id",
        "source_asset_sha256",
        "source_asset_byte_size",
        "source_asset_mime_type",
        "source_asset_width",
        "source_asset_height",
        "source_generation_receipt_digest",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "generation_request_policy_digest",
        "source_provenance_digest",
        "source_provenance_output_id",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
        "synthetic_only_attested",
        "real_person_reference_used",
    ):
        supporting[key] = authority[key]
    supporting["source_authority_key"] = source_key
    supporting["source_authority_digest"] = authority["authority_digest"]
    canonical_supporting = {
        key: supporting[key]
        for key in supporting
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    supporting["canonical_payload"] = canonical_supporting
    supporting["content_digest"] = mirror_demo_digest(
        R2_SOURCE_AUTHORITY_RECORD_SCHEMA, canonical_supporting
    )
    supporting["id"] = mirror_demo_digest(
        R2_RECORD_ID_DOMAIN,
        {
            key: supporting[key]
            for key in (
                "execution_contract_digest",
                "evidence_root_id",
                "root_name_receipt_digest",
                "generation_preregistration_digest",
                "source_allocation_manifest_digest",
                "source_producer_dispatch_digest",
                "source_ordinal",
                "source_output_id",
                "source_authority_key",
                "source_authority_digest",
                "source_qa_snapshot_digest",
                "content_digest",
            )
        },
    )[:32]

    facts = deepcopy(facts)
    facts.update(
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        original_formal_identity_id_status="NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE",
    )
    identity = deepcopy(legacy_identity)
    identity.update(
        schema_version=R2_IDENTITY_SCHEMA,
        formal_synthetic_identity_id=None,
        formal_canonical_asset_id=supporting["source_asset_id"],
        formal_canonical_asset_sha256=supporting["source_asset_sha256"],
        formal_accepted_qa_run_id=None,
        formal_accepted_qa_snapshot_digest=None,
        admission_config_digest=R2_ADMISSION_CONFIG_DIGEST,
        source_output_id=supporting["source_output_id"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot=facts,
        source_fact_snapshot_digest=digest_r2_facts(facts),
        original_formal_identity_id_status=facts["original_formal_identity_id_status"],
        importer_version="demo-d02-r2-identity-importer-v1",
        import_config_digest=R2_ADMISSION_CONFIG_DIGEST,
        source_authority_kind=R2_SOURCE_AUTHORITY_KIND,
        source_authority_key=source_key,
        r2_source_authority_record_id=supporting["id"],
    )
    identity_canonical = {
        key: value
        for key, value in identity.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    identity["canonical_payload"] = identity_canonical
    identity["content_digest"] = mirror_demo_digest(R2_IDENTITY_SCHEMA, identity_canonical)
    identity["id"] = mirror_demo_digest(
        R2_IDENTITY_ID_DOMAIN,
        {
            "source_authority_kind": R2_SOURCE_AUTHORITY_KIND,
            "source_authority_key": source_key,
            "r2_source_authority_record_id": supporting["id"],
            "admission_sequence": identity["admission_sequence"],
            "admission_action": identity["admission_action"],
            "supersedes_id": identity["supersedes_id"],
            "admission_config_digest": identity["admission_config_digest"],
            "canonical_payload_digest": identity["content_digest"],
        },
    )[:32]
    entry = deepcopy(legacy_entry)
    entry.update(
        schema_version=R2_SOURCE_ENTRY_SCHEMA,
        source_authority_kind=R2_SOURCE_AUTHORITY_KIND,
        source_authority_key=source_key,
        source_admission_event_id=identity["id"],
        source_admission_content_digest=identity["content_digest"],
        source_output_id=supporting["source_output_id"],
        source_asset_id=supporting["source_asset_id"],
        source_asset_sha256=supporting["source_asset_sha256"],
        source_asset_byte_size=supporting["source_asset_byte_size"],
        source_asset_mime_type=supporting["source_asset_mime_type"],
        source_asset_width=supporting["source_asset_width"],
        source_asset_height=supporting["source_asset_height"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot_digest=identity["source_fact_snapshot_digest"],
        adult_synthetic_attested=True,
        original_formal_identity_id_status=facts["original_formal_identity_id_status"],
        import_config_digest=R2_ADMISSION_CONFIG_DIGEST,
        r2_source_authority_record_id=supporting["id"],
    )
    entry["record_digest"] = mirror_demo_digest(
        R2_SOURCE_ENTRY_SCHEMA,
        {
            key: value
            for key, value in entry.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    return {
        "generation_receipt": receipt,
        "source_authority": authority,
        "source_qa_snapshot": qa,
        "supporting_row": supporting,
        "facts": facts,
        "identity_row": identity,
        "source_manifest_entry": entry,
        "source_manifest_digest": _digest(f"manifest-{marker}"),
    }


def test_generation_receipt_replays_and_rejects_one_field_splice() -> None:
    receipt = _receipt()
    assert validate_r2_generation_receipt(receipt) == receipt

    spliced = deepcopy(receipt)
    spliced["source_provenance_output_id"] = "r2-provenance-0002"
    with pytest.raises(D02R2AuthorityError, match="digest does not replay"):
        validate_r2_generation_receipt(spliced)


def test_r2_source_key_binds_authority_digest_not_only_asset() -> None:
    common = {
        "source_output_id": "r2-source-0001",
        "source_asset_id": "1" * 32,
        "source_asset_sha256": _digest("asset"),
        "source_generation_receipt_digest": _digest("receipt"),
    }
    first = derive_r2_source_authority_key(**common, source_authority_digest=_digest("authority-a"))
    second = derive_r2_source_authority_key(
        **common, source_authority_digest=_digest("authority-b")
    )

    assert first != second


def test_complete_admission_packet_replays_and_rejects_resigned_splices() -> None:
    packet = _packet("a")
    validate_r2_admission_packet(packet)

    spliced = deepcopy(packet)
    spliced["facts"]["source_provenance_digest"] = _digest("forged-provenance")
    with pytest.raises(D02R2AuthorityError, match="facts/supporting-row equality"):
        validate_r2_admission_packet(spliced)

    other = _packet("b")
    fully_resigned_cross_source = deepcopy(packet)
    for key in ("facts", "identity_row", "source_manifest_entry"):
        fully_resigned_cross_source[key] = other[key]
    with pytest.raises(D02R2AuthorityError, match="facts/supporting-row equality"):
        validate_r2_admission_packet(fully_resigned_cross_source)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("source_asset_width", 33),
        ("source_landmark_digest", _digest("forged-entry-landmark")),
        ("raw_measurement_authority_digest", _digest("forged-entry-raw-authority")),
        ("runtime_manifest_digest", _digest("forged-entry-runtime")),
    ),
)
def test_r2_admission_rejects_resigned_source_entry_projection(
    field: str, replacement: object
) -> None:
    packet = _packet("a")
    entry = cast(dict[str, object], packet["source_manifest_entry"])
    entry[field] = replacement
    _resign_r2_record(entry, R2_SOURCE_ENTRY_SCHEMA)

    with pytest.raises((D02R2AuthorityError, legacy.D02AuthorityError)):
        validate_r2_admission_packet(packet)


def test_r2_admission_rejects_resigned_identity_and_entry_projection() -> None:
    packet = _packet("a")
    identity = cast(dict[str, object], packet["identity_row"])
    identity["source_landmark_digest"] = _digest("forged-identity-landmark")
    canonical = {
        key: value
        for key, value in identity.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    identity["canonical_payload"] = canonical
    identity["content_digest"] = mirror_demo_digest(R2_IDENTITY_SCHEMA, canonical)
    identity["id"] = mirror_demo_digest(
        R2_IDENTITY_ID_DOMAIN,
        {
            "source_authority_kind": identity["source_authority_kind"],
            "source_authority_key": identity["source_authority_key"],
            "r2_source_authority_record_id": identity["r2_source_authority_record_id"],
            "admission_sequence": identity["admission_sequence"],
            "admission_action": identity["admission_action"],
            "supersedes_id": identity["supersedes_id"],
            "admission_config_digest": identity["admission_config_digest"],
            "canonical_payload_digest": identity["content_digest"],
        },
    )[:32]
    entry = cast(dict[str, object], packet["source_manifest_entry"])
    entry.update(
        source_admission_event_id=identity["id"],
        source_admission_content_digest=identity["content_digest"],
        source_landmark_digest=identity["source_landmark_digest"],
    )
    _resign_r2_record(entry, R2_SOURCE_ENTRY_SCHEMA)

    with pytest.raises(D02R2AuthorityError, match="identity/facts projection"):
        validate_r2_admission_packet(packet)


def _dimension_records(
    pairs: list[dict[str, object]], *, exact_sha_gate_passed: bool = True
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index, dimension in enumerate(legacy.CASE_DIMENSIONS):
        pair_digests: list[str] = []
        side_digests: list[str] = []
        side_entries: list[dict[str, object]] = []
        pair_entries: list[dict[str, object]] = []
        for source_index in range(4):
            for magnitude_index in range(2):
                wrapper = pairs[source_index * 6 + index * 2 + magnitude_index]
                payload = cast(dict[str, object], wrapper["pair_screening_record_payload"])
                pair_digests.append(
                    cast(
                        str,
                        pairs[source_index * 6 + index * 2 + magnitude_index][
                            "pair_screening_record_digest"
                        ],
                    )
                )
                for side_label, side_name in (("LEFT", "left"), ("RIGHT", "right")):
                    side = cast(dict[str, object], payload[side_name])
                    side_digests.append(cast(str, side["automated_gate_digest"]))
                    side_entries.append(
                        {
                            "schema_version": legacy.DIMENSION_SIDE_GATE_SCHEMA,
                            "source_ordinal": source_index + 1,
                            "magnitude_ppm": (15_000, 30_000)[magnitude_index],
                            "side": side_label,
                            "case_id": side["case_id"],
                            "automated_gate_digest": side["automated_gate_digest"],
                            "manual_decision_digest": side["manual_decision_digest"],
                            "automated_gate_passed": True,
                            "manual_gate_passed": True,
                            "side_gate_passed": True,
                        }
                    )
                pair_entries.append(
                    {
                        "schema_version": legacy.DIMENSION_PAIR_GATE_SCHEMA,
                        "source_ordinal": source_index + 1,
                        "magnitude_ppm": (15_000, 30_000)[magnitude_index],
                        "pair_record_id": payload["pair_record_id"],
                        "pair_screening_record_digest": wrapper["pair_screening_record_digest"],
                        "pair_gate_passed": True,
                    }
                )
        record: dict[str, object] = {
            "schema_version": "mirror.demo/D02DimensionEligibilityRecord/v4",
            "dimension_key": dimension,
            "priority_index": index + 1,
            "ordered_pair_screening_record_digests": pair_digests,
            "ordered_side_automated_gate_digests": side_digests,
            "sixteen_side_gate_digest": mirror_demo_digest(
                legacy.SIXTEEN_SIDE_GATE_SCHEMA,
                {
                    "dimension_key": dimension,
                    "priority_index": index + 1,
                    "ordered_side_gate_entries": side_entries,
                },
            ),
            "eight_pair_gate_digest": mirror_demo_digest(
                legacy.EIGHT_PAIR_GATE_SCHEMA,
                {
                    "dimension_key": dimension,
                    "priority_index": index + 1,
                    "ordered_pair_gate_entries": pair_entries,
                },
            ),
            "all_sixteen_side_gates_passed": True,
            "all_eight_pair_gates_passed": True,
            "all_manual_gates_passed": True,
            "global_exact_sha_gate_passed": exact_sha_gate_passed,
            "empty_lock_policy_gate_passed": True,
            "eligible": exact_sha_gate_passed,
            "failure_reasons": [] if exact_sha_gate_passed else [legacy._FAILURE_REASONS[3]],
        }
        record["record_digest"] = mirror_demo_digest(
            "mirror.demo/D02DimensionEligibilityRecord/v4",
            {key: value for key, value in record.items() if key != "schema_version"},
        )
        records.append(record)
    return records


def _selection(dimensions: list[dict[str, object]]) -> list[dict[str, object]]:
    eligible = [
        cast(str, dimension["dimension_key"])
        for dimension in dimensions
        if dimension["eligible"] is True
    ]
    selected = eligible[:2] if len(eligible) >= 2 else []
    records: list[dict[str, object]] = []
    for index, dimension in enumerate(dimensions):
        dimension_key = cast(str, dimension["dimension_key"])
        is_eligible = dimension["eligible"] is True
        eligible_rank = eligible.index(dimension_key) + 1 if is_eligible else 0
        is_selected = dimension_key in selected
        selection_decision = (
            "INELIGIBLE"
            if not is_eligible
            else "ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET"
            if len(eligible) < 2
            else "SELECTED_SLOT_1"
            if eligible_rank == 1
            else "SELECTED_SLOT_2"
            if eligible_rank == 2
            else "ELIGIBLE_NOT_SELECTED_CAPACITY"
        )
        record: dict[str, object] = {
            "schema_version": "mirror.demo/D02SelectionTraceRecord/v3",
            "selection_step": index + 1,
            "dimension_key": dimension_key,
            "priority_index": index + 1,
            "dimension_eligibility_record_digest": dimension["record_digest"],
            "eligible": is_eligible,
            "eligible_rank": eligible_rank,
            "selection_decision": selection_decision,
            "selection_slot": selected.index(dimension_key) + 1 if is_selected else 0,
            "selected": is_selected,
        }
        record["record_digest"] = mirror_demo_digest(
            "mirror.demo/D02SelectionTraceRecord/v3",
            {key: value for key, value in record.items() if key != "schema_version"},
        )
        records.append(record)
    return records


@lru_cache(maxsize=2)
def _report_input_template(
    duplicate_result_case_index: int | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if duplicate_result_case_index is not None and not 1 <= duplicate_result_case_index < 48:
        raise ValueError("duplicate result case index must have a preceding case")
    packets = [
        _packet(marker, source_ordinal=index)
        for index, marker in enumerate(("a", "b", "c", "d"), start=1)
    ]
    # The predecessor fixture supplies only the unchanged typed measurement
    # primitives.  Every R2 execution envelope below is rebuilt in its R2
    # schema/domain and rebound to the four validated R2 source packets.
    legacy_report, _, _ = _complete_report_fixture(passing=True)
    legacy_payload = cast(dict[str, object], legacy_report["report_payload"])
    sources = [cast(dict[str, object], packet["source_manifest_entry"]) for packet in packets]
    source_manifest_digest = legacy._sequence_digest(
        "mirror.demo/D02SourceAuthorityManifest/v2", sources
    )
    for packet in packets:
        packet["source_manifest_digest"] = source_manifest_digest
    binding = deepcopy(cast(dict[str, object], legacy_payload["schema_and_policy"]))
    binding["schema_version"] = "mirror.demo/D02SchemaAndPolicyBinding/v3"
    binding["source_manifest_digest"] = source_manifest_digest
    legacy_cases = cast(list[dict[str, object]], legacy_payload["ordered_case_manifest"])
    geometry_fields = (
        "geometry_ontology_version_digest",
        "warp_plan_digest",
        "geometry_algorithm_version",
        "runtime_config_digest",
        "output_policy_version",
        "output_width",
        "output_height",
        "determinism_level",
    )
    cases: list[dict[str, object]] = []
    for index, old in enumerate(legacy_cases):
        source = sources[index // 12]
        fields = {
            "case_ordinal": index + 1,
            "source_manifest_digest": source_manifest_digest,
            "source_ordinal": index // 12 + 1,
            "source_authority_key": source["source_authority_key"],
            "source_admission_event_id": source["source_admission_event_id"],
            "source_asset_id": source["source_asset_id"],
            "source_asset_sha256": source["source_asset_sha256"],
            "source_qa_snapshot_digest": source["source_qa_snapshot_digest"],
            "source_measurement_projection_digest": source["source_measurement_projection_digest"],
            "source_p2_candidate_manifest_content_digest": source[
                "source_p2_candidate_manifest_content_digest"
            ],
            "dimension_authority_manifest_content_digest": source[
                "dimension_authority_manifest_content_digest"
            ],
            "r2_source_authority_record_id": source["r2_source_authority_record_id"],
            "dimension_key": old["dimension_key"],
            "priority_index": old["priority_index"],
            "direction": old["direction"],
            "direction_index": old["direction_index"],
            "magnitude_ppm": old["magnitude_ppm"],
            "magnitude_index": old["magnitude_index"],
            "ordered_control_dimensions": old["ordered_control_dimensions"],
            **{key: old[key] for key in geometry_fields},
            "runtime_manifest_digest": binding["runtime_manifest_digest"],
        }
        cases.append(build_r2_case_manifest_entry(fields, execution_authority=binding))
    case_manifest_digest = legacy._sequence_digest("mirror.demo/D02GeometryCaseManifest/v2", cases)
    binding["case_manifest_digest"] = case_manifest_digest

    legacy_source_m3 = cast(list[dict[str, object]], legacy_payload["source_m3_repeat_evidence"])
    source_m3: list[dict[str, object]] = []
    for index, old in enumerate(legacy_source_m3):
        source = sources[index // 3]
        facts = cast(dict[str, object], packets[index // 3]["facts"])
        observation = cast(dict[str, object], facts["source_measurement_observation"])
        certificate = cast(dict[str, object], facts["source_repeat_certification"])
        repeat_binding = cast(list[dict[str, object]], certificate["ordered_repeat_bindings"])[
            index % 3
        ]
        fields = {
            key: value
            for key, value in old.items()
            if key not in {"schema_version", "source_m3_record_id", "record_digest"}
        }
        fields.update(
            source_ordinal=source["source_ordinal"],
            source_authority_key=source["source_authority_key"],
            source_admission_event_id=source["source_admission_event_id"],
            source_asset_id=source["source_asset_id"],
            source_asset_sha256=source["source_asset_sha256"],
            source_authority_digest=source["source_authority_digest"],
            repeat_index=index % 3 + 1,
            measurement_observation=observation,
            measurement_observation_digest=observation["measurement_observation_digest"],
            canonical_output_digest=observation["canonical_output_digest"],
            landmark_digest=observation["landmark_digest"],
            vision_model_manifest_digest=observation["vision_model_manifest_digest"],
            runtime_manifest_digest=observation["runtime_manifest_digest"],
            topology_digest=observation["topology_digest"],
        )
        for key in (
            "execution_receipt_digest",
            "face_count",
            "landmark_count",
            "coordinates_finite",
            "coordinates_in_bounds",
            "repeat_gate_passed",
        ):
            fields[key] = repeat_binding[key]
        source_m3.append(
            build_r2_source_m3_record(fields, source_manifest_digest=source_manifest_digest)
        )

    legacy_m4 = cast(list[dict[str, object]], legacy_payload["m4_repeat_evidence"])
    m4: list[dict[str, object]] = []
    for index, old in enumerate(legacy_m4):
        case = cases[index // 2]
        source = sources[index // 24]
        fields = {
            key: value
            for key, value in old.items()
            if key not in {"schema_version", "record_digest", "m4_execution_record_id"}
        }
        fields.update(
            case_id=case["case_id"],
            case_specification_digest=case["case_specification_digest"],
            replay_index=index % 2 + 1,
            source_output_id=source["source_output_id"],
            source_asset_id=case["source_asset_id"],
            source_asset_sha256=case["source_asset_sha256"],
            warp_plan_digest=case["warp_plan_digest"],
            geometry_algorithm_version=case["geometry_algorithm_version"],
            runtime_manifest_digest=case["runtime_manifest_digest"],
            runtime_config_digest=case["runtime_config_digest"],
            determinism_level=case["determinism_level"],
        )
        if duplicate_result_case_index is not None and index // 2 == duplicate_result_case_index:
            duplicate_source = m4[(duplicate_result_case_index - 1) * 2]
            for key in (
                "result_sha256",
                "result_byte_size",
                "result_mime_type",
                "result_width",
                "result_height",
                "changed_pixel_count",
            ):
                fields[key] = duplicate_source[key]
        m4.append(build_r2_m4_execution_record(fields))

    image_records = build_r2_image_authority_evidence(
        source_packets=packets,
        case_manifest=cases,
        m4_records=m4,
        execution_authority=binding,
    )
    result_image_id_by_case = {
        cast(str, record["case_id"]): cast(str, record["image_record_id"])
        for record in image_records
        if record["authority_role"] == "RESULT"
    }

    legacy_results = cast(list[dict[str, object]], legacy_payload["result_m3_repeat_evidence"])
    results: list[dict[str, object]] = []
    for index, old in enumerate(legacy_results):
        case = cases[index // 3]
        first = m4[index // 3 * 2]
        observation = deepcopy(cast(dict[str, object], old["measurement_observation"]))
        subject = cast(dict[str, object], observation["subject"])
        subject.update(
            case_id=case["case_id"],
            case_specification_digest=case["case_specification_digest"],
            result_output_id=first["result_output_id"],
            result_sha256=first["result_sha256"],
        )
        _resign_legacy_typed(
            observation,
            "mirror.demo/D02MeasurementObservation/v1",
            "measurement_observation_digest",
        )
        fields = {
            key: value
            for key, value in old.items()
            if key not in {"schema_version", "record_digest", "result_m3_record_id"}
        }
        fields.update(
            case_id=case["case_id"],
            case_specification_digest=case["case_specification_digest"],
            result_output_id=first["result_output_id"],
            result_sha256=first["result_sha256"],
            repeat_index=index % 3 + 1,
            measurement_observation=observation,
            measurement_observation_digest=observation["measurement_observation_digest"],
            canonical_output_digest=observation["canonical_output_digest"],
            landmark_digest=observation["landmark_digest"],
            runtime_manifest_digest=observation["runtime_manifest_digest"],
            vision_model_manifest_digest=observation["vision_model_manifest_digest"],
            topology_digest=observation["topology_digest"],
        )
        results.append(build_r2_result_m3_record(fields))

    legacy_gates = cast(list[dict[str, object]], legacy_payload["measurement_gate_evidence"])
    gates: list[dict[str, object]] = []
    for index, old in enumerate(legacy_gates):
        case = cases[index]
        fields = {
            key: deepcopy(value)
            for key, value in old.items()
            if key not in {"schema_version", "record_digest"}
        }
        fields.update(
            case_id=case["case_id"],
            case_specification_digest=case["case_specification_digest"],
            dimension_key=case["dimension_key"],
            requested_direction=case["direction"],
            requested_magnitude_ppm=case["magnitude_ppm"],
            monotonicity_peer_case_id=cases[index + 1 if index % 2 == 0 else index - 1]["case_id"],
        )
        result_records = results[index * 3 : index * 3 + 3]
        certificate = deepcopy(cast(dict[str, object], fields["result_repeat_certification"]))
        certificate_subject = cast(dict[str, object], certificate["subject"])
        for key in ("case_id", "case_specification_digest", "result_output_id", "result_sha256"):
            certificate_subject[key] = result_records[0][key]
        for certificate_binding, result in zip(
            cast(list[dict[str, object]], certificate["ordered_repeat_bindings"]),
            result_records,
            strict=True,
        ):
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
            ):
                certificate_binding[key] = result[key]
        _resign_legacy_typed(
            certificate,
            "mirror.demo/D02ResultRepeatDeterminismCertification/v1",
            "result_repeat_certification_digest",
        )
        fields["result_repeat_certification"] = certificate
        fields["result_repeat_certification_digest"] = certificate[
            "result_repeat_certification_digest"
        ]
        measurements = cast(list[dict[str, object]], fields["ordered_result_repeat_measurements"])
        for measurement, result in zip(measurements, result_records, strict=True):
            measurement["result_m3_record_digest"] = result["record_digest"]
        gates.append(build_r2_measurement_gate(fields))

    structures: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        case, first, second = cases[index], m4[index * 2], m4[index * 2 + 1]
        structures.append(
            build_r2_decode_structure_record(
                {"result_image_record_id": result_image_id_by_case[cast(str, case["case_id"])]},
                case_entry=case,
                source_entry=sources[index // 12],
                m4_first=first,
                m4_second=second,
                execution_authority=binding,
            )
        )

    old_manual_by_case = {
        old["case_id"]: old
        for old in cast(list[dict[str, object]], legacy_payload["manual_review_evidence"])
    }
    manuals: list[dict[str, object]] = []
    for sequence, (index, case) in enumerate(
        sorted(enumerate(cases), key=lambda item: cast(str, item[1]["case_id"])), start=1
    ):
        old = old_manual_by_case[legacy_cases[index]["case_id"]]
        fields = {key: old[key] for key in legacy._MANUAL_BUILD_FIELDS}
        fields["decision_sequence"] = sequence
        manuals.append(
            build_r2_manual_artifact_decision(
                fields,
                case_entry=case,
                source_entry=sources[index // 12],
                m4_first=m4[index * 2],
                execution_authority=binding,
            )
        )

    exact_duplicate = build_r2_exact_duplicate_evidence(image_records)
    phashes = {
        cast(str, record["image_record_id"]): cast(str, record["sha256"])[:16]
        for record in image_records
    }
    phash_observations = build_r2_phash_observation_evidence(
        image_records=image_records,
        image_phashes=phashes,
        execution_authority=binding,
    )
    pairs = build_r2_pair_screening_evidence(
        source_packets=packets,
        case_manifest=cases,
        m4_records=m4,
        result_records=results,
        gates=gates,
        structure_records=structures,
        manual_records=manuals,
        image_records=image_records,
        execution_authority=binding,
    )
    exact_sha_gate_passed = exact_duplicate["exact_sha_gate_passed"] is True
    dimensions = _dimension_records(
        cast(list[dict[str, object]], pairs),
        exact_sha_gate_passed=exact_sha_gate_passed,
    )
    selection = _selection(dimensions)
    eligible_dimension_keys = [
        cast(str, dimension["dimension_key"])
        for dimension in dimensions
        if dimension["eligible"] is True
    ]
    selected_dimension_keys = (
        eligible_dimension_keys[:2] if len(eligible_dimension_keys) >= 2 else []
    )

    payload: dict[str, object] = {
        "schema_and_policy": binding,
        "ordered_source_manifest": sources,
        "ordered_case_manifest": cases,
        "source_m3_repeat_evidence": source_m3,
        "m4_repeat_evidence": m4,
        "result_m3_repeat_evidence": results,
        "measurement_gate_evidence": gates,
        "decode_structure_immutability_evidence": structures,
        "manual_review_evidence": manuals,
        "exact_duplicate_evidence": exact_duplicate,
        "phash_observation_evidence": phash_observations,
        "pair_quality_evidence": pairs,
        "dimension_eligibility": dimensions,
        "fixed_priority_selection_trace": selection,
        "selected_pair_manifest": [],
        "network_and_runtime_boundary": build_r2_network_runtime_boundary(),
    }
    # The canonical selected entries are supplied by rebuilding from the report graph.
    fields: dict[str, object] = {
        "created_at": "2026-08-26T00:00:00Z",
        "source_manifest_digest": source_manifest_digest,
        "case_manifest_digest": case_manifest_digest,
        "screening_policy_digest": binding["screening_policy_digest"],
        "runtime_manifest_digest": binding["runtime_manifest_digest"],
        "vision_model_manifest_digest": binding["vision_model_manifest_digest"],
        "topology_digest": binding["topology_digest"],
        "measurement_config_digest": binding["measurement_config_digest"],
        "manual_review_policy_digest": binding["manual_review_policy_digest"],
        "duplicate_policy_digest": binding["duplicate_policy_digest"],
        "phash_implementation_digest": binding["phash_implementation_digest"],
        "report_payload": payload,
        "status": "PASSED" if selected_dimension_keys else "FAILED",
        "source_count": 4,
        "case_count": 48,
        "source_m3_repeat_count": 12,
        "m4_execution_count": 96,
        "result_m3_repeat_count": 144,
        "measurement_gate_count": 48,
        "decode_structure_record_count": 48,
        "manual_decision_count": 48,
        "exact_sha_record_count": 52,
        "phash_comparison_count": 1326,
        "candidate_pair_count": 24,
        "selected_pair_count": 16 if selected_dimension_keys else 0,
        "selected_result_side_count": 32 if selected_dimension_keys else 0,
        "eligible_dimension_keys": eligible_dimension_keys,
        "selected_dimension_keys": selected_dimension_keys,
        "selected_pair_manifest_digest": _digest("placeholder")
        if selected_dimension_keys
        else None,
    }
    # Recreate the frozen source-then-magnitude selected-entry projection.
    entries: list[dict[str, object]] = []
    for slot, dimension in enumerate(selected_dimension_keys, start=1):
        for source_index in range(4):
            for magnitude_index, magnitude in enumerate((15_000, 30_000)):
                pair = pairs[source_index * 6 + (slot - 1) * 2 + magnitude_index]
                pair_payload = cast(dict[str, object], pair["pair_screening_record_payload"])
                left, right = (
                    cast(dict[str, object], pair_payload["left"]),
                    cast(dict[str, object], pair_payload["right"]),
                )
                entry = {
                    "schema_version": "mirror.demo/D02SelectedPairManifestEntry/v3",
                    "selected_pair_ordinal": len(entries) + 1,
                    "selected_dimension_slot": slot,
                    "dimension_key": dimension,
                    "priority_index": slot,
                    "source_ordinal": source_index + 1,
                    "source_authority_key": pair_payload["source_authority_key"],
                    "source_admission_event_id": pair_payload["source_admission_event_id"],
                    "magnitude_ppm": magnitude,
                    "pair_record_id": pair_payload["pair_record_id"],
                    "pair_screening_record_digest": pair["pair_screening_record_digest"],
                    "left_case_id": left["case_id"],
                    "left_result_asset_id": left["result_asset_id"],
                    "left_result_asset_sha256": left["result_asset_sha256"],
                    "left_asset_variant_id": left["asset_variant_id"],
                    "right_case_id": right["case_id"],
                    "right_result_asset_id": right["result_asset_id"],
                    "right_result_asset_sha256": right["result_asset_sha256"],
                    "right_asset_variant_id": right["asset_variant_id"],
                }
                entry["entry_digest"] = mirror_demo_digest(
                    "mirror.demo/D02SelectedPairManifestEntry/v3",
                    {key: value for key, value in entry.items() if key != "schema_version"},
                )
                entries.append(entry)
    payload["selected_pair_manifest"] = entries
    if entries:
        fields["selected_pair_manifest_digest"] = legacy._sequence_digest(
            "mirror.demo/D02SelectedPairManifest/v3", entries
        )
    return fields, packets


def _report_input() -> tuple[dict[str, object], list[dict[str, object]]]:
    fields, packets = _report_input_template()
    return deepcopy(fields), deepcopy(packets)


def _report() -> tuple[dict[str, object], list[dict[str, object]]]:
    fields, packets = _report_input()
    return cast(dict[str, object], build_r2_report_row(fields, source_packets=packets)), packets


def test_r2_report_replays_full_typed_graph_and_excludes_created_at() -> None:
    report, packets = _report()
    assert validate_r2_report_row(report, source_packets=packets) == report
    replay = deepcopy(report)
    replay["created_at"] = "2026-08-27T00:00:00Z"
    assert (
        build_r2_report_row(
            {
                key: replay[key]
                for key in report
                if key
                in set(report)
                - {"id", "schema_version", "canonical_payload", "content_digest", "report_digest"}
            },
            source_packets=packets,
        )["content_digest"]
        == report["content_digest"]
    )


@pytest.mark.parametrize(
    "field",
    (
        "runtime_manifest_digest",
        "vision_model_manifest_digest",
        "topology_digest",
        "measurement_config_digest",
        "measurement_quality_config_digest",
        "measurement_quality_manifest_content_digest",
        "screening_policy_digest",
    ),
)
def test_r2_execution_authority_rejects_resigned_accepted_manifest_replacement(
    field: str,
) -> None:
    fields, _ = _report_input()
    binding = deepcopy(cast(dict[str, object], fields["report_payload"])["schema_and_policy"])
    binding[field] = _digest(f"forged-{field}")

    with pytest.raises(D02R2AuthorityError, match="accepted execution authority"):
        r2._r2_execution_authority(binding)


def test_r2_execution_authority_rejects_resigned_measurement_config_replacement() -> None:
    fields, _ = _report_input()
    binding = deepcopy(cast(dict[str, object], fields["report_payload"])["schema_and_policy"])
    config = cast(dict[str, object], binding["measurement_execution_config"])
    config["measurement_algorithm_version"] = "forged-measurement-algorithm"
    binding["measurement_config_digest"] = replay_measurement_config_digest(config)

    with pytest.raises(D02R2AuthorityError, match="accepted execution authority") as error:
        r2._r2_execution_authority(binding)
    assert error.value.__cause__ is not None
    assert str(error.value.__cause__) == "schema and policy binding differs from accepted manifest"


def test_r2_case_rejects_runtime_manifest_divergent_from_report_authority() -> None:
    fields, _ = _report_input()
    payload = cast(dict[str, object], fields["report_payload"])
    binding = cast(dict[str, object], payload["schema_and_policy"])
    case = cast(list[dict[str, object]], payload["ordered_case_manifest"])[0]
    inputs = {
        key: deepcopy(value)
        for key, value in case.items()
        if key
        not in {
            "schema_version",
            "case_id",
            "execution_config_digest",
            "case_specification_digest",
            "record_digest",
        }
    }
    inputs["runtime_manifest_digest"] = _digest("forged-case-runtime")

    with pytest.raises(D02R2AuthorityError, match="case runtime manifest"):
        build_r2_case_manifest_entry(inputs, execution_authority=binding)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("ordered_control_dimensions", ["jaw_width"] * 5, "control dimensions"),
        ("output_width", 0, "output_width"),
        ("geometry_algorithm_version", "bad version!", "geometry_algorithm_version"),
        ("geometry_ontology_version_digest", "not-a-digest", "lowercase SHA-256"),
    ),
)
def test_r2_case_builder_and_graph_reject_resigned_invalid_semantics(
    field: str, value: object, message: str
) -> None:
    fields, packets = _report_input()
    payload = cast(dict[str, object], fields["report_payload"])
    binding = cast(dict[str, object], payload["schema_and_policy"])
    case = cast(list[dict[str, object]], payload["ordered_case_manifest"])[0]
    inputs = {
        key: deepcopy(item)
        for key, item in case.items()
        if key
        not in {
            "schema_version",
            "case_id",
            "execution_config_digest",
            "case_specification_digest",
            "record_digest",
        }
    }
    inputs[field] = deepcopy(value)

    with pytest.raises(D02R2AuthorityError, match=message):
        build_r2_case_manifest_entry(inputs, execution_authority=binding)

    forged_payload = deepcopy(payload)
    forged_binding = cast(dict[str, object], forged_payload["schema_and_policy"])
    forged_cases = cast(list[dict[str, object]], forged_payload["ordered_case_manifest"])
    forged_case = forged_cases[0]
    forged_case[field] = deepcopy(value)
    forged_case["execution_config_digest"] = r2._r2_case_execution_digest(
        forged_case, forged_binding
    )
    forged_case["case_id"] = r2._r2_case_id(forged_case)
    forged_case["case_specification_digest"] = r2._r2_case_specification_digest(forged_case)
    _resign_r2_record(forged_case, r2.R2_CASE_SCHEMA)
    forged_binding["case_manifest_digest"] = legacy._sequence_digest(
        r2.R2_CASE_MANIFEST_SCHEMA, forged_cases
    )

    with pytest.raises(D02R2AuthorityError, match=message):
        r2._validate_r2_upstream_execution_graph(forged_payload, source_packets=packets)


def test_r2_m4_rejects_fully_resigned_divergent_replay_result() -> None:
    report, packets = _report()
    payload = cast(dict[str, object], report["report_payload"])
    m4 = cast(list[dict[str, object]], payload["m4_repeat_evidence"])
    second = m4[1]
    second["result_output_id"] = "forged-second-replay-output"
    second["result_sha256"] = _digest("forged-second-replay-result")
    _resign_r2_record(second, "mirror.demo/D02M4ExecutionRecord/v2")
    structure = cast(list[dict[str, object]], payload["decode_structure_immutability_evidence"])[0]
    structure["m4_execution_record_digests"] = [m4[0]["record_digest"], m4[1]["record_digest"]]
    _resign_r2_record(structure, "mirror.demo/D02DecodeStructureImmutabilityRecord/v2")

    with pytest.raises(D02R2AuthorityError, match="not byte/dimension deterministic"):
        validate_r2_report_row(report, source_packets=packets)


def test_r2_structure_rejects_fully_resigned_false_green_dimensions() -> None:
    report, packets = _report()
    payload = cast(dict[str, object], report["report_payload"])
    case = cast(list[dict[str, object]], payload["ordered_case_manifest"])[0]
    m4 = cast(list[dict[str, object]], payload["m4_repeat_evidence"])
    forged_width = cast(int, case["output_width"]) + 1
    for record in m4[:2]:
        record["result_width"] = forged_width
        _resign_r2_record(record, r2.R2_M4_SCHEMA)
    structure = cast(list[dict[str, object]], payload["decode_structure_immutability_evidence"])[0]
    structure["m4_execution_record_digests"] = [m4[0]["record_digest"], m4[1]["record_digest"]]
    structure["result_width"] = forged_width
    structure["bounded_dimensions_passed"] = True
    structure["structure_gate_passed"] = True
    _resign_r2_record(structure, r2.R2_STRUCTURE_SCHEMA)

    with pytest.raises(D02R2AuthorityError, match="structure gate is not derived"):
        validate_r2_report_row(report, source_packets=packets)


@pytest.mark.parametrize("artifact_value", (True, "false"))
def test_r2_manual_rejects_resigned_false_green_or_boolean_coercion(
    artifact_value: object,
) -> None:
    report, packets = _report()
    payload = cast(dict[str, object], report["report_payload"])
    manual = cast(list[dict[str, object]], payload["manual_review_evidence"])[0]
    manual["background_seam"] = artifact_value
    manual["verdict"] = "PASS"
    _resign_legacy_typed(manual, r2.R2_MANUAL_SCHEMA, "manual_decision_digest")

    message = "verdict is not derived" if artifact_value is True else "must be a JSON boolean"
    with pytest.raises(D02R2AuthorityError, match=message):
        validate_r2_report_row(report, source_packets=packets)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("execution_succeeded", False, "must have succeeded"),
        ("result_byte_size", -1, "result descriptor"),
        ("result_width", 0, "result_width"),
        ("changed_pixel_count", 0, "changed pixel count"),
    ),
)
def test_r2_m4_rejects_fully_resigned_invalid_execution_or_descriptor(
    field: str, value: object, message: str
) -> None:
    report, packets = _report()
    payload = cast(dict[str, object], report["report_payload"])
    m4 = cast(list[dict[str, object]], payload["m4_repeat_evidence"])
    for record in m4[:2]:
        record[field] = value
        _resign_r2_record(record, "mirror.demo/D02M4ExecutionRecord/v2")
    structure = cast(list[dict[str, object]], payload["decode_structure_immutability_evidence"])[0]
    structure["m4_execution_record_digests"] = [m4[0]["record_digest"], m4[1]["record_digest"]]
    if field in structure:
        structure[field] = value
    _resign_r2_record(structure, "mirror.demo/D02DecodeStructureImmutabilityRecord/v2")

    with pytest.raises(D02R2AuthorityError, match=message):
        validate_r2_report_row(report, source_packets=packets)


def test_r2_report_rejects_placeholder_unknown_key_and_resigned_pair_splice() -> None:
    report, packets = _report()
    malformed = deepcopy(report)
    cast(
        list[dict[str, object]],
        cast(dict[str, object], malformed["report_payload"])["ordered_case_manifest"],
    )[0] = {
        "schema_version": "mirror.demo/D02GeometryCaseManifestEntry/v4",
        "record_digest": _digest("bad"),
    }
    with pytest.raises(D02R2AuthorityError):
        validate_r2_report_row(malformed, source_packets=packets)
    forged = deepcopy(report)
    pair = cast(
        list[dict[str, object]],
        cast(dict[str, object], forged["report_payload"])["pair_quality_evidence"],
    )[0]
    cast(dict[str, object], pair["pair_screening_record_payload"])["source_asset_sha256"] = _digest(
        "forged"
    )
    cast(dict[str, object], pair["pair_screening_record_payload"])["pair_record_id"] = "0" * 32
    with pytest.raises(D02R2AuthorityError):
        validate_r2_report_row(forged, source_packets=packets)


@pytest.mark.parametrize(
    "group",
    (
        "schema_and_policy",
        "ordered_source_manifest",
        "ordered_case_manifest",
        "source_m3_repeat_evidence",
        "m4_repeat_evidence",
        "result_m3_repeat_evidence",
        "measurement_gate_evidence",
        "decode_structure_immutability_evidence",
        "manual_review_evidence",
    ),
)
def test_r2_upstream_groups_reject_wrong_schema_and_missing_or_extra_key(group: str) -> None:
    report, packets = _report()
    for mutation in ("schema", "missing", "extra"):
        forged = deepcopy(report)
        payload = cast(dict[str, object], forged["report_payload"])
        member = payload[group]
        if isinstance(member, list):
            item = cast(dict[str, object], member[0])
        else:
            item = cast(dict[str, object], member)
        if mutation == "schema":
            item["schema_version"] = "mirror.demo/forged/v1"
        elif mutation == "missing":
            item.pop(
                next(key for key in item if key not in {"schema_version", "record_digest"}), None
            )
        else:
            item["forged_extra"] = _digest(f"{group}-{mutation}")
        with pytest.raises(D02R2AuthorityError):
            validate_r2_report_row(forged, source_packets=packets)


def test_r2_upstream_graph_rejects_resigned_cross_source_case_and_record_ids() -> None:
    report, packets = _report()
    forged = deepcopy(report)
    payload = cast(dict[str, object], forged["report_payload"])
    case = cast(list[dict[str, object]], payload["ordered_case_manifest"])[0]
    second_source = cast(list[dict[str, object]], payload["ordered_source_manifest"])[1]
    for key in (
        "source_authority_key",
        "source_admission_event_id",
        "source_asset_id",
        "source_asset_sha256",
        "source_qa_snapshot_digest",
        "source_measurement_projection_digest",
        "source_p2_candidate_manifest_content_digest",
        "dimension_authority_manifest_content_digest",
        "r2_source_authority_record_id",
    ):
        case[key] = second_source[key]
    # This is a complete re-sign of the attacked CaseEntry/v4; the aggregate
    # replay must still reject the source-ordinal substitution.
    fields = {
        key: value
        for key, value in case.items()
        if key
        not in {
            "schema_version",
            "case_id",
            "execution_config_digest",
            "case_specification_digest",
            "record_digest",
        }
    }
    binding = cast(dict[str, object], payload["schema_and_policy"])
    case.clear()
    case.update(build_r2_case_manifest_entry(fields, execution_authority=binding))
    with pytest.raises(D02R2AuthorityError, match="source authority binding"):
        validate_r2_report_row(forged, source_packets=packets)


@pytest.mark.parametrize(
    ("group", "field"),
    (
        ("ordered_case_manifest", "case_id"),
        ("source_m3_repeat_evidence", "record_digest"),
        ("m4_repeat_evidence", "m4_execution_record_id"),
        ("result_m3_repeat_evidence", "result_m3_record_id"),
        ("measurement_gate_evidence", "record_digest"),
        ("decode_structure_immutability_evidence", "record_digest"),
        ("manual_review_evidence", "manual_decision_digest"),
    ),
)
def test_r2_upstream_groups_reject_forged_record_id_or_digest(group: str, field: str) -> None:
    report, packets = _report()
    forged = deepcopy(report)
    payload = cast(dict[str, object], forged["report_payload"])
    cast(list[dict[str, object]], payload[group])[0][field] = (
        "0" * 32 if field.endswith("id") else "0" * 64
    )
    with pytest.raises(D02R2AuthorityError):
        validate_r2_report_row(forged, source_packets=packets)


def test_r2_report_rejects_reordered_dimension_selection_and_selected_entry() -> None:
    report, packets = _report()
    for group in (
        "dimension_eligibility",
        "fixed_priority_selection_trace",
        "selected_pair_manifest",
    ):
        forged = deepcopy(report)
        cast(list[object], cast(dict[str, object], forged["report_payload"])[group]).reverse()
        with pytest.raises(D02R2AuthorityError):
            validate_r2_report_row(forged, source_packets=packets)


def test_r2_report_rejects_raw_float_negative_zero_and_mixed_schema() -> None:
    report, packets = _report()
    for value in (0.0, -0.0, "-0"):
        forged = deepcopy(report)
        cast(
            list[dict[str, object]],
            cast(dict[str, object], forged["report_payload"])["ordered_case_manifest"],
        )[0]["case_ordinal"] = value
        with pytest.raises(D02R2AuthorityError):
            validate_r2_report_row(forged, source_packets=packets)
    forged = deepcopy(report)
    cast(
        list[dict[str, object]],
        cast(dict[str, object], forged["report_payload"])["pair_quality_evidence"],
    )[0]["schema_version"] = "mirror.demo/D02PairScreeningRecord/v3"
    with pytest.raises(D02R2AuthorityError):
        validate_r2_report_row(forged, source_packets=packets)


@pytest.mark.parametrize(
    ("record_group", "leaf", "mutation"),
    _R2_MANDATORY_DIGEST_ATTACK_CASES,
    ids=[
        f"{group}-{leaf}-{mutation}" for group, leaf, mutation in _R2_MANDATORY_DIGEST_ATTACK_CASES
    ],
)
def test_r2_negative_input_validation_rejects_every_malformed_mandatory_digest_leaf(
    record_group: str, leaf: str, mutation: str
) -> None:
    """MALFORMED_AUTHORITY_REJECTION: all digest leaves fail closed after outer re-sign."""

    forged, packets = _build_fully_resigned_mandatory_digest_attack(
        record_group=record_group,
        leaf=leaf,
        mutation=mutation,
    )
    with pytest.raises(D02R2AuthorityError) as error:
        validate_r2_report_row(forged, source_packets=packets)
    if mutation not in {"wrong_well_formed_digest", "cross_source_substitution"}:
        assert "mandatory digest leaf" in str(error.value)
    else:
        assert "mandatory digest leaf" not in str(error.value)


def test_r2_source_m3_rejects_resigned_raw_measurement_and_authority_digest_splices() -> None:
    report, packets = _report()
    forged = deepcopy(report)
    payload = cast(dict[str, object], forged["report_payload"])
    source_record = cast(list[dict[str, object]], payload["source_m3_repeat_evidence"])[0]
    source_record["measurement_observation"] = deepcopy(
        cast(dict[str, object], source_record["measurement_observation"])
    )
    observation = cast(dict[str, object], source_record["measurement_observation"])
    measurement = cast(list[dict[str, object]], observation["ordered_measurements"])[0]
    measurement["raw_value_fixed18"] = "0.000000000000000001"
    _resign_legacy_typed(
        observation,
        "mirror.demo/D02MeasurementObservation/v1",
        "measurement_observation_digest",
    )
    source_record["measurement_observation_digest"] = observation["measurement_observation_digest"]
    _resign_r2_record(source_record, "mirror.demo/D02SourceM3RepeatRecord/v3")
    with pytest.raises(D02R2AuthorityError, match="admitted facts projection"):
        validate_r2_report_row(forged, source_packets=packets)

    for mutation in ("missing", "replacement"):
        forged = deepcopy(report)
        source_record = cast(
            list[dict[str, object]],
            cast(dict[str, object], forged["report_payload"])["source_m3_repeat_evidence"],
        )[0]
        if mutation == "missing":
            source_record.pop("source_authority_digest")
        else:
            source_record["source_authority_digest"] = cast(
                list[dict[str, object]],
                cast(dict[str, object], forged["report_payload"])["ordered_source_manifest"],
            )[1]["source_authority_digest"]
            _resign_r2_record(source_record, "mirror.demo/D02SourceM3RepeatRecord/v3")
        with pytest.raises((D02R2AuthorityError, legacy.D02AuthorityError)):
            validate_r2_report_row(forged, source_packets=packets)


def test_r2_result_m3_and_gate_recompute_raw_target_and_control_fixed18() -> None:
    report, packets = _report()
    for entry_index in (0, 1):
        forged = deepcopy(report)
        payload = cast(dict[str, object], forged["report_payload"])
        record = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])[0]
        observation = cast(dict[str, object], record["measurement_observation"])
        measurement = cast(list[dict[str, object]], observation["ordered_measurements"])[
            entry_index
        ]
        measurement["raw_value_fixed18"] = "0.000000000000000001"
        _resign_result_chain(forged, case_index=0, repeat_index=0)
        with pytest.raises((D02R2AuthorityError, legacy.D02AuthorityError)):
            validate_r2_report_row(forged, source_packets=packets)

    forged = deepcopy(report)
    payload = cast(dict[str, object], forged["report_payload"])
    record = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])[0]
    observation = cast(dict[str, object], record["measurement_observation"])
    cast(list[dict[str, object]], observation["ordered_measurements"])[0]["raw_value_fixed18"] = 0.0
    with pytest.raises(D02R2AuthorityError):
        validate_r2_report_row(forged, source_packets=packets)

    for bad_value in ("-0.000000000000000000", "1.00000000000000000"):
        forged = deepcopy(report)
        payload = cast(dict[str, object], forged["report_payload"])
        record = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])[0]
        observation = cast(dict[str, object], record["measurement_observation"])
        cast(list[dict[str, object]], observation["ordered_measurements"])[0][
            "raw_value_fixed18"
        ] = bad_value
        _resign_result_chain(forged, case_index=0, repeat_index=0)
        with pytest.raises((D02R2AuthorityError, legacy.D02AuthorityError)):
            validate_r2_report_row(forged, source_packets=packets)


def test_r2_gate_rejects_repeat_order_support_direction_magnitude_stability_and_monotonicity() -> (
    None
):
    report, packets = _report()

    forged = deepcopy(report)
    result = cast(
        list[dict[str, object]],
        cast(dict[str, object], forged["report_payload"])["result_m3_repeat_evidence"],
    )[1]
    result["repeat_index"] = 1
    _resign_r2_record(result, "mirror.demo/D02ResultM3RepeatRecord/v3")
    with pytest.raises(D02R2AuthorityError):
        validate_r2_report_row(forged, source_packets=packets)

    case = cast(
        list[dict[str, object]],
        cast(dict[str, object], report["report_payload"])["ordered_case_manifest"],
    )[0]
    for key, value in (
        ("requested_direction", "INCREASE" if case["direction"] == "DECREASE" else "DECREASE"),
        ("requested_magnitude_ppm", 30_000 if case["magnitude_ppm"] == 15_000 else 15_000),
    ):
        forged = deepcopy(report)
        gate = cast(
            list[dict[str, object]],
            cast(dict[str, object], forged["report_payload"])["measurement_gate_evidence"],
        )[0]
        gate[key] = value
        _resign_r2_record(gate, "mirror.demo/D02MeasurementGateRecord/v5")
        with pytest.raises((D02R2AuthorityError, legacy.D02AuthorityError)):
            validate_r2_report_row(forged, source_packets=packets)

    forged = deepcopy(report)
    record = cast(
        list[dict[str, object]],
        cast(dict[str, object], forged["report_payload"])["result_m3_repeat_evidence"],
    )[0]
    observation = cast(dict[str, object], record["measurement_observation"])
    unsupported = cast(list[dict[str, object]], observation["ordered_measurements"])[0]
    unsupported.update(
        support_state="UNSUPPORTED",
        raw_value_fixed18=None,
        observability_state="NOT_COMPUTABLE",
        raw_observability_fixed18=None,
        unsupported_reason="MISSING_MEASUREMENT",
    )
    _resign_result_chain(forged, case_index=0, repeat_index=0)
    with pytest.raises((D02R2AuthorityError, legacy.D02AuthorityError)):
        validate_r2_report_row(forged, source_packets=packets)

    forged = deepcopy(report)
    record = cast(
        list[dict[str, object]],
        cast(dict[str, object], forged["report_payload"])["result_m3_repeat_evidence"],
    )[1]
    observation = cast(dict[str, object], record["measurement_observation"])
    cast(list[dict[str, object]], observation["ordered_measurements"])[0]["raw_value_fixed18"] = (
        "0.000000000000000001"
    )
    _resign_result_chain(forged, case_index=0, repeat_index=1)
    with pytest.raises((D02R2AuthorityError, legacy.D02AuthorityError)):
        validate_r2_report_row(forged, source_packets=packets)

    forged = deepcopy(report)
    gate = cast(
        list[dict[str, object]],
        cast(dict[str, object], forged["report_payload"])["measurement_gate_evidence"],
    )[0]
    evaluation = cast(dict[str, object], gate["gate_evaluation"])
    evaluation["magnitude_monotonicity_gate_passed"] = False
    evaluation["measurement_gate_passed"] = False
    _resign_r2_record(gate, "mirror.demo/D02MeasurementGateRecord/v5")
    with pytest.raises(D02R2AuthorityError, match="monotonicity"):
        validate_r2_report_row(forged, source_packets=packets)


def test_r2_gate_rejects_fully_resigned_mixed_supported_unsupported_peer() -> None:
    report, packets = _report()
    forged = deepcopy(report)
    _replace_r2_case_with_unsupported_evidence(forged, case_index=1)

    with pytest.raises(
        D02R2AuthorityError,
        match="supported measurement with unsupported magnitude peer must fail closed",
    ):
        validate_r2_report_row(forged, source_packets=packets)


def test_r2_gate_rejects_fully_resigned_raw_leaf_nonmonotonic_peer() -> None:
    report, packets = _report()
    forged = deepcopy(report)
    payload = cast(dict[str, object], forged["report_payload"])
    lower_gate = cast(list[dict[str, object]], payload["measurement_gate_evidence"])[0]
    lower_measurement = cast(
        list[dict[str, object]], lower_gate["ordered_result_repeat_measurements"]
    )[0]
    lower_absolute_units = legacy._fixed18_units(
        lower_measurement["raw_target_absolute_delta_fixed18"], "test lower absolute delta"
    )
    forged_upper_units = lower_absolute_units - 1
    assert forged_upper_units >= 10_000_000_000_000
    _replace_r2_case_with_supported_delta(
        forged, case_index=1, absolute_delta_units=forged_upper_units
    )

    with pytest.raises(
        D02R2AuthorityError,
        match="magnitude peer monotonicity does not replay raw fixed18 evidence",
    ):
        validate_r2_report_row(forged, source_packets=packets)


def test_r2_report_rejects_resigned_cross_source_pair_attack() -> None:
    report, packets = _report()
    forged = deepcopy(report)
    pair = cast(
        list[dict[str, object]],
        cast(dict[str, object], forged["report_payload"])["pair_quality_evidence"],
    )[0]
    payload = cast(dict[str, object], pair["pair_screening_record_payload"])
    payload["source_asset_id"] = _digest("substituted-source")[:32]
    payload["pair_record_id"] = mirror_demo_digest(
        "mirror.demo/D02PairScreeningRecordId/v2",
        {
            "source_authority_key": payload["source_authority_key"],
            "source_admission_event_id": payload["source_admission_event_id"],
            "source_asset_sha256": payload["source_asset_sha256"],
            "dimension_key": payload["dimension_key"],
            "priority_index": payload["priority_index"],
            "magnitude_ppm": payload["magnitude_ppm"],
            "left_case_id": cast(dict[str, object], payload["left"])["case_id"],
            "right_case_id": cast(dict[str, object], payload["right"])["case_id"],
            "screening_policy_digest": payload["screening_policy_digest"],
            "lock_policy_digest": payload["lock_policy_digest"],
        },
    )[:32]
    pair["pair_screening_record_digest"] = mirror_demo_digest(
        "mirror.demo/D02PairScreeningRecord/v4", payload
    )
    with pytest.raises(D02R2AuthorityError, match="execution graph projection"):
        validate_r2_report_row(forged, source_packets=packets)


def test_r2_b3_replays_complete_image_phash_pair_and_network_authority() -> None:
    report, packets = _report()
    payload = cast(dict[str, object], report["report_payload"])
    exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
    images = cast(list[dict[str, object]], exact["image_records"])
    phash = cast(dict[str, object], payload["phash_observation_evidence"])
    pairs = cast(list[dict[str, object]], payload["pair_quality_evidence"])
    network = cast(dict[str, object], payload["network_and_runtime_boundary"])

    assert len(images) == 52
    assert sum(record["schema_version"] == r2.R2_SOURCE_IMAGE_SCHEMA for record in images) == 4
    assert sum(record["schema_version"] == r2.R2_RESULT_IMAGE_SCHEMA for record in images) == 48
    assert [record["image_record_ordinal"] for record in images] == list(range(1, 53))
    assert exact["exact_sha_gate_passed"] is True
    assert len(cast(list[object], phash["ordered_record_signatures"])) == 52
    assert len(cast(list[object], phash["comparisons"])) == 1326
    assert phash["bit_width"] == 64
    assert phash["threshold_policy"] == "OBSERVATION_ONLY_NO_THRESHOLD"
    assert len(pairs) == 24
    assert network == build_r2_network_runtime_boundary()
    assert validate_r2_report_row(report, source_packets=packets) == report


def test_r2_b3_rejects_fully_resigned_image_lineage_splice() -> None:
    fields, packets = _report_input()
    payload = cast(dict[str, object], fields["report_payload"])
    exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
    images = deepcopy(cast(list[dict[str, object]], exact["image_records"]))
    source_image = next(record for record in images if record["authority_role"] == "SOURCE")
    source_image["byte_size"] = cast(int, source_image["byte_size"]) + 1
    _resign_r2_image_record(source_image)

    with pytest.raises(D02R2AuthorityError, match="source/Case/M4 lineage"):
        r2._validate_r2_image_authority_evidence(
            images,
            source_packets=packets,
            case_manifest=cast(list[dict[str, object]], payload["ordered_case_manifest"]),
            m4_records=cast(list[dict[str, object]], payload["m4_repeat_evidence"]),
            execution_authority=cast(dict[str, object], payload["schema_and_policy"]),
        )


def test_r2_b3_rejects_exact_sha_false_green_and_cardinality() -> None:
    fields, _ = _report_input()
    payload = cast(dict[str, object], fields["report_payload"])
    exact = deepcopy(cast(dict[str, object], payload["exact_duplicate_evidence"]))
    images = cast(list[dict[str, object]], exact["image_records"])
    exact["all_record_sha_unique"] = False
    exact["exact_sha_gate_passed"] = True
    with pytest.raises(D02R2AuthorityError, match="Gate booleans"):
        r2._validate_r2_exact_duplicate_evidence(exact, expected_image_records=images)

    truncated = deepcopy(cast(dict[str, object], payload["exact_duplicate_evidence"]))
    cast(list[dict[str, object]], truncated["image_records"]).pop()
    with pytest.raises(D02R2AuthorityError, match="complete graph projection"):
        r2._validate_r2_exact_duplicate_evidence(truncated, expected_image_records=images)


def test_r2_b3_duplicate_result_builds_complete_failed_report() -> None:
    template, packet_template = _report_input_template(duplicate_result_case_index=1)
    fields, packets = deepcopy(template), deepcopy(packet_template)

    report = cast(dict[str, object], build_r2_report_row(fields, source_packets=packets))
    assert validate_r2_report_row(report, source_packets=packets) == report
    assert report["status"] == "FAILED"
    assert report["selected_pair_count"] == 0
    assert report["selected_result_side_count"] == 0
    assert report["eligible_dimension_keys"] == []
    assert report["selected_dimension_keys"] == []
    assert report["selected_pair_manifest_digest"] is None

    payload = cast(dict[str, object], report["report_payload"])
    exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
    images = cast(list[dict[str, object]], exact["image_records"])
    result_sha = [
        cast(str, image["sha256"]) for image in images if image["authority_role"] == "RESULT"
    ]
    assert len(images) == 52
    assert len(result_sha) == 48
    assert len(set(result_sha)) == 47
    assert exact["all_record_sha_unique"] is False
    assert exact["result_sha_unique"] is False
    assert exact["exact_sha_gate_passed"] is False

    phash = cast(dict[str, object], payload["phash_observation_evidence"])
    assert len(cast(list[dict[str, object]], phash["ordered_record_signatures"])) == 52
    assert len(cast(list[dict[str, object]], phash["comparisons"])) == 1326
    assert len(cast(list[dict[str, object]], payload["pair_quality_evidence"])) == 24
    assert payload["selected_pair_manifest"] == []
    dimensions = cast(list[dict[str, object]], payload["dimension_eligibility"])
    assert all(dimension["global_exact_sha_gate_passed"] is False for dimension in dimensions)
    assert all(dimension["eligible"] is False for dimension in dimensions)
    assert all(
        dimension["failure_reasons"] == [legacy._FAILURE_REASONS[3]] for dimension in dimensions
    )
    selection = cast(list[dict[str, object]], payload["fixed_priority_selection_trace"])
    assert all(record["selection_decision"] == "INELIGIBLE" for record in selection)


def test_r2_b3_rejects_fully_resigned_phash_binding_order_and_distance() -> None:
    fields, _ = _report_input()
    payload = cast(dict[str, object], fields["report_payload"])
    exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
    images = cast(list[dict[str, object]], exact["image_records"])
    binding = cast(dict[str, object], payload["schema_and_policy"])

    reordered = deepcopy(cast(dict[str, object], payload["phash_observation_evidence"]))
    signatures = cast(list[dict[str, object]], reordered["ordered_record_signatures"])
    signatures[0], signatures[1] = signatures[1], signatures[0]
    _resign_r2_phash_matrix(reordered)
    with pytest.raises(D02R2AuthorityError, match="signature image binding"):
        r2._validate_r2_phash_observation_evidence(
            reordered, image_records=images, execution_authority=binding
        )

    wrong_distance = deepcopy(cast(dict[str, object], payload["phash_observation_evidence"]))
    comparison = cast(list[dict[str, object]], wrong_distance["comparisons"])[0]
    comparison["hamming_distance"] = (cast(int, comparison["hamming_distance"]) + 1) % 65
    comparison["comparison_digest"] = r2._r2_phash_comparison_digest(comparison)
    with pytest.raises(D02R2AuthorityError, match="Hamming distance"):
        r2._validate_r2_phash_observation_evidence(
            wrong_distance, image_records=images, execution_authority=binding
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("public_internet_egress", "ALLOWED"),
        ("localhost_and_docker_internal_network", False),
        ("proxy_environment_present", True),
        ("production_provider_calls", 1),
        ("runtime_generation_calls", 1),
    ),
)
def test_r2_b3_rejects_resigned_network_or_runtime_boundary(field: str, value: object) -> None:
    boundary = cast(dict[str, object], build_r2_network_runtime_boundary())
    boundary[field] = value
    _resign_r2_network_boundary(boundary)
    with pytest.raises(D02R2AuthorityError, match="network and runtime boundary"):
        r2._validate_r2_network_runtime_boundary(boundary)


@pytest.mark.parametrize(
    "field",
    (
        "case_id",
        "result_asset_id",
        "asset_variant_id",
        "lineage_digest",
        "image_record_id",
        "measurement_gate_record_digest",
        "manual_decision_digest",
    ),
)
def test_r2_b3_rejects_resigned_pair_side_cross_layer_splice(field: str) -> None:
    fields, packets = _report_input()
    payload = deepcopy(cast(dict[str, object], fields["report_payload"]))
    pairs = cast(list[dict[str, object]], payload["pair_quality_evidence"])
    first_payload = cast(dict[str, object], pairs[0]["pair_screening_record_payload"])
    other_payload = cast(dict[str, object], pairs[1]["pair_screening_record_payload"])
    left = cast(dict[str, object], first_payload["left"])
    other_left = cast(dict[str, object], other_payload["left"])
    left[field] = other_left[field]
    first_payload["pair_record_id"] = r2._pair_record_id(first_payload)
    pairs[0]["pair_screening_record_digest"] = mirror_demo_digest(
        r2.R2_PAIR_SCREENING_SCHEMA, first_payload
    )

    with pytest.raises(D02R2AuthorityError, match="execution graph projection"):
        r2._validate_r2_b3_report_graph(payload, source_packets=packets)


def test_r2_report_requires_exact_source_admission_projection() -> None:
    report, packets = _report()
    forged_packets = deepcopy(packets)
    cast(dict[str, object], forged_packets[0]["source_manifest_entry"])["source_output_id"] = (
        "other-output"
    )
    with pytest.raises(D02R2AuthorityError):
        validate_r2_report_row(report, source_packets=forged_packets)


def test_r2_report_binds_every_admission_packet_to_the_cohort_manifest() -> None:
    report, packets = _report()
    forged_packets = deepcopy(packets)
    forged_packets[0]["source_manifest_digest"] = _digest("other-cohort-manifest")

    with pytest.raises(D02R2AuthorityError, match="differs from cohort authority"):
        validate_r2_report_row(report, source_packets=forged_packets)


def test_r2_bank_and_pair_replay_full_report_membership() -> None:
    report, packets = _report()
    entries = cast(
        list[dict[str, object]],
        cast(dict[str, object], report["report_payload"])["selected_pair_manifest"],
    )
    dimensions = cast(
        list[dict[str, object]],
        cast(dict[str, object], report["report_payload"])["dimension_eligibility"],
    )
    manifest = {
        "schema_version": "mirror.demo/D02QuestionBankDimensionManifest/v2",
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
        "source_manifest_digest": report["source_manifest_digest"],
        "source_p2_candidate_manifest_content_digest": _digest("p2"),
        "dimension_authority_manifest_content_digest": _digest("dimension"),
        "selected_pair_manifest_digest": report["selected_pair_manifest_digest"],
        "selected_dimensions": [
            {
                "dimension_key": dimension,
                "priority_index": slot,
                "sixteen_side_gate_digest": dimensions[slot - 1]["sixteen_side_gate_digest"],
                "eight_pair_gate_digest": dimensions[slot - 1]["eight_pair_gate_digest"],
                "ordered_selected_pair_entry_digests": [
                    entry["entry_digest"] for entry in entries[(slot - 1) * 8 : slot * 8]
                ],
            }
            for slot, dimension in enumerate(legacy.CASE_DIMENSIONS[:2], start=1)
        ],
    }
    bank_fields = {
        "created_at": "2026-08-26T00:00:00Z",
        "version": "d02-r2-v3",
        "algorithm_config_digest": _digest("algorithm"),
        "routing_version": "routing-v3",
        "stopping_version": "stopping-v3",
        "neighborhood_version": "neighborhood-v3",
        "pair_manifest_digest": report["selected_pair_manifest_digest"],
        "dimension_manifest": manifest,
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
    }
    bank = build_r2_question_bank_row(bank_fields, report=report, source_packets=packets)
    assert validate_r2_question_bank_row(bank, report=report, source_packets=packets) == bank
    selected = entries[0]
    record = cast(
        list[dict[str, object]],
        cast(dict[str, object], report["report_payload"])["pair_quality_evidence"],
    )[0]
    source = cast(
        list[dict[str, object]],
        cast(dict[str, object], report["report_payload"])["ordered_source_manifest"],
    )[0]
    qa = {
        "schema_version": "mirror.demo/D02QuestionPairQAPayload/v3",
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
        "source_manifest_digest": report["source_manifest_digest"],
        "source_manifest_entry_schema_version": source["schema_version"],
        "source_manifest_entry_digest": source["record_digest"],
        "pair_screening_record_schema_version": record["schema_version"],
        "pair_screening_record_digest": record["pair_screening_record_digest"],
        "pair_screening_record_payload": record,
        "selected_pair_manifest_digest": report["selected_pair_manifest_digest"],
        "selected_pair_entry_schema_version": selected["schema_version"],
        "selected_pair_entry_digest": selected["entry_digest"],
        "selected_pair_entry_payload": selected,
    }
    pair_payload = cast(dict[str, object], record["pair_screening_record_payload"])
    left, right = (
        cast(dict[str, object], pair_payload["left"]),
        cast(dict[str, object], pair_payload["right"]),
    )
    pair_fields = {
        "created_at": "2026-08-26T00:00:00Z",
        "question_bank_id": bank["id"],
        "demo_synthetic_identity_id": source["source_admission_event_id"],
        "source_asset_id": pair_payload["source_asset_id"],
        "source_asset_sha256": pair_payload["source_asset_sha256"],
        "left_asset_id": left["result_asset_id"],
        "left_asset_sha256": left["result_asset_sha256"],
        "right_asset_id": right["result_asset_id"],
        "right_asset_sha256": right["result_asset_sha256"],
        "left_asset_variant_id": left["asset_variant_id"],
        "right_asset_variant_id": right["asset_variant_id"],
        "dimension_key": pair_payload["dimension_key"],
        "magnitude_ppm": pair_payload["magnitude_ppm"],
        "left_delta_ppm": -15_000,
        "right_delta_ppm": 15_000,
        "pair_quality_ppm": pair_payload["pair_quality_ppm"],
        "qa_payload": qa,
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
    }
    pair = build_r2_question_pair_row(pair_fields, report=report, bank=bank, source_packets=packets)
    assert (
        validate_r2_question_pair_row(pair, report=report, bank=bank, source_packets=packets)
        == pair
    )

    # These are builder replays, rather than stale-row digest checks: each
    # attack asks the builder to calculate a fresh canonical payload and ID.
    # The authority graph must reject the substituted member before a forged
    # persisted row can be produced.
    forged_bank_fields = {key: deepcopy(bank[key]) for key in r2.R2_BANK_FIELDS}
    forged_manifest = cast(dict[str, object], forged_bank_fields["dimension_manifest"])
    forged_dimensions = cast(list[dict[str, object]], forged_manifest["selected_dimensions"])
    forged_dimensions[0]["ordered_selected_pair_entry_digests"][0] = _digest(
        "fully-resigned-bank-selected-member"
    )
    with pytest.raises(D02R2AuthorityError, match="selected"):
        build_r2_question_bank_row(forged_bank_fields, report=report, source_packets=packets)

    # Entry two is the other magnitude for the same source.  Use entry three
    # so both the source and its selected-side asset lineage are substituted.
    second_selected = entries[2]
    second_record = cast(
        list[dict[str, object]],
        cast(dict[str, object], report["report_payload"])["pair_quality_evidence"],
    )[2]
    second_pair_payload = cast(dict[str, object], second_record["pair_screening_record_payload"])
    second_left = cast(dict[str, object], second_pair_payload["left"])
    forged_pair_fields = {key: deepcopy(pair[key]) for key in r2.R2_PAIR_FIELDS}
    forged_pair_fields.update(
        demo_synthetic_identity_id=second_selected["source_admission_event_id"],
        source_asset_id=second_pair_payload["source_asset_id"],
        left_asset_id=second_left["result_asset_id"],
        left_asset_variant_id=second_left["asset_variant_id"],
    )
    with pytest.raises(D02R2AuthorityError):
        build_r2_question_pair_row(
            forged_pair_fields, report=report, bank=bank, source_packets=packets
        )

    for mutation in ("screening_report_digest", "source_asset_sha256", "left_asset_id"):
        forged = deepcopy(pair)
        forged[mutation] = (
            _digest("forged")
            if mutation.endswith("digest") or mutation.endswith("sha256")
            else _digest("forged")[:32]
        )
        with pytest.raises(D02R2AuthorityError):
            validate_r2_question_pair_row(forged, report=report, bank=bank, source_packets=packets)
