"""PostgreSQL-backed command and HTTP boundary tests for D05 Profile wiring."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_demo_profile_service import _authority_time, _database, _other_session

import mirror_api.demo_profile_commands as profile_commands_module
from mirror_api.demo_dependencies import get_demo_actor
from mirror_api.demo_idempotency import DemoIdempotencyPayloadConflict
from mirror_api.demo_job_service import DemoJobSnapshot, DemoJobTargetSnapshot
from mirror_api.demo_models import (
    DemoCommandBinding,
    DemoIdentityConstraints,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoSession,
)
from mirror_api.demo_preference_ledger import (
    AppendDemoPreferenceEvent,
    DemoPreferenceEventType,
    DemoPreferenceSourceType,
    append_demo_preference_event,
    verify_demo_preference_event_chain,
)
from mirror_api.demo_profile_commands import (
    DEMO_PROFILE_COMPILER_VERSION,
    CreateDemoConstraints,
    CreateDemoProfileCompilation,
    CreateDemoStyleFeedback,
    DemoActiveProfile,
    DemoConstraintLockCommand,
    DemoConstraintsResult,
    DemoProfileCommandService,
    DemoProfileCommandUnavailable,
    DemoStyleFeedbackResult,
)
from mirror_api.demo_profile_coordinator import DemoProfileCreateResult
from mirror_api.demo_profile_dependencies import (
    get_demo_profile_commands,
    get_demo_profile_coordinator,
)
from mirror_api.demo_profile_service import DemoProfileCompilationService, _authority_digest
from mirror_api.main import create_app
from mirror_api.models import Job, new_id, utcnow


def _compile_command(actor_id: str, session_id: str, key: str) -> CreateDemoProfileCompilation:
    return CreateDemoProfileCompilation(
        demo_actor_id=actor_id,
        demo_session_id=session_id,
        compiler_version=DEMO_PROFILE_COMPILER_VERSION,
        idempotency_key=key,
        request_id=f"profile-command-{new_id()}",
    )


async def _expired_session(
    sessions: async_sessionmaker[AsyncSession], *, source_session_id: str
) -> DemoSession:
    async with sessions() as session:
        async with session.begin():
            source = await session.get(DemoSession, source_session_id)
            assert source is not None
            expires_at = datetime.now(UTC) - timedelta(seconds=1)
            config = {**source.config, "profile_command_test": "expired-session"}
            payload = {
                "config": config,
                "context_seed": source.context_seed,
                "demo_actor_id": source.demo_actor_id,
                "expires_at": _authority_time(expires_at),
            }
            expired = DemoSession(
                id=new_id(),
                schema_version="mirror.demo/DemoSession/v1",
                canonical_payload=payload,
                content_digest=_authority_digest("mirror.demo/DemoSession/v1", payload),
                created_at=utcnow(),
                demo_actor_id=source.demo_actor_id,
                config=config,
                context_seed=source.context_seed,
                expires_at=expires_at,
                closed_at=None,
                tombstoned_at=None,
            )
            session.add(expired)
        return expired


@pytest.mark.asyncio
async def test_profile_compile_create_replay_conflict_and_session_authority() -> None:
    async with _database() as (sessions, context):
        commands = DemoProfileCommandService(session_factory=sessions)
        key = f"profile-create-{new_id()}"
        command = _compile_command(context.actor_id, context.session_id, key)

        created = await commands.create_compilation(command)
        replay = await commands.create_compilation(
            _compile_command(context.actor_id, context.session_id, key)
        )
        assert created.replayed is False
        assert replay.replayed is True
        assert replay.job_id == created.job_id

        concurrent_key = f"profile-concurrent-{new_id()}"
        concurrent = await asyncio.gather(
            commands.create_compilation(
                _compile_command(context.actor_id, context.session_id, concurrent_key)
            ),
            commands.create_compilation(
                _compile_command(context.actor_id, context.session_id, concurrent_key)
            ),
        )
        assert concurrent[0].job_id == concurrent[1].job_id
        assert sorted(item.replayed for item in concurrent) == [False, True]

        alternate = await _other_session(sessions, context.session_id)
        with pytest.raises(DemoIdempotencyPayloadConflict):
            await commands.create_compilation(_compile_command(context.actor_id, alternate.id, key))

        async with sessions() as session:
            job = await session.get(Job, created.job_id)
            bindings = list(
                await session.scalars(
                    select(DemoJobBinding).where(DemoJobBinding.job_id == created.job_id)
                )
            )
        assert job is not None and job.status == "PENDING" and job.payload == {}
        assert len(bindings) == 1
        binding = bindings[0]
        assert binding.demo_actor_id == context.actor_id
        assert binding.demo_session_id == context.session_id
        assert binding.target_type == "DEMO_ACTOR"
        assert binding.target_id == context.actor_id

        unavailable_session = "f" * 32
        with pytest.raises(DemoProfileCommandUnavailable):
            await commands.create_compilation(
                _compile_command(context.actor_id, unavailable_session, f"missing-{new_id()}")
            )

        expired = await _expired_session(sessions, source_session_id=context.session_id)
        with pytest.raises(DemoProfileCommandUnavailable):
            await commands.create_compilation(
                _compile_command(context.actor_id, expired.id, f"expired-{new_id()}")
            )


@pytest.mark.asyncio
async def test_style_and_constraints_are_idempotent_atomic_and_chain_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _database() as (sessions, context):
        commands = DemoProfileCommandService(session_factory=sessions)
        style = CreateDemoStyleFeedback(
            demo_actor_id=context.actor_id,
            demo_session_id=context.session_id,
            event_type="EXPLICIT_STYLE_SELECTION",
            style_key="editorial",
            idempotency_key=f"style-{new_id()}",
        )
        first_style = await commands.create_style_feedback(style)
        replay_style = await commands.create_style_feedback(style)
        assert first_style.replayed is False
        assert replay_style.replayed is True
        assert replay_style.event_id == first_style.event_id

        persistent = CreateDemoConstraints(
            demo_actor_id=context.actor_id,
            demo_session_id=None,
            scope="PERSISTENT",
            locks=(
                DemoConstraintLockCommand(
                    dimension_key="eyes", lock="PRESERVE", maximum_ppm=200_000
                ),
            ),
            prohibited_operations=("GENERATIVE",),
            idempotency_key=f"persistent-{new_id()}",
        )
        session_override = CreateDemoConstraints(
            demo_actor_id=context.actor_id,
            demo_session_id=context.session_id,
            scope="SESSION_OVERRIDE",
            locks=(DemoConstraintLockCommand(dimension_key="eyes", lock="UNLOCK"),),
            prohibited_operations=(),
            idempotency_key=f"override-{new_id()}",
        )
        persistent_result, override_result = await asyncio.gather(
            commands.create_constraints(persistent), commands.create_constraints(session_override)
        )
        assert {persistent_result.scope, override_result.scope} == {
            "PERSISTENT",
            "SESSION_OVERRIDE",
        }
        assert {persistent_result.version, override_result.version} == {1, 2}

        async with sessions() as session:
            constraints = list(
                await session.scalars(
                    select(DemoIdentityConstraints).order_by(DemoIdentityConstraints.version)
                )
            )
            events = list(
                await session.scalars(
                    select(DemoPreferenceEvent)
                    .where(DemoPreferenceEvent.demo_actor_id == context.actor_id)
                    .order_by(DemoPreferenceEvent.event_sequence)
                )
            )
            bindings = list(
                await session.scalars(
                    select(DemoCommandBinding).where(
                        DemoCommandBinding.endpoint_operation.in_(
                            ("style_feedback.create", "constraint.create")
                        )
                    )
                )
            )
            verified = verify_demo_preference_event_chain(events)
        assert len(constraints) == 2
        assert constraints[0].constraint_scope == "PERSISTENT"
        assert constraints[0].demo_session_id is None
        assert constraints[1].constraint_scope == "SESSION_OVERRIDE"
        assert constraints[1].demo_session_id == context.session_id
        assert constraints[1].locks == {"eyes": {"mode": "ALLOW_CHANGE"}}
        assert [event.event_type for event in events][-3:] == [
            "FEATURE_LOCKED",
            "PROHIBITED_OPERATION_ADDED",
            "TEMPORARY_SESSION_OVERRIDE",
        ]
        assert verified.event_count == len(events)
        assert len(bindings) == 3

        def fail_after_events(*args: object, **kwargs: object) -> dict[str, object]:
            raise RuntimeError("injected constraint snapshot failure")

        monkeypatch.setattr(profile_commands_module, "_constraint_payload", fail_after_events)
        failed = CreateDemoConstraints(
            demo_actor_id=context.actor_id,
            demo_session_id=None,
            scope="PERSISTENT",
            locks=(DemoConstraintLockCommand(dimension_key="nose", lock="PRESERVE"),),
            prohibited_operations=(),
            idempotency_key=f"rollback-{new_id()}",
        )
        with pytest.raises(RuntimeError, match="injected constraint snapshot failure"):
            await commands.create_constraints(failed)
        async with sessions() as session:
            assert len(list(await session.scalars(select(DemoIdentityConstraints)))) == 2
            assert len(
                list(
                    await session.scalars(
                        select(DemoPreferenceEvent).where(
                            DemoPreferenceEvent.demo_actor_id == context.actor_id
                        )
                    )
                )
            ) == len(events)
            assert len(
                list(
                    await session.scalars(
                        select(DemoCommandBinding).where(
                            DemoCommandBinding.endpoint_operation.in_(
                                ("style_feedback.create", "constraint.create")
                            )
                        )
                    )
                )
            ) == len(bindings)


@pytest.mark.asyncio
async def test_active_profile_uses_generation_and_ledger_toggle_not_wall_clock() -> None:
    async with _database() as (sessions, context):
        commands = DemoProfileCommandService(session_factory=sessions)
        compiler = DemoProfileCompilationService(session_factory=sessions)
        first = await commands.create_compilation(
            _compile_command(context.actor_id, context.session_id, f"compile-a-{new_id()}")
        )
        await compiler.compile(demo_actor_id=context.actor_id, job_id=first.job_id)
        second = await commands.create_compilation(
            _compile_command(context.actor_id, context.session_id, f"compile-b-{new_id()}")
        )
        await compiler.compile(demo_actor_id=context.actor_id, job_id=second.job_id)

        async with sessions() as session:
            await append_demo_preference_event(
                session,
                AppendDemoPreferenceEvent(
                    demo_actor_id=context.actor_id,
                    demo_session_id=None,
                    event_type=DemoPreferenceEventType.LEARNING_DISABLED,
                    source_type=DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                    target_type=None,
                    target_id=None,
                    signal={},
                    occurred_at=utcnow(),
                ),
            )
            await session.commit()
        active = await commands.active_profiles(demo_actor_id=context.actor_id)
        assert len(active) == 1
        assert active[0].generation == 2
        assert active[0].learning_enabled is False

        async with sessions() as session:
            await append_demo_preference_event(
                session,
                AppendDemoPreferenceEvent(
                    demo_actor_id=context.actor_id,
                    demo_session_id=None,
                    event_type=DemoPreferenceEventType.LEARNING_ENABLED,
                    source_type=DemoPreferenceSourceType.EXPLICIT_USER_ACTION,
                    target_type=None,
                    target_id=None,
                    signal={},
                    occurred_at=utcnow(),
                ),
            )
            await session.commit()
        assert (await commands.active_profiles(demo_actor_id=context.actor_id))[
            0
        ].learning_enabled is True


_ACTOR_ID = "1" * 32
_SESSION_ID = "2" * 32
_JOB_ID = "3" * 32


@dataclass
class _RouteCoordinator:
    received: CreateDemoProfileCompilation | None = None
    payload_conflict: bool = False

    async def create(self, command: CreateDemoProfileCompilation) -> DemoProfileCreateResult:
        if self.payload_conflict:
            raise DemoIdempotencyPayloadConflict()
        self.received = command
        return DemoProfileCreateResult(
            job=DemoJobSnapshot(
                job_id=_JOB_ID,
                demo_actor_id=_ACTOR_ID,
                demo_session_id=_SESSION_ID,
                status="PENDING",
                capability="P5_COMPILER",
                job_binding_digest="4" * 64,
                target=DemoJobTargetSnapshot(
                    target_type="DEMO_ACTOR", target_id=_ACTOR_ID, authority_digest="5" * 64
                ),
                result_code=None,
                finalized_at=None,
            ),
            replayed=False,
        )


@dataclass
class _RouteCommands:
    unavailable: bool = False

    async def active_profiles(self, *, demo_actor_id: str) -> tuple[DemoActiveProfile, ...]:
        assert demo_actor_id == _ACTOR_ID
        if self.unavailable:
            raise DemoProfileCommandUnavailable("foreign actor")
        return ()

    async def create_style_feedback(
        self, command: CreateDemoStyleFeedback
    ) -> DemoStyleFeedbackResult:
        assert command.demo_actor_id == _ACTOR_ID
        return DemoStyleFeedbackResult("6" * 32, command.event_type, "7" * 64, False)

    async def create_constraints(self, command: CreateDemoConstraints) -> DemoConstraintsResult:
        assert command.demo_actor_id == _ACTOR_ID
        return DemoConstraintsResult("8" * 32, 1, command.scope, False)


def _route_actor() -> object:
    return type("RouteActor", (), {"id": _ACTOR_ID})()


def test_profile_routes_preserve_actor_ownership_and_reject_invalid_commands() -> None:
    app = create_app()
    coordinator = _RouteCoordinator()
    commands = _RouteCommands()
    app.dependency_overrides[get_demo_actor] = _route_actor
    app.dependency_overrides[get_demo_profile_coordinator] = lambda: cast(object, coordinator)
    app.dependency_overrides[get_demo_profile_commands] = lambda: cast(object, commands)
    with TestClient(app) as client:
        capabilities = client.get("/api/v1/demo/capabilities")
        assert capabilities.status_code == 200
        p5 = next(
            item for item in capabilities.json()["capabilities"] if item["code"] == "P5_COMPILER"
        )
        assert p5["status"] == "AVAILABLE"

        created = client.post(
            "/api/v1/demo/profiles/compile",
            headers={"Idempotency-Key": "profile-route-key"},
            json={"session_id": _SESSION_ID, "compiler_version": DEMO_PROFILE_COMPILER_VERSION},
        )
        assert created.status_code == 202
        assert created.json()["target"]["target_id"] == _ACTOR_ID
        assert coordinator.received is not None
        assert coordinator.received.demo_actor_id == _ACTOR_ID

        style = client.post(
            "/api/v1/demo/style-feedback",
            headers={"Idempotency-Key": "style-route-key"},
            json={
                "event_type": "EXPLICIT_STYLE_SELECTION",
                "session_id": _SESSION_ID,
                "style_key": "editorial",
            },
        )
        assert style.status_code == 201
        assert style.json()["event_type"] == "EXPLICIT_STYLE_SELECTION"

        constraints = client.post(
            "/api/v1/demo/constraints",
            headers={"Idempotency-Key": "constraint-route-key"},
            json={
                "scope": "PERSISTENT",
                "locks": [{"dimension_key": "eyes", "lock": "PRESERVE"}],
            },
        )
        assert constraints.status_code == 201
        assert constraints.json()["scope"] == "PERSISTENT"

        coordinator.payload_conflict = True
        conflict = client.post(
            "/api/v1/demo/profiles/compile",
            headers={"Idempotency-Key": "profile-conflict-key"},
            json={"session_id": _SESSION_ID, "compiler_version": DEMO_PROFILE_COMPILER_VERSION},
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

        invalid = client.post(
            "/api/v1/demo/constraints",
            headers={"Idempotency-Key": "bad-constraint"},
            json={"scope": "PERSISTENT", "session_id": _SESSION_ID, "locks": []},
        )
        assert invalid.status_code == 422

        commands.unavailable = True
        denied = client.get("/api/v1/demo/profiles/active")
        assert denied.status_code == 404
        assert denied.json()["code"] == "DEMO_PROFILE_AUTHORITY_UNAVAILABLE"
    app.dependency_overrides.clear()
