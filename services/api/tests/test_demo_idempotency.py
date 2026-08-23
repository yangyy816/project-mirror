from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import _insert_full_demo_graph, _insert_job_binding

from mirror_api.demo_idempotency import (
    DEMO_COMMAND_BINDING_SCHEMA_VERSION,
    IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD,
    SUPPORTED_DEMO_OPERATIONS,
    DemoIdempotencyInputError,
    DemoIdempotencyPayloadConflict,
    DemoIdempotencyTarget,
    DemoSemanticIdempotencyCoordinator,
    binding_content_digest,
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DEMO_TABLE_NAMES,
    DemoActor,
    DemoCommandBinding,
    DemoQuestionnaireStep,
    DemoSession,
)
from mirror_api.models import Job, new_id

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)
EXPIRES_AT = datetime(2026, 8, 24, tzinfo=UTC)


def _canonical_json(value: dict[str, Any]) -> bytes:
    return canonical_json_bytes(value)


def _authority_digest(schema_version: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(schema_version.encode() + b"\n" + _canonical_json(payload)).hexdigest()


def _authority_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        raise RuntimeError("TEST_DATABASE_URL is required for the PostgreSQL idempotency gate")
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


def _session_target_creator(
    *, actor_id: str, marker: str, invalid_binding_scope: bool = False
) -> Callable[[AsyncSession], Awaitable[DemoIdempotencyTarget[DemoSession]]]:
    async def create_target(session: AsyncSession) -> DemoIdempotencyTarget[DemoSession]:
        context_seed = hashlib.sha256(marker.encode()).hexdigest()
        payload = {
            "config": {"marker": marker},
            "context_seed": context_seed,
            "demo_actor_id": actor_id,
            "expires_at": _authority_time(EXPIRES_AT),
        }
        target = DemoSession(
            id=new_id(),
            schema_version="mirror.demo/DemoSession/v1",
            canonical_payload=payload,
            content_digest=_authority_digest("mirror.demo/DemoSession/v1", payload),
            created_at=NOW,
            demo_actor_id=actor_id,
            config={"marker": marker},
            context_seed=context_seed,
            expires_at=EXPIRES_AT,
        )
        session.add(target)
        return DemoIdempotencyTarget(
            value=target,
            response_id=target.id,
            demo_session_id=None if invalid_binding_scope else target.id,
        )

    return create_target


async def _session_target_loader(
    session: AsyncSession, binding: DemoCommandBinding
) -> DemoIdempotencyTarget[DemoSession] | None:
    target = await session.get(DemoSession, binding.response_id)
    if target is None:
        return None
    return DemoIdempotencyTarget(
        value=target,
        response_id=target.id,
        demo_session_id=target.id,
    )


async def _count(
    sessions: async_sessionmaker[AsyncSession], model: type[DemoSession] | type[DemoCommandBinding]
) -> int:
    async with sessions() as session:
        result = await session.scalar(select(func.count()).select_from(model))
    assert isinstance(result, int)
    return result


def test_semantic_digest_uses_deterministic_canonical_json() -> None:
    first = {"nested": {"z": 2, "a": [True, None]}, "message": "中文"}
    second = {"message": "中文", "nested": {"a": [True, None], "z": 2}}
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert semantic_request_digest(first) == semantic_request_digest(second)


def test_semantic_digest_rejects_raw_float_authority() -> None:
    with pytest.raises(DemoIdempotencyInputError, match="quantized integer"):
        semantic_request_digest({"posterior_mean": 0.125})


@pytest.mark.parametrize("invalid_key", ["short", "x" * 129, "bad key!"])
def test_idempotency_key_matches_public_http_boundary(invalid_key: str) -> None:
    with pytest.raises(DemoIdempotencyInputError):
        idempotency_key_hash(invalid_key)

    assert len(idempotency_key_hash("valid-key")) == 64


def test_supported_operation_map_is_exact() -> None:
    assert {
        operation: (response.response_type, response.response_status)
        for operation, response in SUPPORTED_DEMO_OPERATIONS.items()
    } == {
        "session.create": ("DEMO_SESSION", 201),
        "questionnaire.response.create": ("QUESTIONNAIRE_STEP", 201),
        "style_feedback.create": ("PREFERENCE_EVENT", 201),
        "constraint.create": ("IDENTITY_CONSTRAINTS", 201),
        "image_version.feedback": ("PREFERENCE_EVENT", 201),
        "job.cancel": ("JOB", 200),
    }


@pytest.mark.asyncio
async def test_same_payload_replay_reloads_one_target_and_one_binding() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        coordinator = DemoSemanticIdempotencyCoordinator(session_factory=sessions)
        request = {"config": {"mode": "baseline"}}
        first = await coordinator.execute(
            demo_actor_id=actor.id,
            endpoint_operation="session.create",
            idempotency_key="session-create-key",
            semantic_request=request,
            create_target=_session_target_creator(actor_id=actor.id, marker="first"),
            load_target=_session_target_loader,
        )
        replay = await coordinator.execute(
            demo_actor_id=actor.id,
            endpoint_operation="session.create",
            idempotency_key="session-create-key",
            semantic_request={"config": {"mode": "baseline"}},
            create_target=_session_target_creator(actor_id=actor.id, marker="loser"),
            load_target=_session_target_loader,
        )

        assert first.replayed is False
        assert replay.replayed is True
        assert replay.target_id == first.target_id
        assert replay.binding_id == first.binding_id
        assert await _count(sessions, DemoSession) == 1
        assert await _count(sessions, DemoCommandBinding) == 1


@pytest.mark.asyncio
async def test_different_payload_conflict_keeps_only_canonical_winner() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        coordinator = DemoSemanticIdempotencyCoordinator(session_factory=sessions)
        await coordinator.execute(
            demo_actor_id=actor.id,
            endpoint_operation="session.create",
            idempotency_key="shared-key",
            semantic_request={"mode": "one"},
            create_target=_session_target_creator(actor_id=actor.id, marker="winner"),
            load_target=_session_target_loader,
        )
        with pytest.raises(DemoIdempotencyPayloadConflict) as conflict:
            await coordinator.execute(
                demo_actor_id=actor.id,
                endpoint_operation="session.create",
                idempotency_key="shared-key",
                semantic_request={"mode": "two"},
                create_target=_session_target_creator(actor_id=actor.id, marker="loser"),
                load_target=_session_target_loader,
            )
        assert conflict.value.code == IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD
        assert await _count(sessions, DemoSession) == 1
        assert await _count(sessions, DemoCommandBinding) == 1


@pytest.mark.asyncio
async def test_stateful_questionnaire_and_job_replays_never_reinvoke_mutation_creator() -> None:
    async with _database() as sessions:
        async with sessions() as setup_session:

            def setup_stateful_authorities(sync_session: Session) -> tuple[str, ...]:
                graph = _insert_full_demo_graph(sync_session, include_episode=False)
                actor = graph["actor"]
                demo_session = graph["session"]
                job, _ = _insert_job_binding(
                    sync_session,
                    actor,
                    endpoint_operation="profile.compile",
                    target_type="DEMO_ACTOR",
                    target_id=actor.id,
                    demo_session=demo_session,
                )
                return (
                    actor.id,
                    demo_session.id,
                    graph["questionnaire_run"].id,
                    graph["question_pair"].id,
                    job.id,
                )

            actor_id, session_id, run_id, pair_id, job_id = await setup_session.run_sync(
                setup_stateful_authorities
            )

        coordinator = DemoSemanticIdempotencyCoordinator(session_factory=sessions)

        async def create_questionnaire_response(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoQuestionnaireStep]:
            fields = {
                "demo_actor_id": actor_id,
                "demo_session_id": session_id,
                "questionnaire_run_id": run_id,
                "event_sequence": 3,
                "step_number": 2,
                "event_type": "RESPONDED",
                "question_pair_id": pair_id,
                "routing_snapshot": {"selected": 1},
                "response_snapshot": {"choice": "RIGHT"},
                "posterior_before": {"jaw_width_ppm": 1_000},
                "posterior_after": {"jaw_width_ppm": 2_000},
                "scheduler_version": "fixture-scheduler-v1",
            }
            schema_version = "mirror.demo/DemoQuestionnaireStep/v1"
            target = DemoQuestionnaireStep(
                id=new_id(),
                schema_version=schema_version,
                canonical_payload=fields,
                content_digest=_authority_digest(schema_version, fields),
                created_at=NOW,
                **fields,
            )
            session.add(target)
            return DemoIdempotencyTarget(
                value=target,
                response_id=target.id,
                demo_session_id=session_id,
            )

        async def load_questionnaire_response(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[DemoQuestionnaireStep] | None:
            target = await session.get(DemoQuestionnaireStep, binding.response_id)
            if target is None:
                return None
            return DemoIdempotencyTarget(
                value=target,
                response_id=target.id,
                demo_session_id=target.demo_session_id,
            )

        questionnaire_request = {"expected_run_version": 7, "selected_side": "RIGHT"}
        questionnaire_first = await coordinator.execute(
            demo_actor_id=actor_id,
            endpoint_operation="questionnaire.response.create",
            idempotency_key="questionnaire-state-key",
            semantic_request=questionnaire_request,
            create_target=create_questionnaire_response,
            load_target=load_questionnaire_response,
        )

        async def questionnaire_state_already_advanced(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoQuestionnaireStep]:
            del session
            raise AssertionError("questionnaire replay must not advance the run twice")

        bindings_after_questionnaire_create = await _count(sessions, DemoCommandBinding)
        questionnaire_replay = await coordinator.execute(
            demo_actor_id=actor_id,
            endpoint_operation="questionnaire.response.create",
            idempotency_key="questionnaire-state-key",
            semantic_request={"selected_side": "RIGHT", "expected_run_version": 7},
            create_target=questionnaire_state_already_advanced,
            load_target=load_questionnaire_response,
        )
        assert questionnaire_replay.replayed is True
        assert questionnaire_replay.target_id == questionnaire_first.target_id

        with pytest.raises(DemoIdempotencyPayloadConflict):
            await coordinator.execute(
                demo_actor_id=actor_id,
                endpoint_operation="questionnaire.response.create",
                idempotency_key="questionnaire-state-key",
                semantic_request={"selected_side": "LEFT", "expected_run_version": 7},
                create_target=questionnaire_state_already_advanced,
                load_target=load_questionnaire_response,
            )
        assert await _count(sessions, DemoCommandBinding) == bindings_after_questionnaire_create

        async def cancel_job(session: AsyncSession) -> DemoIdempotencyTarget[Job]:
            target = await session.get(Job, job_id)
            assert target is not None
            target.status = "CANCELLED"
            target.finalized_at = NOW
            target.result_code = "USER_REQUEST"
            return DemoIdempotencyTarget(
                value=target,
                response_id=target.id,
                demo_session_id=session_id,
            )

        async def load_cancelled_job(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[Job] | None:
            target = await session.get(Job, binding.response_id)
            if target is None:
                return None
            return DemoIdempotencyTarget(
                value=target,
                response_id=target.id,
                demo_session_id=session_id,
            )

        job_request = {"expected_status": "PENDING", "reason": "USER_REQUEST"}
        job_first = await coordinator.execute(
            demo_actor_id=actor_id,
            endpoint_operation="job.cancel",
            idempotency_key="job-cancel-state-key",
            semantic_request=job_request,
            create_target=cancel_job,
            load_target=load_cancelled_job,
        )

        async def job_state_already_cancelled(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[Job]:
            del session
            raise AssertionError("job replay must not cancel an already terminal job")

        bindings_after_job_cancel = await _count(sessions, DemoCommandBinding)
        job_replay = await coordinator.execute(
            demo_actor_id=actor_id,
            endpoint_operation="job.cancel",
            idempotency_key="job-cancel-state-key",
            semantic_request={"reason": "USER_REQUEST", "expected_status": "PENDING"},
            create_target=job_state_already_cancelled,
            load_target=load_cancelled_job,
        )
        assert job_replay.replayed is True
        assert job_replay.target_id == job_first.target_id

        with pytest.raises(DemoIdempotencyPayloadConflict):
            await coordinator.execute(
                demo_actor_id=actor_id,
                endpoint_operation="job.cancel",
                idempotency_key="job-cancel-state-key",
                semantic_request={"expected_status": "RUNNING", "reason": "USER_REQUEST"},
                create_target=job_state_already_cancelled,
                load_target=load_cancelled_job,
            )

        assert await _count(sessions, DemoCommandBinding) == bindings_after_job_cancel


@pytest.mark.asyncio
async def test_concurrent_creators_reload_one_committed_canonical_winner() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        coordinator = DemoSemanticIdempotencyCoordinator(session_factory=sessions)
        barrier = asyncio.Barrier(2)

        def delayed_creator(
            marker: str,
        ) -> Callable[[AsyncSession], Awaitable[DemoIdempotencyTarget[DemoSession]]]:
            creator = _session_target_creator(actor_id=actor.id, marker=marker)

            async def create_target(session: AsyncSession) -> DemoIdempotencyTarget[DemoSession]:
                target = await creator(session)
                await barrier.wait()
                return target

            return create_target

        results = await asyncio.gather(
            coordinator.execute(
                demo_actor_id=actor.id,
                endpoint_operation="session.create",
                idempotency_key="concurrent-key",
                semantic_request={"mode": "same"},
                create_target=delayed_creator("left"),
                load_target=_session_target_loader,
            ),
            coordinator.execute(
                demo_actor_id=actor.id,
                endpoint_operation="session.create",
                idempotency_key="concurrent-key",
                semantic_request={"mode": "same"},
                create_target=delayed_creator("right"),
                load_target=_session_target_loader,
            ),
        )
        assert {result.target_id for result in results}.__len__() == 1
        assert sorted(result.replayed for result in results) == [False, True]
        assert await _count(sessions, DemoSession) == 1
        assert await _count(sessions, DemoCommandBinding) == 1


@pytest.mark.asyncio
async def test_binding_validation_failure_rolls_back_candidate_target_and_binding() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        coordinator = DemoSemanticIdempotencyCoordinator(session_factory=sessions)
        with pytest.raises(DBAPIError):
            await coordinator.execute(
                demo_actor_id=actor.id,
                endpoint_operation="session.create",
                idempotency_key="invalid-binding-key",
                semantic_request={"mode": "invalid"},
                create_target=_session_target_creator(
                    actor_id=actor.id, marker="invalid", invalid_binding_scope=True
                ),
                load_target=_session_target_loader,
            )
        assert await _count(sessions, DemoSession) == 0
        assert await _count(sessions, DemoCommandBinding) == 0


@pytest.mark.asyncio
async def test_binding_content_digest_and_canonical_payload_pass_actual_trigger() -> None:
    async with _database() as sessions:
        actor = await _actor(sessions)
        coordinator = DemoSemanticIdempotencyCoordinator(session_factory=sessions)
        result = await coordinator.execute(
            demo_actor_id=actor.id,
            endpoint_operation="session.create",
            idempotency_key="trigger-canonical-key",
            semantic_request={"request": {"alpha": 1, "beta": 2}},
            create_target=_session_target_creator(actor_id=actor.id, marker="trigger"),
            load_target=_session_target_loader,
        )
        async with sessions() as session:
            binding = await session.get(DemoCommandBinding, result.binding_id)
        assert binding is not None
        assert binding.schema_version == DEMO_COMMAND_BINDING_SCHEMA_VERSION
        assert binding.content_digest == binding_content_digest(binding.canonical_payload)
