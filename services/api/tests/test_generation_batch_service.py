from __future__ import annotations

import os
import pickle
from asyncio import gather
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import (
    GenerationBatch,
    GenerationItem,
    Job,
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    new_id,
)
from mirror_api.providers.base import (
    GenerationBudgetContext,
    SyntheticGenerationRequest,
    SyntheticOutputSpecification,
    SyntheticStorageWriteRequest,
)
from mirror_api.providers.mock import (
    MockImageGenerationProvider,
    MockSyntheticObjectStorageProvider,
)
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.generation_types import (
    GenerationBatchCreate,
    GenerationOperationRejected,
    ProviderCostInput,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 16, 10, tzinfo=UTC)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE synthetic_source_object_deletion_evidence, "
                    "provider_cost_events, synthetic_generation_evidence, "
                    "synthetic_source_objects, generation_items, generation_batches, "
                    "job_attempts, jobs, synthetic_generation_policies, "
                    "synthetic_prompt_templates CASCADE"
                )
            )
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE synthetic_source_object_deletion_evidence, "
                    "provider_cost_events, synthetic_generation_evidence, "
                    "synthetic_source_objects, generation_items, generation_batches, "
                    "job_attempts, jobs, synthetic_generation_policies, "
                    "synthetic_prompt_templates CASCADE"
                )
            )
        await engine.dispose()


async def _authorities(sessions: async_sessionmaker[AsyncSession]) -> tuple[str, str]:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="generation-service-v1",
        content={"subject": "synthetic"},
        content_digest="a" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="prompt-service-v1",
        content={"template": "clearly adult synthetic non-human fixture"},
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
    return policy.id, prompt.id


def _command(
    policy_id: str,
    prompt_id: str,
    *,
    key: str = "c",
    item_count: int = 2,
    concurrency_ceiling: int = 2,
    model_version: str = "fixture-v1",
    requested_seeds: tuple[int | None, ...] | None = None,
) -> GenerationBatchCreate:
    return GenerationBatchCreate(
        idempotency_key_hash=key * 64,
        request_id=f"generation-service-{key * 8}",
        generation_policy_id=policy_id,
        prompt_template_id=prompt_id,
        provider_reference="mock-provider-v1",
        model_reference="mock-model-v1",
        model_version_reference=(
            "mock-model-version-v1" if model_version == "fixture-v1" else model_version
        ),
        pricing_snapshot_reference="pricing-fixture-v1",
        output_media_type="image/png",
        output_width=1,
        output_height=1,
        output_max_bytes=1024,
        item_count=item_count,
        requested_seeds=(tuple(range(item_count)) if requested_seeds is None else requested_seeds),
        currency="CNY",
        hard_budget_micros=100 * item_count,
        per_item_ceiling_micros=100,
        retry_ceiling=1,
        concurrency_ceiling=concurrency_ceiling,
    )


def _service(
    sessions: async_sessionmaker[AsyncSession], *, now: datetime = NOW
) -> GenerationBatchService:
    return GenerationBatchService(session_factory=sessions, now=lambda: now)


@pytest.mark.asyncio
async def test_concurrent_create_is_idempotent_and_conflicting_reuse_fails_closed() -> None:
    async with _database() as sessions:
        policy_id, prompt_id = await _authorities(sessions)
        service = _service(sessions)
        command = _command(policy_id, prompt_id)
        first, second = await gather(service.create_batch(command), service.create_batch(command))

        assert {first.created, second.created} == {True, False}
        assert first.batch.batch_id == second.batch.batch_id
        assert len(first.items) == len(second.items) == 2
        with pytest.raises(GenerationOperationRejected) as conflict:
            await service.create_batch(
                _command(
                    policy_id,
                    prompt_id,
                    model_version="fixture-v2",
                )
            )
        assert conflict.value.code == "idempotency_conflict"

        async with sessions() as session:
            assert (
                await session.scalar(select(text("count(*)")).select_from(GenerationBatch))
            ) == 1


@pytest.mark.asyncio
async def test_reservation_concurrency_retry_cost_and_ephemeral_prompt() -> None:
    async with _database() as sessions:
        policy_id, prompt_id = await _authorities(sessions)
        service = _service(sessions)
        created = await service.create_batch(
            _command(policy_id, prompt_id, item_count=3, concurrency_ceiling=2)
        )
        await service.queue_batch(created.batch.batch_id)

        reservations = await gather(
            service.reserve_next_item(created.batch.batch_id),
            service.reserve_next_item(created.batch.batch_id),
            service.reserve_next_item(created.batch.batch_id),
        )
        active = [reservation for reservation in reservations if reservation is not None]
        assert len(active) == 2
        assert len({reservation.item_id for reservation in active}) == 2

        prompt = await service.materialize_prompt(
            item_id=active[0].item_id,
            attempt_id=active[0].attempt_id,
            lease_token=active[0].lease_token,
        )
        assert repr(prompt) == "EphemeralPrompt(<redacted>)"
        assert str(prompt) == "<redacted>"
        assert prompt.reveal_for_provider_adapter() == ("clearly adult synthetic non-human fixture")
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(prompt)
        with pytest.raises(GenerationOperationRejected) as wrong_lease:
            await service.materialize_prompt(
                item_id=active[0].item_id,
                attempt_id=active[0].attempt_id,
                lease_token="0" * 64,
            )
        assert wrong_lease.value.code == "prompt_material_unavailable"
        with pytest.raises(GenerationOperationRejected) as expired_lease:
            await _service(sessions, now=NOW + timedelta(seconds=301)).materialize_prompt(
                item_id=active[0].item_id,
                attempt_id=active[0].attempt_id,
                lease_token=active[0].lease_token,
            )
        assert expired_lease.value.code == "prompt_material_unavailable"

        first = active[0]
        assert await service.record_attempt_failure(
            item_id=first.item_id,
            attempt_id=first.attempt_id,
            result_code="provider_unavailable",
            retryable=True,
        )
        retry = await service.reserve_next_item(created.batch.batch_id)
        assert retry is not None
        assert retry.item_id == first.item_id
        assert retry.attempt_number == 2
        assert retry.remaining_budget_micros == 100

        occurred_at = NOW + timedelta(seconds=1)
        outcomes = await gather(
            service.post_cost(
                ProviderCostInput(
                    item_id=first.item_id,
                    job_attempt_id=first.attempt_id,
                    event_kind="final",
                    currency="CNY",
                    amount_micros=60,
                    pricing_snapshot_reference="pricing-fixture-v1",
                    occurred_at=occurred_at,
                )
            ),
            service.post_cost(
                ProviderCostInput(
                    item_id=first.item_id,
                    job_attempt_id=retry.attempt_id,
                    event_kind="final",
                    currency="CNY",
                    amount_micros=60,
                    pricing_snapshot_reference="pricing-fixture-v1",
                    occurred_at=occurred_at,
                )
            ),
            return_exceptions=True,
        )
        assert sum(outcome is True for outcome in outcomes) == 1
        rejected = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
        assert len(rejected) == 1
        assert isinstance(rejected[0], GenerationOperationRejected)
        assert rejected[0].code == "provider_cost_rejected"


@pytest.mark.asyncio
async def test_cancel_stops_new_work_and_finalizes_after_leased_attempt_quiesces() -> None:
    async with _database() as sessions:
        policy_id, prompt_id = await _authorities(sessions)
        service = _service(sessions)
        created = await service.create_batch(
            _command(policy_id, prompt_id, key="d", concurrency_ceiling=1)
        )
        await service.queue_batch(created.batch.batch_id)
        reservation = await service.reserve_next_item(created.batch.batch_id)
        assert reservation is not None

        cancelling = await service.request_cancel(created.batch.batch_id)
        assert cancelling.batch.status == "RUNNING"
        assert cancelling.batch.cancel_requested_at == NOW
        assert sorted(item.status for item in cancelling.items) == ["CANCELLED", "GENERATING"]
        assert await service.reserve_next_item(created.batch.batch_id) is None

        assert await service.record_attempt_failure(
            item_id=reservation.item_id,
            attempt_id=reservation.attempt_id,
            result_code="cancelled_at_safe_point",
            retryable=True,
        )
        assert not await service.record_attempt_failure(
            item_id=reservation.item_id,
            attempt_id=reservation.attempt_id,
            result_code="cancelled_at_safe_point",
            retryable=True,
        )
        async with sessions() as session:
            batch = await session.get(GenerationBatch, created.batch.batch_id)
            assert batch is not None
            assert batch.status == "CANCELLED"
            items = tuple(
                (
                    await session.scalars(
                        select(GenerationItem)
                        .where(GenerationItem.batch_id == batch.id)
                        .order_by(GenerationItem.ordinal)
                    )
                ).all()
            )
            assert all(item.status in {"GENERATION_FAILED", "CANCELLED"} for item in items)
            jobs = tuple(
                (
                    await session.scalars(
                        select(Job).where(Job.id.in_([item.job_id for item in items]))
                    )
                ).all()
            )
            assert all(job.lease_token is None for job in jobs)


@pytest.mark.asyncio
async def test_raw_stored_completion_is_atomic_idempotent_and_finalizes_batch() -> None:
    async with _database() as sessions:
        policy_id, prompt_id = await _authorities(sessions)
        service = _service(sessions)
        created = await service.create_batch(
            _command(
                policy_id,
                prompt_id,
                key="e",
                item_count=1,
                concurrency_ceiling=1,
                requested_seeds=(None,),
            )
        )
        await service.queue_batch(created.batch.batch_id)
        reservation = await service.reserve_next_item(created.batch.batch_id)
        assert reservation is not None

        generation_request = SyntheticGenerationRequest(
            request_reference=reservation.request_reference,
            generation_policy_reference="generation-policy-v1",
            prompt_template_reference="prompt-template-v1",
            output_specification=SyntheticOutputSpecification(
                media_type="image/png",
                width=1,
                height=1,
                max_byte_size=1024,
            ),
            generation_parameters=(),
            seed=None,
            budget=GenerationBudgetContext(
                currency="CNY",
                max_amount_micros=reservation.remaining_budget_micros,
                pricing_snapshot_reference="pricing-fixture-v1",
            ),
        )
        result = await MockImageGenerationProvider().generate_synthetic(request=generation_request)
        storage = MockSyntheticObjectStorageProvider()
        stored = await storage.store_generated_image_if_absent(
            request=SyntheticStorageWriteRequest(
                storage_reference=f"raw-{reservation.item_id}",
                payload=result.payload,
                provenance=result.provenance,
            )
        )
        assert await service.record_raw_stored(
            item_id=reservation.item_id,
            attempt_id=reservation.attempt_id,
            result=result,
            stored=stored,
            retention_expires_at=NOW + timedelta(days=1),
        )
        assert not await service.record_raw_stored(
            item_id=reservation.item_id,
            attempt_id=reservation.attempt_id,
            result=result,
            stored=stored,
            retention_expires_at=NOW + timedelta(days=1),
        )

        async with sessions() as session:
            batch = await session.get(GenerationBatch, created.batch.batch_id)
            item = await session.get(GenerationItem, reservation.item_id)
            assert batch is not None and batch.status == "COMPLETED"
            assert item is not None and item.status == "RAW_STORED"
