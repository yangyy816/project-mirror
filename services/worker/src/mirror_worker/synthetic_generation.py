from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from mirror_api.providers.base import (
    ImageGenerationProvider,
    SyntheticGenerationResult,
    SyntheticObjectStorageProvider,
    SyntheticStorageConflictError,
    SyntheticStorageWriteRequest,
    SyntheticStoredImage,
)
from mirror_api.storage_keys import synthetic_raw_storage_reference
from mirror_api.synthetic_dataset.generation_types import (
    GenerationExecutionContext,
    GenerationItemReservation,
    GenerationOperationRejected,
    GenerationTaskReference,
    ProviderCostInput,
)
from mirror_api.synthetic_dataset.prompt_material import EphemeralPrompt
from mirror_api.synthetic_dataset.raw_storage import SyntheticRawStorageService
from mirror_api.synthetic_dataset.task_contract import (
    SyntheticGenerationDispatcher,
    SyntheticGenerationTaskMessage,
)

from mirror_worker.ingestion import RetryableWorkerFailure


class SyntheticGenerationApplication(Protocol):
    async def reserve_item(
        self, *, item_id: str, job_id: str
    ) -> GenerationItemReservation | None: ...

    async def execution_context(
        self, reservation: GenerationItemReservation
    ) -> GenerationExecutionContext: ...

    async def materialize_prompt(
        self, *, item_id: str, attempt_id: str, lease_token: str
    ) -> EphemeralPrompt: ...

    async def post_cost(self, cost: ProviderCostInput) -> bool: ...

    async def record_raw_stored(
        self,
        *,
        item_id: str,
        attempt_id: str,
        result: SyntheticGenerationResult,
        stored: SyntheticStoredImage,
        retention_expires_at: datetime,
    ) -> bool: ...

    async def record_attempt_failure(
        self,
        *,
        item_id: str,
        attempt_id: str,
        result_code: str,
        retryable: bool,
    ) -> bool: ...

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[GenerationTaskReference, ...]: ...


@dataclass(frozen=True)
class SyntheticGenerationExecutionResult:
    item_id: str
    job_id: str
    status: str


class SyntheticGenerationTaskExecutor:
    """Celery-independent at-least-once coordinator for one reference-only item task."""

    def __init__(
        self,
        *,
        application: SyntheticGenerationApplication,
        provider: ImageGenerationProvider,
        storage: SyntheticObjectStorageProvider,
        raw_storage: SyntheticRawStorageService,
        raw_retention_seconds: int = 86_400,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not 60 <= raw_retention_seconds <= 7 * 86_400:
            raise ValueError("synthetic raw retention is outside the boundary")
        self._application = application
        self._provider = provider
        self._storage = storage
        self._raw_storage = raw_storage
        self._raw_retention_seconds = raw_retention_seconds
        self._now = now or (lambda: datetime.now(UTC))

    async def execute(
        self, message: SyntheticGenerationTaskMessage
    ) -> SyntheticGenerationExecutionResult:
        message.validate()
        reservation = await self._application.reserve_item(
            item_id=message.item_id, job_id=message.job_id
        )
        if reservation is None:
            return SyntheticGenerationExecutionResult(
                item_id=message.item_id, job_id=message.job_id, status="no_op"
            )
        try:
            context = await self._application.execution_context(reservation)
            prompt = await self._application.materialize_prompt(
                item_id=reservation.item_id,
                attempt_id=reservation.attempt_id,
                lease_token=reservation.lease_token,
            )
        except GenerationOperationRejected:
            await self._fail(reservation, code="generation_context_unavailable", retryable=False)
            return self._result(reservation, "generation_failed")

        try:
            generated = await self._provider.generate_synthetic(
                request=context.request,
                prompt=prompt,
            )
        except NotImplementedError:
            await self._fail(reservation, code="provider_not_verified", retryable=False)
            return self._result(reservation, "generation_failed")
        except Exception:
            await self._fail(reservation, code="provider_unavailable", retryable=True)
            raise RetryableWorkerFailure(
                "synthetic generation provider remains retryable"
            ) from None

        validation_code = self._validate_generated_result(context, generated)
        if validation_code is not None:
            await self._fail(reservation, code=validation_code, retryable=False)
            return self._result(reservation, "generation_failed")

        try:
            await self._application.post_cost(
                ProviderCostInput(
                    item_id=reservation.item_id,
                    job_attempt_id=reservation.attempt_id,
                    event_kind=generated.cost.status,
                    currency=generated.cost.currency,
                    amount_micros=generated.cost.amount_micros,
                    pricing_snapshot_reference=context.request.budget.pricing_snapshot_reference,
                    occurred_at=self._now(),
                )
            )
        except GenerationOperationRejected as exc:
            retryable = exc.code == "provider_cost_rejected"
            await self._fail(reservation, code=exc.code, retryable=retryable)
            if retryable:
                raise RetryableWorkerFailure(
                    "synthetic generation cost persistence remains retryable"
                ) from None
            return self._result(reservation, "generation_failed")

        if generated.safety.outcome != "passed":
            await self._fail(reservation, code="provider_safety_rejected", retryable=False)
            return self._result(reservation, "generation_failed")

        storage_reference = synthetic_raw_storage_reference(
            reservation.item_id, reservation.attempt_id
        )
        try:
            stored = await self._storage.store_generated_image_if_absent(
                request=self._storage_request(storage_reference, generated)
            )
        except SyntheticStorageConflictError:
            await self._fail(reservation, code="raw_storage_conflict", retryable=False)
            return self._result(reservation, "generation_failed")
        except Exception:
            await self._fail(reservation, code="raw_storage_unavailable", retryable=True)
            await self._cleanup_orphan(reservation, storage_reference)
            raise RetryableWorkerFailure("synthetic raw storage remains retryable") from None

        try:
            await self._application.record_raw_stored(
                item_id=reservation.item_id,
                attempt_id=reservation.attempt_id,
                result=generated,
                stored=stored,
                retention_expires_at=self._now() + timedelta(seconds=self._raw_retention_seconds),
            )
        except GenerationOperationRejected as exc:
            retryable = exc.code == "raw_stored_rejected"
            await self._fail(
                reservation,
                code="database_write_failed" if retryable else exc.code,
                retryable=retryable,
            )
            await self._cleanup_orphan(reservation, storage_reference)
            if retryable:
                raise RetryableWorkerFailure(
                    "synthetic generation persistence remains retryable"
                ) from None
            return self._result(reservation, "generation_failed")
        return self._result(reservation, "raw_stored")

    async def _fail(
        self,
        reservation: GenerationItemReservation,
        *,
        code: str,
        retryable: bool,
    ) -> None:
        try:
            await self._application.record_attempt_failure(
                item_id=reservation.item_id,
                attempt_id=reservation.attempt_id,
                result_code=code,
                retryable=retryable,
            )
        except GenerationOperationRejected:
            return

    async def _cleanup_orphan(
        self, reservation: GenerationItemReservation, storage_reference: str
    ) -> None:
        try:
            await self._raw_storage.delete_failed_attempt_orphan(
                item_id=reservation.item_id,
                attempt_id=reservation.attempt_id,
                storage_reference=storage_reference,
            )
        except GenerationOperationRejected:
            return

    @staticmethod
    def _validate_generated_result(
        context: GenerationExecutionContext,
        generated: SyntheticGenerationResult,
    ) -> str | None:
        output = context.request.output_specification
        if generated.request_reference != context.request.request_reference:
            return "generation_result_mismatch"
        if generated.cost.currency != context.request.budget.currency:
            return "provider_cost_mismatch"
        if generated.cost.amount_micros > context.request.budget.max_amount_micros:
            return "provider_cost_exceeds_budget"
        if (
            generated.payload.media_type != output.media_type
            or generated.payload.byte_size > output.max_byte_size
        ):
            return "generation_output_mismatch"
        return None

    @staticmethod
    def _storage_request(
        storage_reference: str, generated: SyntheticGenerationResult
    ) -> SyntheticStorageWriteRequest:
        return SyntheticStorageWriteRequest(
            storage_reference=storage_reference,
            payload=generated.payload,
            provenance=generated.provenance,
        )

    @staticmethod
    def _result(
        reservation: GenerationItemReservation, status: str
    ) -> SyntheticGenerationExecutionResult:
        return SyntheticGenerationExecutionResult(
            item_id=reservation.item_id,
            job_id=reservation.job_id,
            status=status,
        )


class SyntheticGenerationReconciler:
    def __init__(
        self,
        *,
        application: SyntheticGenerationApplication,
        dispatcher: SyntheticGenerationDispatcher,
    ) -> None:
        self._application = application
        self._dispatcher = dispatcher

    async def execute(self, *, limit: int = 100) -> tuple[str, ...]:
        candidates = await self._application.reconciliation_candidates(limit=limit)
        dispatched: list[str] = []
        for candidate in candidates:
            message = SyntheticGenerationTaskMessage(
                item_id=candidate.item_id,
                job_id=candidate.job_id,
                request_id=candidate.request_id,
            )
            self._dispatcher.dispatch_synthetic_generation(message)
            dispatched.append(candidate.item_id)
        return tuple(dispatched)
