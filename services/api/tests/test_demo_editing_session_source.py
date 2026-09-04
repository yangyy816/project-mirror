from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_analysis_service import _runtime_evidence
from test_demo_d02_generic_admission import _generic_admission_bundle
from test_demo_profile_service import _profile_job
from test_demo_session_service import _create_actor, _truncate

from mirror_api.demo_analysis_dependencies import accepted_demo_analysis_configuration
from mirror_api.demo_analysis_service import CreateDemoAnalysis, DemoAnalysisService
from mirror_api.demo_d02_generic_admission_coordinator import D02GenericAdmissionCoordinator
from mirror_api.demo_editing_commands import (
    CreateDemoEditingSession,
    DemoEditingCommandService,
)
from mirror_api.demo_idempotency import DemoIdempotencyPayloadConflict
from mirror_api.demo_models import DemoEditingSession, DemoSession, DemoSyntheticIdentity
from mirror_api.demo_profile_service import DemoProfileCompilationService
from mirror_api.demo_session_service import CreateDemoSession, DemoSessionService

TEST_NOW = datetime(2099, 1, 1, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@asynccontextmanager
async def _generic_database(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for the D11 editing source gate")
    sync_engine = create_engine(database_url.replace("+asyncpg", "+psycopg"))
    with Session(sync_engine) as session:
        _truncate(session)
        bundle = _generic_admission_bundle(session, tmp_path)
        session.commit()
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await D02GenericAdmissionCoordinator(session_factory=sessions).admit(
            idempotency_key="session-canonical-source-admission",
            bundle=bundle,
        )
        yield sessions
    finally:
        await engine.dispose()
        with Session(sync_engine) as session:
            _truncate(session)
        sync_engine.dispose()


async def _bound_source(
    sessions: async_sessionmaker[AsyncSession], session_id: str
) -> tuple[str, str]:
    async with sessions() as session:
        demo_session = await session.get(DemoSession, session_id)
        assert demo_session is not None
        identity_id = cast(str, demo_session.config["synthetic_identity_id"])
        identity = await session.get(DemoSyntheticIdentity, identity_id)
        assert identity is not None
        return identity.formal_canonical_asset_id, identity.formal_canonical_asset_sha256


@pytest.mark.asyncio
async def test_session_canonical_source_is_owner_bound_idempotent_and_explicit(
    tmp_path: Path,
) -> None:
    async with _generic_database(tmp_path) as sessions:
        actor = await _create_actor(sessions)
        session_service = DemoSessionService(session_factory=sessions, now=lambda: TEST_NOW)
        identities = await session_service.list_identities(demo_actor_id=actor.id)
        assert identities
        demo_session = await session_service.create(
            CreateDemoSession(
                demo_actor_id=actor.id,
                synthetic_identity_id=identities[0].identity_id,
                context_seed="a" * 64,
                idempotency_key="session-canonical-source-session",
            )
        )
        session_id = demo_session.session_id
        async with sessions() as session:
            identity = await session.get(DemoSyntheticIdentity, identities[0].identity_id)
        assert identity is not None
        analyses = DemoAnalysisService(
            session_factory=sessions,
            configuration=accepted_demo_analysis_configuration(),
            now=lambda: TEST_NOW,
        )
        analysis_command = CreateDemoAnalysis(
            demo_actor_id=actor.id,
            demo_session_id=session_id,
            source_asset_id=identity.formal_canonical_asset_id,
            idempotency_key="session-canonical-source-analysis",
            request_id="session-canonical-source-analysis-request",
        )
        accepted_analysis = await analyses.create(analysis_command)
        reservation = await analyses.claim(
            analysis_run_id=accepted_analysis.analysis_run_id,
            job_id=accepted_analysis.job_id,
            request_id=analysis_command.request_id,
        )
        assert reservation is not None
        assert await analyses.complete(reservation, _runtime_evidence()) is not None

        profile_job_id = await _profile_job(sessions, actor.id, session_id)
        await DemoProfileCompilationService(session_factory=sessions).compile(
            demo_actor_id=actor.id,
            job_id=profile_job_id,
        )
        source_id, source_sha256 = await _bound_source(sessions, session_id)
        commands = DemoEditingCommandService(session_factory=sessions)
        command = CreateDemoEditingSession(
            demo_actor_id=actor.id,
            demo_session_id=session_id,
            source_selector="SESSION_CANONICAL_ASSET",
            idempotency_key="session-canonical-edit-source",
            request_id="session-canonical-edit-source-request",
        )

        first = await commands.create_editing_session(command)
        replay = await commands.create_editing_session(command)
        assert replay.replayed is True
        assert (replay.job_id, replay.target_id) == (first.job_id, first.target_id)
        async with sessions() as session:
            editing = await session.get(DemoEditingSession, first.target_id)
        assert editing is not None
        assert editing.demo_actor_id == actor.id
        assert editing.demo_session_id == session_id
        assert (editing.source_asset_id, editing.source_asset_sha256) == (
            source_id,
            source_sha256,
        )

        with pytest.raises(DemoIdempotencyPayloadConflict):
            await commands.create_editing_session(
                CreateDemoEditingSession(
                    demo_actor_id=actor.id,
                    demo_session_id=session_id,
                    source_asset_id=source_id,
                    idempotency_key=command.idempotency_key,
                    request_id="explicit-source-collision-request",
                )
            )
