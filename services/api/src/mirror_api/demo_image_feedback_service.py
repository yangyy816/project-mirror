"""Owner-bound D09 image feedback and atomic Final Save application service."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_idempotency import (
    DEMO_COMMAND_BINDING_SCHEMA_VERSION,
    DemoIdempotencyTarget,
    DemoSemanticIdempotencyCoordinator,
    binding_content_digest,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DemoAcceptedVisualEpisode,
    DemoCommandBinding,
    DemoImageVersion,
    DemoPreferenceEvent,
)
from mirror_api.demo_preference_ledger import (
    DEMO_ACCEPTED_VISUAL_EPISODE_SCHEMA_VERSION,
    DEMO_PREFERENCE_EVENT_SCHEMA_VERSION,
    AppendDemoPreferenceEvent,
    DemoPreferenceActorUnavailable,
    DemoPreferenceEventType,
    DemoPreferenceFinalSaveUnavailable,
    DemoPreferenceLedgerCorruption,
    DemoPreferenceLedgerInputError,
    DemoPreferenceSessionUnavailable,
    DemoPreferenceSourceType,
    DemoPreferenceTargetType,
    FinalizeDemoAcceptedVisualEpisode,
    accepted_visual_episode_content_digest,
    acquire_demo_preference_actor_lock,
    append_demo_preference_event,
    finalize_demo_accepted_visual_episode,
    preference_event_content_digest,
)
from mirror_api.models import new_id, utcnow

DEMO_IMAGE_FEEDBACK_OPERATION = "image_version.feedback"

_ID = re.compile(r"^[0-9a-f]{32}$")


class DemoImageFeedbackError(RuntimeError):
    """Base error for the D09 image-feedback application boundary."""


class DemoImageFeedbackInputError(DemoImageFeedbackError):
    """The feedback command violates the frozen public semantics."""


class DemoImageFeedbackUnavailable(DemoImageFeedbackError):
    """The target image is absent, foreign, or no longer available."""


class DemoImageFeedbackConflict(DemoImageFeedbackError):
    """The target cannot accept this feedback in its current state."""


class DemoImageFeedbackAuthorityCorruption(DemoImageFeedbackError):
    """Persisted feedback or Final Save authority is inconsistent."""


@dataclass(frozen=True)
class CreateDemoImageFeedback:
    demo_actor_id: str
    image_version_id: str
    feedback: Literal["ACCEPT", "REJECT", "ADJUST"]
    acceptance_kind: Literal["EVENT_ONLY", "FINAL_SAVE"] | None
    intensity_ppm: int | None
    idempotency_key: str

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.image_version_id, "image_version_id")
        if self.feedback not in {"ACCEPT", "REJECT", "ADJUST"}:
            raise DemoImageFeedbackInputError("feedback is unsupported")
        if self.feedback == "ACCEPT":
            if self.acceptance_kind not in {"EVENT_ONLY", "FINAL_SAVE"}:
                raise DemoImageFeedbackInputError("ACCEPT requires EVENT_ONLY or FINAL_SAVE")
            if self.intensity_ppm is not None:
                raise DemoImageFeedbackInputError("ACCEPT forbids intensity_ppm")
            return
        if self.acceptance_kind is not None:
            raise DemoImageFeedbackInputError("acceptance_kind is valid only for ACCEPT")
        if self.feedback == "ADJUST":
            if (
                type(self.intensity_ppm) is not int
                or self.intensity_ppm < 0
                or self.intensity_ppm > 1_000_000
            ):
                raise DemoImageFeedbackInputError("ADJUST requires an integer intensity_ppm")
            return
        if self.intensity_ppm is not None:
            raise DemoImageFeedbackInputError("REJECT forbids intensity_ppm")


@dataclass(frozen=True)
class DemoImageFeedbackResult:
    event_id: str
    event_type: Literal["IMAGE_ACCEPTED", "IMAGE_REJECTED", "IMAGE_ADJUSTED"]
    event_digest: str
    final_save: bool
    replayed: bool


@dataclass(frozen=True)
class DemoImageFinalSaveInSessionResult:
    """The exact D09 event/episode pair for a caller-owned transaction."""

    feedback: DemoImageFeedbackResult
    episode_id: str


class DemoImageFeedbackService:
    """Persist one explicit image action through the shared command authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._idempotency = DemoSemanticIdempotencyCoordinator(session_factory=session_factory)
        self._now = now

    async def create(self, command: CreateDemoImageFeedback) -> DemoImageFeedbackResult:
        command.validate()
        semantic_request = _semantic_request(command)
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(semantic_request)
        event_type, signal = _event_semantics(command)

        async def create_target(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoPreferenceEvent]:
            await acquire_demo_preference_actor_lock(session, command.demo_actor_id)
            image = await _owned_image(
                session,
                demo_actor_id=command.demo_actor_id,
                image_version_id=command.image_version_id,
                lock=True,
            )
            if command.acceptance_kind == "FINAL_SAVE":
                existing = await _existing_final_save_event(
                    session,
                    command=command,
                    image=image,
                    event_type=event_type,
                    signal=signal,
                    key_hash=key_hash,
                    request_digest=request_digest,
                )
                if existing is not None:
                    return DemoIdempotencyTarget(
                        value=existing,
                        response_id=existing.id,
                        demo_session_id=existing.demo_session_id,
                    )
                finalized = await finalize_demo_accepted_visual_episode(
                    session,
                    FinalizeDemoAcceptedVisualEpisode(
                        demo_actor_id=command.demo_actor_id,
                        demo_session_id=image.demo_session_id,
                        editing_session_id=image.editing_session_id,
                        accepted_image_version_id=image.id,
                        source_type=DemoPreferenceSourceType.EDIT_FEEDBACK,
                        signal=signal,
                        occurred_at=self._normalized_now(),
                    ),
                )
                event = finalized.preference_event
            else:
                appended = await append_demo_preference_event(
                    session,
                    AppendDemoPreferenceEvent(
                        demo_actor_id=command.demo_actor_id,
                        demo_session_id=image.demo_session_id,
                        event_type=event_type,
                        source_type=DemoPreferenceSourceType.EDIT_FEEDBACK,
                        target_type=DemoPreferenceTargetType.IMAGE_VERSION,
                        target_id=image.id,
                        signal=signal,
                        occurred_at=self._normalized_now(),
                    ),
                )
                event = appended.event
            return DemoIdempotencyTarget(
                value=event,
                response_id=event.id,
                demo_session_id=event.demo_session_id,
            )

        async def load_target(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[DemoPreferenceEvent] | None:
            event = await session.get(DemoPreferenceEvent, binding.response_id)
            if event is None:
                return None
            image = await _owned_image(
                session,
                demo_actor_id=command.demo_actor_id,
                image_version_id=command.image_version_id,
                lock=False,
            )
            _validate_feedback_event(
                event,
                command=command,
                image=image,
                event_type=event_type,
                signal=signal,
            )
            episode = await _episode_for_event(session, event.id, lock=False)
            if command.acceptance_kind == "FINAL_SAVE":
                if episode is None:
                    raise DemoImageFeedbackAuthorityCorruption(
                        "Final Save command winner lacks its episode"
                    )
                _validate_final_save_episode(episode, event=event, image=image)
            elif episode is not None:
                raise DemoImageFeedbackAuthorityCorruption(
                    "event-only feedback unexpectedly owns a Final Save episode"
                )
            return DemoIdempotencyTarget(
                value=event,
                response_id=event.id,
                demo_session_id=event.demo_session_id,
            )

        try:
            result = await self._idempotency.execute(
                demo_actor_id=command.demo_actor_id,
                endpoint_operation=DEMO_IMAGE_FEEDBACK_OPERATION,
                idempotency_key=command.idempotency_key,
                semantic_request=semantic_request,
                create_target=create_target,
                load_target=load_target,
            )
        except DemoPreferenceLedgerInputError as exc:
            raise DemoImageFeedbackInputError(str(exc)) from exc
        except (DemoPreferenceActorUnavailable, DemoPreferenceSessionUnavailable) as exc:
            raise DemoImageFeedbackUnavailable(str(exc)) from exc
        except DemoPreferenceFinalSaveUnavailable as exc:
            raise DemoImageFeedbackConflict(str(exc)) from exc
        except DemoPreferenceLedgerCorruption as exc:
            raise DemoImageFeedbackAuthorityCorruption(str(exc)) from exc
        event_type_value = cast(
            Literal["IMAGE_ACCEPTED", "IMAGE_REJECTED", "IMAGE_ADJUSTED"],
            result.value.event_type,
        )
        return DemoImageFeedbackResult(
            event_id=result.value.id,
            event_type=event_type_value,
            event_digest=result.value.content_digest,
            final_save=command.acceptance_kind == "FINAL_SAVE",
            replayed=result.replayed,
        )

    async def create_final_save_in_session(
        self, session: AsyncSession, command: CreateDemoImageFeedback
    ) -> DemoImageFinalSaveInSessionResult:
        """Create/replay FINAL_SAVE without owning the enclosing transaction.

        D06 acceptance uses this seam so the immutable D09 winner and the
        self-transfer terminal authority share a single PostgreSQL commit.
        """

        command.validate()
        if command.acceptance_kind != "FINAL_SAVE":
            raise DemoImageFeedbackInputError("in-session acceptance requires FINAL_SAVE")
        semantic_request = _semantic_request(command)
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(semantic_request)
        event_type, signal = _event_semantics(command)
        await acquire_demo_preference_actor_lock(session, command.demo_actor_id)
        image = await _owned_image(
            session,
            demo_actor_id=command.demo_actor_id,
            image_version_id=command.image_version_id,
            lock=True,
        )
        existing_binding = await session.scalar(
            select(DemoCommandBinding).where(
                DemoCommandBinding.demo_actor_id == command.demo_actor_id,
                DemoCommandBinding.endpoint_operation == DEMO_IMAGE_FEEDBACK_OPERATION,
                DemoCommandBinding.idempotency_key_hash == key_hash,
            )
        )
        if existing_binding is not None:
            if (
                existing_binding.request_digest != request_digest
                or existing_binding.response_type != "PREFERENCE_EVENT"
                or existing_binding.response_status != 201
                or existing_binding.demo_session_id != image.demo_session_id
            ):
                raise DemoImageFeedbackConflict(
                    "Final Save idempotency key is bound to another request"
                )
            event = await session.get(DemoPreferenceEvent, existing_binding.response_id)
            episode = await _episode_for_event(session, existing_binding.response_id, lock=True)
            if event is None or episode is None:
                raise DemoImageFeedbackAuthorityCorruption(
                    "Final Save command winner is incomplete"
                )
            _validate_feedback_event(
                event,
                command=command,
                image=image,
                event_type=event_type,
                signal=signal,
            )
            _validate_final_save_episode(episode, event=event, image=image)
            return DemoImageFinalSaveInSessionResult(
                _feedback_result(event, final_save=True, replayed=True), episode.id
            )
        existing = await _existing_final_save_event(
            session,
            command=command,
            image=image,
            event_type=event_type,
            signal=signal,
            key_hash=key_hash,
            request_digest=request_digest,
        )
        if existing is not None:
            episode = await _episode_for_event(session, existing.id, lock=True)
            if episode is None:
                raise DemoImageFeedbackAuthorityCorruption("Final Save winner lacks its episode")
            return DemoImageFinalSaveInSessionResult(
                _feedback_result(existing, final_save=True, replayed=True), episode.id
            )
        finalized = await finalize_demo_accepted_visual_episode(
            session,
            FinalizeDemoAcceptedVisualEpisode(
                demo_actor_id=command.demo_actor_id,
                demo_session_id=image.demo_session_id,
                editing_session_id=image.editing_session_id,
                accepted_image_version_id=image.id,
                source_type=DemoPreferenceSourceType.EDIT_FEEDBACK,
                signal=signal,
                occurred_at=self._normalized_now(),
            ),
        )
        event = finalized.preference_event
        binding_payload = {
            "demo_actor_id": command.demo_actor_id,
            "demo_session_id": image.demo_session_id,
            "endpoint_operation": DEMO_IMAGE_FEEDBACK_OPERATION,
            "idempotency_key_hash": key_hash,
            "request_digest": request_digest,
            "response_id": event.id,
            "response_status": 201,
            "response_type": "PREFERENCE_EVENT",
        }
        session.add(
            DemoCommandBinding(
                id=new_id(),
                schema_version=DEMO_COMMAND_BINDING_SCHEMA_VERSION,
                canonical_payload=binding_payload,
                content_digest=binding_content_digest(binding_payload),
                created_at=self._normalized_now(),
                demo_actor_id=command.demo_actor_id,
                demo_session_id=image.demo_session_id,
                endpoint_operation=DEMO_IMAGE_FEEDBACK_OPERATION,
                idempotency_key_hash=key_hash,
                request_digest=request_digest,
                response_type="PREFERENCE_EVENT",
                response_id=event.id,
                response_status=201,
            )
        )
        await session.flush()
        return DemoImageFinalSaveInSessionResult(
            _feedback_result(event, final_save=True, replayed=False),
            finalized.accepted_visual_episode.id,
        )

    def _normalized_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise DemoImageFeedbackAuthorityCorruption(
                "image feedback clock must be timezone-aware"
            )
        return value.astimezone(UTC)


async def _owned_image(
    session: AsyncSession,
    *,
    demo_actor_id: str,
    image_version_id: str,
    lock: bool,
) -> DemoImageVersion:
    statement = select(DemoImageVersion).where(
        DemoImageVersion.id == image_version_id,
        DemoImageVersion.demo_actor_id == demo_actor_id,
    )
    if lock:
        statement = statement.with_for_update()
    image = await session.scalar(statement)
    if image is None:
        raise DemoImageFeedbackUnavailable(
            "Demo ImageVersion is absent or belongs to another actor"
        )
    return image


async def _existing_final_save_event(
    session: AsyncSession,
    *,
    command: CreateDemoImageFeedback,
    image: DemoImageVersion,
    event_type: DemoPreferenceEventType,
    signal: Mapping[str, Any],
    key_hash: str,
    request_digest: str,
) -> DemoPreferenceEvent | None:
    episode = await session.scalar(
        select(DemoAcceptedVisualEpisode)
        .where(DemoAcceptedVisualEpisode.accepted_image_version_id == image.id)
        .with_for_update()
    )
    if episode is None:
        return None
    event = await session.scalar(
        select(DemoPreferenceEvent)
        .where(DemoPreferenceEvent.id == episode.acceptance_event_id)
        .with_for_update()
    )
    if event is None:
        raise DemoImageFeedbackAuthorityCorruption("Final Save episode references a missing event")
    _validate_feedback_event(
        event,
        command=command,
        image=image,
        event_type=event_type,
        signal=signal,
    )
    _validate_final_save_episode(episode, event=event, image=image)
    binding = await session.scalar(
        select(DemoCommandBinding).where(
            DemoCommandBinding.response_type == "PREFERENCE_EVENT",
            DemoCommandBinding.response_id == event.id,
        )
    )
    if binding is None:
        raise DemoImageFeedbackConflict(
            "ImageVersion already has a Final Save outside this command"
        )
    if (
        binding.demo_actor_id != command.demo_actor_id
        or binding.demo_session_id != image.demo_session_id
        or binding.endpoint_operation != DEMO_IMAGE_FEEDBACK_OPERATION
        or binding.idempotency_key_hash != key_hash
        or binding.request_digest != request_digest
    ):
        raise DemoImageFeedbackConflict("ImageVersion was finalized by a different command")
    return event


async def _episode_for_event(
    session: AsyncSession, event_id: str, *, lock: bool
) -> DemoAcceptedVisualEpisode | None:
    statement = select(DemoAcceptedVisualEpisode).where(
        DemoAcceptedVisualEpisode.acceptance_event_id == event_id
    )
    if lock:
        statement = statement.with_for_update()
    return cast(DemoAcceptedVisualEpisode | None, await session.scalar(statement))


def _validate_feedback_event(
    event: DemoPreferenceEvent,
    *,
    command: CreateDemoImageFeedback,
    image: DemoImageVersion,
    event_type: DemoPreferenceEventType,
    signal: Mapping[str, Any],
) -> None:
    canonical_payload = {
        "demo_actor_id": event.demo_actor_id,
        "demo_session_id": event.demo_session_id,
        "event_sequence": event.event_sequence,
        "event_type": event.event_type,
        "occurred_at": _canonical_time(event.occurred_at),
        "previous_event_digest": event.previous_event_digest,
        "signal": event.signal,
        "source_type": event.source_type,
        "target_id": event.target_id,
        "target_type": event.target_type,
    }
    if (
        event.schema_version != DEMO_PREFERENCE_EVENT_SCHEMA_VERSION
        or event.demo_actor_id != command.demo_actor_id
        or event.demo_session_id != image.demo_session_id
        or event.event_type != event_type.value
        or event.source_type != DemoPreferenceSourceType.EDIT_FEEDBACK.value
        or event.target_type != DemoPreferenceTargetType.IMAGE_VERSION.value
        or event.target_id != image.id
        or event.signal != signal
        or event.canonical_payload != canonical_payload
        or event.content_digest != preference_event_content_digest(canonical_payload)
    ):
        raise DemoImageFeedbackAuthorityCorruption(
            "image feedback command winner event is inconsistent"
        )


def _validate_final_save_episode(
    episode: DemoAcceptedVisualEpisode,
    *,
    event: DemoPreferenceEvent,
    image: DemoImageVersion,
) -> None:
    canonical_payload = {
        "acceptance_event_id": episode.acceptance_event_id,
        "accepted_image_version_id": episode.accepted_image_version_id,
        "context_digest": episode.context_digest,
        "demo_actor_id": episode.demo_actor_id,
        "demo_session_id": episode.demo_session_id,
        "editing_session_id": episode.editing_session_id,
        "final_asset_id": episode.final_asset_id,
        "final_asset_sha256": episode.final_asset_sha256,
        "instruction_digest": episode.instruction_digest,
        "profile_digest": episode.profile_digest,
        "source_asset_id": episode.source_asset_id,
        "source_asset_sha256": episode.source_asset_sha256,
        "trajectory_digests": episode.trajectory_digests,
        "verification_result_id": episode.verification_result_id,
    }
    if (
        episode.schema_version != DEMO_ACCEPTED_VISUAL_EPISODE_SCHEMA_VERSION
        or episode.demo_actor_id != image.demo_actor_id
        or episode.demo_session_id != image.demo_session_id
        or episode.editing_session_id != image.editing_session_id
        or episode.accepted_image_version_id != image.id
        or episode.acceptance_event_id != event.id
        or episode.final_asset_id != image.result_asset_id
        or episode.final_asset_sha256 != image.result_asset_sha256
        or episode.canonical_payload != canonical_payload
        or episode.content_digest != accepted_visual_episode_content_digest(canonical_payload)
    ):
        raise DemoImageFeedbackAuthorityCorruption(
            "Final Save command winner episode is inconsistent"
        )


def _semantic_request(command: CreateDemoImageFeedback) -> dict[str, Any]:
    return {
        "acceptance_kind": command.acceptance_kind,
        "feedback": command.feedback,
        "image_version_id": command.image_version_id,
        "intensity_ppm": command.intensity_ppm,
    }


def _feedback_result(
    event: DemoPreferenceEvent, *, final_save: bool, replayed: bool
) -> DemoImageFeedbackResult:
    return DemoImageFeedbackResult(
        event_id=event.id,
        event_type=cast(
            Literal["IMAGE_ACCEPTED", "IMAGE_REJECTED", "IMAGE_ADJUSTED"], event.event_type
        ),
        event_digest=event.content_digest,
        final_save=final_save,
        replayed=replayed,
    )


def _event_semantics(
    command: CreateDemoImageFeedback,
) -> tuple[DemoPreferenceEventType, dict[str, Any]]:
    signal: dict[str, Any] = {"feedback": command.feedback}
    if command.acceptance_kind is not None:
        signal["acceptance_kind"] = command.acceptance_kind
    if command.intensity_ppm is not None:
        signal["intensity_ppm"] = command.intensity_ppm
    event_type = {
        "ACCEPT": DemoPreferenceEventType.IMAGE_ACCEPTED,
        "REJECT": DemoPreferenceEventType.IMAGE_REJECTED,
        "ADJUST": DemoPreferenceEventType.IMAGE_ADJUSTED,
    }[command.feedback]
    return event_type, signal


def _canonical_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DemoImageFeedbackAuthorityCorruption(
            "persisted image feedback time must be timezone-aware"
        )
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoImageFeedbackInputError(f"{name} must be a lowercase hexadecimal ID")


__all__ = [
    "DEMO_IMAGE_FEEDBACK_OPERATION",
    "CreateDemoImageFeedback",
    "DemoImageFeedbackAuthorityCorruption",
    "DemoImageFeedbackConflict",
    "DemoImageFeedbackInputError",
    "DemoImageFeedbackResult",
    "DemoImageFeedbackService",
    "DemoImageFeedbackUnavailable",
    "DemoImageFinalSaveInSessionResult",
]
