"""Stdlib-only ctypes harness for the frozen Project Mirror OpenCV remap C ABI."""

from __future__ import annotations

import argparse
import array
import contextlib
import ctypes
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

CANDIDATE_ID = "OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2"
SCHEMA_VERSION = "mirror.p2-m4.opencv-minimal-poc/v1"
SAMPLE_COUNT = 12


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


@contextlib.contextmanager
def _dll_directory(library: Path) -> Iterator[None]:
    if os.name == "nt":
        with os.add_dll_directory(str(library.parent)):
            yield
    else:
        yield


def _load_library(library: Path) -> ctypes.CDLL:
    with _dll_directory(library):
        loaded = ctypes.CDLL(str(library.resolve()))
    loaded.mirror_opencv_runtime_version.argtypes = []
    loaded.mirror_opencv_runtime_version.restype = ctypes.c_char_p
    loaded.mirror_opencv_remap_rgb_u8.argtypes = [
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_int32,
        ctypes.c_int32,
        ctypes.c_ssize_t,
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_ssize_t,
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_ssize_t,
    ]
    loaded.mirror_opencv_remap_rgb_u8.restype = ctypes.c_int32
    return loaded


def _fixture(size: int) -> bytearray:
    source = bytearray(size * size * 3)
    offset = 0
    for y in range(size):
        blue = ((y // 8) % 2) * 255
        for x in range(size):
            source[offset] = (x * 17 + y * 3) % 256
            source[offset + 1] = ((x // 8) % 2) * 255
            source[offset + 2] = blue
            offset += 3
    return source


def _maps(size: int) -> tuple[array.array[float], array.array[float]]:
    map_x = array.array("f")
    map_y = array.array("f")
    band_height = max(1, size // 8)
    left = size * 0.2
    right = size * 0.8
    for y in range(size):
        band = (y // band_height) % 3 - 1
        displacement = band * 2.0 + 0.25
        for x in range(size):
            map_x.append(float(x) + (displacement if left <= x < right else 0.0))
            map_y.append(float(y))
    return map_x, map_y


def _buffers(
    source: bytearray,
    map_x: array.array[float],
    map_y: array.array[float],
) -> tuple[Any, Any, Any, bytearray, Any]:
    output = bytearray(len(source))
    source_view = (ctypes.c_uint8 * len(source)).from_buffer(source)
    map_x_view = (ctypes.c_float * len(map_x)).from_buffer(map_x)
    map_y_view = (ctypes.c_float * len(map_y)).from_buffer(map_y)
    output_view = (ctypes.c_uint8 * len(output)).from_buffer(output)
    return source_view, map_x_view, map_y_view, output, output_view


def _call(
    library: ctypes.CDLL,
    size: int,
    source_view: Any,
    map_x_view: Any,
    map_y_view: Any,
    output_view: Any,
) -> int:
    return int(
        library.mirror_opencv_remap_rgb_u8(
            source_view,
            size,
            size,
            size * 3,
            map_x_view,
            map_y_view,
            size * 4,
            output_view,
            size * 3,
        )
    )


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _fixture_result(
    library: ctypes.CDLL, size: int, artifact_dir: Path
) -> tuple[dict[str, Any], list[float]]:
    source = _fixture(size)
    map_x, map_y = _maps(size)
    source_view, map_x_view, map_y_view, output, output_view = _buffers(source, map_x, map_y)
    if _call(library, size, source_view, map_x_view, map_y_view, output_view) != 0:
        raise RuntimeError("REMAP_FAILED")
    expected = bytes(output)
    if expected == bytes(source):
        raise RuntimeError("NON_ZERO_REQUEST_PRODUCED_IDENTICAL_OUTPUT")

    samples: list[float] = []
    for _ in range(SAMPLE_COUNT):
        started = time.perf_counter_ns()
        if _call(library, size, source_view, map_x_view, map_y_view, output_view) != 0:
            raise RuntimeError("REMAP_REPLAY_FAILED")
        samples.append((time.perf_counter_ns() - started) / 1_000_000.0)
        if bytes(output) != expected:
            raise RuntimeError("IN_PROCESS_REPLAY_MISMATCH")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / f"result-{size}.rgb").write_bytes(expected)
    changed = sum(
        source[offset : offset + 3] != expected[offset : offset + 3]
        for offset in range(0, len(source), 3)
    )
    return (
        {
            "size": size,
            "source_sha256": _sha256(bytes(source)),
            "result_sha256": _sha256(expected),
            "map_x_sha256": _sha256(map_x.tobytes()),
            "map_y_sha256": _sha256(map_y.tobytes()),
            "changed_pixel_count": changed,
            "total_pixel_count": size * size,
            "output_min": min(expected),
            "output_max": max(expected),
        },
        samples,
    )


def _signed_area(points: tuple[tuple[float, float], ...]) -> float:
    first, second, third = points
    first_edge = (second[0] - first[0], second[1] - first[1])
    second_edge = (third[0] - first[0], third[1] - first[1])
    return (first_edge[0] * second_edge[1] - first_edge[1] * second_edge[0]) / 2.0


def _negative_controls(library: ctypes.CDLL) -> dict[str, bool]:
    size = 8
    source = _fixture(size)
    map_x, map_y = _maps(size)
    source_view, map_x_view, map_y_view, _, output_view = _buffers(source, map_x, map_y)
    remap = library.mirror_opencv_remap_rgb_u8
    null_source = int(
        remap(None, size, size, size * 3, map_x_view, map_y_view, size * 4, output_view, size * 3)
    )
    zero_edge = int(
        remap(
            source_view, 0, size, size * 3, map_x_view, map_y_view, size * 4, output_view, size * 3
        )
    )
    short_stride = int(
        remap(
            source_view,
            size,
            size,
            size * 3 - 1,
            map_x_view,
            map_y_view,
            size * 4,
            output_view,
            size * 3,
        )
    )
    original = map_x[0]
    map_x[0] = math.nan
    nan_map = int(
        remap(
            source_view,
            size,
            size,
            size * 3,
            map_x_view,
            map_y_view,
            size * 4,
            output_view,
            size * 3,
        )
    )
    map_x[0] = float(size)
    range_map = int(
        remap(
            source_view,
            size,
            size,
            size * 3,
            map_x_view,
            map_y_view,
            size * 4,
            output_view,
            size * 3,
        )
    )
    map_x[0] = original
    valid = ((0.1, 0.1), (0.9, 0.1), (0.5, 0.9))
    folded = ((0.1, 0.1), (0.5, 0.9), (0.9, 0.1))
    collapsed = ((0.1, 0.1), (0.5, 0.1), (0.9, 0.1))
    return {
        "null_source_code_10": null_source == 10,
        "zero_edge_code_11": zero_edge == 11,
        "short_stride_code_12": short_stride == 12,
        "nan_map_code_13": nan_map == 13,
        "range_map_code_13": range_map == 13,
        "valid_triangle_positive": _signed_area(valid) > 0.0,
        "foldover_rejected": _signed_area(folded) <= 0.0,
        "collapsed_rejected": _signed_area(collapsed) <= 0.0,
    }


def run(library_path: Path, artifact_dir: Path) -> dict[str, Any]:
    if sys.byteorder != "little":
        raise RuntimeError("UNSUPPORTED_BYTE_ORDER")
    library = _load_library(library_path)
    version_bytes = library.mirror_opencv_runtime_version()
    if version_bytes is None:
        raise RuntimeError("MISSING_RUNTIME_VERSION")
    small, small_samples = _fixture_result(library, 256, artifact_dir)
    large, large_samples = _fixture_result(library, 1024, artifact_dir)
    negatives = _negative_controls(library)
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
        "numeric_sha256": _sha256(_canonical_json(numeric)),
        "negative_controls": negatives,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": CANDIDATE_ID,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "opencv": version_bytes.decode("ascii"),
            "abi": "ctypes-c-v1",
        },
        "deterministic": deterministic,
        "deterministic_sha256": _sha256(_canonical_json(deterministic)),
        "performance": {
            "warm_256_median_ms": round(statistics.median(small_samples), 6),
            "warm_256_p95_ms": round(_p95(small_samples), 6),
            "warm_1024_median_ms": round(statistics.median(large_samples), 6),
            "warm_1024_p95_ms": round(_p95(large_samples), 6),
            "sample_count_each": SAMPLE_COUNT,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.library, args.artifact_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_json(report) + b"\n")
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
