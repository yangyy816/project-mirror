from __future__ import annotations

import json
from pathlib import Path

import pytest

from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_r2_runtime_forward import build_default_model_identity
from mirror_api.demo_d02_runtime_composition import (
    EXPECTED_M4_RUNTIME_MANIFEST_DIGEST,
    RUNTIME_LOCATOR_HANDOFF_SCHEMA,
    D02RuntimeCompositionError,
    load_runtime_locators,
)


def _document(root: Path) -> dict[str, object]:
    return {
        "schema_version": RUNTIME_LOCATOR_HANDOFF_SCHEMA,
        "authority": "D02_SUBSYSTEM_PRINCIPAL",
        "runtime_identity_digest": measurement.RUNTIME_MANIFEST_DIGEST,
        "model_identity_digest": build_default_model_identity().identity_digest,
        "topology_digest": measurement.TOPOLOGY_DIGEST,
        "m4_runtime_manifest_digest": EXPECTED_M4_RUNTIME_MANIFEST_DIGEST,
        "vision_executable": str(root / "vision.exe"),
        "vision_face_landmarker_dll": str(root / "vision.dll"),
        "vision_opencv_core_dll": str(root / "core.dll"),
        "vision_opencv_imgproc_dll": str(root / "imgproc.dll"),
        "vision_model": str(root / "model.task"),
        "topology_file": str(root / "topology.py"),
        "m4_runtime_root": str(root / "m4-runtime"),
    }


def _write(root: Path, value: object) -> None:
    private = root / ".private-handoff"
    private.mkdir()
    (private / "D02_RUNTIME_LOCATORS.json").write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def test_locator_handoff_is_exact_and_repr_does_not_disclose_paths(tmp_path: Path) -> None:
    root = tmp_path.resolve(strict=True)
    _write(root, _document(root))

    locators = load_runtime_locators(workspace_root=root)

    assert locators.vision_executable == root / "vision.exe"
    assert str(root) not in repr(locators)


def test_locator_handoff_rejects_relative_or_foreign_authority(tmp_path: Path) -> None:
    root = tmp_path.resolve(strict=True)
    document = _document(root)
    document["vision_model"] = "relative-model.task"
    _write(root, document)

    with pytest.raises(D02RuntimeCompositionError):
        load_runtime_locators(workspace_root=root)


def test_locator_handoff_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    root = tmp_path.resolve(strict=True)
    private = root / ".private-handoff"
    private.mkdir()
    (private / "D02_RUNTIME_LOCATORS.json").write_text(
        '{"schema_version":"x","schema_version":"y"}',
        encoding="utf-8",
    )

    with pytest.raises(D02RuntimeCompositionError):
        load_runtime_locators(workspace_root=root)
