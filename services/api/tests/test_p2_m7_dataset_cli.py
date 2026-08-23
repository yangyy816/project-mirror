from __future__ import annotations

import io
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

from mirror_api.scripts import mirror_dataset
from mirror_api.scripts.mirror_dataset import run
from mirror_api.synthetic_dataset.operations import (
    DatasetOperationCommand,
    DatasetOperationCostAggregate,
    DatasetOperationCostAvailability,
    DatasetOperationCostClassification,
    DatasetOperationCostSummary,
    DatasetOperationKind,
    DatasetOperationOutcome,
    DatasetOperationProjection,
    DatasetOperationResult,
    SyntheticDatasetOperationService,
)


def arguments(**overrides: str) -> list[str]:
    values = {
        "--operation": "batch_status",
        "--environment": "ci",
        "--target-id": "a" * 32,
        "--expected-state": "QUEUED",
        "--actor": "system.operator",
        "--reason": "operator_inspection",
        "--request-id": "b" * 32,
    }
    values.update(overrides)
    return [part for pair in values.items() for part in pair]


@dataclass
class Backend:
    result: DatasetOperationResult
    calls: int = 0

    async def execute(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        self.calls += 1
        return self.result


def result_for(command: DatasetOperationCommand) -> DatasetOperationResult:
    return DatasetOperationResult(
        operation=command.operation,
        outcome=DatasetOperationOutcome.SUCCEEDED,
        code="operation_completed",
        target_id=command.target_id,
        request_id=command.request_id,
        projection=DatasetOperationProjection(
            target_status="QUEUED", event_count=2, currency="CNY", amount_micros=10
        ),
    )


def test_dataset_cli_fails_closed_without_a_registered_backend() -> None:
    output = io.StringIO()

    exit_code = run(arguments(), output=output, environment_variables={})

    assert exit_code == 2
    assert json.loads(output.getvalue()) == {
        "code": "operation_backend_unavailable",
        "operation": "batch_status",
        "outcome": "unavailable",
        "request_id": "b" * 32,
        "target_id": "a" * 32,
    }


def test_dataset_cli_fails_closed_before_composition_when_database_environment_mismatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    @asynccontextmanager
    async def composition(database_url: str) -> AsyncIterator[SyntheticDatasetOperationService]:
        calls.append(database_url)
        yield SyntheticDatasetOperationService()

    monkeypatch.setattr(mirror_dataset, "compose_dataset_operation_service", composition)
    marker = "database-config-marker"
    output = io.StringIO()

    exit_code = run(
        arguments(),
        output=output,
        environment_variables={
            "MIRROR_DATASET_DATABASE_ENVIRONMENT": "test",
            "MIRROR_DATASET_DATABASE_URL": marker,
        },
    )

    assert exit_code == 2
    assert calls == []
    assert json.loads(output.getvalue()) == {
        "code": "operation_backend_unavailable",
        "operation": "batch_status",
        "outcome": "unavailable",
        "request_id": "b" * 32,
        "target_id": "a" * 32,
    }
    assert marker not in output.getvalue()


def test_dataset_cli_redacts_composition_failure_and_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = "database-config-marker"

    @asynccontextmanager
    async def composition(database_url: str) -> AsyncIterator[SyntheticDatasetOperationService]:
        assert database_url == marker
        raise RuntimeError(marker)
        yield SyntheticDatasetOperationService()  # pragma: no cover

    monkeypatch.setattr(mirror_dataset, "compose_dataset_operation_service", composition)
    output = io.StringIO()

    exit_code = run(
        arguments(),
        output=output,
        environment_variables={
            "MIRROR_DATASET_DATABASE_ENVIRONMENT": "ci",
            "MIRROR_DATASET_DATABASE_URL": marker,
        },
    )

    assert exit_code == 2
    assert json.loads(output.getvalue()) == {
        "code": "operation_execution_unavailable",
        "operation": "batch_status",
        "outcome": "unavailable",
        "request_id": "b" * 32,
        "target_id": "a" * 32,
    }
    assert marker not in output.getvalue()


def test_dataset_cli_passes_explicit_command_and_renders_only_allowlisted_values() -> None:
    command = DatasetOperationCommand(
        operation=DatasetOperationKind.BATCH_STATUS,
        environment="ci",
        target_id="a" * 32,
        expected_target_state="QUEUED",
        actor_reference="system.operator",
        reason_code="operator_inspection",
        request_id="b" * 32,
    )
    backend = Backend(result=result_for(command))
    service = SyntheticDatasetOperationService(
        backends={DatasetOperationKind.BATCH_STATUS: backend}
    )
    output = io.StringIO()

    exit_code = run(arguments(), service=service, output=output)

    assert exit_code == 0
    assert backend.calls == 1
    assert json.loads(output.getvalue()) == {
        "amount_micros": 10,
        "code": "operation_completed",
        "currency": "CNY",
        "event_count": 2,
        "operation": "batch_status",
        "outcome": "succeeded",
        "request_id": "b" * 32,
        "target_id": "a" * 32,
        "target_status": "QUEUED",
    }


def test_dataset_cli_renders_typed_cost_categories_with_a_fixed_allowlist() -> None:
    command = DatasetOperationCommand(
        operation=DatasetOperationKind.COST_SUMMARY,
        environment="ci",
        target_id="a" * 32,
        expected_target_state="RUNNING",
        actor_reference="system.operator",
        reason_code="operator_inspection",
        request_id="b" * 32,
    )
    cost_summary = DatasetOperationCostSummary(
        availability=DatasetOperationCostAvailability.MIXED,
        actual=(
            DatasetOperationCostAggregate(
                classification=DatasetOperationCostClassification.ACTUAL,
                currency="CNY",
                amount_micros=11,
                event_count=1,
            ),
        ),
        estimated=(
            DatasetOperationCostAggregate(
                classification=DatasetOperationCostClassification.ESTIMATED,
                currency="USD",
                amount_micros=7,
                event_count=1,
            ),
        ),
        unavailable_item_count=1,
        pending_item_count=2,
        total_item_count=3,
    )
    backend = Backend(
        result=DatasetOperationResult(
            operation=command.operation,
            outcome=DatasetOperationOutcome.SUCCEEDED,
            code="operation_completed",
            target_id=command.target_id,
            request_id=command.request_id,
            projection=DatasetOperationProjection(
                target_status="RUNNING",
                event_count=2,
                cost_summary=cost_summary,
            ),
        )
    )
    output = io.StringIO()

    exit_code = run(
        arguments(
            **{
                "--operation": "cost_summary",
                "--expected-state": "RUNNING",
            }
        ),
        service=SyntheticDatasetOperationService(
            backends={DatasetOperationKind.COST_SUMMARY: backend}
        ),
        output=output,
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {
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
                    "currency": "USD",
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
        "request_id": "b" * 32,
        "target_id": "a" * 32,
        "target_status": "RUNNING",
    }


def test_dataset_cli_never_echoes_invalid_or_unknown_argument_values() -> None:
    invalid_output = io.StringIO()
    invalid_exit_code = run(arguments(**{"--actor": "SECRET_OPERATOR"}), output=invalid_output)
    unknown_output = io.StringIO()
    unknown_exit_code = run(["--unknown", "SECRET_ARGUMENT"], output=unknown_output)

    assert invalid_exit_code == 2
    assert json.loads(invalid_output.getvalue()) == {
        "code": "dataset_cli_argument_invalid",
        "outcome": "rejected",
    }
    assert unknown_exit_code == 2
    assert json.loads(unknown_output.getvalue()) == {
        "code": "dataset_cli_argument_invalid",
        "outcome": "rejected",
    }
    assert "SECRET_OPERATOR" not in invalid_output.getvalue()
    assert "SECRET_ARGUMENT" not in unknown_output.getvalue()


def test_dataset_cli_rejects_production_before_backend_dispatch() -> None:
    command = DatasetOperationCommand(
        operation=DatasetOperationKind.BATCH_STATUS,
        environment="ci",
        target_id="a" * 32,
        expected_target_state="QUEUED",
        actor_reference="system.operator",
        reason_code="operator_inspection",
        request_id="b" * 32,
    )
    backend = Backend(result=result_for(command))
    output = io.StringIO()

    exit_code = run(
        arguments(**{"--environment": "production"}),
        service=SyntheticDatasetOperationService(
            backends={DatasetOperationKind.BATCH_STATUS: backend}
        ),
        output=output,
    )

    assert exit_code == 2
    assert backend.calls == 0
    assert json.loads(output.getvalue()) == {
        "code": "operation_production_disabled",
        "operation": "batch_status",
        "outcome": "rejected",
        "request_id": "b" * 32,
        "target_id": "a" * 32,
    }


def test_dataset_cli_rejects_production_before_real_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    @asynccontextmanager
    async def composition(database_url: str) -> AsyncIterator[SyntheticDatasetOperationService]:
        calls.append(database_url)
        yield SyntheticDatasetOperationService()

    monkeypatch.setattr(mirror_dataset, "compose_dataset_operation_service", composition)
    output = io.StringIO()

    exit_code = run(
        arguments(**{"--environment": "production"}),
        output=output,
        environment_variables={
            "MIRROR_DATASET_DATABASE_ENVIRONMENT": "production",
            "MIRROR_DATASET_DATABASE_URL": "database-config-marker",
        },
    )

    assert exit_code == 2
    assert calls == []
    assert json.loads(output.getvalue()) == {
        "code": "operation_production_disabled",
        "operation": "batch_status",
        "outcome": "rejected",
        "request_id": "b" * 32,
        "target_id": "a" * 32,
    }
