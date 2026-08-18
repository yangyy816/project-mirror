"""First-party geometry-transform port and source-relative mesh authority."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from array import array
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

from .domain import DomainValidationError, ReasonCode
from .geometry_variant import VariantSpecification

WARP_PLAN_SCHEMA_VERSION = "mirror.synthetic-dataset/LandmarkWarpPlan/v1"
MAX_TRANSFORM_EDGE_PIXELS = 4096
MAX_TRANSFORM_TOTAL_PIXELS = 16_777_216
MAX_WARP_CONTROL_POINTS = 512
MAX_WARP_TRIANGLES = 1024
MIN_TRIANGLE_AREA_NORMALIZED = 1e-8
MIN_LANDMARK_CONFIDENCE_PPM = 500_000

_REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class CanonicalTransformSource:
    asset_reference: str
    content: bytes
    sha256: str
    width: int
    height: int
    media_type: Literal["image/jpeg"] = "image/jpeg"
    subject_kind: Literal["synthetic"] = "synthetic"

    def __post_init__(self) -> None:
        if _REFERENCE_PATTERN.fullmatch(self.asset_reference) is None:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if self.subject_kind != "synthetic" or self.media_type != "image/jpeg":
            raise DomainValidationError(ReasonCode.SYNTHETIC_ORIGIN_REQUIRED)
        if type(self.content) is not bytes or not self.content:
            raise DomainValidationError(ReasonCode.TRANSFORM_OUTPUT_INVALID)
        if _SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise DomainValidationError(ReasonCode.CHECKSUM_MISMATCH)
        if hashlib.sha256(self.content).hexdigest() != self.sha256:
            raise DomainValidationError(ReasonCode.CHECKSUM_MISMATCH)
        _validate_image_bounds(self.width, self.height)


@dataclass(frozen=True)
class WarpControlPoint:
    landmark_code: str
    source_x: float
    source_y: float
    destination_x: float
    destination_y: float
    confidence_ppm: int

    def __post_init__(self) -> None:
        if _REFERENCE_PATTERN.fullmatch(self.landmark_code) is None:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        coordinates = (
            self.source_x,
            self.source_y,
            self.destination_x,
            self.destination_y,
        )
        if any(type(value) is not float or not math.isfinite(value) for value in coordinates):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if any(value < 0.0 or value > 1.0 for value in coordinates):
            raise DomainValidationError(ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT)
        if (
            type(self.confidence_ppm) is not int
            or self.confidence_ppm < MIN_LANDMARK_CONFIDENCE_PPM
            or self.confidence_ppm > 1_000_000
        ):
            raise DomainValidationError(ReasonCode.INSUFFICIENT_LANDMARK_CONFIDENCE)

    @property
    def moved(self) -> bool:
        return self.source_x != self.destination_x or self.source_y != self.destination_y


@dataclass(frozen=True)
class WarpTriangle:
    landmark_codes: tuple[str, str, str]

    def __post_init__(self) -> None:
        if len(set(self.landmark_codes)) != 3 or any(
            _REFERENCE_PATTERN.fullmatch(code) is None for code in self.landmark_codes
        ):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)


@dataclass(frozen=True)
class LandmarkWarpPlan:
    specification_digest: str
    control_points: tuple[WarpControlPoint, ...]
    triangles: tuple[WarpTriangle, ...]
    content_digest: str

    def __post_init__(self) -> None:
        _validate_sha256(self.specification_digest)
        _validate_sha256(self.content_digest)
        _validate_plan_parts(self.control_points, self.triangles)
        if self.control_points != tuple(
            sorted(self.control_points, key=lambda point: point.landmark_code)
        ) or tuple(item.landmark_codes for item in self.triangles) != tuple(
            sorted(_canonical_triangle(item) for item in self.triangles)
        ):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        facts = _plan_facts(
            specification_digest=self.specification_digest,
            control_points=self.control_points,
            triangles=self.triangles,
        )
        if self.content_digest != _digest(facts):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)

    @classmethod
    def create(
        cls,
        *,
        specification_digest: str,
        control_points: tuple[WarpControlPoint, ...],
        triangles: tuple[WarpTriangle, ...],
    ) -> LandmarkWarpPlan:
        _validate_sha256(specification_digest)
        canonical_points = tuple(sorted(control_points, key=lambda point: point.landmark_code))
        canonical_triangles = tuple(
            WarpTriangle(codes) for codes in sorted(_canonical_triangle(item) for item in triangles)
        )
        _validate_plan_parts(canonical_points, canonical_triangles)
        facts = _plan_facts(
            specification_digest=specification_digest,
            control_points=canonical_points,
            triangles=canonical_triangles,
        )
        return cls(
            specification_digest=specification_digest,
            control_points=canonical_points,
            triangles=canonical_triangles,
            content_digest=_digest(facts),
        )


@dataclass(frozen=True)
class DenseRemap:
    width: int
    height: int
    map_x_float32_le: bytes
    map_y_float32_le: bytes
    changed_pixel_count: int

    def __post_init__(self) -> None:
        _validate_image_bounds(self.width, self.height)
        expected = self.width * self.height * 4
        if (
            type(self.map_x_float32_le) is not bytes
            or type(self.map_y_float32_le) is not bytes
            or len(self.map_x_float32_le) != expected
            or len(self.map_y_float32_le) != expected
            or type(self.changed_pixel_count) is not int
            or not 0 < self.changed_pixel_count <= self.width * self.height
        ):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)


@dataclass(frozen=True)
class GeometryTransformRequest:
    specification: VariantSpecification
    source: CanonicalTransformSource
    warp_plan: LandmarkWarpPlan

    def __post_init__(self) -> None:
        if self.specification.source_asset_reference != self.source.asset_reference:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if self.warp_plan.specification_digest != self.specification.content_digest:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if (self.specification.output_width, self.specification.output_height) != (
            self.source.width,
            self.source.height,
        ):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)


@dataclass(frozen=True)
class GeometryTransformResult:
    content: bytes
    sha256: str
    width: int
    height: int
    changed_pixel_count: int
    runtime_version: str
    runtime_manifest_digest: str
    warp_plan_digest: str
    media_type: Literal["image/jpeg"] = "image/jpeg"
    subject_kind: Literal["synthetic"] = "synthetic"

    def __post_init__(self) -> None:
        if self.subject_kind != "synthetic" or self.media_type != "image/jpeg":
            raise DomainValidationError(ReasonCode.SYNTHETIC_ORIGIN_REQUIRED)
        if (
            type(self.content) is not bytes
            or hashlib.sha256(self.content).hexdigest() != self.sha256
        ):
            raise DomainValidationError(ReasonCode.TRANSFORM_OUTPUT_INVALID)
        _validate_image_bounds(self.width, self.height)
        if (
            type(self.changed_pixel_count) is not int
            or not 0 < self.changed_pixel_count <= self.width * self.height
        ):
            raise DomainValidationError(ReasonCode.TRANSFORM_OUTPUT_INVALID)
        for digest in (self.runtime_manifest_digest, self.warp_plan_digest):
            _validate_sha256(digest)


class GeometryTransform(Protocol):
    def transform(self, *, request: GeometryTransformRequest) -> GeometryTransformResult: ...


def build_dense_remap(plan: LandmarkWarpPlan, *, width: int, height: int) -> DenseRemap:
    """Build a bounded piecewise-affine destination-to-source map using only stdlib types."""
    _validate_image_bounds(width, height)
    if sys.byteorder != "little":
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    if array("f").itemsize != 4:
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    points = {point.landmark_code: point for point in plan.control_points}
    pixel_count = width * height
    map_x = array("f", (float(index % width) for index in range(pixel_count)))
    map_y = array("f", (float(index // width) for index in range(pixel_count)))
    assigned = bytearray(pixel_count)
    changed = 0

    for triangle in plan.triangles:
        first_code, second_code, third_code = triangle.landmark_codes
        controls = (points[first_code], points[second_code], points[third_code])
        source = (
            (_pixel_x(controls[0].source_x, width), _pixel_y(controls[0].source_y, height)),
            (_pixel_x(controls[1].source_x, width), _pixel_y(controls[1].source_y, height)),
            (_pixel_x(controls[2].source_x, width), _pixel_y(controls[2].source_y, height)),
        )
        destination = (
            (
                _pixel_x(controls[0].destination_x, width),
                _pixel_y(controls[0].destination_y, height),
            ),
            (
                _pixel_x(controls[1].destination_x, width),
                _pixel_y(controls[1].destination_y, height),
            ),
            (
                _pixel_x(controls[2].destination_x, width),
                _pixel_y(controls[2].destination_y, height),
            ),
        )
        source_area = _signed_area(*source)
        destination_area = _signed_area(*destination)
        if (
            abs(source_area) < MIN_TRIANGLE_AREA_NORMALIZED * width * height
            or abs(destination_area) < MIN_TRIANGLE_AREA_NORMALIZED * width * height
            or source_area * destination_area <= 0.0
        ):
            raise DomainValidationError(ReasonCode.FOLDOVER_REJECTED)
        min_x = max(0, math.floor(min(point[0] for point in destination)))
        max_x = min(width - 1, math.ceil(max(point[0] for point in destination)))
        min_y = max(0, math.floor(min(point[1] for point in destination)))
        max_y = min(height - 1, math.ceil(max(point[1] for point in destination)))
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                weights = _barycentric(float(x), float(y), destination, destination_area)
                if min(weights) < -1e-6 or max(weights) > 1.0 + 1e-6:
                    continue
                source_x = sum(
                    weight * point[0] for weight, point in zip(weights, source, strict=True)
                )
                source_y = sum(
                    weight * point[1] for weight, point in zip(weights, source, strict=True)
                )
                if (
                    source_x < -1e-5
                    or source_y < -1e-5
                    or source_x > width - 1 + 1e-5
                    or source_y > height - 1 + 1e-5
                ):
                    raise DomainValidationError(ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT)
                source_x = min(max(source_x, 0.0), float(width - 1))
                source_y = min(max(source_y, 0.0), float(height - 1))
                index = y * width + x
                if assigned[index]:
                    if abs(map_x[index] - source_x) > 1e-3 or abs(map_y[index] - source_y) > 1e-3:
                        raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
                    continue
                if abs(source_x - x) > 1e-6 or abs(source_y - y) > 1e-6:
                    changed += 1
                map_x[index] = source_x
                map_y[index] = source_y
                assigned[index] = 1
    if changed == 0:
        raise DomainValidationError(ReasonCode.SOURCE_RESULT_IDENTICAL)
    return DenseRemap(
        width=width,
        height=height,
        map_x_float32_le=map_x.tobytes(),
        map_y_float32_le=map_y.tobytes(),
        changed_pixel_count=changed,
    )


def _validate_plan_parts(
    control_points: tuple[WarpControlPoint, ...], triangles: tuple[WarpTriangle, ...]
) -> None:
    if (
        not 3 <= len(control_points) <= MAX_WARP_CONTROL_POINTS
        or not 1 <= len(triangles) <= MAX_WARP_TRIANGLES
        or len({point.landmark_code for point in control_points}) != len(control_points)
        or not any(point.moved for point in control_points)
    ):
        raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
    codes = {point.landmark_code for point in control_points}
    referenced_codes: set[str] = set()
    triangle_sets: set[frozenset[str]] = set()
    for triangle in triangles:
        if not set(triangle.landmark_codes).issubset(codes):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        key = frozenset(triangle.landmark_codes)
        if key in triangle_sets:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        triangle_sets.add(key)
        referenced_codes.update(triangle.landmark_codes)
    if referenced_codes != codes:
        raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)


def _canonical_triangle(triangle: WarpTriangle) -> tuple[str, str, str]:
    values = triangle.landmark_codes
    rotations = (values, values[1:] + values[:1], values[2:] + values[:2])
    return min(rotations)


def _plan_facts(
    *,
    specification_digest: str,
    control_points: tuple[WarpControlPoint, ...],
    triangles: tuple[WarpTriangle, ...],
) -> dict[str, object]:
    return {
        "control_points": [
            {
                "confidence_ppm": point.confidence_ppm,
                "destination_x": point.destination_x,
                "destination_y": point.destination_y,
                "landmark_code": point.landmark_code,
                "source_x": point.source_x,
                "source_y": point.source_y,
            }
            for point in control_points
        ],
        "specification_digest": specification_digest,
        "triangles": [list(triangle.landmark_codes) for triangle in triangles],
    }


def _digest(facts: Mapping[str, object]) -> str:
    canonical = json.dumps(
        facts,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(f"{WARP_PLAN_SCHEMA_VERSION}\n{canonical}".encode()).hexdigest()


def _validate_sha256(value: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)


def _validate_image_bounds(width: int, height: int) -> None:
    if (
        type(width) is not int
        or type(height) is not int
        or width < 1
        or height < 1
        or width > MAX_TRANSFORM_EDGE_PIXELS
        or height > MAX_TRANSFORM_EDGE_PIXELS
        or width * height > MAX_TRANSFORM_TOTAL_PIXELS
    ):
        raise DomainValidationError(ReasonCode.OUT_OF_BOUNDS_DISPLACEMENT)


def _pixel_x(value: float, width: int) -> float:
    return value * (width - 1)


def _pixel_y(value: float, height: int) -> float:
    return value * (height - 1)


def _signed_area(
    first: tuple[float, float], second: tuple[float, float], third: tuple[float, float]
) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (
        third[0] - first[0]
    )


def _barycentric(
    x: float,
    y: float,
    triangle: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
    denominator: float,
) -> tuple[float, float, float]:
    first, second, third = triangle
    first_weight = (
        (second[0] - x) * (third[1] - y) - (second[1] - y) * (third[0] - x)
    ) / denominator
    second_weight = (
        (third[0] - x) * (first[1] - y) - (third[1] - y) * (first[0] - x)
    ) / denominator
    return first_weight, second_weight, 1.0 - first_weight - second_weight
