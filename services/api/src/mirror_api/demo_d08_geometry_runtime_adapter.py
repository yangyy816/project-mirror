"""D08 bridge from the reconstructed D02 M4 executor to GeometryExecutionBackend.

This adapter only accepts already reconstructed runtime objects and public case
rows.  It neither discovers D02 custody state nor reads a locator, path, or
historical result.  Each call creates fresh M4 output evidence from the bytes
in the current GeometryAdapterRequest.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final, cast

from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api.demo_d08_geometry_adapter import (
    FIXED_RESULT_MEDIA_TYPE,
    D02FixedGeometryCase,
    GeometryDirection,
)
from mirror_api.demo_geometry_editor import (
    GeometryAdapterRequest,
    GeometryAdapterResult,
    GeometryBackendIdentity,
    GeometryExecutionBackend,
)
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION, CANDIDATE_ID

_CASE_COUNT: Final = 48
_DIMENSIONS: Final = ("jaw_width", "chin_height", "eye_spacing")
_DIRECTIONS: Final = ("DECREASE", "INCREASE")
_MAGNITUDES: Final = (15_000, 30_000)
_CASE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "case_ordinal",
        "case_id",
        "source_manifest_digest",
        "source_ordinal",
        "source_authority_key",
        "source_admission_event_id",
        "source_asset_id",
        "source_asset_sha256",
        "r2_source_authority_record_id",
        "source_qa_snapshot_digest",
        "source_measurement_projection_digest",
        "source_p2_candidate_manifest_content_digest",
        "dimension_authority_manifest_content_digest",
        "geometry_ontology_version_digest",
        "dimension_key",
        "priority_index",
        "direction",
        "direction_index",
        "magnitude_ppm",
        "magnitude_index",
        "ordered_control_dimensions",
        "warp_plan_digest",
        "geometry_algorithm_version",
        "runtime_manifest_digest",
        "runtime_config_digest",
        "output_policy_version",
        "output_width",
        "output_height",
        "determinism_level",
        "execution_config_digest",
        "case_specification_digest",
        "record_digest",
    }
)


class GeometryRuntimeAdapterError(RuntimeError):
    """The public D02 runtime/case authority cannot safely serve D08."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class D02M4GeometryRuntimeAdapter(GeometryExecutionBackend):
    """Fresh D08 M4 backend over an already pre-warmed D02 executor."""

    def __init__(
        self,
        *,
        executor: runtime.DemoM3M4Executor,
        case_rows: Sequence[Mapping[str, object]],
    ) -> None:
        if not isinstance(executor, runtime.DemoM3M4Executor):
            raise GeometryRuntimeAdapterError(
                "INVALID_EXECUTOR", "executor must be a reconstructed D02 executor"
            )
        try:
            reconstructed = runtime.reconstruct_executor(
                executor.manifest,
                recipe=executor.recipe,
                model_identity=executor.model_identity,
                runtime_handle=executor.runtime_handle,
                model_handle=executor.model_handle,
                m3_backend=executor.m3_backend,
                m4_backend=executor.m4_backend,
            )
        except Exception:
            raise GeometryRuntimeAdapterError(
                "EXECUTOR_RECONSTRUCTION_FAILED", "executor does not replay from durable inputs"
            ) from None
        if reconstructed != executor:
            raise GeometryRuntimeAdapterError(
                "EXECUTOR_RECONSTRUCTION_FAILED", "executor reconstruction is not self-consistent"
            )
        if executor.recipe.m4_algorithm_version != ALGORITHM_VERSION:
            raise GeometryRuntimeAdapterError(
                "ALGORITHM_MISMATCH", "executor does not use the accepted M4 algorithm"
            )

        rows = _validate_case_rows(executor, case_rows)
        runtime_digests = {cast(str, row["runtime_manifest_digest"]) for row in rows}
        config_digests = {cast(str, row["runtime_config_digest"]) for row in rows}
        if len(runtime_digests) != 1 or len(config_digests) != 1:
            raise GeometryRuntimeAdapterError(
                "RUNTIME_IDENTITY_MISMATCH", "case rows do not have one runtime identity"
            )
        runtime_digest = runtime_digests.pop()
        configuration_digest = config_digests.pop()
        if runtime_digest != executor.recipe.runtime_manifest_digest:
            raise GeometryRuntimeAdapterError(
                "RUNTIME_IDENTITY_MISMATCH", "case runtime does not match executor runtime"
            )

        self._executor = reconstructed
        self._cases = MappingProxyType({cast(str, row["case_id"]): row for row in rows})
        self._identity = GeometryBackendIdentity(
            candidate_id=CANDIDATE_ID,
            algorithm_version=ALGORITHM_VERSION,
            runtime_manifest_digest=runtime_digest,
            configuration_digest=configuration_digest,
        )

    @property
    def identity(self) -> GeometryBackendIdentity:
        return self._identity

    def execute(self, *, request: GeometryAdapterRequest) -> GeometryAdapterResult:
        if not isinstance(request, GeometryAdapterRequest):
            raise GeometryRuntimeAdapterError("INVALID_REQUEST", "request must be typed")
        authority = request.authority
        case = authority.fixed_case
        row = self._cases.get(case.case_id)
        if row is None:
            raise GeometryRuntimeAdapterError("CASE_UNAVAILABLE", "fixed case is unavailable")
        try:
            expected_case = _fixed_case_from_row(
                row, source_landmark_digest=case.source_landmark_digest
            )
        except Exception:
            raise GeometryRuntimeAdapterError("CASE_INVALID", "fixed case is invalid") from None
        if expected_case != case:
            raise GeometryRuntimeAdapterError(
                "CASE_AUTHORITY_MISMATCH", "fixed case differs from public row"
            )
        if self.identity != _identity_for_case(case):
            raise GeometryRuntimeAdapterError(
                "BACKEND_IDENTITY_MISMATCH", "fixed case does not match the installed backend"
            )
        descriptor = self._executor.manifest.descriptors[case.source_ordinal - 1]
        if (
            descriptor.source_id != case.source_asset_id
            or descriptor.content_sha256 != case.source_asset_sha256
            or descriptor.ordinal != case.source_ordinal
        ):
            raise GeometryRuntimeAdapterError(
                "SOURCE_AUTHORITY_MISMATCH", "fixed case source is not in the executor manifest"
            )
        try:
            material = runtime.SourceMaterial(descriptor=descriptor, content=request.source_bytes)
            output = self._executor.transform(
                material=material,
                case_entry=row,
                replay_index=1,
            )
        except Exception:
            raise GeometryRuntimeAdapterError(
                "M4_EXECUTION_FAILED", "M4 execution failed"
            ) from None
        if (
            output.case_id != case.case_id
            or output.replay_index != 1
            or output.result_width != case.output_width
            or output.result_height != case.output_height
            or output.result_mime_type != FIXED_RESULT_MEDIA_TYPE
            or output.execution_succeeded is not True
        ):
            raise GeometryRuntimeAdapterError(
                "M4_OUTPUT_MISMATCH", "fresh M4 output does not match the fixed case"
            )
        return GeometryAdapterResult(
            content=output.content,
            content_sha256=output.result_sha256,
            byte_size=output.result_byte_size,
            media_type=output.result_mime_type,
            width=output.result_width,
            height=output.result_height,
            changed_pixel_count=output.changed_pixel_count,
            identity=self.identity,
            backend_execution_receipt=output.execution_receipt_digest,
            authority_digest=authority.authority_digest,
            operation_authority_digest=authority.operation_authority_digest,
            operation_spec_digest=authority.operation_spec_digest,
            case_record_digest=case.case_record_digest,
            case_specification_digest=case.case_specification_digest,
            case_binding_digest=case.case_binding_digest,
            source_asset_sha256=case.source_asset_sha256,
        )


def _validate_case_rows(
    executor: runtime.DemoM3M4Executor,
    case_rows: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    if isinstance(case_rows, (str, bytes)) or len(case_rows) != _CASE_COUNT:
        raise GeometryRuntimeAdapterError("CASE_MATRIX_INVALID", "case matrix must contain 48 rows")
    rows: list[Mapping[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(case_rows):
        if not isinstance(raw, Mapping) or set(raw) != _CASE_FIELDS:
            raise GeometryRuntimeAdapterError("CASE_MATRIX_INVALID", "case row shape is invalid")
        row = MappingProxyType(dict(raw))
        source_ordinal = index // 12 + 1
        dimension_index = index % 12 // 4
        direction_index = index % 4 // 2
        magnitude_index = index % 2
        expected = (
            ("case_ordinal", index + 1),
            ("source_ordinal", source_ordinal),
            ("dimension_key", _DIMENSIONS[dimension_index]),
            ("priority_index", dimension_index + 1),
            ("direction", _DIRECTIONS[direction_index]),
            ("direction_index", direction_index + 1),
            ("magnitude_ppm", _MAGNITUDES[magnitude_index]),
            ("magnitude_index", magnitude_index + 1),
            ("runtime_manifest_digest", executor.recipe.runtime_manifest_digest),
            ("geometry_algorithm_version", ALGORITHM_VERSION),
        )
        if any(row[key] != value for key, value in expected):
            raise GeometryRuntimeAdapterError(
                "CASE_MATRIX_INVALID", "case row order or runtime binding is invalid"
            )
        descriptor = executor.manifest.descriptors[source_ordinal - 1]
        if (
            row["source_asset_id"] != descriptor.source_id
            or row["source_asset_sha256"] != descriptor.content_sha256
            or row["output_width"] != descriptor.width
            or row["output_height"] != descriptor.height
        ):
            raise GeometryRuntimeAdapterError(
                "CASE_SOURCE_MISMATCH", "case row source does not match executor manifest"
            )
        try:
            fixed = _fixed_case_from_row(row, source_landmark_digest="0" * 64)
        except Exception:
            raise GeometryRuntimeAdapterError(
                "CASE_MATRIX_INVALID", "case row is invalid"
            ) from None
        if fixed.case_id in seen_ids:
            raise GeometryRuntimeAdapterError("CASE_MATRIX_INVALID", "case IDs must be unique")
        seen_ids.add(fixed.case_id)
        rows.append(row)
    return tuple(rows)


def _fixed_case_from_row(
    row: Mapping[str, object], *, source_landmark_digest: str
) -> D02FixedGeometryCase:
    return D02FixedGeometryCase(
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
        backend_candidate_id=CANDIDATE_ID,
        backend_algorithm_version=cast(str, row["geometry_algorithm_version"]),
        backend_runtime_manifest_digest=cast(str, row["runtime_manifest_digest"]),
        backend_configuration_digest=cast(str, row["runtime_config_digest"]),
        output_width=cast(int, row["output_width"]),
        output_height=cast(int, row["output_height"]),
    )


def _identity_for_case(case: D02FixedGeometryCase) -> GeometryBackendIdentity:
    return GeometryBackendIdentity(
        candidate_id=case.backend_candidate_id,
        algorithm_version=case.backend_algorithm_version,
        runtime_manifest_digest=case.backend_runtime_manifest_digest,
        configuration_digest=case.backend_configuration_digest,
    )
