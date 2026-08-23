from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import (
    AuditLog,
    GenerationBatch,
    GenerationItem,
    Job,
    JobAttempt,
    ProviderCostEvent,
    SyntheticGenerationEvidence,
    SyntheticSourceObject,
    new_id,
)
from mirror_api.providers.base import (
    GenerationBudgetContext,
    SyntheticGenerationRequest,
    SyntheticGenerationResult,
    SyntheticOutputSpecification,
    SyntheticStoredImage,
)
from mirror_api.synthetic_dataset.generation_repository import GenerationRepository
from mirror_api.synthetic_dataset.generation_types import (
    GenerationBatchCreate,
    GenerationBatchResult,
    GenerationBatchView,
    GenerationExecutionContext,
    GenerationItemReservation,
    GenerationItemView,
    GenerationOperationRejected,
    GenerationTaskReference,
    ProviderCostInput,
    validate_result_code,
)
from mirror_api.synthetic_dataset.prompt_material import EphemeralPrompt


def _utcnow() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def _transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


class GenerationBatchService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = _utcnow,
        lease_seconds: int = 300,
    ) -> None:
        if not 30 <= lease_seconds <= 3600:
            raise ValueError("generation lease seconds are outside the boundary")
        self._sessions = session_factory
        self._now = now
        self._lease_seconds = lease_seconds

    async def create_batch(self, command: GenerationBatchCreate) -> GenerationBatchResult:
        now = self._now()
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            batch_id = new_id()
            created = await repo.insert_batch_if_absent(batch_id=batch_id, command=command, now=now)
            if not created:
                existing = await repo.locked_batch_by_idempotency(command.idempotency_key_hash)
                if existing is None:
                    raise RuntimeError("generation batch idempotency authority disappeared")
                items = await repo.items(existing.id, lock=True)
                if not self._matches(existing, items, command):
                    raise GenerationOperationRejected("idempotency_conflict")
                return self._result(existing, items, created=False)

            batch = await repo.locked_batch(batch_id)
            if batch is None:  # pragma: no cover - INSERT RETURNING invariant
                raise RuntimeError("generation batch authority disappeared")
            jobs: list[Job] = []
            items_to_add: list[GenerationItem] = []
            for ordinal, seed in enumerate(command.requested_seeds):
                job_id = new_id()
                item_id = new_id()
                request_reference = f"generation-item-{item_id}"
                jobs.append(
                    Job(
                        id=job_id,
                        job_type="synthetic_generation",
                        status="pending",
                        idempotency_key_hash=self._job_key(batch_id, ordinal),
                        request_id=self._item_request_id(command.request_id, ordinal),
                        payload={},
                        owner_user_id=None,
                        attempt_count=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
                items_to_add.append(
                    GenerationItem(
                        id=item_id,
                        batch_id=batch_id,
                        ordinal=ordinal,
                        job_id=job_id,
                        request_reference=request_reference,
                        requested_seed=seed,
                        reserved_budget_micros=command.per_item_ceiling_micros,
                        status="REQUESTED",
                        created_at=now,
                        updated_at=now,
                    )
                )
            session.add_all(jobs)
            await session.flush()
            session.add_all(items_to_add)
            await session.flush()
            return self._result(batch, await repo.items(batch_id), created=True)

    async def queue_batch(self, batch_id: str) -> GenerationBatchResult:
        now = self._now()
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            batch = await repo.locked_batch(batch_id)
            if batch is None:
                raise GenerationOperationRejected("generation_batch_not_found")
            items = await repo.items(batch.id, lock=True)
            if batch.status == "DRAFT":
                batch.status = "QUEUED"
                batch.queued_at = now
                batch.updated_at = now
                await session.flush()
            elif batch.status != "QUEUED":
                raise GenerationOperationRejected("generation_batch_not_queueable")
            return self._result(batch, items, created=False)

    async def get_batch(self, batch_id: str) -> GenerationBatchResult:
        async with self._sessions() as session:
            repo = GenerationRepository(session)
            batch = await repo.locked_batch(batch_id)
            if batch is None:
                raise GenerationOperationRejected("generation_batch_not_found")
            return self._result(batch, await repo.items(batch.id), created=False)

    async def reserve_next_item(self, batch_id: str) -> GenerationItemReservation | None:
        now = self._now()
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            batch = await repo.locked_batch(batch_id)
            if batch is None:
                raise GenerationOperationRejected("generation_batch_not_found")
            if batch.status not in {"QUEUED", "RUNNING"} or batch.cancel_requested_at is not None:
                return None

            item = await repo.locked_retry_item(batch.id)
            if item is None:
                if await repo.generating_count(batch.id) >= batch.concurrency_ceiling:
                    return None
                item = await repo.locked_requested_item(batch.id)
            if item is None:
                return None
            job = await repo.locked_job(item.job_id)
            if job is None or job.status != "pending":
                raise GenerationOperationRejected("generation_job_not_reservable")
            remaining_budget = item.reserved_budget_micros - await repo.item_spend(item.id)
            if remaining_budget <= 0:
                await self._finalize_failed(
                    session, repo, batch, item, job, now, "budget_exhausted"
                )
                return None
            if job.attempt_count >= batch.retry_ceiling + 1:
                await self._finalize_failed(session, repo, batch, item, job, now, "retry_exhausted")
                return None

            if batch.status == "QUEUED":
                batch.status = "RUNNING"
                batch.started_at = now
                batch.updated_at = now
            lease_token = secrets.token_hex(32)
            lease_expires_at = now + timedelta(seconds=self._lease_seconds)
            job.status = "leased"
            job.attempt_count += 1
            job.lease_token = lease_token
            job.lease_acquired_at = now
            job.lease_expires_at = lease_expires_at
            job.updated_at = now
            if item.status == "REQUESTED":
                item.status = "GENERATING"
                item.started_at = now
                item.updated_at = now
            attempt = JobAttempt(
                id=new_id(),
                job_id=job.id,
                attempt=job.attempt_count,
                status="leased",
                lease_token=lease_token,
                started_at=now,
            )
            session.add(attempt)
            await session.flush()
            return GenerationItemReservation(
                batch_id=batch.id,
                item_id=item.id,
                job_id=job.id,
                request_id=job.request_id,
                request_reference=item.request_reference,
                attempt_id=attempt.id,
                attempt_number=attempt.attempt,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                remaining_budget_micros=remaining_budget,
            )

    async def reserve_item(self, *, item_id: str, job_id: str) -> GenerationItemReservation | None:
        now = self._now()
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            observed_item = await repo.item(item_id)
            if observed_item is None or observed_item.job_id != job_id:
                raise GenerationOperationRejected("generation_task_mismatch")
            batch = await repo.locked_batch(observed_item.batch_id)
            item = await repo.locked_item(item_id)
            if batch is None or item is None or item.batch_id != batch.id or item.job_id != job_id:
                raise GenerationOperationRejected("generation_task_mismatch")
            if batch.status not in {"QUEUED", "RUNNING"}:
                return None
            job = await repo.locked_job(job_id)
            if job is None:
                raise GenerationOperationRejected("generation_job_not_reservable")
            if job.status == "leased":
                if job.lease_expires_at is None or job.lease_token is None:
                    raise GenerationOperationRejected("generation_lease_invalid")
                if job.lease_expires_at > now:
                    return None
                expired_attempt = await repo.locked_attempt_for_lease(
                    job_id=job.id, lease_token=job.lease_token
                )
                if expired_attempt is None or expired_attempt.status != "leased":
                    raise GenerationOperationRejected("generation_lease_invalid")
                expired_attempt.status = "retryable_failure"
                expired_attempt.error_code = "lease_expired"
                expired_attempt.finished_at = now
                job.status = "pending"
                job.lease_token = None
                job.lease_acquired_at = None
                job.lease_expires_at = None
                job.updated_at = now
            if batch.cancel_requested_at is not None:
                if job.status == "pending" and item.status == "GENERATING":
                    await self._finalize_failed(
                        session, repo, batch, item, job, now, "batch_cancelled"
                    )
                return None
            if job.status != "pending" or item.status not in {"REQUESTED", "GENERATING"}:
                return None
            if item.status == "REQUESTED" and (
                await repo.generating_count(batch.id) >= batch.concurrency_ceiling
            ):
                return None
            remaining_budget = item.reserved_budget_micros - await repo.item_spend(item.id)
            if remaining_budget <= 0:
                await self._finalize_failed(
                    session, repo, batch, item, job, now, "budget_exhausted"
                )
                return None
            if job.attempt_count >= batch.retry_ceiling + 1:
                await self._finalize_failed(session, repo, batch, item, job, now, "retry_exhausted")
                return None
            if batch.status == "QUEUED":
                batch.status = "RUNNING"
                batch.started_at = now
                batch.updated_at = now
            lease_token = secrets.token_hex(32)
            lease_expires_at = now + timedelta(seconds=self._lease_seconds)
            job.status = "leased"
            job.attempt_count += 1
            job.lease_token = lease_token
            job.lease_acquired_at = now
            job.lease_expires_at = lease_expires_at
            job.updated_at = now
            if item.status == "REQUESTED":
                item.status = "GENERATING"
                item.started_at = now
                item.updated_at = now
            attempt = JobAttempt(
                id=new_id(),
                job_id=job.id,
                attempt=job.attempt_count,
                status="leased",
                lease_token=lease_token,
                started_at=now,
            )
            session.add(attempt)
            await session.flush()
            return GenerationItemReservation(
                batch_id=batch.id,
                item_id=item.id,
                job_id=job.id,
                request_id=job.request_id,
                request_reference=item.request_reference,
                attempt_id=attempt.id,
                attempt_number=attempt.attempt,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                remaining_budget_micros=remaining_budget,
            )

    async def execution_context(
        self, reservation: GenerationItemReservation
    ) -> GenerationExecutionContext:
        async with self._sessions() as session:
            repo = GenerationRepository(session)
            observed_item = await repo.item(reservation.item_id)
            if observed_item is None:
                raise GenerationOperationRejected("generation_context_unavailable")
            batch = await repo.locked_batch(observed_item.batch_id)
            item = await repo.locked_item(reservation.item_id)
            job = None if item is None else await repo.locked_job(item.job_id)
            attempt = await repo.locked_attempt(reservation.attempt_id)
            now = self._now()
            if (
                batch is None
                or item is None
                or job is None
                or item.batch_id != batch.id
                or item.job_id != reservation.job_id
                or job.id != reservation.job_id
                or job.status != "leased"
                or job.lease_token != reservation.lease_token
                or job.lease_expires_at is None
                or job.lease_expires_at <= now
                or attempt is None
                or attempt.job_id != job.id
                or attempt.status != "leased"
                or attempt.lease_token != reservation.lease_token
                or batch.cancel_requested_at is not None
            ):
                raise GenerationOperationRejected("generation_context_unavailable")
            remaining_budget = item.reserved_budget_micros - await repo.item_spend(item.id)
            return GenerationExecutionContext(
                reservation=reservation,
                request=SyntheticGenerationRequest(
                    request_reference=item.request_reference,
                    generation_policy_reference=(f"generation-policy-{batch.generation_policy_id}"),
                    prompt_template_reference=(f"prompt-template-{batch.prompt_template_id}"),
                    output_specification=SyntheticOutputSpecification(
                        media_type=cast(
                            Literal["image/jpeg", "image/png", "image/webp"],
                            batch.output_media_type,
                        ),
                        width=batch.output_width,
                        height=batch.output_height,
                        max_byte_size=batch.output_max_bytes,
                    ),
                    generation_parameters=(),
                    seed=item.requested_seed,
                    budget=GenerationBudgetContext(
                        currency=cast(Literal["CNY", "USD"], batch.currency),
                        max_amount_micros=remaining_budget,
                        pricing_snapshot_reference=batch.pricing_snapshot_reference,
                    ),
                ),
            )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[GenerationTaskReference, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("generation reconciliation limit is outside the boundary")
        async with self._sessions() as session:
            rows = await GenerationRepository(session).generation_reconciliation_rows(
                now=self._now(), limit=limit
            )
            return tuple(
                GenerationTaskReference(
                    item_id=item.id,
                    job_id=job.id,
                    request_id=job.request_id,
                )
                for item, job in rows
            )

    async def record_attempt_failure(
        self,
        *,
        item_id: str,
        attempt_id: str,
        result_code: str,
        retryable: bool,
    ) -> bool:
        validate_result_code(result_code)
        now = self._now()
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            observed_item = await repo.item(item_id)
            if observed_item is None:
                raise GenerationOperationRejected("generation_item_not_found")
            batch = await repo.locked_batch(observed_item.batch_id)
            item = await repo.locked_item(item_id)
            if item is None or batch is None or item.batch_id != batch.id:
                raise GenerationOperationRejected("generation_item_not_found")
            job = await repo.locked_job(item.job_id)
            attempt = await repo.locked_attempt(attempt_id)
            if (
                attempt is not None
                and attempt.job_id == item.job_id
                and attempt.status in {"retryable_failure", "generation_failed"}
                and attempt.error_code == result_code
            ):
                return False
            if (
                job is None
                or attempt is None
                or attempt.job_id != job.id
                or attempt.status != "leased"
                or attempt.lease_token != job.lease_token
            ):
                raise GenerationOperationRejected("generation_attempt_mismatch")
            attempt.status = "retryable_failure" if retryable else "generation_failed"
            attempt.error_code = result_code
            attempt.finished_at = now
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.updated_at = now
            remaining_budget = item.reserved_budget_micros - await repo.item_spend(item.id)
            retry_allowed = (
                retryable
                and batch.cancel_requested_at is None
                and job.attempt_count < batch.retry_ceiling + 1
                and remaining_budget > 0
            )
            if retry_allowed:
                job.status = "pending"
                return True
            await self._finalize_failed(session, repo, batch, item, job, now, result_code)
            return True

    async def request_cancel(self, batch_id: str) -> GenerationBatchResult:
        return await self._request_cancel(batch_id)

    async def request_cancel_with_expectation(
        self,
        *,
        batch_id: str,
        expected_status: str,
        actor_reference: str,
        reason_code: str,
        request_id: str,
    ) -> GenerationBatchResult:
        """Request cancellation atomically with an operator expectation and audit record.

        This is deliberately an additive internal control-plane entry point.  It shares the
        existing batch/item/job locking and cancellation semantics; it does not alter budget or
        worker behaviour.  A stale operator never obtains a best-effort cancellation.
        """

        return await self._request_cancel(
            batch_id,
            expected_status=expected_status,
            actor_reference=actor_reference,
            reason_code=reason_code,
            request_id=request_id,
        )

    async def _request_cancel(
        self,
        batch_id: str,
        *,
        expected_status: str | None = None,
        actor_reference: str | None = None,
        reason_code: str | None = None,
        request_id: str | None = None,
    ) -> GenerationBatchResult:
        now = self._now()
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            batch = await repo.locked_batch(batch_id)
            if batch is None:
                raise GenerationOperationRejected("generation_batch_not_found")
            if expected_status is not None and batch.status != expected_status:
                raise GenerationOperationRejected("generation_batch_stale_expectation")
            if batch.status not in {"QUEUED", "RUNNING", "CANCELLED"}:
                raise GenerationOperationRejected("generation_batch_not_cancellable")
            items = await repo.items(batch.id, lock=True)
            if batch.status == "CANCELLED":
                return self._result(batch, items, created=False)
            if batch.cancel_requested_at is None:
                batch.cancel_requested_at = now
                batch.updated_at = now
            for item in items:
                job = await repo.locked_job(item.job_id)
                if job is None:
                    raise RuntimeError("generation item job authority disappeared")
                if item.status == "REQUESTED" or (
                    item.status == "GENERATING" and job.status == "pending"
                ):
                    item.status = "CANCELLED"
                    item.result_code = "batch_cancelled"
                    item.finalized_at = now
                    item.updated_at = now
                    job.status = "cancelled"
                    job.result_code = "batch_cancelled"
                    job.finalized_at = now
                    job.updated_at = now
            await session.flush()
            await self._finalize_batch_if_quiescent(repo, batch, now)
            if request_id is not None:
                if (
                    actor_reference is None or reason_code is None
                ):  # pragma: no cover - caller invariant
                    raise RuntimeError("operator cancellation audit fields are incomplete")
                session.add(
                    AuditLog(
                        id=new_id(),
                        actor_type="system_operator",
                        actor_id=None,
                        action="synthetic_batch_cancel_requested",
                        target_type="generation_batch",
                        target_id=batch.id,
                        request_id=request_id,
                        metadata_json={
                            "actor_reference": actor_reference,
                            "reason_code": reason_code,
                            "expected_status": expected_status,
                            "result_status": batch.status,
                        },
                        occurred_at=now,
                    )
                )
            await session.flush()
            return self._result(batch, await repo.items(batch.id), created=False)

    async def post_cost(self, cost: ProviderCostInput) -> bool:
        now = self._now()
        try:
            async with _transaction(self._sessions) as session:
                repo = GenerationRepository(session)
                created = await repo.post_cost_if_absent(
                    event_id=new_id(), cost=cost, created_at=now
                )
                if created:
                    return True
                existing = await repo.cost_for_attempt(cost.job_attempt_id)
                if existing is None:
                    raise RuntimeError("provider cost idempotency authority disappeared")
                if (
                    existing.generation_item_id != cost.item_id
                    or existing.event_kind != cost.event_kind
                    or existing.currency != cost.currency
                    or existing.amount_micros != cost.amount_micros
                    or existing.pricing_snapshot_reference != cost.pricing_snapshot_reference
                    or existing.occurred_at != cost.occurred_at
                ):
                    raise GenerationOperationRejected("provider_cost_conflict")
                return False
        except DBAPIError:
            raise GenerationOperationRejected("provider_cost_rejected") from None

    async def record_raw_stored(
        self,
        *,
        item_id: str,
        attempt_id: str,
        result: SyntheticGenerationResult,
        stored: SyntheticStoredImage,
        retention_expires_at: datetime,
    ) -> bool:
        now = self._now()
        if result.safety.outcome != "passed":
            raise GenerationOperationRejected("provider_safety_rejected")
        if retention_expires_at <= now:
            raise GenerationOperationRejected("raw_retention_invalid")
        if (
            result.request_reference == ""
            or stored.sha256 != hashlib.sha256(result.payload.content).hexdigest()
        ):
            raise GenerationOperationRejected("raw_storage_mismatch")
        try:
            async with _transaction(self._sessions) as session:
                repo = GenerationRepository(session)
                observed_item = await repo.item(item_id)
                if observed_item is None:
                    raise GenerationOperationRejected("generation_item_not_found")
                batch = await repo.locked_batch(observed_item.batch_id)
                item = await repo.locked_item(item_id)
                if batch is None or item is None or item.batch_id != batch.id:
                    raise GenerationOperationRejected("generation_item_not_found")
                if item.status == "RAW_STORED":
                    chain = await repo.raw_chain(item.id)
                    if (
                        chain is None
                        or chain[0].job_attempt_id != attempt_id
                        or chain[0].storage_reference != stored.storage_reference
                        or chain[0].sha256 != stored.sha256
                        or chain[1].provider_run_reference != result.provider_run_reference
                    ):
                        raise GenerationOperationRejected("raw_stored_conflict")
                    return False
                job = await repo.locked_job(item.job_id)
                attempt = await repo.locked_attempt(attempt_id)
                if (
                    item.status != "GENERATING"
                    or job is None
                    or attempt is None
                    or attempt.job_id != job.id
                    or attempt.status != "leased"
                    or attempt.lease_token != job.lease_token
                ):
                    raise GenerationOperationRejected("generation_attempt_mismatch")
                await repo.lock_storage_reference(stored.storage_reference)
                if (
                    result.request_reference != item.request_reference
                    or result.provenance.provider_reference != batch.provider_reference
                    or result.provenance.model_reference != batch.model_reference
                    or result.provenance.model_version_reference != batch.model_version_reference
                    or result.payload.media_type != batch.output_media_type
                    or stored.media_type != result.payload.media_type
                    or stored.byte_size != result.payload.byte_size
                    or stored.byte_size > batch.output_max_bytes
                    or result.cost.currency != batch.currency
                ):
                    raise GenerationOperationRejected("generation_result_mismatch")
                existing_cost = await repo.cost_for_attempt(attempt.id)
                if existing_cost is not None and (
                    existing_cost.generation_item_id != item.id
                    or existing_cost.event_kind != result.cost.status
                    or existing_cost.currency != result.cost.currency
                    or existing_cost.amount_micros != result.cost.amount_micros
                    or existing_cost.pricing_snapshot_reference != batch.pricing_snapshot_reference
                ):
                    raise GenerationOperationRejected("provider_cost_conflict")
                records: list[object] = [
                    SyntheticSourceObject(
                        id=new_id(),
                        generation_item_id=item.id,
                        job_attempt_id=attempt.id,
                        storage_reference=stored.storage_reference,
                        sha256=stored.sha256,
                        media_type=stored.media_type,
                        byte_size=stored.byte_size,
                        width=batch.output_width,
                        height=batch.output_height,
                        retention_expires_at=retention_expires_at,
                        created_at=now,
                    ),
                    SyntheticGenerationEvidence(
                        id=new_id(),
                        generation_item_id=item.id,
                        job_attempt_id=attempt.id,
                        provider_reference=result.provenance.provider_reference,
                        model_reference=result.provenance.model_reference,
                        model_version_reference=result.provenance.model_version_reference,
                        provider_run_reference=result.provider_run_reference,
                        safety_policy_reference=result.safety.policy_reference,
                        safety_outcome=result.safety.outcome,
                        safety_reason_code=result.safety.reason_code,
                        retention_status=result.provenance.retention_status,
                        output_rights=result.provenance.output_rights,
                        provider_actual_seed=result.provider_actual_seed,
                        provider_actual_parameters={
                            parameter.parameter_key: parameter.value
                            for parameter in result.provider_actual_parameters
                        },
                        reproducibility_level=result.reproducibility_level,
                        generated_at=now,
                        created_at=now,
                    ),
                ]
                if existing_cost is None:
                    records.append(
                        ProviderCostEvent(
                            id=new_id(),
                            generation_item_id=item.id,
                            job_attempt_id=attempt.id,
                            event_kind=result.cost.status,
                            currency=result.cost.currency,
                            amount_micros=result.cost.amount_micros,
                            pricing_snapshot_reference=batch.pricing_snapshot_reference,
                            occurred_at=now,
                            created_at=now,
                        )
                    )
                session.add_all(records)
                await session.flush()
                attempt.status = "raw_stored"
                attempt.result_code = "raw_stored"
                attempt.error_code = None
                attempt.finished_at = now
                job.status = "succeeded"
                job.lease_token = None
                job.lease_acquired_at = None
                job.lease_expires_at = None
                job.result_code = "raw_stored"
                job.finalized_at = now
                job.updated_at = now
                await session.flush()
                item.status = "RAW_STORED"
                item.result_code = "raw_stored"
                item.finalized_at = now
                item.updated_at = now
                await session.flush()
                await self._finalize_batch_if_quiescent(repo, batch, now)
                await session.flush()
                return True
        except DBAPIError:
            raise GenerationOperationRejected("raw_stored_rejected") from None

    async def materialize_prompt(
        self,
        *,
        item_id: str,
        attempt_id: str,
        lease_token: str,
    ) -> EphemeralPrompt:
        now = self._now()
        async with self._sessions() as session:
            repo = GenerationRepository(session)
            observed_item = await repo.item(item_id)
            if observed_item is None:
                raise GenerationOperationRejected("prompt_material_unavailable")
            batch = await repo.locked_batch(observed_item.batch_id)
            item = await repo.locked_item(item_id)
            if batch is None or item is None or item.batch_id != batch.id:
                raise RuntimeError("generation batch authority disappeared")
            job = await repo.locked_job(item.job_id)
            attempt = await repo.locked_attempt(attempt_id)
            if (
                item.status != "GENERATING"
                or job is None
                or job.status != "leased"
                or job.lease_token != lease_token
                or job.lease_expires_at is None
                or job.lease_expires_at <= now
                or attempt is None
                or attempt.job_id != job.id
                or attempt.status != "leased"
                or attempt.lease_token != lease_token
            ):
                raise GenerationOperationRejected("prompt_material_unavailable")
            template = await repo.prompt_template(batch.prompt_template_id)
            if template is None:
                raise GenerationOperationRejected("prompt_authority_unavailable")
            try:
                return EphemeralPrompt.from_template_content(template.content)
            except (TypeError, ValueError):
                raise GenerationOperationRejected("prompt_authority_unavailable") from None

    @staticmethod
    def _job_key(batch_id: str, ordinal: int) -> str:
        return hashlib.sha256(
            f"synthetic-generation-job-v1\n{batch_id}\n{ordinal}".encode()
        ).hexdigest()

    @staticmethod
    def _item_request_id(request_id: str, ordinal: int) -> str:
        return f"{request_id}:{ordinal}"

    @staticmethod
    def _matches(
        batch: GenerationBatch,
        items: tuple[GenerationItem, ...],
        command: GenerationBatchCreate,
    ) -> bool:
        return (
            batch.generation_policy_id == command.generation_policy_id
            and batch.prompt_template_id == command.prompt_template_id
            and batch.provider_reference == command.provider_reference
            and batch.model_reference == command.model_reference
            and batch.model_version_reference == command.model_version_reference
            and batch.pricing_snapshot_reference == command.pricing_snapshot_reference
            and batch.output_media_type == command.output_media_type
            and batch.output_width == command.output_width
            and batch.output_height == command.output_height
            and batch.output_max_bytes == command.output_max_bytes
            and batch.item_count == command.item_count
            and batch.currency == command.currency
            and batch.hard_budget_micros == command.hard_budget_micros
            and batch.per_item_ceiling_micros == command.per_item_ceiling_micros
            and batch.retry_ceiling == command.retry_ceiling
            and batch.concurrency_ceiling == command.concurrency_ceiling
            and tuple(item.requested_seed for item in items) == command.requested_seeds
        )

    @staticmethod
    def _batch_view(batch: GenerationBatch) -> GenerationBatchView:
        return GenerationBatchView(
            batch_id=batch.id,
            status=batch.status,
            item_count=batch.item_count,
            hard_budget_micros=batch.hard_budget_micros,
            cancel_requested_at=batch.cancel_requested_at,
            queued_at=batch.queued_at,
            started_at=batch.started_at,
            finalized_at=batch.finalized_at,
        )

    @staticmethod
    def _item_view(item: GenerationItem) -> GenerationItemView:
        return GenerationItemView(
            item_id=item.id,
            batch_id=item.batch_id,
            job_id=item.job_id,
            request_reference=item.request_reference,
            ordinal=item.ordinal,
            requested_seed=item.requested_seed,
            reserved_budget_micros=item.reserved_budget_micros,
            status=item.status,
            result_code=item.result_code,
            started_at=item.started_at,
            finalized_at=item.finalized_at,
        )

    @classmethod
    def _result(
        cls, batch: GenerationBatch, items: tuple[GenerationItem, ...], *, created: bool
    ) -> GenerationBatchResult:
        return GenerationBatchResult(
            batch=cls._batch_view(batch),
            items=tuple(cls._item_view(item) for item in items),
            created=created,
        )

    async def _finalize_failed(
        self,
        session: AsyncSession,
        repo: GenerationRepository,
        batch: GenerationBatch,
        item: GenerationItem,
        job: Job,
        now: datetime,
        result_code: str,
    ) -> None:
        item.status = "GENERATION_FAILED"
        item.result_code = result_code
        item.finalized_at = now
        item.updated_at = now
        job.status = "failed"
        job.result_code = result_code
        job.finalized_at = now
        job.updated_at = now
        await session.flush()
        await self._finalize_batch_if_quiescent(repo, batch, now)

    @staticmethod
    async def _finalize_batch_if_quiescent(
        repo: GenerationRepository, batch: GenerationBatch, now: datetime
    ) -> None:
        items = await repo.items(batch.id, lock=True)
        if any(item.status in {"REQUESTED", "GENERATING"} for item in items):
            return
        raw_count = sum(item.status == "RAW_STORED" for item in items)
        failed_count = sum(item.status == "GENERATION_FAILED" for item in items)
        if raw_count == batch.item_count:
            batch.status = "COMPLETED"
        elif raw_count > 0:
            batch.status = "PARTIAL"
        elif batch.cancel_requested_at is not None:
            batch.status = "CANCELLED"
        elif failed_count == batch.item_count:
            batch.status = "FAILED"
        else:
            raise GenerationOperationRejected("generation_batch_outcome_inconsistent")
        batch.finalized_at = now
        batch.updated_at = now
