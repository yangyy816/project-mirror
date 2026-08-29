"""Offline, fail-closed execution boundary for the frozen D02-R2 graph.

The boundary accepts only already-validated source admission packets and
opaque adapter outputs.  It deliberately has no persistence, networking, or
private-locator concerns: callers retain custody of image bytes and handles.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as authority
from mirror_api import demo_measurement_quality as measurement


class ScreeningExecutionError(ValueError):
    """The offline screening run could not produce one complete authority graph."""


class CaseFieldsAdapter(Protocol):
    def case_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        source_entry: Mapping[str, object],
        case_ordinal: int,
        dimension_key: str,
        direction: str,
        magnitude_ppm: int,
    ) -> Mapping[str, object]: ...


class VisionM3Adapter(Protocol):
    def inspect_source(
        self, *, source_packet: Mapping[str, object], repeat_index: int
    ) -> Mapping[str, object]: ...

    def inspect_result(
        self,
        *,
        case_entry: Mapping[str, object],
        m4_record: Mapping[str, object],
        repeat_index: int,
    ) -> Mapping[str, object]: ...


class M4ReplayAdapter(Protocol):
    def transform(
        self,
        *,
        source_packet: Mapping[str, object],
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> Mapping[str, object]: ...


class MeasurementGateAdapter(Protocol):
    def evaluate(
        self,
        *,
        source_packet: Mapping[str, object],
        case_entry: Mapping[str, object],
        result_m3_records: Sequence[Mapping[str, object]],
        result_repeat_certification: Mapping[str, object],
    ) -> Mapping[str, object]: ...


class ManualReviewAdapter(Protocol):
    def decision_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        case_entry: Mapping[str, object],
        m4_record: Mapping[str, object],
        decision_sequence: int,
    ) -> Mapping[str, object]: ...


class PHashAdapter(Protocol):
    def phash_hex(self, *, image_record: Mapping[str, object]) -> str: ...


@dataclass(frozen=True)
class OfflineScreeningRequest:
    """Dependencies needed for one deterministic, non-persistent R2 run."""

    created_at: str
    source_packets: Sequence[Mapping[str, object]]
    execution_authority: Mapping[str, object]
    case_fields: CaseFieldsAdapter
    vision_m3: VisionM3Adapter
    m4: M4ReplayAdapter
    measurement_gate: MeasurementGateAdapter
    manual_review: ManualReviewAdapter
    phash: PHashAdapter


def run_offline_screening(request: OfflineScreeningRequest) -> dict[str, Any]:
    """Run the entire frozen R2 graph and return only a fully validated report.

    Every intermediate object remains local until ``build_r2_report_row`` has
    replayed the whole graph.  Thus an exception never exposes a partial
    report for persistence or admission.
    """

    try:
        packets, sources, source_manifest_digest = _validated_sources(request.source_packets)
        execution_authority = dict(request.execution_authority)
        execution_authority["source_manifest_digest"] = source_manifest_digest

        cases = _build_cases(
            request.case_fields,
            packets=packets,
            sources=sources,
            execution_authority=execution_authority,
        )
        execution_authority["case_manifest_digest"] = legacy._sequence_digest(
            authority.R2_CASE_MANIFEST_SCHEMA, cases
        )
        source_m3 = _build_source_m3(
            request.vision_m3,
            packets=packets,
            sources=sources,
            source_manifest_digest=source_manifest_digest,
        )
        m4_records = _build_m4(request.m4, packets=packets, cases=cases)
        result_m3, result_certificates = _build_result_m3(
            request.vision_m3, packets=packets, cases=cases, m4_records=m4_records
        )
        gates = _build_gates(
            request.measurement_gate,
            packets=packets,
            cases=cases,
            result_m3=result_m3,
            certificates=result_certificates,
        )
        images = authority.build_r2_image_authority_evidence(
            source_packets=packets,
            case_manifest=cases,
            m4_records=m4_records,
            execution_authority=execution_authority,
        )
        image_id_by_case = {
            cast(str, image["case_id"]): cast(str, image["image_record_id"])
            for image in images
            if image["authority_role"] == "RESULT"
        }
        structures = _build_structures(
            cases=cases,
            sources=sources,
            m4_records=m4_records,
            execution_authority=execution_authority,
            image_id_by_case=image_id_by_case,
        )
        manuals = _build_manuals(
            request.manual_review,
            packets=packets,
            cases=cases,
            sources=sources,
            m4_records=m4_records,
            execution_authority=execution_authority,
        )
        exact_duplicate = authority.build_r2_exact_duplicate_evidence(images)
        phashes = {
            cast(str, image["image_record_id"]): request.phash.phash_hex(image_record=image)
            for image in images
        }
        phash_observations = authority.build_r2_phash_observation_evidence(
            image_records=images,
            image_phashes=phashes,
            execution_authority=execution_authority,
        )
        pairs = authority.build_r2_pair_screening_evidence(
            source_packets=packets,
            case_manifest=cases,
            m4_records=m4_records,
            result_records=result_m3,
            gates=gates,
            structure_records=structures,
            manual_records=manuals,
            image_records=images,
            execution_authority=execution_authority,
        )
        dimensions = _build_r2_dimensions(
            pairs, exact_sha_gate_passed=exact_duplicate["exact_sha_gate_passed"] is True
        )
        selection, eligible, selected, status = _build_r2_selection(dimensions)
        selected_manifest, selected_digest = _build_r2_selected_manifest(pairs, selected)
        payload: dict[str, object] = {
            "schema_and_policy": execution_authority,
            "ordered_source_manifest": sources,
            "ordered_case_manifest": cases,
            "source_m3_repeat_evidence": source_m3,
            "m4_repeat_evidence": m4_records,
            "result_m3_repeat_evidence": result_m3,
            "measurement_gate_evidence": gates,
            "decode_structure_immutability_evidence": structures,
            "manual_review_evidence": manuals,
            "exact_duplicate_evidence": exact_duplicate,
            "phash_observation_evidence": phash_observations,
            "pair_quality_evidence": pairs,
            "dimension_eligibility": dimensions,
            "fixed_priority_selection_trace": selection,
            "selected_pair_manifest": selected_manifest,
            "network_and_runtime_boundary": authority.build_r2_network_runtime_boundary(),
        }
        return authority.build_r2_report_row(
            _report_fields(
                created_at=request.created_at,
                source_manifest_digest=source_manifest_digest,
                execution_authority=execution_authority,
                payload=payload,
                eligible=eligible,
                selected=selected,
                status=status,
                selected_digest=selected_digest,
            ),
            source_packets=packets,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ScreeningExecutionError("D02-R2 offline screening failed closed") from error


def _validated_sources(
    source_packets: Sequence[Mapping[str, object]],
) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]], str]:
    if len(source_packets) != 4:
        raise ScreeningExecutionError("D02-R2 requires exactly four source packets")
    packets = list(source_packets)
    sources: list[Mapping[str, object]] = []
    for ordinal, packet in enumerate(packets, start=1):
        authority.validate_r2_admission_packet(packet)
        source = packet.get("source_manifest_entry")
        if not isinstance(source, Mapping) or source.get("source_ordinal") != ordinal:
            raise ScreeningExecutionError("source packet order is invalid")
        sources.append(source)
    digest = legacy._sequence_digest(authority.R2_SOURCE_MANIFEST_SCHEMA, sources)
    if any(packet.get("source_manifest_digest") != digest for packet in packets):
        raise ScreeningExecutionError("source packets are not bound to one cohort manifest")
    return packets, sources, digest


def _build_cases(
    adapter: CaseFieldsAdapter,
    *,
    packets: Sequence[Mapping[str, object]],
    sources: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    ordinal = 1
    for source_ordinal, (packet, source) in enumerate(zip(packets, sources, strict=True), start=1):
        for priority, dimension in enumerate(legacy.CASE_DIMENSIONS, start=1):
            for direction_index, direction in enumerate(legacy.CASE_DIRECTIONS, start=1):
                for magnitude_index, magnitude in enumerate(legacy.CASE_MAGNITUDES, start=1):
                    fields = dict(
                        adapter.case_fields(
                            source_packet=packet,
                            source_entry=source,
                            case_ordinal=ordinal,
                            dimension_key=dimension,
                            direction=direction,
                            magnitude_ppm=magnitude,
                        )
                    )
                    fields.update(
                        {
                            "case_ordinal": ordinal,
                            "source_manifest_digest": execution_authority["source_manifest_digest"],
                            "source_ordinal": source_ordinal,
                            "source_authority_key": source["source_authority_key"],
                            "source_admission_event_id": source["source_admission_event_id"],
                            "source_asset_id": source["source_asset_id"],
                            "source_asset_sha256": source["source_asset_sha256"],
                            "source_qa_snapshot_digest": source["source_qa_snapshot_digest"],
                            "source_measurement_projection_digest": source[
                                "source_measurement_projection_digest"
                            ],
                            "source_p2_candidate_manifest_content_digest": source[
                                "source_p2_candidate_manifest_content_digest"
                            ],
                            "dimension_authority_manifest_content_digest": source[
                                "dimension_authority_manifest_content_digest"
                            ],
                            "r2_source_authority_record_id": source[
                                "r2_source_authority_record_id"
                            ],
                            "dimension_key": dimension,
                            "priority_index": priority,
                            "direction": direction,
                            "direction_index": direction_index,
                            "magnitude_ppm": magnitude,
                            "magnitude_index": magnitude_index,
                            "ordered_control_dimensions": list(legacy._case_controls(dimension)),
                            "runtime_manifest_digest": execution_authority[
                                "runtime_manifest_digest"
                            ],
                        }
                    )
                    cases.append(
                        authority.build_r2_case_manifest_entry(
                            fields, execution_authority=execution_authority
                        )
                    )
                    ordinal += 1
    return cases


def _build_source_m3(
    adapter: VisionM3Adapter,
    *,
    packets: Sequence[Mapping[str, object]],
    sources: Sequence[Mapping[str, object]],
    source_manifest_digest: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for packet, source in zip(packets, sources, strict=True):
        for repeat_index in range(1, 4):
            fields = dict(adapter.inspect_source(source_packet=packet, repeat_index=repeat_index))
            fields.update(
                {
                    "source_ordinal": source["source_ordinal"],
                    "source_authority_key": source["source_authority_key"],
                    "source_admission_event_id": source["source_admission_event_id"],
                    "source_asset_id": source["source_asset_id"],
                    "source_asset_sha256": source["source_asset_sha256"],
                    "source_authority_digest": source["source_authority_digest"],
                    "repeat_index": repeat_index,
                }
            )
            records.append(
                authority.build_r2_source_m3_record(
                    fields, source_manifest_digest=source_manifest_digest
                )
            )
        _replay_source_certificate(packet, records[-3:])
    return records


def _build_m4(
    adapter: M4ReplayAdapter,
    *,
    packets: Sequence[Mapping[str, object]],
    cases: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in cases:
        packet = packets[cast(int, case["source_ordinal"]) - 1]
        pair: list[dict[str, Any]] = []
        for replay_index in (1, 2):
            fields = dict(
                adapter.transform(source_packet=packet, case_entry=case, replay_index=replay_index)
            )
            fields.update(
                {
                    "case_id": case["case_id"],
                    "case_specification_digest": case["case_specification_digest"],
                    "replay_index": replay_index,
                    "source_asset_id": case["source_asset_id"],
                    "source_asset_sha256": case["source_asset_sha256"],
                    "warp_plan_digest": case["warp_plan_digest"],
                    "geometry_algorithm_version": case["geometry_algorithm_version"],
                    "runtime_manifest_digest": case["runtime_manifest_digest"],
                    "runtime_config_digest": case["runtime_config_digest"],
                    "determinism_level": case["determinism_level"],
                }
            )
            pair.append(authority.build_r2_m4_execution_record(fields))
        if any(pair[0][key] != pair[1][key] for key in _M4_DETERMINISM_KEYS):
            raise ScreeningExecutionError("M4 replay output is not deterministic")
        records.extend(pair)
    return records


_M4_DETERMINISM_KEYS = (
    "result_output_id",
    "result_sha256",
    "result_byte_size",
    "result_mime_type",
    "result_width",
    "result_height",
    "changed_pixel_count",
)


def _build_result_m3(
    adapter: VisionM3Adapter,
    *,
    packets: Sequence[Mapping[str, object]],
    cases: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, Any]], list[Mapping[str, object]]]:
    records: list[dict[str, Any]] = []
    certificates: list[Mapping[str, object]] = []
    for index, case in enumerate(cases):
        first_m4 = m4_records[index * 2]
        case_records: list[dict[str, Any]] = []
        for repeat_index in range(1, 4):
            fields = dict(
                adapter.inspect_result(
                    case_entry=case, m4_record=first_m4, repeat_index=repeat_index
                )
            )
            fields.update(
                {
                    "case_id": case["case_id"],
                    "case_specification_digest": case["case_specification_digest"],
                    "result_output_id": first_m4["result_output_id"],
                    "result_sha256": first_m4["result_sha256"],
                    "repeat_index": repeat_index,
                    "runtime_manifest_digest": case["runtime_manifest_digest"],
                }
            )
            case_records.append(authority.build_r2_result_m3_record(fields))
        records.extend(case_records)
        certificates.append(_result_certificate(case_records))
    return records, certificates


def _build_gates(
    adapter: MeasurementGateAdapter,
    *,
    packets: Sequence[Mapping[str, object]],
    cases: Sequence[Mapping[str, object]],
    result_m3: Sequence[Mapping[str, object]],
    certificates: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        result_records = result_m3[index * 3 : index * 3 + 3]
        certificate = certificates[index]
        fields = dict(
            adapter.evaluate(
                source_packet=packets[index // 12],
                case_entry=case,
                result_m3_records=result_records,
                result_repeat_certification=certificate,
            )
        )
        fields.update(
            {
                "case_id": case["case_id"],
                "case_specification_digest": case["case_specification_digest"],
                "dimension_key": case["dimension_key"],
                "requested_direction": case["direction"],
                "requested_magnitude_ppm": case["magnitude_ppm"],
                "monotonicity_peer_case_id": cases[index + 1 if index % 2 == 0 else index - 1][
                    "case_id"
                ],
                "result_repeat_certification": certificate,
                "result_repeat_certification_digest": certificate[
                    "result_repeat_certification_digest"
                ],
            }
        )
        gates.append(authority.build_r2_measurement_gate(fields))
    return gates


def _build_structures(
    *,
    cases: Sequence[Mapping[str, object]],
    sources: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    image_id_by_case: Mapping[str, str],
) -> list[dict[str, Any]]:
    return [
        authority.build_r2_decode_structure_record(
            {"result_image_record_id": image_id_by_case[cast(str, case["case_id"])]},
            case_entry=case,
            source_entry=sources[cast(int, case["source_ordinal"]) - 1],
            m4_first=m4_records[index * 2],
            m4_second=m4_records[index * 2 + 1],
            execution_authority=execution_authority,
        )
        for index, case in enumerate(cases)
    ]


def _build_manuals(
    adapter: ManualReviewAdapter,
    *,
    packets: Sequence[Mapping[str, object]],
    cases: Sequence[Mapping[str, object]],
    sources: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> list[dict[str, Any]]:
    ordered = sorted(enumerate(cases), key=lambda item: cast(str, item[1]["case_id"]))
    records: list[dict[str, Any]] = []
    for decision_sequence, (index, case) in enumerate(ordered, start=1):
        fields = dict(
            adapter.decision_fields(
                source_packet=packets[index // 12],
                case_entry=case,
                m4_record=m4_records[index * 2],
                decision_sequence=decision_sequence,
            )
        )
        fields["decision_sequence"] = decision_sequence
        records.append(
            authority.build_r2_manual_artifact_decision(
                fields,
                case_entry=case,
                source_entry=sources[index // 12],
                m4_first=m4_records[index * 2],
                execution_authority=execution_authority,
            )
        )
    return records


def _measurement_bindings(observation: Mapping[str, object]) -> measurement.AuthorityBindings:
    return measurement.AuthorityBindings(
        runtime_manifest_digest=cast(str, observation["runtime_manifest_digest"]),
        vision_model_manifest_digest=cast(str, observation["vision_model_manifest_digest"]),
        topology_digest=cast(str, observation["topology_digest"]),
        measurement_config_digest=cast(str, observation["measurement_config_digest"]),
        measurement_quality_config_digest=cast(
            str, observation["measurement_quality_config_digest"]
        ),
        measurement_quality_manifest_content_digest=cast(
            str, observation["measurement_quality_manifest_content_digest"]
        ),
    )


def _replay_source_certificate(
    packet: Mapping[str, object], records: Sequence[Mapping[str, object]]
) -> None:
    facts = _required_mapping(packet, "facts")
    expected = _required_mapping(facts, "source_repeat_certification")
    observation = _required_mapping(records[0], "measurement_observation")
    replay = measurement.build_source_repeat_certification(
        subject=_required_mapping(expected, "subject"),
        bindings=_measurement_bindings(observation),
        ordered_repeat_bindings=[
            {
                key: record[key]
                for key in (
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
                )
            }
            for record in records
        ],
    )
    if replay != expected:
        raise ScreeningExecutionError("source M3 repeats do not replay the verified certificate")


def _result_certificate(records: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
    observation = _required_mapping(records[0], "measurement_observation")
    bindings = _measurement_bindings(observation)
    legacy_records: list[dict[str, object]] = []
    for record in records:
        legacy_record = {
            key: record[key]
            for key in (
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
            )
        }
        legacy_record["schema_version"] = measurement.RESULT_M3_REPEAT_RECORD_SCHEMA
        legacy_record["result_m3_record_id"] = measurement.derive_result_m3_record_id(
            case_id=legacy_record["case_id"],
            case_specification_digest=legacy_record["case_specification_digest"],
            result_output_id=legacy_record["result_output_id"],
            result_sha256=legacy_record["result_sha256"],
            repeat_index=legacy_record["repeat_index"],
            bindings=bindings,
        )
        legacy_record["record_digest"] = measurement.mirror_demo_digest(
            measurement.RESULT_M3_REPEAT_RECORD_SCHEMA,
            cast(
                dict[str, measurement.JsonValue],
                {
                    key: value
                    for key, value in legacy_record.items()
                    if key not in {"schema_version", "record_digest"}
                },
            ),
        )
        legacy_records.append(legacy_record)
    certificate = measurement.build_result_repeat_certification(
        subject=_required_mapping(observation, "subject"),
        bindings=bindings,
        result_m3_records=legacy_records,
    )
    certificate["ordered_repeat_bindings"] = cast(
        list[measurement.JsonValue],
        [
            {
                "result_m3_record_id": record["result_m3_record_id"],
                "repeat_index": record["repeat_index"],
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
            for record in records
        ],
    )
    certificate["result_repeat_certification_digest"] = measurement.mirror_demo_digest(
        measurement.RESULT_CERTIFICATE_SCHEMA,
        cast(
            dict[str, measurement.JsonValue],
            {
                key: value
                for key, value in certificate.items()
                if key not in {"schema_version", "result_repeat_certification_digest"}
            },
        ),
    )
    return certificate


def _build_r2_dimensions(
    pairs: Sequence[Mapping[str, object]], *, exact_sha_gate_passed: bool
) -> list[dict[str, Any]]:
    legacy_pairs = [{**pair, "schema_version": legacy.PAIR_SCHEMA} for pair in pairs]
    records = legacy.build_dimension_eligibility_evidence(
        legacy_pairs, exact_sha_gate_passed=exact_sha_gate_passed
    )
    result: list[dict[str, Any]] = []
    for record in records:
        r2_record = dict(record)
        r2_record["schema_version"] = authority.R2_DIMENSION_SCHEMA
        r2_record["record_digest"] = measurement.mirror_demo_digest(
            authority.R2_DIMENSION_SCHEMA,
            {
                key: value
                for key, value in r2_record.items()
                if key not in {"schema_version", "record_digest"}
            },
        )
        result.append(r2_record)
    return result


def _build_r2_selection(
    dimensions: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, Any]], list[str], list[str], str]:
    eligible = [cast(str, item["dimension_key"]) for item in dimensions if item["eligible"] is True]
    selected = eligible[:2] if len(eligible) >= 2 else []
    records: list[dict[str, Any]] = []
    for index, dimension in enumerate(dimensions, start=1):
        is_eligible = dimension["eligible"] is True
        rank = eligible.index(cast(str, dimension["dimension_key"])) + 1 if is_eligible else 0
        selected_slot = (
            selected.index(cast(str, dimension["dimension_key"])) + 1
            if cast(str, dimension["dimension_key"]) in selected
            else 0
        )
        decision = (
            "INELIGIBLE"
            if not is_eligible
            else "ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET"
            if len(eligible) < 2
            else "SELECTED_SLOT_1"
            if rank == 1
            else "SELECTED_SLOT_2"
            if rank == 2
            else "ELIGIBLE_NOT_SELECTED_CAPACITY"
        )
        record: dict[str, Any] = {
            "schema_version": authority.R2_SELECTION_SCHEMA,
            "selection_step": index,
            "dimension_key": dimension["dimension_key"],
            "priority_index": dimension["priority_index"],
            "dimension_eligibility_record_digest": dimension["record_digest"],
            "eligible": is_eligible,
            "eligible_rank": rank,
            "selection_decision": decision,
            "selection_slot": selected_slot,
            "selected": selected_slot != 0,
        }
        record["record_digest"] = measurement.mirror_demo_digest(
            authority.R2_SELECTION_SCHEMA,
            {
                key: value
                for key, value in record.items()
                if key not in {"schema_version", "record_digest"}
            },
        )
        records.append(record)
    return records, eligible, selected, "PASSED" if len(eligible) >= 2 else "FAILED"


def _build_r2_selected_manifest(
    pairs: Sequence[Mapping[str, object]], selected: Sequence[str]
) -> tuple[list[dict[str, Any]], str | None]:
    if not selected:
        return [], None
    legacy_pairs = [{**pair, "schema_version": legacy.PAIR_SCHEMA} for pair in pairs]
    entries, _ = legacy.build_selected_pair_manifest(legacy_pairs, selected_dimension_keys=selected)
    result: list[dict[str, Any]] = []
    for entry in entries:
        r2_entry = dict(entry)
        r2_entry["schema_version"] = authority.R2_SELECTED_ENTRY_SCHEMA
        r2_entry["entry_digest"] = measurement.mirror_demo_digest(
            authority.R2_SELECTED_ENTRY_SCHEMA,
            {
                key: value
                for key, value in r2_entry.items()
                if key not in {"schema_version", "entry_digest"}
            },
        )
        result.append(r2_entry)
    return result, legacy._sequence_digest(authority.R2_SELECTED_MANIFEST_SCHEMA, result)


def _report_fields(
    *,
    created_at: str,
    source_manifest_digest: str,
    execution_authority: Mapping[str, object],
    payload: Mapping[str, object],
    eligible: Sequence[str],
    selected: Sequence[str],
    status: str,
    selected_digest: str | None,
) -> dict[str, object]:
    return {
        "created_at": created_at,
        "source_manifest_digest": source_manifest_digest,
        "case_manifest_digest": execution_authority["case_manifest_digest"],
        "screening_policy_digest": execution_authority["screening_policy_digest"],
        "runtime_manifest_digest": execution_authority["runtime_manifest_digest"],
        "vision_model_manifest_digest": execution_authority["vision_model_manifest_digest"],
        "topology_digest": execution_authority["topology_digest"],
        "measurement_config_digest": execution_authority["measurement_config_digest"],
        "manual_review_policy_digest": execution_authority["manual_review_policy_digest"],
        "duplicate_policy_digest": execution_authority["duplicate_policy_digest"],
        "phash_implementation_digest": execution_authority["phash_implementation_digest"],
        "report_payload": payload,
        "status": status,
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
        "selected_pair_count": 16 if status == "PASSED" else 0,
        "selected_result_side_count": 32 if status == "PASSED" else 0,
        "eligible_dimension_keys": list(eligible),
        "selected_dimension_keys": list(selected),
        "selected_pair_manifest_digest": selected_digest,
    }


def _required_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    candidate = value.get(key)
    if not isinstance(candidate, Mapping):
        raise ScreeningExecutionError(f"{key} must be a mapping")
    return candidate
