from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import pytest
from test_demo_d02_r2_runtime_forward import _executor, _observation_digest
from test_demo_d02_r2_runtime_forward import runtime_inputs as _runtime_inputs_source

from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d08_geometry_adapter import (
    D02FixedGeometryCase,
    GeometryAttemptExecutionEvidence,
    GeometryDirection,
    GeometryExecutionAuthority,
    GeometryJobAttemptBinding,
    GeometryStableMaterializationCore,
)
from mirror_api.demo_d08_geometry_verifier import (
    D08_GEOMETRY_METRICS_SCHEMA,
    D08_GEOMETRY_THRESHOLDS_SCHEMA,
    IndependentGeometryVerifier,
    _signed_ppm,
)
from mirror_api.demo_editing_service import ExecutionCommand, MaterializedObject
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
)


def _operation() -> OperationSpec:
    return OperationSpec(
        engine=OperationEngine.GEOMETRY,
        operation_type=OperationType.GEOMETRY,
        parameters={"dimension_key": "jaw_width", "delta_ppm": 15_000},
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME, PreserveKey.NON_TARGET_GEOMETRY),
        expected_effect={
            "effect_type": "GEOMETRY",
            "target_region": "FACE_REGION",
            "dimension_key": "jaw_width",
            "delta_ppm": 15_000,
        },
    )


@pytest.fixture
def verifier_runtime_inputs() -> object:
    return _runtime_inputs_source.__wrapped__()


def _authority(descriptor: object, executor: object) -> GeometryExecutionAuthority:
    source = descriptor
    runtime_executor = executor
    case = D02FixedGeometryCase(
        case_id="1" * 32,
        case_record_digest="2" * 64,
        case_specification_digest="3" * 64,
        case_binding_digest="0" * 64,
        case_ordinal=1,
        source_ordinal=source.ordinal,
        source_asset_id=source.source_id,
        source_asset_sha256=source.content_sha256,
        dimension_key="jaw_width",
        direction=GeometryDirection.INCREASE,
        magnitude_ppm=15_000,
        warp_plan_digest="4" * 64,
        geometry_ontology_digest="5" * 64,
        source_landmark_digest="6" * 64,
        output_policy_version="output-policy-v1",
        determinism_version="determinism-v1",
        backend_candidate_id="geometry-candidate-v1",
        backend_algorithm_version=runtime_executor.recipe.m4_algorithm_version,
        backend_runtime_manifest_digest=runtime_executor.recipe.runtime_manifest_digest,
        backend_configuration_digest="7" * 64,
        output_width=source.width,
        output_height=source.height,
    )
    return GeometryExecutionAuthority(
        editing_session_id="8" * 32,
        editing_session_digest="9" * 64,
        plan_id="a" * 32,
        plan_digest="b" * 64,
        operation_id="c" * 32,
        operation_authority_digest="d" * 64,
        operation_spec_digest="e" * 64,
        input_image_version_id="f" * 32,
        input_image_version_digest="0" * 64,
        input_sequence=0,
        input_asset_id="1" * 32,
        input_asset_sha256=source.content_sha256,
        root_source_asset_id=source.source_id,
        root_source_asset_sha256=source.content_sha256,
        d02_admission_id="2" * 32,
        d02_admission_digest="3" * 64,
        d02_screening_report_id="4" * 32,
        d02_screening_report_digest="5" * 64,
        fixed_case=case,
        authority_digest="0" * 64,
    )


def _command_and_materialized(
    inputs: object,
) -> tuple[ExecutionCommand, MaterializedObject, object]:
    fixture = _executor(inputs)
    source = inputs.materials[0]
    authority = _authority(source.descriptor, fixture.executor)
    output = fixture.executor.transform(
        material=source,
        case_entry={
            "case_id": authority.fixed_case.case_id,
            "case_specification_digest": authority.fixed_case.case_specification_digest,
            "source_asset_id": source.descriptor.source_id,
            "source_asset_sha256": source.descriptor.content_sha256,
            "source_ordinal": source.descriptor.ordinal,
            "runtime_manifest_digest": fixture.executor.recipe.runtime_manifest_digest,
            "geometry_algorithm_version": fixture.executor.recipe.m4_algorithm_version,
            "output_width": source.descriptor.width,
            "output_height": source.descriptor.height,
        },
        replay_index=1,
    )
    operation = _operation()
    binding = GeometryJobAttemptBinding("6" * 32, "7" * 32, "8" * 64, "9" * 32, "a" * 64)
    core = GeometryStableMaterializationCore(
        operation_id=authority.operation_id,
        operation_authority_digest=authority.operation_authority_digest,
        operation_spec_digest=authority.operation_spec_digest,
        authority_digest=authority.authority_digest,
        case_id=authority.fixed_case.case_id,
        case_record_digest=authority.fixed_case.case_record_digest,
        case_specification_digest=authority.fixed_case.case_specification_digest,
        case_binding_digest=authority.fixed_case.case_binding_digest,
        backend_candidate_id=authority.fixed_case.backend_candidate_id,
        backend_algorithm_version=authority.fixed_case.backend_algorithm_version,
        backend_runtime_manifest_digest=authority.fixed_case.backend_runtime_manifest_digest,
        backend_configuration_digest=authority.fixed_case.backend_configuration_digest,
        warp_plan_digest=authority.fixed_case.warp_plan_digest,
        input_image_version_id=authority.input_image_version_id,
        input_image_version_digest=authority.input_image_version_digest,
        input_asset_id=authority.input_asset_id,
        input_asset_sha256=authority.input_asset_sha256,
        root_source_asset_id=authority.root_source_asset_id,
        root_source_asset_sha256=authority.root_source_asset_sha256,
        result_sha256=output.result_sha256,
        result_byte_size=output.result_byte_size,
        result_media_type=output.result_mime_type,
        result_width=output.result_width,
        result_height=output.result_height,
        changed_pixel_count=output.changed_pixel_count,
        engine_digest="b" * 64,
        config_digest="c" * 64,
        stable_core_digest="0" * 64,
    )
    evidence = GeometryAttemptExecutionEvidence(
        binding,
        authority.operation_id,
        authority.operation_authority_digest,
        authority.operation_spec_digest,
        authority.authority_digest,
        core.stable_core_digest,
        output.execution_receipt_digest,
        "0" * 64,
    )
    command = ExecutionCommand(
        actor_id="d" * 32,
        session_id="e" * 32,
        operation_id=authority.operation_id,
        operation_digest=authority.operation_authority_digest,
        execution_job_binding_id=binding.execution_job_binding_id,
        formal_job_attempt_id=binding.attempt_id,
        source_asset_id=authority.root_source_asset_id,
        source_asset_sha256=authority.root_source_asset_sha256,
        source_bytes=source.content,
        operation=operation,
        engine_version="geometry-engine-v1",
        engine_digest=core.engine_digest,
        config_digest=core.config_digest,
        geometry_authority=authority,
        geometry_job_attempt=binding,
    )
    return (
        command,
        MaterializedObject(
            content=output.content,
            sha256=output.result_sha256,
            width=output.result_width,
            height=output.result_height,
            mime_type=output.result_mime_type,
            engine_digest=core.engine_digest,
            config_digest=core.config_digest,
            geometry_stable_core=core,
            geometry_attempt_evidence=evidence,
        ),
        fixture,
    )


def _force_directional_result_m3(fixture: object, monkeypatch: pytest.MonkeyPatch) -> None:
    original = fixture.m3.inspect_result

    def directional(**kwargs: object) -> runtime.BackendM3Result:
        backend_result = original(**kwargs)
        fields = deepcopy(dict(backend_result.fields))
        observation = fields["measurement_observation"]
        entries = observation["ordered_measurements"]
        jaw = entries[3]
        jaw["raw_value_fixed18"] = measurement.fixed18(
            Decimal(str(jaw["raw_value_fixed18"])) * Decimal("1.07")
        )
        observation["measurement_observation_digest"] = _observation_digest(observation)
        fields["measurement_observation_digest"] = observation["measurement_observation_digest"]
        return runtime.BackendM3Result(payload_schema=backend_result.payload_schema, fields=fields)

    monkeypatch.setattr(fixture.m3, "inspect_result", directional)


@pytest.mark.asyncio
async def test_fresh_verifier_records_three_independent_source_and_result_observations(
    verifier_runtime_inputs: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command, materialized, fixture = _command_and_materialized(verifier_runtime_inputs)
    _force_directional_result_m3(fixture, monkeypatch)

    result = await IndependentGeometryVerifier(fixture.executor)(command, materialized)

    assert fixture.m3.source_calls == 3
    assert fixture.m3.result_calls == 3
    assert result.publishable is True, [
        item["signed_target_delta_ppm"] for item in result.authority_metrics["repeats"]
    ]
    assert result.authority_metrics is not None
    assert result.authority_thresholds is not None
    assert result.authority_metrics["schema_version"] == D08_GEOMETRY_METRICS_SCHEMA
    assert result.authority_thresholds["schema_version"] == D08_GEOMETRY_THRESHOLDS_SCHEMA
    assert result.authority_thresholds["repeat_count"] == 3
    assert len(result.authority_metrics["repeats"]) == 3
    target_category = result.categories[2].canonical_payload()
    assert target_category["evidence"]["requested_delta_ppm"] == 15_000


def test_fixed18_delta_uses_frozen_absolute_normalized_ppm_not_relative_change() -> None:
    assert _signed_ppm(Decimal("0.200000000000000000"), Decimal("0.215000000000000000")) == 15_000
    assert _signed_ppm(Decimal("0.215000000000000000"), Decimal("0.200000000000000000")) == -15_000


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unsupported", "partial_result"])
async def test_unsupported_or_missing_measurement_is_not_publishable(
    verifier_runtime_inputs: object, mode: str
) -> None:
    command, materialized, fixture = _command_and_materialized(verifier_runtime_inputs)
    fixture.m3.mode = mode

    result = await IndependentGeometryVerifier(fixture.executor)(command, materialized)

    assert result.publishable is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes",),
    [
        ({"direction_passed": False},),
        ({"target_minimum_passed": False},),
        ({"target_maximum_passed": False},),
        ({"control_drifts_ppm": (20_001, 0, 0, 0, 0), "control_drift_passed": False},),
    ],
)
async def test_every_repeat_gate_failure_is_not_publishable(
    verifier_runtime_inputs: object,
    changes: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command, materialized, fixture = _command_and_materialized(verifier_runtime_inputs)
    verifier = IndependentGeometryVerifier(fixture.executor)
    original = verifier._repeat_evidence

    def failing_repeat(*args: object) -> object:
        return replace(original(*args), **changes)

    monkeypatch.setattr(verifier, "_repeat_evidence", failing_repeat)

    result = await verifier(command, materialized)

    assert fixture.m3.source_calls == 3
    assert fixture.m3.result_calls == 3
    assert result.publishable is False


@pytest.mark.asyncio
async def test_source_equals_result_and_identity_mismatch_fail_closed(
    verifier_runtime_inputs: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command, materialized, fixture = _command_and_materialized(verifier_runtime_inputs)
    forged = replace(
        materialized,
        content=command.source_bytes,
        sha256=hashlib.sha256(command.source_bytes).hexdigest(),
    )

    result = await IndependentGeometryVerifier(fixture.executor)(command, forged)

    assert result.publishable is False

    original = fixture.m3.inspect_result

    def mismatched_identity(**kwargs: object) -> runtime.BackendM3Result:
        backend_result = original(**kwargs)
        fields = dict(backend_result.fields)
        fields["topology_digest"] = "0" * 64
        return runtime.BackendM3Result(payload_schema=backend_result.payload_schema, fields=fields)

    monkeypatch.setattr(fixture.m3, "inspect_result", mismatched_identity)
    identity_mismatch = await IndependentGeometryVerifier(fixture.executor)(command, materialized)

    assert identity_mismatch.publishable is False

    decode_failure = await IndependentGeometryVerifier(fixture.executor)(
        command, replace(materialized, mime_type="image/png")
    )

    assert decode_failure.publishable is False


@pytest.mark.asyncio
async def test_duplicate_repeat_receipts_are_not_fresh_evidence(
    verifier_runtime_inputs: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command, materialized, fixture = _command_and_materialized(verifier_runtime_inputs)
    _force_directional_result_m3(fixture, monkeypatch)
    verifier = IndependentGeometryVerifier(fixture.executor)
    original = verifier._repeat_evidence

    def duplicate_receipts(*args: object) -> object:
        return replace(
            original(*args),
            source_receipt_digest="1" * 64,
            result_receipt_digest="2" * 64,
        )

    monkeypatch.setattr(verifier, "_repeat_evidence", duplicate_receipts)

    result = await verifier(command, materialized)

    assert result.publishable is False
    assert result.authority_metrics["repeat_group_validation"]["source_receipts_fresh"] is False
    assert result.authority_metrics["repeat_group_validation"]["result_receipts_fresh"] is False
