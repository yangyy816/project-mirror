from __future__ import annotations

import ast
import io
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from mirror_api.scripts.mirror_dataset import run
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.operations import (
    DatasetOperationCommand,
    DatasetOperationKind,
    DatasetOperationOutcome,
    DatasetOperationProjection,
    DatasetOperationResult,
    OperationEnvironment,
    SyntheticDatasetOperationService,
)
from mirror_api.synthetic_dataset.operations_integration import GenerationBatchOperationBackend

_ROOT = Path(__file__).resolve().parents[3]
_OPERATIONS = _ROOT / "services" / "api" / "src" / "mirror_api" / "synthetic_dataset"


def _command(kind: DatasetOperationKind, *, environment: str = "ci") -> DatasetOperationCommand:
    return DatasetOperationCommand(
        operation=kind,
        environment=cast(OperationEnvironment, environment),
        target_id="a" * 32,
        expected_target_state="QUEUED",
        actor_reference="system.operator",
        reason_code="independent_evaluation",
        request_id="b" * 32,
    )


@dataclass
class _TrapBackend:
    calls: int = 0

    async def execute(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        del command
        self.calls += 1
        raise AssertionError("production must reject before backend dispatch")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", tuple(DatasetOperationKind))
async def test_every_operation_kind_rejects_production_before_backend_dispatch(
    kind: DatasetOperationKind,
) -> None:
    backend = _TrapBackend()
    command = _command(kind, environment="production")

    result = await SyntheticDatasetOperationService(backends={kind: backend}).execute(command)

    assert result.outcome is DatasetOperationOutcome.REJECTED
    assert result.code == "operation_production_disabled"
    assert backend.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", tuple(DatasetOperationKind))
async def test_every_operation_kind_is_unavailable_without_an_accepted_backend(
    kind: DatasetOperationKind,
) -> None:
    command = _command(kind)

    result = await SyntheticDatasetOperationService().execute(command)

    assert result.outcome is DatasetOperationOutcome.UNAVAILABLE
    assert result.code == "operation_backend_unavailable"
    assert result.target_id == command.target_id
    assert result.request_id == command.request_id


@dataclass
class _BatchResult:
    status: str
    item_count: int

    @property
    def batch(self) -> SimpleNamespace:
        return SimpleNamespace(status=self.status)

    @property
    def items(self) -> tuple[object, ...]:
        return (object(),) * self.item_count


@dataclass
class _BatchServiceFake:
    status_calls: int = 0
    cancel_calls: int = 0

    async def get_batch(self, batch_id: str) -> _BatchResult:
        assert batch_id == "a" * 32
        self.status_calls += 1
        return _BatchResult(status="QUEUED", item_count=2)

    async def request_cancel_with_expectation(
        self,
        *,
        batch_id: str,
        expected_status: str,
        actor_reference: str,
        reason_code: str,
        request_id: str,
    ) -> _BatchResult:
        assert (batch_id, expected_status, actor_reference, reason_code, request_id) == (
            "a" * 32,
            "QUEUED",
            "system.operator",
            "independent_evaluation",
            "b" * 32,
        )
        self.cancel_calls += 1
        return _BatchResult(status="CANCELLED", item_count=2)


@pytest.mark.asyncio
async def test_batch_backend_only_exposes_accepted_batch_operations() -> None:
    fake = _BatchServiceFake()
    backend = GenerationBatchOperationBackend(generation_batches=cast(GenerationBatchService, fake))

    status = await backend.execute(_command(DatasetOperationKind.BATCH_STATUS))
    cancelled = await backend.execute(_command(DatasetOperationKind.BATCH_CANCEL))
    unavailable = await SyntheticDatasetOperationService(
        backends={DatasetOperationKind.PROVENANCE_STATUS: backend}
    ).execute(_command(DatasetOperationKind.PROVENANCE_STATUS))

    assert status.projection == DatasetOperationProjection(target_status="QUEUED", event_count=2)
    assert cancelled.projection == DatasetOperationProjection(
        target_status="CANCELLED", event_count=2
    )
    assert fake.status_calls == 1
    assert fake.cancel_calls == 1
    assert unavailable.outcome is DatasetOperationOutcome.REJECTED
    assert unavailable.code == "operation_backend_unavailable"


@dataclass
class _RenderingBackend:
    async def execute(self, command: DatasetOperationCommand) -> DatasetOperationResult:
        return DatasetOperationResult(
            operation=command.operation,
            outcome=DatasetOperationOutcome.SUCCEEDED,
            code="operation_completed",
            target_id=command.target_id,
            request_id=command.request_id,
            projection=DatasetOperationProjection(target_status="QUEUED", event_count=1),
        )


def test_cli_success_output_omits_operator_input_and_has_a_fixed_allowlist() -> None:
    output = io.StringIO()
    arguments = [
        "--operation",
        "batch_status",
        "--environment",
        "ci",
        "--target-id",
        "a" * 32,
        "--expected-state",
        "QUEUED",
        "--actor",
        "system.operator",
        "--reason",
        "independent_evaluation",
        "--request-id",
        "b" * 32,
    ]

    exit_code = run(
        arguments,
        service=SyntheticDatasetOperationService(
            backends={DatasetOperationKind.BATCH_STATUS: _RenderingBackend()}
        ),
        output=output,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert set(payload) == {
        "code",
        "event_count",
        "operation",
        "outcome",
        "request_id",
        "target_id",
        "target_status",
    }
    assert "system.operator" not in output.getvalue()
    assert "independent_evaluation" not in output.getvalue()
    assert "QUEUED" in output.getvalue()


def test_m7_modules_have_no_direct_network_database_provider_or_public_api_import() -> None:
    prohibited_roots = {"boto3", "celery", "fastapi", "httpx", "requests", "sqlalchemy", "urllib"}
    paths = (
        _OPERATIONS / "operations.py",
        _OPERATIONS / "operations_integration.py",
        _ROOT / "services" / "api" / "src" / "mirror_api" / "scripts" / "mirror_dataset.py",
    )

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".", maxsplit=1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not prohibited_roots.intersection(imported), path.name


def test_m7_is_absent_from_the_public_openapi_contract() -> None:
    contract = json.loads(
        (_ROOT / "packages" / "contracts" / "openapi.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(contract, sort_keys=True)

    assert "mirror-dataset" not in serialized
    assert "batch_cancel" not in serialized
    assert "cost_summary" not in serialized
