"""Exact Epoch 02 provenance and source-generation receipt authority.

The module is deliberately pure.  It validates the already accepted E2
request/allocation graph plus registry receipt projections, but never resolves
an evidence root, opens a file, invokes a provider, or mutates a registry.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_r2_private_registry_e2 as private_registry
from mirror_api.demo_d02_r2_epoch2_request_bridge import (
    PREFLIGHT_JSON_MAXIMUM_BYTES,
    PREFLIGHT_JSON_MEDIA_TYPE,
    PREFLIGHT_SOURCE_MAXIMUM_BYTES,
    PREFLIGHT_SOURCE_MEDIA_TYPE,
    validate_generation_receipt_request_binding,
)
from mirror_api.demo_d02_r2_generation_epoch2 import (
    ACCEPTED_CAPABILITY_DIGEST,
    E2_DISPATCH_EPOCH,
    E2_PRODUCER_TASK_ID,
    E2_ROOT_ID,
)
from mirror_api.demo_measurement_quality import canonical_json_bytes, mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

PROVENANCE_SCHEMA: Final = "mirror.demo/D02R2Epoch2GenerationResultProvenance/v1"
GENERATION_RECEIPT_SCHEMA: Final = "mirror.demo/D02R2Epoch2SourceGenerationReceipt/v1"

CONTROL_PLANE_INVOCATION: Final = "image_gen.imagegen"
PUBLIC_EGRESS_DURING_CALL: Final = "ORDINAL_SCOPED_CONTROL_PLANE_LEASE_ONLY"
PUBLIC_EGRESS_AFTER_CALL: Final = "DENIED"
CONTROL_PLANE_LEASE_STATE: Final = "REVOKED"
GENERATION_RESULT_STATE: Final = "VALID_PNG_DURABLE_AND_SOURCE_REGISTERED"

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_LOGICAL_NAME_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}\Z")
_UTC_RE: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z\Z")

_NAME_RECEIPT_KEYS: Final = (
    "schema_version",
    "evidence_root_id",
    "root_name_receipt_digest",
    "execution_contract_digest",
    "output_id",
    "allocation_sequence",
    "semantic_role",
    "logical_name",
    "producer_task_id",
    "dispatch_epoch",
    "allowed_tasks",
    "expected_parent_authority",
    "expected_media_type",
    "maximum_bytes",
    "relative_destination_class",
    "allocated_at_utc",
    "name_receipt_digest",
)
_SEAL_RECEIPT_KEYS: Final = (
    "schema_version",
    "evidence_root_id",
    "root_name_receipt_digest",
    "execution_contract_digest",
    "output_id",
    "name_receipt_digest",
    "semantic_role",
    "producer_task_id",
    "actual_sha256",
    "byte_size",
    "media_type",
    "authority_digest",
    "retention",
    "custody",
    "sealed_at_utc",
    "seal_digest",
)
_COMMIT_RECEIPT_KEYS: Final = (
    "schema_version",
    "evidence_root_id",
    "root_name_receipt_digest",
    "execution_contract_digest",
    "transaction_id",
    "intent_digest",
    "output_id",
    "canonical_event_digest",
    "copy_a_event_count",
    "copy_a_head_event_digest",
    "copy_a_semantic_snapshot_digest",
    "copy_b_event_count",
    "copy_b_head_event_digest",
    "copy_b_semantic_snapshot_digest",
    "commit_state",
    "created_at_utc",
    "commit_receipt_digest",
)
_PROVENANCE_KEYS: Final = (
    "schema_version",
    "candidate_ordinal",
    "producer_task_id",
    "dispatch_epoch",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "source_output_id",
    "source_name_receipt_digest",
    "source_seal_receipt_digest",
    "source_registry_commit_receipt_digest",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "control_plane_invocation",
    "call_count",
    "outputs_per_call",
    "retry_count",
    "reference_image_count",
    "provider_id",
    "model_id",
    "model_version",
    "seed",
    "usage",
    "cost",
    "public_internet_egress_during_call",
    "public_internet_egress_after_call",
    "control_plane_lease_state",
    "generation_result_state",
    "synthetic_only_attested",
    "real_person_reference_used",
    "provenance_digest",
)
_GENERATION_RECEIPT_KEYS: Final = (
    "schema_version",
    "candidate_ordinal",
    "producer_task_id",
    "source_producer_task_id",
    "dispatch_epoch",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_output_id",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "generation_result_provenance_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "synthetic_only_attested",
    "real_person_reference_used",
    "receipt_digest",
)


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _exact(value: object, keys: tuple[str, ...], label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or set(value) != set(keys):
        _fail(f"{label} keys drifted")
    return cast(Mapping[str, object], value)


def _strict_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        right_mapping = cast(dict[object, object], right)
        return set(left) == set(right_mapping) and all(
            _strict_equal(item, right_mapping[key]) for key, item in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(cast(list[object], right)) and all(
            _strict_equal(a, b) for a, b in zip(left, cast(list[object], right), strict=True)
        )
    return left == right


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail(f"{label} is not a lowercase SHA-256 digest")
    return value


def _output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT_ID_RE.fullmatch(value) is None:
        _fail(f"{label} does not match the opaque output-ID grammar")
    return value


def _positive_int(value: object, label: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        _fail(f"{label} is invalid")
    return value


def _timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        _fail(f"{label} must be canonical UTC with six fractional digits")
    return value


def _replay(authority: Mapping[str, object], *, schema: str, digest_key: str, label: str) -> None:
    claimed = _digest(authority[digest_key], f"{label} digest")
    payload = cast(
        JsonObject, {key: value for key, value in authority.items() if key != digest_key}
    )
    try:
        observed = mirror_demo_digest(schema, payload)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not canonical") from error
    if observed != claimed:
        _fail(f"{label} digest does not replay")


def _request_graph(
    *,
    generation_request: Mapping[str, object],
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
    allocation_manifest: Mapping[str, object],
    producer_dispatch: Mapping[str, object],
) -> Mapping[str, object]:
    core_binding = {
        "generation_request_policy_digest": generation_request.get("generation_request_digest"),
        "candidate_ordinal": generation_request.get("candidate_ordinal"),
        "execution_contract_digest": allocation_manifest.get("execution_contract_digest"),
        "evidence_root_id": generation_request.get("e2_root_id"),
        "root_name_receipt_digest": preregistration.get("root_name_receipt_digest"),
        "generation_capability_authority_digest": generation_request.get(
            "generation_capability_authority_digest"
        ),
        "generation_preregistration_digest": generation_request.get(
            "generation_preregistration_digest"
        ),
        "source_allocation_manifest_digest": allocation_manifest.get(
            "source_allocation_manifest_digest"
        ),
        "source_producer_dispatch_digest": producer_dispatch.get("source_producer_dispatch_digest"),
        "producer_task_id": private_registry.TASK_ID,
        "source_producer_task_id": generation_request.get("producer_task_id"),
        "dispatch_epoch": generation_request.get("dispatch_epoch"),
        "source_output_id": generation_request.get("source_output_id"),
        "output_name_receipt_digest": generation_request.get("source_name_receipt_digest"),
        "source_provenance_output_id": generation_request.get("provenance_output_id"),
        "source_provenance_name_receipt_digest": generation_request.get(
            "provenance_name_receipt_digest"
        ),
    }
    validate_generation_receipt_request_binding(
        core_binding,
        generation_request=generation_request,
        preregistration=preregistration,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
        allocation_manifest=allocation_manifest,
        producer_dispatch=producer_dispatch,
    )
    return generation_request


def _validate_name_receipt(
    value: object,
    *,
    expected_output_id: str,
    expected_sequence: int,
    expected_role: str,
    expected_producer: str,
    expected_parent: str,
    expected_media_type: str,
    expected_maximum_bytes: int,
    expected_root_name_receipt_digest: str,
    expected_execution_contract_digest: str,
) -> Mapping[str, object]:
    receipt = _exact(value, _NAME_RECEIPT_KEYS, "output name receipt")
    if receipt["schema_version"] != private_registry.OUTPUT_NAME_RECEIPT_SCHEMA:
        _fail("output name receipt schema is invalid")
    _replay(
        receipt,
        schema=private_registry.OUTPUT_NAME_RECEIPT_SCHEMA,
        digest_key="name_receipt_digest",
        label="output name receipt",
    )
    allowed_tasks = (
        [
            private_registry.TASK_ID,
            private_registry.SOURCE_PRODUCER_TASK_ID,
            private_registry.REVIEW_TASK_ID,
        ]
        if expected_role in {"SOURCE_CANDIDATE", "SOURCE_PROVENANCE"}
        else [private_registry.TASK_ID, private_registry.REVIEW_TASK_ID]
    )
    expected = {
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": expected_root_name_receipt_digest,
        "execution_contract_digest": expected_execution_contract_digest,
        "output_id": expected_output_id,
        "allocation_sequence": expected_sequence,
        "semantic_role": expected_role,
        "producer_task_id": expected_producer,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "allowed_tasks": allowed_tasks,
        "expected_parent_authority": expected_parent,
        "expected_media_type": expected_media_type,
        "maximum_bytes": expected_maximum_bytes,
        "relative_destination_class": private_registry.ROLE_DESTINATIONS[expected_role][0],
    }
    for key, expected_value in expected.items():
        if not _strict_equal(receipt[key], expected_value):
            _fail(f"output name receipt {key} binding drifted")
    _output_id(receipt["output_id"], "output name receipt output ID")
    logical_name = receipt["logical_name"]
    if (
        not isinstance(logical_name, str)
        or _LOGICAL_NAME_RE.fullmatch(logical_name) is None
        or logical_name in {".", ".."}
        or ":" in logical_name
    ):
        _fail("output name receipt logical name is invalid")
    _timestamp(receipt["allocated_at_utc"], "output allocation timestamp")
    return receipt


def _validate_seal_receipt(
    value: object,
    *,
    name_receipt: Mapping[str, object],
    expected_actual_sha256: str,
    expected_byte_size: int,
    expected_media_type: str,
    expected_authority_digest: str,
) -> Mapping[str, object]:
    receipt = _exact(value, _SEAL_RECEIPT_KEYS, "output seal receipt")
    if receipt["schema_version"] != private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA:
        _fail("output seal receipt schema is invalid")
    _replay(
        receipt,
        schema=private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA,
        digest_key="seal_digest",
        label="output seal receipt",
    )
    expected = {
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": name_receipt["root_name_receipt_digest"],
        "execution_contract_digest": name_receipt["execution_contract_digest"],
        "output_id": name_receipt["output_id"],
        "name_receipt_digest": name_receipt["name_receipt_digest"],
        "semantic_role": name_receipt["semantic_role"],
        "producer_task_id": name_receipt["producer_task_id"],
        "actual_sha256": expected_actual_sha256,
        "byte_size": expected_byte_size,
        "media_type": expected_media_type,
        "authority_digest": expected_authority_digest,
        "retention": private_registry.RETENTION_POLICY,
        "custody": private_registry.DEFAULT_CUSTODY,
    }
    for key, expected_value in expected.items():
        if receipt[key] != expected_value:
            _fail(f"output seal receipt {key} binding drifted")
    _timestamp(receipt["sealed_at_utc"], "output seal timestamp")
    return receipt


def _validate_commit_receipt(
    value: object,
    *,
    name_receipt: Mapping[str, object],
    seal_receipt: Mapping[str, object],
    expected_event_count: int,
) -> Mapping[str, object]:
    receipt = _exact(value, _COMMIT_RECEIPT_KEYS, "registry commit receipt")
    if receipt["schema_version"] != private_registry.REGISTRY_COMMIT_SCHEMA:
        _fail("registry commit receipt schema is invalid")
    _replay(
        receipt,
        schema=private_registry.REGISTRY_COMMIT_SCHEMA,
        digest_key="commit_receipt_digest",
        label="registry commit receipt",
    )
    transaction_id = mirror_demo_digest(
        private_registry.REGISTRY_TRANSACTION_ID_SCHEMA,
        {
            "evidence_root_id": E2_ROOT_ID,
            "root_name_receipt_digest": cast(JsonValue, name_receipt["root_name_receipt_digest"]),
            "execution_contract_digest": cast(JsonValue, name_receipt["execution_contract_digest"]),
            "output_id": cast(JsonValue, name_receipt["output_id"]),
            "name_receipt_digest": cast(JsonValue, name_receipt["name_receipt_digest"]),
            "seal_receipt_digest": cast(JsonValue, seal_receipt["seal_digest"]),
        },
    )
    expected = {
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": name_receipt["root_name_receipt_digest"],
        "execution_contract_digest": name_receipt["execution_contract_digest"],
        "transaction_id": transaction_id,
        "output_id": name_receipt["output_id"],
        "copy_a_event_count": expected_event_count,
        "copy_b_event_count": expected_event_count,
        "commit_state": "COMMITTED_BOTH_COPIES",
    }
    for key, expected_value in expected.items():
        if receipt[key] != expected_value:
            _fail(f"registry commit receipt {key} binding drifted")
    for key in (
        "intent_digest",
        "canonical_event_digest",
        "copy_a_head_event_digest",
        "copy_a_semantic_snapshot_digest",
        "copy_b_head_event_digest",
        "copy_b_semantic_snapshot_digest",
    ):
        _digest(receipt[key], f"registry commit receipt {key}")
    if (
        receipt["copy_a_head_event_digest"] != receipt["copy_b_head_event_digest"]
        or receipt["copy_a_semantic_snapshot_digest"] != receipt["copy_b_semantic_snapshot_digest"]
    ):
        _fail("registry commit receipt copies disagree")
    _timestamp(receipt["created_at_utc"], "registry commit timestamp")
    return receipt


def _source_and_provenance_names(
    *,
    request: Mapping[str, object],
    preregistration: Mapping[str, object],
    source_name_receipt: Mapping[str, object],
    provenance_name_receipt: Mapping[str, object],
) -> tuple[int, Mapping[str, object], Mapping[str, object]]:
    ordinal = _positive_int(request.get("candidate_ordinal"), "candidate ordinal", 4)
    root_digest = _digest(
        preregistration.get("root_name_receipt_digest"), "root name receipt digest"
    )
    contract_digest = _digest(
        preregistration.get("execution_contract_digest"), "execution contract digest"
    )
    prereg_digest = _digest(
        preregistration.get("generation_preregistration_digest"),
        "generation preregistration digest",
    )
    source_name = _validate_name_receipt(
        source_name_receipt,
        expected_output_id=_output_id(request.get("source_output_id"), "source output ID"),
        expected_sequence=4 + (ordinal - 1) * 2,
        expected_role="SOURCE_CANDIDATE",
        expected_producer=E2_PRODUCER_TASK_ID,
        expected_parent=prereg_digest,
        expected_media_type=PREFLIGHT_SOURCE_MEDIA_TYPE,
        expected_maximum_bytes=PREFLIGHT_SOURCE_MAXIMUM_BYTES,
        expected_root_name_receipt_digest=root_digest,
        expected_execution_contract_digest=contract_digest,
    )
    provenance_name = _validate_name_receipt(
        provenance_name_receipt,
        expected_output_id=_output_id(request.get("provenance_output_id"), "provenance output ID"),
        expected_sequence=5 + (ordinal - 1) * 2,
        expected_role="SOURCE_PROVENANCE",
        expected_producer=E2_PRODUCER_TASK_ID,
        expected_parent=prereg_digest,
        expected_media_type=PREFLIGHT_JSON_MEDIA_TYPE,
        expected_maximum_bytes=PREFLIGHT_JSON_MAXIMUM_BYTES,
        expected_root_name_receipt_digest=root_digest,
        expected_execution_contract_digest=contract_digest,
    )
    if source_name["name_receipt_digest"] != request.get("source_name_receipt_digest"):
        _fail("source name receipt does not equal the E2 request")
    if provenance_name["name_receipt_digest"] != request.get("provenance_name_receipt_digest"):
        _fail("provenance name receipt does not equal the E2 request")
    return ordinal, source_name, provenance_name


def build_generation_result_provenance(
    *,
    generation_request: Mapping[str, object],
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
    allocation_manifest: Mapping[str, object],
    producer_dispatch: Mapping[str, object],
    source_name_receipt: Mapping[str, object],
    source_seal_receipt: Mapping[str, object],
    source_commit_receipt: Mapping[str, object],
    provenance_name_receipt: Mapping[str, object],
    source_asset_sha256: str,
    source_asset_byte_size: int,
    source_asset_width: int,
    source_asset_height: int,
) -> JsonObject:
    """Build the E2 provenance after the source output is durably registered."""

    request = _request_graph(
        generation_request=generation_request,
        preregistration=preregistration,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
        allocation_manifest=allocation_manifest,
        producer_dispatch=producer_dispatch,
    )
    ordinal, source_name, _ = _source_and_provenance_names(
        request=request,
        preregistration=preregistration,
        source_name_receipt=source_name_receipt,
        provenance_name_receipt=provenance_name_receipt,
    )
    source_sha = _digest(source_asset_sha256, "source Asset checksum")
    source_size = _positive_int(
        source_asset_byte_size, "source Asset byte size", PREFLIGHT_SOURCE_MAXIMUM_BYTES
    )
    width = _positive_int(source_asset_width, "source Asset width", 8_192)
    height = _positive_int(source_asset_height, "source Asset height", 8_192)
    if width < 64 or height < 64 or width * height > 40_000_000:
        _fail("source Asset dimensions are outside the receiver envelope")
    binary_authority_digest = mirror_demo_digest(
        private_registry.SEALED_BINARY_AUTHORITY_SCHEMA,
        {
            "semantic_role": "SOURCE_CANDIDATE",
            "actual_sha256": source_sha,
            "byte_size": source_size,
            "media_type": PREFLIGHT_SOURCE_MEDIA_TYPE,
            "name_receipt_digest": cast(JsonValue, source_name["name_receipt_digest"]),
        },
    )
    source_seal = _validate_seal_receipt(
        source_seal_receipt,
        name_receipt=source_name,
        expected_actual_sha256=source_sha,
        expected_byte_size=source_size,
        expected_media_type=PREFLIGHT_SOURCE_MEDIA_TYPE,
        expected_authority_digest=binary_authority_digest,
    )
    source_commit = _validate_commit_receipt(
        source_commit_receipt,
        name_receipt=source_name,
        seal_receipt=source_seal,
        expected_event_count=3 * ordinal + 1,
    )
    payload: JsonObject = {
        "schema_version": PROVENANCE_SCHEMA,
        "candidate_ordinal": ordinal,
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "execution_contract_digest": cast(
            JsonScalar, allocation_manifest["execution_contract_digest"]
        ),
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": cast(JsonScalar, preregistration["root_name_receipt_digest"]),
        "generation_preregistration_digest": cast(
            JsonScalar, preregistration["generation_preregistration_digest"]
        ),
        "source_allocation_manifest_digest": cast(
            JsonScalar, allocation_manifest["source_allocation_manifest_digest"]
        ),
        "source_producer_dispatch_digest": cast(
            JsonScalar, producer_dispatch["source_producer_dispatch_digest"]
        ),
        "generation_capability_authority_digest": ACCEPTED_CAPABILITY_DIGEST,
        "generation_request_policy_digest": cast(JsonScalar, request["generation_request_digest"]),
        "source_output_id": cast(JsonScalar, request["source_output_id"]),
        "source_name_receipt_digest": cast(JsonScalar, source_name["name_receipt_digest"]),
        "source_seal_receipt_digest": cast(JsonScalar, source_seal["seal_digest"]),
        "source_registry_commit_receipt_digest": cast(
            JsonScalar, source_commit["commit_receipt_digest"]
        ),
        "source_asset_sha256": source_sha,
        "source_asset_byte_size": source_size,
        "source_asset_mime_type": PREFLIGHT_SOURCE_MEDIA_TYPE,
        "source_asset_width": width,
        "source_asset_height": height,
        "control_plane_invocation": CONTROL_PLANE_INVOCATION,
        "call_count": 1,
        "outputs_per_call": 1,
        "retry_count": 0,
        "reference_image_count": 0,
        "provider_id": None,
        "model_id": None,
        "model_version": None,
        "seed": None,
        "usage": None,
        "cost": None,
        "public_internet_egress_during_call": PUBLIC_EGRESS_DURING_CALL,
        "public_internet_egress_after_call": PUBLIC_EGRESS_AFTER_CALL,
        "control_plane_lease_state": CONTROL_PLANE_LEASE_STATE,
        "generation_result_state": GENERATION_RESULT_STATE,
        "synthetic_only_attested": True,
        "real_person_reference_used": False,
    }
    payload["provenance_digest"] = mirror_demo_digest(PROVENANCE_SCHEMA, payload)
    return payload


def validate_generation_result_provenance(
    value: object,
    *,
    generation_request: Mapping[str, object],
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
    allocation_manifest: Mapping[str, object],
    producer_dispatch: Mapping[str, object],
    source_name_receipt: Mapping[str, object],
    source_seal_receipt: Mapping[str, object],
    source_commit_receipt: Mapping[str, object],
    provenance_name_receipt: Mapping[str, object],
) -> Mapping[str, object]:
    provenance = _exact(value, _PROVENANCE_KEYS, "E2 generation provenance")
    if provenance["schema_version"] != PROVENANCE_SCHEMA:
        _fail("E2 generation provenance schema is invalid")
    _replay(
        provenance,
        schema=PROVENANCE_SCHEMA,
        digest_key="provenance_digest",
        label="E2 generation provenance",
    )
    rebuilt = build_generation_result_provenance(
        generation_request=generation_request,
        preregistration=preregistration,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
        allocation_manifest=allocation_manifest,
        producer_dispatch=producer_dispatch,
        source_name_receipt=source_name_receipt,
        source_seal_receipt=source_seal_receipt,
        source_commit_receipt=source_commit_receipt,
        provenance_name_receipt=provenance_name_receipt,
        source_asset_sha256=_digest(provenance["source_asset_sha256"], "source Asset checksum"),
        source_asset_byte_size=_positive_int(
            provenance["source_asset_byte_size"],
            "source Asset byte size",
            PREFLIGHT_SOURCE_MAXIMUM_BYTES,
        ),
        source_asset_width=_positive_int(
            provenance["source_asset_width"], "source Asset width", 8_192
        ),
        source_asset_height=_positive_int(
            provenance["source_asset_height"], "source Asset height", 8_192
        ),
    )
    if not _strict_equal(dict(provenance), rebuilt):
        _fail("E2 generation provenance binding drifted")
    return provenance


def build_source_generation_receipt(
    *,
    generation_request: Mapping[str, object],
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
    allocation_manifest: Mapping[str, object],
    producer_dispatch: Mapping[str, object],
    source_name_receipt: Mapping[str, object],
    source_seal_receipt: Mapping[str, object],
    source_commit_receipt: Mapping[str, object],
    provenance: Mapping[str, object],
    provenance_name_receipt: Mapping[str, object],
    provenance_seal_receipt: Mapping[str, object],
    provenance_commit_receipt: Mapping[str, object],
) -> JsonObject:
    """Build the receipt after source and provenance commits are durable."""

    request = _request_graph(
        generation_request=generation_request,
        preregistration=preregistration,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
        allocation_manifest=allocation_manifest,
        producer_dispatch=producer_dispatch,
    )
    ordinal, source_name, provenance_name = _source_and_provenance_names(
        request=request,
        preregistration=preregistration,
        source_name_receipt=source_name_receipt,
        provenance_name_receipt=provenance_name_receipt,
    )
    verified_provenance = validate_generation_result_provenance(
        dict(provenance),
        generation_request=generation_request,
        preregistration=preregistration,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
        allocation_manifest=allocation_manifest,
        producer_dispatch=producer_dispatch,
        source_name_receipt=source_name_receipt,
        source_seal_receipt=source_seal_receipt,
        source_commit_receipt=source_commit_receipt,
        provenance_name_receipt=provenance_name_receipt,
    )
    provenance_bytes = canonical_json_bytes(verified_provenance)
    provenance_digest = _digest(
        verified_provenance["provenance_digest"], "generation provenance digest"
    )
    provenance_seal = _validate_seal_receipt(
        provenance_seal_receipt,
        name_receipt=provenance_name,
        expected_actual_sha256=hashlib.sha256(provenance_bytes).hexdigest(),
        expected_byte_size=len(provenance_bytes),
        expected_media_type=PREFLIGHT_JSON_MEDIA_TYPE,
        expected_authority_digest=provenance_digest,
    )
    provenance_commit = _validate_commit_receipt(
        provenance_commit_receipt,
        name_receipt=provenance_name,
        seal_receipt=provenance_seal,
        expected_event_count=3 * ordinal + 2,
    )
    source_seal = _exact(source_seal_receipt, _SEAL_RECEIPT_KEYS, "source seal receipt")
    source_commit = _exact(
        source_commit_receipt, _COMMIT_RECEIPT_KEYS, "source registry commit receipt"
    )
    payload: JsonObject = {
        "schema_version": GENERATION_RECEIPT_SCHEMA,
        "candidate_ordinal": ordinal,
        "producer_task_id": private_registry.TASK_ID,
        "source_producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "execution_contract_digest": cast(
            JsonScalar, allocation_manifest["execution_contract_digest"]
        ),
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": cast(JsonScalar, preregistration["root_name_receipt_digest"]),
        "generation_preregistration_digest": cast(
            JsonScalar, preregistration["generation_preregistration_digest"]
        ),
        "source_allocation_manifest_digest": cast(
            JsonScalar, allocation_manifest["source_allocation_manifest_digest"]
        ),
        "source_producer_dispatch_digest": cast(
            JsonScalar, producer_dispatch["source_producer_dispatch_digest"]
        ),
        "source_output_id": cast(JsonScalar, request["source_output_id"]),
        "output_name_receipt_digest": cast(JsonScalar, source_name["name_receipt_digest"]),
        "output_seal_receipt_digest": cast(JsonScalar, source_seal["seal_digest"]),
        "registry_commit_receipt_digest": cast(JsonScalar, source_commit["commit_receipt_digest"]),
        "generation_capability_authority_digest": ACCEPTED_CAPABILITY_DIGEST,
        "generation_request_policy_digest": cast(JsonScalar, request["generation_request_digest"]),
        "generation_result_provenance_digest": provenance_digest,
        "source_provenance_output_id": cast(JsonScalar, request["provenance_output_id"]),
        "source_provenance_name_receipt_digest": cast(
            JsonScalar, provenance_name["name_receipt_digest"]
        ),
        "source_provenance_seal_receipt_digest": cast(JsonScalar, provenance_seal["seal_digest"]),
        "source_provenance_registry_commit_receipt_digest": cast(
            JsonScalar, provenance_commit["commit_receipt_digest"]
        ),
        "source_asset_sha256": cast(JsonScalar, verified_provenance["source_asset_sha256"]),
        "source_asset_byte_size": cast(JsonScalar, verified_provenance["source_asset_byte_size"]),
        "source_asset_mime_type": PREFLIGHT_SOURCE_MEDIA_TYPE,
        "source_asset_width": cast(JsonScalar, verified_provenance["source_asset_width"]),
        "source_asset_height": cast(JsonScalar, verified_provenance["source_asset_height"]),
        "synthetic_only_attested": True,
        "real_person_reference_used": False,
    }
    payload["receipt_digest"] = mirror_demo_digest(GENERATION_RECEIPT_SCHEMA, payload)
    return payload


def validate_source_generation_receipt(
    value: object,
    *,
    generation_request: Mapping[str, object],
    preregistration: Mapping[str, object],
    reserve_activation: Mapping[str, object],
    generation_requests: Sequence[Mapping[str, object]],
    allocation_manifest: Mapping[str, object],
    producer_dispatch: Mapping[str, object],
    source_name_receipt: Mapping[str, object],
    source_seal_receipt: Mapping[str, object],
    source_commit_receipt: Mapping[str, object],
    provenance: Mapping[str, object],
    provenance_name_receipt: Mapping[str, object],
    provenance_seal_receipt: Mapping[str, object],
    provenance_commit_receipt: Mapping[str, object],
) -> Mapping[str, object]:
    receipt = _exact(value, _GENERATION_RECEIPT_KEYS, "E2 source generation receipt")
    if receipt["schema_version"] != GENERATION_RECEIPT_SCHEMA:
        _fail("E2 source generation receipt schema is invalid")
    _replay(
        receipt,
        schema=GENERATION_RECEIPT_SCHEMA,
        digest_key="receipt_digest",
        label="E2 source generation receipt",
    )
    rebuilt = build_source_generation_receipt(
        generation_request=generation_request,
        preregistration=preregistration,
        reserve_activation=reserve_activation,
        generation_requests=generation_requests,
        allocation_manifest=allocation_manifest,
        producer_dispatch=producer_dispatch,
        source_name_receipt=source_name_receipt,
        source_seal_receipt=source_seal_receipt,
        source_commit_receipt=source_commit_receipt,
        provenance=provenance,
        provenance_name_receipt=provenance_name_receipt,
        provenance_seal_receipt=provenance_seal_receipt,
        provenance_commit_receipt=provenance_commit_receipt,
    )
    if not _strict_equal(dict(receipt), rebuilt):
        _fail("E2 source generation receipt binding drifted")
    return receipt


def project_generation_receipt_name_receipt(
    *,
    generation_receipt: Mapping[str, object],
    provenance_commit_receipt: Mapping[str, object],
    output_id: str,
    logical_name: str,
    allocated_at_utc: str,
) -> JsonObject:
    """Project allocation 13..16 only after the provenance commit is present."""

    receipt = _exact(generation_receipt, _GENERATION_RECEIPT_KEYS, "E2 source generation receipt")
    if receipt["schema_version"] != GENERATION_RECEIPT_SCHEMA:
        _fail("E2 source generation receipt schema is invalid")
    _replay(
        receipt,
        schema=GENERATION_RECEIPT_SCHEMA,
        digest_key="receipt_digest",
        label="E2 source generation receipt",
    )
    provenance_commit = _exact(
        provenance_commit_receipt, _COMMIT_RECEIPT_KEYS, "provenance commit receipt"
    )
    _replay(
        provenance_commit,
        schema=private_registry.REGISTRY_COMMIT_SCHEMA,
        digest_key="commit_receipt_digest",
        label="provenance commit receipt",
    )
    if (
        provenance_commit["commit_receipt_digest"]
        != receipt["source_provenance_registry_commit_receipt_digest"]
    ):
        _fail("generation receipt allocation requires its committed provenance")
    ordinal = _positive_int(receipt["candidate_ordinal"], "candidate ordinal", 4)
    receipt_output_id = _output_id(output_id, "generation receipt output ID")
    if (
        _LOGICAL_NAME_RE.fullmatch(logical_name) is None
        or logical_name in {".", ".."}
        or ":" in logical_name
        or not logical_name.endswith(".json")
    ):
        _fail("generation receipt logical name is invalid")
    timestamp = _timestamp(allocated_at_utc, "generation receipt allocation timestamp")
    payload: JsonObject = {
        "schema_version": private_registry.OUTPUT_NAME_RECEIPT_SCHEMA,
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": cast(JsonScalar, receipt["root_name_receipt_digest"]),
        "execution_contract_digest": cast(JsonScalar, receipt["execution_contract_digest"]),
        "output_id": receipt_output_id,
        "allocation_sequence": 12 + ordinal,
        "semantic_role": "SOURCE_GENERATION_RECEIPT",
        "logical_name": logical_name,
        "producer_task_id": private_registry.TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "allowed_tasks": [private_registry.TASK_ID, private_registry.REVIEW_TASK_ID],
        "expected_parent_authority": cast(
            JsonScalar, receipt["generation_result_provenance_digest"]
        ),
        "expected_media_type": PREFLIGHT_JSON_MEDIA_TYPE,
        "maximum_bytes": PREFLIGHT_JSON_MAXIMUM_BYTES,
        "relative_destination_class": private_registry.ROLE_DESTINATIONS[
            "SOURCE_GENERATION_RECEIPT"
        ][0],
        "allocated_at_utc": timestamp,
    }
    payload["name_receipt_digest"] = mirror_demo_digest(
        private_registry.OUTPUT_NAME_RECEIPT_SCHEMA, payload
    )
    return payload


def validate_generation_receipt_name_receipt(
    value: object,
    *,
    generation_receipt: Mapping[str, object],
    provenance_commit_receipt: Mapping[str, object],
) -> Mapping[str, object]:
    name_receipt = _exact(value, _NAME_RECEIPT_KEYS, "generation receipt name receipt")
    rebuilt = project_generation_receipt_name_receipt(
        generation_receipt=generation_receipt,
        provenance_commit_receipt=provenance_commit_receipt,
        output_id=_output_id(name_receipt["output_id"], "generation receipt output ID"),
        logical_name=cast(str, name_receipt["logical_name"]),
        allocated_at_utc=_timestamp(
            name_receipt["allocated_at_utc"], "generation receipt allocation timestamp"
        ),
    )
    if not _strict_equal(dict(name_receipt), rebuilt):
        _fail("generation receipt name allocation binding drifted")
    return name_receipt
