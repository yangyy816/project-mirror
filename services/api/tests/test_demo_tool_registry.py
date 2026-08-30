"""D08 typed tool-registry authority tests."""

from __future__ import annotations

import re

import pytest

from mirror_api.demo_operation_graph import CapabilityState, OperationEngine, OperationType
from mirror_api.demo_raster_editor import RASTER_ALGORITHM_VERSION
from mirror_api.demo_tool_registry import (
    GEOMETRY_ENGINE_VERSION,
    RASTER_ENGINE_VERSION,
    TOOL_REGISTRY_SCHEMA_VERSION,
    TOOL_REGISTRY_VERSION,
    DemoToolRegistryError,
    registered_tools,
    registry_digest,
    registry_payload,
    require_execution_mode,
    resolve_persisted_tool,
    resolve_tool,
)


def test_registry_is_complete_canonical_and_replayable() -> None:
    tools = registered_tools()
    assert tuple(item.operation_type.value for item in tools) == tuple(
        sorted(item.value for item in OperationType)
    )
    assert {item.operation_type for item in tools} == set(OperationType)
    assert len({item.tool_name for item in tools}) == len(OperationType)
    assert registry_payload() == {
        "schema_version": TOOL_REGISTRY_SCHEMA_VERSION,
        "tool_registry_version": TOOL_REGISTRY_VERSION,
        "tools": [item.canonical_payload() for item in tools],
    }
    assert re.fullmatch(r"[0-9a-f]{64}", registry_digest())
    assert registry_digest() == registry_digest()


@pytest.mark.parametrize(
    "operation",
    [
        OperationType.CROP,
        OperationType.ROTATE,
        OperationType.EXPOSURE,
        OperationType.CONTRAST,
        OperationType.SATURATION,
        OperationType.TEMPERATURE,
        OperationType.RESTORE,
        OperationType.ROLLBACK,
    ],
)
def test_raster_tools_share_one_registered_engine(operation: OperationType) -> None:
    descriptor = resolve_tool(OperationEngine.RASTER, operation)
    assert descriptor.execution_mode == "DETERMINISTIC_RASTER"
    assert descriptor.capability_state is CapabilityState.AVAILABLE
    assert descriptor.engine_version == RASTER_ENGINE_VERSION
    assert descriptor.engine_version == RASTER_ALGORITHM_VERSION
    assert descriptor.unavailable_reason_code is None
    assert descriptor.verifier_required is True


def test_geometry_is_registered_but_runtime_gated() -> None:
    descriptor = resolve_tool(OperationEngine.GEOMETRY, OperationType.GEOMETRY)
    assert descriptor.execution_mode == "GEOMETRY"
    assert descriptor.capability_state is CapabilityState.CAPABILITY_GATED
    assert descriptor.engine_version == GEOMETRY_ENGINE_VERSION
    assert descriptor.unavailable_reason_code is None
    assert descriptor.verifier_required is True


@pytest.mark.parametrize(
    ("engine", "operation", "mode", "state", "reason"),
    [
        (
            OperationEngine.MAKEUP,
            OperationType.MAKEUP,
            "MAKEUP",
            CapabilityState.DEFERRED_WITH_EXPLICIT_REASON,
            "MAKEUP_DEFERRED_NO_APPROVED_ENGINE",
        ),
        (
            OperationEngine.GENERATIVE,
            OperationType.GENERATIVE,
            "GENERATIVE",
            CapabilityState.CAPABILITY_UNAVAILABLE,
            "GENERATIVE_PROVIDER_UNAVAILABLE",
        ),
    ],
)
def test_unavailable_tools_are_typed_but_never_executable(
    engine: OperationEngine,
    operation: OperationType,
    mode: str,
    state: CapabilityState,
    reason: str,
) -> None:
    descriptor = resolve_tool(engine, operation)
    assert descriptor.execution_mode == mode
    assert descriptor.capability_state is state
    assert descriptor.engine_version is None
    assert descriptor.unavailable_reason_code == reason
    assert descriptor.verifier_required is False


def test_registry_rejects_crossed_or_malformed_tool_identity() -> None:
    with pytest.raises(DemoToolRegistryError) as crossed:
        resolve_tool(OperationEngine.GEOMETRY, OperationType.EXPOSURE)
    assert crossed.value.code == "TOOL_REGISTRY_MISMATCH"

    with pytest.raises(DemoToolRegistryError) as malformed:
        resolve_persisted_tool("UNKNOWN", "EXPOSURE")
    assert malformed.value.code == "INVALID_TOOL_IDENTITY"


def test_execution_mode_is_derived_from_registry_not_caller_choice() -> None:
    descriptor = resolve_persisted_tool("RASTER", "EXPOSURE")
    assert require_execution_mode(descriptor, "DETERMINISTIC_RASTER") is descriptor
    with pytest.raises(DemoToolRegistryError) as mismatch:
        require_execution_mode(descriptor, "GEOMETRY")
    assert mismatch.value.code == "EXECUTION_MODE_MISMATCH"
