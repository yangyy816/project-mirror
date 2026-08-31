"""D02-owned, fail-closed OpenCV M4 execution bridge.

The public D02 case contract has a tracked ontology digest, while the existing
``VariantSpecification`` is an internal geometry-domain envelope.  This module
bridges those two layers without promoting its internal specification digest to
the public authority: the case exposes the tracked ontology digest and the
actual ``LandmarkWarpPlan`` digest; the cached plan remains bound to the same
source, dimension, direction, magnitude, OpenCV runtime manifest, and pixels.

All private locations are explicit inputs.  No path discovery, persistence,
networking, logging, or diagnostic image/landmark return path exists here.
"""

from __future__ import annotations

import ast
import hashlib
import math
import os
import stat
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_runtime_forward as runtime_forward
from mirror_api import demo_measurement_quality as measurement
from mirror_api.providers.opencv_geometry import (
    ALGORITHM_VERSION,
    CANDIDATE_ID,
    RUNTIME_VERSION,
    OpenCvGeometryTransform,
    RemapRuntime,
    load_private_opencv_runtime,
)
from mirror_api.synthetic_dataset.geometry_transform import (
    CanonicalTransformSource,
    GeometryTransformRequest,
    LandmarkWarpPlan,
    WarpControlPoint,
    WarpTriangle,
)
from mirror_api.synthetic_dataset.geometry_variant import (
    DeterminismLevel,
    TransformDirection,
    VariantSpecification,
)

_D02_GEOMETRY_ONTOLOGY_DIGEST: Final = (
    "d902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9"
)
_TOPOLOGY_DIGEST: Final = "85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63"
_LANDMARK_COUNT: Final = 478
_PLAN_LANDMARK_COUNT: Final = 468
_TRIANGLE_COUNT: Final = 852
_CONFIDENCE_PPM: Final = 1_000_000
_M4_RUNTIME_SET_DIGEST: Final = measurement.RUNTIME_MANIFEST_DIGEST
_NETWORK_POLICY: Final = runtime_forward.NETWORK_POLICY
_OUTPUT_POLICY: Final = "image-sanitizer-v1"
_DETERMINISM: Final = DeterminismLevel.BIT_EXACT_SAME_PLATFORM.value
_ONTOLOGY_VERSION: Final = "d02-geometry-ontology-v1"
_TOLERANCE_POLICY: Final = "d02-screening-v1"


class PrivateM4BackendError(ValueError):
    """A private M4 precondition or execution failed without disclosure."""


def _fail() -> NoReturn:
    raise PrivateM4BackendError("private D02 M4 execution failed")


@dataclass(frozen=True, slots=True)
class _SourceBinding:
    material: runtime_forward.SourceMaterial
    landmarks: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class _PlanBinding:
    source_id: str
    source_sha256: str
    source_ordinal: int
    dimension_key: str
    direction: str
    magnitude_ppm: int
    specification: VariantSpecification
    plan: LandmarkWarpPlan


@dataclass(slots=True)
class _ReplayState:
    first_content: bytes
    first_changed_pixel_count: int
    delivered: set[int]


class D02OpenCvM4Backend:
    """Concrete CaseFieldsAdapter and OfflineM4Backend for one four-source run.

    ``from_private_paths`` is the only production factory.  ``for_testing`` is
    deliberately explicit about its test runtime and test topology digest, so
    repository tests never need a qualified private runtime or its topology.
    """

    execution_runtime_set_digest: str = _M4_RUNTIME_SET_DIGEST
    algorithm_version: str = ALGORITHM_VERSION
    network_policy: str = _NETWORK_POLICY

    def __init__(
        self,
        *,
        remap_runtime: RemapRuntime,
        triangles: tuple[WarpTriangle, ...],
        materials: Sequence[runtime_forward.SourceMaterial],
        landmarks_by_source: Mapping[str, Sequence[Sequence[float]]],
    ) -> None:
        self._validate_runtime(remap_runtime)
        bindings = _bindings(materials, landmarks_by_source)
        self._runtime = remap_runtime
        self._transform = OpenCvGeometryTransform(remap_runtime)
        self._triangles = triangles
        self._bindings = bindings
        self._plans: dict[tuple[str, str, int, str, str, int], _PlanBinding] = {}
        self._replays: dict[tuple[str, str], _ReplayState] = {}
        self._lock = threading.RLock()

    @classmethod
    def from_private_paths(
        cls,
        *,
        runtime_root: Path,
        topology_path: Path,
        materials: Sequence[runtime_forward.SourceMaterial],
        landmarks_by_source: Mapping[str, Sequence[Sequence[float]]],
    ) -> D02OpenCvM4Backend:
        """Load only an explicit, exact-qualified runtime and topology path."""

        remap_runtime = load_private_opencv_runtime(runtime_root)
        triangles = _load_topology(topology_path, expected_digest=_TOPOLOGY_DIGEST)
        return cls(
            remap_runtime=remap_runtime,
            triangles=triangles,
            materials=materials,
            landmarks_by_source=landmarks_by_source,
        )

    @classmethod
    def for_testing(
        cls,
        *,
        remap_runtime: RemapRuntime,
        topology_path: Path,
        expected_topology_digest: str,
        materials: Sequence[runtime_forward.SourceMaterial],
        landmarks_by_source: Mapping[str, Sequence[Sequence[float]]],
    ) -> D02OpenCvM4Backend:
        """Construct an injected backend for tests without private artifacts."""

        triangles = _load_topology(topology_path, expected_digest=expected_topology_digest)
        return cls(
            remap_runtime=remap_runtime,
            triangles=triangles,
            materials=materials,
            landmarks_by_source=landmarks_by_source,
        )

    def case_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        source_entry: Mapping[str, object],
        case_ordinal: int,
        dimension_key: str,
        direction: str,
        magnitude_ppm: int,
    ) -> Mapping[str, object]:
        """Build the eight frozen geometry fields and cache the real plan."""

        binding = self._binding_for_packet(source_packet=source_packet, source_entry=source_entry)
        key = _case_key(
            descriptor=binding.material.descriptor,
            dimension_key=dimension_key,
            direction=direction,
            magnitude_ppm=magnitude_ppm,
        )
        if type(case_ordinal) is not int or not 1 <= case_ordinal <= 48:
            _fail()
        with self._lock:
            plan = self._plans.get(key)
            if plan is None:
                plan = self._build_plan(binding=binding, key=key)
                self._plans[key] = plan
            return {
                "geometry_ontology_version_digest": _D02_GEOMETRY_ONTOLOGY_DIGEST,
                "warp_plan_digest": plan.plan.content_digest,
                "geometry_algorithm_version": ALGORITHM_VERSION,
                "runtime_config_digest": self._runtime.manifest_digest,
                "output_policy_version": _OUTPUT_POLICY,
                "output_width": binding.material.descriptor.width,
                "output_height": binding.material.descriptor.height,
                "determinism_level": _DETERMINISM,
            }

    def transform(
        self,
        *,
        content: bytes,
        descriptor: runtime_forward.DurableSourceDescriptor,
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> runtime_forward.BackendM4Result:
        """Execute a cached plan twice, rejecting order, substitution and drift."""

        if type(replay_index) is not int or replay_index not in {1, 2}:
            _fail()
        with self._lock:
            binding = self._binding_for_descriptor(descriptor)
            if content != binding.material.content:
                _fail()
            key = _case_key_from_entry(descriptor, case_entry)
            plan_binding = self._plans.get(key)
            if plan_binding is None or not self._case_matches_plan(case_entry, plan_binding):
                _fail()
            case_id = _identifier(case_entry.get("case_id"))
            specification_digest = _digest(case_entry.get("case_specification_digest"))
            replay_key = (case_id, specification_digest)
            state = self._replays.get(replay_key)
            if state is None:
                if replay_index != 1:
                    _fail()
            elif replay_index != 2 or replay_index in state.delivered:
                _fail()
            result = self._execute(binding.material, plan_binding)
            if state is None:
                self._replays[replay_key] = _ReplayState(
                    first_content=result.content,
                    first_changed_pixel_count=result.changed_pixel_count,
                    delivered={1},
                )
            else:
                if (
                    result.content != state.first_content
                    or result.changed_pixel_count != state.first_changed_pixel_count
                ):
                    _fail()
                state.delivered.add(2)
            return result

    def _build_plan(
        self,
        *,
        binding: _SourceBinding,
        key: tuple[str, str, int, str, str, int],
    ) -> _PlanBinding:
        source_id, source_sha256, source_ordinal, dimension_key, direction, magnitude_ppm = key
        controls = tuple(sorted(legacy._case_controls(dimension_key)))
        specification = _specification(
            source_id=source_id,
            dimension_key=dimension_key,
            direction=TransformDirection(direction),
            magnitude_ppm=magnitude_ppm,
            controls=controls,
            runtime_manifest_digest=self._runtime.manifest_digest,
            width=binding.material.descriptor.width,
            height=binding.material.descriptor.height,
        )
        points = _control_points(
            landmarks=binding.landmarks,
            dimension_key=dimension_key,
            direction=TransformDirection(direction),
            magnitude_ppm=magnitude_ppm,
        )
        try:
            plan = LandmarkWarpPlan.create(
                specification_digest=specification.content_digest,
                control_points=points,
                triangles=self._triangles,
            )
        except ValueError:
            _fail()
        return _PlanBinding(
            source_id=source_id,
            source_sha256=source_sha256,
            source_ordinal=source_ordinal,
            dimension_key=dimension_key,
            direction=direction,
            magnitude_ppm=magnitude_ppm,
            specification=specification,
            plan=plan,
        )

    def _execute(
        self, material: runtime_forward.SourceMaterial, plan_binding: _PlanBinding
    ) -> runtime_forward.BackendM4Result:
        descriptor = material.descriptor
        source = CanonicalTransformSource(
            asset_reference=descriptor.source_id,
            content=material.content,
            sha256=descriptor.content_sha256,
            width=descriptor.width,
            height=descriptor.height,
        )
        try:
            result = self._transform.transform(
                request=GeometryTransformRequest(
                    specification=plan_binding.specification,
                    source=source,
                    warp_plan=plan_binding.plan,
                )
            )
        except ValueError:
            _fail()
        if (
            result.runtime_manifest_digest != self._runtime.manifest_digest
            or result.warp_plan_digest != plan_binding.plan.content_digest
            or result.width != descriptor.width
            or result.height != descriptor.height
        ):
            _fail()
        return runtime_forward.BackendM4Result(
            content=result.content,
            changed_pixel_count=result.changed_pixel_count,
        )

    def _binding_for_packet(
        self, *, source_packet: Mapping[str, object], source_entry: Mapping[str, object]
    ) -> _SourceBinding:
        packet_entry = source_packet.get("source_manifest_entry")
        if not isinstance(packet_entry, Mapping) or not isinstance(source_entry, Mapping):
            _fail()
        descriptor = self._descriptor_from_entry(source_entry)
        if not _same_source_entry(packet_entry, source_entry):
            _fail()
        row = source_packet.get("supporting_row")
        if not isinstance(row, Mapping) or not _row_matches_descriptor(row, descriptor):
            _fail()
        return self._binding_for_descriptor(descriptor)

    def _binding_for_descriptor(
        self, descriptor: runtime_forward.DurableSourceDescriptor
    ) -> _SourceBinding:
        binding = self._bindings.get(descriptor.source_id)
        if binding is None or binding.material.descriptor != descriptor:
            _fail()
        return binding

    def _descriptor_from_entry(
        self, entry: Mapping[str, object]
    ) -> runtime_forward.DurableSourceDescriptor:
        source_id = entry.get("source_asset_id")
        if type(source_id) is not str:
            _fail()
        binding = self._bindings.get(source_id)
        if binding is None:
            _fail()
        descriptor = binding.material.descriptor
        if not _entry_matches_descriptor(entry, descriptor):
            _fail()
        return descriptor

    def _case_matches_plan(self, case_entry: Mapping[str, object], plan: _PlanBinding) -> bool:
        descriptor = self._bindings[plan.source_id].material.descriptor
        return (
            _entry_matches_descriptor(case_entry, descriptor)
            and case_entry.get("dimension_key") == plan.dimension_key
            and case_entry.get("direction") == plan.direction
            and case_entry.get("magnitude_ppm") == plan.magnitude_ppm
            and case_entry.get("geometry_ontology_version_digest") == _D02_GEOMETRY_ONTOLOGY_DIGEST
            and case_entry.get("warp_plan_digest") == plan.plan.content_digest
            and case_entry.get("geometry_algorithm_version") == ALGORITHM_VERSION
            and case_entry.get("runtime_config_digest") == self._runtime.manifest_digest
            and case_entry.get("output_policy_version") == _OUTPUT_POLICY
            and case_entry.get("output_width") == descriptor.width
            and case_entry.get("output_height") == descriptor.height
            and case_entry.get("determinism_level") == _DETERMINISM
        )

    @staticmethod
    def _validate_runtime(remap_runtime: RemapRuntime) -> None:
        if (
            getattr(remap_runtime, "candidate_id", None) != CANDIDATE_ID
            or getattr(remap_runtime, "runtime_version", None) != RUNTIME_VERSION
            or not _is_digest(getattr(remap_runtime, "manifest_digest", None))
        ):
            _fail()


def _specification(
    *,
    source_id: str,
    dimension_key: str,
    direction: TransformDirection,
    magnitude_ppm: int,
    controls: tuple[str, ...],
    runtime_manifest_digest: str,
    width: int,
    height: int,
) -> VariantSpecification:
    facts = {
        "algorithm_version": ALGORITHM_VERSION,
        "control_dimensions": list(controls),
        "determinism_level": _DETERMINISM,
        "direction": direction.value,
        "ontology_digest": _D02_GEOMETRY_ONTOLOGY_DIGEST,
        "ontology_version": _ONTOLOGY_VERSION,
        "output_height": height,
        "output_policy_version": _OUTPUT_POLICY,
        "output_width": width,
        "relative_magnitude_ppm": magnitude_ppm,
        "runtime_manifest_digest": runtime_manifest_digest,
        "source_asset_reference": source_id,
        "source_identity_reference": f"identity-{source_id}",
        "source_qa_run_reference": f"qa-{source_id}",
        "target_dimension": dimension_key,
        "tolerance_policy_reference": _TOLERANCE_POLICY,
    }
    import json

    canonical = json.dumps(
        facts, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return VariantSpecification(
        source_asset_reference=source_id,
        source_identity_reference=f"identity-{source_id}",
        source_qa_run_reference=f"qa-{source_id}",
        ontology_version=_ONTOLOGY_VERSION,
        ontology_digest=_D02_GEOMETRY_ONTOLOGY_DIGEST,
        target_dimension=dimension_key,
        direction=direction,
        relative_magnitude_ppm=magnitude_ppm,
        control_dimensions=controls,
        algorithm_version=ALGORITHM_VERSION,
        runtime_manifest_digest=runtime_manifest_digest,
        tolerance_policy_reference=_TOLERANCE_POLICY,
        output_width=width,
        output_height=height,
        output_policy_version=_OUTPUT_POLICY,
        determinism_level=DeterminismLevel.BIT_EXACT_SAME_PLATFORM,
        content_digest=hashlib.sha256(
            f"mirror.synthetic-dataset/VariantSpecification/v1\n{canonical}".encode()
        ).hexdigest(),
    )


def _bindings(
    materials: Sequence[runtime_forward.SourceMaterial],
    landmarks_by_source: Mapping[str, Sequence[Sequence[float]]],
) -> dict[str, _SourceBinding]:
    if len(materials) != 4:
        _fail()
    ordered = tuple(materials)
    if tuple(item.descriptor.ordinal for item in ordered) != (1, 2, 3, 4):
        _fail()
    source_ids = tuple(item.descriptor.source_id for item in ordered)
    if len(set(source_ids)) != 4 or set(landmarks_by_source) != set(source_ids):
        _fail()
    return {
        item.descriptor.source_id: _SourceBinding(
            material=item,
            landmarks=_landmarks(landmarks_by_source[item.descriptor.source_id]),
        )
        for item in ordered
    }


def _landmarks(value: Sequence[Sequence[float]]) -> tuple[tuple[float, float], ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != _LANDMARK_COUNT
    ):
        _fail()
    result: list[tuple[float, float]] = []
    for point in value:
        if (
            not isinstance(point, Sequence)
            or isinstance(point, (str, bytes))
            or len(point) < 2
            or type(point[0]) is not float
            or type(point[1]) is not float
            or not math.isfinite(point[0])
            or not math.isfinite(point[1])
            or not 0.0 <= point[0] <= 1.0
            or not 0.0 <= point[1] <= 1.0
        ):
            _fail()
        result.append((point[0], point[1]))
    return tuple(result)


def _case_key(
    *,
    descriptor: runtime_forward.DurableSourceDescriptor,
    dimension_key: object,
    direction: object,
    magnitude_ppm: object,
) -> tuple[str, str, int, str, str, int]:
    if (
        type(dimension_key) is not str
        or dimension_key not in legacy.CASE_DIMENSIONS
        or type(direction) is not str
        or direction not in legacy.CASE_DIRECTIONS
        or type(magnitude_ppm) is not int
        or magnitude_ppm not in legacy.CASE_MAGNITUDES
    ):
        _fail()
    return (
        descriptor.source_id,
        descriptor.content_sha256,
        descriptor.ordinal,
        dimension_key,
        direction,
        magnitude_ppm,
    )


def _case_key_from_entry(
    descriptor: runtime_forward.DurableSourceDescriptor, case_entry: Mapping[str, object]
) -> tuple[str, str, int, str, str, int]:
    if not isinstance(case_entry, Mapping):
        _fail()
    return _case_key(
        descriptor=descriptor,
        dimension_key=case_entry.get("dimension_key"),
        direction=case_entry.get("direction"),
        magnitude_ppm=case_entry.get("magnitude_ppm"),
    )


def _control_points(
    *,
    landmarks: tuple[tuple[float, float], ...],
    dimension_key: str,
    direction: TransformDirection,
    magnitude_ppm: int,
) -> tuple[WarpControlPoint, ...]:
    sign = 1.0 if direction is TransformDirection.INCREASE else -1.0
    face_height = _distance(landmarks[10], landmarks[152])
    if face_height <= 0.0:
        _fail()
    if dimension_key == "jaw_width":
        left, right = landmarks[234], landmarks[454]
        width = right[0] - left[0]
        if width <= 0.0:
            _fail()
        return _paired_horizontal_points(
            landmarks=landmarks,
            left=left,
            right=right,
            sigma_x=0.12 * width,
            sigma_y=0.18 * face_height,
            half_delta=sign * width * magnitude_ppm / 2_000_000,
        )
    if dimension_key == "eye_spacing":
        left, right = landmarks[133], landmarks[362]
        spacing = right[0] - left[0]
        if spacing <= 0.0:
            _fail()
        return _paired_horizontal_points(
            landmarks=landmarks,
            left=left,
            right=right,
            sigma_x=0.50 * spacing,
            sigma_y=0.07 * face_height,
            half_delta=sign * spacing * magnitude_ppm / 2_000_000,
        )
    if dimension_key == "chin_height":
        reference, chin = landmarks[17], landmarks[152]
        chin_distance = _distance(reference, chin)
        if chin_distance <= 0.0:
            _fail()
        return _vertical_points(
            landmarks=landmarks,
            center=chin,
            sigma_x=0.18 * face_height,
            sigma_y=0.35 * chin_distance,
            delta_y=sign * chin_distance * magnitude_ppm / 1_000_000,
        )
    _fail()


def _paired_horizontal_points(
    *,
    landmarks: tuple[tuple[float, float], ...],
    left: tuple[float, float],
    right: tuple[float, float],
    sigma_x: float,
    sigma_y: float,
    half_delta: float,
) -> tuple[WarpControlPoint, ...]:
    if (
        sigma_x <= 0.0
        or sigma_y <= 0.0
        or not all(math.isfinite(value) for value in (sigma_x, sigma_y, half_delta))
    ):
        _fail()
    center_x = (left[0] + right[0]) / 2.0
    points: list[WarpControlPoint] = []
    for index, (x, y) in enumerate(landmarks[:_PLAN_LANDMARK_COUNT]):
        anchor, side = (left, -1.0) if x < center_x else (right, 1.0)
        influence = _gaussian(x=x, y=y, center=anchor, sigma_x=sigma_x, sigma_y=sigma_y)
        destination_x = x + side * half_delta * influence
        _in_bounds(destination_x, y)
        points.append(
            WarpControlPoint(
                landmark_code=f"mp-{index:03d}",
                source_x=x,
                source_y=y,
                destination_x=destination_x,
                destination_y=y,
                confidence_ppm=_CONFIDENCE_PPM,
            )
        )
    return tuple(points)


def _vertical_points(
    *,
    landmarks: tuple[tuple[float, float], ...],
    center: tuple[float, float],
    sigma_x: float,
    sigma_y: float,
    delta_y: float,
) -> tuple[WarpControlPoint, ...]:
    if (
        sigma_x <= 0.0
        or sigma_y <= 0.0
        or not all(math.isfinite(value) for value in (sigma_x, sigma_y, delta_y))
    ):
        _fail()
    points: list[WarpControlPoint] = []
    for index, (x, y) in enumerate(landmarks[:_PLAN_LANDMARK_COUNT]):
        influence = _gaussian(x=x, y=y, center=center, sigma_x=sigma_x, sigma_y=sigma_y)
        destination_y = y + delta_y * influence
        _in_bounds(x, destination_y)
        points.append(
            WarpControlPoint(
                landmark_code=f"mp-{index:03d}",
                source_x=x,
                source_y=y,
                destination_x=x,
                destination_y=destination_y,
                confidence_ppm=_CONFIDENCE_PPM,
            )
        )
    return tuple(points)


def _gaussian(
    *, x: float, y: float, center: tuple[float, float], sigma_x: float, sigma_y: float
) -> float:
    dx = (x - center[0]) / sigma_x
    dy = (y - center[1]) / sigma_y
    value = math.exp(-(dx * dx + dy * dy))
    if not math.isfinite(value):
        _fail()
    return value


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    value = math.hypot(first[0] - second[0], first[1] - second[1])
    if not math.isfinite(value):
        _fail()
    return value


def _in_bounds(x: float, y: float) -> None:
    if not math.isfinite(x) or not math.isfinite(y) or not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
        _fail()


def _load_topology(path: Path, *, expected_digest: str) -> tuple[WarpTriangle, ...]:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path.is_symlink()
        or not _is_digest(expected_digest)
    ):
        _fail()
    try:
        resolved = path.resolve(strict=True)
        if resolved != path or not resolved.is_file() or resolved.is_symlink():
            _fail()
        before = os.stat(resolved, follow_symlinks=False)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(resolved, flags)
        try:
            after = os.fstat(descriptor)
            if not stat.S_ISREG(after.st_mode) or (
                before.st_dev,
                before.st_ino,
            ) != (after.st_dev, after.st_ino):
                _fail()
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                content = handle.read()
        finally:
            os.close(descriptor)
    except (OSError, ValueError):
        _fail()
    if hashlib.sha256(content).hexdigest() != expected_digest:
        _fail()
    try:
        module = ast.parse(content.decode("utf-8"), mode="exec")
        directed = _directed_edges(module)
    except (SyntaxError, UnicodeError, ValueError):
        _fail()
    if len(directed) != _TRIANGLE_COUNT * 3:
        _fail()
    triangles: list[WarpTriangle] = []
    for offset in range(0, len(directed), 3):
        vertices = sorted({vertex for edge in directed[offset : offset + 3] for vertex in edge})
        if len(vertices) != 3 or any(not 0 <= vertex < _PLAN_LANDMARK_COUNT for vertex in vertices):
            _fail()
        triangles.append(
            WarpTriangle(
                (f"mp-{vertices[0]:03d}", f"mp-{vertices[1]:03d}", f"mp-{vertices[2]:03d}")
            )
        )
    if len({frozenset(item.landmark_codes) for item in triangles}) != _TRIANGLE_COUNT:
        _fail()
    return tuple(triangles)


def _directed_edges(module: ast.Module) -> list[tuple[int, int]]:
    assignments = [
        statement
        for statement in module.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "FACEMESH_TESSELATION"
            for target in statement.targets
        )
    ]
    if len(assignments) != 1:
        _fail()
    expression = assignments[0].value
    if (
        not isinstance(expression, ast.Call)
        or not isinstance(expression.func, ast.Name)
        or expression.func.id != "frozenset"
        or len(expression.args) != 1
        or expression.keywords
    ):
        _fail()
    value = ast.literal_eval(expression.args[0])
    if not isinstance(value, list):
        _fail()
    result: list[tuple[int, int]] = []
    for edge in value:
        if (
            not isinstance(edge, tuple)
            or len(edge) != 2
            or any(type(vertex) is not int for vertex in edge)
        ):
            _fail()
        result.append(cast(tuple[int, int], edge))
    return result


def _entry_matches_descriptor(
    entry: Mapping[str, object], descriptor: runtime_forward.DurableSourceDescriptor
) -> bool:
    return (
        entry.get("source_asset_id") == descriptor.source_id
        and entry.get("source_output_id", descriptor.source_output_id)
        == descriptor.source_output_id
        and entry.get("source_asset_sha256") == descriptor.content_sha256
        and entry.get("source_ordinal") == descriptor.ordinal
        and entry.get("source_asset_mime_type", descriptor.media_type) == descriptor.media_type
        and entry.get("source_asset_width", descriptor.width) == descriptor.width
        and entry.get("source_asset_height", descriptor.height) == descriptor.height
        and entry.get("source_asset_byte_size", descriptor.byte_length) == descriptor.byte_length
    )


def _row_matches_descriptor(
    row: Mapping[str, object], descriptor: runtime_forward.DurableSourceDescriptor
) -> bool:
    return _entry_matches_descriptor(row, descriptor)


def _same_source_entry(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    keys = (
        "source_asset_id",
        "source_output_id",
        "source_asset_sha256",
        "source_ordinal",
        "source_authority_key",
        "source_admission_event_id",
    )
    return all(left.get(key) == right.get(key) for key in keys)


def _identifier(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 32
        or any(char not in "0123456789abcdef" for char in value)
    ):
        _fail()
    return value


def _digest(value: object) -> str:
    if not _is_digest(value):
        _fail()
    return cast(str, value)


def _is_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )
