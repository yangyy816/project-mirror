"""Run the preregistered P2-M5-CC01C private calibration experiment.

The platform report is private evidence.  ``merge`` deliberately emits only a
redacted aggregate; it is not a threshold or readiness decision.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import math
import subprocess
import tempfile
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

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
    compute_similarity_signature,
)
from PIL import Image

CANDIDATE_SCHEMA = "mirror.p2-m5/CC01CCandidateManifest/v1"
INPUT_SCHEMA = "mirror.p2-m5/CC01C-private-platform-inputs/v2"
PRIVATE_REPORT_SCHEMA = "mirror.p2-m5/CC01C-private-platform-report/v2"
MANUAL_REVIEW_SCHEMA = "mirror.p2-m5/CC01C-private-manual-artifact-review/v1"
AGGREGATE_SCHEMA = "mirror.p2-m5/CC01C-redacted-aggregate/v3"
EXPECTED_MANIFEST_DIGEST = "eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4"
ACCEPTED_CANDIDATE_SHA = "b0b60eb29336d74a0f4c7628c9d1d1458d11d3f9"
ACCEPTED_CANDIDATE_RUN = 32199176469
ACCEPTANCE_CHECKPOINT_SHA = "7a0d112e2b21588630096ab63bb5dc7613662bc5"
ACCEPTANCE_CHECKPOINT_RUN = 32199833331
EXPECTED_LANDMARK_COUNT = 478
PLAN_LANDMARK_COUNT = 468
EXPECTED_TRIANGLE_COUNT = 852
PRIVATE_ENTRY_KEYS = {
    "asset_reference",
    "height",
    "identity_reference",
    "item_reference",
    "normalized_sha256",
    "qa_run_reference",
    "source_landmark_log",
    "source_landmark_log_sha256",
    "source_path",
    "width",
}


class FailureCode(StrEnum):
    SOURCE_CHECKSUM_MISMATCH = "SOURCE_CHECKSUM_MISMATCH"
    SOURCE_LANDMARK_EVIDENCE_MISMATCH = "SOURCE_LANDMARK_EVIDENCE_MISMATCH"
    PLAN_BUILD_FAILED = "PLAN_BUILD_FAILED"
    TRANSFORM_FAILED = "TRANSFORM_FAILED"
    SAME_PLATFORM_NONDETERMINISM = "SAME_PLATFORM_NONDETERMINISM"
    SOURCE_RESULT_IDENTICAL = "SOURCE_RESULT_IDENTICAL"
    RESULT_QA_FAILED = "RESULT_QA_FAILED"
    TARGET_DIRECTION_MISMATCH = "TARGET_DIRECTION_MISMATCH"
    RESULT_SIGNATURE_FAILED = "RESULT_SIGNATURE_FAILED"


class CalibrationFailure(RuntimeError):
    def __init__(self, code: FailureCode, stage: str) -> None:
        self.code = code
        self.stage = stage
        super().__init__(code.value)


RUNTIME_FILENAMES = {
    "windows_x86_64": {
        "wrapper_sha256": None,
        "main_sha256": "mirror_face_landmarker_source.dll",
        "opencv_core_sha256": "opencv_core3411.dll",
        "opencv_imgproc_sha256": "opencv_imgproc3411.dll",
    },
    "linux_x86_64_network_none": {
        "wrapper_sha256": None,
        "main_sha256": "libmirror_face_landmarker_source.so",
        "opencv_core_sha256": "libopencv_core.so.3.4.11",
        "opencv_imgproc_sha256": "libopencv_imgproc.so.3.4.11",
    },
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_digest(schema: str, document: dict[str, Any], omitted: str) -> str:
    facts = {key: value for key, value in document.items() if key != omitted}
    canonical = json.dumps(
        facts, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return _sha256(f"{schema}\n{canonical}".encode())


def _require_sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{label} must be a normalized SHA-256")
    return value


def load_candidate_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != CANDIDATE_SCHEMA:
        raise ValueError("candidate manifest schema is invalid")
    if value.get("status") != "PREREGISTERED_NOT_EXECUTED":
        raise ValueError("candidate manifest status is invalid")
    if value.get("manifest_content_digest") != EXPECTED_MANIFEST_DIGEST:
        raise ValueError("candidate manifest digest is not the accepted digest")
    if (
        _canonical_digest(CANDIDATE_SCHEMA, value, "manifest_content_digest")
        != EXPECTED_MANIFEST_DIGEST
    ):
        raise ValueError("candidate manifest content digest mismatch")
    candidates = value.get("candidate_dimensions")
    if not isinstance(candidates, list) or len(candidates) != 6:
        raise ValueError("candidate manifest must contain exactly six candidates")
    keys = [item.get("dimension_key") for item in candidates if isinstance(item, dict)]
    if len(keys) != 6 or set(keys) != {
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    }:
        raise ValueError("candidate manifest candidate set is invalid")
    envelope = value.get("resource_envelope")
    contract = value.get("evaluation_contract")
    runtime = value.get("runtime_authority")
    if (
        not isinstance(envelope, dict)
        or not isinstance(contract, dict)
        or not isinstance(runtime, dict)
    ):
        raise ValueError("candidate manifest authority is invalid")
    if envelope != {
        "identity_count": 12,
        "candidate_count": 6,
        "direction_count": 2,
        "magnitude_count": 2,
        "platform_count": 2,
        "repeat_count": 3,
        "maximum_transform_vision_rows": 1728,
        "retry_attempts": 0,
        "concurrency_per_platform": 1,
    }:
        raise ValueError("candidate resource envelope is invalid")
    if (
        contract.get("directions") != ["INCREASE", "DECREASE"]
        or contract.get("magnitude_grid_ppm") != [15000, 30000]
        or contract.get("repeat_count_per_platform_direction_magnitude") != 3
    ):
        raise ValueError("candidate evaluation envelope is invalid")
    if (
        runtime.get("expected_landmarks") != EXPECTED_LANDMARK_COUNT
        or runtime.get("plan_landmarks") != PLAN_LANDMARK_COUNT
        or runtime.get("expected_triangles") != EXPECTED_TRIANGLE_COUNT
    ):
        raise ValueError("candidate geometry authority is invalid")
    return value


def _cohort_digest(entries: list[dict[str, Any]]) -> str:
    facts = [
        {
            key: entry[key]
            for key in (
                "item_reference",
                "identity_reference",
                "asset_reference",
                "qa_run_reference",
                "normalized_sha256",
                "width",
                "height",
                "source_landmark_log_sha256",
            )
        }
        for entry in entries
    ]
    return _sha256(
        json.dumps(facts, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    )


def load_platform_manifest(
    path: Path,
    candidate_manifest: dict[str, Any],
    stage_b_evidence_path: Path,
) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "acceptance_checkpoint_run",
        "acceptance_checkpoint_sha",
        "accepted_candidate_run",
        "accepted_candidate_sha",
        "cohort_digest",
        "entries",
        "expected_runtime_manifest_digest",
        "platform",
        "schema",
        "stage_b_evidence_sha256",
    }
    if not isinstance(value, dict) or set(value) != required or value.get("schema") != INPUT_SCHEMA:
        raise ValueError("private platform manifest shape is invalid")
    if (
        value["accepted_candidate_sha"] != ACCEPTED_CANDIDATE_SHA
        or value["accepted_candidate_run"] != ACCEPTED_CANDIDATE_RUN
    ):
        raise ValueError("accepted candidate authority mismatch")
    if (
        value["acceptance_checkpoint_sha"] != ACCEPTANCE_CHECKPOINT_SHA
        or value["acceptance_checkpoint_run"] != ACCEPTANCE_CHECKPOINT_RUN
    ):
        raise ValueError("acceptance checkpoint authority mismatch")
    stage_b_bytes = stage_b_evidence_path.read_bytes()
    expected_stage_b_digest = candidate_manifest["calibration_authority"][
        "redacted_evidence_sha256"
    ]
    if (
        _sha256(stage_b_bytes) != expected_stage_b_digest
        or value.get("stage_b_evidence_sha256") != expected_stage_b_digest
    ):
        raise ValueError("Stage B evidence authority mismatch")
    stage_b = json.loads(stage_b_bytes)
    if (
        not isinstance(stage_b, dict)
        or stage_b.get("status")
        not in {
            "LOCAL_PASS_PENDING_TRACKED_EVIDENCE",
            "PASS_AT_7282094_RUN_32197326163",
        }
        or stage_b.get("resource_envelope", {}).get("accepted_identities") != 12
    ):
        raise ValueError("Stage B evidence status is invalid")
    platform = value.get("platform")
    runtime = candidate_manifest["runtime_authority"]
    if platform not in RUNTIME_FILENAMES or value.get(
        "expected_runtime_manifest_digest"
    ) != runtime["transform_runtime_manifest_digest"].get(platform):
        raise ValueError("private platform runtime authority mismatch")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) != 12:
        raise ValueError("private platform manifest requires exactly twelve calibration entries")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != PRIVATE_ENTRY_KEYS:
            raise ValueError("private calibration entry shape is invalid")
        for field in (
            "item_reference",
            "identity_reference",
            "asset_reference",
            "qa_run_reference",
            "source_path",
            "source_landmark_log",
        ):
            if not isinstance(entry[field], str) or not entry[field]:
                raise ValueError(f"private calibration entry {field} is invalid")
        _require_sha256(entry["normalized_sha256"], "private calibration entry checksum")
        _require_sha256(entry["source_landmark_log_sha256"], "private landmark evidence checksum")
        if (
            type(entry["width"]) is not int
            or type(entry["height"]) is not int
            or entry["width"] <= 0
            or entry["height"] <= 0
        ):
            raise ValueError("private calibration dimensions are invalid")
    for field in (
        "item_reference",
        "identity_reference",
        "asset_reference",
        "qa_run_reference",
        "normalized_sha256",
    ):
        if len({entry[field] for entry in entries}) != len(entries):
            raise ValueError(f"duplicate private calibration {field}")
    stage_b_items = stage_b.get("items")
    if not isinstance(stage_b_items, list) or len(stage_b_items) != 12:
        raise ValueError("Stage B item authority is incomplete")
    expected_items = {
        (
            item.get("item_reference"),
            item.get("identity_id"),
            item.get("normalized_asset_id"),
            item.get("qa_run_id"),
            item.get("normalized_sha256"),
        )
        for item in stage_b_items
        if isinstance(item, dict)
    }
    actual_items = {
        (
            item["item_reference"],
            item["identity_reference"],
            item["asset_reference"],
            item["qa_run_reference"],
            item["normalized_sha256"],
        )
        for item in entries
    }
    if len(expected_items) != 12 or actual_items != expected_items:
        raise ValueError("private cohort does not match accepted Stage B authority")
    if value.get("cohort_digest") != _cohort_digest(entries):
        raise ValueError("private cohort digest mismatch")
    return value


def parse_landmarks(text: str) -> list[tuple[float, float, float]]:
    lines = [line for line in text.splitlines() if line.startswith("face_0_landmarks=")]
    if len(lines) != 1:
        raise ValueError("exactly one landmark payload is required")
    points: list[tuple[float, float, float]] = []
    for item in lines[0].split("=", 1)[1].split(";"):
        parts = item.split(",")
        if len(parts) != 3:
            raise ValueError("landmarks must be XYZ triples")
        points.append((float(parts[0]), float(parts[1]), float(parts[2])))
    _validate_landmarks(points)
    return points


def _validate_landmarks(points: list[tuple[float, float, float]]) -> None:
    if len(points) != EXPECTED_LANDMARK_COUNT:
        raise ValueError("unexpected landmark count")
    if any(not all(math.isfinite(value) for value in point) for point in points):
        raise ValueError("landmarks must be finite")
    if any(not 0.0 <= point[0] <= 1.0 or not 0.0 <= point[1] <= 1.0 for point in points):
        raise ValueError("landmarks are outside normalized image bounds")


def _distance(points: list[tuple[float, float, float]], first: int, second: int) -> float:
    return math.hypot(points[first][0] - points[second][0], points[first][1] - points[second][1])


def measurement_vector(
    points: list[tuple[float, float, float]], candidate_manifest: dict[str, Any]
) -> dict[str, float]:
    _validate_landmarks(points)
    face_height = _distance(points, 10, 152)
    if not math.isfinite(face_height) or face_height <= 0.0:
        raise ValueError("face-height normalization is invalid")
    result: dict[str, float] = {}
    for candidate in candidate_manifest["candidate_dimensions"]:
        formula = candidate["measurement_formula"]
        anchors = candidate["anchors"]
        expected = f"distance_xy({anchors[0]},{anchors[1]})/distance_xy(10,152)"
        if formula != expected:
            raise ValueError("unsupported candidate measurement formula")
        value = _distance(points, anchors[0], anchors[1]) / face_height
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("candidate measurement is invalid")
        result[candidate["dimension_key"]] = value
    return result


def build_control_points(
    landmarks: list[tuple[float, float, float]],
    candidate: dict[str, Any],
    direction: TransformDirection,
    magnitude_ppm: int,
    admission_floor_ppm: int,
) -> tuple[WarpControlPoint, ...]:
    _validate_landmarks(landmarks)
    if magnitude_ppm not in (15000, 30000):
        raise ValueError("magnitude is outside the preregistered envelope")
    sign = 1.0 if direction is TransformDirection.INCREASE else -1.0
    anchors = candidate.get("anchors")
    if (
        not isinstance(anchors, list)
        or len(anchors) != 2
        or any(type(item) is not int for item in anchors)
    ):
        raise ValueError("candidate anchors are invalid")
    face_height = _distance(landmarks, 10, 152)
    if face_height <= 0.0:
        raise ValueError("source face height is invalid")
    kind = candidate.get("plan_kind")
    result: list[WarpControlPoint] = []
    if kind == "PAIRED_HORIZONTAL_GAUSSIAN":
        left, right = landmarks[anchors[0]], landmarks[anchors[1]]
        span = right[0] - left[0]
        if span <= 0.0:
            raise ValueError("paired anchors must be left to right with positive span")
        sigma_x = _paired_sigma_x(candidate["dimension_key"], span)
        sigma_y = _paired_sigma_y(candidate["dimension_key"], face_height)
        maximum = sign * span * magnitude_ppm / 2_000_000
        midpoint = (left[0] + right[0]) / 2.0
        for index, point in enumerate(landmarks[:PLAN_LANDMARK_COUNT]):
            anchor, side = (left, -1.0) if point[0] < midpoint else (right, 1.0)
            influence = math.exp(
                -(((point[0] - anchor[0]) / sigma_x) ** 2 + ((point[1] - anchor[1]) / sigma_y) ** 2)
            )
            result.append(
                _control(
                    index,
                    point,
                    point[0] + side * maximum * influence,
                    point[1],
                    admission_floor_ppm,
                )
            )
    elif kind == "SINGLE_VERTICAL_GAUSSIAN":
        if candidate.get("dimension_key") != "chin_height" or candidate.get("moving_anchor") != 152:
            raise ValueError("single vertical candidate authority is invalid")
        moving = landmarks[152]
        span = _distance(landmarks, anchors[0], 152)
        if span <= 0.0:
            raise ValueError("chin reference span is invalid")
        sigma_x, sigma_y = 0.18 * face_height, 0.35 * span
        maximum = sign * span * magnitude_ppm / 1_000_000
        for index, point in enumerate(landmarks[:PLAN_LANDMARK_COUNT]):
            influence = math.exp(
                -(((point[0] - moving[0]) / sigma_x) ** 2 + ((point[1] - moving[1]) / sigma_y) ** 2)
            )
            result.append(
                _control(
                    index, point, point[0], point[1] + maximum * influence, admission_floor_ppm
                )
            )
    else:
        raise ValueError("unsupported candidate plan kind")
    if any(
        not 0.0 <= point.destination_x <= 1.0 or not 0.0 <= point.destination_y <= 1.0
        for point in result
    ):
        raise ValueError("plan remap is outside normalized image bounds")
    return tuple(result)


def _paired_sigma_x(key: str, span: float) -> float:
    factors = {
        "jaw_width": 0.12,
        "eye_spacing": 0.50,
        "nose_width": 0.75,
        "mouth_width": 0.60,
        "cheekbone_width": 0.20,
    }
    if key not in factors:
        raise ValueError("paired candidate sigma authority is invalid")
    return factors[key] * span


def _paired_sigma_y(key: str, face_height: float) -> float:
    factors = {
        "jaw_width": 0.18,
        "eye_spacing": 0.07,
        "nose_width": 0.10,
        "mouth_width": 0.10,
        "cheekbone_width": 0.12,
    }
    return factors[key] * face_height


def _control(
    index: int, point: tuple[float, float, float], x: float, y: float, floor: int
) -> WarpControlPoint:
    return WarpControlPoint(
        f"mp-{index:03d}", float(point[0]), float(point[1]), float(x), float(y), floor
    )


def _directed_tessellation(path: Path) -> list[tuple[int, int]]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for statement in module.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "FACEMESH_TESSELATION"
            for target in statement.targets
        ):
            if isinstance(statement.value, ast.Call) and len(statement.value.args) == 1:
                value = ast.literal_eval(statement.value.args[0])
                if isinstance(value, list) and all(
                    isinstance(edge, tuple)
                    and len(edge) == 2
                    and all(type(vertex) is int for vertex in edge)
                    for edge in value
                ):
                    return value
    raise ValueError("FACEMESH_TESSELATION list is missing")


def load_triangles(path: Path) -> tuple[WarpTriangle, ...]:
    edges = _directed_tessellation(path)
    if len(edges) != EXPECTED_TRIANGLE_COUNT * 3:
        raise ValueError("unexpected tessellation edge count")
    triangles: list[WarpTriangle] = []
    for offset in range(0, len(edges), 3):
        vertices = sorted({vertex for edge in edges[offset : offset + 3] for vertex in edge})
        if len(vertices) != 3 or not all(0 <= vertex < PLAN_LANDMARK_COUNT for vertex in vertices):
            raise ValueError("invalid ordered triangle edge group")
        triangles.append(
            WarpTriangle(
                (f"mp-{vertices[0]:03d}", f"mp-{vertices[1]:03d}", f"mp-{vertices[2]:03d}")
            )
        )
    if len({frozenset(item.landmark_codes) for item in triangles}) != EXPECTED_TRIANGLE_COUNT:
        raise ValueError("duplicate tessellation triangle")
    return tuple(triangles)


def _ontology(candidate_manifest: dict[str, Any]) -> GeometryOntology:
    keys = tuple(item["dimension_key"] for item in candidate_manifest["candidate_dimensions"])
    policy = CanonicalPolicy.create(
        kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
        version="geometry-p2-m5-cc01c-v1",
        content={"dimensions": list(keys)},
    )
    return GeometryOntology(
        authority=policy,
        dimensions=tuple(
            GeometryDimension(
                key=key,
                classification=GeometryDimensionClassification.EXPERIMENTAL,
                reason_codes=(ReasonCode.FURTHER_RESEARCH,),
            )
            for key in keys
        ),
    )


def _verify_frozen_inputs(
    args: argparse.Namespace, platform_manifest: dict[str, Any], candidate_manifest: dict[str, Any]
) -> None:
    runtime = candidate_manifest["runtime_authority"]
    platform = platform_manifest["platform"]
    for key, name in RUNTIME_FILENAMES[platform].items():
        path = args.vision_executable if name is None else args.vision_executable.parent / name
        if _sha256(path.read_bytes()) != runtime["vision_artifacts"][platform][key]:
            raise RuntimeError(f"Vision runtime artifact checksum mismatch: {key}")
    if _sha256(args.model.read_bytes()) != runtime["vision_model_sha256"]:
        raise RuntimeError("model checksum mismatch")
    if _sha256(args.topology.read_bytes()) != runtime["topology_sha256"]:
        raise RuntimeError("topology checksum mismatch")


def _run_vision(
    executable: Path, model: Path, content: bytes, width: int, height: int
) -> tuple[list[tuple[float, float, float]], str]:
    decoded = decode_canonical_rgb_image(content, expected_width=width, expected_height=height)
    with tempfile.TemporaryDirectory(prefix="project-mirror-p2-m5-cc01c-") as directory:
        rgb_path = Path(directory) / "vision-input.rgb"
        rgb_path.write_bytes(decoded.bytes_value)
        completed = subprocess.run(  # noqa: S603 - executable/model are hash-gated before use
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
        raise CalibrationFailure(FailureCode.RESULT_QA_FAILED, "RESULT_VISION_QA")
    return parse_landmarks(output), output


def _preflight_vision_runtime(
    executable: Path, model: Path, platform_manifest: dict[str, Any]
) -> None:
    """Prove that the exact Vision runtime starts before any transform work."""
    entry = platform_manifest["entries"][0]
    content = Path(entry["source_path"]).read_bytes()
    if _sha256(content) != entry["normalized_sha256"]:
        raise RuntimeError("Vision runtime preflight source checksum mismatch")
    try:
        _run_vision(executable, model, content, entry["width"], entry["height"])
    except CalibrationFailure as error:
        raise RuntimeError("Vision runtime preflight failed") from error


def _case_digest(identity: str, candidate: str, direction: str, magnitude: int) -> str:
    return _sha256(f"{identity}\n{candidate}\n{direction}\n{magnitude}".encode())


def _private_report_digest(report: dict[str, Any]) -> str:
    return _canonical_digest(PRIVATE_REPORT_SCHEMA, report, "report_digest")


def build_platform_manifest(args: argparse.Namespace) -> dict[str, Any]:
    candidate = load_candidate_manifest(args.candidate_manifest)
    if args.platform not in RUNTIME_FILENAMES:
        raise ValueError("platform is outside the accepted execution envelope")
    stage_b_bytes = args.stage_b_evidence.read_bytes()
    stage_b_sha256 = _sha256(stage_b_bytes)
    if stage_b_sha256 != candidate["calibration_authority"]["redacted_evidence_sha256"]:
        raise ValueError("Stage B evidence authority mismatch")
    stage_b = json.loads(stage_b_bytes)
    items = stage_b.get("items") if isinstance(stage_b, dict) else None
    if not isinstance(items, list) or len(items) != 12:
        raise ValueError("Stage B item authority is incomplete")
    entries: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("item_reference"), str):
            raise ValueError("Stage B item authority is invalid")
        item_reference = item["item_reference"]
        source_path = (args.normalized_dir / f"{item_reference}.jpg").resolve()
        landmark_path = (args.vision_log_dir / f"{item_reference}.log").resolve()
        content, landmark_bytes = source_path.read_bytes(), landmark_path.read_bytes()
        if _sha256(content) != item.get("normalized_sha256"):
            raise ValueError("Stage B normalized source checksum mismatch")
        parse_landmarks(landmark_bytes.decode("utf-8", errors="replace"))
        with Image.open(io.BytesIO(content)) as image:
            if image.format != "JPEG" or image.mode != "RGB":
                raise ValueError("Stage B normalized source is not canonical JPEG/RGB")
            width, height = image.size
        decode_canonical_rgb_image(
            content,
            expected_width=width,
            expected_height=height,
        )
        entries.append(
            {
                "item_reference": item_reference,
                "identity_reference": item.get("identity_id"),
                "asset_reference": item.get("normalized_asset_id"),
                "qa_run_reference": item.get("qa_run_id"),
                "normalized_sha256": item.get("normalized_sha256"),
                "source_path": str(source_path),
                "source_landmark_log": str(landmark_path),
                "source_landmark_log_sha256": _sha256(landmark_bytes),
                "width": width,
                "height": height,
            }
        )
    manifest: dict[str, Any] = {
        "schema": INPUT_SCHEMA,
        "platform": args.platform,
        "expected_runtime_manifest_digest": candidate["runtime_authority"][
            "transform_runtime_manifest_digest"
        ][args.platform],
        "accepted_candidate_sha": ACCEPTED_CANDIDATE_SHA,
        "accepted_candidate_run": ACCEPTED_CANDIDATE_RUN,
        "acceptance_checkpoint_sha": ACCEPTANCE_CHECKPOINT_SHA,
        "acceptance_checkpoint_run": ACCEPTANCE_CHECKPOINT_RUN,
        "stage_b_evidence_sha256": stage_b_sha256,
        "entries": entries,
    }
    manifest["cohort_digest"] = _cohort_digest(entries)
    if args.output.exists():
        raise FileExistsError("private platform manifest output must not already exist")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def run(args: argparse.Namespace) -> dict[str, Any]:
    candidate_manifest = load_candidate_manifest(args.candidate_manifest)
    platform_manifest = load_platform_manifest(
        args.manifest, candidate_manifest, args.stage_b_evidence
    )
    if args.output_root.exists():
        raise FileExistsError("private output root must not already exist")
    _verify_frozen_inputs(args, platform_manifest, candidate_manifest)
    _preflight_vision_runtime(args.vision_executable, args.model, platform_manifest)
    runtime = load_private_opencv_runtime(args.runtime_root)
    if runtime.manifest_digest != platform_manifest["expected_runtime_manifest_digest"]:
        raise RuntimeError("runtime manifest mismatch")
    triangles = load_triangles(args.topology)
    args.output_root.mkdir(parents=True, exist_ok=False)
    transform, ontology = OpenCvGeometryTransform(runtime), _ontology(candidate_manifest)
    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for entry in platform_manifest["entries"]:
        content = Path(entry["source_path"]).read_bytes()
        if _sha256(content) != entry["normalized_sha256"]:
            raise CalibrationFailure(FailureCode.SOURCE_CHECKSUM_MISMATCH, "SOURCE_ADMISSION")
        landmark_log = Path(entry["source_landmark_log"]).read_bytes()
        if _sha256(landmark_log) != entry["source_landmark_log_sha256"]:
            raise CalibrationFailure(
                FailureCode.SOURCE_LANDMARK_EVIDENCE_MISMATCH, "SOURCE_ADMISSION"
            )
        source_landmarks = parse_landmarks(landmark_log.decode("utf-8", errors="replace"))
        source_vector = measurement_vector(source_landmarks, candidate_manifest)
        for candidate in candidate_manifest["candidate_dimensions"]:
            for direction in (TransformDirection.INCREASE, TransformDirection.DECREASE):
                for magnitude in candidate_manifest["evaluation_contract"]["magnitude_grid_ppm"]:
                    case = _case_digest(
                        entry["identity_reference"],
                        candidate["dimension_key"],
                        direction.value,
                        magnitude,
                    )
                    try:
                        specification = VariantSpecification.create(
                            ontology=ontology,
                            source_asset_reference=entry["asset_reference"],
                            source_identity_reference=entry["identity_reference"],
                            source_qa_run_reference=entry["qa_run_reference"],
                            target_dimension=candidate["dimension_key"],
                            direction=direction,
                            relative_magnitude_ppm=magnitude,
                            control_dimensions=tuple(candidate["control_dimensions"]),
                            algorithm_version=ALGORITHM_VERSION,
                            runtime_manifest_digest=runtime.manifest_digest,
                            tolerance_policy_reference="p2-m5-cc01c-preregistered-v1",
                            output_width=entry["width"],
                            output_height=entry["height"],
                            output_policy_version=candidate_manifest["runtime_authority"][
                                "output_policy_version"
                            ],
                            determinism_level=DeterminismLevel.MEASUREMENT_EQUIVALENT,
                        )
                        plan = LandmarkWarpPlan.create(
                            specification_digest=specification.content_digest,
                            control_points=build_control_points(
                                source_landmarks,
                                candidate,
                                direction,
                                magnitude,
                                candidate_manifest["runtime_authority"]["plan_admission_floor_ppm"],
                            ),
                            triangles=triangles,
                        )
                        source = CanonicalTransformSource(
                            asset_reference=entry["asset_reference"],
                            content=content,
                            sha256=entry["normalized_sha256"],
                            width=entry["width"],
                            height=entry["height"],
                        )
                        request = GeometryTransformRequest(
                            specification=specification, source=source, warp_plan=plan
                        )
                        outputs = [transform.transform(request=request) for _ in range(3)]
                        hashes = {output.sha256 for output in outputs}
                        if len(hashes) != 1:
                            raise CalibrationFailure(
                                FailureCode.SAME_PLATFORM_NONDETERMINISM, "TRANSFORM_REPLAY"
                            )
                        for repeat, output in enumerate(outputs, start=1):
                            if output.sha256 == entry["normalized_sha256"]:
                                raise CalibrationFailure(
                                    FailureCode.SOURCE_RESULT_IDENTICAL, "RESULT_ADMISSION"
                                )
                            result_landmarks, vision_log = _run_vision(
                                args.vision_executable,
                                args.model,
                                output.content,
                                output.width,
                                output.height,
                            )
                            result_vector = measurement_vector(result_landmarks, candidate_manifest)
                            delta = (
                                result_vector[candidate["dimension_key"]]
                                - source_vector[candidate["dimension_key"]]
                            )
                            if (direction is TransformDirection.INCREASE and delta <= 0.0) or (
                                direction is TransformDirection.DECREASE and delta >= 0.0
                            ):
                                raise CalibrationFailure(
                                    FailureCode.TARGET_DIRECTION_MISMATCH, "MEASUREMENT"
                                )
                            signature = compute_similarity_signature(
                                output.content,
                                expected_width=output.width,
                                expected_height=output.height,
                                expected_sha256=output.sha256,
                            )
                            output_name = f"{case}-{repeat}.jpg"
                            vision_name = f"{case}-{repeat}.vision.log"
                            output_path = args.output_root / output_name
                            output_path.write_bytes(output.content)
                            (args.output_root / vision_name).write_text(
                                vision_log, encoding="utf-8"
                            )
                            rows.append(
                                {
                                    "case_digest": case,
                                    "identity_reference": entry["identity_reference"],
                                    "candidate": candidate["dimension_key"],
                                    "direction": direction.value,
                                    "magnitude_ppm": magnitude,
                                    "repeat": repeat,
                                    "status": "PASSED",
                                    "source_sha256": entry["normalized_sha256"],
                                    "result_sha256": output.sha256,
                                    "result_artifact": output_name,
                                    "plan_digest": plan.content_digest,
                                    "source_measurements": source_vector,
                                    "result_measurements": result_vector,
                                    "vision_log_sha256": _sha256(vision_log.encode()),
                                    "vision_log_artifact": vision_name,
                                    "phash_hex": signature.phash_hex,
                                    "changed_pixel_count": output.changed_pixel_count,
                                }
                            )
                        cases.append(
                            {
                                "case_digest": case,
                                "identity_reference": entry["identity_reference"],
                                "candidate": candidate["dimension_key"],
                                "direction": direction.value,
                                "magnitude_ppm": magnitude,
                                "status": "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW",
                                "executed_repeat_count": 3,
                            }
                        )
                    except CalibrationFailure as error:
                        cases.append(
                            {
                                "case_digest": case,
                                "identity_reference": entry["identity_reference"],
                                "candidate": candidate["dimension_key"],
                                "direction": direction.value,
                                "magnitude_ppm": magnitude,
                                "status": "FAILED",
                                "failure_stage": error.stage,
                                "failure_code": error.code.value,
                                "executed_repeat_count": len(
                                    [row for row in rows if row["case_digest"] == case]
                                ),
                            }
                        )
                    except (RuntimeError, ValueError) as error:
                        cases.append(
                            {
                                "case_digest": case,
                                "identity_reference": entry["identity_reference"],
                                "candidate": candidate["dimension_key"],
                                "direction": direction.value,
                                "magnitude_ppm": magnitude,
                                "status": "FAILED",
                                "failure_stage": "PLAN_OR_TRANSFORM",
                                "failure_code": (
                                    FailureCode.PLAN_BUILD_FAILED.value
                                    if isinstance(error, ValueError)
                                    else FailureCode.TRANSFORM_FAILED.value
                                ),
                                "executed_repeat_count": len(
                                    [row for row in rows if row["case_digest"] == case]
                                ),
                            }
                        )
    report: dict[str, Any] = {
        "schema": PRIVATE_REPORT_SCHEMA,
        "platform": platform_manifest["platform"],
        "runtime_manifest_digest": runtime.manifest_digest,
        "candidate_manifest_digest": EXPECTED_MANIFEST_DIGEST,
        "model_sha256": candidate_manifest["runtime_authority"]["vision_model_sha256"],
        "topology_sha256": candidate_manifest["runtime_authority"]["topology_sha256"],
        "triangle_count": len(triangles),
        "stage_b_evidence_sha256": platform_manifest["stage_b_evidence_sha256"],
        "cohort_digest": platform_manifest["cohort_digest"],
        "input_manifest_digest": _sha256(args.manifest.read_bytes()),
        "case_set_digest": _sha256(
            "\n".join(sorted(item["case_digest"] for item in cases)).encode()
        ),
        "cases": cases,
        "rows": rows,
    }
    report["report_digest"] = _private_report_digest(report)
    (args.output_root / "private-platform-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def _distribution(values: Sequence[float | int]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "minimum": None, "median": None, "p95": None, "maximum": None}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "median": ordered[(len(ordered) - 1) // 2],
        "p95": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "maximum": ordered[-1],
    }


def _relative_delta(source: float, result: float) -> float:
    if not math.isfinite(source) or not math.isfinite(result) or source <= 0.0:
        raise ValueError("measurement row contains an invalid value")
    return (result - source) / source


def _pairwise_duplicate_evidence(
    groups: dict[tuple[str, ...], list[dict[str, Any]]],
    *,
    content_key: str,
    include_phash: bool,
) -> dict[str, Any]:
    comparison_pairs = 0
    exact_duplicate_pairs = 0
    phash_distances: list[int] = []
    for rows in groups.values():
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                if left["identity_reference"] == right["identity_reference"]:
                    continue
                comparison_pairs += 1
                exact_duplicate_pairs += left[content_key] == right[content_key]
                if include_phash:
                    phash_distances.append(
                        (int(left["phash_hex"], 16) ^ int(right["phash_hex"], 16)).bit_count()
                    )
    return {
        "comparison_pair_count": comparison_pairs,
        "exact_duplicate_pair_count": exact_duplicate_pairs,
        "phash_hamming": _distribution(phash_distances) if include_phash else None,
    }


def _manual_review_digest(review: dict[str, Any]) -> str:
    return _canonical_digest(MANUAL_REVIEW_SCHEMA, review, "content_digest")


def _load_manual_review(
    review_path: Path, rows_by_key: dict[tuple[str, str, int], dict[str, Any]]
) -> tuple[dict[str, dict[str, int | str]], dict[str, Any]]:
    content = review_path.read_bytes()
    review = json.loads(content)
    if (
        not isinstance(review, dict)
        or review.get("schema") != MANUAL_REVIEW_SCHEMA
        or review.get("status") != "COMPLETE"
        or review.get("content_digest") != _manual_review_digest(review)
    ):
        raise ValueError("manual artifact review authority mismatch")
    expected: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    windows = {
        case: row
        for (platform, case, repeat), row in rows_by_key.items()
        if platform == "windows_x86_64" and repeat == 1
    }
    linux = {
        case: row
        for (platform, case, repeat), row in rows_by_key.items()
        if platform == "linux_x86_64_network_none" and repeat == 1
    }
    if set(windows) != set(linux):
        raise ValueError("manual review requires matching qualified platform case sets")
    expected = {case: (windows[case], linux[case]) for case in windows}
    decisions = review.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != len(expected):
        raise ValueError("manual artifact review case coverage is incomplete")
    criteria_keys = {
        "background_seam",
        "disconnected_contour",
        "duplicated_feature",
        "warp_tear",
    }
    by_candidate: dict[str, dict[str, int | str]] = {}
    seen: set[str] = set()
    rejected = 0
    for decision in decisions:
        if not isinstance(decision, dict) or not isinstance(decision.get("case_digest"), str):
            raise ValueError("manual artifact review decision is invalid")
        case = decision["case_digest"]
        if case in seen or case not in expected:
            raise ValueError("manual artifact review case authority mismatch")
        seen.add(case)
        left, right = expected[case]
        if (
            decision.get("windows_result_sha256") != left["result_sha256"]
            or decision.get("linux_result_sha256") != right["result_sha256"]
        ):
            raise ValueError("manual artifact review result checksum mismatch")
        criteria = decision.get("criteria")
        if not isinstance(criteria, dict) or set(criteria) != criteria_keys:
            raise ValueError("manual artifact review criteria are incomplete")
        values = set(criteria.values())
        if not values <= {"PASS", "FAIL"}:
            raise ValueError("manual artifact review criterion is invalid")
        expected_outcome = "PASS" if values == {"PASS"} else "REJECT"
        if decision.get("outcome") != expected_outcome:
            raise ValueError("manual artifact review outcome contradicts criteria")
        candidate = left["candidate"]
        summary = by_candidate.setdefault(
            candidate,
            {
                "status": "COMPLETE",
                "reviewed_case_count": 0,
                "passed_case_count": 0,
                "rejected_case_count": 0,
            },
        )
        summary["reviewed_case_count"] = cast(int, summary["reviewed_case_count"]) + 1
        if expected_outcome == "PASS":
            summary["passed_case_count"] = cast(int, summary["passed_case_count"]) + 1
        else:
            summary["rejected_case_count"] = cast(int, summary["rejected_case_count"]) + 1
            rejected += 1
    if seen != set(expected):
        raise ValueError("manual artifact review case coverage is incomplete")
    overall = {
        "status": "COMPLETE",
        "reviewed_cross_platform_case_count": len(expected),
        "reviewed_artifact_count": len(expected) * 2,
        "rejected_cross_platform_case_count": rejected,
        "private_evidence_sha256": _sha256(content),
        "content_digest": review["content_digest"],
    }
    return by_candidate, overall


def merge_reports(
    windows_path: Path, linux_path: Path, manual_review_path: Path | None = None
) -> dict[str, Any]:
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in (windows_path, linux_path)]
    platforms = {report.get("platform") for report in reports if isinstance(report, dict)}
    if platforms != {"windows_x86_64", "linux_x86_64_network_none"} or len(reports) != 2:
        raise ValueError("merge requires exactly the two preregistered platform reports")
    if (
        len({report.get("cohort_digest") for report in reports}) != 1
        or len({report.get("case_set_digest") for report in reports}) != 1
    ):
        raise ValueError("platform reports do not use the identical frozen cohort and case set")

    candidate_keys = {
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    }
    all_rows: list[tuple[str, dict[str, Any]]] = []
    all_cases: list[tuple[str, dict[str, Any]]] = []
    rows_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    case_sets: list[set[str]] = []
    for report in reports:
        if (
            report.get("schema") != PRIVATE_REPORT_SCHEMA
            or report.get("candidate_manifest_digest") != EXPECTED_MANIFEST_DIGEST
            or report.get("report_digest") != _private_report_digest(report)
        ):
            raise ValueError("private platform report authority mismatch")
        rows, cases = report.get("rows"), report.get("cases")
        if not isinstance(rows, list) or not isinstance(cases, list) or len(cases) != 288:
            raise ValueError("private platform report case coverage is incomplete")
        case_digests = {case.get("case_digest") for case in cases if isinstance(case, dict)}
        if len(case_digests) != 288 or any(not isinstance(value, str) for value in case_digests):
            raise ValueError("private platform case set is invalid")
        case_sets.append({cast(str, value) for value in case_digests})
        for case in cases:
            if (
                not isinstance(case, dict)
                or case.get("candidate") not in candidate_keys
                or case.get("direction") not in {"INCREASE", "DECREASE"}
                or case.get("magnitude_ppm") not in {15000, 30000}
                or case.get("status") not in {"PASSED_PENDING_MANUAL_ARTIFACT_REVIEW", "FAILED"}
            ):
                raise ValueError("private report case is invalid")
            expected = _case_digest(
                case["identity_reference"],
                case["candidate"],
                case["direction"],
                case["magnitude_ppm"],
            )
            if case.get("case_digest") != expected:
                raise ValueError("private report case digest mismatch")
            all_cases.append((report["platform"], case))
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("repeat") not in (1, 2, 3)
                or row.get("candidate") not in candidate_keys
                or row.get("direction") not in {"INCREASE", "DECREASE"}
                or row.get("magnitude_ppm") not in {15000, 30000}
                or row.get("status") != "PASSED"
                or set(row.get("source_measurements", {})) != candidate_keys
                or set(row.get("result_measurements", {})) != candidate_keys
            ):
                raise ValueError("private report row is invalid")
            key = (report["platform"], row["case_digest"], row["repeat"])
            if key in rows_by_key:
                raise ValueError("duplicate transform/Vision row")
            rows_by_key[key] = row
            all_rows.append((report["platform"], row))
        report_rows_by_case: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            report_rows_by_case.setdefault(row["case_digest"], []).append(row)
        identities = {case["identity_reference"] for case in cases}
        if len(identities) != 12:
            raise ValueError("private platform identity coverage is incomplete")
        for case in cases:
            executed = report_rows_by_case.get(case["case_digest"], [])
            if (
                case.get("executed_repeat_count") != len(executed)
                or {row["repeat"] for row in executed} != set(range(1, len(executed) + 1))
                or (
                    case["status"] == "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW" and len(executed) != 3
                )
                or (case["status"] == "FAILED" and len(executed) > 2)
            ):
                raise ValueError("private platform row count does not match case execution")
    if case_sets[0] != case_sets[1]:
        raise ValueError("Windows and Linux case identities differ")

    source_rows_by_platform_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for platform, row in all_rows:
        source_identity_key = (platform, row["identity_reference"])
        previous = source_rows_by_platform_identity.setdefault(source_identity_key, row)
        if previous["source_sha256"] != row["source_sha256"]:
            raise ValueError("identity source checksum is inconsistent within a platform")
    source_groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for (platform, _), row in source_rows_by_platform_identity.items():
        source_groups.setdefault((platform,), []).append(row)
    source_duplicate_evidence = _pairwise_duplicate_evidence(
        source_groups, content_key="source_sha256", include_phash=False
    )
    manual_by_candidate: dict[str, dict[str, int | str]] = {}
    manual_overall: dict[str, Any] = {
        "status": "PENDING",
        "reviewed_cross_platform_case_count": 0,
        "reviewed_artifact_count": 0,
        "rejected_cross_platform_case_count": 0,
        "private_evidence_sha256": None,
        "content_digest": None,
    }
    if manual_review_path is not None:
        manual_by_candidate, manual_overall = _load_manual_review(manual_review_path, rows_by_key)

    outcomes: list[dict[str, Any]] = []
    for candidate in sorted(candidate_keys):
        candidate_cases = [(p, c) for p, c in all_cases if c["candidate"] == candidate]
        candidate_rows = [(p, r) for p, r in all_rows if r["candidate"] == candidate]
        target_deltas: list[float] = []
        target_errors: list[float] = []
        control_drifts: list[float] = []
        for _, row in candidate_rows:
            target = row["candidate"]
            measured = _relative_delta(
                row["source_measurements"][target], row["result_measurements"][target]
            )
            requested = row["magnitude_ppm"] / 1_000_000
            if row["direction"] == "DECREASE":
                requested = -requested
            target_deltas.append(measured)
            target_errors.append(abs(measured - requested))
            control_drifts.append(
                max(
                    abs(
                        _relative_delta(
                            row["source_measurements"][key], row["result_measurements"][key]
                        )
                    )
                    for key in candidate_keys - {target}
                )
            )
        repeat_variance: list[float] = []
        for platform in platforms:
            for case_digest in case_sets[0]:
                repeated = [
                    rows_by_key.get((platform, case_digest, repeat)) for repeat in (1, 2, 3)
                ]
                repeated_rows = [row for row in repeated if row is not None]
                if len(repeated_rows) == 3 and all(
                    row["candidate"] == candidate for row in repeated_rows
                ):
                    for dimension in candidate_keys:
                        values = [row["result_measurements"][dimension] for row in repeated_rows]
                        repeat_variance.append(max(values) - min(values))
        platform_variance: list[float] = []
        for case_digest in case_sets[0]:
            for repeat in (1, 2, 3):
                left = rows_by_key.get(("windows_x86_64", case_digest, repeat))
                right = rows_by_key.get(("linux_x86_64_network_none", case_digest, repeat))
                if left is not None and right is not None and left["candidate"] == candidate:
                    platform_variance.extend(
                        abs(left["result_measurements"][key] - right["result_measurements"][key])
                        for key in candidate_keys
                    )
        variant_groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for platform, row in candidate_rows:
            if row["repeat"] == 1:
                group = (platform, row["direction"], str(row["magnitude_ppm"]))
                variant_groups.setdefault(group, []).append(row)
        variant_duplicate_evidence = _pairwise_duplicate_evidence(
            variant_groups, content_key="result_sha256", include_phash=True
        )
        failed_case_count = sum(case["status"] == "FAILED" for _, case in candidate_cases)
        manual_summary = manual_by_candidate.get(
            candidate,
            {
                "status": "PENDING",
                "reviewed_case_count": 0,
                "passed_case_count": 0,
                "rejected_case_count": 0,
            },
        )
        if failed_case_count:
            stage_d_consideration = "INELIGIBLE_INCOMPLETE_CASE_COVERAGE"
        elif manual_summary["status"] != "COMPLETE":
            stage_d_consideration = "INELIGIBLE_MANUAL_REVIEW_PENDING"
        elif cast(int, manual_summary["rejected_case_count"]):
            stage_d_consideration = "INELIGIBLE_MANUAL_ARTIFACT_REJECTION"
        else:
            stage_d_consideration = "ELIGIBLE_FOR_STAGE_D_PREREGISTRATION_ONLY"
        outcomes.append(
            {
                "candidate": candidate,
                "case_count": len(candidate_cases),
                "failed_case_count": failed_case_count,
                "failure_reason_counts": {
                    code: sum(
                        case.get("failure_code") == code
                        for _, case in candidate_cases
                        if case["status"] == "FAILED"
                    )
                    for code in sorted(
                        cast(str, case["failure_code"])
                        for _, case in candidate_cases
                        if isinstance(case.get("failure_code"), str)
                    )
                },
                "transform_vision_row_count": len(candidate_rows),
                "manual_artifact_review": manual_summary,
                "target_relative_delta": _distribution(target_deltas),
                "target_error": _distribution(target_errors),
                "maximum_normalized_control_drift": _distribution(control_drifts),
                "same_platform_repeat_measurement_variance": _distribution(repeat_variance),
                "cross_platform_measurement_variance": _distribution(platform_variance),
                "variant_duplicate_evidence": variant_duplicate_evidence,
                "near_duplicate_threshold": None,
                "stage_d_consideration": stage_d_consideration,
                "ready_decision": "NOT_PERMITTED_IN_STAGE_C",
            }
        )
    return {
        "schema": AGGREGATE_SCHEMA,
        "status": (
            "CALIBRATION_COMPLETE_NO_STAGE_D_DECISION"
            if manual_review_path is not None
            else "CALIBRATION_AGGREGATE_PENDING_MANUAL_REVIEW_NO_STAGE_D_DECISION"
        ),
        "platform_count": 2,
        "cohort_digest": reports[0]["cohort_digest"],
        "case_set_digest": reports[0]["case_set_digest"],
        "transform_vision_row_count": len(all_rows),
        "unique_cross_platform_case_count": len(case_sets[0]),
        "source_duplicate_evidence": source_duplicate_evidence,
        "manual_artifact_review": manual_overall,
        "failure_reason_counts": {
            code: sum(
                case.get("failure_code") == code
                for _, case in all_cases
                if case["status"] == "FAILED"
            )
            for code in sorted(
                cast(str, case["failure_code"])
                for _, case in all_cases
                if isinstance(case.get("failure_code"), str)
            )
        },
        "candidate_outcomes": outcomes,
        "stage_d_eligible_candidate_count": sum(
            item["stage_d_consideration"] == "ELIGIBLE_FOR_STAGE_D_PREREGISTRATION_ONLY"
            for item in outcomes
        ),
        "stage_d_required_candidate_count": 4,
        "thresholds_selected": False,
        "stage_d_opened": False,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build-input")
    build_parser.add_argument("--candidate-manifest", type=Path, required=True)
    build_parser.add_argument("--stage-b-evidence", type=Path, required=True)
    build_parser.add_argument("--platform", choices=tuple(RUNTIME_FILENAMES), required=True)
    build_parser.add_argument("--normalized-dir", type=Path, required=True)
    build_parser.add_argument("--vision-log-dir", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    run_parser = subparsers.add_parser("run-platform")
    run_parser.add_argument("--candidate-manifest", type=Path, required=True)
    run_parser.add_argument("--stage-b-evidence", type=Path, required=True)
    run_parser.add_argument("--manifest", type=Path, required=True)
    run_parser.add_argument("--runtime-root", type=Path, required=True)
    run_parser.add_argument("--vision-executable", type=Path, required=True)
    run_parser.add_argument("--model", type=Path, required=True)
    run_parser.add_argument("--topology", type=Path, required=True)
    run_parser.add_argument("--output-root", type=Path, required=True)
    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--windows-report", type=Path, required=True)
    merge_parser.add_argument("--linux-report", type=Path, required=True)
    merge_parser.add_argument("--manual-review", type=Path)
    merge_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    if args.command == "build-input":
        manifest = build_platform_manifest(args)
        print(f"PLATFORM={manifest['platform']}")
        print(f"COHORT_DIGEST={manifest['cohort_digest']}")
        return
    if args.command == "run-platform":
        report = run(args)
        print(f"PLATFORM={report['platform']}")
        print(f"TRANSFORM_VISION_ROWS={len(report['rows'])}")
        print(f"PRIVATE_REPORT_DIGEST={report['report_digest']}")
        return
    aggregate = merge_reports(args.windows_report, args.linux_report, args.manual_review)
    if args.output.exists():
        raise FileExistsError("redacted aggregate output must not already exist")
    args.output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TRANSFORM_VISION_ROWS={aggregate['transform_vision_row_count']}")
    print("REDACTED_CALIBRATION_AGGREGATE_COMPLETE=YES")


if __name__ == "__main__":
    main()
