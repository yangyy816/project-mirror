from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

import pytest
from PIL import Image
from test_demo_d02_r2_runtime_forward import _executor, _screen
from test_demo_d02_r2_runtime_forward import runtime_inputs as runtime_inputs_source
from test_demo_d02_targeted_m4_repair_execution import _context as _targeted_context

from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_targeted_m4_repair_backend as targeted_backend_module
from mirror_api import demo_d02_targeted_m4_repair_execution as targeted_execution
from mirror_api.demo_d08_geometry_adapter import (
    TARGETED_REPAIR_ALGORITHM_VERSION,
    TARGETED_REPAIR_CANDIDATE_ID,
    D02FixedGeometryCase,
    GeometryDirection,
    GeometryExecutionAuthority,
    qualified_backend_candidate_id,
)
from mirror_api.demo_d08_geometry_runtime_adapter import (
    D02M4GeometryRuntimeAdapter,
    GeometryRuntimeAdapterError,
    reconstruct_d08_executor,
)
from mirror_api.demo_d08_geometry_verifier import IndependentGeometryVerifierRouter
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


class _TargetedM4:
    algorithm_version = TARGETED_REPAIR_ALGORITHM_VERSION
    network_policy = runtime.NETWORK_POLICY

    def __init__(self, runtime_digest: str, config_digest: str) -> None:
        self.execution_runtime_set_digest = runtime_digest
        self.config_digest = config_digest

    def transform(
        self,
        *,
        content: bytes,
        descriptor: runtime.DurableSourceDescriptor,
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> runtime.BackendM4Result:
        del case_entry, replay_index
        with Image.open(BytesIO(content)) as image:
            image.load()
            rgb = image.convert("RGB")
            try:
                pixel = rgb.getpixel((0, 0))
                rgb.putpixel((0, 0), ((pixel[0] + 17) % 256, pixel[1], pixel[2]))
                output = BytesIO()
                rgb.save(output, format="JPEG", quality=95, subsampling=0, optimize=False)
            finally:
                rgb.close()
        assert image.size == (descriptor.width, descriptor.height)
        return runtime.BackendM4Result(content=output.getvalue(), changed_pixel_count=1)


def _targeted_executor(
    standard: runtime.DemoM3M4Executor, *, config_digest: str
) -> runtime.DemoM3M4Executor:
    recipe = targeted_execution.build_targeted_runtime_recipe(
        predecessor_recipe=standard.recipe,
        algorithm_version=TARGETED_REPAIR_ALGORITHM_VERSION,
    )
    ordered_ids = cast(
        tuple[str, str, str, str],
        tuple(item.source_id for item in standard.manifest.descriptors),
    )
    runtime_handle = runtime.M3RuntimeHandle(
        source_manifest_digest=standard.manifest.manifest_digest,
        ordered_source_ids=ordered_ids,
        recipe_version=recipe.recipe_version,
        recipe_digest=recipe.recipe_digest,
        runtime_manifest_digest=recipe.runtime_manifest_digest,
        model_identity_digest=standard.model_identity.identity_digest,
    )
    model_handle = runtime.M3ModelHandle(
        source_manifest_digest=standard.manifest.manifest_digest,
        ordered_source_ids=ordered_ids,
        recipe_digest=recipe.recipe_digest,
        model_identity_digest=standard.model_identity.identity_digest,
        model_config_digest=standard.model_identity.config_digest,
        weights_digest_or_no_weights=standard.model_identity.weights_digest_or_no_weights,
    )
    return runtime.DemoM3M4Executor(
        manifest=standard.manifest,
        recipe=recipe,
        model_identity=standard.model_identity,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        m3_backend=standard.m3_backend,
        m4_backend=_TargetedM4(recipe.runtime_manifest_digest, config_digest),
    )


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
    algorithm_version = cast(str, row["geometry_algorithm_version"])
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
        backend_candidate_id=qualified_backend_candidate_id(
            case_ordinal=cast(int, row["case_ordinal"]),
            source_ordinal=cast(int, row["source_ordinal"]),
            dimension_key=cast(str, row["dimension_key"]),
            direction=cast(str, row["direction"]),
            magnitude_ppm=cast(int, row["magnitude_ppm"]),
            algorithm_version=algorithm_version,
        ),
        backend_algorithm_version=algorithm_version,
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


def test_heterogeneous_successor_routes_only_case_25_to_targeted_executor(
    runtime_context: _RuntimeContext,
) -> None:
    rows = [dict(row) for row in runtime_context.rows]
    target_config_digest = _digest("targeted-config")
    rows[24]["geometry_algorithm_version"] = TARGETED_REPAIR_ALGORITHM_VERSION
    rows[24]["runtime_config_digest"] = target_config_digest
    targeted = _targeted_executor(runtime_context.executor, config_digest=target_config_digest)

    adapter = D02M4GeometryRuntimeAdapter(
        executor=runtime_context.executor,
        case_rows=rows,
        additional_executors=(targeted,),
    )
    verifier = IndependentGeometryVerifierRouter(
        runtime_context.executor,
        (targeted,),
    )
    assert callable(verifier)
    request = _request(
        _RuntimeContext(
            executor=runtime_context.executor,
            m4=runtime_context.m4,
            rows=tuple(rows),
            materials=runtime_context.materials,
        ),
        row_index=24,
    )

    assert request.authority.fixed_case.backend_algorithm_version == (
        TARGETED_REPAIR_ALGORITHM_VERSION
    )
    assert adapter.identity_for(authority=request.authority).candidate_id == (
        TARGETED_REPAIR_CANDIDATE_ID
    )
    result = adapter.execute(request=request)
    assert result.identity.candidate_id == TARGETED_REPAIR_CANDIDATE_ID
    assert result.identity.algorithm_version == TARGETED_REPAIR_ALGORITHM_VERSION
    assert result.content_sha256 != request.authority.root_source_asset_sha256

    with pytest.raises(GeometryRuntimeAdapterError, match="backend is unavailable"):
        D02M4GeometryRuntimeAdapter(
            executor=runtime_context.executor,
            case_rows=rows,
        )

    forged = [dict(row) for row in rows]
    forged[0]["geometry_algorithm_version"] = TARGETED_REPAIR_ALGORITHM_VERSION
    forged[0]["runtime_config_digest"] = cast(str, rows[24]["runtime_config_digest"])
    with pytest.raises(GeometryRuntimeAdapterError, match="case row is invalid"):
        D02M4GeometryRuntimeAdapter(
            executor=runtime_context.executor,
            case_rows=forged,
            additional_executors=(targeted,),
        )


def test_real_targeted_repair_executor_replays_accepted_handle_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def decode(content: bytes, *, expected_width: int, expected_height: int) -> object:
        with Image.open(BytesIO(content)) as image:
            image.load()
            rgb = image.convert("RGB")
            try:
                assert rgb.size == (expected_width, expected_height)
                return SimpleNamespace(
                    bytes_value=rgb.tobytes(),
                    width=expected_width,
                    height=expected_height,
                )
            finally:
                rgb.close()

    monkeypatch.setattr(targeted_backend_module, "decode_canonical_rgb_image", decode)
    context = _targeted_context(tmp_path)

    assert reconstruct_d08_executor(context.executor) is context.executor
