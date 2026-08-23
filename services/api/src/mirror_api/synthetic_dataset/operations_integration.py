"""PostgreSQL-backed P2-M7 operation backends for accepted batch authority.

Only batch status and cancellation are wired here.  Other T02 operation kinds remain
unavailable until their owning milestones expose an accepted application service.
"""

from __future__ import annotations

from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.generation_types import GenerationOperationRejected
from mirror_api.synthetic_dataset.operations import (
    DatasetOperationCommand,
    DatasetOperationKind,
    DatasetOperationOutcome,
    DatasetOperationProjection,
    DatasetOperationRejected,
    DatasetOperationResult,
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
