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
    fields["warp_plan_digest"] = "c" * 64
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
    output_digest = runtime._canonical_digest(runtime.M4_EXECUTION_OUTPUT_SCHEMA, payload)
    first = replace(old, case_id=cast(str, new_case["case_id"]), output_digest=output_digest)
    payload["replay_index"] = 2
    second = replace(
        old,
        case_id=cast(str, new_case["case_id"]),
        replay_index=2,
        output_digest=runtime._canonical_digest(runtime.M4_EXECUTION_OUTPUT_SCHEMA, payload),
    )
    adapters = _Adapters(deepcopy(report_fields))
    m4_record = {"result_output_id": first.result_output_id, "result_sha256": first.result_sha256}
    result_fields = tuple(
        {
            **adapters.inspect_result(case_entry=new_case, m4_record=m4_record, repeat_index=index),
            "canonical_output_digest": first.result_sha256,
        }
        for index in (1, 2, 3)
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
    prepared, _, report_fields = _prepared_runtime()
    fields, outputs, result_m3, decision = _replacement(prepared, report_fields)
    return repair.compose_targeted_m4_successor(
        predecessor=prepared,
        predecessor_report=_failed_predecessor_report(),
        predecessor_checkpoint_payload_digest="a" * 64,
        predecessor_artifact_decisions=_decisions(prepared),
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


@pytest.mark.parametrize(
    "tamper",
    ["scope", "case_fields", "m4_cardinality", "result_fields", "decision", "report_status"],
)
def test_rejects_tampered_or_out_of_scope_replacement(tamper: str) -> None:
    prepared, _, report_fields = _prepared_runtime()
    fields, outputs, result_m3, decision = _replacement(prepared, report_fields)
    policy = repair.build_repair_policy()
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
                implementation_digest="b" * 64,
                configuration_digest="d" * 64,
            ),
        )


def test_envelope_is_public_and_never_contains_result_bytes_or_paths() -> None:
    successor = _compose()
    rendered = repr(successor) + repr(successor.provenance_envelope)
    assert "content=" not in rendered
    assert "path" not in rendered.lower()
    assert "\\" not in rendered
