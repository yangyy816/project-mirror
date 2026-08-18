"""Run the preregistered P2-M4-T07 private synthetic evaluation.

The input manifest and all produced images/logs are private evidence. This script emits no image,
raw landmark, object key, or private path to stdout.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mirror_api.image_sanitizer import decode_canonical_rgb_image
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

SCHEMA = "mirror.p2-m4.t07-private-evaluation/v2"
PLAN_BUILDER_VERSION = "p2-m4-t07-jaw-local-field-v1"
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
MAGNITUDE_PPM = 30_000
HORIZONTAL_SIGMA = 0.12
VERTICAL_SIGMA = 0.18
PLAN_ADMISSION_FLOOR_PPM = 500_000
EXPECTED_TRIANGLE_COUNT = 852
EXPECTED_LANDMARK_COUNT = 478
PLAN_LANDMARK_COUNT = 468
SPLIT_SCHEMA = "mirror.p2-m4.t07-identity-split/v2"
INPUT_SCHEMA = "mirror.p2-m4.t07-private-inputs/v2"
TOPOLOGY_SHA256 = "85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63"
VISION_RUNTIME_ARTIFACT_SHA256_BY_PLATFORM = {
    "windows-x86_64": {
        "executable": "d7d656252b4311fc617802340bd81f0350805f481092f28774f32f9496794e83",
        "mirror_face_landmarker_source.dll": (
            "1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef"
        ),
        "opencv_core3411.dll": ("e0415de8bd7dd97f1c2bcccfba627fe6efe4da9441c9b4c9772f3f4faa8f4343"),
        "opencv_imgproc3411.dll": (
            "1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4"
        ),
    },
    "linux-x86_64-network-none": {
        "executable": "1cfbd3b219542262be424b2cdcff512cc16ce042f847c6d0fcf50eabb98782d3",
        "libmirror_face_landmarker_source.so": (
            "6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7"
        ),
        "libopencv_core.so.3.4.11": (
            "116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408"
        ),
        "libopencv_imgproc.so.3.4.11": (
            "765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5"
        ),
    },
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def split_digest(*, cohort: str, sources: list[dict[str, str]]) -> str:
    facts = {"cohort": cohort, "sources": sources}
    canonical = json.dumps(facts, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return _sha256(f"{SPLIT_SCHEMA}\n{canonical}".encode())


def _split_sources(value: object, *, expected_count: int) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise ValueError("private split shape is invalid")
    sources: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "asset_reference",
            "identity_reference",
            "normalized_sha256",
        }:
            raise ValueError("private split source shape is invalid")
        if any(type(item[key]) is not str or not item[key] for key in item):
            raise ValueError("private split source value is invalid")
        if len(item["normalized_sha256"]) != 64:
            raise ValueError("private split checksum is invalid")
        sources.append(dict(item))
    for field in ("identity_reference", "asset_reference", "normalized_sha256"):
        if len({item[field] for item in sources}) != len(sources):
            raise ValueError(f"duplicate {field} within split")
    return sources


def parse_landmarks(text: str) -> list[tuple[float, float, float]]:
    lines = [line for line in text.splitlines() if line.startswith("face_0_landmarks=")]
    if len(lines) != 1:
        raise ValueError("exactly one landmark payload is required")
    values: list[tuple[float, float, float]] = []
    for item in lines[0].split("=", 1)[1].split(";"):
        parts = item.split(",")
        if len(parts) != 3:
            raise ValueError("landmarks must be XYZ triples")
        values.append((float(parts[0]), float(parts[1]), float(parts[2])))
    if len(values) != EXPECTED_LANDMARK_COUNT:
        raise ValueError("unexpected landmark count")
    if any(len(point) != 3 or not all(math.isfinite(value) for value in point) for point in values):
        raise ValueError("landmarks must be finite XYZ triples")
    if any(not 0.0 <= point[0] <= 1.0 or not 0.0 <= point[1] <= 1.0 for point in values):
        raise ValueError("landmarks are outside normalized image bounds")
    return values


def measurement_vector(points: list[tuple[float, float, float]]) -> dict[str, float]:
    def distance(first: int, second: int) -> float:
        return math.hypot(
            points[first][0] - points[second][0],
            points[first][1] - points[second][1],
        )

    face_height = distance(10, 152)
    if not math.isfinite(face_height) or face_height <= 0.0:
        raise ValueError("face-height normalization is invalid")
    return {
        "jaw_width": distance(234, 454) / face_height,
        "nose_width": distance(98, 327) / face_height,
        "eye_spacing": distance(133, 362) / face_height,
        "right_eye_width": distance(33, 133) / face_height,
        "left_eye_width": distance(362, 263) / face_height,
    }


def _directed_tessellation(path: Path) -> list[tuple[int, int]]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "FACEMESH_TESSELATION"
            for target in statement.targets
        ):
            continue
        if not isinstance(statement.value, ast.Call) or len(statement.value.args) != 1:
            break
        value = ast.literal_eval(statement.value.args[0])
        if not isinstance(value, list):
            break
        result: list[tuple[int, int]] = []
        for edge in value:
            if (
                not isinstance(edge, tuple)
                or len(edge) != 2
                or any(type(vertex) is not int for vertex in edge)
            ):
                raise ValueError("invalid tessellation edge")
            result.append((edge[0], edge[1]))
        return result
    raise ValueError("FACEMESH_TESSELATION list is missing")


def load_triangles(path: Path) -> tuple[WarpTriangle, ...]:
    directed = _directed_tessellation(path)
    if len(directed) != EXPECTED_TRIANGLE_COUNT * 3:
        raise ValueError("unexpected tessellation edge count")
    triangles: list[WarpTriangle] = []
    for offset in range(0, len(directed), 3):
        edge_group = directed[offset : offset + 3]
        vertices = sorted({vertex for edge in edge_group for vertex in edge})
        if len(vertices) != 3 or not all(0 <= vertex < PLAN_LANDMARK_COUNT for vertex in vertices):
            raise ValueError("invalid ordered triangle edge group")
        triangles.append(
            WarpTriangle(
                (
                    f"mp-{vertices[0]:03d}",
                    f"mp-{vertices[1]:03d}",
                    f"mp-{vertices[2]:03d}",
                )
            )
        )
    if len({frozenset(item.landmark_codes) for item in triangles}) != EXPECTED_TRIANGLE_COUNT:
        raise ValueError("duplicate tessellation triangle")
    return tuple(triangles)


def _ontology() -> GeometryOntology:
    authority = CanonicalPolicy.create(
        kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
        version="geometry-m4-t07-v1",
        content={"dimensions": ["eye_spacing", "jaw_width", "nose_width"]},
    )
    return GeometryOntology(
        authority=authority,
        dimensions=tuple(
            GeometryDimension(
                key,
                GeometryDimensionClassification.EXPERIMENTAL,
                (ReasonCode.FURTHER_RESEARCH,),
            )
            for key in ("eye_spacing", "jaw_width", "nose_width")
        ),
    )


def build_control_points(
    landmarks: list[tuple[float, float, float]], direction: TransformDirection
) -> tuple[WarpControlPoint, ...]:
    left = landmarks[234]
    right = landmarks[454]
    center_x = (left[0] + right[0]) / 2.0
    jaw_width = right[0] - left[0]
    face_height = math.hypot(
        landmarks[10][0] - landmarks[152][0], landmarks[10][1] - landmarks[152][1]
    )
    if jaw_width <= 0.0 or face_height <= 0.0:
        raise ValueError("source reference frame is invalid")
    direction_sign = 1.0 if direction is TransformDirection.INCREASE else -1.0
    half_delta = direction_sign * jaw_width * MAGNITUDE_PPM / 2_000_000
    result: list[WarpControlPoint] = []
    for index, point in enumerate(landmarks[:PLAN_LANDMARK_COUNT]):
        is_left = point[0] < center_x
        anchor = left if is_left else right
        side_sign = -1.0 if is_left else 1.0
        dx = (point[0] - anchor[0]) / (HORIZONTAL_SIGMA * jaw_width)
        dy = (point[1] - anchor[1]) / (VERTICAL_SIGMA * face_height)
        influence = math.exp(-(dx * dx + dy * dy))
        result.append(
            WarpControlPoint(
                landmark_code=f"mp-{index:03d}",
                source_x=float(point[0]),
                source_y=float(point[1]),
                destination_x=float(point[0] + side_sign * half_delta * influence),
                destination_y=float(point[1]),
                confidence_ppm=PLAN_ADMISSION_FLOOR_PPM,
            )
        )
    return tuple(result)


def _run_vision(
    *, executable: Path, model: Path, content: bytes, width: int, height: int
) -> tuple[list[tuple[float, float, float]], str]:
    decoded = decode_canonical_rgb_image(content, expected_width=width, expected_height=height)
    with tempfile.TemporaryDirectory(prefix="project-mirror-p2-m4-t07-") as directory:
        rgb_path = Path(directory) / "vision-input.rgb"
        rgb_path.write_bytes(decoded.bytes_value)
        completed = subprocess.run(  # noqa: S603 - exact private executable is manifest-gated
            [str(executable), str(model), str(rgb_path), str(width), str(height)],
            capture_output=True,
            text=True,
            check=False,
        )
    output = completed.stdout + completed.stderr
    if (
        completed.returncode != 0
        or "detect_status=ok" not in output
        or "face_count=1" not in output
        or "close_status=ok" not in output
    ):
        raise RuntimeError("Vision evaluation failed closed")
    return parse_landmarks(output), output


def _manifest(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "calibration_sources",
        "calibration_split_digest",
        "entries",
        "expected_runtime_manifest_digest",
        "holdout_split_digest",
        "platform",
        "schema",
    }:
        raise ValueError("private evaluation manifest shape is invalid")
    if document["schema"] != INPUT_SCHEMA:
        raise ValueError("private evaluation manifest schema is invalid")
    if not isinstance(document["entries"], list) or len(document["entries"]) != 2:
        raise ValueError("exactly two holdout entries are required")
    calibration_sources = _split_sources(document["calibration_sources"], expected_count=2)
    if (
        split_digest(cohort="calibration", sources=calibration_sources)
        != document["calibration_split_digest"]
    ):
        raise ValueError("calibration split digest mismatch")
    holdout_sources = _split_sources(
        [
            {
                "asset_reference": entry.get("source_asset_reference"),
                "identity_reference": entry.get("source_identity_reference"),
                "normalized_sha256": entry.get("source_sha256"),
            }
            if isinstance(entry, dict)
            else entry
            for entry in document["entries"]
        ],
        expected_count=2,
    )
    for field, label in (
        ("identity_reference", "identity"),
        ("asset_reference", "Asset"),
        ("normalized_sha256", "normalized SHA-256"),
    ):
        if {item[field] for item in calibration_sources} & {
            item[field] for item in holdout_sources
        }:
            raise ValueError(f"calibration and holdout {label} overlap")
    if split_digest(cohort="holdout", sources=holdout_sources) != document["holdout_split_digest"]:
        raise ValueError("holdout split digest mismatch")
    return document


def _verify_frozen_inputs(args: argparse.Namespace, manifest: dict[str, Any]) -> None:
    expected_vision_artifacts = VISION_RUNTIME_ARTIFACT_SHA256_BY_PLATFORM.get(manifest["platform"])
    if expected_vision_artifacts is None:
        raise RuntimeError("platform Vision runtime is not qualified")
    for name, expected_sha256 in expected_vision_artifacts.items():
        path = (
            args.vision_executable if name == "executable" else args.vision_executable.parent / name
        )
        if _sha256(path.read_bytes()) != expected_sha256:
            raise RuntimeError(f"Vision runtime artifact checksum mismatch: {name}")
    if _sha256(args.model.read_bytes()) != MODEL_SHA256:
        raise RuntimeError("model checksum mismatch")
    if _sha256(args.topology.read_bytes()) != TOPOLOGY_SHA256:
        raise RuntimeError("topology checksum mismatch")


def run(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _manifest(args.manifest)
    _verify_frozen_inputs(args, manifest)
    runtime = load_private_opencv_runtime(args.runtime_root)
    if runtime.manifest_digest != manifest["expected_runtime_manifest_digest"]:
        raise RuntimeError("runtime manifest mismatch")
    triangles = load_triangles(args.topology)
    ontology = _ontology()
    transform = OpenCvGeometryTransform(runtime)
    args.output_root.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    seen_sha256: set[str] = set()
    for entry in manifest["entries"]:
        if not isinstance(entry, dict) or set(entry) != {
            "height",
            "reference",
            "source_landmark_log",
            "source_asset_reference",
            "source_identity_reference",
            "source_path",
            "source_sha256",
            "width",
        }:
            raise ValueError("private entry shape is invalid")
        source_path = Path(entry["source_path"])
        source_content = source_path.read_bytes()
        if _sha256(source_content) != entry["source_sha256"]:
            raise RuntimeError("source checksum mismatch")
        if entry["source_sha256"] in seen_sha256:
            raise RuntimeError("duplicate holdout source")
        seen_sha256.add(entry["source_sha256"])
        source_landmarks = parse_landmarks(
            Path(entry["source_landmark_log"]).read_text(encoding="utf-8", errors="replace")
        )
        source_measurements = measurement_vector(source_landmarks)
        for direction in (TransformDirection.INCREASE, TransformDirection.DECREASE):
            specification = VariantSpecification.create(
                ontology=ontology,
                source_asset_reference=entry["source_asset_reference"],
                source_identity_reference=entry["source_identity_reference"],
                source_qa_run_reference=f"qa-{entry['reference']}",
                target_dimension="jaw_width",
                direction=direction,
                relative_magnitude_ppm=MAGNITUDE_PPM,
                control_dimensions=("eye_spacing", "nose_width"),
                algorithm_version=ALGORITHM_VERSION,
                runtime_manifest_digest=runtime.manifest_digest,
                tolerance_policy_reference="p2-m4-t07-preregistered-v1",
                output_width=entry["width"],
                output_height=entry["height"],
                output_policy_version="image-sanitizer-v1",
                determinism_level=DeterminismLevel.MEASUREMENT_EQUIVALENT,
            )
            plan = LandmarkWarpPlan.create(
                specification_digest=specification.content_digest,
                control_points=build_control_points(source_landmarks, direction),
                triangles=triangles,
            )
            source = CanonicalTransformSource(
                asset_reference=entry["source_asset_reference"],
                content=source_content,
                sha256=entry["source_sha256"],
                width=entry["width"],
                height=entry["height"],
            )
            request = GeometryTransformRequest(
                specification=specification,
                source=source,
                warp_plan=plan,
            )
            outputs = [transform.transform(request=request) for _ in range(args.repeats)]
            output_sha256 = {output.sha256 for output in outputs}
            if len(output_sha256) != 1:
                raise RuntimeError("same-platform transform replay mismatch")
            stem = f"{entry['reference']}-{direction.value.lower()}"
            (args.output_root / f"{stem}.jpg").write_bytes(outputs[0].content)
            vision_measurements: list[dict[str, float]] = []
            vision_log_sha256: list[str] = []
            for repeat, output in enumerate(outputs, start=1):
                landmarks, log = _run_vision(
                    executable=args.vision_executable,
                    model=args.model,
                    content=output.content,
                    width=output.width,
                    height=output.height,
                )
                (args.output_root / f"{stem}-{repeat:02d}.vision.log").write_text(
                    log, encoding="utf-8"
                )
                vision_log_sha256.append(_sha256(log.encode()))
                vision_measurements.append(measurement_vector(landmarks))
            rows.append(
                {
                    "reference": entry["reference"],
                    "direction": direction.value,
                    "source_sha256": entry["source_sha256"],
                    "output_sha256": outputs[0].sha256,
                    "changed_pixel_count": outputs[0].changed_pixel_count,
                    "warp_plan_digest": plan.content_digest,
                    "source_measurements": source_measurements,
                    "vision_measurements": vision_measurements,
                    "vision_log_sha256": vision_log_sha256,
                    "same_platform_output_replay": True,
                }
            )
    report = {
        "schema": SCHEMA,
        "platform": manifest["platform"],
        "plan_builder_version": PLAN_BUILDER_VERSION,
        "runtime_manifest_digest": runtime.manifest_digest,
        "model_sha256": MODEL_SHA256,
        "topology_sha256": _sha256(args.topology.read_bytes()),
        "triangle_count": len(triangles),
        "repeat_count": args.repeats,
        "rows": rows,
    }
    (args.output_root / "private-evaluation-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--vision-executable", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=(3,), default=3)
    return parser.parse_args()


def main() -> None:
    report = run(_arguments())
    print(f"PLATFORM={report['platform']}")
    print(f"ROWS={len(report['rows'])}")
    print(f"REPEATS={report['repeat_count']}")
    print("PRIVATE_EVALUATION_COMPLETE=YES")


if __name__ == "__main__":
    main()
