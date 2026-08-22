from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import cast

import pytest

from mirror_api.synthetic_dataset.operations import (
    DatasetOperationCommand,
    DatasetOperationKind,
    DatasetOperationOutcome,
    DatasetOperationProjection,
    DatasetOperationRejected,
    DatasetOperationResult,
    OperationEnvironment,
    SyntheticDatasetOperationService,
)


def command(**overrides: object) -> DatasetOperationCommand:
    values: dict[str, object] = {
        "operation": DatasetOperationKind.BATCH_STATUS,
        "environment": "ci",
        "target_id": "a" * 32,
        "expected_target_state": "QUEUED",
        "actor_reference": "system.operator",
        "reason_code": "operator_inspection",
        "request_id": "b" * 32,
    }
    values.update(overrides)
    return DatasetOperationCommand(**values)  # type: ignore[arg-type]


@dataclass
class Backend:
    result: DatasetOperationResult | None = None
    error: Exception | None = None
    calls: int = 0

    async def execute(self, value: DatasetOperationCommand) -> DatasetOperationResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@pytest.mark.asyncio
async def test_operation_contract_dispatches_a_redacted_success() -> None:
    value = command()
    backend = Backend(
        result=DatasetOperationResult(
            operation=value.operation,
            outcome=DatasetOperationOutcome.SUCCEEDED,
            code="operation_completed",
            target_id=value.target_id,
            request_id=value.request_id,
            projection=DatasetOperationProjection(target_status="QUEUED", event_count=2),
        )
    )
    result = await SyntheticDatasetOperationService(
        backends={DatasetOperationKind.BATCH_STATUS: backend}
    ).execute(value)
    assert result.outcome is DatasetOperationOutcome.SUCCEEDED
    assert result.projection == DatasetOperationProjection(target_status="QUEUED", event_count=2)
    assert backend.calls == 1


@pytest.mark.asyncio
async def test_operation_contract_fails_closed_for_production_before_backend() -> None:
    value = command(environment="production")
    backend = Backend()
    result = await SyntheticDatasetOperationService(
        backends={DatasetOperationKind.BATCH_STATUS: backend}
    ).execute(value)
    assert result.outcome is DatasetOperationOutcome.REJECTED
    assert result.code == "operation_production_disabled"
    assert backend.calls == 0


@pytest.mark.asyncio
async def test_operation_contract_fails_closed_for_missing_backend() -> None:
    result = await SyntheticDatasetOperationService().execute(command())
    assert result.outcome is DatasetOperationOutcome.UNAVAILABLE
    assert result.code == "operation_backend_unavailable"


@pytest.mark.asyncio
async def test_operation_contract_redacts_backend_failure_and_mismatch() -> None:
    value = command()
    failure = await SyntheticDatasetOperationService(
        backends={DatasetOperationKind.BATCH_STATUS: Backend(error=RuntimeError("secret-value"))}
    ).execute(value)
    assert failure.outcome is DatasetOperationOutcome.UNAVAILABLE
    assert failure.code == "operation_execution_unavailable"
    assert "secret-value" not in str(failure)

    rejected = await SyntheticDatasetOperationService(
        backends={
            DatasetOperationKind.BATCH_STATUS: Backend(
                error=DatasetOperationRejected("secret_like_backend_code")
            )
        }
    ).execute(value)
    assert rejected.code == "dataset_operation_rejected"
    assert "secret_like_backend_code" not in str(rejected)

    mismatch = DatasetOperationResult.rejected(
        command(operation=DatasetOperationKind.QA_STATUS), "operation_rejected"
    )
    result = await SyntheticDatasetOperationService(
        backends={DatasetOperationKind.BATCH_STATUS: Backend(result=mismatch)}
    ).execute(value)
    assert result.outcome is DatasetOperationOutcome.REJECTED
    assert result.code == "operation_result_kind_mismatch"


@pytest.mark.parametrize(
    ("field", "invalid", "code"),
    [
        ("target_id", "not-an-id", "operation_target_invalid"),
        ("expected_target_state", "queued", "operation_expected_state_invalid"),
        ("actor_reference", "x", "operation_actor_invalid"),
        ("reason_code", "BAD", "operation_reason_invalid"),
        ("request_id", "short", "operation_request_id_invalid"),
        ("request_id", "prompt_like_token_123456", "operation_request_id_invalid"),
    ],
)
def test_operation_contract_rejects_invalid_inputs_without_echoing_them(
    field: str, invalid: str, code: str
) -> None:
    with pytest.raises(DatasetOperationRejected) as raised:
        command(**{field: invalid})
    assert raised.value.code == code
    assert invalid not in str(raised.value)


def test_operation_contract_rejects_unknown_environment_without_echoing_it() -> None:
    invalid = "staging-secret"
    with pytest.raises(DatasetOperationRejected) as raised:
        command(environment=cast(OperationEnvironment, invalid))
    assert raised.value.code == "operation_environment_invalid"
    assert invalid not in str(raised.value)


def test_operation_contract_rejects_nonopaque_result_correlation_without_echoing_it() -> None:
    unsafe_request_id = "secret_like_result_token"
    with pytest.raises(DatasetOperationRejected) as raised:
        DatasetOperationResult(
            operation=DatasetOperationKind.BATCH_STATUS,
            outcome=DatasetOperationOutcome.REJECTED,
            code="operation_rejected",
            target_id="a" * 32,
            request_id=unsafe_request_id,
        )
    assert raised.value.code == "operation_result_request_id_invalid"
    assert unsafe_request_id not in str(raised.value)


def test_operation_contract_rejects_nonallowlisted_result_code_without_echoing_it() -> None:
    unsafe_code = "secret_like_result_code"
    with pytest.raises(DatasetOperationRejected) as raised:
        DatasetOperationResult(
            operation=DatasetOperationKind.BATCH_STATUS,
            outcome=DatasetOperationOutcome.REJECTED,
            code=unsafe_code,
            target_id="a" * 32,
            request_id="b" * 32,
        )
    assert raised.value.code == "operation_result_code_invalid"
    assert unsafe_code not in str(raised.value)


def test_operation_contract_has_no_database_or_provider_import_boundary() -> None:
    source = inspect.getsource(SyntheticDatasetOperationService)
    module_source = inspect.getsource(inspect.getmodule(SyntheticDatasetOperationService))
    assert "sqlalchemy" not in module_source
    assert "providers" not in module_source
    assert "session" not in source
