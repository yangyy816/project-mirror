"""Principal-only composition of explicit private D02 runtime locators.

The tracked runtime identities never contain host paths.  This loader consumes
one fixed ignored handoff file supplied by the D02 Principal, validates its
exact schema, and passes the explicit locators into the accepted runtime
factories.  It never searches a directory or renders a locator in an error.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, NoReturn

from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_private_m4_backend import D02OpenCvM4Backend
from mirror_api.demo_d02_private_vision_backend import WindowsFaceLandmarkerOfflineM3Backend
from mirror_api.demo_d02_r2_runtime_forward import SourceMaterial, build_default_model_identity

RUNTIME_LOCATOR_HANDOFF_SCHEMA: Final = "mirror.private/D02RuntimeLocatorHandoff/v1"
RUNTIME_LOCATOR_HANDOFF_RELATIVE: Final = Path(".private-handoff") / "D02_RUNTIME_LOCATORS.json"
EXPECTED_M4_RUNTIME_MANIFEST_DIGEST: Final = (
    "27b33d646d8587f76d5ca317ac9d6aec95bc04fd87d413bb3dd6394f9694bb7a"
)


class D02RuntimeCompositionError(RuntimeError):
    """A private runtime handoff failed without disclosing a locator."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class D02RuntimeLocators:
    vision_executable: Path = field(repr=False)
    vision_face_landmarker_dll: Path = field(repr=False)
    vision_opencv_core_dll: Path = field(repr=False)
    vision_opencv_imgproc_dll: Path = field(repr=False)
    vision_model: Path = field(repr=False)
    topology_file: Path = field(repr=False)
    m4_runtime_root: Path = field(repr=False)


def load_runtime_locators(*, workspace_root: Path) -> D02RuntimeLocators:
    root = _exact_directory(workspace_root, "D02_WORKSPACE_INVALID")
    handoff = root / RUNTIME_LOCATOR_HANDOFF_RELATIVE
    content = _read_exact_file(handoff, maximum_bytes=65_536)
    try:
        value = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise D02RuntimeCompositionError("RUNTIME_LOCATOR_HANDOFF_INVALID") from error
    expected = {
        "schema_version",
        "authority",
        "runtime_identity_digest",
        "model_identity_digest",
        "topology_digest",
        "m4_runtime_manifest_digest",
        "vision_executable",
        "vision_face_landmarker_dll",
        "vision_opencv_core_dll",
        "vision_opencv_imgproc_dll",
        "vision_model",
        "topology_file",
        "m4_runtime_root",
    }
    model = build_default_model_identity()
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or value.get("schema_version") != RUNTIME_LOCATOR_HANDOFF_SCHEMA
        or value.get("authority") != "D02_SUBSYSTEM_PRINCIPAL"
        or value.get("runtime_identity_digest") != measurement.RUNTIME_MANIFEST_DIGEST
        or value.get("model_identity_digest") != model.identity_digest
        or value.get("topology_digest") != measurement.TOPOLOGY_DIGEST
        or value.get("m4_runtime_manifest_digest") != EXPECTED_M4_RUNTIME_MANIFEST_DIGEST
    ):
        _fail("RUNTIME_LOCATOR_HANDOFF_AUTHORITY_MISMATCH")
    paths: dict[str, Path] = {}
    for name in (
        "vision_executable",
        "vision_face_landmarker_dll",
        "vision_opencv_core_dll",
        "vision_opencv_imgproc_dll",
        "vision_model",
        "topology_file",
        "m4_runtime_root",
    ):
        raw = value.get(name)
        if not isinstance(raw, str) or not raw:
            _fail("RUNTIME_LOCATOR_HANDOFF_INVALID")
        path = Path(raw)
        if not path.is_absolute():
            _fail("RUNTIME_LOCATOR_HANDOFF_INVALID")
        paths[name] = path
    return D02RuntimeLocators(
        vision_executable=paths["vision_executable"],
        vision_face_landmarker_dll=paths["vision_face_landmarker_dll"],
        vision_opencv_core_dll=paths["vision_opencv_core_dll"],
        vision_opencv_imgproc_dll=paths["vision_opencv_imgproc_dll"],
        vision_model=paths["vision_model"],
        topology_file=paths["topology_file"],
        m4_runtime_root=paths["m4_runtime_root"],
    )


def compose_accepted_m3_backend(
    *,
    locators: D02RuntimeLocators,
    staging_root: Path,
) -> WindowsFaceLandmarkerOfflineM3Backend:
    if type(locators) is not D02RuntimeLocators:
        _fail("RUNTIME_LOCATOR_AUTHORITY_INVALID")
    try:
        return WindowsFaceLandmarkerOfflineM3Backend.from_accepted_windows_artifacts(
            executable=locators.vision_executable,
            face_landmarker_dll=locators.vision_face_landmarker_dll,
            opencv_core_dll=locators.vision_opencv_core_dll,
            opencv_imgproc_dll=locators.vision_opencv_imgproc_dll,
            model=locators.vision_model,
            staging_root=staging_root,
        )
    except ValueError as error:
        raise D02RuntimeCompositionError("M3_RUNTIME_COMPOSITION_FAILED") from error


def compose_accepted_m4_backend(
    *,
    locators: D02RuntimeLocators,
    materials: tuple[SourceMaterial, SourceMaterial, SourceMaterial, SourceMaterial],
    landmarks_by_source: dict[str, tuple[tuple[float, float, float], ...]],
) -> D02OpenCvM4Backend:
    if type(locators) is not D02RuntimeLocators:
        _fail("RUNTIME_LOCATOR_AUTHORITY_INVALID")
    try:
        return D02OpenCvM4Backend.from_private_paths(
            runtime_root=locators.m4_runtime_root,
            topology_path=locators.topology_file,
            materials=materials,
            landmarks_by_source=landmarks_by_source,
        )
    except ValueError as error:
        raise D02RuntimeCompositionError("M4_RUNTIME_COMPOSITION_FAILED") from error


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _exact_directory(path: Path, code: str) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        _fail(code)
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise D02RuntimeCompositionError(code) from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        resolved != path
        or not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (reparse_flag and attributes & reparse_flag)
    ):
        _fail(code)
    return path


def _read_exact_file(path: Path, *, maximum_bytes: int) -> bytes:
    if not path.is_absolute():
        _fail("RUNTIME_LOCATOR_HANDOFF_INVALID")
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise D02RuntimeCompositionError("RUNTIME_LOCATOR_HANDOFF_UNAVAILABLE") from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    identity = info.st_dev, info.st_ino
    if (
        resolved != path
        or parent != path.parent
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (reparse_flag and attributes & reparse_flag)
    ):
        _fail("RUNTIME_LOCATOR_HANDOFF_INVALID")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != identity or not stat.S_ISREG(opened.st_mode):
                _fail("RUNTIME_LOCATOR_HANDOFF_INVALID")
            chunks: list[bytes] = []
            total = 0
            while chunk := os.read(descriptor, 16_384):
                total += len(chunk)
                if total > maximum_bytes:
                    _fail("RUNTIME_LOCATOR_HANDOFF_INVALID")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except D02RuntimeCompositionError:
        raise
    except OSError as error:
        raise D02RuntimeCompositionError("RUNTIME_LOCATOR_HANDOFF_INVALID") from error


def _fail(code: str) -> NoReturn:
    raise D02RuntimeCompositionError(code)
