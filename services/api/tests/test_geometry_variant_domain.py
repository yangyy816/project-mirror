from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from mirror_api.synthetic_dataset import (
    CanonicalPolicy,
    DeterminismLevel,
    DomainValidationError,
    GeometryDimension,
    GeometryDimensionClassification,
    GeometryOntology,
    PolicyKind,
    ReasonCode,
    TransformDirection,
    TransformRunState,
    VariantSpecification,
    require_researchable_dimension,
    transition_transform_run,
)


def _ontology() -> GeometryOntology:
    authority = CanonicalPolicy.create(
        kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
        version="geometry-ontology-v1",
        content={
            "dimensions": [
                "jaw_width",
                "nose_width",
                "eye_spacing",
                "profile_depth",
                "hair_texture",
            ]
        },
    )
    return GeometryOntology(
        authority=authority,
        dimensions=(
            GeometryDimension("jaw_width", GeometryDimensionClassification.READY),
            GeometryDimension("nose_width", GeometryDimensionClassification.READY),
            GeometryDimension(
                "eye_spacing",
                GeometryDimensionClassification.EXPERIMENTAL,
                (ReasonCode.FURTHER_RESEARCH,),
            ),
            GeometryDimension(
                "profile_depth",
                GeometryDimensionClassification.REQUIRES_3D,
                (ReasonCode.REQUIRES_3D_RESEARCH,),
            ),
            GeometryDimension(
                "hair_texture",
                GeometryDimensionClassification.STYLE_ONLY,
                (ReasonCode.STYLE_ONLY_DIMENSION,),
            ),
        ),
    )


def _specification(**overrides: object) -> VariantSpecification:
    values: dict[str, object] = {
        "ontology": _ontology(),
        "source_asset_reference": "asset-01",
        "source_identity_reference": "identity-01",
        "source_qa_run_reference": "qa-run-01",
        "target_dimension": "eye_spacing",
        "direction": TransformDirection.INCREASE,
        "relative_magnitude_ppm": 50_000,
        "control_dimensions": ("jaw_width",),
        "algorithm_version": "geometry-transform-v1",
        "runtime_manifest_digest": "a" * 64,
        "tolerance_policy_reference": "tolerance-policy-v1",
        "output_width": 1024,
        "output_height": 1024,
        "output_policy_version": "variant-output-v1",
        "determinism_level": DeterminismLevel.BIT_EXACT_SAME_PLATFORM,
    }
    values.update(overrides)
    return VariantSpecification.create(**values)  # type: ignore[arg-type]


def test_variant_specification_digest_is_deterministic_and_controls_are_canonical() -> None:
    first = _specification(control_dimensions=("nose_width", "jaw_width"))
    second = _specification(control_dimensions=("jaw_width", "nose_width"))

    assert first == second
    assert first.control_dimensions == ("jaw_width", "nose_width")
    assert len(first.content_digest) == 64


def test_experimental_and_ready_dimensions_are_researchable_without_ready_promotion() -> None:
    ontology = _ontology()

    assert require_researchable_dimension(ontology, "jaw_width").classification is (
        GeometryDimensionClassification.READY
    )
    assert require_researchable_dimension(ontology, "eye_spacing").classification is (
        GeometryDimensionClassification.EXPERIMENTAL
    )


@pytest.mark.parametrize(
    ("dimension", "reason"),
    [
        ("profile_depth", ReasonCode.REQUIRES_3D_RESEARCH),
        ("hair_texture", ReasonCode.STYLE_ONLY_DIMENSION),
        ("undeclared", ReasonCode.UNKNOWN_GEOMETRY_DIMENSION),
    ],
)
def test_non_researchable_dimensions_fail_closed(dimension: str, reason: ReasonCode) -> None:
    with pytest.raises(DomainValidationError) as error:
        _specification(target_dimension=dimension)
    assert error.value.reason_code is reason


@pytest.mark.parametrize("magnitude", [0, -1, 1_000_001, True])
def test_relative_magnitude_is_strictly_bounded(magnitude: object) -> None:
    with pytest.raises(DomainValidationError) as error:
        _specification(relative_magnitude_ppm=magnitude)
    assert error.value.reason_code is ReasonCode.INVALID_RELATIVE_MAGNITUDE


def test_control_dimensions_are_required_and_must_not_include_target() -> None:
    with pytest.raises(DomainValidationError) as missing:
        _specification(control_dimensions=())
    assert missing.value.reason_code is ReasonCode.CONTROL_DIMENSION_REQUIRED

    with pytest.raises(DomainValidationError) as conflict:
        _specification(control_dimensions=("eye_spacing",))
    assert conflict.value.reason_code is ReasonCode.TARGET_CONTROL_CONFLICT


def test_unknown_direction_and_determinism_claims_fail_closed() -> None:
    with pytest.raises(DomainValidationError) as direction:
        _specification(direction=cast(TransformDirection, "SIDEWAYS"))
    assert direction.value.reason_code is ReasonCode.INVALID_VARIANT_SPECIFICATION

    with pytest.raises(DomainValidationError) as determinism:
        _specification(determinism_level=cast(DeterminismLevel, "BEST_EFFORT"))
    assert determinism.value.reason_code is ReasonCode.INVALID_DETERMINISM_CLAIM


def test_direct_construction_rejects_digest_tampering_without_echoing_references() -> None:
    specification = _specification()
    marker = "private-asset-reference"

    with pytest.raises(DomainValidationError) as error:
        replace(
            specification,
            source_asset_reference=marker,
            content_digest="f" * 64,
        )
    assert error.value.reason_code is ReasonCode.INVALID_VARIANT_SPECIFICATION
    assert marker not in str(error.value)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TransformRunState.SPECIFIED, TransformRunState.RUNNING),
        (TransformRunState.SPECIFIED, TransformRunState.CANCELLED),
        (TransformRunState.RUNNING, TransformRunState.OUTPUT_STORED),
        (TransformRunState.RUNNING, TransformRunState.REJECTED),
        (TransformRunState.OUTPUT_STORED, TransformRunState.MEASURING),
        (TransformRunState.MEASURING, TransformRunState.COMPLETED),
    ],
)
def test_transform_run_accepts_only_monotonic_transitions(
    current: TransformRunState, target: TransformRunState
) -> None:
    assert transition_transform_run(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TransformRunState.SPECIFIED, TransformRunState.COMPLETED),
        (TransformRunState.OUTPUT_STORED, TransformRunState.COMPLETED),
        (TransformRunState.COMPLETED, TransformRunState.RUNNING),
        (TransformRunState.REJECTED, TransformRunState.RUNNING),
        (TransformRunState.FAILED, TransformRunState.SPECIFIED),
    ],
)
def test_transform_run_rejects_skips_and_terminal_reentry(
    current: TransformRunState, target: TransformRunState
) -> None:
    with pytest.raises(DomainValidationError) as error:
        transition_transform_run(current, target)
    assert error.value.reason_code is ReasonCode.INVALID_STATE_TRANSITION


@pytest.mark.parametrize(
    ("width", "height"),
    [(0, 1024), (1024, 0), (16_385, 1), (8_001, 8_000), (True, 1024)],
)
def test_output_shape_is_bounded(width: object, height: object) -> None:
    with pytest.raises(DomainValidationError) as error:
        _specification(output_width=width, output_height=height)
    assert error.value.reason_code is ReasonCode.INVALID_VARIANT_SPECIFICATION
