"""Pure, deterministic authority for the D07-A linear Demo operation graph."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, cast

GRAPH_SCHEMA_VERSION: Final = "mirror.demo/OperationGraph/v2"
GRAPH_ALGORITHM_VERSION: Final = "demo-operation-graph-linear-v1"
MAX_OPERATIONS: Final = 64
MAX_SAFE_INTEGER: Final = 9_007_199_254_740_991

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_DIMENSION = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


class OperationEngine(StrEnum):
    RASTER = "RASTER"
    GEOMETRY = "GEOMETRY"
    MAKEUP = "MAKEUP"
    GENERATIVE = "GENERATIVE"


class OperationType(StrEnum):
    CROP = "CROP"
    ROTATE = "ROTATE"
    EXPOSURE = "EXPOSURE"
    CONTRAST = "CONTRAST"
    SATURATION = "SATURATION"
    TEMPERATURE = "TEMPERATURE"
    RESTORE = "RESTORE"
    ROLLBACK = "ROLLBACK"
    GEOMETRY = "GEOMETRY"
    MAKEUP = "MAKEUP"
    GENERATIVE = "GENERATIVE"


class CapabilityState(StrEnum):
    AVAILABLE = "AVAILABLE"
    CAPABILITY_GATED = "CAPABILITY_GATED"
    DEFERRED_WITH_EXPLICIT_REASON = "DEFERRED_WITH_EXPLICIT_REASON"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"


class TargetRegion(StrEnum):
    CANVAS = "CANVAS"
    FULL_IMAGE = "FULL_IMAGE"
    FACE_REGION = "FACE_REGION"
    VERSION_CONTENT = "VERSION_CONTENT"
    NONE = "NONE"


class PreserveKey(StrEnum):
    BACKGROUND = "BACKGROUND"
    COLOR_OUTSIDE_TARGET = "COLOR_OUTSIDE_TARGET"
    COMPOSITION = "COMPOSITION"
    EXPRESSION = "EXPRESSION"
    HAIR = "HAIR"
    IDENTITY_REFERENCE_FRAME = "IDENTITY_REFERENCE_FRAME"
    NON_TARGET_GEOMETRY = "NON_TARGET_GEOMETRY"
    POSE = "POSE"
    SKIN_TEXTURE = "SKIN_TEXTURE"
    TARGET_VERSION_BYTES = "TARGET_VERSION_BYTES"


class DemoOperationGraphError(ValueError):
    """Fail-closed error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OperationExecutionUnavailable(DemoOperationGraphError):
    """An execution request includes a deliberately unavailable capability."""


class OperationLineageError(DemoOperationGraphError):
    """A restore or rollback lineage request is not safe to materialize."""


@dataclass(frozen=True)
class OperationSpec:
    engine: OperationEngine
    operation_type: OperationType
    parameters: Mapping[str, Any]
    preserve: tuple[PreserveKey, ...]
    expected_effect: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.engine, OperationEngine) or not isinstance(
            self.operation_type, OperationType
        ):
            raise DemoOperationGraphError(
                "ENGINE_OPERATION_MISMATCH", "operation spec requires frozen enum values"
            )
        if self.operation_type not in _ENGINE_TYPES[self.engine]:
            raise DemoOperationGraphError(
                "ENGINE_OPERATION_MISMATCH", "operation type is not supported by engine"
            )
        _validate_json_value(self.parameters)
        parameters = _normalize_parameters(self.operation_type, self.parameters)
        preserve = _validate_constructed_preserve(self.operation_type, self.preserve)
        supplied_effect = _normalize_json_object(self.expected_effect, "expected effect")
        expected_effect = _expected_effect(self.operation_type, parameters)
        if supplied_effect != expected_effect:
            raise DemoOperationGraphError(
                "EXPECTED_EFFECT_MISMATCH", "expected effect is not derived from parameters"
            )
        object.__setattr__(self, "parameters", _freeze_json_mapping(parameters))
        object.__setattr__(self, "preserve", preserve)
        object.__setattr__(self, "expected_effect", _freeze_json_mapping(expected_effect))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "expected_effect": _thaw_json_value(self.expected_effect),
            "operation_type": self.operation_type.value,
            "parameters": _thaw_json_value(self.parameters),
            "preserve": [item.value for item in self.preserve],
        }


@dataclass(frozen=True)
class OperationNode:
    """One graph-local address; ``node_id`` is never an execution idempotency key."""

    depends_on: tuple[str, ...]
    node_id: str
    operation_index: int
    spec: OperationSpec

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "depends_on": list(self.depends_on),
            "node_id": self.node_id,
            "operation_index": self.operation_index,
            "spec": self.spec.canonical_payload(),
        }


@dataclass(frozen=True)
class OperationGraph:
    algorithm_version: str
    input_image_version_digest: str
    input_image_version_id: str
    nodes: tuple[OperationNode, ...]

    def __post_init__(self) -> None:
        """Freeze direct-construction nodes before the graph can become authority."""

        supplied_nodes: object = self.nodes
        if not isinstance(supplied_nodes, (list, tuple)):
            raise DemoOperationGraphError(
                "INVALID_GRAPH", "nodes must be a tuple or list of OperationNode values"
            )
        candidate_nodes = tuple(supplied_nodes)
        if not all(isinstance(node, OperationNode) for node in candidate_nodes):
            raise DemoOperationGraphError(
                "INVALID_GRAPH", "nodes must contain OperationNode values"
            )
        object.__setattr__(
            self,
            "nodes",
            tuple(cast(OperationNode, node) for node in candidate_nodes),
        )

    def canonical_payload(self) -> dict[str, Any]:
        return graph_canonical_payload(self)

    def content_digest(self) -> str:
        return graph_content_digest(self)


@dataclass(frozen=True)
class ImageVersionReference:
    """Read-only, immutable lineage fact supplied by the persistence boundary."""

    image_version_id: str
    image_version_digest: str
    actor_id: str
    demo_session_id: str
    editing_session_id: str
    result_asset_id: str
    result_asset_sha256: str
    sequence: int
    parent_image_version_id: str | None
    quarantined: bool = False


@dataclass(frozen=True)
class TransitionIntent:
    kind: str
    parent_image_version_id: str
    parent_image_version_digest: str
    result_sequence: int
    source_image_version_id: str
    source_image_version_digest: str
    source_asset_id: str
    source_asset_sha256: str
    target_image_version_id: str
    target_image_version_digest: str
    target_result_asset_id: str
    target_result_asset_sha256: str
    expected_result_asset_sha256: str
    requires_distinct_result_asset_id: bool = True


_ENGINE_TYPES: Final = {
    OperationEngine.RASTER: frozenset(
        {
            OperationType.CROP,
            OperationType.ROTATE,
            OperationType.EXPOSURE,
            OperationType.CONTRAST,
            OperationType.SATURATION,
            OperationType.TEMPERATURE,
            OperationType.RESTORE,
            OperationType.ROLLBACK,
        }
    ),
    OperationEngine.GEOMETRY: frozenset({OperationType.GEOMETRY}),
    OperationEngine.MAKEUP: frozenset({OperationType.MAKEUP}),
    OperationEngine.GENERATIVE: frozenset({OperationType.GENERATIVE}),
}
_UNAVAILABLE_REASONS: Final = {
    OperationType.MAKEUP: (
        CapabilityState.DEFERRED_WITH_EXPLICIT_REASON,
        "MAKEUP_DEFERRED_NO_APPROVED_ENGINE",
    ),
    OperationType.GENERATIVE: (
        CapabilityState.CAPABILITY_UNAVAILABLE,
        "GENERATIVE_PROVIDER_UNAVAILABLE",
    ),
}
_EXECUTION_GATES: Final = {
    OperationType.GEOMETRY: "GEOMETRY_EXECUTION_REGISTRY_REQUIRED",
}
_EFFECT_TARGETS: Final = {
    OperationType.CROP: TargetRegion.CANVAS,
    OperationType.ROTATE: TargetRegion.CANVAS,
    OperationType.EXPOSURE: TargetRegion.FULL_IMAGE,
    OperationType.CONTRAST: TargetRegion.FULL_IMAGE,
    OperationType.SATURATION: TargetRegion.FULL_IMAGE,
    OperationType.TEMPERATURE: TargetRegion.FULL_IMAGE,
    OperationType.GEOMETRY: TargetRegion.FACE_REGION,
    OperationType.RESTORE: TargetRegion.VERSION_CONTENT,
    OperationType.ROLLBACK: TargetRegion.VERSION_CONTENT,
}


def parse_operation_spec(value: Mapping[str, Any]) -> OperationSpec:
    """Strictly parse one five-key operation specification into its canonical form."""

    _require_mapping_keys(
        value,
        {"engine", "operation_type", "parameters", "preserve", "expected_effect"},
        "operation spec",
    )
    try:
        engine = OperationEngine(value["engine"])
        operation_type = OperationType(value["operation_type"])
    except (TypeError, ValueError) as exc:
        raise DemoOperationGraphError(
            "ENGINE_OPERATION_MISMATCH", "unsupported operation engine or type"
        ) from exc
    if operation_type not in _ENGINE_TYPES[engine]:
        raise DemoOperationGraphError(
            "ENGINE_OPERATION_MISMATCH", "operation type is not supported by engine"
        )
    parameters = _normalize_parameters(operation_type, value["parameters"])
    preserve = _normalize_preserve(operation_type, value["preserve"])
    expected_effect = _expected_effect(operation_type, parameters)
    supplied_effect = _normalize_json_object(value["expected_effect"], "expected effect")
    if supplied_effect != expected_effect:
        raise DemoOperationGraphError(
            "EXPECTED_EFFECT_MISMATCH", "expected effect is not derived from parameters"
        )
    return OperationSpec(engine, operation_type, parameters, preserve, expected_effect)


def build_operation_graph(
    input_image_version_id: str,
    input_image_version_digest: str,
    specs: Sequence[OperationSpec | Mapping[str, Any]],
) -> OperationGraph:
    """Build a canonical single-root linear graph from ordered specifications."""

    _require_id(input_image_version_id, "input image version id")
    _require_digest(input_image_version_digest, "input image version digest")
    _require_sequence(specs, "specs")
    parsed = tuple(
        item if isinstance(item, OperationSpec) else parse_operation_spec(item) for item in specs
    )
    _require_node_count(len(parsed))
    nodes = tuple(
        OperationNode(
            depends_on=() if index == 0 else (f"op-{index - 1:08d}",),
            node_id=f"op-{index:08d}",
            operation_index=index,
            spec=item,
        )
        for index, item in enumerate(parsed)
    )
    graph = OperationGraph(
        algorithm_version=GRAPH_ALGORITHM_VERSION,
        input_image_version_digest=input_image_version_digest,
        input_image_version_id=input_image_version_id,
        nodes=nodes,
    )
    validate_operation_graph(graph)
    return graph


def hydrate_operation_graph(value: Mapping[str, Any]) -> OperationGraph:
    """Hydrate untrusted persisted graph payload only when every metadata fact recomputes."""

    _require_mapping_keys(
        value,
        {
            "algorithm_version",
            "input_image_version_digest",
            "input_image_version_id",
            "nodes",
            "schema_version",
        },
        "operation graph",
    )
    if value["schema_version"] != GRAPH_SCHEMA_VERSION:
        raise DemoOperationGraphError(
            "UNSUPPORTED_SCHEMA_VERSION", "unsupported graph schema version"
        )
    if value["algorithm_version"] != GRAPH_ALGORITHM_VERSION:
        raise DemoOperationGraphError(
            "UNSUPPORTED_ALGORITHM_VERSION", "unsupported graph algorithm version"
        )
    _require_id(value["input_image_version_id"], "input image version id")
    _require_digest(value["input_image_version_digest"], "input image version digest")
    raw_nodes = value["nodes"]
    if not isinstance(raw_nodes, list):
        raise DemoOperationGraphError("INVALID_GRAPH", "nodes must be a JSON array")
    nodes: list[OperationNode] = []
    for raw_node in raw_nodes:
        if not isinstance(raw_node, Mapping):
            raise DemoOperationGraphError("INVALID_GRAPH", "node must be an object")
        _require_mapping_keys(
            raw_node, {"depends_on", "node_id", "operation_index", "spec"}, "node"
        )
        dependencies = raw_node["depends_on"]
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) for item in dependencies
        ):
            raise DemoOperationGraphError("INVALID_GRAPH", "depends_on must be a string array")
        index = raw_node["operation_index"]
        if not _is_int(index):
            raise DemoOperationGraphError("INVALID_GRAPH", "operation index must be an integer")
        node_id = raw_node["node_id"]
        if not isinstance(node_id, str):
            raise DemoOperationGraphError("INVALID_GRAPH", "node id must be a string")
        spec_value = raw_node["spec"]
        if not isinstance(spec_value, Mapping):
            raise DemoOperationGraphError("INVALID_GRAPH", "node spec must be an object")
        nodes.append(
            OperationNode(tuple(dependencies), node_id, index, parse_operation_spec(spec_value))
        )
    graph = OperationGraph(
        algorithm_version=GRAPH_ALGORITHM_VERSION,
        input_image_version_digest=value["input_image_version_digest"],
        input_image_version_id=value["input_image_version_id"],
        nodes=tuple(nodes),
    )
    validate_operation_graph(graph)
    return graph


def validate_operation_graph(graph: OperationGraph) -> None:
    """Validate the full linear topology and canonical operation-node metadata."""

    if not isinstance(graph, OperationGraph):
        raise DemoOperationGraphError("INVALID_GRAPH", "graph must be an OperationGraph")
    if graph.algorithm_version != GRAPH_ALGORITHM_VERSION:
        raise DemoOperationGraphError(
            "UNSUPPORTED_ALGORITHM_VERSION", "unsupported graph algorithm version"
        )
    _require_id(graph.input_image_version_id, "input image version id")
    _require_digest(graph.input_image_version_digest, "input image version digest")
    if not isinstance(graph.nodes, tuple):
        raise DemoOperationGraphError("INVALID_GRAPH", "nodes must be an immutable tuple")
    _require_node_count(len(graph.nodes))
    by_id: dict[str, OperationNode] = {}
    by_index: dict[int, OperationNode] = {}
    for node in graph.nodes:
        if not isinstance(node, OperationNode):
            raise DemoOperationGraphError(
                "INVALID_GRAPH", "nodes must contain OperationNode values"
            )
        if node.node_id in by_id:
            raise DemoOperationGraphError("DUPLICATE_NODE_ID", "duplicate node id")
        if node.operation_index in by_index:
            raise DemoOperationGraphError("DUPLICATE_OPERATION_INDEX", "duplicate operation index")
        if not _is_int(node.operation_index):
            raise DemoOperationGraphError("INVALID_GRAPH", "operation index must be an integer")
        by_id[node.node_id] = node
        by_index[node.operation_index] = node
        # Reparse the canonical payload to reject manually constructed, drifting dataclasses.
        parse_operation_spec(node.spec.canonical_payload())
    count = len(graph.nodes)
    if set(by_index) != set(range(count)):
        raise DemoOperationGraphError(
            "INVALID_GRAPH", "operation indexes must be contiguous from zero"
        )
    if tuple(node.operation_index for node in graph.nodes) != tuple(range(count)):
        raise DemoOperationGraphError(
            "NON_CANONICAL_NODE_ORDER", "nodes must be ordered by operation index"
        )
    for node in graph.nodes:
        if len(set(node.depends_on)) != len(node.depends_on):
            raise DemoOperationGraphError("DUPLICATE_EDGE", "duplicate dependency edge")
        for dependency in node.depends_on:
            if dependency not in by_id:
                raise DemoOperationGraphError("ORPHAN_DEPENDENCY", "dependency does not exist")
    order = _kahn_order(by_id, by_index)
    if len(order) != count:
        raise DemoOperationGraphError("GRAPH_CYCLE", "graph contains a cycle")
    root = by_index[0]
    reachable = _reachable(root.node_id, by_id)
    if len(reachable) != count:
        raise DemoOperationGraphError("DISCONNECTED_GRAPH", "graph is disconnected")
    expected_order = [by_index[index].node_id for index in range(count)]
    if order != expected_order:
        raise DemoOperationGraphError(
            "NON_LINEAR_GRAPH_UNSUPPORTED", "topological order is not linear"
        )
    for index in range(count):
        node = by_index[index]
        if node.node_id != f"op-{index:08d}":
            raise DemoOperationGraphError(
                "NON_LINEAR_GRAPH_UNSUPPORTED", "node id does not match operation index"
            )
        expected_dependencies = () if index == 0 else (f"op-{index - 1:08d}",)
        if node.depends_on != expected_dependencies:
            raise DemoOperationGraphError(
                "NON_LINEAR_GRAPH_UNSUPPORTED", "graph is not a single linear chain"
            )


def graph_canonical_payload(graph: OperationGraph) -> dict[str, Any]:
    validate_operation_graph(graph)
    return {
        "algorithm_version": graph.algorithm_version,
        "input_image_version_digest": graph.input_image_version_digest,
        "input_image_version_id": graph.input_image_version_id,
        "nodes": [node.canonical_payload() for node in graph.nodes],
        "schema_version": GRAPH_SCHEMA_VERSION,
    }


def graph_canonical_json(graph: OperationGraph) -> bytes:
    return canonical_json_bytes(graph_canonical_payload(graph))


def graph_content_digest(graph: OperationGraph) -> str:
    return hashlib.sha256(
        GRAPH_SCHEMA_VERSION.encode("utf-8") + b"\n" + graph_canonical_json(graph)
    ).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """Encode the restricted JSON authority format, refusing non-canonical Python values."""

    _validate_json_value(value)
    canonical_value = _canonicalize_json_value(value)
    return json.dumps(
        canonical_value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")


def capability_state(spec: OperationSpec) -> CapabilityState:
    """Return the D07-A structural state, not D07-B ExecutionRegistry authority."""

    if spec.operation_type in _UNAVAILABLE_REASONS:
        return _UNAVAILABLE_REASONS[spec.operation_type][0]
    if spec.operation_type in _EXECUTION_GATES:
        return CapabilityState.CAPABILITY_GATED
    return CapabilityState.AVAILABLE


def validate_for_execution(graph: OperationGraph) -> None:
    """Fail before a caller can invoke any execution callback for unavailable capabilities."""

    validate_operation_graph(graph)
    for node in graph.nodes:
        state = capability_state(node.spec)
        if state is not CapabilityState.AVAILABLE:
            unavailable = _UNAVAILABLE_REASONS.get(node.spec.operation_type)
            reason = (
                unavailable[1]
                if unavailable is not None
                else _EXECUTION_GATES[node.spec.operation_type]
            )
            raise OperationExecutionUnavailable(state.value, reason)


def plan_restore_transition(
    current: ImageVersionReference,
    history: Sequence[ImageVersionReference],
    target_image_version_id: str,
    target_image_version_digest: str,
) -> TransitionIntent:
    return _plan_transition(
        "RESTORED", current, history, target_image_version_id, target_image_version_digest, False
    )


def plan_rollback_transition(
    current: ImageVersionReference,
    history: Sequence[ImageVersionReference],
    target_image_version_id: str,
    target_image_version_digest: str,
) -> TransitionIntent:
    return _plan_transition(
        "ROLLED_BACK", current, history, target_image_version_id, target_image_version_digest, True
    )


def validate_result_asset_id(intent: TransitionIntent, result_asset_id: str) -> None:
    """Require the future persistence layer to allocate a distinct immutable asset id."""

    _require_id(result_asset_id, "result asset id")
    if intent.requires_distinct_result_asset_id and result_asset_id in {
        intent.source_asset_id,
        intent.target_result_asset_id,
    }:
        raise OperationLineageError(
            "RESULT_ASSET_NOT_DISTINCT", "result asset id must differ from source and target"
        )


def _plan_transition(
    kind: str,
    current: ImageVersionReference,
    history: Sequence[ImageVersionReference],
    target_id: str,
    target_digest: str,
    immediate_parent_only: bool,
) -> TransitionIntent:
    chain = _validated_ancestor_chain(current, history)
    _require_id(target_id, "target image version id")
    _require_digest(target_digest, "target image version digest")
    by_id = {item.image_version_id: item for item in history}
    target = by_id.get(target_id)
    if target is None:
        raise OperationLineageError("TARGET_NOT_FOUND", "target is not in immutable history")
    if target.image_version_digest != target_digest:
        raise OperationLineageError(
            "TARGET_DIGEST_MISMATCH", "target digest does not bind target id"
        )
    if target.image_version_id == current.image_version_id:
        raise OperationLineageError(
            "CURRENT_TARGET_UNSUPPORTED", "current version cannot be its own target"
        )
    if immediate_parent_only and current.parent_image_version_id != target_id:
        raise OperationLineageError(
            "ROLLBACK_NOT_IMMEDIATE_PARENT", "rollback must target immediate parent"
        )
    if target_id not in {item.image_version_id for item in chain[1:]}:
        raise OperationLineageError("TARGET_NOT_ANCESTOR", "target is not a current ancestor")
    return TransitionIntent(
        kind=kind,
        parent_image_version_id=current.image_version_id,
        parent_image_version_digest=current.image_version_digest,
        result_sequence=current.sequence + 1,
        source_image_version_id=current.image_version_id,
        source_image_version_digest=current.image_version_digest,
        source_asset_id=current.result_asset_id,
        source_asset_sha256=current.result_asset_sha256,
        target_image_version_id=target.image_version_id,
        target_image_version_digest=target.image_version_digest,
        target_result_asset_id=target.result_asset_id,
        target_result_asset_sha256=target.result_asset_sha256,
        expected_result_asset_sha256=target.result_asset_sha256,
    )


def _validate_history(
    current: ImageVersionReference, history: Sequence[ImageVersionReference]
) -> None:
    _require_sequence(history, "history")
    if not history:
        raise OperationLineageError("INVALID_HISTORY", "history must not be empty")
    by_id: dict[str, ImageVersionReference] = {}
    for item in history:
        if not isinstance(item, ImageVersionReference):
            raise OperationLineageError("INVALID_HISTORY", "history contains an invalid reference")
        _require_id(item.image_version_id, "image version id")
        _require_digest(item.image_version_digest, "image version digest")
        _require_id(item.result_asset_id, "result asset id")
        _require_digest(item.result_asset_sha256, "result asset sha256")
        _require_id(item.actor_id, "actor id")
        _require_id(item.demo_session_id, "demo session id")
        _require_id(item.editing_session_id, "editing session id")
        if not _is_int(item.sequence) or item.sequence < 0:
            raise OperationLineageError(
                "INVALID_HISTORY", "sequence must be a non-negative integer"
            )
        if item.parent_image_version_id is not None:
            _require_id(item.parent_image_version_id, "parent image version id")
        if item.image_version_id in by_id:
            raise OperationLineageError("INVALID_HISTORY", "history is not immutable and unique")
        by_id[item.image_version_id] = item
    stored_current = by_id.get(current.image_version_id)
    if stored_current != current:
        raise OperationLineageError(
            "INVALID_HISTORY", "current version is not an immutable history member"
        )
    for item in history:
        if item.parent_image_version_id is not None:
            parent = by_id.get(item.parent_image_version_id)
            if parent is None or parent.sequence >= item.sequence:
                raise OperationLineageError("INVALID_HISTORY", "history parent linkage is invalid")


def _validated_ancestor_chain(
    current: ImageVersionReference, history: Sequence[ImageVersionReference]
) -> tuple[ImageVersionReference, ...]:
    _validate_history(current, history)
    by_id = {item.image_version_id: item for item in history}
    chain: list[ImageVersionReference] = []
    seen: set[str] = set()
    item = current
    while True:
        if item.image_version_id in seen:
            raise OperationLineageError("INVALID_HISTORY", "history contains a parent cycle")
        seen.add(item.image_version_id)
        if item.quarantined:
            raise OperationLineageError(
                "QUARANTINED_HISTORY", "current ancestor chain is quarantined"
            )
        if (
            item.actor_id != current.actor_id
            or item.demo_session_id != current.demo_session_id
            or item.editing_session_id != current.editing_session_id
        ):
            raise OperationLineageError(
                "CROSS_SESSION_HISTORY", "current ancestor chain has foreign authority"
            )
        chain.append(item)
        if item.parent_image_version_id is None:
            return tuple(chain)
        parent = by_id.get(item.parent_image_version_id)
        if parent is None:
            raise OperationLineageError("INVALID_HISTORY", "history parent is absent")
        if parent.sequence != item.sequence - 1:
            raise OperationLineageError(
                "SEQUENCE_GAP", "current ancestor chain sequence is not contiguous"
            )
        item = parent


def _ancestor_ids(
    current: ImageVersionReference, by_id: Mapping[str, ImageVersionReference]
) -> set[str]:
    ancestors: set[str] = set()
    parent_id = current.parent_image_version_id
    while parent_id is not None:
        if parent_id in ancestors:
            raise OperationLineageError("INVALID_HISTORY", "history contains a parent cycle")
        ancestors.add(parent_id)
        parent = by_id.get(parent_id)
        if parent is None:  # guarded by _validate_history, retained for fail-closed callers.
            raise OperationLineageError("INVALID_HISTORY", "history parent is absent")
        parent_id = parent.parent_image_version_id
    return ancestors


def _normalize_parameters(operation_type: OperationType, value: Any) -> dict[str, Any]:
    if operation_type is OperationType.CROP:
        names = {"left_inset_ppm", "right_inset_ppm", "top_inset_ppm", "bottom_inset_ppm"}
        _require_mapping_keys(value, names, "crop parameters")
        result = {name: _require_integer_in_range(value[name], name, 0, 250_000) for name in names}
        if (
            result["left_inset_ppm"] + result["right_inset_ppm"] > 500_000
            or result["top_inset_ppm"] + result["bottom_inset_ppm"] > 500_000
        ):
            raise DemoOperationGraphError(
                "INVALID_PARAMETERS", "crop inset sums must not exceed 500000"
            )
        if not any(result.values()):
            raise DemoOperationGraphError(
                "INVALID_PARAMETERS", "crop must change at least one inset"
            )
        return result
    if operation_type is OperationType.ROTATE:
        _require_mapping_keys(value, {"angle_mdeg", "expand_canvas"}, "rotate parameters")
        angle = _require_integer_in_range(
            value["angle_mdeg"], "angle_mdeg", -15_000, 15_000, nonzero=True
        )
        if not isinstance(value["expand_canvas"], bool):
            raise DemoOperationGraphError("INVALID_PARAMETERS", "expand_canvas must be a bool")
        return {"angle_mdeg": angle, "expand_canvas": value["expand_canvas"]}
    ranges: dict[OperationType, tuple[str, int, int]] = {
        OperationType.EXPOSURE: ("exposure_ev_milli", -2_000, 2_000),
        OperationType.CONTRAST: ("contrast_delta_ppm", -500_000, 500_000),
        OperationType.SATURATION: ("saturation_delta_ppm", -1_000_000, 1_000_000),
        OperationType.TEMPERATURE: ("temperature_delta_mired", -100, 100),
    }
    if operation_type in ranges:
        name, minimum, maximum = ranges[operation_type]
        _require_mapping_keys(value, {name}, f"{operation_type.value.lower()} parameters")
        return {name: _require_integer_in_range(value[name], name, minimum, maximum, nonzero=True)}
    if operation_type is OperationType.GEOMETRY:
        _require_mapping_keys(value, {"dimension_key", "delta_ppm"}, "geometry parameters")
        key = value["dimension_key"]
        if not isinstance(key, str) or _DIMENSION.fullmatch(key) is None:
            raise DemoOperationGraphError("INVALID_PARAMETERS", "dimension_key is invalid")
        return {
            "delta_ppm": _require_integer_in_range(
                value["delta_ppm"], "delta_ppm", -100_000, 100_000, nonzero=True
            ),
            "dimension_key": key,
        }
    if operation_type in (OperationType.RESTORE, OperationType.ROLLBACK):
        names = {"target_image_version_id", "target_image_version_digest"}
        _require_mapping_keys(value, names, "transition parameters")
        _require_id(value["target_image_version_id"], "target image version id")
        _require_digest(value["target_image_version_digest"], "target image version digest")
        return {
            "target_image_version_digest": value["target_image_version_digest"],
            "target_image_version_id": value["target_image_version_id"],
        }
    reason = _UNAVAILABLE_REASONS[operation_type][1]
    _require_mapping_keys(value, {"reason_code"}, "unavailable parameters")
    if value["reason_code"] != reason:
        raise DemoOperationGraphError(
            "INVALID_PARAMETERS", "unavailable capability reason is not exact"
        )
    return {"reason_code": reason}


def _normalize_preserve(operation_type: OperationType, value: Any) -> tuple[PreserveKey, ...]:
    if not isinstance(value, list):
        raise DemoOperationGraphError("INVALID_PRESERVE", "preserve must be a JSON array")
    try:
        keys = tuple(PreserveKey(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise DemoOperationGraphError(
            "INVALID_PRESERVE", "preserve contains an unsupported key"
        ) from exc
    canonical = tuple(sorted(keys, key=lambda item: item.value.encode("utf-8")))
    return _validate_preserve_keys(operation_type, canonical)


def _validate_constructed_preserve(
    operation_type: OperationType, value: Any
) -> tuple[PreserveKey, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise DemoOperationGraphError("INVALID_PRESERVE", "preserve must be a sequence")
    keys = tuple(value)
    if not all(isinstance(item, PreserveKey) for item in keys):
        raise DemoOperationGraphError(
            "INVALID_PRESERVE", "preserve must contain frozen enum values"
        )
    return _validate_preserve_keys(operation_type, keys)


def _validate_preserve_keys(
    operation_type: OperationType, keys: tuple[PreserveKey, ...]
) -> tuple[PreserveKey, ...]:
    if len(set(keys)) != len(keys):
        raise DemoOperationGraphError("INVALID_PRESERVE", "preserve keys must be unique")
    canonical = tuple(sorted(keys, key=lambda item: item.value.encode("utf-8")))
    if canonical != keys:
        raise DemoOperationGraphError("INVALID_PRESERVE", "preserve keys must be canonical")
    if operation_type in _UNAVAILABLE_REASONS:
        if canonical:
            raise DemoOperationGraphError(
                "INVALID_PRESERVE", "unavailable operations preserve nothing"
            )
    elif operation_type in (OperationType.RESTORE, OperationType.ROLLBACK):
        if canonical != (PreserveKey.TARGET_VERSION_BYTES,):
            raise DemoOperationGraphError(
                "INVALID_PRESERVE", "transition operations preserve target bytes exactly"
            )
    else:
        required = {PreserveKey.IDENTITY_REFERENCE_FRAME}
        if operation_type is OperationType.GEOMETRY:
            required.add(PreserveKey.NON_TARGET_GEOMETRY)
        if not required.issubset(canonical):
            raise DemoOperationGraphError(
                "INVALID_PRESERVE", "operation is missing required preserve keys"
            )
    return canonical


def _expected_effect(
    operation_type: OperationType, parameters: Mapping[str, Any]
) -> dict[str, Any]:
    if operation_type in _UNAVAILABLE_REASONS:
        state, reason = _UNAVAILABLE_REASONS[operation_type]
        return {
            "capability_state": state.value,
            "effect_type": "UNAVAILABLE",
            "reason_code": reason,
            "target_region": TargetRegion.NONE.value,
        }
    target = _EFFECT_TARGETS[operation_type]
    result: dict[str, Any] = {"effect_type": operation_type.value, "target_region": target.value}
    parameter_effect_keys = {
        OperationType.CROP: (
            "bottom_inset_ppm",
            "left_inset_ppm",
            "right_inset_ppm",
            "top_inset_ppm",
        ),
        OperationType.ROTATE: ("angle_mdeg", "expand_canvas"),
        OperationType.GEOMETRY: ("delta_ppm", "dimension_key"),
    }
    for key in parameter_effect_keys.get(operation_type, ()):
        result[key] = parameters[key]
    scalar_effect_keys = {
        OperationType.EXPOSURE: "exposure_ev_milli",
        OperationType.CONTRAST: "contrast_delta_ppm",
        OperationType.SATURATION: "saturation_delta_ppm",
        OperationType.TEMPERATURE: "temperature_delta_mired",
    }
    scalar_key = scalar_effect_keys.get(operation_type)
    if scalar_key is not None:
        result[scalar_key] = parameters[scalar_key]
    if operation_type in (OperationType.RESTORE, OperationType.ROLLBACK):
        result["target_image_version_digest"] = parameters["target_image_version_digest"]
    return result


def _kahn_order(
    by_id: Mapping[str, OperationNode], by_index: Mapping[int, OperationNode]
) -> list[str]:
    children: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    indegree = {node_id: 0 for node_id in by_id}
    for node in by_id.values():
        for dependency in node.depends_on:
            children[dependency].append(node.node_id)
            indegree[node.node_id] += 1
    ready = sorted(
        (node_id for node_id, degree in indegree.items() if degree == 0),
        key=lambda item: (by_id[item].operation_index, item),
    )
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for child in sorted(
            children[node_id], key=lambda item: (by_id[item].operation_index, item)
        ):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=lambda item: (by_id[item].operation_index, item))
    return order


def _reachable(root_id: str, by_id: Mapping[str, OperationNode]) -> set[str]:
    children: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for node in by_id.values():
        for dependency in node.depends_on:
            children[dependency].append(node.node_id)
    pending = [root_id]
    visited: set[str] = set()
    while pending:
        node_id = pending.pop()
        if node_id not in visited:
            visited.add(node_id)
            pending.extend(children[node_id])
    return visited


def _normalize_json_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DemoOperationGraphError("INVALID_PARAMETERS", f"{name} must be an object")
    _validate_json_value(value)
    return dict(value)


def _freeze_json_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("canonical JSON object must be a mapping")
    return MappingProxyType({key: _freeze_json_value(item) for key, item in value.items()})


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_json_mapping(value)
    if isinstance(value, list) or isinstance(value, tuple):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value


def _canonicalize_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _canonicalize_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: pair[0].encode("utf-8"))
        }
    if isinstance(value, list):
        return [_canonicalize_json_value(item) for item in value]
    return value


def _validate_json_value(value: Any) -> None:
    if isinstance(value, bool):
        return
    if _is_int(value):
        if value < -MAX_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
            raise DemoOperationGraphError(
                "NON_CANONICAL_JSON", "integers must be within the interoperable safe range"
            )
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise DemoOperationGraphError(
                "NON_CANONICAL_JSON", "strings must be valid UTF-8"
            ) from exc
        if unicodedata.normalize("NFC", value) != value:
            raise DemoOperationGraphError(
                "NON_CANONICAL_JSON", "strings must use Unicode NFC normalization"
            )
        return
    if value is None:
        raise DemoOperationGraphError("NON_CANONICAL_JSON", "null is not permitted")
    if isinstance(value, float):
        raise DemoOperationGraphError("NON_CANONICAL_JSON", "floats are not permitted")
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DemoOperationGraphError(
                    "NON_CANONICAL_JSON", "JSON object keys must be strings"
                )
            _validate_json_value(key)
            _validate_json_value(item)
        return
    raise DemoOperationGraphError("NON_CANONICAL_JSON", "unsupported canonical JSON value")


def _require_mapping_keys(value: Any, expected: set[str], name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise DemoOperationGraphError("INVALID_PARAMETERS", f"{name} keys must match exactly")
    _validate_json_value(value)


def _require_integer_in_range(
    value: Any, name: str, minimum: int, maximum: int, *, nonzero: bool = False
) -> int:
    if not _is_int(value) or value < minimum or value > maximum or (nonzero and value == 0):
        raise DemoOperationGraphError(
            "INVALID_PARAMETERS", f"{name} is outside its permitted integer range"
        )
    return int(value)


def _require_id(value: Any, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoOperationGraphError(
            "INVALID_ID", f"{name} must be 32 lowercase hexadecimal characters"
        )


def _require_digest(value: Any, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DemoOperationGraphError(
            "INVALID_DIGEST", f"{name} must be 64 lowercase hexadecimal characters"
        )


def _require_node_count(count: int) -> None:
    if count < 1 or count > MAX_OPERATIONS:
        raise DemoOperationGraphError(
            "INVALID_GRAPH", f"graph must contain 1 through {MAX_OPERATIONS} nodes"
        )


def _require_sequence(value: Any, name: str) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise DemoOperationGraphError("INVALID_GRAPH", f"{name} must be a sequence")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
