from __future__ import annotations

import hashlib
import io
from collections.abc import Mapping
from pathlib import Path

import pytest
from PIL import Image

from mirror_api import demo_d02_private_m4_backend as backend
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api.providers.opencv_geometry import CANDIDATE_ID, RUNTIME_VERSION
from mirror_api.synthetic_dataset.geometry_transform import DenseRemap
from mirror_api.synthetic_dataset.geometry_variant import TransformDirection


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class _RemapRuntime:
    candidate_id = CANDIDATE_ID
    runtime_version = RUNTIME_VERSION

    def __init__(self) -> None:
        self.manifest_digest = _digest("test-opencv-runtime")
        self.calls = 0

    def remap_rgb(self, *, source: bytes, remap: DenseRemap) -> bytes:
        self.calls += 1
        assert remap.changed_pixel_count > 0
        value = bytearray(source)
        value[0] ^= 0xFF
        return bytes(value)


def _jpeg(index: int) -> bytes:
    image = Image.new("RGB", (64, 64), (30 + index * 15, 100, 160))
    image.putpixel((index + 3, index + 4), (240, 15, 30))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=95, subsampling=0)
    return output.getvalue()


def _material(index: int) -> runtime.SourceMaterial:
    content = _jpeg(index)
    descriptor = runtime.DurableSourceDescriptor(
        source_id=f"{index:032x}",
        source_output_id=f"source-{index}",
        ordinal=index,
        content_sha256=hashlib.sha256(content).hexdigest(),
        media_type="image/jpeg",
        width=64,
        height=64,
        byte_length=len(content),
        generation_request_identity=_digest(f"generation-{index}"),
        provenance_identity=_digest(f"provenance-{index}"),
        source_authority_key=_digest(f"authority-{index}"),
        source_schema_version="d02-source-v1",
    )
    return runtime.SourceMaterial(descriptor=descriptor, content=content)


def _topology_and_landmarks() -> tuple[str, tuple[tuple[float, float, float], ...]]:
    columns, rows = 25, 18
    coordinates: list[tuple[float, float]] = [
        (0.02 + x * 0.96 / (columns - 1), 0.02 + y * 0.96 / (rows - 1))
        for y in range(rows)
        for x in range(columns)
    ]
    base_triangles: list[tuple[int, int, int]] = []
    for y in range(rows - 1):
        for x in range(columns - 1):
            top_left = y * columns + x
            top_right = top_left + 1
            bottom_left = top_left + columns
            bottom_right = bottom_left + 1
            base_triangles.extend(
                ((top_left, top_right, bottom_right), (top_left, bottom_right, bottom_left))
            )
    triangles: list[tuple[int, int, int]] = []
    selected = set(range(18))
    extra = 450
    for index, (first, second, third) in enumerate(base_triangles):
        if index not in selected:
            triangles.append((first, second, third))
            continue
        center_x = (coordinates[first][0] + coordinates[second][0] + coordinates[third][0]) / 3.0
        center_y = (coordinates[first][1] + coordinates[second][1] + coordinates[third][1]) / 3.0
        coordinates.append((center_x, center_y))
        triangles.extend(((first, second, extra), (second, third, extra), (third, first, extra)))
        extra += 1
    assert len(coordinates) == 468
    assert len(triangles) == 852
    # Keep the mesh planar after assigning its fixed MediaPipe-style anchors:
    # indices own positions, and topology edges are rewritten through the
    # inverse permutation instead of moving vertices through an existing mesh.
    position_for_index = list(range(468))
    index_for_position = list(range(468))
    required_positions = {10: 87, 17: 262, 152: 412, 234: 331, 454: 343, 133: 185, 362: 189}
    for index, position in required_positions.items():
        prior_index = index_for_position[position]
        prior_position = position_for_index[index]
        position_for_index[index], position_for_index[prior_index] = position, prior_position
        index_for_position[position], index_for_position[prior_position] = index, prior_index
    edges = [
        edge
        for triangle in triangles
        for edge in (
            (index_for_position[triangle[0]], index_for_position[triangle[1]]),
            (index_for_position[triangle[1]], index_for_position[triangle[2]]),
            (index_for_position[triangle[2]], index_for_position[triangle[0]]),
        )
    ]
    topology = "FACEMESH_TESSELATION = frozenset(" + repr(edges) + ")\n"
    values = [coordinates[position_for_index[index]] for index in range(468)]
    points = tuple((float(x), float(y), 0.0) for x, y in values)
    return topology, points + tuple((0.5, 0.5, 0.0) for _ in range(10))


@pytest.fixture
def m4(
    tmp_path: Path,
) -> tuple[backend.D02OpenCvM4Backend, tuple[runtime.SourceMaterial, ...], _RemapRuntime]:
    topology_text, landmarks = _topology_and_landmarks()
    topology = tmp_path / "topology.py"
    topology.write_text(topology_text, encoding="utf-8")
    materials = tuple(_material(index) for index in range(1, 5))
    remap = _RemapRuntime()
    instance = backend.D02OpenCvM4Backend.for_testing(
        remap_runtime=remap,
        topology_path=topology.resolve(),
        expected_topology_digest=hashlib.sha256(topology.read_bytes()).hexdigest(),
        materials=materials,
        landmarks_by_source={item.descriptor.source_id: landmarks for item in materials},
    )
    return instance, materials, remap


def _entry(material: runtime.SourceMaterial) -> dict[str, object]:
    descriptor = material.descriptor
    return {
        "source_asset_id": descriptor.source_id,
        "source_output_id": descriptor.source_output_id,
        "source_asset_sha256": descriptor.content_sha256,
        "source_ordinal": descriptor.ordinal,
        "source_asset_mime_type": descriptor.media_type,
        "source_asset_width": descriptor.width,
        "source_asset_height": descriptor.height,
        "source_asset_byte_size": descriptor.byte_length,
        "source_authority_key": descriptor.source_authority_key,
        "source_admission_event_id": f"{descriptor.ordinal:032x}",
    }


def _case(
    instance: backend.D02OpenCvM4Backend,
    material: runtime.SourceMaterial,
    *,
    ordinal: int,
    dimension: str,
    direction: str,
    magnitude: int,
) -> dict[str, object]:
    entry = _entry(material)
    packet: Mapping[str, object] = {
        "source_manifest_entry": dict(entry),
        "supporting_row": dict(entry),
    }
    fields = dict(
        instance.case_fields(
            source_packet=packet,
            source_entry=entry,
            case_ordinal=ordinal,
            dimension_key=dimension,
            direction=direction,
            magnitude_ppm=magnitude,
        )
    )
    return {
        **entry,
        **fields,
        "case_id": f"{ordinal:032x}",
        "case_specification_digest": _digest(f"case-{ordinal}"),
        "dimension_key": dimension,
        "direction": direction,
        "magnitude_ppm": magnitude,
    }


def test_case_fields_and_48_case_96_execution_replay(
    m4: tuple[backend.D02OpenCvM4Backend, tuple[runtime.SourceMaterial, ...], _RemapRuntime],
) -> None:
    instance, materials, remap = m4
    ordinal = 1
    for material in materials:
        for dimension in ("jaw_width", "chin_height", "eye_spacing"):
            for direction in ("DECREASE", "INCREASE"):
                for magnitude in (15_000, 30_000):
                    case = _case(
                        instance,
                        material,
                        ordinal=ordinal,
                        dimension=dimension,
                        direction=direction,
                        magnitude=magnitude,
                    )
                    assert (
                        case["geometry_ontology_version_digest"]
                        == backend._D02_GEOMETRY_ONTOLOGY_DIGEST
                    )
                    first = instance.transform(
                        content=material.content,
                        descriptor=material.descriptor,
                        case_entry=case,
                        replay_index=1,
                    )
                    second = instance.transform(
                        content=material.content,
                        descriptor=material.descriptor,
                        case_entry=case,
                        replay_index=2,
                    )
                    assert first.content == second.content
                    assert first.changed_pixel_count == second.changed_pixel_count
                    ordinal += 1
    assert ordinal == 49
    assert remap.calls == 96


def test_replay_order_substitution_and_case_mutation_fail_closed(
    m4: tuple[backend.D02OpenCvM4Backend, tuple[runtime.SourceMaterial, ...], _RemapRuntime],
) -> None:
    instance, materials, _ = m4
    case = _case(
        instance,
        materials[0],
        ordinal=1,
        dimension="jaw_width",
        direction="INCREASE",
        magnitude=15_000,
    )
    with pytest.raises(backend.PrivateM4BackendError):
        instance.transform(
            content=materials[0].content,
            descriptor=materials[0].descriptor,
            case_entry=case,
            replay_index=2,
        )
    instance.transform(
        content=materials[0].content,
        descriptor=materials[0].descriptor,
        case_entry=case,
        replay_index=1,
    )
    with pytest.raises(backend.PrivateM4BackendError):
        instance.transform(
            content=materials[0].content,
            descriptor=materials[0].descriptor,
            case_entry=case,
            replay_index=1,
        )
    altered = dict(case)
    altered["warp_plan_digest"] = _digest("forged-plan")
    with pytest.raises(backend.PrivateM4BackendError):
        instance.transform(
            content=materials[0].content,
            descriptor=materials[0].descriptor,
            case_entry=altered,
            replay_index=2,
        )
    with pytest.raises(backend.PrivateM4BackendError):
        instance.transform(
            content=materials[1].content,
            descriptor=materials[0].descriptor,
            case_entry=case,
            replay_index=2,
        )


def test_private_factory_uses_explicit_loader_and_locked_topology(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    topology_text, landmarks = _topology_and_landmarks()
    topology = tmp_path / "topology.py"
    topology.write_text(topology_text, encoding="utf-8")
    materials = tuple(_material(index) for index in range(1, 5))
    remap = _RemapRuntime()
    received_roots: list[Path] = []

    def _loader(root: Path) -> _RemapRuntime:
        received_roots.append(root)
        return remap

    monkeypatch.setattr(
        backend, "_TOPOLOGY_DIGEST", hashlib.sha256(topology.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(backend, "load_private_opencv_runtime", _loader)
    instance = backend.D02OpenCvM4Backend.from_private_paths(
        runtime_root=tmp_path.resolve(),
        topology_path=topology.resolve(),
        materials=materials,
        landmarks_by_source={item.descriptor.source_id: landmarks for item in materials},
    )
    assert received_roots == [tmp_path.resolve()]
    assert instance.algorithm_version == "opencv-piecewise-affine-v1"


def test_topology_shape_and_out_of_bounds_fail_closed(tmp_path: Path) -> None:
    topology = tmp_path / "bad.py"
    topology.write_text("FACEMESH_TESSELATION = frozenset([])\n", encoding="utf-8")
    with pytest.raises(backend.PrivateM4BackendError):
        backend._load_topology(
            topology.resolve(), expected_digest=hashlib.sha256(topology.read_bytes()).hexdigest()
        )
    points = [(0.5, 0.5, 0.0) for _ in range(478)]
    points[10], points[17], points[152] = (0.5, 0.1, 0.0), (0.5, 0.3, 0.0), (0.5, 0.9, 0.0)
    points[234], points[454] = (0.25, 0.7, 0.0), (0.75, 0.7, 0.0)
    points[133], points[362] = (0.4, 0.4, 0.0), (0.6, 0.4, 0.0)
    with pytest.raises(backend.PrivateM4BackendError):
        backend._control_points(
            landmarks=tuple((float(x), float(y)) for x, y, _ in points[:468]),
            dimension_key="jaw_width",
            direction=TransformDirection.INCREASE,
            magnitude_ppm=4_000_000,
        )
