"""Exact, owner-bound media projection for completed Demo edit executions."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_editing_asset_loader import (
    DemoAssetByteLoader,
    DemoAssetByteReference,
    DemoAssetLoadError,
)
from mirror_api.demo_editing_commands import (
    DemoEditingCommandAuthorityCorruption,
    DemoEditingCommandService,
    DemoEditingCommandUnavailable,
    DemoEditResultNotReady,
    DemoEditResultTerminal,
)
from mirror_api.demo_models import DemoEditPlan, DemoImageVersion, DemoJobBinding
from mirror_api.image_sanitizer import ImageSanitizationError, decode_canonical_rgb_image
from mirror_api.models import Asset

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class DemoEditingMediaError(RuntimeError):
    pass


class DemoEditingMediaInputError(DemoEditingMediaError):
    pass


class DemoEditingMediaUnavailable(DemoEditingMediaError):
    pass


class DemoEditingMediaAuthorityCorruption(DemoEditingMediaError):
    pass


class DemoEditingMediaBytesUnavailable(DemoEditingMediaError):
    pass


@dataclass(frozen=True, slots=True)
class DemoEditingMedia:
    content: bytes
    media_type: Literal["image/jpeg"] = "image/jpeg"


@dataclass(frozen=True, slots=True)
class _ResolvedMedia:
    job_id: str
    binding_digest: str
    plan_digest: str
    image_version_id: str
    image_digest: str
    side: Literal["INPUT", "RESULT"]
    reference: DemoAssetByteReference
    width: int
    height: int


class DemoEditingMediaService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        asset_loader: DemoAssetByteLoader,
    ) -> None:
        self._sessions = session_factory
        self._asset_loader = asset_loader
        self._commands = DemoEditingCommandService(session_factory=session_factory)

    async def load(
        self, *, demo_actor_id: str, job_id: str, side: Literal["INPUT", "RESULT"]
    ) -> DemoEditingMedia:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(job_id, "job_id")
        if side not in {"INPUT", "RESULT"}:
            raise DemoEditingMediaInputError("media side is invalid")
        resolved = await self._resolve(demo_actor_id=demo_actor_id, job_id=job_id, side=side)
        try:
            content = await self._asset_loader.load(resolved.reference)
            await asyncio.to_thread(
                decode_canonical_rgb_image,
                content,
                expected_width=resolved.width,
                expected_height=resolved.height,
            )
        except (DemoAssetLoadError, ImageSanitizationError) as exc:
            raise DemoEditingMediaBytesUnavailable("edit media bytes are unavailable") from exc
        if await self._resolve(demo_actor_id=demo_actor_id, job_id=job_id, side=side) != resolved:
            raise DemoEditingMediaUnavailable("edit media changed during loading")
        return DemoEditingMedia(content)

    async def _resolve(
        self, *, demo_actor_id: str, job_id: str, side: Literal["INPUT", "RESULT"]
    ) -> _ResolvedMedia:
        try:
            execution = await self._commands.read_execution_result(
                demo_actor_id=demo_actor_id, job_id=job_id
            )
        except (
            DemoEditingCommandUnavailable,
            DemoEditResultNotReady,
            DemoEditResultTerminal,
        ) as exc:
            raise DemoEditingMediaUnavailable("completed edit execution is unavailable") from exc
        except DemoEditingCommandAuthorityCorruption as exc:
            raise DemoEditingMediaAuthorityCorruption(
                "edit execution authority is invalid"
            ) from exc
        async with self._sessions() as session:
            # Locate the canonical binding by exact Job and assert its digest.
            bindings = list(
                await session.scalars(
                    select(DemoJobBinding).where(
                        DemoJobBinding.demo_actor_id == demo_actor_id,
                        DemoJobBinding.job_id == job_id,
                        DemoJobBinding.endpoint_operation == "edit_plan.execute",
                        DemoJobBinding.target_type == "EDIT_PLAN",
                    )
                )
            )
            if len(bindings) != 1:
                raise DemoEditingMediaAuthorityCorruption("edit execution binding is ambiguous")
            binding = bindings[0]
            plan = await session.get(DemoEditPlan, execution.edit_plan_id)
            image = await session.get(DemoImageVersion, execution.image_version_id)
            if (
                plan is None
                or image is None
                or binding.content_digest != execution.job_binding_digest
                or binding.target_id != execution.edit_plan_id
                or binding.demo_session_id != execution.session_id
                or plan.content_digest != execution.plan_digest
                or plan.demo_actor_id != demo_actor_id
                or plan.demo_session_id != execution.session_id
                or plan.editing_session_id != execution.editing_session_id
                or image.content_digest != execution.image_version_digest
                or image.demo_actor_id != demo_actor_id
                or image.demo_session_id != execution.session_id
                or image.editing_session_id != execution.editing_session_id
                or image.plan_digest != plan.content_digest
                or image.parent_version_id != plan.input_image_version_id
                or image.sequence != execution.sequence
                or image.result_asset_id != execution.result_asset_id
                or image.result_asset_sha256 != execution.result_asset_sha256
                or image.version_kind != execution.version_kind
                or plan.input_image_version_id == image.id
            ):
                raise DemoEditingMediaAuthorityCorruption("edit execution lineage is invalid")
            selected = (
                image
                if side == "RESULT"
                else await session.get(DemoImageVersion, plan.input_image_version_id)
            )
            if (
                selected is None
                or selected.demo_actor_id != demo_actor_id
                or selected.demo_session_id != plan.demo_session_id
                or selected.editing_session_id != plan.editing_session_id
                or selected.version_kind == "QUARANTINED"
                or _DIGEST.fullmatch(selected.content_digest) is None
            ):
                raise DemoEditingMediaAuthorityCorruption("edit input lineage is invalid")
            asset_id = selected.result_asset_id
            asset_sha = selected.result_asset_sha256
            asset = await session.get(Asset, asset_id)
            if (
                asset is None
                or asset.id != asset_id
                or asset.sha256 != asset_sha
                or asset.deleted_at is not None
                or asset.mime_type != "image/jpeg"
                or asset.synthetic is not True
                or asset.owner_user_id is not None
                or asset.asset_role not in {"synthetic", "derived"}
                or type(asset.byte_size) is not int
                or type(asset.width) is not int
                or type(asset.height) is not int
                or asset.byte_size <= 0
                or asset.width <= 0
                or asset.height <= 0
                or _DIGEST.fullmatch(asset.sha256) is None
            ):
                raise DemoEditingMediaAuthorityCorruption("edit media Asset authority is invalid")
            return _ResolvedMedia(
                execution.job_id,
                binding.content_digest,
                plan.content_digest,
                selected.id,
                selected.content_digest,
                side,
                DemoAssetByteReference(
                    asset.id, asset.storage_key, asset.sha256, asset.byte_size, True
                ),
                asset.width,
                asset.height,
            )


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoEditingMediaInputError(f"{name} is invalid")


__all__ = [
    "DemoEditingMedia",
    "DemoEditingMediaAuthorityCorruption",
    "DemoEditingMediaBytesUnavailable",
    "DemoEditingMediaInputError",
    "DemoEditingMediaService",
    "DemoEditingMediaUnavailable",
]
