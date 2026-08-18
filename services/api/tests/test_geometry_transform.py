from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mirror_api.image_sanitizer import canonicalize_rgb_image, decode_canonical_rgb_image
from mirror_api.providers.opencv_geometry import (
    ALGORITHM_VERSION,
    CANDIDATE_ID,
    OpenCvGeometryTransform,
    load_private_opencv_runtime,
)
from mirror_api.synthetic_dataset import (
    CanonicalPolicy,
    CanonicalTransformSource,
    DenseRemap,
    DeterminismLevel,
    DomainValidationError,
    GeometryDimension,
    GeometryDimensionClassification,
    GeometryOntology,
    GeometryTransformRequest,
    LandmarkWarpPlan,
    PolicyKind,
    ReasonCode,
    TransformDirection,
    VariantSpecification,
    WarpControlPoint,
    WarpTriangle,
    build_dense_remap,
)


class FakeRuntime:
    candidate_id = CANDIDATE_ID
    runtime_version = "5.0.0"

    def __init__(self, manifest_digest: str = "a" * 64, *, identical: bool = False) -> None:
        self.manifest_digest = manifest_digest
        self.identical = identical

    def remap_rgb(self, *, source: bytes, remap: DenseRemap) -> bytes:
        if self.identical:
            return source
        result = bytearray(source)
        result[0] ^= 0xFF
        return bytes(result)


def _ontology() -> GeometryOntology:
    authority = CanonicalPolicy.create(
        kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
        version="geometry-ontology-v1",
        content={"dimensions": ["eye_spacing", "jaw_width"]},
    )
    return GeometryOntology(
        authority=authority,
        dimensions=(
            GeometryDimension(
                "eye_spacing",
                GeometryDimensionClassification.EXPERIMENTAL,
                (ReasonCode.FURTHER_RESEARCH,),
            ),
            GeometryDimension("jaw_width", GeometryDimensionClassification.READY),
        ),
    )


def _specification(*, runtime_digest: str = "a" * 64) -> VariantSpecification:
    return VariantSpecification.create(
        ontology=_ontology(),
        source_asset_reference="asset-01",
        source_identity_reference="identity-01",
        source_qa_run_reference="qa-run-01",
        target_dimension="eye_spacing",
        direction=TransformDirection.INCREASE,
        relative_magnitude_ppm=50_000,
        control_dimensions=("jaw_width",),
        algorithm_version=ALGORITHM_VERSION,
        runtime_manifest_digest=runtime_digest,
        tolerance_policy_reference="tolerance-policy-v1",
        output_width=64,
        output_height=64,
        output_policy_version="image-sanitizer-v1",
        determinism_level=DeterminismLevel.BIT_EXACT_CROSS_PLATFORM,
    )


def _source() -> CanonicalTransformSource:
    rgb = bytes((index * 13) % 256 for index in range(64 * 64 * 3))
    canonical = canonicalize_rgb_image(rgb, width=64, height=64)
    return CanonicalTransformSource(
        asset_reference="asset-01",
        content=canonical.bytes_value,
        sha256=canonical.sha256,
        width=64,
        height=64,
    )


def _point(
    code: str,
    source_x: float,
    source_y: float,
    destination_x: float,
    destination_y: float,
    *,
    confidence_ppm: int = 900_000,
) -> WarpControlPoint:
    return WarpControlPoint(
        landmark_code=code,
        source_x=source_x,
        source_y=source_y,
        destination_x=destination_x,
        destination_y=destination_y,
        confidence_ppm=confidence_ppm,
    )


def _plan(specification: VariantSpecification) -> LandmarkWarpPlan:
    return LandmarkWarpPlan.create(
        specification_digest=specification.content_digest,
        control_points=(
            _point("a", 0.0, 0.0, 0.05, 0.0),
            _point("b", 1.0, 0.0, 1.0, 0.0),
            _point("c", 0.0, 1.0, 0.05, 1.0),
        ),
        triangles=(WarpTriangle(("a", "b", "c")),),
    )


def _request() -> GeometryTransformRequest:
    specification = _specification()
    return GeometryTransformRequest(
        specification=specification,
        source=_source(),
        warp_plan=_plan(specification),
    )


def test_warp_plan_digest_and_dense_map_are_deterministic() -> None:
    request = _request()
    first = build_dense_remap(request.warp_plan, width=64, height=64)
    second = build_dense_remap(request.warp_plan, width=64, height=64)

    assert first == second
    assert first.changed_pixel_count > 0
    assert len(first.map_x_float32_le) == 64 * 64 * 4
    assert request.warp_plan.content_digest == _plan(request.specification).content_digest


def test_adapter_returns_new_canonical_synthetic_asset_deterministically() -> None:
    request = _request()
    adapter = OpenCvGeometryTransform(FakeRuntime())

    first = adapter.transform(request=request)
    second = adapter.transform(request=request)
    decoded = decode_canonical_rgb_image(
        first.content,
        expected_width=64,
        expected_height=64,
    )

    assert first == second
    assert first.sha256 != request.source.sha256
    assert len(decoded.bytes_value) == 64 * 64 * 3
    assert first.runtime_manifest_digest == "a" * 64
    assert first.warp_plan_digest == request.warp_plan.content_digest


def test_runtime_identity_and_identical_output_fail_closed() -> None:
    request = _request()
    with pytest.raises(DomainValidationError) as mismatch:
        OpenCvGeometryTransform(FakeRuntime("b" * 64)).transform(request=request)
    assert mismatch.value.reason_code is ReasonCode.TRANSFORM_RUNTIME_MISMATCH

    with pytest.raises(DomainValidationError) as identical:
        OpenCvGeometryTransform(FakeRuntime(identical=True)).transform(request=request)
    assert identical.value.reason_code is ReasonCode.SOURCE_RESULT_IDENTICAL


def test_foldover_low_confidence_bounds_and_digest_tamper_are_rejected() -> None:
    specification = _specification()
    with pytest.raises(DomainValidationError) as confidence:
        _point("a", 0.0, 0.0, 0.1, 0.0, confidence_ppm=499_999)
    assert confidence.value.reason_code is ReasonCode.INSUFFICIENT_LANDMARK_CONFIDENCE

    with pytest.raises(DomainValidationError) as bounds:
        _point("a", 0.0, 0.0, -0.1, 0.0)
    assert bounds.value.reason_code is ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT

    folded = LandmarkWarpPlan.create(
        specification_digest=specification.content_digest,
        control_points=(
            _point("a", 0.0, 0.0, 0.0, 0.0),
            _point("b", 1.0, 0.0, 0.0, 1.0),
            _point("c", 0.0, 1.0, 1.0, 0.0),
        ),
        triangles=(WarpTriangle(("a", "b", "c")),),
    )
    with pytest.raises(DomainValidationError) as foldover:
        build_dense_remap(folded, width=64, height=64)
    assert foldover.value.reason_code is ReasonCode.FOLDOVER_REJECTED

    with pytest.raises(DomainValidationError) as tampered:
        replace(_plan(specification), content_digest="f" * 64)
    assert tampered.value.reason_code is ReasonCode.INVALID_WARP_PLAN


def test_native_loader_rejects_untrusted_runtime_location(tmp_path: Path) -> None:
    with pytest.raises(DomainValidationError) as relative:
        load_private_opencv_runtime(Path("relative-runtime"))
    assert relative.value.reason_code is ReasonCode.TRANSFORM_RUNTIME_MISMATCH

    extra = tmp_path / "runtime"
    extra.mkdir()
    (extra / "unexpected.dll").write_bytes(b"not-a-runtime")
    with pytest.raises(DomainValidationError) as shape:
        load_private_opencv_runtime(extra)
    assert shape.value.reason_code is ReasonCode.TRANSFORM_RUNTIME_MISMATCH
