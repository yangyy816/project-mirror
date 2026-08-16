from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from test_synthetic_asset_qa_invariants import _normalized_record

from mirror_api.models import SyntheticQAPolicy, SyntheticQARun, new_id, utcnow
from mirror_api.synthetic_dataset.domain import CanonicalPolicy, PolicyKind
from mirror_api.synthetic_dataset.qa_repository import SyntheticQARepository
from mirror_api.synthetic_dataset.qa_service import SyntheticQAService

pytestmark = pytest.mark.integration


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        await engine.dispose()


def _policy_content() -> dict[str, object]:
    return {
        "schema_version": "mirror.synthetic-dataset/QAPolicyDefinition/v1",
        "requirements": [
            {
                "code": "exactly_one_face",
                "evidence_type": "measurement",
                "hard_gate": True,
                "algorithm_reference": "mirror.fixture/face-count",
                "algorithm_version": "v1",
                "threshold_rule_reference": "face-count-rule-v1",
            },
            {
                "code": "adult_presentation",
                "evidence_type": "review",
                "hard_gate": True,
                "review_rule_reference": "adult-review-v1",
            },
        ],
    }


@pytest.mark.asyncio
async def test_real_postgresql_service_finalization_uses_bound_policy_only() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")

    # This creates a real M3 raw->normalized lineage through existing PostgreSQL guards.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sync_engine = create_engine(database_url)
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE synthetic_identities, synthetic_qa_review_decisions, "
                "synthetic_qa_measurements, synthetic_qa_runs, synthetic_asset_records, "
                "synthetic_source_object_deletion_evidence, provider_cost_events, "
                "synthetic_generation_evidence, synthetic_source_objects, generation_items, "
                "generation_batches, job_attempts, jobs, synthetic_qa_policies, "
                "synthetic_generation_policies, synthetic_prompt_templates, assets CASCADE"
            )
        )
    with Session(sync_engine) as session:
        record, asset = _normalized_record(session)
        content = _policy_content()
        canonical = CanonicalPolicy.create(
            kind=PolicyKind.SYNTHETIC_QA_POLICY, version="m3-service-fixture-v1", content=content
        )
        policy = SyntheticQAPolicy(
            id=new_id(),
            version=canonical.version,
            content=content,
            content_digest=canonical.content_digest,
        )
        session.add(policy)
        session.commit()
        session.execute(
            update(SyntheticQAPolicy)
            .where(SyntheticQAPolicy.id == policy.id)
            .values(approval_status="APPROVED", approved_at=utcnow())
        )
        session.commit()
        run = SyntheticQARun(
            id=new_id(),
            synthetic_asset_record_id=record.id,
            normalized_asset_id=asset.id,
            qa_policy_id=policy.id,
        )
        session.add(run)
        session.commit()
        run_id = run.id
    sync_engine.dispose()

    async with _database() as sessions:
        async with sessions.begin() as session:
            service = SyntheticQAService(SyntheticQARepository(session))
            assert await service.start(run_id=run_id)
            result = await service.finalize(run_id=run_id)
            assert result.outcome.value == "REJECTED"
            assert result.reason_code == "required_evidence_unresolved"
        async with sessions() as session:
            run = await session.get(SyntheticQARun, run_id)
            assert run is not None
            assert run.status == "REJECTED"
            assert run.result_code == "required_evidence_unresolved"
