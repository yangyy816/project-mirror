from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from dataclasses import fields, replace
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import Session
from test_demo_d08_geometry_runtime_postgres import _context
from test_demo_schema_authority_invariants import (
    _insert_demo_row,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)
from test_demo_stepped_self_transfer_acceptance import (
    _append_persistent_constraints,
    _desired_dimension,
)

from mirror_api.demo_editing_commands import (
    CreateDemoEditPlan,
    CreateProfileGuidedGeometryPlan,
    DemoEditingCommandAuthorityCorruption,
    DemoEditingCommandInputError,
    DemoEditingCommandService,
    DemoEditingCommandUnavailable,
    DemoProfileGuidedGeometryPlanAccepted,
)
from mirror_api.demo_idempotency import DemoIdempotencyPayloadConflict
from mirror_api.demo_models import (
    DemoDesiredDeltaProfile,
    DemoEditOperation,
    DemoEditPlan,
    DemoJobBinding,
)
from mirror_api.demo_operation_graph import OperationType
from mirror_api.demo_profile_geometry_selector import (
    DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
    DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
    DemoProfileGeometryDimension,
    DemoProfileGeometryStepUnavailable,
    select_profile_guided_geometry_step,
)
from mirror_api.demo_self_transfer_service import (
    DemoSelfTransferService,
    DemoSelfTransferServiceError,
)
from mirror_api.models import Job

pytestmark = pytest.mark.integration


@pytest.fixture
def postgres_session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
        yield session
        session.rollback()
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
    engine.dispose()


def _command(graph: dict[str, Any], *, key: str) -> CreateProfileGuidedGeometryPlan:
    return CreateProfileGuidedGeometryPlan(
        demo_actor_id=graph["actor"].id,
        editing_session_id=graph["editing"].id,
        selection_policy_version=DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
        idempotency_key=key,
        request_id=f"{key}-request",
    )


def test_profile_guided_selector_missing_selected_case_fails_closed() -> None:
    with pytest.raises(DemoProfileGeometryStepUnavailable):
        select_profile_guided_geometry_step(
            dimensions=(
                DemoProfileGeometryDimension(
                    dimension_key="jaw_width",
                    desired_delta_ppm=30_000,
                    confidence_ppm=400_000,
                    restraint="NONE",
                    geometry_prohibited=False,
                    d02_selected_dimension=True,
                    persistent_preserve_lock=False,
                    current_session_allow_change=False,
                ),
            ),
            cases=(),
        )


async def _setup(
    postgres_session: Session,
    tmp_path: Any,
    *,
    desired_delta_ppm: int = 30_000,
    confidence_ppm: int = 400_000,
    restraint: str = "NONE",
) -> tuple[
    DemoEditingCommandService,
    async_sessionmaker[Any],
    AsyncEngine,
    dict[str, Any],
]:
    sessions, engine, graph = await _context(
        postgres_session,
        tmp_path,
        desired_dimensions={
            "jaw_width": _desired_dimension(
                desired_delta_ppm,
                confidence=confidence_ppm,
                restraint=restraint,
            )
        },
    )
    return DemoEditingCommandService(session_factory=sessions), sessions, engine, graph


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile_delta", "expected_step"),
    ((30_000, 30_000), (22_500, 15_000)),
)
async def test_profile_guided_plan_persists_exact_server_selection_and_safe_preview(
    postgres_session: Session,
    tmp_path: Any,
    profile_delta: int,
    expected_step: int,
) -> None:
    commands, sessions, engine, graph = await _setup(
        postgres_session, tmp_path, desired_delta_ppm=profile_delta
    )
    try:
        accepted = await commands.create_profile_guided_geometry_plan(
            _command(graph, key=f"profile-guided-{profile_delta}")
        )
        assert accepted.dimension_key == "jaw_width"
        assert accepted.direction == "INCREASE"
        assert accepted.execution_delta_ppm == expected_step
        assert accepted.policy_version == DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION
        assert accepted.replayed is False
        assert {item.name for item in fields(DemoProfileGuidedGeometryPlanAccepted)} == {
            "job_id",
            "target_id",
            "request_id",
            "dimension_key",
            "direction",
            "execution_delta_ppm",
            "policy_version",
            "replayed",
        }
        async with sessions() as session:
            plan = await session.get(DemoEditPlan, accepted.target_id)
            operations = tuple(
                await session.scalars(
                    select(DemoEditOperation).where(
                        DemoEditOperation.edit_plan_id == accepted.target_id
                    )
                )
            )
            binding = await session.scalar(
                select(DemoJobBinding).where(DemoJobBinding.job_id == accepted.job_id)
            )
            job = await session.get(Job, accepted.job_id)
        assert plan is not None and binding is not None and job is not None
        assert len(operations) == 1 and operations[0].operation_index == 0
        assert operations[0].parameters == {
            "dimension_key": "jaw_width",
            "delta_ppm": expected_step,
        }
        assert plan.operation_specs == [
            {
                "engine": "GEOMETRY",
                "operation_type": "GEOMETRY",
                "parameters": {"dimension_key": "jaw_width", "delta_ppm": expected_step},
                "preserve": ["IDENTITY_REFERENCE_FRAME", "NON_TARGET_GEOMETRY"],
                "expected_effect": {
                    "effect_type": "GEOMETRY",
                    "target_region": "FACE_REGION",
                    "dimension_key": "jaw_width",
                    "delta_ppm": expected_step,
                },
            }
        ]
        assert plan.instruction_digest == graph["editing"].instruction_digest
        assert binding.target_id == plan.id and binding.endpoint_operation == "edit_plan.create"
        assert job.status == "PENDING"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_profile_guided_plan_concurrent_replay_and_collision(
    postgres_session: Session, tmp_path: Any
) -> None:
    commands, sessions, engine, graph = await _setup(postgres_session, tmp_path)
    command = _command(graph, key="profile-guided-concurrent")
    try:
        first, second = await asyncio.gather(
            commands.create_profile_guided_geometry_plan(command),
            commands.create_profile_guided_geometry_plan(command),
        )
        assert first.job_id == second.job_id
        assert first.target_id == second.target_id
        assert sorted((first.replayed, second.replayed)) == [False, True]
        async with sessions() as session:
            bindings = await session.scalar(
                select(func.count())
                .select_from(DemoJobBinding)
                .where(
                    DemoJobBinding.demo_actor_id == graph["actor"].id,
                    DemoJobBinding.endpoint_operation == "edit_plan.create",
                )
            )
        assert bindings == 1
        with pytest.raises(DemoIdempotencyPayloadConflict):
            await commands.create_profile_guided_geometry_plan(
                replace(command, editing_session_id="f" * 32)
            )
        with pytest.raises(DemoEditingCommandInputError, match="policy"):
            await commands.create_profile_guided_geometry_plan(
                replace(command, selection_policy_version="unsupported-policy")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_profile_guided_plan_replay_rejects_current_constraint_drift(
    postgres_session: Session, tmp_path: Any
) -> None:
    commands, _, engine, graph = await _setup(postgres_session, tmp_path)
    command = _command(graph, key="profile-guided-drift")
    try:
        await commands.create_profile_guided_geometry_plan(command)
        _append_persistent_constraints(
            postgres_session,
            graph,
            locks={"jaw_width": {"mode": "PRESERVE"}},
            prohibited_operations=[],
        )
        with pytest.raises(DemoEditingCommandUnavailable, match="selection"):
            await commands.create_profile_guided_geometry_plan(command)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("confidence", "restraint"),
    ((0, "NONE"), (400_000, "INSUFFICIENT_CONFIDENCE")),
)
async def test_profile_guided_plan_rejects_ineligible_profile(
    postgres_session: Session,
    tmp_path: Any,
    confidence: int,
    restraint: str,
) -> None:
    commands, _, engine, graph = await _setup(
        postgres_session,
        tmp_path,
        confidence_ppm=confidence,
        restraint=restraint,
    )
    try:
        with pytest.raises(DemoEditingCommandUnavailable, match="selection"):
            await commands.create_profile_guided_geometry_plan(
                _command(graph, key=f"profile-guided-ineligible-{confidence}-{restraint}")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("locks", "prohibited"),
    (({"jaw_width": {"mode": "PRESERVE"}}, []), ({}, ["GEOMETRY"])),
)
async def test_profile_guided_plan_rejects_current_constraints(
    postgres_session: Session,
    tmp_path: Any,
    locks: dict[str, Any],
    prohibited: list[str],
) -> None:
    commands, _, engine, graph = await _setup(postgres_session, tmp_path)
    try:
        _append_persistent_constraints(
            postgres_session,
            graph,
            locks=locks,
            prohibited_operations=prohibited,
        )
        with pytest.raises(DemoEditingCommandUnavailable, match="selection"):
            await commands.create_profile_guided_geometry_plan(
                _command(graph, key=f"profile-guided-constraints-{len(locks)}-{len(prohibited)}")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_profile_guided_plan_replay_rejects_ambiguous_plan_operation(
    postgres_session: Session, tmp_path: Any
) -> None:
    commands, _, engine, graph = await _setup(postgres_session, tmp_path)
    command = _command(graph, key="profile-guided-extra-operation")
    try:
        accepted = await commands.create_profile_guided_geometry_plan(command)
        postgres_session.expire_all()
        original = postgres_session.scalar(
            select(DemoEditOperation).where(
                DemoEditOperation.edit_plan_id == accepted.target_id,
                DemoEditOperation.operation_index == 0,
            )
        )
        assert original is not None
        _insert_demo_row(
            postgres_session,
            DemoEditOperation,
            demo_actor_id=original.demo_actor_id,
            demo_session_id=original.demo_session_id,
            edit_plan_id=original.edit_plan_id,
            operation_index=1,
            engine=original.engine,
            operation_type=original.operation_type,
            parameters=dict(original.parameters),
            preserve=list(original.preserve),
            expected_effect=dict(original.expected_effect),
        )
        with pytest.raises(DemoEditingCommandAuthorityCorruption, match="preview"):
            await commands.create_profile_guided_geometry_plan(command)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_profile_guided_context_rejects_wrong_actor_session_profile_and_source(
    postgres_session: Session, tmp_path: Any
) -> None:
    commands, sessions, engine, graph = await _setup(postgres_session, tmp_path)
    del commands
    try:
        async with sessions() as session:
            profile = await session.scalar(
                select(DemoDesiredDeltaProfile).where(
                    DemoDesiredDeltaProfile.content_digest
                    == graph["editing"].desired_delta_profile_digest
                )
            )
            assert profile is not None
            service = DemoSelfTransferService(session_factory=sessions)
            base = {
                "demo_actor_id": graph["actor"].id,
                "demo_session_id": graph["session"].id,
                "source_asset_id": graph["source"].id,
                "desired_delta_profile_id": profile.id,
                "policy_version": DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
                "policy_digest": DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
            }
            for override in (
                {"demo_actor_id": "f" * 32},
                {"demo_session_id": "e" * 32},
                {"desired_delta_profile_id": "d" * 32},
                {"source_asset_id": "c" * 32},
            ):
                with pytest.raises(DemoSelfTransferServiceError):
                    await service.select_profile_geometry_step_in_session(
                        session, **(base | override)
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ordinary_geometry_plan_regression(postgres_session: Session, tmp_path: Any) -> None:
    commands, _, engine, graph = await _setup(postgres_session, tmp_path, desired_delta_ppm=15_000)
    try:
        accepted = await commands.create_edit_plan(
            CreateDemoEditPlan(
                graph["actor"].id,
                graph["editing"].id,
                OperationType.GEOMETRY,
                15_000,
                "ordinary-geometry-regression",
                "ordinary-geometry-regression-request",
            )
        )
        assert accepted.replayed is False
    finally:
        await engine.dispose()
