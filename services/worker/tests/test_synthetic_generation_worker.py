from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mirror_api.models import (
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    SyntheticSourceObject,
    new_id,
)
from mirror_api.providers.base import (
    GenerationBudgetContext,
    SyntheticGenerationRequest,
    SyntheticOutputSpecification,
    SyntheticStorageConflictError,
)
from mirror_api.providers.mock import (
    MockImageGenerationProvider,
    MockSyntheticObjectStorageProvider,
)
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.generation_types import (
    GenerationBatchCreate,
    GenerationExecutionContext,
    GenerationItemReservation,
    GenerationOperationRejected,
    GenerationTaskReference,
    ProviderCostInput,
)
from mirror_api.synthetic_dataset.prompt_material import EphemeralPrompt
from mirror_api.synthetic_dataset.task_contract import SyntheticGenerationTaskMessage
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mirror_worker.celery_adapter import process_synthetic_generation
from mirror_worker.ingestion import RetryableWorkerFailure
from mirror_worker.synthetic_generation import (
    SyntheticGenerationReconciler,
    SyntheticGenerationTaskExecutor,
)

NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)


class FakeApplication:
    def __init__(self) -> None:
        self.reservation = GenerationItemReservation(
            batch_id="a" * 32,
            item_id="b" * 32,
            job_id="c" * 32,
            request_id="synthetic-worker-request",
            request_reference="synthetic-request-v1",
            attempt_id="d" * 32,
            attempt_number=1,
            lease_token="e" * 64,
            lease_expires_at=NOW,
            remaining_budget_micros=100,
        )
        self.available = True
        self.costs: list[ProviderCostInput] = []
        self.raw_records = 0
        self.failures: list[tuple[str, bool]] = []

    async def reserve_item(self, *, item_id: str, job_id: str) -> GenerationItemReservation | None:
        assert (item_id, job_id) == (self.reservation.item_id, self.reservation.job_id)
        if not self.available:
            return None
        self.available = False
        return self.reservation

    async def execution_context(
        self, reservation: GenerationItemReservation
    ) -> GenerationExecutionContext:
        return GenerationExecutionContext(
            reservation=reservation,
            request=SyntheticGenerationRequest(
                request_reference=reservation.request_reference,
                generation_policy_reference="generation-policy-v1",
                prompt_template_reference="prompt-template-v1",
                output_specification=SyntheticOutputSpecification(
                    media_type="image/png", width=1, height=1, max_byte_size=1024
                ),
                generation_parameters=(),
                seed=None,
                budget=GenerationBudgetContext(
                    currency="CNY",
                    max_amount_micros=100,
                    pricing_snapshot_reference="pricing-fixture-v1",
                ),
            ),
        )

    async def materialize_prompt(
        self, *, item_id: str, attempt_id: str, lease_token: str
    ) -> EphemeralPrompt:
        assert item_id == self.reservation.item_id
        assert attempt_id == self.reservation.attempt_id
        assert lease_token == self.reservation.lease_token
        return EphemeralPrompt("clearly adult synthetic non-human fixture")

    async def post_cost(self, cost: ProviderCostInput) -> bool:
        self.costs.append(cost)
        return True

    async def record_raw_stored(self, **kwargs: object) -> bool:
        assert kwargs["item_id"] == self.reservation.item_id
        assert kwargs["attempt_id"] == self.reservation.attempt_id
        self.raw_records += 1
        return True

    async def record_attempt_failure(
        self, *, item_id: str, attempt_id: str, result_code: str, retryable: bool
    ) -> bool:
        assert (item_id, attempt_id) == (
            self.reservation.item_id,
            self.reservation.attempt_id,
        )
        self.failures.append((result_code, retryable))
        return True

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[GenerationTaskReference, ...]:
        assert limit == 10
        return (
            GenerationTaskReference(
                item_id=self.reservation.item_id,
                job_id=self.reservation.job_id,
                request_id=self.reservation.request_id,
            ),
        )


class FakeRawStorage:
    async def delete_failed_attempt_orphan(self, **kwargs: str) -> object:
        raise AssertionError(f"unexpected orphan cleanup: {sorted(kwargs)}")


class CapturingRawStorage:
    def __init__(self) -> None:
        self.references: list[str] = []

    async def delete_failed_attempt_orphan(self, **kwargs: str) -> object:
        self.references.append(kwargs["storage_reference"])
        return object()


class UnavailableProvider:
    async def generate_synthetic(self, **kwargs: object) -> object:
        del kwargs
        raise RuntimeError("provider details must not escape")


class ConflictingStorage:
    async def store_generated_image_if_absent(self, **kwargs: object) -> object:
        del kwargs
        raise SyntheticStorageConflictError


class CapturingDispatcher:
    def __init__(self) -> None:
        self.messages: list[SyntheticGenerationTaskMessage] = []

    def dispatch_synthetic_generation(self, message: SyntheticGenerationTaskMessage) -> str:
        self.messages.append(message)
        return message.job_id


def _message(application: FakeApplication) -> SyntheticGenerationTaskMessage:
    return SyntheticGenerationTaskMessage(
        item_id=application.reservation.item_id,
        job_id=application.reservation.job_id,
        request_id=application.reservation.request_id,
    )


def test_reference_only_task_contract_round_trips_and_rejects_payload_expansion() -> None:
    application = FakeApplication()
    message = _message(application)
    assert SyntheticGenerationTaskMessage.from_message(message.to_message()) == message
    expanded: dict[str, object] = dict(message.to_message())
    expanded["prompt"] = "forbidden"
    with pytest.raises(ValueError, match="invalid shape"):
        SyntheticGenerationTaskMessage.from_message(expanded)
    assert set(message.to_message()) == {"item_id", "job_id", "request_id", "schema_version"}


@pytest.mark.asyncio
async def test_executor_is_at_least_once_safe_and_records_cost_before_raw_completion() -> None:
    application = FakeApplication()
    executor = SyntheticGenerationTaskExecutor(
        application=application,
        provider=MockImageGenerationProvider(),
        storage=MockSyntheticObjectStorageProvider(),
        raw_storage=FakeRawStorage(),  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    first = await executor.execute(_message(application))
    duplicate = await executor.execute(_message(application))
    assert first.status == "raw_stored"
    assert duplicate.status == "no_op"
    assert len(application.costs) == 1
    assert application.raw_records == 1
    assert application.failures == []


@pytest.mark.asyncio
async def test_provider_failure_is_redacted_retryable_and_records_attempt_failure() -> None:
    application = FakeApplication()
    executor = SyntheticGenerationTaskExecutor(
        application=application,
        provider=UnavailableProvider(),  # type: ignore[arg-type]
        storage=MockSyntheticObjectStorageProvider(),
        raw_storage=FakeRawStorage(),  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    with pytest.raises(RetryableWorkerFailure, match="provider remains retryable") as failure:
        await executor.execute(_message(application))
    assert "provider details" not in str(failure.value)
    assert application.failures == [("provider_unavailable", True)]


@pytest.mark.asyncio
async def test_storage_conflict_fails_closed_after_preserving_provider_cost() -> None:
    application = FakeApplication()
    executor = SyntheticGenerationTaskExecutor(
        application=application,
        provider=MockImageGenerationProvider(),
        storage=ConflictingStorage(),  # type: ignore[arg-type]
        raw_storage=FakeRawStorage(),  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    result = await executor.execute(_message(application))
    assert result.status == "generation_failed"
    assert len(application.costs) == 1
    assert application.failures == [("raw_storage_conflict", False)]


@pytest.mark.asyncio
async def test_database_completion_failure_marks_retryable_and_cleans_exact_orphan() -> None:
    application = FakeApplication()

    async def reject_raw(**kwargs: object) -> bool:
        del kwargs
        raise GenerationOperationRejected("raw_stored_rejected")

    application.record_raw_stored = reject_raw  # type: ignore[method-assign]
    raw_storage = CapturingRawStorage()
    executor = SyntheticGenerationTaskExecutor(
        application=application,
        provider=MockImageGenerationProvider(),
        storage=MockSyntheticObjectStorageProvider(),
        raw_storage=raw_storage,  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    with pytest.raises(RetryableWorkerFailure, match="persistence remains retryable"):
        await executor.execute(_message(application))
    assert application.failures == [("database_write_failed", True)]
    assert len(raw_storage.references) == 1
    assert raw_storage.references[0].startswith("raw-")


@pytest.mark.asyncio
async def test_reconciler_dispatches_only_reference_messages() -> None:
    application = FakeApplication()
    dispatcher = CapturingDispatcher()
    dispatched = await SyntheticGenerationReconciler(
        application=application,
        dispatcher=dispatcher,
    ).execute(limit=10)
    assert dispatched == (application.reservation.item_id,)
    assert dispatcher.messages == [_message(application)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_linux_celery_postgresql_synthetic_generation_round_trip() -> None:
    if os.getenv("RUN_CELERY_INTEGRATION") != "true":
        pytest.skip("NOT VERIFIED LOCALLY: Linux Celery + Redis worker unavailable")
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required for the Celery integration gate")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    stored_reference: str | None = None
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
        policy = SyntheticGenerationPolicy(
            id=new_id(),
            version="celery-generation-v1",
            content={"subject": "synthetic"},
            content_digest="1" * 64,
        )
        prompt = SyntheticPromptTemplate(
            id=new_id(),
            version="celery-prompt-v1",
            content={"template": "clearly adult synthetic non-human fixture"},
            content_digest="2" * 64,
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
        service = GenerationBatchService(session_factory=sessions)
        created = await service.create_batch(
            GenerationBatchCreate(
                idempotency_key_hash="3" * 64,
                request_id="celery-synthetic-generation",
                generation_policy_id=policy.id,
                prompt_template_id=prompt.id,
                provider_reference="mock-provider-v1",
                model_reference="mock-model-v1",
                model_version_reference="mock-model-version-v1",
                pricing_snapshot_reference="pricing-fixture-v1",
                output_media_type="image/png",
                output_width=1,
                output_height=1,
                output_max_bytes=1024,
                item_count=1,
                requested_seeds=(None,),
                currency="CNY",
                hard_budget_micros=100,
                per_item_ceiling_micros=100,
                retry_ceiling=1,
                concurrency_ceiling=1,
            )
        )
        await service.queue_batch(created.batch.batch_id)
        item = created.items[0]
        message = SyntheticGenerationTaskMessage(
            item_id=item.item_id,
            job_id=item.job_id,
            request_id="celery-synthetic-generation",
        )
        async_result = process_synthetic_generation.apply_async(args=[message.to_message()])
        result = await asyncio.to_thread(async_result.get, 20)
        assert result == {
            "item_id": item.item_id,
            "job_id": item.job_id,
            "status": "raw_stored",
        }
        observed = await service.get_batch(created.batch.batch_id)
        assert observed.batch.status == "COMPLETED"
        assert observed.items[0].status == "RAW_STORED"
        async with sessions() as session:
            stored_reference = await session.scalar(
                select(SyntheticSourceObject.storage_reference).where(
                    SyntheticSourceObject.generation_item_id == item.item_id
                )
            )
        assert stored_reference is not None
        persistent_storage = LocalSyntheticRawStorageProvider(
            root=Path(os.environ["LOCAL_STORAGE_ROOT"])
        )
        metadata = await persistent_storage.inspect_generated_image(
            storage_reference=stored_reference
        )
        assert metadata is not None
        assert metadata.media_type == "image/png"
        assert (
            await persistent_storage.delete_generated_image(storage_reference=stored_reference)
            == "deleted"
        )
    finally:
        if stored_reference is not None:
            persistent_storage = LocalSyntheticRawStorageProvider(
                root=Path(os.environ["LOCAL_STORAGE_ROOT"])
            )
            await persistent_storage.delete_generated_image(storage_reference=stored_reference)
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
