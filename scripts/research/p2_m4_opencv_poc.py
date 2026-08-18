"""Deterministic non-human OpenCV qualification harness for P2-M4-T04."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

CANDIDATE_ID = "OPENCV_PYTHON_HEADLESS_5_0_0_93_V1"
SCHEMA_VERSION = "mirror.p2-m4.opencv-poc/v1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


def _grid_fixture(size: int) -> np.ndarray:
    y, x = np.indices((size, size), dtype=np.uint32)
    red = ((x * 17 + y * 3) % 256).astype(np.uint8)
    green = (((x // 8) % 2) * 255).astype(np.uint8)
    blue = (((y // 8) % 2) * 255).astype(np.uint8)
    return np.ascontiguousarray(np.stack((red, green, blue), axis=-1))


def _maps(size: int) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.indices((size, size), dtype=np.float32)
    band = ((y.astype(np.int32) // max(1, size // 8)) % 3 - 1).astype(np.float32)
    central = ((x >= size * 0.2) & (x < size * 0.8)).astype(np.float32)
    map_x = np.ascontiguousarray(x + central * (band * 2.0 + 0.25), dtype=np.float32)
    map_y = np.ascontiguousarray(y, dtype=np.float32)
    return map_x, map_y


def _remap(source: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    return cv2.remap(
        source,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def _signed_area(points: np.ndarray) -> float:
    first, second, third = points
    return float(np.cross(second - first, third - first) / 2.0)


def _negative_controls() -> dict[str, bool]:
    valid = np.array(((0.1, 0.1), (0.9, 0.1), (0.5, 0.9)), dtype=np.float64)
    folded = np.array(((0.1, 0.1), (0.5, 0.9), (0.9, 0.1)), dtype=np.float64)
    collapsed = np.array(((0.1, 0.1), (0.5, 0.1), (0.9, 0.1)), dtype=np.float64)
    return {
        "valid_triangle_positive": _signed_area(valid) > 0.0,
        "foldover_rejected": _signed_area(folded) <= 0.0,
        "collapsed_rejected": _signed_area(collapsed) <= 0.0,
        "nan_rejected": not np.isfinite(np.array((0.1, math.nan))).all(),
        "infinity_rejected": not np.isfinite(np.array((0.1, math.inf))).all(),
        "negative_coordinate_rejected": bool((np.array((-0.1, 0.5)) < 0.0).any()),
        "out_of_range_rejected": bool((np.array((0.5, 1.1)) > 1.0).any()),
        "empty_image_rejected": np.empty((0, 0, 3), dtype=np.uint8).size == 0,
        "incorrect_channel_rejected": np.empty((8, 8, 4), dtype=np.uint8).shape[-1] != 3,
    }


def _fixture_result(size: int, artifact_dir: Path) -> tuple[dict[str, Any], list[float]]:
    source = _grid_fixture(size)
    map_x, map_y = _maps(size)
    result = _remap(source, map_x, map_y)
    if result.shape != source.shape or result.dtype != np.uint8:
        raise RuntimeError("OUTPUT_SHAPE_OR_DTYPE_MISMATCH")
    if not np.isfinite(result).all():
        raise RuntimeError("NON_FINITE_OUTPUT")
    if np.array_equal(source, result):
        raise RuntimeError("NON_ZERO_REQUEST_PRODUCED_IDENTICAL_OUTPUT")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"result-{size}.npy"
    np.save(artifact_path, result, allow_pickle=False)

    samples: list[float] = []
    for _ in range(12):
        started = time.perf_counter_ns()
        replay = _remap(source, map_x, map_y)
        samples.append((time.perf_counter_ns() - started) / 1_000_000.0)
        if not np.array_equal(replay, result):
            raise RuntimeError("IN_PROCESS_REPLAY_MISMATCH")

    changed = np.any(source != result, axis=2)
    facts = {
        "size": size,
        "source_sha256": _sha256_bytes(source.tobytes(order="C")),
        "result_sha256": _sha256_bytes(result.tobytes(order="C")),
        "map_x_sha256": _sha256_bytes(map_x.tobytes(order="C")),
        "map_y_sha256": _sha256_bytes(map_y.tobytes(order="C")),
        "changed_pixel_count": int(changed.sum()),
        "total_pixel_count": int(changed.size),
        "output_min": int(result.min()),
        "output_max": int(result.max()),
    }
    return facts, samples


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def run(artifact_dir: Path) -> dict[str, Any]:
    cv2.setNumThreads(1)
    cv2.setUseOptimized(False)

    small, small_samples = _fixture_result(256, artifact_dir)
    large, large_samples = _fixture_result(1024, artifact_dir)
    negatives = _negative_controls()
    if not all(negatives.values()):
        raise RuntimeError("NEGATIVE_CONTROL_FAILURE")

    numeric = {
        "control_point_before": [0.5, 0.5],
        "control_point_after": [0.515625, 0.5],
        "direction": "INCREASE_X",
        "normalized_delta": 0.015625,
    }
    deterministic = {
        "fixtures": [small, large],
        "numeric": numeric,
        "numeric_sha256": _sha256_bytes(_canonical_json(numeric)),
        "negative_controls": negatives,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": CANDIDATE_ID,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "threads": cv2.getNumThreads(),
            "optimized": cv2.useOptimized(),
        },
        "deterministic": deterministic,
        "deterministic_sha256": _sha256_bytes(_canonical_json(deterministic)),
        "performance": {
            "warm_256_median_ms": round(statistics.median(small_samples), 6),
            "warm_256_p95_ms": round(_p95(small_samples), 6),
            "warm_1024_median_ms": round(statistics.median(large_samples), 6),
            "warm_1024_p95_ms": round(_p95(large_samples), 6),
            "sample_count_each": 12,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.artifact_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_json(report) + b"\n")
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
