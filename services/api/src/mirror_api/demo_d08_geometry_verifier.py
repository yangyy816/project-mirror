"""Fresh, independent D08 Geometry M3 verification.

This module is intentionally an in-process verifier boundary.  The injected
executor is reconstructed by the D02 custodian; this code consumes only the
public durable descriptor plus the current command/materialization bytes.
It never discovers D02 handles, locators, checkpoints, prompts, or assets.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Final, cast

from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d08_geometry_adapter import (
    D08_VERIFIER_POLICY_VERSION,
    GeometryExecutionAuthority,
)
from mirror_api.demo_d08_geometry_runtime_adapter import (
    reconstruct_d08_executor,
    validate_d08_executors,
)
from mirror_api.demo_editing_service import ExecutionCommand, MaterializedObject
from mirror_api.demo_effect_verifier import (
    SUPPORTED_DIMENSIONS,
    VERIFIER_VERSION,
    EffectVerificationInput,
    EffectVerificationResult,
    EffectVerifierPolicy,
    verify_effect,
)

D08_GEOMETRY_METRICS_SCHEMA: Final = "mirror.demo/D08GeometryVerificationMetrics/v1"
D08_GEOMETRY_THRESHOLDS_SCHEMA: Final = "mirror.demo/D08GeometryVerificationThresholds/v1"
_REPEAT_COUNT: Final = 3
_TARGET_MIN_ABS_PPM: Final = 10
_TARGET_MAX_ABS_PPM: Final = 60_000
_MAX_CONTROL_DRIFT_PPM: Final = 20_000
_DIMENSIONS: Final = (
    "cheekbone_width",
    "chin_height",
    "eye_spacing",
    "jaw_width",
    "mouth_width",
    "nose_width",
)
_FIXED18 = re.compile(r"-?(?:0|[1-9][0-9]*)\.\d{18}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class _RepeatEvidence:
    repeat_index: int
    source_output_digest: str | None
    source_receipt_digest: str | None
    source_landmark_digest: str | None
    source_observation_digest: str | None
    result_output_digest: str | None
    result_receipt_digest: str | None
    result_landmark_digest: str | None
    result_observation_digest: str | None
    source_measurements_fixed18: tuple[str, ...]
    result_measurements_fixed18: tuple[str, ...]
    signed_target_delta_ppm: int
    control_dimensions: tuple[str, ...]
    control_drifts_ppm: tuple[int, ...]
    max_control_dimension_key: str | None
    max_control_drift_ppm: int | None
    direction_passed: bool
    target_minimum_passed: bool
    target_maximum_passed: bool
    control_drift_passed: bool
    observation_passed: bool

    @property
    def passed(self) -> bool:
        return (
            self.direction_passed
            and self.target_minimum_passed
            and self.target_maximum_passed
            and self.control_drift_passed
            and self.observation_passed
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "control_drift_passed": self.control_drift_passed,
            "control_dimensions": list(self.control_dimensions),
            "control_drifts_ppm": list(self.control_drifts_ppm),
            "direction_passed": self.direction_passed,
            "observation_passed": self.observation_passed,
            "repeat_index": self.repeat_index,
            "max_control_dimension_key": self.max_control_dimension_key,
            "max_control_drift_ppm": self.max_control_drift_ppm,
            "result_landmark_digest": self.result_landmark_digest,
            "result_measurements_fixed18": list(self.result_measurements_fixed18),
            "result_observation_digest": self.result_observation_digest,
            "result_output_digest": self.result_output_digest,
            "result_receipt_digest": self.result_receipt_digest,
            "signed_target_delta_ppm": self.signed_target_delta_ppm,
            "source_landmark_digest": self.source_landmark_digest,
            "source_measurements_fixed18": list(self.source_measurements_fixed18),
            "source_observation_digest": self.source_observation_digest,
            "source_output_digest": self.source_output_digest,
            "source_receipt_digest": self.source_receipt_digest,
            "target_maximum_passed": self.target_maximum_passed,
            "target_minimum_passed": self.target_minimum_passed,
        }


class IndependentGeometryVerifier:
    """An async ``EditVerifier`` compatible callable for D08 Geometry only."""

    def __init__(self, executor: runtime.DemoM3M4Executor) -> None:
        try:
            self._executor = reconstruct_d08_executor(executor)
        except Exception as error:
            raise TypeError("executor does not replay accepted runtime authority") from error

    async def __call__(
        self, command: ExecutionCommand, materialized: MaterializedObject
    ) -> EffectVerificationResult:
        authority = command.geometry_authority
        attempt = materialized.geometry_attempt_evidence
        core = materialized.geometry_stable_core
        if authority is None or attempt is None or core is None:
            return self._failed_without_measurements(command, materialized, ())
        if not self._authority_matches_executor(authority):
            return self._failed_without_measurements(command, materialized, ())
        descriptor = self._descriptor_for(
            authority.root_source_asset_id, authority.root_source_asset_sha256
        )
        if descriptor is None:
            return self._failed_without_measurements(command, materialized, ())
        try:
            source = runtime.SourceMaterial(descriptor=descriptor, content=command.source_bytes)
            output = self._fresh_result_output(authority, materialized)
            case_entry = self._case_entry(authority, descriptor)
        except (ValueError, runtime.RuntimeForwardError):
            return self._failed_without_measurements(command, materialized, ())

        repeats: list[_RepeatEvidence] = []
        for repeat_index in range(1, _REPEAT_COUNT + 1):
            try:
                source_output, result_output = await asyncio.to_thread(
                    self._observe_repeat,
                    source,
                    output,
                    case_entry,
                    repeat_index,
                )
                repeats.append(
                    _failed_repeat(repeat_index, source=source_output, result=result_output)
                    if source_output is None or result_output is None
                    else self._repeat_evidence(
                        repeat_index,
                        source_output,
                        result_output,
                        authority.dimension_key,
                        authority.direction.value,
                    )
                )
            except (ValueError, runtime.RuntimeForwardError, measurement.MeasurementQualityError):
                repeats.append(_failed_repeat(repeat_index))
        return self._result(command, materialized, tuple(repeats))

    def _authority_matches_executor(self, authority: GeometryExecutionAuthority) -> bool:
        recipe = self._executor.recipe
        model = self._executor.model_identity
        expected_model = runtime.build_default_model_identity()
        return (
            recipe.m3_algorithm_version == runtime.M3_ALGORITHM_VERSION
            and recipe.m4_algorithm_version == authority.fixed_case.backend_algorithm_version
            and recipe.runtime_manifest_digest
            == authority.fixed_case.backend_runtime_manifest_digest
            and recipe.runtime_manifest_digest == measurement.RUNTIME_MANIFEST_DIGEST
            and recipe.topology_digest == measurement.TOPOLOGY_DIGEST
            and recipe.measurement_config_digest == measurement.MEASUREMENT_CONFIG_DIGEST
            and recipe.network_policy == runtime.NETWORK_POLICY
            and model == expected_model
        )

    def _descriptor_for(
        self, source_id: str, source_sha256: str
    ) -> runtime.DurableSourceDescriptor | None:
        matches = tuple(
            descriptor
            for descriptor in self._executor.manifest.descriptors
            if descriptor.source_id == source_id and descriptor.content_sha256 == source_sha256
        )
        return matches[0] if len(matches) == 1 else None

    def _fresh_result_output(
        self, authority: GeometryExecutionAuthority, materialized: MaterializedObject
    ) -> runtime.M4ExecutionOutput:
        fixed_case = authority.fixed_case
        evidence = materialized.geometry_attempt_evidence
        core = materialized.geometry_stable_core
        if evidence is None or core is None:
            raise ValueError("fresh result requires typed geometry evidence")
        payload: dict[str, measurement.JsonValue] = {
            "schema_version": runtime.M4_EXECUTION_OUTPUT_SCHEMA,
            "case_id": fixed_case.case_id,
            "replay_index": 1,
            "result_output_id": f"m4-{fixed_case.case_id}",
            "result_sha256": materialized.sha256,
            "result_byte_size": len(materialized.content),
            "result_mime_type": materialized.mime_type,
            "result_width": materialized.width,
            "result_height": materialized.height,
            "changed_pixel_count": core.changed_pixel_count,
            "execution_receipt_digest": evidence.backend_execution_receipt,
            "execution_succeeded": True,
        }
        return runtime.M4ExecutionOutput(
            case_id=fixed_case.case_id,
            replay_index=1,
            result_output_id=f"m4-{fixed_case.case_id}",
            content=materialized.content,
            result_sha256=materialized.sha256,
            result_byte_size=len(materialized.content),
            result_width=materialized.width,
            result_height=materialized.height,
            changed_pixel_count=core.changed_pixel_count,
            execution_receipt_digest=evidence.backend_execution_receipt,
            output_digest=measurement.mirror_demo_digest(
                runtime.M4_EXECUTION_OUTPUT_SCHEMA, payload
            ),
            result_mime_type=materialized.mime_type,
        )

    @staticmethod
    def _case_entry(
        authority: GeometryExecutionAuthority, descriptor: runtime.DurableSourceDescriptor
    ) -> dict[str, object]:
        fixed = authority.fixed_case
        return {
            "case_id": fixed.case_id,
            "case_ordinal": fixed.case_ordinal,
            "case_specification_digest": fixed.case_specification_digest,
            "source_asset_id": descriptor.source_id,
            "source_asset_sha256": descriptor.content_sha256,
            "source_ordinal": descriptor.ordinal,
            "dimension_key": fixed.dimension_key,
            "direction": fixed.direction.value,
            "magnitude_ppm": fixed.magnitude_ppm,
            "runtime_manifest_digest": fixed.backend_runtime_manifest_digest,
            "geometry_algorithm_version": fixed.backend_algorithm_version,
            "output_width": fixed.output_width,
            "output_height": fixed.output_height,
        }

    def _observe_repeat(
        self,
        source: runtime.SourceMaterial,
        output: runtime.M4ExecutionOutput,
        case_entry: Mapping[str, object],
        repeat_index: int,
    ) -> tuple[runtime.M3ExecutionOutput | None, runtime.M3ExecutionOutput | None]:
        try:
            source_output = self._executor.inspect_source(
                material=source, repeat_index=repeat_index
            )
        except (ValueError, runtime.RuntimeForwardError):
            source_output = None
        try:
            result_output = self._executor.inspect_result(
                output=output, case_entry=case_entry, repeat_index=repeat_index
            )
        except (ValueError, runtime.RuntimeForwardError):
            result_output = None
        return source_output, result_output

    def _repeat_evidence(
        self,
        repeat_index: int,
        source: runtime.M3ExecutionOutput,
        result: runtime.M3ExecutionOutput,
        target_dimension: str,
        direction: str,
    ) -> _RepeatEvidence:
        source_values = _ordered_measurements(source, expected_result=False)
        result_values = _ordered_measurements(result, expected_result=True)
        source_ok = _m3_gate(source, self._executor, expected_result=False)
        result_ok = _m3_gate(result, self._executor, expected_result=True)
        target_index = (
            _DIMENSIONS.index(target_dimension) if target_dimension in _DIMENSIONS else -1
        )
        if target_index < 0 or source_values is None or result_values is None:
            return _failed_repeat(repeat_index, source=source, result=result)
        deltas = tuple(
            _signed_ppm(before, after)
            for before, after in zip(source_values, result_values, strict=True)
        )
        target = deltas[target_index]
        control_dimensions = tuple(
            dimension for index, dimension in enumerate(_DIMENSIONS) if index != target_index
        )
        controls = tuple(abs(value) for index, value in enumerate(deltas) if index != target_index)
        maximum = max(controls)
        maximum_index = controls.index(maximum)
        direction_ok = (direction == "INCREASE" and target > 0) or (
            direction == "DECREASE" and target < 0
        )
        return _RepeatEvidence(
            repeat_index=repeat_index,
            source_output_digest=source.output_digest,
            source_receipt_digest=cast(str, source.fields["execution_receipt_digest"]),
            source_landmark_digest=cast(str, source.fields["landmark_digest"]),
            source_observation_digest=cast(str, source.fields["measurement_observation_digest"]),
            result_output_digest=result.output_digest,
            result_receipt_digest=cast(str, result.fields["execution_receipt_digest"]),
            result_landmark_digest=cast(str, result.fields["landmark_digest"]),
            result_observation_digest=cast(str, result.fields["measurement_observation_digest"]),
            source_measurements_fixed18=tuple(
                measurement.fixed18(value) for value in source_values
            ),
            result_measurements_fixed18=tuple(
                measurement.fixed18(value) for value in result_values
            ),
            signed_target_delta_ppm=target,
            control_dimensions=control_dimensions,
            control_drifts_ppm=controls,
            max_control_dimension_key=control_dimensions[maximum_index],
            max_control_drift_ppm=maximum,
            direction_passed=direction_ok,
            target_minimum_passed=abs(target) >= _TARGET_MIN_ABS_PPM,
            target_maximum_passed=abs(target) <= _TARGET_MAX_ABS_PPM,
            control_drift_passed=maximum <= _MAX_CONTROL_DRIFT_PPM,
            observation_passed=source_ok and result_ok,
        )

    def _result(
        self,
        command: ExecutionCommand,
        materialized: MaterializedObject,
        repeats: tuple[_RepeatEvidence, ...],
    ) -> EffectVerificationResult:
        authority = command.geometry_authority
        if authority is None:
            raise ValueError("geometry authority is required")
        target_dimension = authority.dimension_key
        target_values = tuple(item.signed_target_delta_ppm for item in repeats)
        control_values = tuple(value for item in repeats for value in item.control_drifts_ppm)
        max_control = max(
            (abs(value) for value in control_values), default=_MAX_CONTROL_DRIFT_PPM + 1
        )
        source_result_distinct = authority.root_source_asset_sha256 != materialized.sha256
        repeat_group = _repeat_group_validation(repeats)
        all_repeats_pass = (
            len(repeats) == _REPEAT_COUNT
            and all(item.passed for item in repeats)
            and all(repeat_group.values())
            and source_result_distinct
        )
        requested = command.operation.parameters.get("delta_ppm")
        measured = target_values[0] if target_values else 0
        control_dimensions = tuple(
            key for key in _DIMENSIONS if key != target_dimension and key in SUPPORTED_DIMENSIONS
        )
        structural = {key: _MAX_CONTROL_DRIFT_PPM for key in control_dimensions}
        observed_controls = {
            key: max(
                (
                    abs(item.control_drifts_ppm[_control_index(target_dimension, key)])
                    for item in repeats
                    if len(item.control_drifts_ppm) == 5
                ),
                default=_MAX_CONTROL_DRIFT_PPM + 1,
            )
            for key in control_dimensions
        }
        facts = EffectVerificationInput(
            source_asset_id=authority.input_asset_id,
            result_asset_id=_result_asset_id(command, materialized),
            target_dimension_key=target_dimension,
            operation_digest=authority.operation_authority_digest,
            requested_delta_ppm=requested,
            measured_delta_ppm=measured,
            structural_drifts_ppm=observed_controls,
            locked_drifts_ppm={},
            non_target_drift_ppm=max_control,
            artifact_status="PASS" if all_repeats_pass else "FAIL",
            artifact_codes=() if all_repeats_pass else ("FRESH_M3_REPEAT_GATE_FAILED",),
            original_before_sha256=authority.root_source_asset_sha256,
            original_after_sha256=hashlib.sha256(command.source_bytes).hexdigest(),
            result_bytes=materialized.content,
            declared_result_sha256=materialized.sha256,
            decode_valid=materialized.mime_type == "image/jpeg"
            and materialized.width > 0
            and materialized.height > 0,
            width=materialized.width,
            height=materialized.height,
            media_type=materialized.mime_type,
        )
        policy = EffectVerifierPolicy(
            structural_drift_thresholds_ppm=structural,
            locked_drift_thresholds_ppm={},
            target_tolerance_ppm=_TARGET_MAX_ABS_PPM,
            non_target_drift_threshold_ppm=_MAX_CONTROL_DRIFT_PPM,
            allowed_media_types=("image/jpeg",),
            verifier_version=VERIFIER_VERSION,
        )
        base = verify_effect(policy, facts)
        metrics = self._metrics(command, materialized, repeats)
        thresholds = {
            "schema_version": D08_GEOMETRY_THRESHOLDS_SCHEMA,
            "policy_digest": base.policy_digest,
            "repeat_count": _REPEAT_COUNT,
            "target_min_abs_ppm": _TARGET_MIN_ABS_PPM,
            "target_max_abs_ppm": _TARGET_MAX_ABS_PPM,
            "max_control_drift_ppm": _MAX_CONTROL_DRIFT_PPM,
            "d08_verifier_policy_version": D08_VERIFIER_POLICY_VERSION,
        }
        return EffectVerificationResult(
            categories=base.categories,
            policy_digest=base.policy_digest,
            request_digest=base.request_digest,
            result_digest=base.result_digest,
            status=base.status,
            publishable=base.publishable,
            authority_metrics=metrics,
            authority_thresholds=thresholds,
        )

    def _metrics(
        self,
        command: ExecutionCommand,
        materialized: MaterializedObject,
        repeats: Sequence[_RepeatEvidence],
    ) -> dict[str, object]:
        authority = command.geometry_authority
        attempt = materialized.geometry_attempt_evidence
        core = materialized.geometry_stable_core
        if authority is None or attempt is None or core is None:
            raise ValueError("geometry evidence is required")
        repeat_group = _repeat_group_validation(repeats)
        controls = tuple(
            (repeat.repeat_index, dimension, drift)
            for repeat in repeats
            for dimension, drift in zip(
                repeat.control_dimensions, repeat.control_drifts_ppm, strict=True
            )
        )
        maximum_control = max(controls, key=lambda item: item[2]) if controls else None
        source_digest_after = hashlib.sha256(command.source_bytes).hexdigest()
        return {
            "schema_version": D08_GEOMETRY_METRICS_SCHEMA,
            "authority_digest": authority.authority_digest,
            "stable_core_digest": core.stable_core_digest,
            "attempt_receipt_digest": attempt.attempt_receipt_digest,
            "operation_id": authority.operation_id,
            "operation_authority_digest": authority.operation_authority_digest,
            "operation_spec_digest": authority.operation_spec_digest,
            "case_id": authority.fixed_case.case_id,
            "case_ordinal": authority.fixed_case.case_ordinal,
            "source_ordinal": authority.fixed_case.source_ordinal,
            "source_asset_id": authority.root_source_asset_id,
            "result_sha256": materialized.sha256,
            "source_sha256": authority.root_source_asset_sha256,
            "dimension_key": authority.dimension_key,
            "direction": authority.direction.value,
            "magnitude_ppm": authority.magnitude_ppm,
            "source_result_digest_distinct": authority.root_source_asset_sha256
            != materialized.sha256,
            "source_digest_after_verification": source_digest_after,
            "original_immutability_passed": source_digest_after
            == authority.root_source_asset_sha256,
            "decode_passed": materialized.mime_type == "image/jpeg"
            and materialized.width > 0
            and materialized.height > 0,
            "artifact_passed": core.changed_pixel_count > 0,
            "runtime_identity": {
                "recipe_digest": self._executor.recipe.recipe_digest,
                "runtime_manifest_digest": self._executor.recipe.runtime_manifest_digest,
                "m3_algorithm_version": self._executor.recipe.m3_algorithm_version,
                "m4_algorithm_version": self._executor.recipe.m4_algorithm_version,
                "model_identity_digest": self._executor.model_identity.identity_digest,
                "model_config_digest": self._executor.model_identity.config_digest,
                "weights_digest_or_no_weights": (
                    self._executor.model_identity.weights_digest_or_no_weights
                ),
                "topology_digest": self._executor.recipe.topology_digest,
                "measurement_config_digest": self._executor.recipe.measurement_config_digest,
                "network_policy": self._executor.recipe.network_policy,
            },
            "d08_verifier_policy_version": D08_VERIFIER_POLICY_VERSION,
            "measurement_dimension_order": list(_DIMENSIONS),
            "repeats": [item.canonical_payload() for item in repeats],
            "repeat_gate_passed": len(repeats) == _REPEAT_COUNT
            and all(item.passed for item in repeats)
            and all(repeat_group.values()),
            "repeat_group_validation": repeat_group,
            "max_non_target_drift_ppm": (None if maximum_control is None else maximum_control[2]),
            "max_non_target_dimension_key": (
                None if maximum_control is None else maximum_control[1]
            ),
            "max_non_target_repeat_index": (
                None if maximum_control is None else maximum_control[0]
            ),
        }

    def _failed_without_measurements(
        self,
        command: ExecutionCommand,
        materialized: MaterializedObject,
        repeats: Sequence[_RepeatEvidence],
    ) -> EffectVerificationResult:
        return self._result(command, materialized, tuple(repeats))


class IndependentGeometryVerifierRouter:
    """Route fresh M3 verification by the exact admitted per-case algorithm."""

    def __init__(
        self,
        executor: runtime.DemoM3M4Executor,
        additional_executors: Sequence[runtime.DemoM3M4Executor] = (),
    ) -> None:
        executors = validate_d08_executors(executor, additional_executors)
        self._verifiers = {
            (item.recipe.m4_algorithm_version, item.recipe.runtime_manifest_digest): (
                IndependentGeometryVerifier(item)
            )
            for item in executors.values()
        }
        self._fallback = self._verifiers[
            (executor.recipe.m4_algorithm_version, executor.recipe.runtime_manifest_digest)
        ]

    async def __call__(
        self, command: ExecutionCommand, materialized: MaterializedObject
    ) -> EffectVerificationResult:
        authority = command.geometry_authority
        if authority is None:
            return await self._fallback(command, materialized)
        case = authority.fixed_case
        verifier = self._verifiers.get(
            (case.backend_algorithm_version, case.backend_runtime_manifest_digest)
        )
        return await (self._fallback if verifier is None else verifier)(command, materialized)


def _m3_gate(
    output: runtime.M3ExecutionOutput, executor: runtime.DemoM3M4Executor, *, expected_result: bool
) -> bool:
    fields = output.fields
    if (
        fields.get("face_count") != 1
        or fields.get("landmark_count") != 478
        or fields.get("coordinates_finite") is not True
        or fields.get("coordinates_in_bounds") is not True
        or fields.get("repeat_gate_passed") is not True
        or fields.get("topology_digest") != executor.recipe.topology_digest
        or fields.get("vision_model_manifest_digest")
        != executor.model_identity.weights_digest_or_no_weights
    ):
        return False
    if expected_result and fields.get("observation_state") != "SUPPORTED":
        return False
    observation = fields.get("measurement_observation")
    return isinstance(observation, Mapping) and (
        observation.get("runtime_manifest_digest") == executor.recipe.runtime_manifest_digest
        and observation.get("measurement_config_digest")
        == executor.recipe.measurement_config_digest
        and observation.get("topology_digest") == executor.recipe.topology_digest
    )


def _ordered_measurements(
    output: runtime.M3ExecutionOutput, *, expected_result: bool
) -> tuple[Decimal, ...] | None:
    observation = output.fields.get("measurement_observation")
    if not isinstance(observation, Mapping):
        return None
    entries = observation.get("ordered_measurements")
    if not isinstance(entries, list) or len(entries) != len(_DIMENSIONS):
        return None
    values: list[Decimal] = []
    for expected, entry in zip(_DIMENSIONS, entries, strict=True):
        if not isinstance(entry, Mapping) or entry.get("dimension_key") != expected:
            return None
        raw = entry.get("raw_value_fixed18")
        if entry.get("support_state") != "SUPPORTED" or not isinstance(raw, str):
            return None
        value = _fixed18_decimal(raw)
        if value is None or value <= 0:
            return None
        values.append(value)
    if expected_result and output.fields.get("observation_state") != "SUPPORTED":
        return None
    return tuple(values)


def _fixed18_decimal(value: str) -> Decimal | None:
    if _FIXED18.fullmatch(value) is None:
        return None
    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        return None
    return decimal_value if decimal_value.is_finite() else None


def _signed_ppm(source: Decimal, result: Decimal) -> int:
    if source <= 0 or result <= 0:
        raise measurement.MeasurementQualityError("measurements must be positive")
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        ppm = ((result - source) * Decimal(1_000_000)).to_integral_value(rounding=ROUND_HALF_EVEN)
    return int(ppm)


def _repeat_group_validation(repeats: Sequence[_RepeatEvidence]) -> dict[str, bool]:
    indexes = tuple(item.repeat_index for item in repeats)
    source_receipts = tuple(item.source_receipt_digest for item in repeats)
    result_receipts = tuple(item.result_receipt_digest for item in repeats)
    source_outputs = tuple(item.source_output_digest for item in repeats)
    result_outputs = tuple(item.result_output_digest for item in repeats)
    source_landmarks = tuple(item.source_landmark_digest for item in repeats)
    result_landmarks = tuple(item.result_landmark_digest for item in repeats)
    return {
        "repeat_indexes_complete": indexes == (1, 2, 3),
        "source_receipts_fresh": None not in source_receipts
        and len(set(source_receipts)) == _REPEAT_COUNT,
        "result_receipts_fresh": None not in result_receipts
        and len(set(result_receipts)) == _REPEAT_COUNT,
        "source_outputs_fresh": None not in source_outputs
        and len(set(source_outputs)) == _REPEAT_COUNT,
        "result_outputs_fresh": None not in result_outputs
        and len(set(result_outputs)) == _REPEAT_COUNT,
        "source_landmarks_stable": None not in source_landmarks and len(set(source_landmarks)) == 1,
        "result_landmarks_stable": None not in result_landmarks and len(set(result_landmarks)) == 1,
    }


def _failed_repeat(
    repeat_index: int,
    *,
    source: runtime.M3ExecutionOutput | None = None,
    result: runtime.M3ExecutionOutput | None = None,
) -> _RepeatEvidence:
    return _RepeatEvidence(
        repeat_index=repeat_index,
        source_output_digest=source.output_digest if source is not None else None,
        source_receipt_digest=_field_digest(source, "execution_receipt_digest"),
        source_landmark_digest=_field_digest(source, "landmark_digest"),
        source_observation_digest=_field_digest(source, "measurement_observation_digest"),
        result_output_digest=result.output_digest if result is not None else None,
        result_receipt_digest=_field_digest(result, "execution_receipt_digest"),
        result_landmark_digest=_field_digest(result, "landmark_digest"),
        result_observation_digest=_field_digest(result, "measurement_observation_digest"),
        source_measurements_fixed18=(),
        result_measurements_fixed18=(),
        signed_target_delta_ppm=0,
        control_dimensions=(),
        control_drifts_ppm=(),
        max_control_dimension_key=None,
        max_control_drift_ppm=None,
        direction_passed=False,
        target_minimum_passed=False,
        target_maximum_passed=False,
        control_drift_passed=False,
        observation_passed=False,
    )


def _field_digest(output: runtime.M3ExecutionOutput | None, key: str) -> str | None:
    if output is None:
        return None
    value = output.fields.get(key)
    return value if isinstance(value, str) and _DIGEST.fullmatch(value) else None


def _result_asset_id(command: ExecutionCommand, materialized: MaterializedObject) -> str:
    """Derive a public temporary result ID; no storage identifier is consulted."""

    return hashlib.sha256(
        f"{command.operation_id}:{materialized.sha256}".encode("ascii")
    ).hexdigest()[:32]


def _control_index(target_dimension: str, dimension_key: str) -> int:
    return tuple(key for key in _DIMENSIONS if key != target_dimension).index(dimension_key)
