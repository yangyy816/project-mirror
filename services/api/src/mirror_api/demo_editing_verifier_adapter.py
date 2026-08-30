"""Deterministic verifier adapter for the local synthetic D07 raster runtime.

The pure verifier consumes independently assembled facts.  This adapter binds
those facts to PostgreSQL artifact authority, reloads the immutable source,
replays the typed raster operation, and decodes the materialized result.  It
does not claim biometric identity verification and deliberately refuses to
manufacture fresh geometry measurements.
"""

from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass
from typing import Final

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_editing_asset_loader import (
    DemoAssetByteLoader,
    DemoAssetByteReference,
)
from mirror_api.demo_editing_service import ExecutionCommand, MaterializedObject
from mirror_api.demo_effect_verifier import (
    EffectVerificationInput,
    EffectVerificationResult,
    EffectVerifierPolicy,
    verify_effect,
)
from mirror_api.demo_models import DemoEditArtifact, DemoImageVersion
from mirror_api.demo_operation_graph import OperationEngine, OperationType
from mirror_api.demo_raster_editor import (
    MAX_INPUT_BYTES,
    MAX_INPUT_PIXELS,
    RasterEditError,
    execute_raster_operation,
)
from mirror_api.models import Asset

_STRUCTURAL_DIMENSIONS: Final = ("chin_height", "eye_spacing", "jaw_width")
_POLICY: Final = EffectVerifierPolicy(
    target_tolerance_ppm=0,
    structural_drift_thresholds_ppm={key: 0 for key in _STRUCTURAL_DIMENSIONS},
    locked_drift_thresholds_ppm={key: 0 for key in _STRUCTURAL_DIMENSIONS},
    non_target_drift_threshold_ppm=0,
    allowed_media_types=("image/jpeg", "image/png"),
)


class DemoEditingVerifierAdapterError(RuntimeError):
    """Fail-closed authority error without byte or locator disclosure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class _VerifierContext:
    artifact_id: str
    source: DemoAssetByteReference
    transition_target: DemoAssetByteReference | None


class DemoDeterministicEditVerifier:
    """Verify deterministic raster/transition output for synthetic Demo use."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        asset_loader: DemoAssetByteLoader,
    ) -> None:
        self._sessions = session_factory
        self._asset_loader = asset_loader

    async def __call__(
        self, command: ExecutionCommand, materialized: MaterializedObject
    ) -> EffectVerificationResult:
        context = await self._context(command)
        source_after = await self._asset_loader.load(context.source)
        source_before_sha256 = hashlib.sha256(command.source_bytes).hexdigest()
        source_after_sha256 = hashlib.sha256(source_after).hexdigest()

        artifact_codes: set[str] = set()
        exact_expected: bytes | None = None
        if command.operation.operation_type in {
            OperationType.RESTORE,
            OperationType.ROLLBACK,
        }:
            if context.transition_target is None:
                artifact_codes.add("TRANSITION_TARGET_UNAVAILABLE")
            else:
                exact_expected = await self._asset_loader.load(context.transition_target)
        elif command.operation.engine is OperationEngine.RASTER:
            try:
                exact_expected = execute_raster_operation(
                    command.source_bytes, command.operation
                ).png_bytes
            except RasterEditError:
                artifact_codes.add("DETERMINISTIC_REPLAY_FAILED")
        else:
            artifact_codes.add("GEOMETRY_MEASUREMENT_UNAVAILABLE")

        if exact_expected is not None and exact_expected != materialized.content:
            artifact_codes.add("DETERMINISTIC_REPLAY_MISMATCH")
        decode_valid, width, height, media_type = _decode_result(materialized.content)
        if (
            width != materialized.width
            or height != materialized.height
            or media_type != materialized.mime_type
        ):
            decode_valid = False
        result_asset_id = _deterministic_result_asset_id(context.artifact_id, materialized.sha256)
        zero_drifts = {key: 0 for key in _STRUCTURAL_DIMENSIONS}
        return verify_effect(
            _POLICY,
            EffectVerificationInput(
                source_asset_id=command.source_asset_id,
                result_asset_id=result_asset_id,
                target_dimension_key="jaw_width",
                operation_digest=command.operation_digest,
                requested_delta_ppm=0,
                measured_delta_ppm=0,
                structural_drifts_ppm=zero_drifts,
                locked_drifts_ppm=zero_drifts,
                non_target_drift_ppm=0,
                artifact_status="PASS" if not artifact_codes else "FAIL",
                artifact_codes=tuple(sorted(artifact_codes)),
                original_before_sha256=source_before_sha256,
                original_after_sha256=source_after_sha256,
                result_bytes=materialized.content,
                declared_result_sha256=materialized.sha256,
                decode_valid=decode_valid,
                width=width,
                height=height,
                media_type=media_type,
            ),
        )

    async def _context(self, command: ExecutionCommand) -> _VerifierContext:
        async with self._sessions() as session:
            artifact = await session.scalar(
                select(DemoEditArtifact).where(
                    DemoEditArtifact.execution_job_binding_id == command.execution_job_binding_id,
                    DemoEditArtifact.formal_job_attempt_id == command.formal_job_attempt_id,
                    DemoEditArtifact.edit_operation_id == command.operation_id,
                )
            )
            source = await session.get(Asset, command.source_asset_id)
            if artifact is None or source is None:
                raise DemoEditingVerifierAdapterError(
                    "VERIFIER_AUTHORITY_UNAVAILABLE", "verification authority is unavailable"
                )
            source_reference = _reference(source)
            target_reference = None
            if command.operation.operation_type in {
                OperationType.RESTORE,
                OperationType.ROLLBACK,
            }:
                target_id = command.operation.parameters.get("target_image_version_id")
                target_digest = command.operation.parameters.get("target_image_version_digest")
                if not isinstance(target_id, str) or not isinstance(target_digest, str):
                    raise DemoEditingVerifierAdapterError(
                        "TRANSITION_TARGET_INVALID", "transition target is invalid"
                    )
                target = await session.get(DemoImageVersion, target_id)
                if target is None or target.content_digest != target_digest:
                    raise DemoEditingVerifierAdapterError(
                        "TRANSITION_TARGET_INVALID", "transition target changed"
                    )
                target_asset = await session.get(Asset, target.result_asset_id)
                if target_asset is None or target_asset.sha256 != target.result_asset_sha256:
                    raise DemoEditingVerifierAdapterError(
                        "TRANSITION_TARGET_INVALID", "transition Asset changed"
                    )
                target_reference = _reference(target_asset)
            return _VerifierContext(artifact.id, source_reference, target_reference)


def _reference(asset: Asset) -> DemoAssetByteReference:
    if asset.deleted_at is not None or not asset.synthetic:
        raise DemoEditingVerifierAdapterError(
            "VERIFIER_ASSET_UNAVAILABLE", "verification Asset is unavailable"
        )
    return DemoAssetByteReference(asset.id, asset.storage_key, asset.sha256, asset.byte_size, True)


def _decode_result(content: bytes) -> tuple[bool, int, int, str]:
    if not content or len(content) > MAX_INPUT_BYTES:
        return False, 0, 0, "application/octet-stream"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                media_type = {"JPEG": "image/jpeg", "PNG": "image/png"}.get(
                    image.format or "", "application/octet-stream"
                )
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_INPUT_PIXELS:
                    return False, width, height, media_type
                image.load()
                return media_type in _POLICY.allowed_media_types, width, height, media_type
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        return False, 0, 0, "application/octet-stream"


def _deterministic_result_asset_id(artifact_id: str, digest: str) -> str:
    return hashlib.sha256(
        f"mirror.demo/D07ResultAsset/v1\n{artifact_id}\n{digest}".encode()
    ).hexdigest()[:32]


__all__ = ["DemoDeterministicEditVerifier", "DemoEditingVerifierAdapterError"]
