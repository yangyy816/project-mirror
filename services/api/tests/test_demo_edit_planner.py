from __future__ import annotations

import pytest

from mirror_api.demo_edit_planner import DemoEditPlannerError, TypedPlanInput, plan_operation
from mirror_api.demo_operation_graph import OperationType


def _input(
    operation: OperationType,
    value_ppm: int,
    *,
    desired: dict[str, int] | None = None,
    persistent: dict[str, str] | None = None,
    overrides: dict[str, str] | None = None,
    prohibited: tuple[OperationType, ...] = (),
) -> TypedPlanInput:
    return TypedPlanInput(
        operation=operation,
        value_ppm=value_ppm,
        desired_delta_ppm=desired or {"jaw_width": 10},
        persistent_locks=persistent or {},
        session_override_locks=overrides or {},
        prohibited_operations=prohibited,
    )


@pytest.mark.parametrize(
    ("operation", "value_ppm", "parameters"),
    [
        (
            OperationType.CROP,
            8,
            {
                "left_inset_ppm": 2,
                "right_inset_ppm": 2,
                "top_inset_ppm": 2,
                "bottom_inset_ppm": 2,
            },
        ),
        (OperationType.ROTATE, 1_000_000, {"angle_mdeg": 15_000, "expand_canvas": True}),
        (OperationType.EXPOSURE, 1_000_000, {"exposure_ev_milli": 2_000}),
        (OperationType.CONTRAST, -1_000_000, {"contrast_delta_ppm": -500_000}),
        (OperationType.SATURATION, 1_000_000, {"saturation_delta_ppm": 1_000_000}),
        (OperationType.TEMPERATURE, -1_000_000, {"temperature_delta_mired": -100}),
    ],
)
def test_all_deterministic_raster_tools_map_to_canonical_operation_specs(
    operation: OperationType, value_ppm: int, parameters: dict[str, int | bool]
) -> None:
    spec = plan_operation(_input(operation, value_ppm))
    assert spec.operation_type is operation
    assert dict(spec.parameters) == parameters


@pytest.mark.parametrize(
    ("operation", "value_ppm", "code"),
    [
        (OperationType.CROP, 3, "QUANTIZED_VALUE_ZERO"),
        (OperationType.ROTATE, 1, "QUANTIZED_VALUE_ZERO"),
        (OperationType.EXPOSURE, 0, "QUANTIZED_VALUE_ZERO"),
        (OperationType.CONTRAST, 1_000_001, "INVALID_RASTER_VALUE"),
        (OperationType.SATURATION, 0, "QUANTIZED_VALUE_ZERO"),
        (OperationType.TEMPERATURE, 1, "QUANTIZED_VALUE_ZERO"),
    ],
)
def test_raster_zero_or_out_of_range_requests_fail_closed(
    operation: OperationType, value_ppm: int, code: str
) -> None:
    with pytest.raises(DemoEditPlannerError) as error:
        plan_operation(_input(operation, value_ppm))
    assert error.value.code == code


def test_geometry_chooses_highest_absolute_profile_delta_with_dimension_tie_break() -> None:
    spec = plan_operation(
        _input(
            OperationType.GEOMETRY,
            -10_000,
            desired={"jaw_width": 40, "eye_spacing": -40, "chin_height": 20},
        )
    )
    assert dict(spec.parameters) == {"dimension_key": "eye_spacing", "delta_ppm": -10_000}


def test_geometry_current_instruction_controls_delta_not_profile_delta() -> None:
    spec = plan_operation(_input(OperationType.GEOMETRY, 8_000, desired={"jaw_width": -90_000}))
    assert dict(spec.parameters) == {"dimension_key": "jaw_width", "delta_ppm": 8_000}


def test_geometry_lock_requires_session_override_without_changing_persistent_lock() -> None:
    value = _input(
        OperationType.GEOMETRY,
        10_000,
        persistent={"jaw_width": "PRESERVE"},
        desired={"jaw_width": 20},
    )
    with pytest.raises(DemoEditPlannerError) as error:
        plan_operation(value)
    assert error.value.code == "LOCK_CONFLICT_REQUIRES_SESSION_OVERRIDE"

    spec = plan_operation(
        _input(
            OperationType.GEOMETRY,
            10_000,
            persistent={"jaw_width": "PRESERVE"},
            overrides={"jaw_width": "ALLOW_CHANGE"},
            desired={"jaw_width": 20},
        )
    )
    assert dict(spec.parameters)["dimension_key"] == "jaw_width"


def test_geometry_without_nonzero_profile_candidate_or_valid_instruction_fails_closed() -> None:
    for value, code in [
        (0, "INVALID_GEOMETRY_VALUE"),
        (100_001, "INVALID_GEOMETRY_VALUE"),
    ]:
        with pytest.raises(DemoEditPlannerError) as error:
            plan_operation(_input(OperationType.GEOMETRY, value))
        assert error.value.code == code
    with pytest.raises(DemoEditPlannerError) as error:
        plan_operation(_input(OperationType.GEOMETRY, 1, desired={"jaw_width": 0}))
    assert error.value.code == "NO_ELIGIBLE_GEOMETRY_DIMENSION"


def test_prohibited_operation_fails_before_capability_or_execution_output() -> None:
    with pytest.raises(DemoEditPlannerError) as error:
        plan_operation(
            _input(
                OperationType.GENERATIVE,
                0,
                prohibited=(OperationType.GENERATIVE,),
            )
        )
    assert error.value.code == "PROHIBITED_OPERATION"


@pytest.mark.parametrize(
    ("operation", "state", "reason"),
    [
        (
            OperationType.MAKEUP,
            "DEFERRED_WITH_EXPLICIT_REASON",
            "MAKEUP_DEFERRED_NO_APPROVED_ENGINE",
        ),
        (
            OperationType.GENERATIVE,
            "CAPABILITY_UNAVAILABLE",
            "GENERATIVE_PROVIDER_UNAVAILABLE",
        ),
    ],
)
def test_unavailable_operations_remain_explicit_in_the_plan(
    operation: OperationType, state: str, reason: str
) -> None:
    spec = plan_operation(_input(operation, 0))
    assert dict(spec.expected_effect)["capability_state"] == state
    assert dict(spec.parameters)["reason_code"] == reason


def test_rejects_raw_float_and_noncanonical_prohibited_order_and_replays_deterministically() -> (
    None
):
    with pytest.raises(DemoEditPlannerError) as error:
        plan_operation(_input(OperationType.EXPOSURE, 1.0))  # type: ignore[arg-type]
    assert error.value.code == "INVALID_INPUT"
    with pytest.raises(DemoEditPlannerError) as error:
        plan_operation(
            _input(
                OperationType.CROP,
                8,
                prohibited=(OperationType.ROTATE, OperationType.CROP),
            )
        )
    assert error.value.code == "INVALID_PROHIBITED_OPERATIONS"
    request = _input(OperationType.GEOMETRY, 5_000, desired={"eye_spacing": 10})
    assert (
        plan_operation(request).canonical_payload() == plan_operation(request).canonical_payload()
    )
