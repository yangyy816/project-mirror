from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_d02_generic_admission import _generic_admission_bundle

from mirror_api.demo_analysis_dependencies import accepted_demo_analysis_configuration
from mirror_api.demo_analysis_service import CreateDemoAnalysis, DemoAnalysisService
from mirror_api.demo_d02_generic_admission_coordinator import (
    D02GenericAdmissionCoordinator,
)
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import (
    DemoActor,
    DemoCommandBinding,
    DemoSession,
    DemoSyntheticIdentity,
)
from mirror_api.demo_session_service import (
    CreateDemoSession,
    DemoSessionActorUnavailable,
    DemoSessionPayloadConflict,
    DemoSessionService,
    DemoSyntheticIdentityUnavailable,
)
from mirror_api.models import new_id

NOW = datetime(2026, 9, 3, 12, tzinfo=UTC)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def database_session() -> Iterator[Session]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for the D11 Session gate")
    engine = create_engine(database_url)
    session = Session(engine, expire_on_commit=False)
    _truncate(session)
    try:
        yield session
    finally:
        session.rollback()
        _truncate(session)
        session.close()
        engine.dispose()


def _truncate(session: Session) -> None:
    session.execute(
        text(
            "TRUNCATE TABLE job_attempts, jobs, demo_command_bindings, "
            "demo_sessions, demo_actors, "
            "demo_d02_r2_epoch2_admissions, demo_question_pairs, demo_question_banks, "
            "demo_pair_screening_reports, asset_variants, demo_synthetic_identities, "
            "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
            "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
            "demo_d02_source_acquisition_runs, demo_d02_cohort_specs, assets CASCADE"
        )
    )
    session.commit()


@asynccontextmanager
async def _async_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for the D11 Session gate")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        await engine.dispose()


def _digest(schema: str, payload: dict[str, object]) -> str:
    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _create_actor(sessions: async_sessionmaker[AsyncSession]) -> DemoActor:
    payload: dict[str, object] = {
        "actor_kind": "AUTOMATED_TEST",
        "authority_at": _time(NOW),
        "credential_key_id": new_id() + new_id(),
    }
    actor = DemoActor(
        id=new_id(),
        schema_version="mirror.demo/DemoActor/v1",
        canonical_payload=payload,
        content_digest=_digest("mirror.demo/DemoActor/v1", payload),
        created_at=NOW,
        actor_kind="AUTOMATED_TEST",
        credential_key_id=payload["credential_key_id"],
        authority_at=NOW,
    )
    async with sessions() as session:
        session.add(actor)
        await session.commit()
    return actor


@pytest.mark.asyncio
async def test_current_d02_identities_create_idempotent_owner_bound_session(
    database_session: Session, tmp_path: Path
) -> None:
    bundle = _generic_admission_bundle(database_session, tmp_path)
    database_session.commit()

    async with _async_sessions() as sessions:
        await D02GenericAdmissionCoordinator(session_factory=sessions).admit(
            idempotency_key="d11-session-source-admission", bundle=bundle
        )
        actor = await _create_actor(sessions)
        service = DemoSessionService(session_factory=sessions, now=lambda: NOW)

        identities = await service.list_identities(demo_actor_id=actor.id)
        assert len(identities) == 4
        assert [item.identity_id for item in identities] == sorted(
            item.identity_id for item in identities
        )
        assert {item.admission_status for item in identities} == {"ADMITTED"}
        assert all(len(item.canonical_asset_digest) == 64 for item in identities)

        command = CreateDemoSession(
            demo_actor_id=actor.id,
            synthetic_identity_id=identities[0].identity_id,
            context_seed="a" * 64,
            idempotency_key="d11-session-idempotency",
        )
        first = await service.create(command)
        replay = await service.create(command)
        assert replay == first
        assert first.status == "ACTIVE"
        assert first.synthetic_identity_id == identities[0].identity_id
        assert int((first.expires_at - NOW).total_seconds()) == 900

        async with sessions() as session:
            identity = await session.get(DemoSyntheticIdentity, identities[0].identity_id)
        assert identity is not None
        analysis = await DemoAnalysisService(
            session_factory=sessions,
            configuration=accepted_demo_analysis_configuration(),
            now=lambda: NOW,
        ).create(
            CreateDemoAnalysis(
                demo_actor_id=actor.id,
                demo_session_id=first.session_id,
                source_asset_id=identity.formal_canonical_asset_id,
                idempotency_key="d11-session-d03-start",
                request_id="d11-session-d03-request",
            )
        )
        assert analysis.demo_session_id == first.session_id

        async with sessions() as session:
            persisted = await session.get(DemoSession, first.session_id)
            assert persisted is not None
            assert persisted.demo_actor_id == actor.id
            assert persisted.config == {
                "schema_version": "mirror.demo/DemoSessionConfig/v1",
                "synthetic_identity_id": identities[0].identity_id,
            }
            assert await session.scalar(select(func.count()).select_from(DemoSession)) == 1
            assert await session.scalar(select(func.count()).select_from(DemoCommandBinding)) == 1

        with pytest.raises(DemoSessionPayloadConflict):
            await service.create(
                CreateDemoSession(
                    demo_actor_id=actor.id,
                    synthetic_identity_id=identities[0].identity_id,
                    context_seed="b" * 64,
                    idempotency_key=command.idempotency_key,
                )
            )

        concurrent = CreateDemoSession(
            demo_actor_id=actor.id,
            synthetic_identity_id=identities[1].identity_id,
            context_seed="c" * 64,
            idempotency_key="d11-session-concurrent",
        )
        left, right = await asyncio.gather(service.create(concurrent), service.create(concurrent))
        assert left == right
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(DemoSession)) == 2
            assert await session.scalar(select(func.count()).select_from(DemoCommandBinding)) == 2


@pytest.mark.asyncio
async def test_unknown_identity_and_missing_actor_fail_without_partial_session(
    database_session: Session, tmp_path: Path
) -> None:
    bundle = _generic_admission_bundle(database_session, tmp_path)
    database_session.commit()

    async with _async_sessions() as sessions:
        actor = await _create_actor(sessions)
        service = DemoSessionService(session_factory=sessions, now=lambda: NOW)
        assert await service.list_identities(demo_actor_id=actor.id) == ()
        await D02GenericAdmissionCoordinator(session_factory=sessions).admit(
            idempotency_key="d11-session-negative-admission", bundle=bundle
        )

        with pytest.raises(DemoSyntheticIdentityUnavailable):
            await service.create(
                CreateDemoSession(
                    demo_actor_id=actor.id,
                    synthetic_identity_id="0" * 32,
                    context_seed="d" * 64,
                    idempotency_key="d11-session-missing",
                )
            )
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(DemoSession)) == 0
            assert await session.scalar(select(func.count()).select_from(DemoCommandBinding)) == 0

        with pytest.raises(DemoSessionActorUnavailable):
            await service.list_identities(demo_actor_id="0" * 32)
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(DemoSession)) == 0
            assert await session.scalar(select(func.count()).select_from(DemoCommandBinding)) == 0
