"""PostgreSQL-backed P2-M7 backends for accepted batch and cost authorities.

Batch status/cancellation and read-only cost summary are wired here.  Provenance and QA remain
unavailable until their owning milestones expose accepted application services.
"""

from __future__ import annotations

import logging

from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.generation_types import GenerationOperationRejected
from mirror_api.synthetic_dataset.operations import (
    DatasetOperationCommand,
    DatasetOperationCostAggregate,
    DatasetOperationCostAvailability,
    DatasetOperationCostClassification,
    DatasetOperationCostSummary,
    DatasetOperationKind,
    DatasetOperationOutcome,
    DatasetOperationProjection,
    DatasetOperationRejected,
    DatasetOperationResult,
)
from mirror_api.synthetic_dataset.operations_projection import (
    CostClassification,
    CostProjectionCode,
    CostProjectionRejected,
    CostSummary,
    CostSummaryReadPort,
    DatasetOperationalEvent,
    emit_dataset_operational_event,
)


class GenerationBatchOperationBackend:
    """Adapter over the accepted batch service; it owns no SQL or Provider calls."""

    def __init__(self, *, generation_batches: GenerationBatchService) -> None:
        self._generation_batches = generation_batches

    async def execute(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        if command.operation is DatasetOperationKind.BATCH_STATUS:
            return await self._status(command)
        if command.operation is DatasetOperationKind.BATCH_CANCEL:
            return await self._cancel(command)
        raise DatasetOperationRejected("operation_backend_unavailable")

    async def _status(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        try:
            result = await self._generation_batches.get_batch(command.target_id)
        except GenerationOperationRejected as error:
            return _rejected(command, error.code)
        if result.batch.status != command.expected_target_state:
            return DatasetOperationResult.rejected(command, "operation_stale_expectation")
        return _succeeded(command, result.batch.status, len(result.items))

    async def _cancel(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        try:
            result = await self._generation_batches.request_cancel_with_expectation(
                batch_id=command.target_id,
                expected_status=command.expected_target_state,
                actor_reference=command.actor_reference,
                reason_code=command.reason_code,
                request_id=command.request_id,
            )
        except GenerationOperationRejected as error:
            return _rejected(command, error.code)
        return _succeeded(command, result.batch.status, len(result.items))


class CostSummaryOperationBackend:
    """Adapter over the accepted read model; it owns no SQL or monetary inference."""

    def __init__(self, *, costs: CostSummaryReadPort, logger: logging.Logger | None = None) -> None:
        self._costs = costs
        self._logger = logger or logging.getLogger("mirror.synthetic_dataset.cost_summary")

    async def execute(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        if command.operation is not DatasetOperationKind.COST_SUMMARY:
            raise DatasetOperationRejected("operation_backend_unavailable")
        try:
            summary = await self._costs.summarize_batch(command.target_id)
        except CostProjectionRejected as error:
            return _cost_rejected(command, error.code)
        if summary.batch_status != command.expected_target_state:
            return DatasetOperationResult.rejected(command, "operation_stale_expectation")
        event = DatasetOperationalEvent.from_summary(
            summary,
            request_id=command.request_id,
            actor_reference=command.actor_reference,
            reason_code=command.reason_code,
        )
        emit_dataset_operational_event(self._logger, event)
        return _cost_succeeded(command, summary)


def _succeeded(
    command: DatasetOperationCommand, status: str, event_count: int
) -> DatasetOperationResult:
    return DatasetOperationResult(
        operation=command.operation,
        outcome=DatasetOperationOutcome.SUCCEEDED,
        code="operation_completed",
        target_id=command.target_id,
        request_id=command.request_id,
        projection=DatasetOperationProjection(target_status=status, event_count=event_count),
    )


def _rejected(command: DatasetOperationCommand, source_code: str) -> DatasetOperationResult:
    codes = {
        "generation_batch_not_found": "operation_target_not_found",
        "generation_batch_request_conflict": "operation_rejected",
        "generation_batch_stale_expectation": "operation_stale_expectation",
        "generation_batch_not_cancellable": "operation_rejected",
    }
    return DatasetOperationResult.rejected(command, codes.get(source_code, "operation_rejected"))


def _cost_succeeded(
    command: DatasetOperationCommand, summary: CostSummary
) -> DatasetOperationResult:
    actual = tuple(
        DatasetOperationCostAggregate(
            classification=DatasetOperationCostClassification.ACTUAL,
            currency=item.currency,
            amount_micros=item.amount_micros,
            event_count=item.event_count,
        )
        for item in summary.actual
        if item.classification is CostClassification.ACTUAL
    )
    estimated = tuple(
        DatasetOperationCostAggregate(
            classification=DatasetOperationCostClassification.ESTIMATED,
            currency=item.currency,
            amount_micros=item.amount_micros,
            event_count=item.event_count,
        )
        for item in summary.estimated
        if item.classification is CostClassification.ESTIMATED
    )
    cost_summary = DatasetOperationCostSummary(
        availability=DatasetOperationCostAvailability(summary.availability.value),
        actual=actual,
        estimated=estimated,
        unavailable_item_count=summary.unavailable_item_count,
        pending_item_count=summary.pending_item_count,
        total_item_count=summary.total_item_count,
    )
    return DatasetOperationResult(
        operation=command.operation,
        outcome=DatasetOperationOutcome.SUCCEEDED,
        code="operation_completed",
        target_id=command.target_id,
        request_id=command.request_id,
        projection=DatasetOperationProjection(
            target_status=summary.batch_status,
            event_count=sum(item.event_count for item in (*actual, *estimated)),
            cost_summary=cost_summary,
        ),
    )


def _cost_rejected(
    command: DatasetOperationCommand, source_code: CostProjectionCode
) -> DatasetOperationResult:
    code = (
        "operation_target_not_found"
        if source_code is CostProjectionCode.BATCH_NOT_FOUND
        else "operation_rejected"
    )
    return DatasetOperationResult.rejected(command, code)
