"""Exact E2 singleton authority and request-to-allocation bridge.

This is a pure domain module: it neither resolves custody locations nor performs
filesystem, database, network, or provider work.  The legacy-named allocation
field is deliberately a storage compatibility projection of the E2 request
digest, never an E1 request-policy authority.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_r2_private_registry_e2 as private_registry
from mirror_api.demo_d02_r2_generation_capability import build_generation_capability_authority
from mirror_api.demo_d02_r2_generation_epoch2 import (
    ACCEPTED_CAPABILITY_DIGEST,
    E2_CONCURRENCY,
    E2_DISPATCH_EPOCH,
    E2_PRODUCER_TASK_ID,
    E2_RESERVE_CALLS,
    E2_RETRY_CEILING,
    E2_ROOT_ID,
    D02R2Epoch2GenerationError,
    validate_generation_request,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

PREREGISTRATION_SCHEMA: Final = "mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1"
ALLOCATION_MANIFEST_SCHEMA: Final = "mirror.demo/D02R2SourceAllocationManifest/v1"
PRODUCER_DISPATCH_SCHEMA: Final = "mirror.demo/D02R2SourceProducerDispatchReceipt/v1"
PREFLIGHT_JSON_MEDIA_TYPE: Final = "application/json"
PREFLIGHT_JSON_MAXIMUM_BYTES: Final = 262_144
PREFLIGHT_SOURCE_MEDIA_TYPE: Final = "image/png"
PREFLIGHT_SOURCE_MAXIMUM_BYTES: Final = 20_971_520
PREFLIGHT_SEMANTIC_ROLES_BY_SEQUENCE: Final = (
    "SOURCE_GENERATION_PREREGISTRATION",
    "SOURCE_ALLOCATION_MANIFEST",
    "SOURCE_PRODUCER_DISPATCH_RECEIPT",
    "SOURCE_CANDIDATE",
    "SOURCE_PROVENANCE",
    "SOURCE_CANDIDATE",
    "SOURCE_PROVENANCE",
    "SOURCE_CANDIDATE",
    "SOURCE_PROVENANCE",
    "SOURCE_CANDIDATE",
    "SOURCE_PROVENANCE",
    "NEGATIVE_RECEIPT",
)
_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")

_PREREGISTRATION_KEYS: Final = (
    "schema_version",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_capability_authority_digest",
    "cohort_policy_digest",
    "producer_task_id",
    "dispatch_epoch",
    "source_count",
    "ordered_candidate_ordinals",
    "generation_preregistration_digest",
)
_ALLOCATION_KEYS: Final = (
    "schema_version",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "producer_task_id",
    "dispatch_epoch",
    "source_count",
    "ordered_allocations",
    "source_allocation_manifest_digest",
)
_ALLOCATION_ENTRY_KEYS: Final = (
    "candidate_ordinal",
    "source_output_id",
    "output_name_receipt_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "generation_request_policy_digest",
    "producer_task_id",
    "dispatch_epoch",
    "source_maximum_bytes",
    "source_expected_media_type",
    "provenance_maximum_bytes",
    "provenance_expected_media_type",
)
_DISPATCH_KEYS: Final = (
    "schema_version",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_capability_authority_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "producer_task_id",
    "dispatch_epoch",
    "call_ceiling",
    "retry_ceiling",
    "concurrency",
    "approved_endpoint_policy_digest",
    "credential_process_boundary_digest",
    "provider_retention_policy_digest",
    "producer_writable_classes",
    "dispatch_state",
    "source_producer_dispatch_digest",
)
_RESERVE_ACTIVATION_KEYS: Final = (
    "schema_version",
    "authority_id",
    "accepted_capability_digest",
    "accepted_e2_plan_sha",
    "accepted_e2_plan_tree",
    "accepted_e2_plan_file_sha256",
    "e1_terminal_head_digest",
    "e1_terminal_event_count",
    "e1_actual_call_count",
    "e2_dispatch_epoch",
    "e2_root_id",
    "e2_root_name_receipt_digest",
    "e2_task_id",
    "e2_producer_task_id",
    "e2_private_namespace_id",
    "reserve_calls_authorized",
    "retry_ceiling",
    "concurrency",
    "total_actual_call_ceiling",
    "allocations",
    "egress_lease_policy",
    "activation_state",
    "reserve_activation_digest",
)
_RESERVE_ALLOCATION_KEYS: Final = (
    "candidate_ordinal",
    "source_output_id",
    "source_name_receipt_digest",
    "provenance_output_id",
    "provenance_name_receipt_digest",
    "prompt_material_digest",
)
_GENERATION_REQUEST_KEYS: Final = (
    "schema_version",
    "reserve_activation_digest",
    "generation_capability_authority_digest",
    "generation_preregistration_digest",
    "e2_root_id",
    "e2_root_name_receipt_digest",
    "producer_task_id",
    "dispatch_epoch",
    "candidate_ordinal",
    "source_output_id",
    "source_name_receipt_digest",
    "provenance_output_id",
    "provenance_name_receipt_digest",
    "prompt_material_digest",
    "requested_call_count",
    "retry_ceiling",
    "concurrency",
    "source_expected_media_type",
    "source_maximum_bytes",
    "request_state",
    "generation_request_digest",
)


@dataclass(frozen=True)
class PreflightOutputNameBinding:
    """Frozen parent, producer and media envelope for one E2 preflight role."""

    producer_task_id: str
    expected_parent_authority: str
    expected_media_type: str
    maximum_bytes: int


@dataclass(frozen=True)
class PreflightParentAuthorities:
    """Validated upstream graph used to derive one receipt parent."""

    preregistration: Mapping[str, object]
    allocation_manifest: Mapping[str, object]
    producer_dispatch: Mapping[str, object]
    reserve_activation: Mapping[str, object]
    generation_requests: Sequence[Mapping[str, object]]


def _preflight_role_envelope(semantic_role: str) -> tuple[str, str, int]:
    if semantic_role == "SOURCE_CANDIDATE":
        return (
            private_registry.SOURCE_PRODUCER_TASK_ID,
            PREFLIGHT_SOURCE_MEDIA_TYPE,
            PREFLIGHT_SOURCE_MAXIMUM_BYTES,
        )
    if semantic_role not in PREFLIGHT_SEMANTIC_ROLES_BY_SEQUENCE:
        _fail("semantic role is not part of the E2 preflight allocation envelope")
    producer_task_id = (
        private_registry.SOURCE_PRODUCER_TASK_ID
        if semantic_role == "SOURCE_PROVENANCE"
        else private_registry.TASK_ID
    )
    return producer_task_id, PREFLIGHT_JSON_MEDIA_TYPE, PREFLIGHT_JSON_MAXIMUM_BYTES


def resolve_preflight_output_name_binding(
    semantic_role: str,
    *,
    generation_capability_authority_digest: str | None = None,
    generation_preregistration_digest: str | None = None,
    source_allocation_manifest_digest: str | None = None,
    source_producer_dispatch_digest: str | None = None,
) -> PreflightOutputNameBinding:
    """Resolve the only accepted parent/media binding for E2 allocations 1..12."""

    if semantic_role == "SOURCE_GENERATION_PREREGISTRATION":
        parent = _digest(
            generation_capability_authority_digest,
            "generation capability authority digest",
        )
        if parent != ACCEPTED_CAPABILITY_DIGEST:
            _fail("generation capability authority digest is not the accepted capability")
    elif semantic_role in {
        "SOURCE_ALLOCATION_MANIFEST",
        "SOURCE_CANDIDATE",
        "SOURCE_PROVENANCE",
    }:
        parent = _digest(
            generation_preregistration_digest,
            "generation preregistration digest",
        )
    elif semantic_role == "SOURCE_PRODUCER_DISPATCH_RECEIPT":
        parent = _digest(
            source_allocation_manifest_digest,
            "source allocation manifest digest",
        )
    elif semantic_role == "NEGATIVE_RECEIPT":
        parent = _digest(
            source_producer_dispatch_digest,
            "source producer dispatch digest",
        )
    else:
        _fail("semantic role is not part of the E2 preflight allocation envelope")

    producer, media_type, maximum_bytes = _preflight_role_envelope(semantic_role)
    return PreflightOutputNameBinding(
        producer_task_id=producer,
        expected_parent_authority=parent,
        expected_media_type=media_type,
        maximum_bytes=maximum_bytes,
    )


def project_preflight_output_name_receipt(
    *,
    root_receipt: Mapping[str, object],
    output_id: str,
    allocation_sequence: int,
    semantic_role: str,
    logical_name: str,
    parent_authorities: PreflightParentAuthorities | None,
    allocated_at_utc: str,
) -> JsonObject:
    """Purely project the exact registry payload before any create-new write."""

    if (
        root_receipt.get("evidence_root_id") != private_registry.EVIDENCE_ROOT_ID
        or root_receipt.get("dispatch_epoch") != private_registry.DISPATCH_EPOCH
    ):
        _fail("root receipt is not bound to E2")
    root_receipt_digest = _digest(root_receipt.get("receipt_digest"), "root receipt digest")
    execution_contract_digest = _digest(
        root_receipt.get("contract_digest"), "execution contract digest"
    )
    private_registry._require_output_id(output_id)
    if (
        type(allocation_sequence) is not int
        or allocation_sequence < 1
        or allocation_sequence > len(PREFLIGHT_SEMANTIC_ROLES_BY_SEQUENCE)
        or PREFLIGHT_SEMANTIC_ROLES_BY_SEQUENCE[allocation_sequence - 1] != semantic_role
    ):
        _fail("allocation sequence and semantic role do not match the E2 preflight matrix")
    binding = _resolve_preflight_binding_from_parent_authorities(semantic_role, parent_authorities)
    destination = private_registry._role_destination(semantic_role)
    private_registry._require_logical_name(logical_name)
    private_registry._require_digest(binding.expected_parent_authority, "expected parent authority")
    private_registry._require_media_type(binding.expected_media_type)
    private_registry._require_timestamp(allocated_at_utc)
    if binding.maximum_bytes < 1 or binding.maximum_bytes > private_registry.MAXIMUM_ROOT_BYTES:
        _fail("maximum bytes are outside the root envelope")
    expected_envelope = _preflight_role_envelope(semantic_role)
    if (
        binding.producer_task_id,
        binding.expected_media_type,
        binding.maximum_bytes,
    ) != expected_envelope:
        _fail("binding differs from the E2 preflight role envelope")
    allowed_tasks: list[JsonValue] = (
        [
            private_registry.TASK_ID,
            private_registry.SOURCE_PRODUCER_TASK_ID,
            private_registry.REVIEW_TASK_ID,
        ]
        if semantic_role in {"SOURCE_CANDIDATE", "SOURCE_PROVENANCE"}
        else [private_registry.TASK_ID, private_registry.REVIEW_TASK_ID]
    )
    if (
        binding.producer_task_id not in allowed_tasks
        or binding.producer_task_id == private_registry.REVIEW_TASK_ID
    ):
        _fail("producer task is not authorized for the semantic role")
    payload: JsonObject = {
        "schema_version": private_registry.OUTPUT_NAME_RECEIPT_SCHEMA,
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt_digest,
        "execution_contract_digest": execution_contract_digest,
        "output_id": output_id,
        "allocation_sequence": allocation_sequence,
        "semantic_role": semantic_role,
        "logical_name": logical_name,
        "producer_task_id": binding.producer_task_id,
        "dispatch_epoch": private_registry.DISPATCH_EPOCH,
        "allowed_tasks": allowed_tasks,
        "expected_parent_authority": binding.expected_parent_authority,
        "expected_media_type": binding.expected_media_type,
        "maximum_bytes": binding.maximum_bytes,
        "relative_destination_class": destination[0],
        "allocated_at_utc": allocated_at_utc,
    }
    payload["name_receipt_digest"] = mirror_demo_digest(
        private_registry.OUTPUT_NAME_RECEIPT_SCHEMA,
        payload,
    )
    return payload


def _resolve_preflight_binding_from_parent_authorities(
    semantic_role: str,
    parent_authorities: PreflightParentAuthorities | None,
) -> PreflightOutputNameBinding:
    if semantic_role == "SOURCE_GENERATION_PREREGISTRATION":
        if parent_authorities is not None:
            _fail("generation preregistration name receipt cannot override its capability parent")
        _capability()
        return resolve_preflight_output_name_binding(
            semantic_role,
            generation_capability_authority_digest=ACCEPTED_CAPABILITY_DIGEST,
        )

    if parent_authorities is None:
        _fail("preflight parent authorities are required for this semantic role")
    if semantic_role in {
        "SOURCE_ALLOCATION_MANIFEST",
        "SOURCE_CANDIDATE",
        "SOURCE_PROVENANCE",
    }:
        preregistration = validate_generation_preregistration_authority(
            parent_authorities.preregistration
        )
        return resolve_preflight_output_name_binding(
            semantic_role,
            generation_preregistration_digest=_digest(
                preregistration["generation_preregistration_digest"],
                "generation preregistration digest",
            ),
        )
    if semantic_role == "SOURCE_PRODUCER_DISPATCH_RECEIPT":
        manifest = validate_source_allocation_manifest(
            parent_authorities.allocation_manifest,
            preregistration=parent_authorities.preregistration,
            reserve_activation=parent_authorities.reserve_activation,
            generation_requests=parent_authorities.generation_requests,
        )
        return resolve_preflight_output_name_binding(
            semantic_role,
            source_allocation_manifest_digest=_digest(
                manifest["source_allocation_manifest_digest"],
                "source allocation manifest digest",
            ),
        )
    if semantic_role == "NEGATIVE_RECEIPT":
        dispatch = validate_source_producer_dispatch(
            parent_authorities.producer_dispatch,
            preregistration=parent_authorities.preregistration,
            allocation_manifest=parent_authorities.allocation_manifest,
            reserve_activation=parent_authorities.reserve_activation,
            generation_requests=parent_authorities.generation_requests,
        )
        return resolve_preflight_output_name_binding(
            semantic_role,
            source_producer_dispatch_digest=_digest(
                dispatch["source_producer_dispatch_digest"],
                "source producer dispatch digest",
            ),
        )
    _fail("semantic role is not part of the E2 preflight allocation envelope")


def _fail(message: str) -> NoReturn:
    raise D02R2Epoch2GenerationError("E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", message)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail(f"{label} is invalid")
    return value


def _exact(value: object, keys: tuple[str, ...], label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or set(value) != set(keys):
        _fail(f"{label} keys drifted")
    return cast(Mapping[str, object], value)


def _strict_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(cast(dict[object, object], right)) and all(
            _strict_equal(item, cast(dict[object, object], right)[key])
            for key, item in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(cast(list[object], right)) and all(
            _strict_equal(a, b) for a, b in zip(left, cast(list[object], right), strict=True)
        )
    return left == right


def _normalize_reserve_activation(value: object) -> dict[str, object]:
    """Restore the accepted E2 validator's construction order after canonical JSON parse."""
    authority = _exact(value, _RESERVE_ACTIVATION_KEYS, "reserve activation")
    allocations = authority["allocations"]
    if not isinstance(allocations, list):
        _fail("reserve activation allocations are invalid")
    normalized_allocations = [
        {
            key: _exact(item, _RESERVE_ALLOCATION_KEYS, "reserve allocation")[key]
            for key in _RESERVE_ALLOCATION_KEYS
        }
        for item in allocations
    ]
    return {
        key: normalized_allocations if key == "allocations" else authority[key]
        for key in _RESERVE_ACTIVATION_KEYS
    }


def _normalize_generation_request(value: object) -> dict[str, object]:
    """Restore accepted request key order without weakening exact-key validation."""
    request = _exact(value, _GENERATION_REQUEST_KEYS, "generation request")
    return {key: request[key] for key in _GENERATION_REQUEST_KEYS}


def _replay(authority: Mapping[str, object], schema: str, digest_key: str, label: str) -> None:
    claimed = _digest(authority[digest_key], f"{label} digest")
    try:
        observed = mirror_demo_digest(
            schema, cast(JsonObject, {k: v for k, v in authority.items() if k != digest_key})
        )
    except (TypeError, ValueError) as error:
        raise D02R2Epoch2GenerationError(
            "E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", f"{label} is not canonical"
        ) from error
    if observed != claimed:
        _fail(f"{label} digest does not replay")


def _capability() -> Mapping[str, object]:
    value = build_generation_capability_authority()
    if value.get("generation_capability_authority_digest") != ACCEPTED_CAPABILITY_DIGEST:
        _fail("accepted capability digest drifted")
    return value


def build_generation_preregistration_authority(
    *, execution_contract_digest: str, root_name_receipt_digest: str, cohort_policy_digest: str
) -> JsonObject:
    """Build the E2 preregistration before output-name allocation."""
    payload: JsonObject = {
        "schema_version": PREREGISTRATION_SCHEMA,
        "execution_contract_digest": _digest(
            execution_contract_digest, "execution contract digest"
        ),
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": _digest(root_name_receipt_digest, "root name receipt digest"),
        "generation_capability_authority_digest": ACCEPTED_CAPABILITY_DIGEST,
        "cohort_policy_digest": _digest(cohort_policy_digest, "cohort policy digest"),
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "source_count": E2_RESERVE_CALLS,
        "ordered_candidate_ordinals": [1, 2, 3, 4],
    }
    payload["generation_preregistration_digest"] = mirror_demo_digest(
        PREREGISTRATION_SCHEMA, payload
    )
    return payload


def validate_generation_preregistration_authority(value: object) -> Mapping[str, object]:
    authority = _exact(value, _PREREGISTRATION_KEYS, "generation preregistration")
    _replay(
        authority,
        PREREGISTRATION_SCHEMA,
        "generation_preregistration_digest",
        "generation preregistration",
    )
    rebuilt = build_generation_preregistration_authority(
        execution_contract_digest=_digest(
            authority["execution_contract_digest"], "execution contract digest"
        ),
        root_name_receipt_digest=_digest(
            authority["root_name_receipt_digest"], "root name receipt digest"
        ),
        cohort_policy_digest=_digest(authority["cohort_policy_digest"], "cohort policy digest"),
    )
    if not _strict_equal(dict(authority), rebuilt):
        _fail("generation preregistration binding drifted")
    return authority


def _allocation_entry(request: Mapping[str, object], preregistration_digest: str) -> JsonObject:
    if request.get("generation_preregistration_digest") != preregistration_digest:
        _fail("request preregistration digest mismatch")
    if request.get("generation_capability_authority_digest") != ACCEPTED_CAPABILITY_DIGEST:
        _fail("request capability digest mismatch")
    if (
        request.get("e2_root_id") != E2_ROOT_ID
        or request.get("e2_root_name_receipt_digest") is None
        or request.get("producer_task_id") != E2_PRODUCER_TASK_ID
        or request.get("dispatch_epoch") != E2_DISPATCH_EPOCH
    ):
        _fail("request E2 identity tuple mismatch")
    return {
        "candidate_ordinal": cast(JsonScalar, request["candidate_ordinal"]),
        "source_output_id": cast(JsonScalar, request["source_output_id"]),
        "output_name_receipt_digest": cast(JsonScalar, request["source_name_receipt_digest"]),
        "source_provenance_output_id": cast(JsonScalar, request["provenance_output_id"]),
        "source_provenance_name_receipt_digest": cast(
            JsonScalar, request["provenance_name_receipt_digest"]
        ),
        # Compatibility field: E2 request digest, never an E1 policy digest.
        "generation_request_policy_digest": cast(JsonScalar, request["generation_request_digest"]),
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "source_maximum_bytes": cast(JsonScalar, request["source_maximum_bytes"]),
        "source_expected_media_type": cast(JsonScalar, request["source_expected_media_type"]),
        "provenance_maximum_bytes": 262_144,
        "provenance_expected_media_type": "application/json",
    }


def build_source_allocation_manifest(
    *,
    execution_contract_digest: str,
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
) -> JsonObject:
    """Bridge four verified E2 requests into the legacy-shaped allocation manifest."""
    prereg = validate_generation_preregistration_authority(dict(preregistration))
    contract_digest = _digest(execution_contract_digest, "execution contract digest")
    if prereg["execution_contract_digest"] != contract_digest:
        _fail("allocation execution contract does not match preregistration")
    prereg_digest = _digest(
        prereg["generation_preregistration_digest"], "generation preregistration digest"
    )
    normalized_activation = _normalize_reserve_activation(reserve_activation)
    requests = [
        validate_generation_request(
            _normalize_generation_request(item), reserve_activation=normalized_activation
        )
        for item in generation_requests
    ]
    if len(requests) != E2_RESERVE_CALLS:
        _fail("exactly four generation requests are required")
    for request in requests:
        if request["e2_root_name_receipt_digest"] != prereg["root_name_receipt_digest"]:
            _fail("request root name receipt does not match preregistration")
    entries = [_allocation_entry(item, prereg_digest) for item in requests]
    if [entry["candidate_ordinal"] for entry in entries] != [1, 2, 3, 4]:
        _fail("generation requests must be ordered ordinals 1 through 4")
    payload: JsonObject = {
        "schema_version": ALLOCATION_MANIFEST_SCHEMA,
        "execution_contract_digest": contract_digest,
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": cast(JsonScalar, prereg["root_name_receipt_digest"]),
        "generation_preregistration_digest": prereg_digest,
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "source_count": E2_RESERVE_CALLS,
        "ordered_allocations": cast(list[JsonValue], entries),
    }
    payload["source_allocation_manifest_digest"] = mirror_demo_digest(
        ALLOCATION_MANIFEST_SCHEMA, payload
    )
    return payload


def validate_source_allocation_manifest(
    value: object,
    *,
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    manifest = _exact(value, _ALLOCATION_KEYS, "source allocation manifest")
    _replay(
        manifest,
        ALLOCATION_MANIFEST_SCHEMA,
        "source_allocation_manifest_digest",
        "source allocation manifest",
    )
    entries = manifest["ordered_allocations"]
    if not isinstance(entries, list) or len(entries) != E2_RESERVE_CALLS:
        _fail("allocation cardinality is invalid")
    for entry in entries:
        _exact(entry, _ALLOCATION_ENTRY_KEYS, "allocation entry")
    rebuilt = build_source_allocation_manifest(
        execution_contract_digest=_digest(
            manifest["execution_contract_digest"], "execution contract digest"
        ),
        preregistration=preregistration,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
    )
    if not _strict_equal(dict(manifest), rebuilt):
        _fail("allocation manifest does not exactly bridge E2 requests")
    return manifest


def build_source_producer_dispatch(
    *,
    execution_contract_digest: str,
    preregistration: Mapping[str, object],
    allocation_manifest: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
) -> JsonObject:
    prereg = validate_generation_preregistration_authority(dict(preregistration))
    manifest = validate_source_allocation_manifest(
        dict(allocation_manifest),
        preregistration=prereg,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
    )
    contract_digest = _digest(execution_contract_digest, "execution contract digest")
    if (
        prereg["execution_contract_digest"] != contract_digest
        or manifest["execution_contract_digest"] != contract_digest
    ):
        _fail("dispatch execution contract does not match preregistration and allocation")
    if manifest["generation_preregistration_digest"] != prereg["generation_preregistration_digest"]:
        _fail("dispatch preregistration binding mismatch")
    capability = _capability()
    payload: JsonObject = {
        "schema_version": PRODUCER_DISPATCH_SCHEMA,
        "execution_contract_digest": contract_digest,
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": cast(JsonScalar, prereg["root_name_receipt_digest"]),
        "generation_capability_authority_digest": ACCEPTED_CAPABILITY_DIGEST,
        "generation_preregistration_digest": cast(
            JsonScalar, prereg["generation_preregistration_digest"]
        ),
        "source_allocation_manifest_digest": cast(
            JsonScalar, manifest["source_allocation_manifest_digest"]
        ),
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "call_ceiling": E2_RESERVE_CALLS,
        "retry_ceiling": E2_RETRY_CEILING,
        "concurrency": E2_CONCURRENCY,
        "approved_endpoint_policy_digest": cast(
            JsonScalar, capability["approved_endpoint_policy_digest"]
        ),
        "credential_process_boundary_digest": cast(
            JsonScalar, capability["credential_process_boundary_digest"]
        ),
        "provider_retention_policy_digest": cast(
            JsonScalar, capability["provider_retention_policy_digest"]
        ),
        "producer_writable_classes": ["DATA_SOURCE_CANDIDATES", "DATA_SOURCE_PROVENANCE"],
        "dispatch_state": "AUTHORIZED_EXACT_ALLOCATIONS_ONLY",
    }
    payload["source_producer_dispatch_digest"] = mirror_demo_digest(
        PRODUCER_DISPATCH_SCHEMA, payload
    )
    return payload


def validate_source_producer_dispatch(
    value: object,
    *,
    preregistration: Mapping[str, object],
    allocation_manifest: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    dispatch = _exact(value, _DISPATCH_KEYS, "source producer dispatch")
    _replay(
        dispatch,
        PRODUCER_DISPATCH_SCHEMA,
        "source_producer_dispatch_digest",
        "source producer dispatch",
    )
    rebuilt = build_source_producer_dispatch(
        execution_contract_digest=_digest(
            dispatch["execution_contract_digest"], "execution contract digest"
        ),
        preregistration=preregistration,
        allocation_manifest=allocation_manifest,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
    )
    if not _strict_equal(dict(dispatch), rebuilt):
        _fail("source producer dispatch binding drifted")
    return dispatch


def validate_generation_receipt_request_binding(
    receipt: Mapping[str, object],
    *,
    generation_request: Mapping[str, object],
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
    allocation_manifest: Mapping[str, object],
    producer_dispatch: Mapping[str, object],
) -> None:
    """Bind one receipt to a validated E2 request and its accepted allocation chain."""
    prereg = validate_generation_preregistration_authority(dict(preregistration))
    normalized_activation = _normalize_reserve_activation(reserve_activation)
    requests = [
        validate_generation_request(
            _normalize_generation_request(item), reserve_activation=normalized_activation
        )
        for item in generation_requests
    ]
    manifest = validate_source_allocation_manifest(
        dict(allocation_manifest),
        preregistration=prereg,
        reserve_activation=normalized_activation,
        generation_requests=requests,
    )
    dispatch = validate_source_producer_dispatch(
        dict(producer_dispatch),
        preregistration=prereg,
        allocation_manifest=manifest,
        reserve_activation=normalized_activation,
        generation_requests=requests,
    )
    request = validate_generation_request(
        _normalize_generation_request(generation_request),
        reserve_activation=normalized_activation,
    )
    ordinal = request["candidate_ordinal"]
    if type(ordinal) is not int or ordinal not in {1, 2, 3, 4}:
        _fail("generation receipt request ordinal is invalid")
    if len(requests) != E2_RESERVE_CALLS or not _strict_equal(
        dict(request), dict(requests[ordinal - 1])
    ):
        _fail("generation receipt request is not the manifest request member")
    entries = cast(list[object], manifest["ordered_allocations"])
    entry = _exact(entries[ordinal - 1], _ALLOCATION_ENTRY_KEYS, "receipt allocation entry")
    expected_entry = _allocation_entry(
        request,
        _digest(prereg["generation_preregistration_digest"], "preregistration digest"),
    )
    if not _strict_equal(dict(entry), expected_entry):
        _fail("generation receipt allocation entry does not bind the E2 request")
    expected = {
        "generation_request_policy_digest": request.get("generation_request_digest"),
        "candidate_ordinal": request.get("candidate_ordinal"),
        "execution_contract_digest": manifest.get("execution_contract_digest"),
        "evidence_root_id": request.get("e2_root_id"),
        "root_name_receipt_digest": prereg.get("root_name_receipt_digest"),
        "generation_capability_authority_digest": request.get(
            "generation_capability_authority_digest"
        ),
        "generation_preregistration_digest": request.get("generation_preregistration_digest"),
        "source_allocation_manifest_digest": manifest.get("source_allocation_manifest_digest"),
        "source_producer_dispatch_digest": dispatch.get("source_producer_dispatch_digest"),
        "producer_task_id": request.get("producer_task_id"),
        "dispatch_epoch": request.get("dispatch_epoch"),
        "source_output_id": request.get("source_output_id"),
        "output_name_receipt_digest": request.get("source_name_receipt_digest"),
        "source_provenance_output_id": request.get("provenance_output_id"),
        "source_provenance_name_receipt_digest": request.get("provenance_name_receipt_digest"),
    }
    for key, expected_value in expected.items():
        if key not in receipt or receipt[key] != expected_value:
            _fail(f"generation receipt {key} does not bind the E2 request")
