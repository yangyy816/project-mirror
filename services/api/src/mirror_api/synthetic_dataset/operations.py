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
_PROJECTION_CURRENCIES = frozenset({"CNY", "USD"})
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
        "operation_projection_currency_invalid",
        "operation_projection_currency_missing",
        "operation_projection_status_invalid",
        "operation_production_disabled",
        "operation_reason_invalid",
        "operation_rejected",
        "operation_request_id_invalid",
        "operation_result_code_invalid",
        "operation_result_correlation_mismatch",
        "operation_result_invalid",
        "operation_result_kind_mismatch",
        "operation_result_outcome_invalid",
        "operation_result_projection_forbidden",
        "operation_result_projection_missing",
        "operation_result_request_id_invalid",
        "operation_result_target_invalid",
        "operation_target_invalid",
        "operation_target_not_found",
        "operation_stale_expectation",
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
        _validate_projection(self)


@dataclass(frozen=True)
class DatasetOperationResult:
    operation: DatasetOperationKind
    outcome: DatasetOperationOutcome
    code: str
    target_id: str
    request_id: str
    projection: DatasetOperationProjection | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not str or self.code not in _RESULT_CODES:
            raise DatasetOperationRejected("operation_result_code_invalid")
        if type(self.target_id) is not str or _ID.fullmatch(self.target_id) is None:
            raise DatasetOperationRejected("operation_result_target_invalid")
        if type(self.request_id) is not str or _ID.fullmatch(self.request_id) is None:
            raise DatasetOperationRejected("operation_result_request_id_invalid")
        if not isinstance(self.operation, DatasetOperationKind):
            raise DatasetOperationRejected("operation_result_kind_mismatch")
        if not isinstance(self.outcome, DatasetOperationOutcome):
            raise DatasetOperationRejected("operation_result_outcome_invalid")
        if self.outcome is DatasetOperationOutcome.SUCCEEDED and self.projection is None:
            raise DatasetOperationRejected("operation_result_projection_missing")
        if self.outcome is not DatasetOperationOutcome.SUCCEEDED and self.projection is not None:
            raise DatasetOperationRejected("operation_result_projection_forbidden")
        if self.projection is not None:
            _validate_projection(self.projection)

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


def _validate_projection(projection: DatasetOperationProjection) -> None:
    if type(projection) is not DatasetOperationProjection:
        raise DatasetOperationRejected("operation_result_invalid")
    if (
        type(projection.target_status) is not str
        or projection.target_status not in _PROJECTION_TARGET_STATUSES
    ):
        raise DatasetOperationRejected("operation_projection_status_invalid")
    if type(projection.event_count) is not int or projection.event_count < 0:
        raise DatasetOperationRejected("operation_projection_count_invalid")
    if projection.currency is not None and (
        type(projection.currency) is not str or projection.currency not in _PROJECTION_CURRENCIES
    ):
        raise DatasetOperationRejected("operation_projection_currency_invalid")
    if projection.currency is None and projection.amount_micros is not None:
        raise DatasetOperationRejected("operation_projection_currency_missing")
    if projection.amount_micros is not None and (
        type(projection.amount_micros) is not int or projection.amount_micros < 0
    ):
        raise DatasetOperationRejected("operation_projection_amount_invalid")


def _canonicalize_backend_result(result: DatasetOperationResult) -> DatasetOperationResult:
    try:
        return DatasetOperationResult(
            operation=result.operation,
            outcome=result.outcome,
            code=result.code,
            target_id=result.target_id,
            request_id=result.request_id,
            projection=result.projection,
        )
    except DatasetOperationRejected:
        raise
    except Exception:
        raise DatasetOperationRejected("operation_result_invalid") from None


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
        try:
            canonical_result = _canonicalize_backend_result(result)
        except DatasetOperationRejected as error:
            return DatasetOperationResult.rejected(command, error.code)
        if canonical_result.operation is not command.operation:
            return DatasetOperationResult.rejected(command, "operation_result_kind_mismatch")
        if (
            canonical_result.target_id != command.target_id
            or canonical_result.request_id != command.request_id
        ):
            return DatasetOperationResult.rejected(command, "operation_result_correlation_mismatch")
        return canonical_result
