from __future__ import annotations

import os
from asyncio import gather
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import (
    AuditLog,
    GenerationBatch,
    GenerationItem,
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    new_id,
)
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.generation_types import (
    GenerationBatchCreate,
    GenerationOperationRejected,
)
from mirror_api.synthetic_dataset.operations import (
    DatasetOperationCommand,
    DatasetOperationKind,
    DatasetOperationOutcome,
)
from mirror_api.synthetic_dataset.operations_integration import GenerationBatchOperationBackend

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    truncate = (
        "TRUNCATE TABLE audit_logs, provider_cost_events, synthetic_generation_evidence, "
        "synthetic_source_objects, generation_items, generation_batches, job_attempts, jobs, "
        "synthetic_generation_policies, synthetic_prompt_templates CASCADE"
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text(truncate))
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(truncate))
        await engine.dispose()


async def _batch(sessions: async_sessionmaker[AsyncSession]) -> tuple[GenerationBatchService, str]:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="p2-m7-t05-v1",
        content={"subject": "synthetic"},
        content_digest="a" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="p2-m7-t05-v1",
        content={"template": "synthetic fixture"},
        content_digest="b" * 64,
    )
    async with sessions() as session:
        session.add_all((policy, prompt))
        await session.commit()
        await session.execute(
            update(SyntheticGenerationPolicy)
            .where(SyntheticGenerationPolicy.id == policy.id)
            .values(approval_status="APPROVED", approved_at=NOW)
        )
        await session.execute(
            update(SyntheticPromptTemplate)
            .where(SyntheticPromptTemplate.id == prompt.id)
            .values(approval_status="APPROVED", approved_at=NOW)
        )
        await session.commit()
    service = GenerationBatchService(session_factory=sessions, now=lambda: NOW)
    created = await service.create_batch(
        GenerationBatchCreate(
            idempotency_key_hash="c" * 64,
            request_id="p2-m7-t05-fixture",
            generation_policy_id=policy.id,
            prompt_template_id=prompt.id,
            provider_reference="deterministic-mock",
            model_reference="fixture-model",
            model_version_reference="fixture-v1",
            pricing_snapshot_reference="pricing-fixture-v1",
            output_media_type="image/png",
            output_width=1,
            output_height=1,
            output_max_bytes=1024,
            item_count=1,
            requested_seeds=(1,),
            currency="CNY",
            hard_budget_micros=100,
            per_item_ceiling_micros=100,
            retry_ceiling=0,
            concurrency_ceiling=1,
        )
    )
    await service.queue_batch(created.batch.batch_id)
    return service, created.batch.batch_id


def _command(
    kind: DatasetOperationKind, batch_id: str, request: str, expected: str = "QUEUED"
) -> DatasetOperationCommand:
    return DatasetOperationCommand(
        operation=kind,
        environment="ci",
        target_id=batch_id,
        expected_target_state=expected,
        actor_reference="system.operator",
        reason_code="operator_cancel",
        request_id=request * 32,
    )


@pytest.mark.asyncio
async def test_postgresql_concurrent_duplicate_cancel_has_one_audited_authoritative_effect() -> (
    None
):
    async with _database() as sessions:
        service, batch_id = await _batch(sessions)
        backend = GenerationBatchOperationBackend(generation_batches=service)
        left, right = await gather(
            backend.execute(_command(DatasetOperationKind.BATCH_CANCEL, batch_id, "a")),
            backend.execute(_command(DatasetOperationKind.BATCH_CANCEL, batch_id, "b")),
        )

        assert {left.outcome, right.outcome} == {
            DatasetOperationOutcome.SUCCEEDED,
            DatasetOperationOutcome.REJECTED,
        }
        assert {left.code, right.code} == {"operation_completed", "operation_stale_expectation"}
        async with sessions() as session:
            batch = await session.get(GenerationBatch, batch_id)
            assert batch is not None and batch.status == "CANCELLED"
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(GenerationItem)
                    .where(GenerationItem.status == "CANCELLED")
                )
                == 1
            )


@pytest.mark.asyncio
async def test_postgresql_status_and_stale_cancel_are_read_only_fail_closed() -> None:
    async with _database() as sessions:
        service, batch_id = await _batch(sessions)
        backend = GenerationBatchOperationBackend(generation_batches=service)
        stale_status = await backend.execute(
            _command(DatasetOperationKind.BATCH_STATUS, batch_id, "c", "DRAFT")
        )
        stale_cancel = await backend.execute(
            _command(DatasetOperationKind.BATCH_CANCEL, batch_id, "d", "DRAFT")
        )

        assert stale_status.code == stale_cancel.code == "operation_stale_expectation"
        async with sessions() as session:
            batch = await session.get(GenerationBatch, batch_id)
            assert batch is not None and batch.status == "QUEUED"
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.asyncio
async def test_postgresql_cancelled_lease_cannot_resume_after_worker_crash_recovery() -> None:
    async with _database() as sessions:
        service, batch_id = await _batch(sessions)
        reservation = await service.reserve_next_item(batch_id)
        assert reservation is not None
        backend = GenerationBatchOperationBackend(generation_batches=service)

        cancelled = await backend.execute(
            _command(DatasetOperationKind.BATCH_CANCEL, batch_id, "e", "RUNNING")
        )
        assert cancelled.outcome is DatasetOperationOutcome.SUCCEEDED
        assert cancelled.projection is not None and cancelled.projection.target_status == "RUNNING"
        with pytest.raises(GenerationOperationRejected) as unavailable:
            await service.execution_context(reservation)
        assert unavailable.value.code == "generation_context_unavailable"

        assert await service.record_attempt_failure(
            item_id=reservation.item_id,
            attempt_id=reservation.attempt_id,
            result_code="worker_crash_recovered",
            retryable=True,
        )
        observed = await service.get_batch(batch_id)
        assert observed.batch.status == "CANCELLED"
        assert observed.items[0].status == "GENERATION_FAILED"
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1
