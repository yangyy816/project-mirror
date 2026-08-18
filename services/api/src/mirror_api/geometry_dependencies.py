"""Typed composition root for the private synthetic geometry transform."""

from __future__ import annotations

from mirror_api.config import Settings
from mirror_api.providers.opencv_geometry import (
    OpenCvGeometryTransform,
    load_private_opencv_runtime,
)
from mirror_api.synthetic_dataset.geometry_transform import GeometryTransform


def create_geometry_transform_provider(settings: Settings) -> GeometryTransform:
    """Build only an explicitly configured, manifest-verified private transform."""
    if settings.geometry_transform_provider != "private_opencv":
        raise RuntimeError("private geometry transform provider is not enabled")
    runtime_root = settings.geometry_runtime_root
    if runtime_root is None:
        raise RuntimeError("private geometry runtime root is not configured")
    return OpenCvGeometryTransform(load_private_opencv_runtime(runtime_root))
