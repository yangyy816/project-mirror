from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

import pytest
from test_demo_d02_r2_runtime_forward import _executor, _screen
from test_demo_d02_r2_runtime_forward import runtime_inputs as runtime_inputs_source

from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api.demo_d08_geometry_adapter import (
    D02FixedGeometryCase,
    GeometryDirection,
    GeometryExecutionAuthority,
)
from mirror_api.demo_d08_geometry_runtime_adapter import (
    D02M4GeometryRuntimeAdapter,
    GeometryRuntimeAdapterError,
)
from mirror_api.demo_geometry_editor import (
    GeometryAdapterRequest,
    GeometryBackendIdentity,
)


def _digest(marker: str) -> str:
    return hashlib.sha256(marker.encode()).hexdigest()


@dataclass(frozen=True)
class _RuntimeContext:
    executor: runtime.DemoM3M4Executor
    m4: _CallCountingM4
    rows: tuple[Mapping[str, object], ...]
    materials: tuple[runtime.SourceMaterial, ...]


class _CallCountingM4(Protocol):
    calls: int


@pytest.fixture(scope="module")
def runtime_context() -> _RuntimeContext:
    inputs = runtime_inputs_source.__wrapped__()
    screening = _screen(inputs)
    fixture = _executor(inputs)
    report = cast(Mapping[str, object], screening.result.report_row)
    report_payload = report.get("report_payload")
    assert isinstance(report_payload, Mapping)
    rows = report_payload.get("ordered_case_manifest")
    assert isinstance(rows, list)
    assert all(isinstance(row, Mapping) for row in rows)
    return _RuntimeContext(
        executor=fixture.executor,
        m4=cast(_CallCountingM4, fixture.m4),
        rows=tuple(cast(Mapping[str, object], row) for row in rows),
        materials=tuple(inputs.materials),
    )


def _authority(
    row: Mapping[str, object], source_landmark_digest: str
) -> GeometryExecutionAuthority:
    fixed = D02FixedGeometryCase(
        case_id=cast(str, row["case_id"]),
        case_record_digest=cast(str, row["record_digest"]),
        case_specification_digest=cast(str, row["case_specification_digest"]),
        case_binding_digest="0" * 64,
        case_ordinal=cast(int, row["case_ordinal"]),
        source_ordinal=cast(int, row["source_ordinal"]),
        source_asset_id=cast(str, row["source_asset_id"]),
        source_asset_sha256=cast(str, row["source_asset_sha256"]),
        dimension_key=cast(str, row["dimension_key"]),
        direction=GeometryDirection(cast(str, row["direction"])),
        magnitude_ppm=cast(int, row["magnitude_ppm"]),
        warp_plan_digest=cast(str, row["warp_plan_digest"]),
        geometry_ontology_digest=cast(str, row["geometry_ontology_version_digest"]),
        source_landmark_digest=source_landmark_digest,
        output_policy_version=cast(str, row["output_policy_version"]),
        determinism_version=cast(str, row["determinism_level"]),
        backend_candidate_id="OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2",
        backend_algorithm_version=cast(str, row["geometry_algorithm_version"]),
        backend_runtime_manifest_digest=cast(str, row["runtime_manifest_digest"]),
        backend_configuration_digest=cast(str, row["runtime_config_digest"]),
        output_width=cast(int, row["output_width"]),
        output_height=cast(int, row["output_height"]),
    )
    return GeometryExecutionAuthority(
        editing_session_id="1" * 32,
        editing_session_digest=_digest("session"),
        plan_id="2" * 32,
        plan_digest=_digest("plan"),
        operation_id="3" * 32,
        operation_authority_digest=_digest("operation-authority"),
        operation_spec_digest=_digest("operation-spec"),
        input_image_version_id="4" * 32,
        input_image_version_digest=_digest("image-version"),
        input_sequence=0,
        input_asset_id="5" * 32,
        input_asset_sha256=fixed.source_asset_sha256,
        root_source_asset_id=fixed.source_asset_id,
        root_source_asset_sha256=fixed.source_asset_sha256,
        d02_admission_id="6" * 32,
        d02_admission_digest=_digest("admission"),
        d02_screening_report_id="7" * 32,
        d02_screening_report_digest=_digest("screening"),
        fixed_case=fixed,
        authority_digest="0" * 64,
    )


def _request(runtime_context: _RuntimeContext, row_index: int = 0) -> GeometryAdapterRequest:
    row = runtime_context.rows[row_index]
    material = runtime_context.materials[cast(int, row["source_ordinal"]) - 1]
    authority = _authority(row, _digest("source-landmark"))
    return GeometryAdapterRequest(
        authority=authority,
        operation_authority_digest=authority.operation_authority_digest,
        operation_spec_digest=authority.operation_spec_digest,
        source_bytes=material.content,
    )


def test_reconstructed_adapter_executes_current_bytes_once_with_fresh_m4_receipt(
    runtime_context: _RuntimeContext,
) -> None:
    adapter = D02M4GeometryRuntimeAdapter(
        executor=runtime_context.executor, case_rows=runtime_context.rows
    )
    request = _request(runtime_context)
    calls_before = runtime_context.m4.calls

    result = adapter.execute(request=request)

    assert runtime_context.m4.calls == calls_before + 1
    assert result.content != request.source_bytes
    assert result.content_sha256 == hashlib.sha256(result.content).hexdigest()
    assert result.byte_size == len(result.content)
    assert result.identity == GeometryBackendIdentity(
        candidate_id=request.authority.fixed_case.backend_candidate_id,
        algorithm_version=request.authority.fixed_case.backend_algorithm_version,
        runtime_manifest_digest=request.authority.fixed_case.backend_runtime_manifest_digest,
        configuration_digest=request.authority.fixed_case.backend_configuration_digest,
    )
    assert result.backend_execution_receipt != "0" * 64
    assert result.case_record_digest == request.authority.fixed_case.case_record_digest


@pytest.mark.parametrize("mutation", ["source", "case_order"])
def test_source_and_case_substitution_fail_closed(
    runtime_context: _RuntimeContext, mutation: str
) -> None:
    request = _request(runtime_context)
    if mutation == "source":
        substituted = GeometryAdapterRequest(
            authority=request.authority,
            operation_authority_digest=request.operation_authority_digest,
            operation_spec_digest=request.operation_spec_digest,
            source_bytes=b"substituted-source",
        )
        adapter = D02M4GeometryRuntimeAdapter(
            executor=runtime_context.executor, case_rows=runtime_context.rows
        )
        with pytest.raises(GeometryRuntimeAdapterError, match="M4 execution failed"):
            adapter.execute(request=substituted)
    else:
        swapped = list(runtime_context.rows)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        with pytest.raises(GeometryRuntimeAdapterError, match="case row order"):
            D02M4GeometryRuntimeAdapter(executor=runtime_context.executor, case_rows=swapped)


def test_identity_mismatch_is_rejected_before_execution(runtime_context: _RuntimeContext) -> None:
    request = _request(runtime_context)
    altered_rows = [dict(row) for row in runtime_context.rows]
    for row in altered_rows:
        row["runtime_config_digest"] = _digest("other-runtime-config")
    adapter = D02M4GeometryRuntimeAdapter(executor=runtime_context.executor, case_rows=altered_rows)

    assert adapter.identity != GeometryBackendIdentity(
        candidate_id=request.authority.fixed_case.backend_candidate_id,
        algorithm_version=request.authority.fixed_case.backend_algorithm_version,
        runtime_manifest_digest=request.authority.fixed_case.backend_runtime_manifest_digest,
        configuration_digest=request.authority.fixed_case.backend_configuration_digest,
    )
    with pytest.raises(GeometryRuntimeAdapterError, match="fixed case differs"):
        adapter.execute(request=request)


def test_backend_failure_and_historical_output_injection_fail_closed(
    runtime_context: _RuntimeContext,
) -> None:
    inputs = runtime_inputs_source.__wrapped__()
    failing_executor = _executor(inputs, m4_mode="partial_failure").executor
    adapter = D02M4GeometryRuntimeAdapter(executor=failing_executor, case_rows=runtime_context.rows)
    with pytest.raises(GeometryRuntimeAdapterError, match="M4 execution failed"):
        adapter.execute(request=_request(runtime_context))

    injected = [dict(row) for row in runtime_context.rows]
    injected[0]["historical_result"] = {"pass": True}
    with pytest.raises(GeometryRuntimeAdapterError, match="case row shape"):
        D02M4GeometryRuntimeAdapter(executor=runtime_context.executor, case_rows=injected)
