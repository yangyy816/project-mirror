from __future__ import annotations

import io
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import (
    GenerationItem,
    ProviderCostEvent,
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    new_id,
)
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.generation_types import (
    GenerationBatchCreate,
    GenerationItemReservation,
    ProviderCostInput,
)
from mirror_api.synthetic_dataset.operations_projection import (
    CostAvailability,
    CostClassification,
    CostProjectionCode,
    CostProjectionRejected,
    CostSummary,
    DatasetOperationalEvent,
    MonetaryCostAggregate,
    PostgresCostSummaryReadModel,
    emit_dataset_operational_event,
)

NOW = datetime(2026, 8, 23, 10, tzinfo=UTC)


def test_cost_summary_keeps_actual_estimated_and_unavailable_distinct() -> None:
    summary = CostSummary(
        batch_id="a" * 32,
        generation_policy_id="b" * 32,
        actual=(
            MonetaryCostAggregate(
                classification=CostClassification.ACTUAL,
                currency="CNY",
                amount_micros=12,
                event_count=1,
            ),
        ),
        estimated=(
            MonetaryCostAggregate(
                classification=CostClassification.ESTIMATED,
                currency="USD",
                amount_micros=7,
                event_count=1,
            ),
        ),
        unavailable_item_count=1,
        pending_item_count=0,
        total_item_count=3,
    )

    assert summary.availability is CostAvailability.MIXED
    assert summary.actual[0].amount_micros == 12
    assert summary.estimated[0].amount_micros == 7
    assert summary.unavailable_item_count == 1


@pytest.mark.parametrize(
    ("factory", "code"),
    [
        (
            lambda: MonetaryCostAggregate(
                classification=CostClassification.ACTUAL,
                currency="SECRET_CURRENCY",  # type: ignore[arg-type]
                amount_micros=1,
                event_count=1,
            ),
            CostProjectionCode.INVALID_CURRENCY,
        ),
        (
            lambda: DatasetOperationalEvent(
                request_id="c" * 32,
                batch_id="a" * 32,
                generation_policy_id="b" * 32,
                actor_reference="SECRET_OPERATOR",
                reason_code="operator_inspection",
                availability=CostAvailability.UNAVAILABLE,
                actual_event_count=0,
                estimated_event_count=0,
                unavailable_item_count=1,
                pending_item_count=0,
            ),
            CostProjectionCode.INVALID_ACTOR,
        ),
    ],
)
def test_cost_projection_rejects_unsafe_values_without_echoing(
    factory: object, code: CostProjectionCode
) -> None:
    with pytest.raises(CostProjectionRejected) as raised:
        factory()  # type: ignore[operator]
    assert raised.value.code is code
    assert "SECRET" not in str(raised.value)


def test_dataset_operational_event_has_fixed_payload_allowlist() -> None:
    summary = CostSummary(
        batch_id="a" * 32,
        generation_policy_id="b" * 32,
        actual=(),
        estimated=(),
        unavailable_item_count=1,
        pending_item_count=0,
        total_item_count=1,
    )
    event = DatasetOperationalEvent.from_summary(
        summary,
        request_id="c" * 32,
        actor_reference="system.operator",
        reason_code="operator_inspection",
    )
    stream = io.StringIO()
    logger = logging.getLogger("p2-m7-event-test")
    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    emit_dataset_operational_event(logger, event)
    payload = json.loads(stream.getvalue())

    assert set(payload) == {
        "actual_event_count",
        "actor_reference",
        "availability",
        "batch_id",
        "estimated_event_count",
        "event_name",
        "generation_policy_id",
        "pending_item_count",
        "reason_code",
        "request_id",
        "unavailable_item_count",
    }
    assert payload["availability"] == "unavailable"


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    truncate = (
        "TRUNCATE TABLE provider_cost_events, generation_items, generation_batches, "
        "job_attempts, jobs, synthetic_generation_policies, synthetic_prompt_templates CASCADE"
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text(truncate))
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(truncate))
        await engine.dispose()


async def _seed_cost_authority(sessions: async_sessionmaker[AsyncSession]) -> str:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="p2-m7-cost-v1",
        content={"subject": "synthetic"},
        content_digest="a" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="p2-m7-cost-v1",
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
            request_id="p2-m7-cost-projection",
            generation_policy_id=policy.id,
            prompt_template_id=prompt.id,
            provider_reference="deterministic-mock",
            model_reference="non-human-fixture",
            model_version_reference="fixture-v1",
            pricing_snapshot_reference="pricing-fixture-v1",
            output_media_type="image/png",
            output_width=1,
            output_height=1,
            output_max_bytes=1024,
            item_count=3,
            requested_seeds=(1, 2, 3),
            currency="CNY",
            hard_budget_micros=300,
            per_item_ceiling_micros=100,
            retry_ceiling=1,
            concurrency_ceiling=3,
        )
    )
    await service.queue_batch(created.batch.batch_id)
    reservations: list[GenerationItemReservation] = []
    for _ in range(3):
        reservation = await service.reserve_next_item(created.batch.batch_id)
        assert reservation is not None
        reservations.append(reservation)
    first, second, third = reservations
    assert await service.post_cost(
        ProviderCostInput(
            item_id=first.item_id,
            job_attempt_id=first.attempt_id,
            event_kind="final",
            currency="CNY",
            amount_micros=11,
            pricing_snapshot_reference="pricing-fixture-v1",
            occurred_at=NOW,
        )
    )
    assert await service.post_cost(
        ProviderCostInput(
            item_id=second.item_id,
            job_attempt_id=second.attempt_id,
            event_kind="estimated",
            currency="CNY",
            amount_micros=7,
            pricing_snapshot_reference="pricing-fixture-v1",
            occurred_at=NOW,
        )
    )
    assert await service.record_attempt_failure(
        item_id=third.item_id,
        attempt_id=third.attempt_id,
        result_code="provider_unavailable",
        retryable=False,
    )
    return created.batch.batch_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgresql_cost_read_model_is_read_only_and_preserves_cost_categories() -> None:
    async with _database() as sessions:
        batch_id = await _seed_cost_authority(sessions)
        async with sessions() as session:
            before_counts = (
                await session.scalar(select(func.count()).select_from(GenerationItem)),
                await session.scalar(select(func.count()).select_from(ProviderCostEvent)),
            )
        summary = await PostgresCostSummaryReadModel(session_factory=sessions).summarize_batch(
            batch_id
        )
        async with sessions() as session:
            after_counts = (
                await session.scalar(select(func.count()).select_from(GenerationItem)),
                await session.scalar(select(func.count()).select_from(ProviderCostEvent)),
            )

        assert summary.batch_id == batch_id
        assert before_counts == after_counts == (3, 2)
        assert summary.actual == (MonetaryCostAggregate(CostClassification.ACTUAL, "CNY", 11, 1),)
        assert summary.estimated == (
            MonetaryCostAggregate(CostClassification.ESTIMATED, "CNY", 7, 1),
        )
        assert summary.availability is CostAvailability.MIXED
        assert summary.unavailable_item_count == 1
        assert summary.pending_item_count == 2
        assert summary.total_item_count == 3
