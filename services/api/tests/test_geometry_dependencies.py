from __future__ import annotations

from pathlib import Path

import pytest

from mirror_api.config import Settings
from mirror_api.geometry_dependencies import create_geometry_transform_provider
from mirror_api.providers.opencv_geometry import OpenCvGeometryTransform


class FakeRuntime:
    candidate_id = "OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2"
    runtime_version = "5.0.0"
    manifest_digest = "a" * 64

    def remap_rgb(self, *, source: bytes, remap: object) -> bytes:
        del remap
        return source


def test_geometry_factory_fails_closed_when_provider_is_disabled() -> None:
    with pytest.raises(RuntimeError, match="provider is not enabled"):
        create_geometry_transform_provider(Settings())


def test_geometry_factory_uses_only_the_manifest_verified_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_root = Path(Path.cwd().anchor) / "private" / "mirror-opencv"
    captured: list[Path] = []

    def fake_loader(runtime_root: Path) -> FakeRuntime:
        captured.append(runtime_root)
        return FakeRuntime()

    monkeypatch.setattr("mirror_api.geometry_dependencies.load_private_opencv_runtime", fake_loader)
    provider = create_geometry_transform_provider(
        Settings(
            app_env="test",
            geometry_transform_provider="private_opencv",
            geometry_runtime_root=configured_root,
        )
    )

    assert isinstance(provider, OpenCvGeometryTransform)
    assert captured == [configured_root]
