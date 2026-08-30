"""Typed, deterministic D08 tool registry for the Demo editing runtime.

The registry is product authority for tool identity and capability semantics;
it does not discover runtimes, load private assets, or make a Provider call.
Geometry remains executable only when the accepted M4 runtime is injected by
the Principal-owned composition boundary.  Makeup and Generative remain
explicitly unavailable and therefore never receive an engine version.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_operation_graph import CapabilityState, OperationEngine, OperationType

TOOL_REGISTRY_SCHEMA_VERSION: Final = "mirror.demo/ToolRegistry/v1"
TOOL_REGISTRY_VERSION: Final = "demo-tool-registry-v1"
RASTER_ENGINE_VERSION: Final = "demo-raster-editor-pillow12-fixedpoint-v1"
GEOMETRY_ENGINE_VERSION: Final = "demo-geometry-injected-v1"

ExecutionMode = Literal["DETERMINISTIC_RASTER", "GEOMETRY", "MAKEUP", "GENERATIVE"]


class DemoToolRegistryError(ValueError):
    """A persisted operation or requested mode does not match registry authority."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DemoToolDescriptor:
    operation_type: OperationType
    engine: OperationEngine
    execution_mode: ExecutionMode
    tool_name: str
    capability_state: CapabilityState
    engine_version: str | None
    unavailable_reason_code: str | None
    verifier_required: bool

    def __post_init__(self) -> None:
        unavailable = self.capability_state in {
            CapabilityState.DEFERRED_WITH_EXPLICIT_REASON,
            CapabilityState.CAPABILITY_UNAVAILABLE,
        }
        if unavailable != (self.engine_version is None):
            raise DemoToolRegistryError(
                "INVALID_TOOL_DESCRIPTOR",
                "only unavailable tools omit an engine version",
            )
        if unavailable != (self.unavailable_reason_code is not None):
            raise DemoToolRegistryError(
                "INVALID_TOOL_DESCRIPTOR",
                "unavailable tool reason does not match capability state",
            )
        if unavailable and self.verifier_required:
            raise DemoToolRegistryError(
                "INVALID_TOOL_DESCRIPTOR",
                "an unavailable tool cannot require execution verification",
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "capability_state": self.capability_state.value,
            "engine": self.engine.value,
            "engine_version": self.engine_version,
            "execution_mode": self.execution_mode,
            "operation_type": self.operation_type.value,
            "tool_name": self.tool_name,
            "unavailable_reason_code": self.unavailable_reason_code,
            "verifier_required": self.verifier_required,
        }


def _descriptor(
    operation_type: OperationType,
    engine: OperationEngine,
    execution_mode: ExecutionMode,
    capability_state: CapabilityState,
    engine_version: str | None,
    unavailable_reason_code: str | None = None,
) -> DemoToolDescriptor:
    return DemoToolDescriptor(
        operation_type=operation_type,
        engine=engine,
        execution_mode=execution_mode,
        tool_name=f"demo-{engine.value.lower()}-{operation_type.value.lower()}",
        capability_state=capability_state,
        engine_version=engine_version,
        unavailable_reason_code=unavailable_reason_code,
        verifier_required=engine_version is not None,
    )


_RASTER_TYPES: Final = (
    OperationType.CROP,
    OperationType.ROTATE,
    OperationType.EXPOSURE,
    OperationType.CONTRAST,
    OperationType.SATURATION,
    OperationType.TEMPERATURE,
    OperationType.RESTORE,
    OperationType.ROLLBACK,
)

_TOOLS = {
    operation: _descriptor(
        operation,
        OperationEngine.RASTER,
        "DETERMINISTIC_RASTER",
        CapabilityState.AVAILABLE,
        RASTER_ENGINE_VERSION,
    )
    for operation in _RASTER_TYPES
}
_TOOLS.update(
    {
        OperationType.GEOMETRY: _descriptor(
            OperationType.GEOMETRY,
            OperationEngine.GEOMETRY,
            "GEOMETRY",
            CapabilityState.CAPABILITY_GATED,
            GEOMETRY_ENGINE_VERSION,
        ),
        OperationType.MAKEUP: _descriptor(
            OperationType.MAKEUP,
            OperationEngine.MAKEUP,
            "MAKEUP",
            CapabilityState.DEFERRED_WITH_EXPLICIT_REASON,
            None,
            "MAKEUP_DEFERRED_NO_APPROVED_ENGINE",
        ),
        OperationType.GENERATIVE: _descriptor(
            OperationType.GENERATIVE,
            OperationEngine.GENERATIVE,
            "GENERATIVE",
            CapabilityState.CAPABILITY_UNAVAILABLE,
            None,
            "GENERATIVE_PROVIDER_UNAVAILABLE",
        ),
    }
)
TOOLS: Final = MappingProxyType(_TOOLS)


def registered_tools() -> tuple[DemoToolDescriptor, ...]:
    """Return the complete registry in canonical operation-type order."""

    return tuple(TOOLS[item] for item in sorted(TOOLS, key=lambda value: value.value))


def resolve_tool(engine: OperationEngine, operation_type: OperationType) -> DemoToolDescriptor:
    if not isinstance(engine, OperationEngine) or not isinstance(operation_type, OperationType):
        raise DemoToolRegistryError(
            "INVALID_TOOL_IDENTITY", "tool identity must use typed engine and operation values"
        )
    descriptor = TOOLS.get(operation_type)
    if descriptor is None or descriptor.engine is not engine:
        raise DemoToolRegistryError(
            "TOOL_REGISTRY_MISMATCH", "operation engine does not match tool registry"
        )
    return descriptor


def resolve_persisted_tool(engine: object, operation_type: object) -> DemoToolDescriptor:
    """Resolve untrusted PostgreSQL scalar values without leaking parser errors."""

    if not isinstance(engine, str) or not isinstance(operation_type, str):
        raise DemoToolRegistryError("INVALID_TOOL_IDENTITY", "persisted tool identity is invalid")
    try:
        typed_engine = OperationEngine(engine)
        typed_operation = OperationType(operation_type)
    except (TypeError, ValueError) as exc:
        raise DemoToolRegistryError(
            "INVALID_TOOL_IDENTITY", "persisted tool identity is invalid"
        ) from exc
    return resolve_tool(typed_engine, typed_operation)


def require_execution_mode(
    descriptor: DemoToolDescriptor, execution_mode: object
) -> DemoToolDescriptor:
    if not isinstance(descriptor, DemoToolDescriptor):
        raise DemoToolRegistryError("INVALID_TOOL_IDENTITY", "tool descriptor is invalid")
    if execution_mode != descriptor.execution_mode:
        raise DemoToolRegistryError(
            "EXECUTION_MODE_MISMATCH", "execution mode does not match registered tool"
        )
    return descriptor


def registry_payload() -> dict[str, object]:
    return {
        "schema_version": TOOL_REGISTRY_SCHEMA_VERSION,
        "tool_registry_version": TOOL_REGISTRY_VERSION,
        "tools": [item.canonical_payload() for item in registered_tools()],
    }


def registry_digest() -> str:
    return hashlib.sha256(canonical_json_bytes(registry_payload())).hexdigest()


__all__ = [
    "GEOMETRY_ENGINE_VERSION",
    "RASTER_ENGINE_VERSION",
    "TOOL_REGISTRY_SCHEMA_VERSION",
    "TOOL_REGISTRY_VERSION",
    "DemoToolDescriptor",
    "DemoToolRegistryError",
    "registered_tools",
    "registry_digest",
    "registry_payload",
    "require_execution_mode",
    "resolve_persisted_tool",
    "resolve_tool",
]
