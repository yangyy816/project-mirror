"""Append-only Demo preference-event authority and offline chain verification."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.demo_idempotency import DemoIdempotencyInputError, canonical_json_bytes
from mirror_api.demo_models import (
    DemoAcceptedVisualEpisode,
    DemoActor,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoImageVersion,
    DemoPreferenceEvent,
    DemoSession,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.models import new_id

DEMO_PREFERENCE_EVENT_SCHEMA_VERSION = "mirror.demo/DemoPreferenceEvent/v1"
DEMO_ACCEPTED_VISUAL_EPISODE_SCHEMA_VERSION = "mirror.demo/DemoAcceptedVisualEpisode/v1"
GENESIS_EVENT_DIGEST = "0" * 64
MAX_FINAL_SAVE_LINEAGE_DEPTH = 256

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DemoPreferenceEventType(StrEnum):
    EXPLICIT_STYLE_SELECTION = "EXPLICIT_STYLE_SELECTION"
    FEATURE_LOCKED = "FEATURE_LOCKED"
    FEATURE_UNLOCKED = "FEATURE_UNLOCKED"
    TEMPORARY_SESSION_OVERRIDE = "TEMPORARY_SESSION_OVERRIDE"
    MAXIMUM_INTENSITY_CHANGED = "MAXIMUM_INTENSITY_CHANGED"
    PROHIBITED_OPERATION_ADDED = "PROHIBITED_OPERATION_ADDED"
    IMAGE_ACCEPTED = "IMAGE_ACCEPTED"
    IMAGE_REJECTED = "IMAGE_REJECTED"
    IMAGE_ADJUSTED = "IMAGE_ADJUSTED"
    LEARNING_DISABLED = "LEARNING_DISABLED"
    LEARNING_ENABLED = "LEARNING_ENABLED"
    RESET = "RESET"
    ROLLBACK = "ROLLBACK"
    TOMBSTONE = "TOMBSTONE"
    DELETE = "DELETE"
    SESSION_CLOSED = "SESSION_CLOSED"
    ACTOR_TOMBSTONED = "ACTOR_TOMBSTONED"
    EDITING_SESSION_CLOSED = "EDITING_SESSION_CLOSED"


class DemoPreferenceSourceType(StrEnum):
    EXPLICIT_USER_ACTION = "EXPLICIT_USER_ACTION"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    SELF_TRANSFER = "SELF_TRANSFER"
    EDIT_FEEDBACK = "EDIT_FEEDBACK"
    SYSTEM_LIFECYCLE = "SYSTEM_LIFECYCLE"


class DemoPreferenceTargetType(StrEnum):
    DEMO_ACTOR = "DEMO_ACTOR"
    BASELINE_FACE_MODEL = "BASELINE_FACE_MODEL"
    SELF_STATE = "SELF_STATE"
    DESIRED_DELTA_PROFILE = "DESIRED_DELTA_PROFILE"
    STYLE_PROFILE = "STYLE_PROFILE"
    REFERENCE_PROFILE = "REFERENCE_PROFILE"
    IMAGE_VERSION = "IMAGE_VERSION"
    AESTHETIC_PROFILE = "AESTHETIC_PROFILE"
    CONTEXT_COMPILATION = "CONTEXT_COMPILATION"


class DemoPreferenceLedgerError(RuntimeError):
    """Base error for Demo preference-event authority."""


class DemoPreferenceLedgerInputError(DemoPreferenceLedgerError):
    """A command is not a valid, canonicalizable preference event."""


class DemoPreferenceActorUnavailable(DemoPreferenceLedgerError):
    """The actor does not exist or has already been tombstoned."""


class DemoPreferenceSessionUnavailable(DemoPreferenceLedgerError):
    """The referenced session is absent, foreign, closed, or tombstoned."""


class DemoPreferenceLedgerCorruption(DemoPreferenceLedgerError):
    """Persisted preference-event authority does not form a valid chain."""


class DemoPreferenceFinalSaveUnavailable(DemoPreferenceLedgerError):
    """The requested image lineage is not eligible for a Demo Final Save."""


@dataclass(frozen=True)
class AppendDemoPreferenceEvent:
    demo_actor_id: str
    demo_session_id: str | None
    event_type: DemoPreferenceEventType
    source_type: DemoPreferenceSourceType
    target_type: DemoPreferenceTargetType | None
    target_id: str | None
    signal: Mapping[str, Any]
    occurred_at: datetime


@dataclass(frozen=True)
class DemoPreferenceEventAppendResult:
    event: DemoPreferenceEvent
    event_sequence: int
    previous_event_digest: str


@dataclass(frozen=True)
class DemoPreferenceChainVerification:
    demo_actor_id: str | None
    event_count: int
    final_content_digest: str | None


@dataclass(frozen=True)
class FinalizeDemoAcceptedVisualEpisode:
    """Trusted command that atomically records one Demo Final Save."""

    demo_actor_id: str
    demo_session_id: str
    editing_session_id: str
    accepted_image_version_id: str
    source_type: DemoPreferenceSourceType
    signal: Mapping[str, Any]
    occurred_at: datetime


@dataclass(frozen=True)
class DemoAcceptedVisualEpisodeFinalSaveResult:
    """The immutable event and episode created by one successful Final Save."""

    preference_event: DemoPreferenceEvent
    accepted_visual_episode: DemoAcceptedVisualEpisode


async def append_demo_preference_event(
    session: AsyncSession, command: AppendDemoPreferenceEvent
) -> DemoPreferenceEventAppendResult:
    """Append one event in the caller-owned transaction without committing it."""

    _validate_command(command)
    occurred_at = _normalize_time(command.occurred_at)
    signal = _normalize_signal(command.signal)

    await _acquire_preference_actor_lock(session, command.demo_actor_id)
    actor = await _lock_active_actor(session, command.demo_actor_id)
    await _lock_active_session(session, actor.id, command.demo_session_id)
    return await _append_locked_preference_event(
        session,
        command,
        actor=actor,
        signal=signal,
        occurred_at=occurred_at,
    )


async def finalize_demo_accepted_visual_episode(
    session: AsyncSession, command: FinalizeDemoAcceptedVisualEpisode
) -> DemoAcceptedVisualEpisodeFinalSaveResult:
    """Append one acceptance event and its sole Final Save episode atomically.

    The caller owns the enclosing transaction.  This function deliberately never
    commits so an exception, cancellation, or caller rollback leaves no partial
    event/episode pair behind.
    """

    _validate_final_save_command(command)
    occurred_at = _normalize_time(command.occurred_at)
    signal = _normalize_signal(command.signal)

    await _acquire_preference_actor_lock(session, command.demo_actor_id)
    actor = await _lock_active_actor(session, command.demo_actor_id)
    await _lock_active_session(session, actor.id, command.demo_session_id)
    editing_session = await _lock_active_editing_session(
        session,
        demo_actor_id=actor.id,
        demo_session_id=command.demo_session_id,
        editing_session_id=command.editing_session_id,
    )
    lineage, verification = await _lock_and_validate_final_save_lineage(
        session,
        demo_actor_id=actor.id,
        demo_session_id=command.demo_session_id,
        editing_session=editing_session,
        accepted_image_version_id=command.accepted_image_version_id,
    )
    accepted_image = lineage[-1]
    append_command = AppendDemoPreferenceEvent(
        demo_actor_id=actor.id,
        demo_session_id=command.demo_session_id,
        event_type=DemoPreferenceEventType.IMAGE_ACCEPTED,
        source_type=command.source_type,
        target_type=DemoPreferenceTargetType.IMAGE_VERSION,
        target_id=accepted_image.id,
        signal=signal,
        occurred_at=occurred_at,
    )
    preference_event = await _append_locked_preference_event(
        session,
        append_command,
        actor=actor,
        signal=signal,
        occurred_at=occurred_at,
    )
    episode_payload = _accepted_visual_episode_payload(
        demo_actor_id=actor.id,
        demo_session_id=command.demo_session_id,
        editing_session_id=editing_session.id,
        accepted_image_version_id=accepted_image.id,
        verification_result_id=verification.id,
        acceptance_event_id=preference_event.event.id,
        source_asset_id=editing_session.source_asset_id,
        source_asset_sha256=editing_session.source_asset_sha256,
        final_asset_id=accepted_image.result_asset_id,
        final_asset_sha256=accepted_image.result_asset_sha256,
        trajectory_digests=[image.content_digest for image in lineage],
        profile_digest=editing_session.desired_delta_profile_digest,
        context_digest=editing_session.context_digest,
        instruction_digest=editing_session.instruction_digest,
    )
    episode = DemoAcceptedVisualEpisode(
        id=new_id(),
        schema_version=DEMO_ACCEPTED_VISUAL_EPISODE_SCHEMA_VERSION,
        canonical_payload=episode_payload,
        content_digest=accepted_visual_episode_content_digest(episode_payload),
        **episode_payload,
    )
    session.add(episode)
    await session.flush()
    return DemoAcceptedVisualEpisodeFinalSaveResult(
        preference_event=preference_event.event,
        accepted_visual_episode=episode,
    )


async def list_demo_final_save_episodes(
    session: AsyncSession,
    *,
    demo_actor_id: str,
    demo_session_id: str | None = None,
) -> list[DemoAcceptedVisualEpisode]:
    """Return Final Save evidence only; acceptance events alone are excluded."""

    _require_id(demo_actor_id, "demo actor id")
    if demo_session_id is not None:
        _require_id(demo_session_id, "demo session id")
    statement = (
        select(DemoAcceptedVisualEpisode)
        .join(
            DemoPreferenceEvent,
            DemoPreferenceEvent.id == DemoAcceptedVisualEpisode.acceptance_event_id,
        )
        .where(
            DemoAcceptedVisualEpisode.demo_actor_id == demo_actor_id,
            DemoPreferenceEvent.demo_actor_id == demo_actor_id,
            DemoPreferenceEvent.event_type == DemoPreferenceEventType.IMAGE_ACCEPTED.value,
            DemoPreferenceEvent.target_type == DemoPreferenceTargetType.IMAGE_VERSION.value,
            DemoPreferenceEvent.target_id == DemoAcceptedVisualEpisode.accepted_image_version_id,
        )
        .order_by(DemoPreferenceEvent.event_sequence)
    )
    if demo_session_id is not None:
        statement = statement.where(DemoAcceptedVisualEpisode.demo_session_id == demo_session_id)
    return list((await session.scalars(statement)).all())


async def _acquire_preference_actor_lock(session: AsyncSession, demo_actor_id: str) -> None:
    """Acquire the exact advisory namespace before every actor-scoped read."""

    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended('mirror.demo.preference/' || :demo_actor_id, 0))"
        ),
        {"demo_actor_id": demo_actor_id},
    )


async def _lock_active_actor(session: AsyncSession, demo_actor_id: str) -> DemoActor:
    actor = await session.scalar(
        select(DemoActor).where(DemoActor.id == demo_actor_id).with_for_update()
    )
    if actor is None or actor.tombstoned_at is not None:
        raise DemoPreferenceActorUnavailable("Demo actor is unavailable")
    return actor


async def _lock_active_session(
    session: AsyncSession, demo_actor_id: str, demo_session_id: str | None
) -> DemoSession | None:
    if demo_session_id is None:
        return None
    demo_session = await session.scalar(
        select(DemoSession).where(DemoSession.id == demo_session_id).with_for_update()
    )
    if (
        demo_session is None
        or demo_session.demo_actor_id != demo_actor_id
        or demo_session.closed_at is not None
        or demo_session.tombstoned_at is not None
    ):
        raise DemoPreferenceSessionUnavailable("Demo session is unavailable")
    return demo_session


async def _append_locked_preference_event(
    session: AsyncSession,
    command: AppendDemoPreferenceEvent,
    *,
    actor: DemoActor,
    signal: dict[str, Any],
    occurred_at: datetime,
) -> DemoPreferenceEventAppendResult:
    """Allocate a tail-only ledger entry after the actor advisory lock is held."""

    previous = await session.scalar(
        select(DemoPreferenceEvent)
        .where(DemoPreferenceEvent.demo_actor_id == actor.id)
        .order_by(DemoPreferenceEvent.event_sequence.desc())
        .limit(1)
    )
    if previous is None:
        event_sequence = 1
        previous_digest = GENESIS_EVENT_DIGEST
    else:
        event_sequence = previous.event_sequence + 1
        previous_digest = previous.content_digest

    _validate_event_semantics(
        command,
        signal=signal,
        event_sequence=event_sequence,
    )

    payload = _event_payload(
        demo_actor_id=actor.id,
        demo_session_id=command.demo_session_id,
        event_sequence=event_sequence,
        event_type=command.event_type,
        source_type=command.source_type,
        target_type=command.target_type,
        target_id=command.target_id,
        signal=signal,
        occurred_at=occurred_at,
        previous_event_digest=previous_digest,
    )
    event = DemoPreferenceEvent(
        id=new_id(),
        schema_version=DEMO_PREFERENCE_EVENT_SCHEMA_VERSION,
        canonical_payload=payload,
        content_digest=preference_event_content_digest(payload),
        demo_actor_id=actor.id,
        demo_session_id=command.demo_session_id,
        event_sequence=event_sequence,
        event_type=command.event_type.value,
        source_type=command.source_type.value,
        target_type=command.target_type.value if command.target_type is not None else None,
        target_id=command.target_id,
        signal=signal,
        occurred_at=occurred_at,
        previous_event_digest=previous_digest,
    )
    session.add(event)
    await session.flush()
    return DemoPreferenceEventAppendResult(
        event=event,
        event_sequence=event_sequence,
        previous_event_digest=previous_digest,
    )


def accepted_visual_episode_content_digest(payload: Mapping[str, Any]) -> str:
    """Return the exact existing DemoAcceptedVisualEpisode authority digest."""

    try:
        canonical = canonical_json_bytes(payload)
    except DemoIdempotencyInputError as exc:
        raise DemoPreferenceLedgerInputError(str(exc)) from exc
    authority = DEMO_ACCEPTED_VISUAL_EPISODE_SCHEMA_VERSION.encode("utf-8") + b"\n"
    return hashlib.sha256(authority + canonical).hexdigest()


async def _lock_active_editing_session(
    session: AsyncSession,
    *,
    demo_actor_id: str,
    demo_session_id: str,
    editing_session_id: str,
) -> DemoEditingSession:
    editing_session = await session.scalar(
        select(DemoEditingSession)
        .where(
            DemoEditingSession.id == editing_session_id,
            DemoEditingSession.demo_actor_id == demo_actor_id,
            DemoEditingSession.demo_session_id == demo_session_id,
        )
        .with_for_update()
    )
    if (
        editing_session is None
        or editing_session.closed_at is not None
        or editing_session.tombstoned_at is not None
    ):
        raise DemoPreferenceFinalSaveUnavailable("Demo editing session is unavailable")
    return editing_session


async def _lock_and_validate_final_save_lineage(
    session: AsyncSession,
    *,
    demo_actor_id: str,
    demo_session_id: str,
    editing_session: DemoEditingSession,
    accepted_image_version_id: str,
) -> tuple[list[DemoImageVersion], DemoVerificationResult]:
    lineage_reversed: list[DemoImageVersion] = []
    visited_image_ids: set[str] = set()
    current_image_id = accepted_image_version_id
    while True:
        if current_image_id in visited_image_ids:
            raise DemoPreferenceFinalSaveUnavailable("Demo image lineage contains a cycle")
        if len(lineage_reversed) >= MAX_FINAL_SAVE_LINEAGE_DEPTH:
            raise DemoPreferenceFinalSaveUnavailable("Demo image lineage exceeds the maximum depth")
        visited_image_ids.add(current_image_id)
        image = await session.scalar(
            select(DemoImageVersion)
            .where(
                DemoImageVersion.id == current_image_id,
                DemoImageVersion.demo_actor_id == demo_actor_id,
                DemoImageVersion.demo_session_id == demo_session_id,
                DemoImageVersion.editing_session_id == editing_session.id,
            )
            .with_for_update()
        )
        if image is None:
            raise DemoPreferenceFinalSaveUnavailable("Demo image lineage is unavailable")
        lineage_reversed.append(image)
        if image.parent_version_id is None:
            break
        current_image_id = image.parent_version_id

    lineage = list(reversed(lineage_reversed))
    root = lineage[0]
    terminal = lineage[-1]
    if (
        root.sequence != 0
        or root.version_kind != "ORIGINAL"
        or root.source_asset_id != editing_session.source_asset_id
        or root.source_asset_sha256 != editing_session.source_asset_sha256
    ):
        raise DemoPreferenceFinalSaveUnavailable("Demo image lineage root is invalid")
    if terminal.sequence == 0 or terminal.version_kind not in {"EDITED", "RESTORED", "ROLLED_BACK"}:
        raise DemoPreferenceFinalSaveUnavailable(
            "Accepted Demo image is not a Final Save candidate"
        )

    terminal_verification: DemoVerificationResult | None = None
    for sequence, image in enumerate(lineage):
        if image.sequence != sequence:
            raise DemoPreferenceFinalSaveUnavailable("Demo image lineage sequence is discontinuous")
        if sequence == 0:
            continue
        parent = lineage[sequence - 1]
        if (
            image.parent_version_id != parent.id
            or image.source_asset_id != parent.result_asset_id
            or image.source_asset_sha256 != parent.result_asset_sha256
            or image.version_kind not in {"EDITED", "RESTORED", "ROLLED_BACK"}
        ):
            raise DemoPreferenceFinalSaveUnavailable("Demo image lineage edge is invalid")
        verification = await _lock_and_validate_image_execution(
            session,
            image=image,
            parent=parent,
            editing_session=editing_session,
            require_terminal_operation=image.id == terminal.id,
        )
        if image.id == terminal.id:
            terminal_verification = verification
    if terminal_verification is None:
        raise DemoPreferenceFinalSaveUnavailable("Accepted Demo image lacks a verifier")
    return lineage, terminal_verification


async def _lock_and_validate_image_execution(
    session: AsyncSession,
    *,
    image: DemoImageVersion,
    parent: DemoImageVersion,
    editing_session: DemoEditingSession,
    require_terminal_operation: bool,
) -> DemoVerificationResult:
    if image.plan_digest is None or image.tool_run_digest is None or image.verifier_digest is None:
        raise DemoPreferenceFinalSaveUnavailable("Derived Demo image lacks execution authority")
    plan = await session.scalar(
        select(DemoEditPlan)
        .where(
            DemoEditPlan.content_digest == image.plan_digest,
            DemoEditPlan.record_kind == "RESULT",
            DemoEditPlan.demo_actor_id == image.demo_actor_id,
            DemoEditPlan.demo_session_id == image.demo_session_id,
            DemoEditPlan.editing_session_id == image.editing_session_id,
        )
        .with_for_update()
    )
    if (
        plan is None
        or plan.desired_delta_profile_digest != editing_session.desired_delta_profile_digest
        or plan.style_profile_digest != editing_session.style_profile_digest
        or plan.identity_constraints_digest != editing_session.identity_constraints_digest
        or plan.instruction_digest != editing_session.instruction_digest
        or plan.tool_registry_version != editing_session.tool_registry_version
    ):
        raise DemoPreferenceFinalSaveUnavailable("Demo EditPlan provenance is invalid")
    tool_run = await session.scalar(
        select(DemoToolRun)
        .where(
            DemoToolRun.content_digest == image.tool_run_digest,
            DemoToolRun.demo_actor_id == image.demo_actor_id,
            DemoToolRun.demo_session_id == image.demo_session_id,
            DemoToolRun.outcome == "COMPLETED",
            DemoToolRun.input_asset_id == parent.result_asset_id,
            DemoToolRun.input_asset_sha256 == parent.result_asset_sha256,
            DemoToolRun.output_asset_id.is_(None),
            DemoToolRun.output_asset_sha256.is_(None),
        )
        .with_for_update()
    )
    if tool_run is None:
        raise DemoPreferenceFinalSaveUnavailable("Demo ToolRun provenance is invalid")
    operation = await session.scalar(
        select(DemoEditOperation)
        .where(
            DemoEditOperation.id == tool_run.edit_operation_id,
            DemoEditOperation.content_digest == tool_run.edit_operation_digest,
            DemoEditOperation.edit_plan_id == plan.id,
            DemoEditOperation.demo_actor_id == image.demo_actor_id,
            DemoEditOperation.demo_session_id == image.demo_session_id,
        )
        .with_for_update()
    )
    expected_operation = {
        "engine": operation.engine if operation is not None else None,
        "operation_type": operation.operation_type if operation is not None else None,
        "parameters": operation.parameters if operation is not None else None,
        "preserve": operation.preserve if operation is not None else None,
        "expected_effect": operation.expected_effect if operation is not None else None,
    }
    if (
        operation is None
        or operation.operation_index < 0
        or operation.operation_index >= len(plan.operation_specs)
        or plan.operation_specs[operation.operation_index] != expected_operation
        or (
            require_terminal_operation
            and operation.operation_index != len(plan.operation_specs) - 1
        )
    ):
        raise DemoPreferenceFinalSaveUnavailable("Demo EditOperation provenance is invalid")
    if operation.operation_index == 0:
        if plan.input_image_version_id != parent.id:
            raise DemoPreferenceFinalSaveUnavailable("Demo plan input image is invalid")
    else:
        previous_tool = await session.scalar(
            select(DemoToolRun)
            .join(DemoEditOperation, DemoEditOperation.id == DemoToolRun.edit_operation_id)
            .where(
                DemoToolRun.content_digest == parent.tool_run_digest,
                DemoEditOperation.edit_plan_id == plan.id,
                DemoEditOperation.operation_index == operation.operation_index - 1,
                DemoToolRun.demo_job_binding_id == tool_run.demo_job_binding_id,
                DemoToolRun.formal_job_attempt_id == tool_run.formal_job_attempt_id,
            )
            .with_for_update()
        )
        if parent.plan_digest != plan.content_digest or previous_tool is None:
            raise DemoPreferenceFinalSaveUnavailable("Demo multi-operation execution is invalid")
    verification = await session.scalar(
        select(DemoVerificationResult)
        .where(
            DemoVerificationResult.content_digest == image.verifier_digest,
            DemoVerificationResult.demo_actor_id == image.demo_actor_id,
            DemoVerificationResult.demo_session_id == image.demo_session_id,
            DemoVerificationResult.image_version_id == image.id,
            DemoVerificationResult.tool_run_id == tool_run.id,
            DemoVerificationResult.output_asset_id == image.result_asset_id,
            DemoVerificationResult.output_asset_sha256 == image.result_asset_sha256,
        )
        .with_for_update()
    )
    if verification is None or verification.outcome != "PASS":
        raise DemoPreferenceFinalSaveUnavailable("Demo verification is not an accepted PASS")
    return verification


def _accepted_visual_episode_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    editing_session_id: str,
    accepted_image_version_id: str,
    verification_result_id: str,
    acceptance_event_id: str,
    source_asset_id: str,
    source_asset_sha256: str,
    final_asset_id: str,
    final_asset_sha256: str,
    trajectory_digests: list[str],
    profile_digest: str,
    context_digest: str,
    instruction_digest: str,
) -> dict[str, Any]:
    return {
        "acceptance_event_id": acceptance_event_id,
        "accepted_image_version_id": accepted_image_version_id,
        "context_digest": context_digest,
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "editing_session_id": editing_session_id,
        "final_asset_id": final_asset_id,
        "final_asset_sha256": final_asset_sha256,
        "instruction_digest": instruction_digest,
        "profile_digest": profile_digest,
        "source_asset_id": source_asset_id,
        "source_asset_sha256": source_asset_sha256,
        "trajectory_digests": trajectory_digests,
        "verification_result_id": verification_result_id,
    }


def preference_event_content_digest(payload: Mapping[str, Any]) -> str:
    """Return the content digest for one canonical preference-event payload."""

    try:
        canonical = canonical_json_bytes(payload)
    except DemoIdempotencyInputError as exc:
        raise DemoPreferenceLedgerInputError(str(exc)) from exc
    authority = DEMO_PREFERENCE_EVENT_SCHEMA_VERSION.encode("utf-8") + b"\n"
    return hashlib.sha256(authority + canonical).hexdigest()


def verify_demo_preference_event_chain(
    events: Sequence[DemoPreferenceEvent],
) -> DemoPreferenceChainVerification:
    """Fail closed unless every ordered event is a recomputable contiguous chain."""

    actor_id: str | None = None
    expected_sequence = 1
    previous_digest = GENESIS_EVENT_DIGEST
    for event in events:
        _validate_persisted_event(event)
        if actor_id is None:
            actor_id = event.demo_actor_id
        elif event.demo_actor_id != actor_id:
            raise DemoPreferenceLedgerCorruption("preference events span multiple actors")
        if event.event_sequence != expected_sequence:
            raise DemoPreferenceLedgerCorruption("preference event sequence is not contiguous")
        if event.previous_event_digest != previous_digest:
            raise DemoPreferenceLedgerCorruption("preference event previous digest is invalid")
        expected_payload = _event_payload_from_event(event)
        if event.canonical_payload != expected_payload:
            raise DemoPreferenceLedgerCorruption("preference event canonical payload is invalid")
        if event.content_digest != preference_event_content_digest(expected_payload):
            raise DemoPreferenceLedgerCorruption("preference event content digest is invalid")
        previous_digest = event.content_digest
        expected_sequence += 1
    return DemoPreferenceChainVerification(
        demo_actor_id=actor_id,
        event_count=len(events),
        final_content_digest=previous_digest if events else None,
    )


def _validate_command(command: AppendDemoPreferenceEvent) -> None:
    _require_id(command.demo_actor_id, "demo actor id")
    if command.demo_session_id is not None:
        _require_id(command.demo_session_id, "demo session id")
    if (command.target_type is None) != (command.target_id is None):
        raise DemoPreferenceLedgerInputError("target type and target id must be supplied together")
    if command.target_id is not None:
        _require_id(command.target_id, "target id")
    if not isinstance(command.event_type, DemoPreferenceEventType):
        raise DemoPreferenceLedgerInputError("unsupported preference event type")
    if not isinstance(command.source_type, DemoPreferenceSourceType):
        raise DemoPreferenceLedgerInputError("unsupported preference source type")
    if command.target_type is not None and not isinstance(
        command.target_type, DemoPreferenceTargetType
    ):
        raise DemoPreferenceLedgerInputError("unsupported preference target type")


def _validate_event_semantics(
    command: AppendDemoPreferenceEvent,
    *,
    signal: Mapping[str, Any],
    event_sequence: int,
) -> None:
    if command.event_type is not DemoPreferenceEventType.RESET:
        return
    reset_watermark = signal.get("reset_watermark")
    if (
        command.target_type is not DemoPreferenceTargetType.DEMO_ACTOR
        or command.target_id != command.demo_actor_id
        or type(reset_watermark) is not int
        or reset_watermark < 0
        or reset_watermark >= event_sequence
    ):
        raise DemoPreferenceLedgerInputError(
            "Demo RESET requires its actor target and a strict earlier event watermark"
        )


def _validate_final_save_command(command: FinalizeDemoAcceptedVisualEpisode) -> None:
    _require_id(command.demo_actor_id, "demo actor id")
    _require_id(command.demo_session_id, "demo session id")
    _require_id(command.editing_session_id, "editing session id")
    _require_id(command.accepted_image_version_id, "accepted image version id")
    if command.source_type not in {
        DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
        DemoPreferenceSourceType.EDIT_FEEDBACK,
    }:
        raise DemoPreferenceLedgerInputError(
            "Demo Final Save requires an explicit user acceptance signal"
        )


def _event_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str | None,
    event_sequence: int,
    event_type: DemoPreferenceEventType,
    source_type: DemoPreferenceSourceType,
    target_type: DemoPreferenceTargetType | None,
    target_id: str | None,
    signal: dict[str, Any],
    occurred_at: datetime,
    previous_event_digest: str,
) -> dict[str, Any]:
    return {
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "event_sequence": event_sequence,
        "event_type": event_type.value,
        "occurred_at": _canonical_time(occurred_at),
        "previous_event_digest": previous_event_digest,
        "signal": signal,
        "source_type": source_type.value,
        "target_id": target_id,
        "target_type": target_type.value if target_type is not None else None,
    }


def _event_payload_from_event(event: DemoPreferenceEvent) -> dict[str, Any]:
    try:
        event_type = DemoPreferenceEventType(event.event_type)
        source_type = DemoPreferenceSourceType(event.source_type)
        target_type = (
            DemoPreferenceTargetType(event.target_type) if event.target_type is not None else None
        )
    except ValueError as exc:
        raise DemoPreferenceLedgerCorruption(
            "preference event contains an unsupported enum"
        ) from exc
    signal = _normalize_signal(event.signal, corruption=True)
    try:
        occurred_at = _normalize_time(event.occurred_at)
    except DemoPreferenceLedgerInputError as exc:
        raise DemoPreferenceLedgerCorruption(str(exc)) from exc
    return _event_payload(
        demo_actor_id=event.demo_actor_id,
        demo_session_id=event.demo_session_id,
        event_sequence=event.event_sequence,
        event_type=event_type,
        source_type=source_type,
        target_type=target_type,
        target_id=event.target_id,
        signal=signal,
        occurred_at=occurred_at,
        previous_event_digest=event.previous_event_digest,
    )


def _validate_persisted_event(event: DemoPreferenceEvent) -> None:
    try:
        _require_id(event.demo_actor_id, "event actor id")
        if event.demo_session_id is not None:
            _require_id(event.demo_session_id, "event session id")
        if event.target_id is not None:
            _require_id(event.target_id, "event target id")
    except DemoPreferenceLedgerInputError as exc:
        raise DemoPreferenceLedgerCorruption(str(exc)) from exc
    if (event.target_type is None) != (event.target_id is None):
        raise DemoPreferenceLedgerCorruption("preference event target shape is invalid")
    if event.event_sequence < 1:
        raise DemoPreferenceLedgerCorruption("preference event sequence is invalid")
    if event.schema_version != DEMO_PREFERENCE_EVENT_SCHEMA_VERSION:
        raise DemoPreferenceLedgerCorruption("preference event schema version is unsupported")
    if _DIGEST_PATTERN.fullmatch(event.previous_event_digest) is None:
        raise DemoPreferenceLedgerCorruption("preference event previous digest shape is invalid")
    if _DIGEST_PATTERN.fullmatch(event.content_digest) is None:
        raise DemoPreferenceLedgerCorruption("preference event content digest shape is invalid")


def _normalize_signal(value: Mapping[str, Any], *, corruption: bool = False) -> dict[str, Any]:
    try:
        normalized = json.loads(canonical_json_bytes(value))
    except (DemoIdempotencyInputError, TypeError, ValueError) as exc:
        error_type = (
            DemoPreferenceLedgerCorruption if corruption else DemoPreferenceLedgerInputError
        )
        raise error_type("preference event signal must be a canonical JSON object") from exc
    if not isinstance(normalized, dict):  # pragma: no cover - canonical_json_bytes guards Mapping.
        error_type = (
            DemoPreferenceLedgerCorruption if corruption else DemoPreferenceLedgerInputError
        )
        raise error_type("preference event signal must be a JSON object")
    return normalized


def _normalize_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DemoPreferenceLedgerInputError("occurred_at must be timezone-aware")
    return value.astimezone(UTC)


def _canonical_time(value: datetime) -> str:
    return _normalize_time(value).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _require_id(value: str, description: str) -> None:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise DemoPreferenceLedgerInputError(f"{description} must be a lowercase hexadecimal ID")
