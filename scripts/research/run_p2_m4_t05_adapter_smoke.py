"""Run the T05 adapter against an exact private runtime using a non-human fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mirror_api.image_sanitizer import canonicalize_rgb_image
from mirror_api.providers.opencv_geometry import (
    ALGORITHM_VERSION,
    OpenCvGeometryTransform,
    load_private_opencv_runtime,
)
from mirror_api.synthetic_dataset import (
    CanonicalPolicy,
    CanonicalTransformSource,
    DeterminismLevel,
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
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    runtime = load_private_opencv_runtime(args.runtime)
    authority = CanonicalPolicy.create(
        kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
        version="geometry-ontology-v1",
        content={"dimensions": ["eye_spacing", "jaw_width"]},
    )
    ontology = GeometryOntology(
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
    specification = VariantSpecification.create(
        ontology=ontology,
        source_asset_reference="non-human-grid-asset",
        source_identity_reference="synthetic-fixture-identity",
        source_qa_run_reference="synthetic-fixture-qa",
        target_dimension="eye_spacing",
        direction=TransformDirection.INCREASE,
        relative_magnitude_ppm=50_000,
        control_dimensions=("jaw_width",),
        algorithm_version=ALGORITHM_VERSION,
        runtime_manifest_digest=runtime.manifest_digest,
        tolerance_policy_reference="tolerance-policy-v1",
        output_width=64,
        output_height=64,
        output_policy_version="image-sanitizer-v1",
        determinism_level=DeterminismLevel.BIT_EXACT_CROSS_PLATFORM,
    )
    rgb = bytes((index * 13) % 256 for index in range(64 * 64 * 3))
    canonical = canonicalize_rgb_image(rgb, width=64, height=64)
    source = CanonicalTransformSource(
        asset_reference="non-human-grid-asset",
        content=canonical.bytes_value,
        sha256=canonical.sha256,
        width=64,
        height=64,
    )
    plan = LandmarkWarpPlan.create(
        specification_digest=specification.content_digest,
        control_points=(
            _point("a", 0.0, 0.0, 0.05, 0.0),
            _point("b", 1.0, 0.0, 1.0, 0.0),
            _point("c", 0.0, 1.0, 0.05, 1.0),
        ),
        triangles=(WarpTriangle(("a", "b", "c")),),
    )
    request = GeometryTransformRequest(
        specification=specification,
        source=source,
        warp_plan=plan,
    )
    adapter = OpenCvGeometryTransform(runtime)
    first = adapter.transform(request=request)
    second = adapter.transform(request=request)
    if first != second or first.sha256 == source.sha256:
        raise RuntimeError("T05_ADAPTER_REPLAY_FAILED")
    print(
        json.dumps(
            {
                "changed_pixel_count": first.changed_pixel_count,
                "result_sha256": first.sha256,
                "runtime_manifest_digest": runtime.manifest_digest,
                "status": "PASS",
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _point(
    code: str,
    source_x: float,
    source_y: float,
    destination_x: float,
    destination_y: float,
) -> WarpControlPoint:
    return WarpControlPoint(
        landmark_code=code,
        source_x=source_x,
        source_y=source_y,
        destination_x=destination_x,
        destination_y=destination_y,
        confidence_ppm=900_000,
    )


if __name__ == "__main__":
    main()
