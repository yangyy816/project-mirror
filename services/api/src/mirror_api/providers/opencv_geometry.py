"""Private synthetic OpenCV geometry adapter with an exact native-runtime manifest."""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import os
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mirror_api.image_sanitizer import (
    ImageSanitizationError,
    canonicalize_rgb_image,
    decode_canonical_rgb_image,
)
from mirror_api.synthetic_dataset.domain import DomainValidationError, ReasonCode
from mirror_api.synthetic_dataset.geometry_transform import (
    DenseRemap,
    GeometryTransformRequest,
    GeometryTransformResult,
    build_dense_remap,
)

CANDIDATE_ID = "OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2"
ALGORITHM_VERSION = "opencv-piecewise-affine-v1"
RUNTIME_VERSION = "5.0.0"
RUNTIME_ABI = "ctypes-c-v1"
RUNTIME_MANIFEST_SCHEMA = "mirror.p2-m4.opencv-runtime-manifest/v1"

_WINDOWS_FILES: Mapping[str, str] = {
    "mirror_opencv_remap.dll": "2d7a2722d386ad3796045d0992da5cf7edc7ce4c4c07cc10ae6b3e44972829a3",
    "opencv_core500.dll": "ef313484c24614ab9b3b263a46ecb930ae621b0e969d001c2583dcada483905f",
    "opencv_flann500.dll": "1c7e087b02cd541a3205e58c800e9edf61483f49fda193ad1d90fee703923232",
    "opencv_geometry500.dll": "a91f8ecc0f1f22d3c60e72e1c875beb242a17357d121f18497f2c4b00ce01144",
    "opencv_imgproc500.dll": "6baf90843b20fa07b8e9b95c38ccbcc4c0f83d44191de1cc29febd27c17dc2d3",
}
_LINUX_FILES: Mapping[str, str] = {
    "libmirror_opencv_remap.so": "9ce503f8e5e1186269c8ef37d00a26ab04c40c9681d4a043d2ea94e2e4a861dd",
    "libopencv_core.so.5.0.0": "1984bb9695ffb5b628809f23d0026fd49c30a8e3ed6093040e6fc7c54e5bd9ab",
    "libopencv_flann.so.5.0.0": "b3afa2bc31b96fec8bcab48e8f47ff9a9618a236e9fcf3a5298ee8124f8f3fff",
    "libopencv_geometry.so.5.0.0": (
        "31095c77a09445c2a876dc2ea17db87c1edca051213261f3a6443274b3198e39"
    ),
    "libopencv_imgproc.so.5.0.0": (
        "5eb430711d7883602d694c8cfbd021edb9ce345ad311e65531aa13d1e31cbb89"
    ),
}
_LINUX_LINKS: Mapping[str, str] = {
    "libopencv_core.so": "libopencv_core.so.5.0.0",
    "libopencv_core.so.500": "libopencv_core.so.5.0.0",
    "libopencv_flann.so": "libopencv_flann.so.5.0.0",
    "libopencv_flann.so.500": "libopencv_flann.so.5.0.0",
    "libopencv_geometry.so": "libopencv_geometry.so.5.0.0",
    "libopencv_geometry.so.500": "libopencv_geometry.so.5.0.0",
    "libopencv_imgproc.so": "libopencv_imgproc.so.5.0.0",
    "libopencv_imgproc.so.500": "libopencv_imgproc.so.5.0.0",
}


@dataclass(frozen=True)
class OpenCvRuntimeManifest:
    platform: str
    file_sha256: tuple[tuple[str, str], ...]
    symlinks: tuple[tuple[str, str], ...]
    content_digest: str


class RemapRuntime(Protocol):
    candidate_id: str
    runtime_version: str
    manifest_digest: str

    def remap_rgb(self, *, source: bytes, remap: DenseRemap) -> bytes: ...


class OpenCvGeometryTransform:
    """Execute only a first-party map through the qualified private runtime."""

    def __init__(self, runtime: RemapRuntime) -> None:
        self._runtime = runtime

    def transform(self, *, request: GeometryTransformRequest) -> GeometryTransformResult:
        if (
            self._runtime.candidate_id != CANDIDATE_ID
            or self._runtime.runtime_version != RUNTIME_VERSION
            or request.specification.algorithm_version != ALGORITHM_VERSION
            or request.specification.runtime_manifest_digest != self._runtime.manifest_digest
            or request.specification.output_policy_version != "image-sanitizer-v1"
        ):
            raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
        remap = build_dense_remap(
            request.warp_plan,
            width=request.source.width,
            height=request.source.height,
        )
        try:
            decoded = decode_canonical_rgb_image(
                request.source.content,
                expected_width=request.source.width,
                expected_height=request.source.height,
            )
            output_rgb = self._runtime.remap_rgb(source=decoded.bytes_value, remap=remap)
            if type(output_rgb) is not bytes or len(output_rgb) != len(decoded.bytes_value):
                raise DomainValidationError(ReasonCode.TRANSFORM_OUTPUT_INVALID)
            if output_rgb == decoded.bytes_value:
                raise DomainValidationError(ReasonCode.SOURCE_RESULT_IDENTICAL)
            canonical = canonicalize_rgb_image(
                output_rgb,
                width=decoded.width,
                height=decoded.height,
            )
        except DomainValidationError:
            raise
        except ImageSanitizationError:
            raise DomainValidationError(ReasonCode.TRANSFORM_OUTPUT_INVALID) from None
        if canonical.sha256 == request.source.sha256:
            raise DomainValidationError(ReasonCode.SOURCE_RESULT_IDENTICAL)
        return GeometryTransformResult(
            content=canonical.bytes_value,
            sha256=canonical.sha256,
            width=canonical.width,
            height=canonical.height,
            changed_pixel_count=remap.changed_pixel_count,
            runtime_version=self._runtime.runtime_version,
            runtime_manifest_digest=self._runtime.manifest_digest,
            warp_plan_digest=request.warp_plan.content_digest,
        )


class NativeOpenCvRemapRuntime:
    candidate_id = CANDIDATE_ID
    runtime_version = RUNTIME_VERSION

    def __init__(self, *, library: ctypes.CDLL, manifest: OpenCvRuntimeManifest) -> None:
        self._library = library
        self.manifest_digest = manifest.content_digest

    def remap_rgb(self, *, source: bytes, remap: DenseRemap) -> bytes:
        expected = remap.width * remap.height * 3
        if type(source) is not bytes or len(source) != expected:
            raise DomainValidationError(ReasonCode.TRANSFORM_OUTPUT_INVALID)
        source_buffer = (ctypes.c_uint8 * expected).from_buffer_copy(source)
        map_count = remap.width * remap.height
        map_x = (ctypes.c_float * map_count).from_buffer_copy(remap.map_x_float32_le)
        map_y = (ctypes.c_float * map_count).from_buffer_copy(remap.map_y_float32_le)
        output = (ctypes.c_uint8 * expected)()
        result = int(
            self._library.mirror_opencv_remap_rgb_u8(
                source_buffer,
                remap.width,
                remap.height,
                remap.width * 3,
                map_x,
                map_y,
                remap.width * 4,
                output,
                remap.width * 3,
            )
        )
        if result != 0:
            raise DomainValidationError(ReasonCode.TRANSFORM_OUTPUT_INVALID)
        return bytes(output)


def load_private_opencv_runtime(runtime_root: Path) -> NativeOpenCvRemapRuntime:
    """Verify the complete fixed runtime identity before loading any native code."""
    root = _resolve_runtime_root(runtime_root)
    if sys.platform == "win32":
        files = _WINDOWS_FILES
        links: Mapping[str, str] = {}
        library_name = "mirror_opencv_remap.dll"
    elif sys.platform == "linux":
        files = _LINUX_FILES
        links = _LINUX_LINKS
        library_name = "libmirror_opencv_remap.so"
    else:
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    _verify_directory_shape(root, files=files, links=links)
    manifest = _manifest(platform=sys.platform, files=files, links=links)
    try:
        with _dll_directory(root):
            library = ctypes.CDLL(str(root / library_name))
        _configure_library(library)
        version_value = library.mirror_opencv_runtime_version()
        version = version_value.decode("ascii", errors="strict")
    except (OSError, UnicodeError, AttributeError):
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH) from None
    if version != RUNTIME_VERSION:
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    return NativeOpenCvRemapRuntime(library=library, manifest=manifest)


def _resolve_runtime_root(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute() or value.is_symlink():
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    try:
        resolved = value.resolve(strict=True)
    except OSError:
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH) from None
    if not resolved.is_dir() or resolved != value:
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    return resolved


def _verify_directory_shape(
    root: Path, *, files: Mapping[str, str], links: Mapping[str, str]
) -> None:
    try:
        entries = {entry.name: entry for entry in root.iterdir()}
    except OSError:
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH) from None
    if set(entries) != set(files) | set(links):
        raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    for name, expected_sha256 in files.items():
        candidate = entries[name]
        if candidate.is_symlink() or not candidate.is_file():
            raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
        try:
            actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError:
            raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH) from None
        if actual != expected_sha256:
            raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
    for name, target in links.items():
        candidate = entries[name]
        if not candidate.is_symlink() or os.readlink(candidate) != target:
            raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)


def _manifest(
    *, platform: str, files: Mapping[str, str], links: Mapping[str, str]
) -> OpenCvRuntimeManifest:
    file_facts = tuple(sorted(files.items()))
    link_facts = tuple(sorted(links.items()))
    facts = {
        "abi": RUNTIME_ABI,
        "candidate_id": CANDIDATE_ID,
        "files": [list(item) for item in file_facts],
        "platform": platform,
        "runtime_version": RUNTIME_VERSION,
        "symlinks": [list(item) for item in link_facts],
    }
    canonical = json.dumps(facts, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(f"{RUNTIME_MANIFEST_SCHEMA}\n{canonical}".encode()).hexdigest()
    return OpenCvRuntimeManifest(
        platform=platform,
        file_sha256=file_facts,
        symlinks=link_facts,
        content_digest=digest,
    )


@contextlib.contextmanager
def _dll_directory(root: Path) -> Iterator[None]:
    if os.name == "nt":
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is None:
            raise DomainValidationError(ReasonCode.TRANSFORM_RUNTIME_MISMATCH)
        with add_dll_directory(str(root)):
            yield
    else:
        yield


def _configure_library(library: ctypes.CDLL) -> None:
    library.mirror_opencv_runtime_version.argtypes = []
    library.mirror_opencv_runtime_version.restype = ctypes.c_char_p
    library.mirror_opencv_remap_rgb_u8.argtypes = [
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
    library.mirror_opencv_remap_rgb_u8.restype = ctypes.c_int32
