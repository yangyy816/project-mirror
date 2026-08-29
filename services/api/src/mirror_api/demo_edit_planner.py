"""Deterministic typed D07 planner with no persistence or runtime dependency."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final

from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
)

_DIMENSION = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_LOCK_MODES: Final = frozenset({"PRESERVE", "ALLOW_CHANGE"})
_PPM = 1_000_000


class DemoEditPlannerError(ValueError):
    """Fail-closed planner error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class TypedPlanInput:
    operation: OperationType
    value_ppm: int
    desired_delta_ppm: Mapping[str, int]
    persistent_locks: Mapping[str, str]
    session_override_locks: Mapping[str, str]
    prohibited_operations: Sequence[OperationType]


def plan_operation(value: TypedPlanInput) -> OperationSpec:
    """Produce one canonical operation or fail before any execution is possible."""

    if not isinstance(value, TypedPlanInput):
        raise DemoEditPlannerError("INVALID_INPUT", "planner input must be typed")
    _validate_input(value)
    if value.operation in value.prohibited_operations:
        raise DemoEditPlannerError("PROHIBITED_OPERATION", "operation is prohibited by constraints")
    if value.operation is OperationType.GEOMETRY:
        return _geometry_spec(value)
    if value.operation is OperationType.MAKEUP:
        return _unavailable_spec(OperationType.MAKEUP, "MAKEUP_DEFERRED_NO_APPROVED_ENGINE")
    if value.operation is OperationType.GENERATIVE:
        return _unavailable_spec(OperationType.GENERATIVE, "GENERATIVE_PROVIDER_UNAVAILABLE")
    if value.operation not in _RASTER_OPERATIONS:
        raise DemoEditPlannerError("UNSUPPORTED_OPERATION", "operation cannot be planned here")
    return _raster_spec(value.operation, value.value_ppm)


_RASTER_OPERATIONS: Final = frozenset(
    {
        OperationType.CROP,
        OperationType.ROTATE,
        OperationType.EXPOSURE,
        OperationType.CONTRAST,
        OperationType.SATURATION,
        OperationType.TEMPERATURE,
    }
)


def _validate_input(value: TypedPlanInput) -> None:
    if not isinstance(value.operation, OperationType) or type(value.value_ppm) is not int:
        raise DemoEditPlannerError("INVALID_INPUT", "operation and value_ppm are invalid")
    _validate_deltas(value.desired_delta_ppm)
    _validate_locks(value.persistent_locks, "persistent_locks")
    _validate_locks(value.session_override_locks, "session_override_locks")
    prohibited = tuple(value.prohibited_operations)
    if not all(isinstance(item, OperationType) for item in prohibited):
        raise DemoEditPlannerError("INVALID_PROHIBITED_OPERATIONS", "prohibited values are invalid")
    if len(set(prohibited)) != len(prohibited):
        raise DemoEditPlannerError(
            "INVALID_PROHIBITED_OPERATIONS", "prohibited operations duplicate"
        )
    if tuple(sorted(prohibited, key=lambda item: item.value)) != prohibited:
        raise DemoEditPlannerError(
            "INVALID_PROHIBITED_OPERATIONS", "prohibited operations are not canonical"
        )


def _validate_deltas(values: Mapping[str, int]) -> None:
    if not isinstance(values, Mapping):
        raise DemoEditPlannerError("INVALID_DESIRED_DELTA", "desired delta must be a mapping")
    for key, delta in values.items():
        if not isinstance(key, str) or _DIMENSION.fullmatch(key) is None:
            raise DemoEditPlannerError("INVALID_DESIRED_DELTA", "dimension key is invalid")
        if type(delta) is not int or not -100_000 <= delta <= 100_000:
            raise DemoEditPlannerError("INVALID_DESIRED_DELTA", "dimension delta is invalid")


def _validate_locks(locks: Mapping[str, str], name: str) -> None:
    if not isinstance(locks, Mapping):
        raise DemoEditPlannerError("INVALID_LOCKS", f"{name} must be a mapping")
    for key, mode in locks.items():
        if not isinstance(key, str) or _DIMENSION.fullmatch(key) is None:
            raise DemoEditPlannerError("INVALID_LOCKS", f"{name} dimension key is invalid")
        if mode not in _LOCK_MODES:
            raise DemoEditPlannerError("INVALID_LOCKS", f"{name} mode is invalid")


def _geometry_spec(value: TypedPlanInput) -> OperationSpec:
    delta = value.value_ppm
    if not -100_000 <= delta <= 100_000 or delta == 0:
        raise DemoEditPlannerError("INVALID_GEOMETRY_VALUE", "geometry value_ppm is out of range")
    candidates = [(key, item) for key, item in value.desired_delta_ppm.items() if item != 0]
    if not candidates:
        raise DemoEditPlannerError(
            "NO_ELIGIBLE_GEOMETRY_DIMENSION", "no desired-delta dimension is eligible"
        )
    dimension, _ = min(candidates, key=lambda item: (-abs(item[1]), item[0]))
    persistent = value.persistent_locks.get(dimension)
    override = value.session_override_locks.get(dimension)
    if persistent == "PRESERVE" and override != "ALLOW_CHANGE":
        raise DemoEditPlannerError(
            "LOCK_CONFLICT_REQUIRES_SESSION_OVERRIDE", "persistent feature lock blocks geometry"
        )
    parameters = {"dimension_key": dimension, "delta_ppm": delta}
    return OperationSpec(
        engine=OperationEngine.GEOMETRY,
        operation_type=OperationType.GEOMETRY,
        parameters=parameters,
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME, PreserveKey.NON_TARGET_GEOMETRY),
        expected_effect={
            "effect_type": "GEOMETRY",
            "target_region": "FACE_REGION",
            **parameters,
        },
    )


def _raster_spec(operation: OperationType, value_ppm: int) -> OperationSpec:
    parameters = _raster_parameters(operation, value_ppm)
    target = "CANVAS" if operation in {OperationType.CROP, OperationType.ROTATE} else "FULL_IMAGE"
    return OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=operation,
        parameters=parameters,
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME,),
        expected_effect={"effect_type": operation.value, "target_region": target, **parameters},
    )


def _raster_parameters(operation: OperationType, value_ppm: int) -> dict[str, int | bool]:
    if operation is OperationType.CROP:
        if not 1 <= value_ppm <= 250_000:
            raise DemoEditPlannerError("INVALID_CROP_VALUE", "crop value_ppm is out of range")
        inset = value_ppm // 4
        if inset == 0:
            raise DemoEditPlannerError("QUANTIZED_VALUE_ZERO", "crop value quantizes to zero")
        return {
            "left_inset_ppm": inset,
            "right_inset_ppm": inset,
            "top_inset_ppm": inset,
            "bottom_inset_ppm": inset,
        }
    mappings: Mapping[OperationType, tuple[str, int]] = {
        OperationType.ROTATE: ("angle_mdeg", 15_000),
        OperationType.EXPOSURE: ("exposure_ev_milli", 2_000),
        OperationType.CONTRAST: ("contrast_delta_ppm", 500_000),
        OperationType.SATURATION: ("saturation_delta_ppm", 1_000_000),
        OperationType.TEMPERATURE: ("temperature_delta_mired", 100),
    }
    name, maximum = mappings[operation]
    if not -_PPM <= value_ppm <= _PPM:
        raise DemoEditPlannerError("INVALID_RASTER_VALUE", "raster value_ppm is out of range")
    quantized = _half_even_ratio(value_ppm, maximum)
    if quantized == 0:
        raise DemoEditPlannerError("QUANTIZED_VALUE_ZERO", "raster value quantizes to zero")
    if operation is OperationType.ROTATE:
        return {"angle_mdeg": quantized, "expand_canvas": True}
    return {name: quantized}


def _half_even_ratio(value_ppm: int, maximum: int) -> int:
    return int(
        (Decimal(value_ppm) * Decimal(maximum) / Decimal(_PPM)).to_integral_value(ROUND_HALF_EVEN)
    )


def _unavailable_spec(operation: OperationType, reason_code: str) -> OperationSpec:
    state = (
        "DEFERRED_WITH_EXPLICIT_REASON"
        if operation is OperationType.MAKEUP
        else "CAPABILITY_UNAVAILABLE"
    )
    return OperationSpec(
        engine=OperationEngine.MAKEUP
        if operation is OperationType.MAKEUP
        else OperationEngine.GENERATIVE,
        operation_type=operation,
        parameters={"reason_code": reason_code},
        preserve=(),
        expected_effect={
            "capability_state": state,
            "effect_type": "UNAVAILABLE",
            "reason_code": reason_code,
            "target_region": "NONE",
        },
    )
