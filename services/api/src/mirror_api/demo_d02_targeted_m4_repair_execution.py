"""Strict execution factory for the ADR-053 Case-25 successor.

The accepted V1 runtime recipe allowlist remains untouched.  This module
constructs a separate, fully bound repair recipe and handles for exactly one
case, while retaining the accepted M3 runtime/model identities.  It exposes
no discovery or persistence and never calls source M3 or a Provider.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_final_orchestrator as orchestrator
from mirror_api import demo_d02_r2_authority as r2
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_r2_screening_execution as screening
from mirror_api import demo_d02_targeted_m4_repair as repair
from mirror_api.demo_d02_private_vision_backend import WindowsFaceLandmarkerOfflineM3Backend
from mirror_api.demo_d02_screening_adapters import MeasurementGateAdapter
from mirror_api.demo_d02_targeted_m4_repair_backend import D02TargetedM4RepairBackend

TARGETED_RUNTIME_RECIPE_VERSION: Final = "d02-targeted-m4-repair-runtime-v1"


class D02TargetedM4RepairExecutionError(RuntimeError):
    """Stable public-safe execution failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True, repr=False)
class TargetedM4ExecutionContext:
    replacement_case_fields: Mapping[str, object]
    replacement_case: Mapping[str, object]
    source_material: runtime.SourceMaterial = field(repr=False)
    recipe: runtime.DemoRuntimeRecipe
    runtime_handle: runtime.M3RuntimeHandle
    model_handle: runtime.M3ModelHandle
    executor: runtime.DemoM3M4Executor = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TargetedMeasurementOutcome:
    measured_signed_delta_ppm: tuple[int, int, int]
    predecessor_case_26_absolute_delta_ppm: tuple[int, int, int]
    repeat_consistent: bool
    direction_and_margin_passed: bool
    predecessor_bound_passed: bool
    measurement_gate_passed: bool

    @property
    def passed(self) -> bool:
        return (
            self.repeat_consistent
            and self.direction_and_margin_passed
            and self.predecessor_bound_passed
            and self.measurement_gate_passed
        )


def build_targeted_runtime_recipe(
    *,
    predecessor_recipe: runtime.DemoRuntimeRecipe,
    algorithm_version: str,
) -> runtime.DemoRuntimeRecipe:
    """Create the separate repair recipe without extending the V1 allowlist."""

    if predecessor_recipe != runtime.build_default_runtime_recipe():
        _fail("TARGETED_PREDECESSOR_RECIPE_INVALID")
    try:
        return runtime.DemoRuntimeRecipe(
            recipe_version=TARGETED_RUNTIME_RECIPE_VERSION,
            preprocessing_version=predecessor_recipe.preprocessing_version,
            m3_algorithm_version=predecessor_recipe.m3_algorithm_version,
            m4_algorithm_version=algorithm_version,
            runtime_manifest_digest=predecessor_recipe.runtime_manifest_digest,
            topology_digest=predecessor_recipe.topology_digest,
            measurement_config_digest=predecessor_recipe.measurement_config_digest,
            threshold_config_digest=predecessor_recipe.threshold_config_digest,
            deterministic_ordering=predecessor_recipe.deterministic_ordering,
            unsupported_behavior=predecessor_recipe.unsupported_behavior,
            failure_behavior=predecessor_recipe.failure_behavior,
            network_policy=predecessor_recipe.network_policy,
            source_m3_output_schema=predecessor_recipe.source_m3_output_schema,
            result_m3_output_schema=predecessor_recipe.result_m3_output_schema,
            m4_output_schema=predecessor_recipe.m4_output_schema,
            screening_output_schema=predecessor_recipe.screening_output_schema,
        )
    except (TypeError, ValueError) as error:
        raise D02TargetedM4RepairExecutionError("TARGETED_RECIPE_INVALID") from error


def prepare_targeted_execution(
    *,
    predecessor: orchestrator.PreparedRuntimeEvidence,
    m3_backend: WindowsFaceLandmarkerOfflineM3Backend,
    m4_backend: D02TargetedM4RepairBackend,
) -> TargetedM4ExecutionContext:
    """Bind one Case-25 repair executor to the immutable predecessor sources."""

    if (
        type(predecessor) is not orchestrator.PreparedRuntimeEvidence
        or type(m3_backend) is not WindowsFaceLandmarkerOfflineM3Backend
        or type(m4_backend) is not D02TargetedM4RepairBackend
        or predecessor.model_identity != runtime.build_default_model_identity()
        or len(predecessor.source_materials) != 4
        or len(predecessor.formal_bundle.runtime_packets) != 4
    ):
        _fail("TARGETED_EXECUTION_INPUT_INVALID")
    source = predecessor.source_materials[repair.TARGET_SOURCE_ORDINAL - 1]
    if source.descriptor.ordinal != repair.TARGET_SOURCE_ORDINAL:
        _fail("TARGETED_SOURCE_BINDING_INVALID")
    packet = predecessor.formal_bundle.runtime_packets[repair.TARGET_SOURCE_ORDINAL - 1]
    entry = packet.get("source_manifest_entry")
    if not isinstance(entry, Mapping):
        _fail("TARGETED_SOURCE_BINDING_INVALID")
    fields = dict(
        m4_backend.case_fields(
            source_packet=packet,
            source_entry=entry,
            case_ordinal=repair.TARGET_CASE_ORDINAL,
            dimension_key=cast(str, repair.TARGET_SELECTOR["dimension_key"]),
            direction=cast(str, repair.TARGET_SELECTOR["direction"]),
            magnitude_ppm=cast(int, repair.TARGET_SELECTOR["magnitude_ppm"]),
        )
    )
    case = repair.build_targeted_replacement_case(
        predecessor=predecessor,
        replacement_case_fields=fields,
    )
    recipe = build_targeted_runtime_recipe(
        predecessor_recipe=predecessor.recipe,
        algorithm_version=m4_backend.algorithm_version,
    )
    runtime_handle, model_handle = _mint_targeted_handles(
        manifest=predecessor.formal_bundle.descriptor_manifest,
        recipe=recipe,
        model_identity=predecessor.model_identity,
    )
    if (
        m3_backend.execution_runtime_set_digest != recipe.runtime_manifest_digest
        or m3_backend.model_identity_digest != predecessor.model_identity.identity_digest
        or m3_backend.model_config_digest != predecessor.model_identity.config_digest
        or m3_backend.weights_digest_or_no_weights
        != predecessor.model_identity.weights_digest_or_no_weights
        or m4_backend.execution_runtime_set_digest != recipe.runtime_manifest_digest
        or m4_backend.algorithm_version != recipe.m4_algorithm_version
        or m3_backend.network_policy != recipe.network_policy
        or m4_backend.network_policy != recipe.network_policy
    ):
        _fail("TARGETED_RUNTIME_IDENTITY_MISMATCH")
    executor = runtime.DemoM3M4Executor(
        manifest=predecessor.formal_bundle.descriptor_manifest,
        recipe=recipe,
        model_identity=predecessor.model_identity,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        m3_backend=m3_backend,
        m4_backend=m4_backend,
    )
    return TargetedM4ExecutionContext(
        replacement_case_fields=fields,
        replacement_case=case,
        source_material=source,
        recipe=recipe,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        executor=executor,
    )


def execute_target_m4(
    context: TargetedM4ExecutionContext,
) -> tuple[runtime.M4ExecutionOutput, runtime.M4ExecutionOutput]:
    """Execute exactly the required first and second replay."""

    _validate_context(context)
    first = context.executor.transform(
        material=context.source_material,
        case_entry=context.replacement_case,
        replay_index=1,
    )
    second = context.executor.transform(
        material=context.source_material,
        case_entry=context.replacement_case,
        replay_index=2,
    )
    if (
        first.content != second.content
        or first.result_sha256 != second.result_sha256
        or first.changed_pixel_count != second.changed_pixel_count
    ):
        _fail("TARGETED_M4_REPEAT_MISMATCH")
    return first, second


def inspect_target_result_m3(
    *,
    context: TargetedM4ExecutionContext,
    first_output: runtime.M4ExecutionOutput,
) -> tuple[
    tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]],
    tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]],
]:
    """Run exactly three result-M3 repeats and build their immutable records."""

    _validate_context(context)
    if first_output.case_id != context.replacement_case.get("case_id"):
        _fail("TARGETED_RESULT_BINDING_INVALID")
    adapter_fields: list[Mapping[str, object]] = []
    records: list[Mapping[str, object]] = []
    for repeat_index in (1, 2, 3):
        output = context.executor.inspect_result(
            output=first_output,
            case_entry=context.replacement_case,
            repeat_index=repeat_index,
        )
        fields = dict(output.fields)
        adapter_fields.append(fields)
        materialized = {
            **fields,
            "case_id": context.replacement_case["case_id"],
            "case_specification_digest": context.replacement_case["case_specification_digest"],
            "result_output_id": first_output.result_output_id,
            "result_sha256": first_output.result_sha256,
            "repeat_index": repeat_index,
            "runtime_manifest_digest": context.replacement_case["runtime_manifest_digest"],
        }
        try:
            records.append(r2.build_r2_result_m3_record(materialized))
        except (KeyError, TypeError, ValueError, r2.D02R2AuthorityError) as error:
            raise D02TargetedM4RepairExecutionError("TARGETED_RESULT_M3_RECORD_INVALID") from error
    return (
        cast(
            tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]],
            tuple(adapter_fields),
        ),
        cast(
            tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]],
            tuple(records),
        ),
    )


def adapter_fields_from_records(
    records: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    """Recover the three backend adapter fields without rerunning M3."""

    if len(records) != 3:
        _fail("TARGETED_RESULT_M3_CARDINALITY_INVALID")
    fields: list[Mapping[str, object]] = []
    for repeat_index, record in enumerate(records, start=1):
        if record.get("repeat_index") != repeat_index:
            _fail("TARGETED_RESULT_M3_RECORD_INVALID")
        try:
            replay = r2.build_r2_result_m3_record(
                {
                    key: value
                    for key, value in record.items()
                    if key not in {"schema_version", "result_m3_record_id", "record_digest"}
                }
            )
        except (KeyError, TypeError, ValueError, r2.D02R2AuthorityError) as error:
            raise D02TargetedM4RepairExecutionError("TARGETED_RESULT_M3_RECORD_INVALID") from error
        if dict(record) != replay:
            _fail("TARGETED_RESULT_M3_RECORD_INVALID")
        fields.append(
            {
                key: value
                for key, value in record.items()
                if key
                not in {
                    "schema_version",
                    "result_m3_record_id",
                    "record_digest",
                    "case_id",
                    "case_specification_digest",
                    "result_output_id",
                    "result_sha256",
                    "repeat_index",
                    "runtime_manifest_digest",
                }
            }
        )
    return cast(
        tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]],
        tuple(fields),
    )


def evaluate_target_measurement(
    *,
    predecessor_report: Mapping[str, object],
    predecessor: orchestrator.PreparedRuntimeEvidence,
    replacement_case: Mapping[str, object],
    result_m3_records: Sequence[Mapping[str, object]],
) -> TargetedMeasurementOutcome:
    """Evaluate only redacted measurement facts for calibration/formal gating."""

    if len(result_m3_records) != 3:
        _fail("TARGETED_RESULT_M3_CARDINALITY_INVALID")
    try:
        certificate = screening._result_certificate(result_m3_records)
        packet = predecessor.formal_bundle.runtime_packets[repair.TARGET_SOURCE_ORDINAL - 1]
        gate = MeasurementGateAdapter().evaluate(
            source_packet=packet,
            case_entry=replacement_case,
            result_m3_records=result_m3_records,
            result_repeat_certification=certificate,
        )
        measurements = cast(
            Sequence[Mapping[str, object]], gate["ordered_result_repeat_measurements"]
        )
        deltas = cast(
            tuple[int, int, int],
            tuple(cast(int, item["measured_signed_delta_ppm"]) for item in measurements),
        )
        peer = _predecessor_case_measurements(predecessor_report, case_ordinal=26)
        peer_absolute = cast(tuple[int, int, int], tuple(abs(value) for value in peer))
        evaluation = cast(Mapping[str, object], gate["gate_evaluation"])
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise D02TargetedM4RepairExecutionError(
            "TARGETED_MEASUREMENT_EVALUATION_INVALID"
        ) from error
    return TargetedMeasurementOutcome(
        measured_signed_delta_ppm=deltas,
        predecessor_case_26_absolute_delta_ppm=peer_absolute,
        repeat_consistent=(len(set(deltas)) == 1)
        and all(record.get("repeat_gate_passed") is True for record in result_m3_records),
        direction_and_margin_passed=all(value < -10 for value in deltas),
        predecessor_bound_passed=all(
            abs(value) <= bound for value, bound in zip(deltas, peer_absolute, strict=True)
        ),
        measurement_gate_passed=evaluation.get("measurement_gate_passed") is True,
    )


def validate_accurate_failure_report(report: Mapping[str, object]) -> None:
    """Require the frozen V1 failure shape before any targeted execution."""

    if (
        report.get("status") != "FAILED"
        or report.get("eligible_dimension_keys") != ["eye_spacing"]
        or report.get("selected_pair_count") != 0
        or report.get("selected_result_side_count") != 0
    ):
        _fail("ACCURATE_FAILURE_REPORT_INVALID")
    case_05 = _predecessor_case_measurements(report, case_ordinal=5)
    case_25 = _predecessor_case_measurements(report, case_ordinal=25)
    case_26 = _predecessor_case_measurements(report, case_ordinal=26)
    if not (
        all(value > 0 for value in case_05)
        and all(value > 0 for value in case_25)
        and all(value < -10 for value in case_26)
    ):
        _fail("ACCURATE_FAILURE_REPORT_INVALID")


def _predecessor_case_measurements(
    report: Mapping[str, object], *, case_ordinal: int
) -> tuple[int, int, int]:
    payload = report.get("report_payload")
    if not isinstance(payload, Mapping):
        _fail("PREDECESSOR_REPORT_INVALID")
    gates = payload.get("measurement_gate_evidence")
    cases = payload.get("ordered_case_manifest")
    if (
        not isinstance(gates, list)
        or len(gates) != 48
        or not isinstance(cases, list)
        or len(cases) != 48
        or case_ordinal not in {5, 25, 26}
    ):
        _fail("PREDECESSOR_REPORT_INVALID")
    case = cases[case_ordinal - 1]
    gate = gates[case_ordinal - 1]
    if (
        not isinstance(case, Mapping)
        or case.get("case_ordinal") != case_ordinal
        or not isinstance(gate, Mapping)
        or gate.get("case_id") != case.get("case_id")
    ):
        _fail("PREDECESSOR_REPORT_INVALID")
    measurements = gate.get("ordered_result_repeat_measurements")
    if not isinstance(measurements, list) or len(measurements) != 3:
        _fail("PREDECESSOR_REPORT_INVALID")
    values: list[int] = []
    for item in measurements:
        if not isinstance(item, Mapping):
            _fail("PREDECESSOR_REPORT_INVALID")
        value = item.get("measured_signed_delta_ppm")
        if type(value) is not int:
            _fail("PREDECESSOR_REPORT_INVALID")
        values.append(value)
    return cast(tuple[int, int, int], tuple(values))


def _mint_targeted_handles(
    *,
    manifest: runtime.SourceDescriptorManifest,
    recipe: runtime.DemoRuntimeRecipe,
    model_identity: runtime.DemoModelIdentity,
) -> tuple[runtime.M3RuntimeHandle, runtime.M3ModelHandle]:
    if (
        model_identity != runtime.build_default_model_identity()
        or model_identity.runtime_manifest_digest != recipe.runtime_manifest_digest
        or recipe.recipe_version != TARGETED_RUNTIME_RECIPE_VERSION
    ):
        _fail("TARGETED_HANDLE_INPUT_INVALID")
    ordered = cast(
        tuple[str, str, str, str], tuple(item.source_id for item in manifest.descriptors)
    )
    runtime_handle = runtime.M3RuntimeHandle(
        source_manifest_digest=manifest.manifest_digest,
        ordered_source_ids=ordered,
        recipe_version=recipe.recipe_version,
        recipe_digest=recipe.recipe_digest,
        runtime_manifest_digest=recipe.runtime_manifest_digest,
        model_identity_digest=model_identity.identity_digest,
    )
    model_handle = runtime.M3ModelHandle(
        source_manifest_digest=manifest.manifest_digest,
        ordered_source_ids=ordered,
        recipe_digest=recipe.recipe_digest,
        model_identity_digest=model_identity.identity_digest,
        model_config_digest=model_identity.config_digest,
        weights_digest_or_no_weights=model_identity.weights_digest_or_no_weights,
    )
    return runtime_handle, model_handle


def _validate_context(context: TargetedM4ExecutionContext) -> None:
    if (
        type(context) is not TargetedM4ExecutionContext
        or context.replacement_case.get("case_ordinal") != repair.TARGET_CASE_ORDINAL
        or context.replacement_case.get("source_ordinal") != repair.TARGET_SOURCE_ORDINAL
        or context.replacement_case.get("dimension_key") != repair.TARGET_SELECTOR["dimension_key"]
        or context.replacement_case.get("direction") != repair.TARGET_SELECTOR["direction"]
        or context.replacement_case.get("magnitude_ppm") != repair.TARGET_SELECTOR["magnitude_ppm"]
    ):
        _fail("TARGETED_EXECUTION_CONTEXT_INVALID")


def _fail(code: str) -> NoReturn:
    raise D02TargetedM4RepairExecutionError(code)
