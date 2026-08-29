from __future__ import annotations

import pytest

from mirror_api.demo_face_runtime import (
    INTEGRATION_STATUS,
    RUNTIME_READINESS,
    DimensionObservation,
    FaceObservation,
    FaceRuntimeError,
    compile_baseline_face_model,
    compile_face_runtime,
    derive_self_state,
)


def _observation(
    repeat_index: int,
    *,
    face_width: int | None = 500_000,
    observability: int = 900_000,
    unsupported: bool = False,
    include_height: bool = True,
) -> FaceObservation:
    dimensions = [
        DimensionObservation(
            dimension="face_width",
            support_state="UNSUPPORTED" if unsupported else "SUPPORTED",
            value_ppm=None if unsupported else face_width,
            measurement_confidence_ppm=observability,
            unsupported_reason="fixture_unsupported" if unsupported else None,
        )
    ]
    if include_height:
        dimensions.append(
            DimensionObservation(
                dimension="face_height",
                support_state="SUPPORTED",
                value_ppm=400_000,
                measurement_confidence_ppm=observability,
            )
        )
    return FaceObservation(
        evidence_reference=f"observation-repeat-{repeat_index}",
        repeat_index=repeat_index,
        dimensions=tuple(dimensions),
    )


def test_successful_repeat_compilation_is_reliable_and_routing_eligible() -> None:
    result = compile_face_runtime((_observation(3), _observation(1), _observation(2)))

    baseline = next(
        entry for entry in result.baseline.dimensions if entry.dimension == "face_width"
    )
    state = next(entry for entry in result.self_state.dimensions if entry.dimension == "face_width")
    assert baseline.value_ppm == 500_000
    assert baseline.reliability_ppm == 900_000
    assert baseline.measurement_confidence_ppm == 900_000
    assert baseline.repeat_reliability_ppm == 1_000_000
    assert baseline.uncertainty_ppm == 100_000
    assert state.routing_eligibility == "ROUTING_ELIGIBLE"
    assert result.baseline.runtime_readiness == RUNTIME_READINESS
    assert result.self_state.integration_status == INTEGRATION_STATUS


def test_low_repeat_agreement_reduces_reliability_and_increases_uncertainty() -> None:
    baseline = compile_baseline_face_model(
        (
            _observation(1, face_width=200_000),
            _observation(2, face_width=500_000),
            _observation(3, face_width=800_000),
        )
    )
    dimension = next(entry for entry in baseline.dimensions if entry.dimension == "face_width")

    assert dimension.reliability_ppm == 360_000
    assert dimension.uncertainty_ppm == 640_000


def test_missing_dimension_fails_closed_as_unsupported_and_unroutable() -> None:
    baseline = compile_baseline_face_model(
        (_observation(1), _observation(2, include_height=False), _observation(3))
    )
    state = derive_self_state(baseline)
    height = next(entry for entry in state.dimensions if entry.dimension == "face_height")

    assert height.value_ppm is None
    assert height.reliability_ppm == 0
    assert height.uncertainty_ppm == 1_000_000
    assert height.routing_eligibility == "UNSUPPORTED"


def test_explicit_unsupported_dimension_never_becomes_routable() -> None:
    state = compile_face_runtime(
        (_observation(1), _observation(2, unsupported=True), _observation(3))
    ).self_state
    width = next(entry for entry in state.dimensions if entry.dimension == "face_width")

    assert width.value_ppm is None
    assert width.reliability_ppm == 0
    assert width.routing_eligibility == "UNSUPPORTED"


@pytest.mark.parametrize(
    "repeats",
    [(_observation(1), _observation(2)), (_observation(1), _observation(2), _observation(2))],
)
def test_illegal_repeat_count_or_index_is_rejected(repeats: tuple[FaceObservation, ...]) -> None:
    with pytest.raises(FaceRuntimeError):
        compile_baseline_face_model(repeats)


def test_duplicate_evidence_reference_is_rejected_as_input_tampering() -> None:
    first = _observation(1)
    second = FaceObservation(
        evidence_reference=first.evidence_reference,
        repeat_index=2,
        dimensions=first.dimensions,
    )
    with pytest.raises(FaceRuntimeError, match="distinct evidence references"):
        compile_baseline_face_model((first, second, _observation(3)))


def test_canonical_replay_is_deterministic_and_order_independent() -> None:
    forward = compile_face_runtime((_observation(1), _observation(2), _observation(3)))
    reordered = compile_face_runtime((_observation(3), _observation(1), _observation(2)))

    assert forward.baseline.canonical_digest == reordered.baseline.canonical_digest
    assert forward.self_state.canonical_digest == reordered.self_state.canonical_digest
