from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from importlib import import_module
from typing import Any, Protocol, cast

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import (
    DEMO_TABLE_NAMES,
    DemoAcceptedVisualEpisode,
    DemoActor,
    DemoAestheticProfile,
    DemoContextCompilation,
    DemoEditingSession,
    DemoPreferenceEvent,
    DemoSession,
)
from mirror_api.demo_preference_ledger import (
    DEMO_ACCEPTED_VISUAL_EPISODE_SCHEMA_VERSION,
    DEMO_PREFERENCE_EVENT_SCHEMA_VERSION,
    GENESIS_EVENT_DIGEST,
    AppendDemoPreferenceEvent,
    DemoAcceptedVisualEpisodeFinalSaveResult,
    DemoPreferenceActorUnavailable,
    DemoPreferenceChainVerification,
    DemoPreferenceEventType,
    DemoPreferenceFinalSaveUnavailable,
    DemoPreferenceLedgerCorruption,
    DemoPreferenceLedgerInputError,
    DemoPreferenceSessionUnavailable,
    DemoPreferenceSourceType,
    DemoPreferenceTargetType,
    FinalizeDemoAcceptedVisualEpisode,
    append_demo_preference_event,
    finalize_demo_accepted_visual_episode,
    list_demo_final_save_episodes,
    preference_event_content_digest,
    verify_demo_preference_event_chain,
)
from mirror_api.models import new_id

NOW = datetime(2026, 8, 23, 12, 30, 15, 123456, tzinfo=UTC)
EXPIRES_AT = NOW + timedelta(days=1)


@dataclass(frozen=True)
class _FinalSaveFixture:
    demo_actor_id: str
    demo_session_id: str
    editing_session_id: str
    accepted_image_version_id: str
    event_only_acceptance_event_id: str


class _InsertFullDemoGraph(Protocol):
    def __call__(
        self,
        session: Session,
        *,
        include_episode: bool = True,
        plan_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class _InsertTwoOperationExecution(Protocol):
    def __call__(self, session: Session, graph: dict[str, Any]) -> dict[str, Any]: ...


class _TruncateDemoAuthority(Protocol):
    def __call__(self, session: Session) -> None: ...


@asynccontextmanager
async def _final_save_database(
    *,
    plan_overrides: dict[str, Any] | None = None,
    intermediate_operation_as_terminal: bool = False,
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], _FinalSaveFixture]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    sync_database_url = database_url.replace("+asyncpg", "+psycopg")
    sync_engine = create_engine(sync_database_url)
    schema_invariants = import_module("test_demo_schema_authority_invariants")
    insert_full_demo_graph = cast(
        _InsertFullDemoGraph,
        vars(schema_invariants)["_insert_full_demo_graph"],
    )
    truncate_demo_authority = cast(
        _TruncateDemoAuthority,
        vars(schema_invariants)["_truncate_demo_authority"],
    )
    insert_two_operation_execution = cast(
        _InsertTwoOperationExecution,
        vars(schema_invariants)["_insert_two_operation_execution"],
    )
    try:
        with Session(sync_engine) as sync_session:
            truncate_demo_authority(sync_session)
            graph = insert_full_demo_graph(
                sync_session,
                include_episode=False,
                plan_overrides=plan_overrides,
            )
            accepted_image_version_id = graph["image1"].id
            if intermediate_operation_as_terminal:
                execution = insert_two_operation_execution(sync_session, graph)
                accepted_image_version_id = execution["first_step"]["image"].id
            fixture = _FinalSaveFixture(
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                editing_session_id=graph["editing_session"].id,
                accepted_image_version_id=accepted_image_version_id,
                event_only_acceptance_event_id=graph["accepted_event"].id,
            )
        engine = create_async_engine(database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            yield sessions, fixture
        finally:
            await engine.dispose()
    finally:
        with Session(sync_engine) as sync_session:
            truncate_demo_authority(sync_session)
        sync_engine.dispose()


def _final_save_command(fixture: _FinalSaveFixture) -> FinalizeDemoAcceptedVisualEpisode:
    return FinalizeDemoAcceptedVisualEpisode(
        demo_actor_id=fixture.demo_actor_id,
        demo_session_id=fixture.demo_session_id,
        editing_session_id=fixture.editing_session_id,
        accepted_image_version_id=fixture.accepted_image_version_id,
        source_type=DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
        signal={"final_save": 1},
        occurred_at=NOW + timedelta(hours=1),
    )


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


async def _alternate_editing_session(
    sessions: async_sessionmaker[AsyncSession],
    fixture: _FinalSaveFixture,
) -> DemoEditingSession:
    async with sessions() as session:
        original = await session.get(DemoEditingSession, fixture.editing_session_id)
        assert original is not None
        context_digest = hashlib.sha256(b"alternate-editing-context").hexdigest()
        payload = {
            **original.canonical_payload,
            "context_digest": context_digest,
        }
        alternate = DemoEditingSession(
            id=new_id(),
            schema_version=original.schema_version,
            canonical_payload=payload,
            content_digest=_authority_digest(original.schema_version, payload),
            created_at=NOW,
            demo_actor_id=original.demo_actor_id,
            demo_session_id=original.demo_session_id,
            source_asset_id=original.source_asset_id,
            source_asset_sha256=original.source_asset_sha256,
            desired_delta_profile_digest=original.desired_delta_profile_digest,
            style_profile_digest=original.style_profile_digest,
            identity_constraints_digest=original.identity_constraints_digest,
            context_digest=context_digest,
            instruction_digest=original.instruction_digest,
            tool_registry_version=original.tool_registry_version,
            closed_at=None,
            tombstoned_at=None,
        )
        session.add(alternate)
        await session.commit()
        return alternate


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


async def _direct_sql_append(
    session: AsyncSession,
    actor: DemoActor,
    *,
    marker: str,
    content_digest_override: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
) -> tuple[int, str]:
    """Exercise a non-service writer using the shared PostgreSQL lock namespace."""

    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended('mirror.demo.preference/' || :demo_actor_id, 0))"
        ),
        {"demo_actor_id": actor.id},
    )
    previous = await session.scalar(
        select(DemoPreferenceEvent)
        .where(DemoPreferenceEvent.demo_actor_id == actor.id)
        .order_by(DemoPreferenceEvent.event_sequence.desc())
        .limit(1)
    )
    sequence = 1 if previous is None else previous.event_sequence + 1
    previous_digest = GENESIS_EVENT_DIGEST if previous is None else previous.content_digest
    occurred_at = NOW + timedelta(seconds=sequence)
    signal = {"direct_sql_marker": marker}
    payload = {
        "demo_actor_id": actor.id,
        "demo_session_id": None,
        "event_sequence": sequence,
        "event_type": DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION.value,
        "occurred_at": _authority_time(occurred_at),
        "previous_event_digest": previous_digest,
        "signal": signal,
        "source_type": DemoPreferenceSourceType.EXPLICIT_USER_ACTION.value,
        "target_id": target_id,
        "target_type": target_type,
    }
    content_digest = content_digest_override or preference_event_content_digest(payload)
    await session.execute(
        text(
            "INSERT INTO demo_preference_events ("
            "id, schema_version, canonical_payload, content_digest, created_at, "
            "demo_actor_id, demo_session_id, event_sequence, event_type, source_type, "
            "target_type, target_id, signal, occurred_at, previous_event_digest"
            ") VALUES ("
            ":id, :schema_version, CAST(:canonical_payload AS jsonb), :content_digest, "
            ":created_at, :demo_actor_id, NULL, :event_sequence, :event_type, "
            ":source_type, :target_type, :target_id, CAST(:signal AS jsonb), "
            ":occurred_at, :previous_event_digest"
            ")"
        ),
        {
            "id": new_id(),
            "schema_version": DEMO_PREFERENCE_EVENT_SCHEMA_VERSION,
            "canonical_payload": json.dumps(payload),
            "content_digest": content_digest,
            "created_at": NOW + timedelta(days=1),
            "demo_actor_id": actor.id,
            "event_sequence": sequence,
            "event_type": DemoPreferenceEventType.EXPLICIT_STYLE_SELECTION.value,
            "source_type": DemoPreferenceSourceType.EXPLICIT_USER_ACTION.value,
            "target_type": target_type,
            "target_id": target_id,
            "signal": json.dumps(signal),
            "occurred_at": occurred_at,
            "previous_event_digest": previous_digest,
        },
    )
    return sequence, content_digest


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
                assert first.event.created_at != first.event.occurred_at
                assert "created_at" not in first.event.canonical_payload

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
async def test_service_and_direct_sql_append_share_the_actor_advisory_lock() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        barrier = asyncio.Barrier(2)

        async def service_append() -> int:
            async with sessions() as session:
                async with session.begin():
                    await barrier.wait()
                    result = await append_demo_preference_event(
                        session, _command(actor, signal={"service_marker": "service"})
                    )
                    return result.event_sequence

        async def direct_append() -> int:
            async with sessions() as session:
                async with session.begin():
                    await barrier.wait()
                    sequence, _ = await _direct_sql_append(session, actor, marker="direct")
                    return sequence

        assert sorted(await asyncio.gather(service_append(), direct_append())) == [1, 2]
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
        assert verify_demo_preference_event_chain(events).event_count == 2


@pytest.mark.parametrize(
    ("signal", "target_type", "target_is_actor"),
    (
        ({}, DemoPreferenceTargetType.DEMO_ACTOR, True),
        ({"reset_watermark": -1}, DemoPreferenceTargetType.DEMO_ACTOR, True),
        ({"reset_watermark": False}, DemoPreferenceTargetType.DEMO_ACTOR, True),
        ({"reset_watermark": "0"}, DemoPreferenceTargetType.DEMO_ACTOR, True),
        ({"reset_watermark": 1}, DemoPreferenceTargetType.DEMO_ACTOR, True),
        ({"reset_watermark": 2}, DemoPreferenceTargetType.DEMO_ACTOR, True),
        ({"reset_watermark": 0}, DemoPreferenceTargetType.AESTHETIC_PROFILE, False),
    ),
    ids=(
        "missing-watermark",
        "negative-watermark",
        "bool-watermark",
        "non-integer-watermark",
        "current-sequence-watermark",
        "future-sequence-watermark",
        "non-actor-target",
    ),
)
@pytest.mark.asyncio
async def test_reset_rejects_noncanonical_or_not_strictly_earlier_watermarks(
    signal: Mapping[str, Any],
    target_type: DemoPreferenceTargetType,
    target_is_actor: bool,
) -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        target_id = actor.id if target_is_actor else new_id()
        async with sessions() as session:
            with pytest.raises(
                DemoPreferenceLedgerInputError,
                match="strict earlier event watermark",
            ):
                async with session.begin():
                    await append_demo_preference_event(
                        session,
                        _command(
                            actor,
                            event_type=DemoPreferenceEventType.RESET,
                            source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
                            target_type=target_type,
                            target_id=target_id,
                            signal=signal,
                        ),
                    )

        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == actor.id)
                )
                == 0
            )


@pytest.mark.asyncio
async def test_reset_accepts_an_earlier_watermark_and_preserves_history() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        async with sessions() as session:
            async with session.begin():
                first = await append_demo_preference_event(
                    session,
                    _command(actor, signal={"style": "minimal"}),
                )
                second = await append_demo_preference_event(
                    session,
                    _command(
                        actor,
                        signal={"style": "editorial"},
                        occurred_at=NOW + timedelta(microseconds=1),
                    ),
                )
                reset = await append_demo_preference_event(
                    session,
                    _command(
                        actor,
                        event_type=DemoPreferenceEventType.RESET,
                        source_type=DemoPreferenceSourceType.SYSTEM_LIFECYCLE,
                        target_type=DemoPreferenceTargetType.DEMO_ACTOR,
                        target_id=actor.id,
                        signal={"reset_watermark": first.event_sequence},
                        occurred_at=NOW + timedelta(microseconds=2),
                    ),
                )

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
        assert [event.event_sequence for event in events] == [1, 2, 3]
        assert [event.content_digest for event in events[:2]] == [
            first.event.content_digest,
            second.event.content_digest,
        ]
        assert reset.event.signal == {"reset_watermark": 1}
        assert verify_demo_preference_event_chain(events).event_count == 3


@pytest.mark.asyncio
async def test_direct_sql_bad_digest_and_target_are_rejected_by_postgresql() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        async with sessions() as session:
            with pytest.raises(DBAPIError, match="canonical digest mismatch"):
                async with session.begin():
                    await _direct_sql_append(
                        session,
                        actor,
                        marker="bad-digest",
                        content_digest_override="0" * 64,
                    )
        async with sessions() as session:
            with pytest.raises(DBAPIError, match="target ownership mismatch"):
                async with session.begin():
                    await _direct_sql_append(
                        session,
                        actor,
                        marker="bad-target",
                        target_type=DemoPreferenceTargetType.IMAGE_VERSION.value,
                        target_id=new_id(),
                    )
        async with sessions() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == actor.id)
            )
        assert count == 0


@pytest.mark.asyncio
async def test_final_save_is_atomic_and_event_only_feedback_is_excluded() -> None:
    async with _final_save_database() as (sessions, fixture):
        async with sessions() as session:
            assert (
                await list_demo_final_save_episodes(
                    session,
                    demo_actor_id=fixture.demo_actor_id,
                    demo_session_id=fixture.demo_session_id,
                )
                == []
            )
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None
            profile_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoAestheticProfile)
                .where(DemoAestheticProfile.demo_actor_id == fixture.demo_actor_id)
            )
            context_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoContextCompilation)
                .where(DemoContextCompilation.demo_actor_id == fixture.demo_actor_id)
            )

        async with sessions() as session:
            async with session.begin():
                result = await finalize_demo_accepted_visual_episode(
                    session, _final_save_command(fixture)
                )
                assert isinstance(result, DemoAcceptedVisualEpisodeFinalSaveResult)
                assert result.preference_event.event_type == DemoPreferenceEventType.IMAGE_ACCEPTED
                assert result.preference_event.event_sequence == event_count_before + 1
                assert result.preference_event.target_id == fixture.accepted_image_version_id
                assert "created_at" not in result.preference_event.canonical_payload
                assert (
                    result.accepted_visual_episode.schema_version
                    == DEMO_ACCEPTED_VISUAL_EPISODE_SCHEMA_VERSION
                )
                assert (
                    result.accepted_visual_episode.acceptance_event_id == result.preference_event.id
                )

        async with sessions() as session:
            episodes = await list_demo_final_save_episodes(
                session,
                demo_actor_id=fixture.demo_actor_id,
                demo_session_id=fixture.demo_session_id,
            )
            event_count_after = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            profile_count_after = await session.scalar(
                select(func.count())
                .select_from(DemoAestheticProfile)
                .where(DemoAestheticProfile.demo_actor_id == fixture.demo_actor_id)
            )
            context_count_after = await session.scalar(
                select(func.count())
                .select_from(DemoContextCompilation)
                .where(DemoContextCompilation.demo_actor_id == fixture.demo_actor_id)
            )
        assert len(episodes) == 1
        assert episodes[0].accepted_image_version_id == fixture.accepted_image_version_id
        assert episodes[0].acceptance_event_id != fixture.event_only_acceptance_event_id
        assert event_count_after == event_count_before + 1
        assert profile_count_after == profile_count_before
        assert context_count_after == context_count_before


@pytest.mark.asyncio
async def test_final_save_rollback_reuses_the_next_sequence_without_partial_rows() -> None:
    async with _final_save_database() as (sessions, fixture):
        async with sessions() as session:
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None
            await session.rollback()
            await session.begin()
            provisional = await finalize_demo_accepted_visual_episode(
                session, _final_save_command(fixture)
            )
            assert provisional.preference_event.event_sequence == event_count_before + 1
            await session.rollback()

        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
                )
                == event_count_before
            )
            assert (
                await session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
                == 0
            )

        async with sessions() as session:
            async with session.begin():
                replay = await finalize_demo_accepted_visual_episode(
                    session, _final_save_command(fixture)
                )
                assert replay.preference_event.event_sequence == event_count_before + 1


@pytest.mark.asyncio
async def test_final_save_invalid_or_duplicate_requests_leave_no_partial_rows() -> None:
    async with _final_save_database() as (sessions, fixture):
        invalid_command = FinalizeDemoAcceptedVisualEpisode(
            demo_actor_id=fixture.demo_actor_id,
            demo_session_id=fixture.demo_session_id,
            editing_session_id=fixture.editing_session_id,
            accepted_image_version_id=new_id(),
            source_type=DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
            signal={"final_save": 1},
            occurred_at=NOW + timedelta(hours=1),
        )
        async with sessions() as session:
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None
            await session.rollback()
            with pytest.raises(DemoPreferenceFinalSaveUnavailable):
                async with session.begin():
                    await finalize_demo_accepted_visual_episode(session, invalid_command)

        async with sessions() as session:
            async with session.begin():
                await finalize_demo_accepted_visual_episode(session, _final_save_command(fixture))
        async with sessions() as session:
            with pytest.raises(DBAPIError):
                async with session.begin():
                    await finalize_demo_accepted_visual_episode(
                        session, _final_save_command(fixture)
                    )

        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
                )
                == event_count_before + 1
            )
            assert (
                await session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
                == 1
            )


@pytest.mark.asyncio
async def test_concurrent_final_saves_have_one_canonical_winner() -> None:
    async with _final_save_database() as (sessions, fixture):
        async with sessions() as session:
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None

        barrier = asyncio.Barrier(2)

        async def final_save() -> str:
            async with sessions() as session:
                try:
                    async with session.begin():
                        await barrier.wait()
                        await finalize_demo_accepted_visual_episode(
                            session,
                            _final_save_command(fixture),
                        )
                except DBAPIError:
                    return "conflict"
            return "created"

        assert sorted(await asyncio.gather(final_save(), final_save())) == [
            "conflict",
            "created",
        ]
        async with sessions() as session:
            assert (
                await session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
                )
                == event_count_before + 1
            )


@pytest.mark.asyncio
async def test_final_save_cancellation_after_event_flush_rolls_back_and_reuses_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _final_save_database() as (sessions, fixture):
        async with sessions() as session:
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None

        async with sessions() as session:
            original_flush = session.flush
            flush_count = 0

            async def cancel_after_first_flush(
                objects: Sequence[Any] | None = None,
            ) -> None:
                nonlocal flush_count
                await original_flush(objects)
                flush_count += 1
                if flush_count == 1:
                    raise asyncio.CancelledError

            monkeypatch.setattr(session, "flush", cancel_after_first_flush)
            with pytest.raises(asyncio.CancelledError):
                async with session.begin():
                    await finalize_demo_accepted_visual_episode(
                        session,
                        _final_save_command(fixture),
                    )
            assert flush_count == 1

        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
                )
                == event_count_before
            )
            assert (
                await session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
                == 0
            )

        async with sessions() as session:
            async with session.begin():
                replay = await finalize_demo_accepted_visual_episode(
                    session,
                    _final_save_command(fixture),
                )
                assert replay.preference_event.event_sequence == event_count_before + 1


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("desired_delta_profile_digest", hashlib.sha256(b"drift-profile").hexdigest()),
        ("instruction_digest", hashlib.sha256(b"drift-instruction").hexdigest()),
        ("tool_registry_version", "fixture-tools-v2"),
    ),
    ids=("profile", "instruction", "tool-registry"),
)
@pytest.mark.asyncio
async def test_final_save_rejects_terminal_plan_provenance_drift_before_event_append(
    field_name: str,
    field_value: str,
) -> None:
    async with _final_save_database(plan_overrides={field_name: field_value}) as (
        sessions,
        fixture,
    ):
        async with sessions() as session:
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None
            await session.rollback()
            with pytest.raises(
                DemoPreferenceFinalSaveUnavailable,
                match="EditPlan provenance",
            ):
                async with session.begin():
                    await finalize_demo_accepted_visual_episode(
                        session,
                        _final_save_command(fixture),
                    )
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
                )
                == event_count_before
            )
            assert (
                await session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
                == 0
            )


@pytest.mark.asyncio
async def test_final_save_rejects_nonterminal_operation_before_event_append() -> None:
    async with _final_save_database(intermediate_operation_as_terminal=True) as (
        sessions,
        fixture,
    ):
        async with sessions() as session:
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None
            await session.rollback()
            with pytest.raises(
                DemoPreferenceFinalSaveUnavailable,
                match="EditOperation provenance",
            ):
                async with session.begin():
                    await finalize_demo_accepted_visual_episode(
                        session,
                        _final_save_command(fixture),
                    )
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
                )
                == event_count_before
            )
            assert (
                await session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
                == 0
            )


@pytest.mark.asyncio
async def test_final_save_rejects_actor_session_editing_and_terminal_plan_mixing() -> None:
    async with _final_save_database() as (sessions, fixture):
        foreign_actor = await _actor(sessions)
        foreign_session = await _demo_session(sessions, foreign_actor)
        alternate_editing_session = await _alternate_editing_session(sessions, fixture)
        commands = (
            replace(
                _final_save_command(fixture),
                demo_session_id=foreign_session.id,
            ),
            replace(
                _final_save_command(fixture),
                demo_actor_id=foreign_actor.id,
                demo_session_id=foreign_session.id,
            ),
            replace(
                _final_save_command(fixture),
                editing_session_id=alternate_editing_session.id,
            ),
        )
        async with sessions() as session:
            event_count_before = await session.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
            )
            assert event_count_before is not None
        for command, error_type in zip(
            commands,
            (
                DemoPreferenceSessionUnavailable,
                DemoPreferenceFinalSaveUnavailable,
                DemoPreferenceFinalSaveUnavailable,
            ),
            strict=True,
        ):
            async with sessions() as session:
                with pytest.raises(error_type):
                    async with session.begin():
                        await finalize_demo_accepted_visual_episode(session, command)
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id)
                )
                == event_count_before
            )
            assert (
                await session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
                == 0
            )


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
async def test_non_learning_feedback_does_not_materialize_or_reinforce_stable_state() -> None:
    async with _final_save_database() as (sessions, fixture):
        async with sessions() as session:
            profile_rows_before = list(
                (
                    await session.scalars(
                        select(DemoAestheticProfile)
                        .where(DemoAestheticProfile.demo_actor_id == fixture.demo_actor_id)
                        .order_by(DemoAestheticProfile.id)
                    )
                ).all()
            )
            context_rows_before = list(
                (
                    await session.scalars(
                        select(DemoContextCompilation)
                        .where(DemoContextCompilation.demo_actor_id == fixture.demo_actor_id)
                        .order_by(DemoContextCompilation.id)
                    )
                ).all()
            )
            profile_authority_before = [
                (row.id, row.content_digest, row.canonical_payload) for row in profile_rows_before
            ]
            context_authority_before = [
                (row.id, row.content_digest, row.canonical_payload) for row in context_rows_before
            ]
            episode_count_before = await session.scalar(
                select(func.count()).select_from(DemoAcceptedVisualEpisode)
            )
            event_sequence_before = await session.scalar(
                select(func.max(DemoPreferenceEvent.event_sequence)).where(
                    DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id
                )
            )
            assert event_sequence_before is not None

        event_specs: tuple[
            tuple[
                DemoPreferenceEventType,
                DemoPreferenceSourceType,
                DemoPreferenceTargetType,
                str,
                Mapping[str, Any],
            ],
            ...,
        ] = (
            (
                DemoPreferenceEventType.IMAGE_REJECTED,
                DemoPreferenceSourceType.EDIT_FEEDBACK,
                DemoPreferenceTargetType.IMAGE_VERSION,
                fixture.accepted_image_version_id,
                {"reason": "explicit-reject"},
            ),
            (
                DemoPreferenceEventType.LEARNING_DISABLED,
                DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                DemoPreferenceTargetType.DEMO_ACTOR,
                fixture.demo_actor_id,
                {"learning_enabled": 0},
            ),
            (
                DemoPreferenceEventType.FEATURE_LOCKED,
                DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                DemoPreferenceTargetType.DEMO_ACTOR,
                fixture.demo_actor_id,
                {"feature": "eyes"},
            ),
            (
                DemoPreferenceEventType.FEATURE_UNLOCKED,
                DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                DemoPreferenceTargetType.DEMO_ACTOR,
                fixture.demo_actor_id,
                {"feature": "eyes"},
            ),
        )
        async with sessions() as session:
            async with session.begin():
                for index, (event_type, source_type, target_type, target_id, signal) in enumerate(
                    event_specs,
                    start=1,
                ):
                    await append_demo_preference_event(
                        session,
                        AppendDemoPreferenceEvent(
                            demo_actor_id=fixture.demo_actor_id,
                            demo_session_id=fixture.demo_session_id,
                            event_type=event_type,
                            source_type=source_type,
                            target_type=target_type,
                            target_id=target_id,
                            signal=signal,
                            occurred_at=NOW + timedelta(hours=2, microseconds=index),
                        ),
                    )

        async with sessions() as session:
            profile_rows_after = list(
                (
                    await session.scalars(
                        select(DemoAestheticProfile)
                        .where(DemoAestheticProfile.demo_actor_id == fixture.demo_actor_id)
                        .order_by(DemoAestheticProfile.id)
                    )
                ).all()
            )
            context_rows_after = list(
                (
                    await session.scalars(
                        select(DemoContextCompilation)
                        .where(DemoContextCompilation.demo_actor_id == fixture.demo_actor_id)
                        .order_by(DemoContextCompilation.id)
                    )
                ).all()
            )
            event_types = list(
                (
                    await session.scalars(
                        select(DemoPreferenceEvent.event_type)
                        .where(
                            DemoPreferenceEvent.demo_actor_id == fixture.demo_actor_id,
                            DemoPreferenceEvent.event_sequence > event_sequence_before,
                        )
                        .order_by(DemoPreferenceEvent.event_sequence)
                    )
                ).all()
            )
            episode_count_after = await session.scalar(
                select(func.count()).select_from(DemoAcceptedVisualEpisode)
            )

        assert event_types == [event_type.value for event_type, *_ in event_specs]
        assert [
            (row.id, row.content_digest, row.canonical_payload) for row in profile_rows_after
        ] == profile_authority_before
        assert [
            (row.id, row.content_digest, row.canonical_payload) for row in context_rows_after
        ] == context_authority_before
        assert episode_count_after == episode_count_before


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
