from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import cast

import pytest
from test_demo_d02_final_orchestrator import _prepared_runtime
from test_demo_d02_generic_runtime_admission import _runtime_result
from test_demo_d02_r2_screening_execution import _Adapters, _request

from mirror_api import demo_d02_final_orchestrator as orchestrator
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_r2_screening_execution as screening
from mirror_api import demo_d02_targeted_m4_repair as repair
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision


def _failed_predecessor_report() -> dict[str, object]:
    original, _, _ = _runtime_result()
    fields = {
        "created_at": original.report_row["created_at"],
        "report_payload": original.report_row["report_payload"],
    }
    packets = list(original.source_packets)
    adapters = _Adapters(deepcopy(fields))
    adapters.failing_manual = True
    return screening.run_offline_screening(_request(adapters, fields, packets))


def _decisions(prepared: object) -> dict[str, PrincipalArtifactDecision]:
    runtime_evidence = cast("orchestrator.PreparedRuntimeEvidence", prepared)
    return {
        subject.case_id: PrincipalArtifactDecision.seal(
            case_id=subject.case_id,
            result_sha256=subject.result_sha256,
            decision_sequence=subject.decision_sequence,
            manual_review_version="test-review-v1",
            manual_review_policy_digest=cast(
                str, runtime_evidence.execution_authority["manual_review_policy_digest"]
            ),
            background_seam=False,
            disconnected_contour=False,
            duplicated_feature=False,
            warp_tear=False,
        )
        for subject in runtime_evidence.review_subjects
    }


def _ordered_prepared_runtime() -> tuple[
    orchestrator.PreparedRuntimeEvidence,
    dict[str, object],
]:
    prepared, _, report_fields = _prepared_runtime()
    output_by_case_id = {item.case_id: item for item in prepared.result_outputs}
    ordered = tuple(output_by_case_id[cast(str, case["case_id"])] for case in prepared.cases)
    return (
        orchestrator.PreparedRuntimeEvidence(
            formal_bundle=prepared.formal_bundle,
            source_materials=prepared.source_materials,
            recipe=prepared.recipe,
            model_identity=prepared.model_identity,
            created_at=prepared.created_at,
            execution_authority=prepared.execution_authority,
            cases=prepared.cases,
            m4_adapter_fields=prepared.m4_adapter_fields,
            result_m3_adapter_fields=prepared.result_m3_adapter_fields,
            result_outputs=ordered,
            _factory_token=orchestrator._PREPARED_TOKEN,
        ),
        report_fields,
    )


def _replacement(
    prepared: object, report_fields: dict[str, object]
) -> tuple[
    dict[str, object],
    tuple[runtime.M4ExecutionOutput, runtime.M4ExecutionOutput],
    tuple[dict[str, object], dict[str, object], dict[str, object]],
    PrincipalArtifactDecision,
]:
    evidence = cast("orchestrator.PreparedRuntimeEvidence", prepared)
    old_case = evidence.cases[24]
    fields = {
        key: old_case[key]
        for key in (
            "geometry_ontology_version_digest",
            "warp_plan_digest",
            "geometry_algorithm_version",
            "runtime_config_digest",
            "output_policy_version",
            "output_width",
            "output_height",
            "determinism_level",
        )
    }
    fields["geometry_algorithm_version"] = "d02-targeted-jaw-repair-v1"
    fields["geometry_ontology_version_digest"] = "b" * 64
    fields["runtime_config_digest"] = "d" * 64
    descriptor = evidence.source_materials[2].descriptor
    fields["warp_plan_digest"] = repair.build_repair_warp_plan_digest(
        algorithm_version="d02-targeted-jaw-repair-v1",
        implementation_digest="b" * 64,
        repair_policy_digest=cast(str, repair.build_repair_policy()["repair_policy_digest"]),
        configuration_digest="d" * 64,
        source_descriptor_digest=descriptor.descriptor_digest,
        source_content_sha256=descriptor.content_sha256,
    )
    packets, sources, source_digest = screening._validated_sources(
        evidence.formal_bundle.runtime_packets
    )
    authority = dict(evidence.execution_authority)
    authority["source_manifest_digest"] = source_digest

    class _TargetFields:
        def case_fields(self, *, case_ordinal: int, **_: object) -> dict[str, object]:
            source = evidence.cases[case_ordinal - 1]
            if case_ordinal == 25:
                return dict(fields)
            return {
                key: source[key]
                for key in (
                    "geometry_ontology_version_digest",
                    "warp_plan_digest",
                    "geometry_algorithm_version",
                    "runtime_config_digest",
                    "output_policy_version",
                    "output_width",
                    "output_height",
                    "determinism_level",
                )
            }

    new_case = screening._build_cases(
        _TargetFields(), packets=packets, sources=sources, execution_authority=authority
    )[24]
    old = evidence.result_outputs[24]
    payload = old.payload()
    payload["case_id"] = new_case["case_id"]
    payload["result_output_id"] = f"m4-{new_case['case_id']}"
    output_digest = runtime._canonical_digest(runtime.M4_EXECUTION_OUTPUT_SCHEMA, payload)
    first = replace(
        old,
        case_id=cast(str, new_case["case_id"]),
        result_output_id=cast(str, payload["result_output_id"]),
        output_digest=output_digest,
    )
    payload["replay_index"] = 2
    second = replace(
        old,
        case_id=cast(str, new_case["case_id"]),
        result_output_id=first.result_output_id,
        replay_index=2,
        output_digest=runtime._canonical_digest(runtime.M4_EXECUTION_OUTPUT_SCHEMA, payload),
    )
    adapters = _Adapters(deepcopy(report_fields))
    m4_record = {"result_output_id": first.result_output_id, "result_sha256": first.result_sha256}
    result_values: list[dict[str, object]] = []
    for index in (1, 2, 3):
        value = dict(
            adapters.inspect_result(
                case_entry=new_case,
                m4_record=m4_record,
                repeat_index=index,
            )
        )
        observation = deepcopy(cast(dict[str, object], value["measurement_observation"]))
        observation["canonical_output_digest"] = first.result_sha256
        observation["measurement_observation_digest"] = measurement.mirror_demo_digest(
            measurement.MEASUREMENT_OBSERVATION_SCHEMA,
            cast(
                dict[str, measurement.JsonValue],
                {
                    key: item
                    for key, item in observation.items()
                    if key not in {"schema_version", "measurement_observation_digest"}
                },
            ),
        )
        value["canonical_output_digest"] = first.result_sha256
        value["measurement_observation"] = observation
        value["measurement_observation_digest"] = observation["measurement_observation_digest"]
        result_values.append(value)
    result_fields = cast(
        tuple[dict[str, object], dict[str, object], dict[str, object]],
        tuple(result_values),
    )
    decision = PrincipalArtifactDecision.seal(
        case_id=cast(str, new_case["case_id"]),
        result_sha256=first.result_sha256,
        decision_sequence=25,
        manual_review_version="test-review-v1",
        manual_review_policy_digest=cast(
            str, evidence.execution_authority["manual_review_policy_digest"]
        ),
        background_seam=False,
        disconnected_contour=False,
        duplicated_feature=False,
        warp_tear=False,
    )
    return fields, (first, second), result_fields, decision


def _compose() -> repair.TargetedM4RepairSuccessor:
    prepared, report_fields = _ordered_prepared_runtime()
    fields, outputs, result_m3, decision = _replacement(prepared, report_fields)
    predecessor_decisions = _decisions(prepared)
    failed_case_05 = prepared.review_subjects[4]
    predecessor_decisions[failed_case_05.case_id] = PrincipalArtifactDecision.seal(
        case_id=failed_case_05.case_id,
        result_sha256=failed_case_05.result_sha256,
        decision_sequence=failed_case_05.decision_sequence,
        manual_review_version="test-review-v1",
        manual_review_policy_digest=cast(
            str, prepared.execution_authority["manual_review_policy_digest"]
        ),
        background_seam=True,
        disconnected_contour=False,
        duplicated_feature=False,
        warp_tear=False,
    )
    return repair.compose_targeted_m4_successor(
        predecessor=prepared,
        predecessor_report=_failed_predecessor_report(),
        predecessor_checkpoint_payload_digest="a" * 64,
        predecessor_artifact_decisions=predecessor_decisions,
        replacement_case_fields=fields,
        replacement_m4_outputs=outputs,
        replacement_result_m3_fields=result_m3,
        replacement_artifact_decision=decision,
        repair_policy=repair.build_repair_policy(),
        repair_implementation=repair.build_repair_implementation(
            algorithm_version="d02-targeted-jaw-repair-v1",
            implementation_digest="b" * 64,
            configuration_digest="d" * 64,
        ),
    )


def test_composes_only_case_25_and_binds_complete_successor_universe() -> None:
    successor = _compose()

    assert len(successor.prepared.cases) == 48
    assert len(successor.prepared.m4_adapter_fields) == 96
    assert len(successor.prepared.result_m3_adapter_fields) == 144
    assert len(successor.prepared.result_outputs) == 48
    assert successor.reexecution_counts == {
        "provider": 0,
        "source_m3": 0,
        "m4": 2,
        "result_m3": 3,
        "manual_review": 1,
    }
    assert len(successor.provenance_envelope["ordered_predecessor_reused_slot_digests"]) == 47
    assert len(successor.provenance_envelope["predecessor_source_m3_record_digests"]) == 12
    assert len(successor.provenance_envelope["successor_m4_record_digests"]) == 2
    assert len(successor.provenance_envelope["successor_result_m3_record_digests"]) == 3
    assert successor.provenance_envelope["backend_reexecution_case_ordinals"] == [25]
    assert successor.prepared.cases[24]["case_id"] == successor.successor_case_id
    assert (
        successor.successor_universe["successor_universe_digest"]
        == successor.successor_universe_digest
    )
    assert successor.predecessor_case_id != successor.successor_case_id
    assert set(successor.artifact_decisions) == {
        item.case_id for item in successor.prepared.review_subjects
    }


def test_successor_finalization_recomputes_monotonicity_and_selects_16_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    successor = _compose()
    _, report_fields = _ordered_prepared_runtime()
    monkeypatch.setattr(
        orchestrator,
        "PHashAdapter",
        lambda _: _Adapters(deepcopy(report_fields)),
    )

    result = orchestrator.finalize_runtime_evidence(
        prepared=successor.prepared,
        artifact_decisions=successor.artifact_decisions,
    )

    assert result.admission_ready
    assert result.report_row["status"] == "PASSED"
    assert result.report_row["selected_dimension_keys"] == ["jaw_width", "eye_spacing"]
    assert result.report_row["selected_pair_count"] == 16
    assert result.report_row["selected_result_side_count"] == 32
    payload = cast(dict[str, object], result.report_row["report_payload"])
    cases = cast(list[dict[str, object]], payload["ordered_case_manifest"])
    gates = cast(list[dict[str, object]], payload["measurement_gate_evidence"])
    assert gates[24]["monotonicity_peer_case_id"] == cases[25]["case_id"]
    assert (
        cast(dict[str, object], gates[24]["gate_evaluation"])["magnitude_monotonicity_gate_passed"]
        is True
    )
    selected = cast(list[dict[str, object]], payload["selected_pair_manifest"])
    assert len(selected) == 16
    assert (
        len(
            {
                cast(str, entry[key])
                for entry in selected
                for key in ("left_case_id", "right_case_id")
            }
        )
        == 32
    )


@pytest.mark.parametrize(
    "tamper",
    [
        "scope",
        "case_fields",
        "m4_cardinality",
        "result_fields",
        "decision",
        "report_status",
        "implementation_link",
        "config_link",
        "policy_warp_link",
    ],
)
def test_rejects_tampered_or_out_of_scope_replacement(tamper: str) -> None:
    prepared, report_fields = _ordered_prepared_runtime()
    fields, outputs, result_m3, decision = _replacement(prepared, report_fields)
    policy = repair.build_repair_policy()
    implementation_digest = "b" * 64
    configuration_digest = "d" * 64
    if tamper == "scope":
        policy["m4_reexecution_count"] = 4
    elif tamper == "case_fields":
        fields["output_width"] = 0
    elif tamper == "m4_cardinality":
        outputs = outputs[:1]
    elif tamper == "result_fields":
        result_m3[0]["canonical_output_digest"] = "f" * 64
    elif tamper == "decision":
        decision = PrincipalArtifactDecision.seal(
            case_id="0" * 32,
            result_sha256=decision.result_sha256,
            decision_sequence=decision.decision_sequence,
            manual_review_version=decision.manual_review_version,
            manual_review_policy_digest=decision.manual_review_policy_digest,
            background_seam=decision.background_seam,
            disconnected_contour=decision.disconnected_contour,
            duplicated_feature=decision.duplicated_feature,
            warp_tear=decision.warp_tear,
        )
    elif tamper == "implementation_link":
        implementation_digest = "e" * 64
    elif tamper == "config_link":
        configuration_digest = "e" * 64
    elif tamper == "policy_warp_link":
        policy = repair.build_repair_policy(policy_version="D02_TARGETED_JAW_REPAIR_V2")
    report = (
        _runtime_result()[0].report_row
        if tamper == "report_status"
        else _failed_predecessor_report()
    )

    with pytest.raises(repair.D02TargetedM4RepairError):
        repair.compose_targeted_m4_successor(
            predecessor=prepared,
            predecessor_report=report,
            predecessor_checkpoint_payload_digest="a" * 64,
            predecessor_artifact_decisions=_decisions(prepared),
            replacement_case_fields=fields,
            replacement_m4_outputs=outputs,
            replacement_result_m3_fields=result_m3,
            replacement_artifact_decision=decision,
            repair_policy=policy,
            repair_implementation=repair.build_repair_implementation(
                algorithm_version="d02-targeted-jaw-repair-v1",
                implementation_digest=implementation_digest,
                configuration_digest=configuration_digest,
            ),
        )


def test_envelope_is_public_and_never_contains_result_bytes_or_paths() -> None:
    successor = _compose()
    rendered = repr(successor) + repr(successor.provenance_envelope)
    assert "content=" not in rendered
    assert "path" not in rendered.lower()
    assert "\\" not in rendered
