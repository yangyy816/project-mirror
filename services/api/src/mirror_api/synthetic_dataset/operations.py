"""Typed, fail-closed internal-operation contracts for P2 services.

This module deliberately owns neither persistence nor command-line parsing.  It gives a
future internal adapter one narrow way to carry an explicit operator, reason, correlation and
expected state to an already-accepted application service.  A missing backend is unavailable,
never a direct-SQL fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

from .domain import GenerationBatchState, GenerationItemState

_ID = re.compile(r"[0-9a-f]{32}\Z")
_CODE = re.compile(r"[a-z][a-z0-9_]{2,63}\Z")
_REFERENCE = re.compile(r"[a-z][a-z0-9._:-]{2,63}\Z")
_STATE = re.compile(r"[A-Z][A-Z0-9_]{2,63}\Z")

OperationEnvironment = Literal["development", "test", "ci", "production"]
_OPERATION_ENVIRONMENTS = frozenset({"development", "test", "ci", "production"})
_PROJECTION_TARGET_STATUSES = frozenset(
    state.value for state in (*GenerationBatchState, *GenerationItemState)
)
_RESULT_CODES = frozenset(
    {
        "dataset_operation_rejected",
        "operation_actor_invalid",
        "operation_backend_unavailable",
        "operation_completed",
        "operation_environment_invalid",
        "operation_execution_unavailable",
        "operation_expected_state_invalid",
        "operation_projection_amount_invalid",
        "operation_projection_count_invalid",
        "operation_projection_currency_missing",
        "operation_projection_status_invalid",
        "operation_production_disabled",
        "operation_reason_invalid",
        "operation_rejected",
        "operation_request_id_invalid",
        "operation_result_code_invalid",
        "operation_result_correlation_mismatch",
        "operation_result_kind_mismatch",
        "operation_result_projection_forbidden",
        "operation_result_projection_missing",
        "operation_result_request_id_invalid",
        "operation_result_target_invalid",
        "operation_target_invalid",
    }
)


class DatasetOperationKind(StrEnum):
    BATCH_STATUS = "batch_status"
    BATCH_CANCEL = "batch_cancel"
    PROVENANCE_STATUS = "provenance_status"
    QA_STATUS = "qa_status"
    COST_SUMMARY = "cost_summary"


class DatasetOperationOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class DatasetOperationRejected(Exception):
    """A safe, stable rejection that never includes operator-supplied values."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _RESULT_CODES else "dataset_operation_rejected"
        super().__init__("synthetic dataset operation was rejected")


@dataclass(frozen=True)
class DatasetOperationCommand:
    operation: DatasetOperationKind
    environment: OperationEnvironment
    target_id: str
    expected_target_state: str
    actor_reference: str
    reason_code: str
    request_id: str

    def __post_init__(self) -> None:
        if self.environment not in _OPERATION_ENVIRONMENTS:
            raise DatasetOperationRejected("operation_environment_invalid")
        if _ID.fullmatch(self.target_id) is None:
            raise DatasetOperationRejected("operation_target_invalid")
        if _STATE.fullmatch(self.expected_target_state) is None:
            raise DatasetOperationRejected("operation_expected_state_invalid")
        if _REFERENCE.fullmatch(self.actor_reference) is None:
            raise DatasetOperationRejected("operation_actor_invalid")
        if _CODE.fullmatch(self.reason_code) is None:
            raise DatasetOperationRejected("operation_reason_invalid")
        if _ID.fullmatch(self.request_id) is None:
            raise DatasetOperationRejected("operation_request_id_invalid")


@dataclass(frozen=True)
class DatasetOperationProjection:
    """The only values a future CLI may render without an additional projection policy."""

    target_status: str
    event_count: int = 0
    currency: Literal["CNY", "USD"] | None = None
    amount_micros: int | None = None

    def __post_init__(self) -> None:
        if self.target_status not in _PROJECTION_TARGET_STATUSES:
            raise DatasetOperationRejected("operation_projection_status_invalid")
        if self.event_count < 0:
            raise DatasetOperationRejected("operation_projection_count_invalid")
        if self.currency is None and self.amount_micros is not None:
            raise DatasetOperationRejected("operation_projection_currency_missing")
        if self.amount_micros is not None and self.amount_micros < 0:
            raise DatasetOperationRejected("operation_projection_amount_invalid")


@dataclass(frozen=True)
class DatasetOperationResult:
    operation: DatasetOperationKind
    outcome: DatasetOperationOutcome
    code: str
    target_id: str
    request_id: str
    projection: DatasetOperationProjection | None = None

    def __post_init__(self) -> None:
        if self.code not in _RESULT_CODES:
            raise DatasetOperationRejected("operation_result_code_invalid")
        if _ID.fullmatch(self.target_id) is None:
            raise DatasetOperationRejected("operation_result_target_invalid")
        if _ID.fullmatch(self.request_id) is None:
            raise DatasetOperationRejected("operation_result_request_id_invalid")
        if self.outcome is DatasetOperationOutcome.SUCCEEDED and self.projection is None:
            raise DatasetOperationRejected("operation_result_projection_missing")
        if self.outcome is not DatasetOperationOutcome.SUCCEEDED and self.projection is not None:
            raise DatasetOperationRejected("operation_result_projection_forbidden")
        if self.projection is not None:
            self.projection.__post_init__()

    @classmethod
    def rejected(cls, command: DatasetOperationCommand, code: str) -> DatasetOperationResult:
        return cls(
            operation=command.operation,
            outcome=DatasetOperationOutcome.REJECTED,
            code=code,
            target_id=command.target_id,
            request_id=command.request_id,
        )

    @classmethod
    def unavailable(cls, command: DatasetOperationCommand, code: str) -> DatasetOperationResult:
        return cls(
            operation=command.operation,
            outcome=DatasetOperationOutcome.UNAVAILABLE,
            code=code,
            target_id=command.target_id,
            request_id=command.request_id,
        )


class DatasetOperationBackend(Protocol):
    """A future application-service adapter; never a database or Provider port."""

    async def execute(self, command: DatasetOperationCommand) -> DatasetOperationResult: ...


class SyntheticDatasetOperationService:
    """Dispatch approved internal operations through registered application-service backends.

    Backends are deliberately optional at T02.  This prevents a CLI or an operator script from
    gaining authority before the relevant accepted service has an audit-safe implementation.
    """

    def __init__(
        self, *, backends: dict[DatasetOperationKind, DatasetOperationBackend] | None = None
    ) -> None:
        self._backends = dict(backends or {})

    async def execute(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        if command.environment == "production":
            return DatasetOperationResult.rejected(command, "operation_production_disabled")
        backend = self._backends.get(command.operation)
        if backend is None:
            return DatasetOperationResult.unavailable(command, "operation_backend_unavailable")
        try:
            result = await backend.execute(command)
        except DatasetOperationRejected as error:
            return DatasetOperationResult.rejected(command, error.code)
        except Exception:
            return DatasetOperationResult.unavailable(command, "operation_execution_unavailable")
        if result.operation is not command.operation:
            return DatasetOperationResult.rejected(command, "operation_result_kind_mismatch")
        if result.target_id != command.target_id or result.request_id != command.request_id:
            return DatasetOperationResult.rejected(command, "operation_result_correlation_mismatch")
        try:
            result.__post_init__()
        except DatasetOperationRejected as error:
            return DatasetOperationResult.rejected(command, error.code)
        return result
