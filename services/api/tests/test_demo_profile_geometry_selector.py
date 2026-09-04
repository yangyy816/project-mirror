from __future__ import annotations

import pytest

from mirror_api.demo_profile_geometry_selector import (
    DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
    DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
    DemoProfileGeometryCase,
    DemoProfileGeometryDimension,
    DemoProfileGeometrySelectionError,
    DemoProfileGeometryStepUnavailable,
    profile_guided_step_policy_payload,
    select_profile_guided_geometry_step,
)


def _dimension(
    key: str,
    delta: int,
    **overrides: object,
) -> DemoProfileGeometryDimension:
    values: dict[str, object] = {
        "dimension_key": key,
        "desired_delta_ppm": delta,
        "confidence_ppm": 500_000,
        "restraint": "NONE",
        "geometry_prohibited": False,
        "d02_selected_dimension": True,
        "persistent_preserve_lock": False,
        "current_session_allow_change": False,
    }
    values.update(overrides)
    return DemoProfileGeometryDimension(**values)  # type: ignore[arg-type]


def _case(key: str, direction: str, magnitude: int, marker: str) -> DemoProfileGeometryCase:
    return DemoProfileGeometryCase(key, direction, magnitude, marker * 64)  # type: ignore[arg-type]


def test_fixed_policy_payload_has_frozen_digest_and_nearest_step_sign() -> None:
    selection = select_profile_guided_geometry_step(
        dimensions=(_dimension("jaw_width", -22_500),),
        cases=(
            _case("jaw_width", "DECREASE", 30_000, "b"),
            _case("jaw_width", "DECREASE", 15_000, "a"),
        ),
    )

    assert (
        profile_guided_step_policy_payload()["policy_version"]
        == DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION
    )
    assert selection.profile_desired_delta_ppm == -22_500
    assert selection.execution_delta_ppm == -15_000
    assert selection.selected_case_digest == "a" * 64
    assert selection.selection_policy_digest == DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (1, 15_000),
        (14_999, 15_000),
        (15_000, 15_000),
        (22_500, 15_000),
        (29_999, 30_000),
        (30_000, 30_000),
        (100_000, 30_000),
        (-1, -15_000),
        (-100_000, -30_000),
    ],
)
def test_nearest_fixed_step_boundary(delta: int, expected: int) -> None:
    direction = "INCREASE" if delta > 0 else "DECREASE"
    selection = select_profile_guided_geometry_step(
        dimensions=(_dimension("chin_height", delta),),
        cases=(
            _case("chin_height", direction, 15_000, "a"),
            _case("chin_height", direction, 30_000, "b"),
        ),
    )
    assert selection.execution_delta_ppm == expected


@pytest.mark.parametrize(
    "overrides",
    [
        {"desired_delta_ppm": 0},
        {"confidence_ppm": 0},
        {"restraint": "MAXIMUM"},
        {"geometry_prohibited": True},
        {"d02_selected_dimension": False},
        {"persistent_preserve_lock": True, "current_session_allow_change": False},
    ],
)
def test_ineligible_dimension_fails_closed(overrides: dict[str, object]) -> None:
    with pytest.raises(DemoProfileGeometryStepUnavailable) as raised:
        select_profile_guided_geometry_step(
            dimensions=(_dimension("jaw_width", 15_000, **overrides),),
            cases=(_case("jaw_width", "INCREASE", 15_000, "a"),),
        )
    assert raised.value.code == "DEMO_PROFILE_GEOMETRY_STEP_UNAVAILABLE"


def test_rank_is_profile_delta_then_dimension_and_case_duplicates_fail_closed() -> None:
    selected = select_profile_guided_geometry_step(
        dimensions=(
            _dimension("jaw_width", 15_000),
            _dimension("chin_height", -30_000),
        ),
        cases=(
            _case("jaw_width", "INCREASE", 15_000, "a"),
            _case("chin_height", "DECREASE", 30_000, "b"),
        ),
    )
    assert selected.dimension_key == "chin_height"

    with pytest.raises(DemoProfileGeometrySelectionError, match="ambiguous"):
        select_profile_guided_geometry_step(
            dimensions=(_dimension("jaw_width", 15_000),),
            cases=(
                _case("jaw_width", "INCREASE", 15_000, "a"),
                _case("jaw_width", "INCREASE", 15_000, "b"),
            ),
        )


def test_policy_mismatch_fails_closed() -> None:
    with pytest.raises(DemoProfileGeometrySelectionError, match="unsupported"):
        select_profile_guided_geometry_step(
            dimensions=(_dimension("jaw_width", 15_000),),
            cases=(_case("jaw_width", "INCREASE", 15_000, "a"),),
            policy_digest="f" * 64,
        )
