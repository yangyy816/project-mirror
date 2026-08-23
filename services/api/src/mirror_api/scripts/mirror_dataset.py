"""Fail-closed internal CLI adapter for accepted synthetic-dataset operations.

The adapter contains no SQL, HTTP, storage, Provider, or task-runner access.  In non-production it
may ask the dedicated composition boundary to register already accepted application services using
one explicit task-scoped PostgreSQL environment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from typing import NoReturn, TextIO, cast

from mirror_api.synthetic_dataset.operations import (
    DatasetOperationCommand,
    DatasetOperationKind,
    DatasetOperationProjection,
    DatasetOperationRejected,
    DatasetOperationResult,
    OperationEnvironment,
    SyntheticDatasetOperationService,
)
from mirror_api.synthetic_dataset.operations_composition import compose_dataset_operation_service

_CLI_ARGUMENT_INVALID = "dataset_cli_argument_invalid"
_CLI_RESULT_INVALID = "dataset_cli_result_invalid"
_DATABASE_ENVIRONMENT_VARIABLE = "MIRROR_DATASET_DATABASE_ENVIRONMENT"
_DATABASE_URL_VARIABLE = "MIRROR_DATASET_DATABASE_URL"


class DatasetCliArgumentError(ValueError):
    """A parser rejection that intentionally has no user-controlled detail."""


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise DatasetCliArgumentError()


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(
        description="Internal dataset adapter. Output is redacted; production is disabled."
    )
    parser.add_argument(
        "--operation", required=True, choices=tuple(kind.value for kind in DatasetOperationKind)
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("development", "test", "ci", "production"),
        help="explicit execution environment; production is always rejected",
    )
    parser.add_argument(
        "--target-id", required=True, help="opaque 32-character target authority identifier"
    )
    parser.add_argument("--expected-state", required=True, help="expected immutable target state")
    parser.add_argument("--actor", required=True, help="opaque operator reference")
    parser.add_argument("--reason", required=True, help="allowlisted operator reason code")
    parser.add_argument(
        "--request-id", required=True, help="opaque 32-character request correlation identifier"
    )
    return parser


def _write_payload(payload: dict[str, object], *, output: TextIO) -> None:
    output.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _write_rejection(code: str, *, output: TextIO) -> None:
    _write_payload({"code": code, "outcome": "rejected"}, output=output)


def _canonicalize_result(result: DatasetOperationResult) -> DatasetOperationResult:
    """Defend the rendering boundary even when a test-only service is substituted."""

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


def render_result(result: DatasetOperationResult, *, output: TextIO) -> None:
    canonical_result = _canonicalize_result(result)
    payload: dict[str, object] = {
        "code": canonical_result.code,
        "operation": canonical_result.operation.value,
        "outcome": canonical_result.outcome.value,
        "request_id": canonical_result.request_id,
        "target_id": canonical_result.target_id,
    }
    projection = canonical_result.projection
    if projection is not None:
        _add_projection(payload, projection=projection)
    _write_payload(payload, output=output)


def _add_projection(payload: dict[str, object], *, projection: DatasetOperationProjection) -> None:
    payload["event_count"] = projection.event_count
    payload["target_status"] = projection.target_status
    if projection.currency is not None:
        payload["currency"] = projection.currency
        if projection.amount_micros is not None:
            payload["amount_micros"] = projection.amount_micros
    if projection.cost_summary is not None:
        payload["cost_summary"] = {
            "actual": [
                {
                    "amount_micros": item.amount_micros,
                    "classification": item.classification.value,
                    "currency": item.currency,
                    "event_count": item.event_count,
                }
                for item in projection.cost_summary.actual
            ],
            "availability": projection.cost_summary.availability.value,
            "estimated": [
                {
                    "amount_micros": item.amount_micros,
                    "classification": item.classification.value,
                    "currency": item.currency,
                    "event_count": item.event_count,
                }
                for item in projection.cost_summary.estimated
            ],
            "pending_item_count": projection.cost_summary.pending_item_count,
            "total_item_count": projection.cost_summary.total_item_count,
            "unavailable_item_count": projection.cost_summary.unavailable_item_count,
        }


def _command_from_args(args: argparse.Namespace) -> DatasetOperationCommand:
    return DatasetOperationCommand(
        operation=DatasetOperationKind(args.operation),
        environment=cast(OperationEnvironment, args.environment),
        target_id=args.target_id,
        expected_target_state=args.expected_state,
        actor_reference=args.actor,
        reason_code=args.reason,
        request_id=args.request_id,
    )


def _database_url_for(
    command: DatasetOperationCommand, environment_variables: Mapping[str, str]
) -> str:
    configured_environment = environment_variables.get(_DATABASE_ENVIRONMENT_VARIABLE)
    database_url = environment_variables.get(_DATABASE_URL_VARIABLE)
    if configured_environment != command.environment or not database_url:
        raise DatasetOperationRejected("operation_backend_unavailable")
    return database_url


async def _execute_command(
    command: DatasetOperationCommand,
    *,
    service: SyntheticDatasetOperationService | None,
    environment_variables: Mapping[str, str],
) -> DatasetOperationResult:
    if service is not None:
        return await service.execute(command)
    if command.environment == "production":
        return await SyntheticDatasetOperationService().execute(command)
    try:
        database_url = _database_url_for(command, environment_variables)
        async with compose_dataset_operation_service(database_url) as composed_service:
            return await composed_service.execute(command)
    except DatasetOperationRejected as error:
        return DatasetOperationResult.unavailable(command, error.code)
    except Exception:
        return DatasetOperationResult.unavailable(command, "operation_execution_unavailable")


def run(
    argv: Sequence[str] | None = None,
    *,
    service: SyntheticDatasetOperationService | None = None,
    output: TextIO | None = None,
    environment_variables: Mapping[str, str] | None = None,
) -> int:
    """Run one internal operation without acquiring any additional authority."""

    stream = output or sys.stdout
    try:
        args = build_parser().parse_args(argv)
        command = _command_from_args(args)
    except (DatasetCliArgumentError, DatasetOperationRejected):
        _write_rejection(_CLI_ARGUMENT_INVALID, output=stream)
        return 2

    try:
        result = asyncio.run(
            _execute_command(
                command,
                service=service,
                environment_variables=(
                    environment_variables if environment_variables is not None else os.environ
                ),
            )
        )
        render_result(result, output=stream)
    except DatasetOperationRejected as error:
        _write_rejection(error.code, output=stream)
        return 2
    except Exception:
        _write_rejection(_CLI_RESULT_INVALID, output=stream)
        return 2
    return 0 if result.outcome.value == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(run())
