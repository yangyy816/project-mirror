"""Read-only, owner-bound media projection for the current D04 presentation."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_editing_asset_loader import (
    DemoAssetByteLoader,
    DemoAssetByteReference,
    DemoAssetLoadError,
)
from mirror_api.demo_models import (
    DemoQuestionnaireRun,
    DemoQuestionnaireStep,
)
from mirror_api.demo_questionnaire_service import (
    DemoQuestionnaireAuthorityCorruption,
    DemoQuestionnaireInputError,
    DemoQuestionnaireService,
    DemoQuestionnaireUnavailable,
)
from mirror_api.image_sanitizer import ImageSanitizationError, decode_canonical_rgb_image
from mirror_api.models import Asset

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class DemoQuestionnaireMediaError(RuntimeError):
    """Base failure for the Demo-only presentation media projection."""


class DemoQuestionnaireMediaInputError(DemoQuestionnaireMediaError):
    """The caller supplied an invalid run ID or side."""


class DemoQuestionnaireMediaUnavailable(DemoQuestionnaireMediaError):
    """No current owner-bound presentation is available."""


class DemoQuestionnaireMediaAuthorityCorruption(DemoQuestionnaireMediaError):
    """The public presentation authority cannot be replayed safely."""


class DemoQuestionnaireMediaBytesUnavailable(DemoQuestionnaireMediaError):
    """The exact admitted JPEG bytes are missing or invalid."""


@dataclass(frozen=True, slots=True)
class DemoQuestionnaireMedia:
    content: bytes
    byte_size: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class _ResolvedPresentation:
    run_id: str
    run_digest: str
    step_id: str
    step_digest: str
    question_pair_id: str
    side: Literal["LEFT", "RIGHT"]
    reference: DemoAssetByteReference
    width: int
    height: int


class DemoQuestionnaireMediaService:
    """Load one current D02 result side without exposing its storage authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        asset_loader: DemoAssetByteLoader,
        questionnaire_service: DemoQuestionnaireService,
    ) -> None:
        self._sessions = session_factory
        self._asset_loader = asset_loader
        self._questionnaires = questionnaire_service

    async def load(
        self,
        *,
        demo_actor_id: str,
        questionnaire_run_id: str,
        side: Literal["LEFT", "RIGHT"],
    ) -> DemoQuestionnaireMedia:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(questionnaire_run_id, "questionnaire_run_id")
        if side not in {"LEFT", "RIGHT"}:
            raise DemoQuestionnaireMediaInputError("presentation side is invalid")

        resolved = await self._resolve(
            demo_actor_id=demo_actor_id,
            questionnaire_run_id=questionnaire_run_id,
            side=side,
        )
        try:
            content = await self._asset_loader.load(resolved.reference)
            await asyncio.to_thread(
                decode_canonical_rgb_image,
                content,
                expected_width=resolved.width,
                expected_height=resolved.height,
            )
        except (DemoAssetLoadError, ImageSanitizationError) as exc:
            raise DemoQuestionnaireMediaBytesUnavailable(
                "questionnaire presentation bytes are unavailable"
            ) from exc

        replayed = await self._resolve(
            demo_actor_id=demo_actor_id,
            questionnaire_run_id=questionnaire_run_id,
            side=side,
        )
        if replayed != resolved:
            raise DemoQuestionnaireMediaUnavailable(
                "questionnaire presentation changed during media loading"
            )
        return DemoQuestionnaireMedia(
            content=content,
            byte_size=resolved.reference.byte_size,
            width=resolved.width,
            height=resolved.height,
        )

    async def _resolve(
        self,
        *,
        demo_actor_id: str,
        questionnaire_run_id: str,
        side: Literal["LEFT", "RIGHT"],
    ) -> _ResolvedPresentation:
        try:
            current = await self._questionnaires.current_presentation(
                demo_actor_id=demo_actor_id,
                questionnaire_run_id=questionnaire_run_id,
            )
        except DemoQuestionnaireInputError as exc:
            raise DemoQuestionnaireMediaInputError(
                "questionnaire presentation request is invalid"
            ) from exc
        except DemoQuestionnaireUnavailable as exc:
            raise DemoQuestionnaireMediaUnavailable(
                "questionnaire presentation is unavailable"
            ) from exc
        except DemoQuestionnaireAuthorityCorruption as exc:
            raise DemoQuestionnaireMediaAuthorityCorruption(
                "questionnaire presentation authority is unavailable"
            ) from exc

        async with self._sessions() as session:
            async with session.begin():
                run = cast(
                    DemoQuestionnaireRun | None,
                    await session.scalar(
                        select(DemoQuestionnaireRun).where(
                            DemoQuestionnaireRun.id == questionnaire_run_id,
                            DemoQuestionnaireRun.demo_actor_id == demo_actor_id,
                        )
                    ),
                )
                if run is None:
                    raise DemoQuestionnaireMediaUnavailable(
                        "questionnaire presentation is unavailable"
                    )
                step = cast(
                    DemoQuestionnaireStep | None,
                    await session.scalar(
                        select(DemoQuestionnaireStep).where(
                            DemoQuestionnaireStep.id == current.snapshot.step_id,
                            DemoQuestionnaireStep.questionnaire_run_id == run.id,
                        )
                    ),
                )
                if (
                    step is None
                    or step.demo_actor_id != demo_actor_id
                    or step.demo_session_id != run.demo_session_id
                    or step.event_type != "PRESENTED"
                    or step.question_pair_id != current.question_pair_id
                    or step.step_number != current.snapshot.step_number
                    or step.event_sequence != current.snapshot.step_sequence
                    or step.response_snapshot is not None
                ):
                    raise DemoQuestionnaireMediaAuthorityCorruption(
                        "questionnaire presentation authority changed"
                    )
                selected = (
                    current.presentation.left if side == "LEFT" else current.presentation.right
                )
                asset = await session.get(Asset, selected.result_asset_id)
                if (
                    asset is None
                    or asset.owner_user_id is not None
                    or asset.asset_role != "synthetic"
                    or asset.internal_purpose != "synthetic_dataset"
                    or asset.synthetic is not True
                    or asset.is_ai_generated is not False
                    or asset.is_ai_modified is not True
                    or asset.deleted_at is not None
                    or asset.mime_type != "image/jpeg"
                    or asset.sha256 != selected.result_checksum
                    or asset.storage_key
                    != f"internal-synthetic/v1/d02/result/{selected.result_asset_id}"
                    or type(asset.byte_size) is not int
                    or asset.byte_size <= 0
                    or type(asset.width) is not int
                    or asset.width <= 0
                    or type(asset.height) is not int
                    or asset.height <= 0
                    or _DIGEST.fullmatch(asset.sha256) is None
                ):
                    raise DemoQuestionnaireMediaAuthorityCorruption(
                        "questionnaire result Asset authority is invalid"
                    )
                return _ResolvedPresentation(
                    run_id=run.id,
                    run_digest=run.content_digest,
                    step_id=step.id,
                    step_digest=step.content_digest,
                    question_pair_id=current.question_pair_id,
                    side=side,
                    reference=DemoAssetByteReference(
                        asset_id=asset.id,
                        storage_key=asset.storage_key,
                        sha256=asset.sha256,
                        byte_size=asset.byte_size,
                        synthetic=True,
                    ),
                    width=asset.width,
                    height=asset.height,
                )


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoQuestionnaireMediaInputError(
            f"{name} must be a 32-character lowercase hexadecimal ID"
        )


__all__ = [
    "DemoQuestionnaireMedia",
    "DemoQuestionnaireMediaAuthorityCorruption",
    "DemoQuestionnaireMediaBytesUnavailable",
    "DemoQuestionnaireMediaInputError",
    "DemoQuestionnaireMediaService",
    "DemoQuestionnaireMediaUnavailable",
]
