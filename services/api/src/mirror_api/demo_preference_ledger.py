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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.demo_idempotency import DemoIdempotencyInputError, canonical_json_bytes
from mirror_api.demo_models import DemoActor, DemoPreferenceEvent, DemoSession
from mirror_api.models import new_id

DEMO_PREFERENCE_EVENT_SCHEMA_VERSION = "mirror.demo/DemoPreferenceEvent/v1"
GENESIS_EVENT_DIGEST = "0" * 64

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


async def append_demo_preference_event(
    session: AsyncSession, command: AppendDemoPreferenceEvent
) -> DemoPreferenceEventAppendResult:
    """Append one event in the caller-owned transaction without committing it."""

    _validate_command(command)
    occurred_at = _normalize_time(command.occurred_at)
    signal = _normalize_signal(command.signal)

    actor = await session.scalar(
        select(DemoActor).where(DemoActor.id == command.demo_actor_id).with_for_update()
    )
    if actor is None or actor.tombstoned_at is not None:
        raise DemoPreferenceActorUnavailable("Demo actor is unavailable")

    if command.demo_session_id is not None:
        demo_session = await session.scalar(
            select(DemoSession).where(DemoSession.id == command.demo_session_id).with_for_update()
        )
        if (
            demo_session is None
            or demo_session.demo_actor_id != actor.id
            or demo_session.closed_at is not None
            or demo_session.tombstoned_at is not None
        ):
            raise DemoPreferenceSessionUnavailable("Demo session is unavailable")

    existing_events = list(
        (
            await session.scalars(
                select(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == actor.id)
                .order_by(DemoPreferenceEvent.event_sequence)
            )
        ).all()
    )
    verify_demo_preference_event_chain(existing_events)
    if not existing_events:
        event_sequence = 1
        previous_digest = GENESIS_EVENT_DIGEST
    else:
        previous = existing_events[-1]
        event_sequence = previous.event_sequence + 1
        previous_digest = previous.content_digest

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
        created_at=occurred_at,
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
