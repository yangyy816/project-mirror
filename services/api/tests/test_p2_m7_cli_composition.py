from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import (
    AuditLog,
    GenerationBatch,
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

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 23, 0, tzinfo=UTC)


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


async def _service(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[GenerationBatchService, str, str]:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="p2-m7-r14-v1",
        content={"subject": "synthetic"},
        content_digest="a" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="p2-m7-r14-v1",
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
    return GenerationBatchService(session_factory=sessions, now=lambda: NOW), policy.id, prompt.id


async def _batch(
    service: GenerationBatchService,
    *,
    generation_policy_id: str,
    prompt_template_id: str,
    idempotency_character: str,
    item_count: int,
) -> str:
    created = await service.create_batch(
        GenerationBatchCreate(
            idempotency_key_hash=idempotency_character * 64,
            request_id=f"p2-m7-r14-{idempotency_character}",
            generation_policy_id=generation_policy_id,
            prompt_template_id=prompt_template_id,
            provider_reference="deterministic-mock",
            model_reference="non-human-fixture",
            model_version_reference="fixture-v1",
            pricing_snapshot_reference="pricing-fixture-v1",
            output_media_type="image/png",
            output_width=1,
            output_height=1,
            output_max_bytes=1024,
            item_count=item_count,
            requested_seeds=tuple(range(1, item_count + 1)),
            currency="CNY",
            hard_budget_micros=100 * item_count,
            per_item_ceiling_micros=100,
            retry_ceiling=1,
            concurrency_ceiling=item_count,
        )
    )
    await service.queue_batch(created.batch.batch_id)
    return created.batch.batch_id


def _arguments(
    operation: str,
    batch_id: str,
    expected_state: str,
    request_id: str,
) -> list[str]:
    return [
        "--operation",
        operation,
        "--environment",
        "ci",
        "--target-id",
        batch_id,
        "--expected-state",
        expected_state,
        "--actor",
        "system.operator",
        "--reason",
        "r14_integration",
        "--request-id",
        request_id,
    ]


def _run_cli(arguments: Sequence[str], database_url: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["MIRROR_DATASET_DATABASE_ENVIRONMENT"] = "ci"
    environment["MIRROR_DATASET_DATABASE_URL"] = database_url
    source_paths = (ROOT / "services" / "api" / "src", ROOT / "services" / "worker" / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            *(str(path) for path in source_paths),
            *([existing_pythonpath] if existing_pythonpath else []),
        ]
    )
    return subprocess.run(  # noqa: S603 - fixed interpreter/module and validated argument vector.
        [sys.executable, "-m", "mirror_api.scripts.mirror_dataset", *arguments],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _assert_configuration_redacted(
    database_url: str, *results: subprocess.CompletedProcess[str]
) -> None:
    assert all(database_url not in result.stdout + result.stderr for result in results)


@pytest.mark.asyncio
async def test_real_subprocess_batch_status_cancel_stale_and_replay() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    async with _database() as sessions:
        service, policy_id, prompt_id = await _service(sessions)
        batch_id = await _batch(
            service,
            generation_policy_id=policy_id,
            prompt_template_id=prompt_id,
            idempotency_character="c",
            item_count=1,
        )

        status = _run_cli(_arguments("batch_status", batch_id, "QUEUED", "1" * 32), database_url)
        stale = _run_cli(_arguments("batch_cancel", batch_id, "DRAFT", "2" * 32), database_url)
        cancelled = _run_cli(_arguments("batch_cancel", batch_id, "QUEUED", "3" * 32), database_url)
        replay = _run_cli(_arguments("batch_cancel", batch_id, "QUEUED", "3" * 32), database_url)

        assert status.returncode == 0
        assert json.loads(status.stdout) == {
            "code": "operation_completed",
            "event_count": 1,
            "operation": "batch_status",
            "outcome": "succeeded",
            "request_id": "1" * 32,
            "target_id": batch_id,
            "target_status": "QUEUED",
        }
        assert stale.returncode == 2
        assert json.loads(stale.stdout)["code"] == "operation_stale_expectation"
        assert cancelled.returncode == replay.returncode == 0
        assert cancelled.stdout == replay.stdout
        assert json.loads(cancelled.stdout)["target_status"] == "CANCELLED"
        async with sessions() as session:
            batch = await session.get(GenerationBatch, batch_id)
            assert batch is not None and batch.status == "CANCELLED"
            assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1
        _assert_configuration_redacted(database_url, status, stale, cancelled, replay)


@pytest.mark.asyncio
async def test_real_subprocess_cost_summary_and_unavailable_capabilities() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    async with _database() as sessions:
        service, policy_id, prompt_id = await _service(sessions)
        batch_id = await _batch(
            service,
            generation_policy_id=policy_id,
            prompt_template_id=prompt_id,
            idempotency_character="d",
            item_count=3,
        )
        reservations: list[GenerationItemReservation] = []
        for _ in range(3):
            reservation = await service.reserve_next_item(batch_id)
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
        async with sessions() as session:
            before = (
                await session.scalar(select(func.count()).select_from(GenerationItem)),
                await session.scalar(select(func.count()).select_from(ProviderCostEvent)),
                await session.scalar(select(func.count()).select_from(AuditLog)),
            )

        cost = _run_cli(_arguments("cost_summary", batch_id, "RUNNING", "4" * 32), database_url)
        provenance = _run_cli(
            _arguments("provenance_status", batch_id, "RUNNING", "5" * 32), database_url
        )
        qa = _run_cli(_arguments("qa_status", batch_id, "RUNNING", "6" * 32), database_url)

        assert cost.returncode == 0
        assert json.loads(cost.stdout) == {
            "code": "operation_completed",
            "cost_summary": {
                "actual": [
                    {
                        "amount_micros": 11,
                        "classification": "actual",
                        "currency": "CNY",
                        "event_count": 1,
                    }
                ],
                "availability": "mixed",
                "estimated": [
                    {
                        "amount_micros": 7,
                        "classification": "estimated",
                        "currency": "CNY",
                        "event_count": 1,
                    }
                ],
                "pending_item_count": 2,
                "total_item_count": 3,
                "unavailable_item_count": 1,
            },
            "event_count": 2,
            "operation": "cost_summary",
            "outcome": "succeeded",
            "request_id": "4" * 32,
            "target_id": batch_id,
            "target_status": "RUNNING",
        }
        assert provenance.returncode == qa.returncode == 2
        assert json.loads(provenance.stdout)["code"] == "operation_backend_unavailable"
        assert json.loads(qa.stdout)["code"] == "operation_backend_unavailable"
        async with sessions() as session:
            after = (
                await session.scalar(select(func.count()).select_from(GenerationItem)),
                await session.scalar(select(func.count()).select_from(ProviderCostEvent)),
                await session.scalar(select(func.count()).select_from(AuditLog)),
            )
        assert before == after == (3, 2, 0)
        _assert_configuration_redacted(database_url, cost, provenance, qa)
