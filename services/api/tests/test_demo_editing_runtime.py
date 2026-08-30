"""Unit boundaries for the D07 runtime core.

PostgreSQL publication invariants remain covered by the repository integration
suite; these tests pin the runtime's non-negotiable message/capability
boundaries without materializing private image bytes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_editing_asset_loader import DemoAssetByteLoader
from mirror_api.demo_editing_runtime import DemoEditingRuntime, DemoEditingRuntimeError
from mirror_api.demo_editing_storage import DemoLocalPrivateObjectStorage
from mirror_api.demo_editing_task_contract import DemoEditingTaskMessage
from mirror_api.demo_models import DemoEditOperation, DemoJobBinding
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
)
from mirror_api.models import Job


def _runtime(*, lease_seconds: int = 120, max_attempts: int = 3) -> DemoEditingRuntime:
    return DemoEditingRuntime(
        session_factory=cast(async_sessionmaker[AsyncSession], object()),
        asset_loader=cast(DemoAssetByteLoader, object()),
        storage=cast(DemoLocalPrivateObjectStorage, object()),
        lease_seconds=lease_seconds,
        max_attempts=max_attempts,
    )


def test_runtime_rejects_unbounded_retry_configuration() -> None:
    with pytest.raises(ValueError, match="lease and retry"):
        _runtime(lease_seconds=0)
    with pytest.raises(ValueError, match="lease and retry"):
        _runtime(max_attempts=11)


def test_runtime_parses_only_the_persisted_canonical_operation() -> None:
    spec = OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=OperationType.EXPOSURE,
        parameters={"exposure_ev_milli": 100},
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME,),
        expected_effect={
            "effect_type": "EXPOSURE",
            "target_region": "FULL_IMAGE",
            "exposure_ev_milli": 100,
        },
    )
    row = SimpleNamespace(
        engine=spec.engine.value,
        operation_type=spec.operation_type.value,
        parameters=dict(spec.parameters),
        preserve=[item.value for item in spec.preserve],
        expected_effect=dict(spec.expected_effect),
    )
    assert DemoEditingRuntime._operation_spec(cast(DemoEditOperation, row)) == spec


def test_runtime_refuses_message_binding_request_or_operation_mismatch() -> None:
    message = DemoEditingTaskMessage(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        operation="edit_plan.execute",
        request_id="request-01",
    )
    job = SimpleNamespace(
        id="b" * 32,
        request_id="different",
        job_type="demo_p3_p7.edit_plan.execute",
    )
    binding = SimpleNamespace(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        endpoint_operation="edit_plan.execute",
    )
    with pytest.raises(DemoEditingRuntimeError, match="task message") as error:
        DemoEditingRuntime._validate_message_binding(
            cast(Job, job), cast(DemoJobBinding, binding), message
        )
    assert error.value.code == "TASK_BINDING_MISMATCH"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("GEOMETRY_CAPABILITY_UNAVAILABLE", "REJECTED"),
        ("VERIFIER_CAPABILITY_UNAVAILABLE", "REJECTED"),
        ("SOURCE_DIGEST_MISMATCH", "FAILED"),
    ],
)
def test_runtime_capability_and_integrity_failures_have_distinct_terminal_semantics(
    code: str, status: str
) -> None:
    assert DemoEditingRuntime._terminal_for(code) == status
