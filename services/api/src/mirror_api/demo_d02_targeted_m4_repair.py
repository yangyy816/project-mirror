"""Pure, fail-closed successor composition for ADR-053.

This module never calls an M3/M4 backend, reads a checkpoint, or persists
anything.  It composes the already reviewed predecessor evidence with the one
durable Case 25 replacement authorized by ADR-053.  The caller subsequently
hands ``prepared`` and ``artifact_decisions`` to the ordinary finalizer.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_final_orchestrator as orchestrator
from mirror_api import demo_d02_r2_authority as r2
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_r2_screening_execution as screening
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest

REPAIR_POLICY_SCHEMA: Final = "mirror.demo/D02TargetedM4RepairPolicy/v1"
REPAIR_IMPLEMENTATION_SCHEMA: Final = "mirror.demo/D02TargetedM4RepairImplementation/v1"
REPAIR_SCOPE_SCHEMA: Final = "mirror.demo/D02TargetedM4RepairScope/v1"
SUCCESSOR_UNIVERSE_SCHEMA: Final = "mirror.demo/D02TargetedM4RepairUniverse/v1"
SUCCESSOR_ENVELOPE_SCHEMA: Final = "mirror.demo/D02TargetedM4RepairProvenance/v1"
SUCCESSOR_SLOT_SCHEMA: Final = "mirror.demo/D02TargetedM4RepairSlot/v1"

TARGET_CASE_ORDINAL: Final = 25
TARGET_SOURCE_ORDINAL: Final = 3
TARGET_SELECTOR: Final = {
    "case_ordinal": 25,
    "source_ordinal": TARGET_SOURCE_ORDINAL,
    "dimension_key": "jaw_width",
    "direction": "DECREASE",
    "magnitude_ppm": 15_000,
}
_CASE_FIELD_KEYS: Final = (
    "geometry_ontology_version_digest",
    "warp_plan_digest",
    "geometry_algorithm_version",
    "runtime_config_digest",
    "output_policy_version",
    "output_width",
    "output_height",
    "determinism_level",
)
_PRIVATE_KEYS: Final = frozenset(
    {
        "absolute_path",
        "content",
        "image_bytes",
        "locator",
        "object_key",
        "path",
        "private_locator",
        "prompt",
        "prompt_text",
        "raw_bytes",
        "secret",
        "signed_url",
        "storage_key",
        "token",
        "url",
    }
)


class D02TargetedM4RepairError(RuntimeError):
    """Stable public error; never embeds evidence, paths, or bytes."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True, repr=False)
class TargetedM4RepairSuccessor:
    """The composite evidence and projected decisions for the normal finalizer."""

    prepared: orchestrator.PreparedRuntimeEvidence
    artifact_decisions: Mapping[str, PrincipalArtifactDecision]
    predecessor_report_id: str
    predecessor_case_id: str
    successor_case_id: str
    repair_policy_digest: str
    repair_implementation_digest: str
    successor_universe: Mapping[str, object]
    successor_universe_digest: str
    provenance_envelope: Mapping[str, object]

    @property
    def reexecution_counts(self) -> Mapping[str, int]:
        return {
            "provider": 0,
            "source_m3": 0,
            "m4": 2,
            "result_m3": 3,
            "manual_review": 1,
        }


def build_repair_policy(*, policy_version: str = "D02_TARGETED_JAW_REPAIR_V1") -> dict[str, object]:
    """Return the fixed ADR-053 policy and its canonical digest."""

    if not isinstance(policy_version, str) or not legacy._VERSION.fullmatch(policy_version):
        _fail("REPAIR_POLICY_INVALID")
    payload: dict[str, object] = {
        "schema_version": REPAIR_POLICY_SCHEMA,
        "policy_version": policy_version,
        "target_selector": dict(TARGET_SELECTOR),
        "provider_reexecution": False,
        "source_m3_reexecution": False,
        "m4_reexecution_count": 2,
        "result_m3_reexecution_count": 3,
        "manual_review_count": 1,
        "minimum_effect_margin_ppm": 10,
        "required_target_direction": "STRICTLY_NEGATIVE",
        "monotonicity_peer_case_ordinal": 26,
        "canonical_source_input": "BOUND_CANONICAL_SOURCE_JPEG_ONLY",
        "landmark_input": "FORBIDDEN",
        "network": "FORBIDDEN",
    }
    return {**payload, "repair_policy_digest": _digest(REPAIR_POLICY_SCHEMA, payload)}


def build_repair_implementation(
    *,
    algorithm_version: str,
    implementation_digest: str,
    configuration_digest: str,
) -> dict[str, object]:
    """Bind the selected, source-byte-only implementation without private inputs."""

    if (
        not isinstance(algorithm_version, str)
        or legacy._VERSION.fullmatch(algorithm_version) is None
        or not _is_digest(implementation_digest)
        or not _is_digest(configuration_digest)
    ):
        _fail("REPAIR_IMPLEMENTATION_INVALID")
    payload: dict[str, object] = {
        "schema_version": REPAIR_IMPLEMENTATION_SCHEMA,
        "algorithm_version": algorithm_version,
        "implementation_digest": implementation_digest,
        "configuration_digest": configuration_digest,
        "input_contract": "BOUND_CANONICAL_SOURCE_JPEG_ONLY",
        "landmark_recovery": False,
        "network": "FORBIDDEN",
    }
    return {
        **payload,
        "repair_implementation_binding_digest": _digest(REPAIR_IMPLEMENTATION_SCHEMA, payload),
    }


def build_repair_scope() -> dict[str, object]:
    """Build the one-case scope binding; anything else is intentionally absent."""

    payload: dict[str, object] = {
        "schema_version": REPAIR_SCOPE_SCHEMA,
        "target_selector": dict(TARGET_SELECTOR),
        "backend_reexecution_case_ordinals": [TARGET_CASE_ORDINAL],
        "provider_reexecution": False,
        "source_m3_reexecution": False,
        "m4_reexecution_count": 2,
        "result_m3_reexecution_count": 3,
        "manual_review_count": 1,
    }
    return {**payload, "repair_scope_digest": _digest(REPAIR_SCOPE_SCHEMA, payload)}


def compose_targeted_m4_successor(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    predecessor_report: Mapping[str, object],
    predecessor_checkpoint_payload_digest: str,
    predecessor_artifact_decisions: Mapping[str, PrincipalArtifactDecision],
    replacement_case_fields: Mapping[str, object],
    replacement_m4_outputs: Sequence[runtime.M4ExecutionOutput],
    replacement_result_m3_fields: Sequence[Mapping[str, object]],
    replacement_artifact_decision: PrincipalArtifactDecision,
    repair_policy: Mapping[str, object],
    repair_implementation: Mapping[str, object],
) -> TargetedM4RepairSuccessor:
    """Overlay Case 25 while preserving all 47 predecessor evidence slots.

    Inputs are expected to be verified by the targeted executor.  This pure
    composition nevertheless replays every public binding and rejects a
    broadened scope, a malformed target, or any stale/detached predecessor.
    """

    if type(predecessor) is not orchestrator.PreparedRuntimeEvidence:
        _fail("PREDECESSOR_EVIDENCE_INVALID")
    if not _is_digest(predecessor_checkpoint_payload_digest):
        _fail("PREDECESSOR_CHECKPOINT_BINDING_INVALID")
    _validate_predecessor(predecessor, predecessor_report)
    policy = _validate_policy(repair_policy)
    implementation = _validate_implementation(repair_implementation)
    scope = build_repair_scope()
    old_case = _target_case(predecessor.cases)
    _validate_target(old_case)
    new_cases = _compose_cases(
        predecessor=predecessor, replacement_case_fields=replacement_case_fields
    )
    new_case = new_cases[TARGET_CASE_ORDINAL - 1]
    if (
        new_case["case_id"] == old_case["case_id"]
        or new_case["case_specification_digest"] == old_case["case_specification_digest"]
    ):
        _fail("REPLACEMENT_CASE_IDENTITY_UNCHANGED")
    if new_case["geometry_algorithm_version"] != implementation["algorithm_version"]:
        _fail("REPLACEMENT_IMPLEMENTATION_MISMATCH")
    first, second = _validate_replacement_outputs(
        outputs=replacement_m4_outputs, case=new_case, predecessor=predecessor
    )
    m4_fields = _compose_m4_fields(predecessor, new_case, first, second)
    result_fields = _compose_result_m3_fields(
        predecessor=predecessor,
        replacement_fields=replacement_result_m3_fields,
        replacement_case=new_case,
        first_output=first,
    )
    replacement_m4_records = _replacement_m4_records(
        case=new_case,
        fields=m4_fields[(TARGET_CASE_ORDINAL - 1) * 2 : TARGET_CASE_ORDINAL * 2],
    )
    replacement_result_m3_records = _replacement_result_m3_records(
        case=new_case,
        first_m4=replacement_m4_records[0],
        fields=result_fields[(TARGET_CASE_ORDINAL - 1) * 3 : TARGET_CASE_ORDINAL * 3],
    )
    outputs = tuple(
        first if index == TARGET_CASE_ORDINAL - 1 else output
        for index, output in enumerate(predecessor.result_outputs)
    )
    decisions = _compose_decisions(
        predecessor=predecessor,
        predecessor_decisions=predecessor_artifact_decisions,
        replacement_case=new_case,
        replacement_output=first,
        replacement_decision=replacement_artifact_decision,
    )
    authority = dict(predecessor.execution_authority)
    authority["case_manifest_digest"] = legacy._sequence_digest(
        r2.R2_CASE_MANIFEST_SCHEMA, new_cases
    )
    prepared = orchestrator.PreparedRuntimeEvidence(
        formal_bundle=predecessor.formal_bundle,
        source_materials=predecessor.source_materials,
        recipe=predecessor.recipe,
        model_identity=predecessor.model_identity,
        created_at=predecessor.created_at,
        execution_authority=authority,
        cases=tuple(new_cases),
        m4_adapter_fields=tuple(m4_fields),
        result_m3_adapter_fields=tuple(result_fields),
        result_outputs=outputs,
        _factory_token=orchestrator._PREPARED_TOKEN,
    )
    universe = _build_successor_universe(predecessor=predecessor, successor=prepared)
    envelope = _build_envelope(
        predecessor=predecessor,
        predecessor_report=predecessor_report,
        predecessor_checkpoint_payload_digest=predecessor_checkpoint_payload_digest,
        old_case=old_case,
        new_case=new_case,
        policy=policy,
        implementation=implementation,
        scope=scope,
        universe=universe,
        replacement_output=first,
        replacement_m4_records=replacement_m4_records,
        replacement_result_m3_records=replacement_result_m3_records,
    )
    _reject_private_tree(envelope)
    return TargetedM4RepairSuccessor(
        prepared=prepared,
        artifact_decisions=decisions,
        predecessor_report_id=cast(str, predecessor_report["id"]),
        predecessor_case_id=cast(str, old_case["case_id"]),
        successor_case_id=cast(str, new_case["case_id"]),
        repair_policy_digest=cast(str, policy["repair_policy_digest"]),
        repair_implementation_digest=cast(
            str, implementation["repair_implementation_binding_digest"]
        ),
        successor_universe=universe,
        successor_universe_digest=cast(str, universe["successor_universe_digest"]),
        provenance_envelope=envelope,
    )


def build_targeted_replacement_case(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    replacement_case_fields: Mapping[str, object],
) -> Mapping[str, object]:
    """Replay the manifest and return only the authorized successor Case 25.

    This helper is intentionally pure.  It lets the recovery operator bind its
    store/checkpoint to the successor case identity before any M4 execution.
    """

    if type(predecessor) is not orchestrator.PreparedRuntimeEvidence:
        _fail("PREDECESSOR_EVIDENCE_INVALID")
    cases = _compose_cases(
        predecessor=predecessor,
        replacement_case_fields=replacement_case_fields,
    )
    return dict(cases[TARGET_CASE_ORDINAL - 1])


def _validate_predecessor(
    predecessor: orchestrator.PreparedRuntimeEvidence, report: Mapping[str, object]
) -> None:
    if (
        len(predecessor.cases) != 48
        or len(predecessor.m4_adapter_fields) != 96
        or len(predecessor.result_m3_adapter_fields) != 144
        or len(predecessor.result_outputs) != 48
        or len(predecessor.formal_bundle.sources) != 4
    ):
        _fail("PREDECESSOR_CARDINALITY_INVALID")
    try:
        payload = cast(Mapping[str, object], report["report_payload"])
        r2.validate_r2_report_payload(payload)
        if report.get("schema_version") != r2.R2_REPORT_SCHEMA:
            _fail("PREDECESSOR_REPORT_INVALID")
        report_digest = _authority_digest(r2.R2_REPORT_SCHEMA, payload)
        canonical = {key: report[key] for key in r2.R2_REPORT_FIELDS if key != "created_at"}
        if report.get("status") == "FAILED":
            canonical.pop("selected_pair_manifest_digest", None)
        content_digest = _authority_digest(r2.R2_REPORT_SCHEMA, canonical)
        report_id = _authority_digest(
            r2.R2_REPORT_ID_DOMAIN,
            {
                "report_digest": report_digest,
                "source_manifest_digest": report["source_manifest_digest"],
                "case_manifest_digest": report["case_manifest_digest"],
            },
        )[:32]
        if (
            report.get("report_digest") != report_digest
            or report.get("content_digest") != content_digest
            or report.get("id") != report_id
            or report.get("canonical_payload") != canonical
        ):
            _fail("PREDECESSOR_REPORT_INVALID")
    except (KeyError, TypeError, ValueError, r2.D02R2AuthorityError) as error:
        raise D02TargetedM4RepairError("PREDECESSOR_REPORT_INVALID") from error
    if (
        report.get("status") != "FAILED"
        or not isinstance(payload.get("ordered_case_manifest"), list)
        or tuple(cast(Sequence[Mapping[str, object]], payload["ordered_case_manifest"]))
        != predecessor.cases
    ):
        _fail("PREDECESSOR_REPORT_BINDING_INVALID")
    report_m4 = payload.get("m4_repeat_evidence")
    report_result = payload.get("result_m3_repeat_evidence")
    report_source = payload.get("source_m3_repeat_evidence")
    if (
        not isinstance(report_m4, list)
        or not isinstance(report_result, list)
        or not isinstance(report_source, list)
        or len(report_m4) != 96
        or len(report_result) != 144
        or len(report_source) != 12
        or any(
            not isinstance(item, Mapping) for item in (*report_m4, *report_result, *report_source)
        )
    ):
        _fail("PREDECESSOR_REPORT_BINDING_INVALID")


def _validate_policy(value: Mapping[str, object]) -> Mapping[str, object]:
    expected = build_repair_policy(policy_version=cast(str, value.get("policy_version")))
    if dict(value) != expected:
        _fail("REPAIR_POLICY_BINDING_INVALID")
    return expected


def _validate_implementation(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        expected = build_repair_implementation(
            algorithm_version=cast(str, value["algorithm_version"]),
            implementation_digest=cast(str, value["implementation_digest"]),
            configuration_digest=cast(str, value["configuration_digest"]),
        )
    except (KeyError, TypeError, ValueError, D02TargetedM4RepairError) as error:
        raise D02TargetedM4RepairError("REPAIR_IMPLEMENTATION_BINDING_INVALID") from error
    if dict(value) != expected:
        _fail("REPAIR_IMPLEMENTATION_BINDING_INVALID")
    return expected


def _target_case(cases: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
    if len(cases) != 48:
        _fail("PREDECESSOR_CARDINALITY_INVALID")
    return cases[TARGET_CASE_ORDINAL - 1]


def _validate_target(case: Mapping[str, object]) -> None:
    if any(case.get(key) != value for key, value in TARGET_SELECTOR.items()):
        _fail("TARGET_SELECTOR_INVALID")


def _compose_cases(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    replacement_case_fields: Mapping[str, object],
) -> list[dict[str, object]]:
    if set(replacement_case_fields) != set(_CASE_FIELD_KEYS):
        _fail("REPLACEMENT_CASE_FIELDS_INVALID")

    class _OverlayFields:
        def case_fields(self, *, case_ordinal: int, **_: object) -> Mapping[str, object]:
            if not 1 <= case_ordinal <= 48:
                _fail("TARGET_SELECTOR_INVALID")
            if case_ordinal == TARGET_CASE_ORDINAL:
                return dict(replacement_case_fields)
            current = predecessor.cases[case_ordinal - 1]
            return {key: current[key] for key in _CASE_FIELD_KEYS}

    try:
        packets, sources, source_digest = screening._validated_sources(
            predecessor.formal_bundle.runtime_packets
        )
        authority = dict(predecessor.execution_authority)
        authority["source_manifest_digest"] = source_digest
        cases = screening._build_cases(
            _OverlayFields(), packets=packets, sources=sources, execution_authority=authority
        )
    except (KeyError, TypeError, ValueError, screening.ScreeningExecutionError) as error:
        raise D02TargetedM4RepairError("REPLACEMENT_CASE_BUILD_FAILED") from error
    if len(cases) != 48 or any(
        cases[index] != predecessor.cases[index]
        for index in range(48)
        if index != TARGET_CASE_ORDINAL - 1
    ):
        _fail("PREDECESSOR_CASE_REUSE_INVALID")
    _validate_target(cases[TARGET_CASE_ORDINAL - 1])
    return [dict(item) for item in cases]


def _validate_replacement_outputs(
    *,
    outputs: Sequence[runtime.M4ExecutionOutput],
    case: Mapping[str, object],
    predecessor: orchestrator.PreparedRuntimeEvidence,
) -> tuple[runtime.M4ExecutionOutput, runtime.M4ExecutionOutput]:
    if len(outputs) != 2 or any(type(item) is not runtime.M4ExecutionOutput for item in outputs):
        _fail("REPLACEMENT_M4_CARDINALITY_INVALID")
    first, second = outputs
    source = predecessor.source_materials[TARGET_SOURCE_ORDINAL - 1]
    expected_width = cast(int, case["output_width"])
    expected_height = cast(int, case["output_height"])
    if (
        first.case_id != case["case_id"]
        or second.case_id != case["case_id"]
        or first.replay_index != 1
        or second.replay_index != 2
        or first.result_width != expected_width
        or second.result_width != expected_width
        or first.result_height != expected_height
        or second.result_height != expected_height
        or first.result_sha256 != second.result_sha256
        or first.content != second.content
        or first.changed_pixel_count != second.changed_pixel_count
        or source.descriptor.content_sha256 != case["source_asset_sha256"]
    ):
        _fail("REPLACEMENT_M4_BINDING_INVALID")
    return first, second


def _compose_m4_fields(
    predecessor: orchestrator.PreparedRuntimeEvidence,
    case: Mapping[str, object],
    first: runtime.M4ExecutionOutput,
    second: runtime.M4ExecutionOutput,
) -> list[dict[str, object]]:
    start = (TARGET_CASE_ORDINAL - 1) * 2
    source_output_id = predecessor.source_materials[
        TARGET_SOURCE_ORDINAL - 1
    ].descriptor.source_output_id
    replacement = [
        {
            "case_id": first.case_id,
            "replay_index": 1,
            **first.screening_fields(source_output_id=source_output_id),
        },
        {
            "case_id": second.case_id,
            "replay_index": 2,
            **second.screening_fields(source_output_id=source_output_id),
        },
    ]
    original = predecessor.m4_adapter_fields
    if set(replacement[0]) != set(original[start]) or set(replacement[1]) != set(
        original[start + 1]
    ):
        _fail("REPLACEMENT_M4_FIELDS_INVALID")
    return [
        dict(replacement[index - start]) if start <= index < start + 2 else dict(item)
        for index, item in enumerate(original)
    ]


def _compose_result_m3_fields(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    replacement_fields: Sequence[Mapping[str, object]],
    replacement_case: Mapping[str, object],
    first_output: runtime.M4ExecutionOutput,
) -> list[dict[str, object]]:
    start = (TARGET_CASE_ORDINAL - 1) * 3
    if len(replacement_fields) != 3:
        _fail("REPLACEMENT_RESULT_M3_CARDINALITY_INVALID")
    original = predecessor.result_m3_adapter_fields
    expected_keys = set(original[start])
    result: list[dict[str, object]] = []
    for fields in replacement_fields:
        copied = dict(fields)
        if (
            set(copied) != expected_keys
            or "repeat_index" in copied
            or copied.get("canonical_output_digest") != first_output.result_sha256
            or copied.get("runtime_manifest_digest") == ""
        ):
            _fail("REPLACEMENT_RESULT_M3_BINDING_INVALID")
        _reject_private_tree(copied)
        result.append(copied)
    return [
        result[index - start] if start <= index < start + 3 else dict(item)
        for index, item in enumerate(original)
    ]


def _compose_decisions(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    predecessor_decisions: Mapping[str, PrincipalArtifactDecision],
    replacement_case: Mapping[str, object],
    replacement_output: runtime.M4ExecutionOutput,
    replacement_decision: PrincipalArtifactDecision,
) -> dict[str, PrincipalArtifactDecision]:
    subjects = {subject.case_id: subject for subject in predecessor.review_subjects}
    if set(predecessor_decisions) != set(subjects):
        _fail("PREDECESSOR_DECISION_CARDINALITY_INVALID")
    for case_id, subject in subjects.items():
        decision = predecessor_decisions[case_id]
        if (
            type(decision) is not PrincipalArtifactDecision
            or decision.case_id != case_id
            or decision.result_sha256 != subject.result_sha256
        ):
            _fail("PREDECESSOR_DECISION_BINDING_INVALID")
    if (
        type(replacement_decision) is not PrincipalArtifactDecision
        or replacement_decision.case_id != replacement_case["case_id"]
        or replacement_decision.result_sha256 != replacement_output.result_sha256
    ):
        _fail("REPLACEMENT_DECISION_BINDING_INVALID")
    old_id = predecessor.result_outputs[TARGET_CASE_ORDINAL - 1].case_id
    return {
        (replacement_case["case_id"] if case_id == old_id else case_id): (
            replacement_decision if case_id == old_id else decision
        )
        for case_id, decision in predecessor_decisions.items()
    }


def _replacement_m4_records(
    *, case: Mapping[str, object], fields: Sequence[Mapping[str, object]]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    if len(fields) != 2:
        _fail("REPLACEMENT_M4_CARDINALITY_INVALID")
    records: list[Mapping[str, object]] = []
    for replay_index, raw in enumerate(fields, start=1):
        materialized = dict(raw)
        materialized.update(
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
        try:
            records.append(r2.build_r2_m4_execution_record(materialized))
        except (KeyError, TypeError, ValueError, r2.D02R2AuthorityError) as error:
            raise D02TargetedM4RepairError("REPLACEMENT_M4_RECORD_INVALID") from error
    if any(
        records[0][key] != records[1][key]
        for key in (
            "result_output_id",
            "result_sha256",
            "result_byte_size",
            "result_mime_type",
            "result_width",
            "result_height",
            "changed_pixel_count",
        )
    ):
        _fail("REPLACEMENT_M4_DETERMINISM_INVALID")
    return (records[0], records[1])


def _replacement_result_m3_records(
    *,
    case: Mapping[str, object],
    first_m4: Mapping[str, object],
    fields: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    if len(fields) != 3:
        _fail("REPLACEMENT_RESULT_M3_CARDINALITY_INVALID")
    records: list[Mapping[str, object]] = []
    for repeat_index, raw in enumerate(fields, start=1):
        materialized = dict(raw)
        materialized.update(
            {
                "case_id": case["case_id"],
                "case_specification_digest": case["case_specification_digest"],
                "result_output_id": first_m4["result_output_id"],
                "result_sha256": first_m4["result_sha256"],
                "repeat_index": repeat_index,
                "runtime_manifest_digest": case["runtime_manifest_digest"],
            }
        )
        try:
            records.append(r2.build_r2_result_m3_record(materialized))
        except (KeyError, TypeError, ValueError, r2.D02R2AuthorityError) as error:
            raise D02TargetedM4RepairError("REPLACEMENT_RESULT_M3_RECORD_INVALID") from error
    return (records[0], records[1], records[2])


def _build_successor_universe(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    successor: orchestrator.PreparedRuntimeEvidence,
) -> dict[str, object]:
    if len(successor.cases) != 48 or len(successor.result_outputs) != 48:
        _fail("SUCCESSOR_CARDINALITY_INVALID")
    slot_digests = [
        _slot_digest(case=case, output=output)
        for case, output in zip(successor.cases, successor.result_outputs, strict=True)
    ]
    predecessor_slots = [
        _slot_digest(case=case, output=output)
        for case, output in zip(predecessor.cases, predecessor.result_outputs, strict=True)
    ]
    if any(
        slot_digests[index] != predecessor_slots[index]
        for index in range(48)
        if index != TARGET_CASE_ORDINAL - 1
    ):
        _fail("SUCCESSOR_REUSED_SLOT_INVALID")
    payload: dict[str, object] = {
        "schema_version": SUCCESSOR_UNIVERSE_SCHEMA,
        "case_count": 48,
        "case_manifest_digest": successor.execution_authority["case_manifest_digest"],
        "ordered_case_specification_digests": [
            case["case_specification_digest"] for case in successor.cases
        ],
        "ordered_slot_digests": slot_digests,
        "reused_predecessor_slot_count": 47,
        "replacement_case_ordinal": TARGET_CASE_ORDINAL,
        "replacement_slot_digest": slot_digests[TARGET_CASE_ORDINAL - 1],
    }
    return {**payload, "successor_universe_digest": _digest(SUCCESSOR_UNIVERSE_SCHEMA, payload)}


def _build_envelope(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    predecessor_report: Mapping[str, object],
    predecessor_checkpoint_payload_digest: str,
    old_case: Mapping[str, object],
    new_case: Mapping[str, object],
    policy: Mapping[str, object],
    implementation: Mapping[str, object],
    scope: Mapping[str, object],
    universe: Mapping[str, object],
    replacement_output: runtime.M4ExecutionOutput,
    replacement_m4_records: Sequence[Mapping[str, object]],
    replacement_result_m3_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    payload = cast(Mapping[str, object], predecessor_report["report_payload"])
    source_records = cast(Sequence[Mapping[str, object]], payload["source_m3_repeat_evidence"])
    predecessor_slots = [
        _slot_digest(case=case, output=output)
        for case, output in zip(predecessor.cases, predecessor.result_outputs, strict=True)
    ]
    successor_slot = _slot_digest(case=new_case, output=replacement_output)
    envelope: dict[str, object] = {
        "schema_version": SUCCESSOR_ENVELOPE_SCHEMA,
        "predecessor_report_id": predecessor_report["id"],
        "predecessor_report_digest": predecessor_report["report_digest"],
        "predecessor_report_content_digest": predecessor_report["content_digest"],
        "predecessor_status": "FAILED",
        "predecessor_checkpoint_payload_digest": predecessor_checkpoint_payload_digest,
        "repair_policy_digest": policy["repair_policy_digest"],
        "repair_implementation_digest": implementation["repair_implementation_binding_digest"],
        "repair_scope_digest": scope["repair_scope_digest"],
        "backend_reexecution_case_ordinals": [TARGET_CASE_ORDINAL],
        "provider_reexecution": False,
        "predecessor_case_id": old_case["case_id"],
        "predecessor_case_specification_digest": old_case["case_specification_digest"],
        "successor_case_id": new_case["case_id"],
        "successor_case_specification_digest": new_case["case_specification_digest"],
        "replacement_result_output_digest": replacement_output.output_digest,
        "replacement_result_sha256": replacement_output.result_sha256,
        "successor_m4_record_digests": [
            record["record_digest"] for record in replacement_m4_records
        ],
        "successor_result_m3_record_digests": [
            record["record_digest"] for record in replacement_result_m3_records
        ],
        "ordered_predecessor_reused_slot_digests": [
            value
            for index, value in enumerate(predecessor_slots, start=1)
            if index != TARGET_CASE_ORDINAL
        ],
        "replacement_slot_digest": successor_slot,
        "predecessor_source_m3_record_digests": [
            record["record_digest"] for record in source_records
        ],
        "source_m3_reexecution_count": 0,
        "m4_reexecution_count": 2,
        "result_m3_reexecution_count": 3,
        "manual_review_count": 1,
        "successor_universe_digest": universe["successor_universe_digest"],
    }
    return {**envelope, "provenance_envelope_digest": _digest(SUCCESSOR_ENVELOPE_SCHEMA, envelope)}


def _slot_digest(*, case: Mapping[str, object], output: runtime.M4ExecutionOutput) -> str:
    return _digest(
        SUCCESSOR_SLOT_SCHEMA,
        {
            "case_ordinal": case["case_ordinal"],
            "case_id": case["case_id"],
            "case_specification_digest": case["case_specification_digest"],
            "result_output_digest": output.output_digest,
            "result_sha256": output.result_sha256,
            "result_byte_size": output.result_byte_size,
        },
    )


def _digest(schema: str, payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _authority_digest(schema: str, payload: Mapping[str, object]) -> str:
    return mirror_demo_digest(schema, cast(dict[str, JsonValue], dict(payload)))


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _reject_private_tree(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in _PRIVATE_KEYS:
                _fail("PRIVATE_FIELD_FORBIDDEN")
            _reject_private_tree(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_tree(item)
    elif isinstance(value, bytes):
        _fail("PRIVATE_FIELD_FORBIDDEN")
    elif isinstance(value, str) and ("\\" in value or ":\\" in value or value.startswith("file:")):
        _fail("PRIVATE_FIELD_FORBIDDEN")


def _fail(code: str) -> NoReturn:
    raise D02TargetedM4RepairError(code)
