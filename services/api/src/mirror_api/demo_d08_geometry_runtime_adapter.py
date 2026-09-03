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
from mirror_api import demo_d02_targeted_m4_repair_execution as targeted_execution
from mirror_api.demo_d08_geometry_adapter import (
    FIXED_RESULT_MEDIA_TYPE,
    TARGETED_REPAIR_ALGORITHM_VERSION,
    D02FixedGeometryCase,
    GeometryDirection,
    GeometryExecutionAuthority,
    qualified_backend_candidate_id,
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
        additional_executors: Sequence[runtime.DemoM3M4Executor] = (),
    ) -> None:
        executors = validate_d08_executors(executor, additional_executors)
        rows = _validate_case_rows(executors, case_rows)
        standard_rows = tuple(
            row for row in rows if row["geometry_algorithm_version"] == ALGORITHM_VERSION
        )
        standard_configs = {cast(str, row["runtime_config_digest"]) for row in standard_rows}
        if not standard_rows or len(standard_configs) != 1:
            raise GeometryRuntimeAdapterError(
                "RUNTIME_IDENTITY_MISMATCH",
                "standard cases must have one configuration identity",
            )
        standard_executor = executors[ALGORITHM_VERSION]
        configuration_digest = standard_configs.pop()

        self._executors = MappingProxyType(dict(executors))
        self._cases = MappingProxyType({cast(str, row["case_id"]): row for row in rows})
        self._identity = GeometryBackendIdentity(
            candidate_id=CANDIDATE_ID,
            algorithm_version=ALGORITHM_VERSION,
            runtime_manifest_digest=standard_executor.recipe.runtime_manifest_digest,
            configuration_digest=configuration_digest,
        )

    @property
    def identity(self) -> GeometryBackendIdentity:
        return self._identity

    def identity_for(self, *, authority: GeometryExecutionAuthority) -> GeometryBackendIdentity:
        if not isinstance(authority, GeometryExecutionAuthority):
            raise GeometryRuntimeAdapterError("INVALID_AUTHORITY", "authority must be typed")
        case = authority.fixed_case
        if case.case_id not in self._cases or case.backend_algorithm_version not in self._executors:
            raise GeometryRuntimeAdapterError(
                "CASE_BACKEND_UNAVAILABLE", "fixed case backend is unavailable"
            )
        return _identity_for_case(case)

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
        if self.identity_for(authority=authority) != _identity_for_case(case):
            raise GeometryRuntimeAdapterError(
                "BACKEND_IDENTITY_MISMATCH", "fixed case does not match the installed backend"
            )
        executor = self._executors.get(case.backend_algorithm_version)
        if executor is None:
            raise GeometryRuntimeAdapterError(
                "CASE_BACKEND_UNAVAILABLE", "fixed case backend is unavailable"
            )
        descriptor = executor.manifest.descriptors[case.source_ordinal - 1]
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
            output = executor.transform(
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
            identity=self.identity_for(authority=authority),
            backend_execution_receipt=output.execution_receipt_digest,
            authority_digest=authority.authority_digest,
            operation_authority_digest=authority.operation_authority_digest,
            operation_spec_digest=authority.operation_spec_digest,
            case_record_digest=case.case_record_digest,
            case_specification_digest=case.case_specification_digest,
            case_binding_digest=case.case_binding_digest,
            source_asset_sha256=case.source_asset_sha256,
        )


def reconstruct_d08_executor(
    executor: runtime.DemoM3M4Executor,
) -> runtime.DemoM3M4Executor:
    """Replay either frozen D02 M4 identity without opening private custody."""

    if not isinstance(executor, runtime.DemoM3M4Executor):
        raise GeometryRuntimeAdapterError(
            "INVALID_EXECUTOR", "executor must be a reconstructed D02 executor"
        )
    if executor.recipe.m4_algorithm_version == ALGORITHM_VERSION:
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
                "EXECUTOR_RECONSTRUCTION_FAILED",
                "standard executor does not replay from durable inputs",
            ) from None
        if reconstructed != executor:
            raise GeometryRuntimeAdapterError(
                "EXECUTOR_RECONSTRUCTION_FAILED",
                "standard executor reconstruction is not self-consistent",
            )
        return reconstructed
    if executor.recipe.m4_algorithm_version != TARGETED_REPAIR_ALGORITHM_VERSION:
        raise GeometryRuntimeAdapterError(
            "ALGORITHM_MISMATCH", "executor algorithm is not in the exact D08 allowlist"
        )
    try:
        expected_recipe = targeted_execution.build_targeted_runtime_recipe(
            predecessor_recipe=runtime.build_default_runtime_recipe(),
            algorithm_version=TARGETED_REPAIR_ALGORITHM_VERSION,
        )
        ordered_ids = cast(
            tuple[str, str, str, str],
            tuple(descriptor.source_id for descriptor in executor.manifest.descriptors),
        )
        expected_runtime_handle = runtime.M3RuntimeHandle(
            source_manifest_digest=executor.manifest.manifest_digest,
            ordered_source_ids=ordered_ids,
            recipe_version=expected_recipe.recipe_version,
            recipe_digest=expected_recipe.recipe_digest,
            runtime_manifest_digest=expected_recipe.runtime_manifest_digest,
            model_identity_digest=executor.model_identity.identity_digest,
        )
        expected_model_handle = runtime.M3ModelHandle(
            source_manifest_digest=executor.manifest.manifest_digest,
            ordered_source_ids=ordered_ids,
            recipe_digest=expected_recipe.recipe_digest,
            model_identity_digest=executor.model_identity.identity_digest,
            model_config_digest=executor.model_identity.config_digest,
            weights_digest_or_no_weights=executor.model_identity.weights_digest_or_no_weights,
        )
    except Exception:
        raise GeometryRuntimeAdapterError(
            "EXECUTOR_RECONSTRUCTION_FAILED",
            "targeted executor authority cannot be reconstructed",
        ) from None
    if (
        executor.recipe != expected_recipe
        or executor.model_identity != runtime.build_default_model_identity()
        or executor.runtime_handle != expected_runtime_handle
        or executor.model_handle != expected_model_handle
        or executor.m3_backend.execution_runtime_set_digest
        != expected_recipe.runtime_manifest_digest
        or executor.m3_backend.model_identity_digest != executor.model_identity.identity_digest
        or executor.m3_backend.model_config_digest != executor.model_identity.config_digest
        or executor.m3_backend.weights_digest_or_no_weights
        != executor.model_identity.weights_digest_or_no_weights
        or executor.m3_backend.network_policy != expected_recipe.network_policy
        or executor.m4_backend.execution_runtime_set_digest
        != expected_recipe.runtime_manifest_digest
        or executor.m4_backend.algorithm_version != TARGETED_REPAIR_ALGORITHM_VERSION
        or executor.m4_backend.network_policy != expected_recipe.network_policy
    ):
        raise GeometryRuntimeAdapterError(
            "EXECUTOR_RECONSTRUCTION_FAILED",
            "targeted executor differs from its accepted durable authority",
        )
    return executor


def validate_d08_executors(
    primary: runtime.DemoM3M4Executor,
    additional: Sequence[runtime.DemoM3M4Executor],
) -> Mapping[str, runtime.DemoM3M4Executor]:
    if isinstance(additional, (str, bytes)) or len(additional) > 1:
        raise GeometryRuntimeAdapterError(
            "INVALID_EXECUTOR_SET", "D08 permits at most one targeted executor"
        )
    reconstructed = tuple(reconstruct_d08_executor(item) for item in (primary, *tuple(additional)))
    if reconstructed[0].recipe.m4_algorithm_version != ALGORITHM_VERSION:
        raise GeometryRuntimeAdapterError(
            "ALGORITHM_MISMATCH", "primary executor must be the accepted OpenCV backend"
        )
    by_algorithm: dict[str, runtime.DemoM3M4Executor] = {}
    reference = reconstructed[0]
    shared_recipe_fields = (
        "preprocessing_version",
        "m3_algorithm_version",
        "runtime_manifest_digest",
        "topology_digest",
        "measurement_config_digest",
        "threshold_config_digest",
        "deterministic_ordering",
        "unsupported_behavior",
        "failure_behavior",
        "network_policy",
        "source_m3_output_schema",
        "result_m3_output_schema",
        "m4_output_schema",
        "screening_output_schema",
    )
    for item in reconstructed:
        algorithm = item.recipe.m4_algorithm_version
        if algorithm in by_algorithm:
            raise GeometryRuntimeAdapterError(
                "INVALID_EXECUTOR_SET", "executor algorithms must be unique"
            )
        if (
            item.manifest != reference.manifest
            or item.model_identity != reference.model_identity
            or any(
                getattr(item.recipe, field) != getattr(reference.recipe, field)
                for field in shared_recipe_fields
            )
        ):
            raise GeometryRuntimeAdapterError(
                "EXECUTOR_AUTHORITY_MISMATCH",
                "case executors do not share one M3/source authority",
            )
        by_algorithm[algorithm] = item
    return MappingProxyType(by_algorithm)


def _validate_case_rows(
    executors: Mapping[str, runtime.DemoM3M4Executor],
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
        algorithm = row["geometry_algorithm_version"]
        if not isinstance(algorithm, str) or algorithm not in executors:
            raise GeometryRuntimeAdapterError(
                "CASE_BACKEND_UNAVAILABLE", "case row backend is unavailable"
            )
        executor = executors[algorithm]
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
            ("geometry_algorithm_version", algorithm),
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
    algorithms = {cast(str, row["geometry_algorithm_version"]) for row in rows}
    if algorithms != set(executors):
        raise GeometryRuntimeAdapterError(
            "INVALID_EXECUTOR_SET", "executor set must exactly match admitted case algorithms"
        )
    for algorithm in algorithms:
        configs = {
            cast(str, row["runtime_config_digest"])
            for row in rows
            if row["geometry_algorithm_version"] == algorithm
        }
        if len(configs) != 1:
            raise GeometryRuntimeAdapterError(
                "RUNTIME_IDENTITY_MISMATCH",
                "each case algorithm must have one configuration identity",
            )
        if algorithm == TARGETED_REPAIR_ALGORITHM_VERSION:
            backend_config = getattr(executors[algorithm].m4_backend, "config_digest", None)
            if backend_config != next(iter(configs)):
                raise GeometryRuntimeAdapterError(
                    "RUNTIME_IDENTITY_MISMATCH",
                    "targeted case configuration differs from its executor",
                )
    return tuple(rows)


def _fixed_case_from_row(
    row: Mapping[str, object], *, source_landmark_digest: str
) -> D02FixedGeometryCase:
    algorithm_version = cast(str, row["geometry_algorithm_version"])
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


def _identity_for_case(case: D02FixedGeometryCase) -> GeometryBackendIdentity:
    return GeometryBackendIdentity(
        candidate_id=case.backend_candidate_id,
        algorithm_version=case.backend_algorithm_version,
        runtime_manifest_digest=case.backend_runtime_manifest_digest,
        configuration_digest=case.backend_configuration_digest,
    )
