from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import (
    DEMO_TABLE_NAMES,
    DemoActor,
    DemoAestheticProfile,
    DemoPreferenceEvent,
    DemoSession,
)
from mirror_api.demo_preference_ledger import (
    DEMO_PREFERENCE_EVENT_SCHEMA_VERSION,
    GENESIS_EVENT_DIGEST,
    AppendDemoPreferenceEvent,
    DemoPreferenceActorUnavailable,
    DemoPreferenceChainVerification,
    DemoPreferenceEventType,
    DemoPreferenceLedgerCorruption,
    DemoPreferenceLedgerInputError,
    DemoPreferenceSessionUnavailable,
    DemoPreferenceSourceType,
    DemoPreferenceTargetType,
    append_demo_preference_event,
    preference_event_content_digest,
    verify_demo_preference_event_chain,
)
from mirror_api.models import new_id

NOW = datetime(2026, 8, 23, 12, 30, 15, 123456, tzinfo=UTC)
EXPIRES_AT = NOW + timedelta(days=1)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    table_list = ", ".join(sorted(DEMO_TABLE_NAMES))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE TABLE {table_list} CASCADE"))
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE TABLE {table_list} CASCADE"))
        await engine.dispose()


def _authority_digest(schema_version: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _authority_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _actor(sessions: async_sessionmaker[AsyncSession]) -> DemoActor:
    payload = {
        "actor_kind": "AUTOMATED_TEST",
        "authority_at": _authority_time(NOW),
        "credential_key_id": new_id() + new_id(),
    }
    actor = DemoActor(
        id=new_id(),
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload=payload,
        content_digest=_authority_digest("mirror.demo/DemoActor/v1", payload),
        created_at=NOW,
        actor_kind="AUTOMATED_TEST",
        credential_key_id=payload["credential_key_id"],
        authority_at=NOW,
    )
    async with sessions() as session:
        session.add(actor)
        await session.commit()
    return actor


async def _demo_session(
    sessions: async_sessionmaker[AsyncSession], actor: DemoActor
) -> DemoSession:
    context_seed = hashlib.sha256(new_id().encode("ascii")).hexdigest()
    payload = {
        "config": {"fixture": "preference-ledger"},
        "context_seed": context_seed,
        "demo_actor_id": actor.id,
        "expires_at": _authority_time(EXPIRES_AT),
    }
    demo_session = DemoSession(
        id=new_id(),
        schema_version="mirror.demo/DemoSession/v1",
        canonical_payload=payload,
        content_digest=_authority_digest("mirror.demo/DemoSession/v1", payload),
        created_at=NOW,
        demo_actor_id=actor.id,
        config=payload["config"],
        context_seed=context_seed,
        expires_at=EXPIRES_AT,
    )
    async with sessions() as session:
        session.add(demo_session)
        await session.commit()
    return demo_session


async def _aesthetic_profile(
    sessions: async_sessionmaker[AsyncSession], actor: DemoActor
) -> DemoAestheticProfile:
    payload = {
        "as_of_event_sequence": 0,
        "compilation_watermark": "b" * 64,
        "compiler_version": "preference-ledger-fixture-v1",
        "demo_actor_id": actor.id,
        "demo_job_binding_id": None,
        "evidence_digests": [],
        "generation": 1,
        "profile_payload": {"fixture": "preference-ledger"},
        "reset_epoch": 0,
    }
    profile = DemoAestheticProfile(
        id=new_id(),
        schema_version="mirror.demo/DemoAestheticProfile/v1",
        canonical_payload=payload,
        content_digest=_authority_digest("mirror.demo/DemoAestheticProfile/v1", payload),
        created_at=NOW,
        demo_actor_id=actor.id,
        demo_job_binding_id=None,
        generation=1,
        as_of_event_sequence=0,
        compilation_watermark=payload["compilation_watermark"],
        reset_epoch=0,
        compiler_version=payload["compiler_version"],
        evidence_digests=[],
        profile_payload=payload["profile_payload"],
    )
    async with sessions() as session:
        session.add(profile)
        await session.commit()
    return profile


def _command(
    actor: DemoActor,
    *,
    demo_session_id: str | None = None,
    event_type: DemoPreferenceEventType = DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION,
    source_type: DemoPreferenceSourceType = DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
    target_type: DemoPreferenceTargetType | None = None,
    target_id: str | None = None,
    signal: Mapping[str, Any] | None = None,
    occurred_at: datetime = NOW,
) -> AppendDemoPreferenceEvent:
    return AppendDemoPreferenceEvent(
        demo_actor_id=actor.id,
        demo_session_id=demo_session_id,
        event_type=event_type,
        source_type=source_type,
        target_type=target_type,
        target_id=target_id,
        signal={} if signal is None else signal,
        occurred_at=occurred_at,
    )


def _raw_event(
    actor: DemoActor,
    demo_session: DemoSession,
    *,
    sequence: int,
    previous_digest: str,
    event_type: DemoPreferenceEventType,
    signal: dict[str, Any],
    occurred_at: datetime,
) -> DemoPreferenceEvent:
    payload = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id,
        "event_sequence": sequence,
        "event_type": event_type.value,
        "occurred_at": _authority_time(occurred_at),
        "previous_event_digest": previous_digest,
        "signal": signal,
        "source_type": DemoPreferenceSourceType.SYSTEM_LIFECYCLE.value,
        "target_id": None,
        "target_type": None,
    }
    return DemoPreferenceEvent(
        id=new_id(),
        schema_version=DEMO_PREFERENCE_EVENT_SCHEMA_VERSION,
        canonical_payload=payload,
        content_digest=preference_event_content_digest(payload),
        created_at=occurred_at,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        event_sequence=sequence,
        event_type=event_type.value,
        source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE.value,
        target_type=None,
        target_id=None,
        signal=signal,
        occurred_at=occurred_at,
        previous_event_digest=previous_digest,
    )


async def _close_session(
    sessions: async_sessionmaker[AsyncSession], actor: DemoActor, demo_session: DemoSession
) -> None:
    async with sessions() as session:
        stored_session = await session.get(DemoSession, demo_session.id)
        assert stored_session is not None
        previous = await session.scalar(
            select(DemoPreferenceEvent)
            .where(DemoPreferenceEvent.demo_actor_id == actor.id)
            .order_by(DemoPreferenceEvent.event_sequence.desc())
            .limit(1)
        )
        closing_event = _raw_event(
            actor,
            demo_session,
            sequence=1 if previous is None else previous.event_sequence + 1,
            previous_digest=GENESIS_EVENT_DIGEST if previous is None else previous.content_digest,
            event_type=DemoPreferenceEventType.SESSION_CLOSED,
            signal={},
            occurred_at=NOW,
        )
        session.add(closing_event)
        stored_session.closed_at = NOW
        await session.commit()


async def _tombstone_session(
    sessions: async_sessionmaker[AsyncSession], actor: DemoActor, demo_session: DemoSession
) -> None:
    await _close_session(sessions, actor, demo_session)
    async with sessions() as session:
        stored_session = await session.get(DemoSession, demo_session.id)
        assert stored_session is not None
        existing = await session.scalar(
            select(DemoPreferenceEvent)
            .where(DemoPreferenceEvent.demo_actor_id == actor.id)
            .order_by(DemoPreferenceEvent.event_sequence.desc())
            .limit(1)
        )
        assert existing is not None
        tombstone_event = _raw_event(
            actor,
            demo_session,
            sequence=existing.event_sequence + 1,
            previous_digest=existing.content_digest,
            event_type=DemoPreferenceEventType.TOMBSTONE,
            signal={"authority_id": demo_session.id, "authority_type": "DEMO_SESSION"},
            occurred_at=NOW + timedelta(microseconds=1),
        )
        session.add(tombstone_event)
        stored_session.tombstoned_at = NOW + timedelta(microseconds=1)
        await session.commit()


@pytest.mark.asyncio
async def test_append_is_caller_transactional_and_builds_a_recomputable_chain() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        async with sessions() as session:
            async with session.begin():
                first = await append_demo_preference_event(
                    session, _command(actor, signal={"style": "minimal"})
                )
                second = await append_demo_preference_event(
                    session,
                    _command(
                        actor,
                        signal={"style": "editorial"},
                        occurred_at=NOW + timedelta(microseconds=1),
                    ),
                )
                assert first.event_sequence == 1
                assert second.event_sequence == 2
                assert second.previous_event_digest == first.event.content_digest
                assert first.event.created_at == NOW

        async with sessions() as session:
            events = list(
                (
                    await session.scalars(
                        select(DemoPreferenceEvent)
                        .where(DemoPreferenceEvent.demo_actor_id == actor.id)
                        .order_by(DemoPreferenceEvent.event_sequence)
                    )
                ).all()
            )
        assert verify_demo_preference_event_chain(events) == DemoPreferenceChainVerification(
            demo_actor_id=actor.id,
            event_count=2,
            final_content_digest=events[-1].content_digest,
        )


@pytest.mark.asyncio
async def test_concurrent_appends_are_serialized_by_the_actor_lock() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        barrier = asyncio.Barrier(2)

        async def append(marker: str) -> int:
            async with sessions() as session:
                async with session.begin():
                    await barrier.wait()
                    result = await append_demo_preference_event(
                        session,
                        _command(actor, signal={"marker": marker}),
                    )
                    return result.event_sequence

        assert sorted(await asyncio.gather(append("left"), append("right"))) == [1, 2]
        async with sessions() as session:
            sequences = list(
                (
                    await session.scalars(
                        select(DemoPreferenceEvent.event_sequence)
                        .where(DemoPreferenceEvent.demo_actor_id == actor.id)
                        .order_by(DemoPreferenceEvent.event_sequence)
                    )
                ).all()
            )
        assert sequences == [1, 2]


@pytest.mark.asyncio
async def test_session_and_actor_fail_closed_boundaries() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        foreign_actor = await _actor(sessions)
        active_session = await _demo_session(sessions, actor)
        async with sessions() as session:
            async with session.begin():
                with pytest.raises(DemoPreferenceSessionUnavailable):
                    await append_demo_preference_event(
                        session, _command(foreign_actor, demo_session_id=active_session.id)
                    )

        closed_session = await _demo_session(sessions, actor)
        await _close_session(sessions, actor, closed_session)
        async with sessions() as session:
            async with session.begin():
                with pytest.raises(DemoPreferenceSessionUnavailable):
                    await append_demo_preference_event(
                        session, _command(actor, demo_session_id=closed_session.id)
                    )

        tombstoned_session = await _demo_session(sessions, actor)
        await _tombstone_session(sessions, actor, tombstoned_session)
        async with sessions() as session:
            async with session.begin():
                with pytest.raises(DemoPreferenceSessionUnavailable):
                    await append_demo_preference_event(
                        session, _command(actor, demo_session_id=tombstoned_session.id)
                    )

        async with sessions() as session:
            async with session.begin():
                await append_demo_preference_event(
                    session,
                    _command(
                        actor,
                        event_type=DemoPreferenceEventType.ACTOR_TOMBSTONED,
                        source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
                        target_type=DemoPreferenceTargetType.DEMO_ACTOR,
                        target_id=actor.id,
                    ),
                )
                stored_actor = await session.get(DemoActor, actor.id)
                assert stored_actor is not None
                stored_actor.tombstoned_at = NOW

        async with sessions() as session:
            async with session.begin():
                with pytest.raises(DemoPreferenceActorUnavailable):
                    await append_demo_preference_event(session, _command(actor))


@pytest.mark.asyncio
async def test_timezone_float_rollback_and_chain_tampering_fail_closed() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        china_time = NOW.astimezone(timezone(timedelta(hours=8)))
        async with sessions() as session:
            await session.begin()
            result = await append_demo_preference_event(
                session,
                _command(actor, occurred_at=china_time, signal={"level_ppm": 125_000}),
            )
            assert result.event.occurred_at == NOW
            assert result.event.canonical_payload["occurred_at"] == _authority_time(NOW)
            await session.rollback()

        async with sessions() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == actor.id)
            )
            assert count == 0
            await session.rollback()
            async with session.begin():
                with pytest.raises(DemoPreferenceLedgerInputError, match="canonical JSON"):
                    await append_demo_preference_event(
                        session, _command(actor, signal={"unquantized": 0.125})
                    )

        async with sessions() as session:
            async with session.begin():
                result = await append_demo_preference_event(session, _command(actor))
        tampered = DemoPreferenceEvent(
            id=result.event.id,
            schema_version=result.event.schema_version,
            canonical_payload={**result.event.canonical_payload, "signal": {"changed": 1}},
            content_digest=result.event.content_digest,
            created_at=result.event.created_at,
            demo_actor_id=result.event.demo_actor_id,
            demo_session_id=result.event.demo_session_id,
            event_sequence=result.event.event_sequence,
            event_type=result.event.event_type,
            source_type=result.event.source_type,
            target_type=result.event.target_type,
            target_id=result.event.target_id,
            signal=result.event.signal,
            occurred_at=result.event.occurred_at,
            previous_event_digest=result.event.previous_event_digest,
        )
        with pytest.raises(DemoPreferenceLedgerCorruption, match="canonical payload"):
            verify_demo_preference_event_chain([tampered])


def test_allowlists_exactly_match_the_persisted_constraints() -> None:
    assert {event.value for event in DemoPreferenceEventType} == {
        "EXPLICIT_STYLE_SELECTION",
        "FEATURE_LOCKED",
        "FEATURE_UNLOCKED",
        "TEMPORARY_SESSION_OVERRIDE",
        "MAXIMUM_INTENSITY_CHANGED",
        "PROHIBITED_OPERATION_ADDED",
        "IMAGE_ACCEPTED",
        "IMAGE_REJECTED",
        "IMAGE_ADJUSTED",
        "LEARNING_DISABLED",
        "LEARNING_ENABLED",
        "RESET",
        "ROLLBACK",
        "TOMBSTONE",
        "DELETE",
        "SESSION_CLOSED",
        "ACTOR_TOMBSTONED",
        "EDITING_SESSION_CLOSED",
    }
    assert {source.value for source in DemoPreferenceSourceType} == {
        "EXPLICIT_USER_ACTION",
        "QUESTIONNAIRE",
        "SELF_TRANSFER",
        "EDIT_FEEDBACK",
        "SYSTEM_LIFECYCLE",
    }
    assert {target.value for target in DemoPreferenceTargetType} == {
        "DEMO_ACTOR",
        "BASELINE_FACE_MODEL",
        "SELF_STATE",
        "DESIRED_DELTA_PROFILE",
        "STYLE_PROFILE",
        "REFERENCE_PROFILE",
        "IMAGE_VERSION",
        "AESTHETIC_PROFILE",
        "CONTEXT_COMPILATION",
    }


@pytest.mark.asyncio
async def test_lifecycle_events_are_append_only_and_do_not_materialize_profiles() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        aesthetic_profile = await _aesthetic_profile(sessions, actor)
        async with sessions() as session:
            async with session.begin():
                await append_demo_preference_event(
                    session,
                    _command(
                        actor,
                        event_type=DemoPreferenceEventType.RESET,
                        source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
                        target_type=DemoPreferenceTargetType.DEMO_ACTOR,
                        target_id=actor.id,
                        signal={"reset_watermark": 0},
                    ),
                )
                for index, event_type in enumerate(
                    (
                        DemoPreferenceEventType.ROLLBACK,
                        DemoPreferenceEventType.TOMBSTONE,
                        DemoPreferenceEventType.DELETE,
                    ),
                    start=1,
                ):
                    await append_demo_preference_event(
                        session,
                        _command(
                            actor,
                            event_type=event_type,
                            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
                            target_type=DemoPreferenceTargetType.AESTHETIC_PROFILE,
                            target_id=aesthetic_profile.id,
                            occurred_at=NOW + timedelta(seconds=index),
                        ),
                    )
        async with sessions() as session:
            event_types = list(
                (
                    await session.scalars(
                        select(DemoPreferenceEvent.event_type)
                        .where(DemoPreferenceEvent.demo_actor_id == actor.id)
                        .order_by(DemoPreferenceEvent.event_sequence)
                    )
                ).all()
            )
            profile_count = await session.scalar(
                select(func.count())
                .select_from(DemoAestheticProfile)
                .where(DemoAestheticProfile.demo_actor_id == actor.id)
            )
            stored_profile = await session.get(DemoAestheticProfile, aesthetic_profile.id)
        assert event_types == ["RESET", "ROLLBACK", "TOMBSTONE", "DELETE"]
        assert profile_count == 1
        assert stored_profile is not None
        assert stored_profile.content_digest == aesthetic_profile.content_digest
        assert stored_profile.canonical_payload == aesthetic_profile.canonical_payload
