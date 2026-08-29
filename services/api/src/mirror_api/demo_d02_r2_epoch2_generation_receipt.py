"""Exact Epoch 02 provenance and source-generation receipt authority.

The module is deliberately pure.  It validates the already accepted E2
request/allocation graph plus registry receipt projections, but never resolves
an evidence root, opens a file, invokes a provider, or mutates a registry.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from mirror_api.demo_d02_r2_generation_receiver import ReceivedPng
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
_INTENT_KEYS: Final = (
    "schema_version",
    "evidence_root_id",
    "root_name_receipt_digest",
    "execution_contract_digest",
    "transaction_id",
    "output_id",
    "semantic_role",
    "authority_digest",
    "name_receipt_digest",
    "seal_receipt_digest",
    "canonical_event_digest",
    "canonical_event_json_b64",
    "expected_copy_a_previous_head",
    "expected_copy_b_previous_head",
    "expected_sequence",
    "commit_receipt_logical_name",
    "commit_receipt_created_at_utc",
    "intent_created_at_utc",
    "intent_digest",
)
_EVENT_KEYS: Final = (
    "SCHEMA_VERSION",
    "EVIDENCE_ROOT_ID",
    "ROOT_NAME_RECEIPT_DIGEST",
    "EXECUTION_CONTRACT_DIGEST",
    "OUTPUT_ID",
    "SEMANTIC_ROLE",
    "CREATING_TASK",
    "OPAQUE_LOCATOR",
    "EXPECTED_DIGEST",
    "ACTUAL_DIGEST",
    "BYTE_SIZE",
    "MEDIA_TYPE",
    "AUTHORITY",
    "ALLOWED_TASKS",
    "RETENTION",
    "CUSTODY",
    "RECOVERY_STATUS",
    "BACKUP_STATUS",
    "CLEANUP_STATUS",
    "NAME_RECEIPT_DIGEST",
    "SEAL_RECEIPT_DIGEST",
    "TRANSACTION_ID",
    "SEQUENCE",
    "PREVIOUS_EVENT_DIGEST",
    "EVENT_DIGEST",
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

_COMMITTED_PROJECTION_TOKEN: Final = object()
_VALIDATED_GENERATION_RECEIPT_TOKEN: Final = object()


@dataclass(frozen=True, slots=True, init=False)
class CommittedRegistryOutputProjection:
    """Pure, immutable projection of one fully replayed A/B registry commit."""

    _name_receipt_bytes: bytes
    _seal_receipt_bytes: bytes
    _commit_receipt_bytes: bytes

    def __init__(
        self,
        *,
        name_receipt: Mapping[str, object],
        seal_receipt: Mapping[str, object],
        commit_receipt: Mapping[str, object],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _COMMITTED_PROJECTION_TOKEN:
            raise TypeError(
                "registry projection must be created by the complete projection validator"
            )
        object.__setattr__(self, "_name_receipt_bytes", canonical_json_bytes(name_receipt))
        object.__setattr__(self, "_seal_receipt_bytes", canonical_json_bytes(seal_receipt))
        object.__setattr__(self, "_commit_receipt_bytes", canonical_json_bytes(commit_receipt))

    def name_receipt(self) -> JsonObject:
        return _canonical_object(self._name_receipt_bytes, "projected output name receipt")

    def seal_receipt(self) -> JsonObject:
        return _canonical_object(self._seal_receipt_bytes, "projected output seal receipt")

    def commit_receipt(self) -> JsonObject:
        return _canonical_object(self._commit_receipt_bytes, "projected registry commit receipt")


@dataclass(frozen=True, slots=True, init=False)
class ValidatedSourceGenerationReceipt:
    """Receipt authority that has replayed both source and provenance commits."""

    _payload_bytes: bytes

    def __init__(self, *, payload: Mapping[str, object], _factory_token: object) -> None:
        if _factory_token is not _VALIDATED_GENERATION_RECEIPT_TOKEN:
            raise TypeError("generation receipt must be created by its complete validator")
        object.__setattr__(self, "_payload_bytes", canonical_json_bytes(payload))

    def payload(self) -> JsonObject:
        return _canonical_object(self._payload_bytes, "validated source generation receipt")


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


def _canonical_object(data: bytes, label: str) -> JsonObject:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not canonical JSON") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != data:
        _fail(f"{label} is not an exact canonical object")
    return cast(JsonObject, value)


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


def validate_committed_registry_output_projection(
    *,
    name_receipt: Mapping[str, object],
    seal_receipt: Mapping[str, object],
    intent: Mapping[str, object],
    canonical_event: Mapping[str, object],
    snapshot_a: private_registry.RegistrySnapshot,
    snapshot_b: private_registry.RegistrySnapshot,
    commit_receipt: Mapping[str, object],
) -> CommittedRegistryOutputProjection:
    """Bind a commit receipt to its replayed intent, event, and exact A/B snapshots.

    The accepted registry process performs all filesystem and SQLite replay and
    passes those values here.  This function remains pure and rejects a
    self-signed commit mapping that is not the final event of both snapshots.
    """

    name = _exact(name_receipt, _NAME_RECEIPT_KEYS, "projected output name receipt")
    seal = _exact(seal_receipt, _SEAL_RECEIPT_KEYS, "projected output seal receipt")
    transaction_intent = _exact(intent, _INTENT_KEYS, "projected registry intent")
    event = _exact(canonical_event, _EVENT_KEYS, "projected canonical registry event")
    commit = _exact(commit_receipt, _COMMIT_RECEIPT_KEYS, "projected registry commit receipt")

    if name["schema_version"] != private_registry.OUTPUT_NAME_RECEIPT_SCHEMA:
        _fail("projected output name receipt schema is invalid")
    _replay(
        name,
        schema=private_registry.OUTPUT_NAME_RECEIPT_SCHEMA,
        digest_key="name_receipt_digest",
        label="projected output name receipt",
    )
    if seal["schema_version"] != private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA:
        _fail("projected output seal receipt schema is invalid")
    _replay(
        seal,
        schema=private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA,
        digest_key="seal_digest",
        label="projected output seal receipt",
    )

    transaction_id = mirror_demo_digest(
        private_registry.REGISTRY_TRANSACTION_ID_SCHEMA,
        {
            "evidence_root_id": cast(JsonValue, name["evidence_root_id"]),
            "root_name_receipt_digest": cast(JsonValue, name["root_name_receipt_digest"]),
            "execution_contract_digest": cast(JsonValue, name["execution_contract_digest"]),
            "output_id": cast(JsonValue, name["output_id"]),
            "name_receipt_digest": cast(JsonValue, name["name_receipt_digest"]),
            "seal_receipt_digest": cast(JsonValue, seal["seal_digest"]),
        },
    )
    fixed_seal = {
        "evidence_root_id": name["evidence_root_id"],
        "root_name_receipt_digest": name["root_name_receipt_digest"],
        "execution_contract_digest": name["execution_contract_digest"],
        "output_id": name["output_id"],
        "name_receipt_digest": name["name_receipt_digest"],
        "semantic_role": name["semantic_role"],
        "producer_task_id": name["producer_task_id"],
        "media_type": name["expected_media_type"],
    }
    if any(seal[key] != expected for key, expected in fixed_seal.items()):
        _fail("projected seal does not bind the projected name receipt")
    for digest_key in ("actual_sha256", "authority_digest"):
        _digest(seal[digest_key], f"projected seal {digest_key}")
    byte_size = seal["byte_size"]
    maximum_bytes = name["maximum_bytes"]
    if (
        type(byte_size) is not int
        or type(maximum_bytes) is not int
        or not 0 <= byte_size <= maximum_bytes
    ):
        _fail("projected seal byte size is outside the name receipt envelope")

    expected_sequence = _positive_int(
        transaction_intent["expected_sequence"], "registry intent sequence", 99_999_999
    )
    previous_head = _digest(
        transaction_intent["expected_copy_a_previous_head"], "registry previous head"
    )
    if transaction_intent["expected_copy_b_previous_head"] != previous_head:
        _fail("registry intent previous heads disagree")
    created_at = _timestamp(transaction_intent["intent_created_at_utc"], "registry intent time")
    if transaction_intent["commit_receipt_created_at_utc"] != created_at:
        _fail("registry intent timestamps disagree")

    semantic_role = name["semantic_role"]
    role_destination = private_registry.ROLE_DESTINATIONS.get(cast(str, semantic_role))
    if role_destination is None or name["relative_destination_class"] != role_destination[0]:
        _fail("projected registry role destination is invalid")
    logical_name = name["logical_name"]
    if not isinstance(logical_name, str):
        _fail("projected registry logical name is invalid")
    relative = f"{role_destination[1]}/{logical_name}"
    opaque_locator = "r2rel1:" + base64.urlsafe_b64encode(relative.encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")
    expected_event: JsonObject = {
        "SCHEMA_VERSION": private_registry.REGISTRY_EVENT_SCHEMA,
        "EVIDENCE_ROOT_ID": cast(JsonScalar, name["evidence_root_id"]),
        "ROOT_NAME_RECEIPT_DIGEST": cast(JsonScalar, name["root_name_receipt_digest"]),
        "EXECUTION_CONTRACT_DIGEST": cast(JsonScalar, name["execution_contract_digest"]),
        "OUTPUT_ID": cast(JsonScalar, name["output_id"]),
        "SEMANTIC_ROLE": cast(JsonScalar, name["semantic_role"]),
        "CREATING_TASK": cast(JsonScalar, name["producer_task_id"]),
        "OPAQUE_LOCATOR": opaque_locator,
        "EXPECTED_DIGEST": cast(JsonScalar, seal["actual_sha256"]),
        "ACTUAL_DIGEST": cast(JsonScalar, seal["actual_sha256"]),
        "BYTE_SIZE": cast(JsonScalar, seal["byte_size"]),
        "MEDIA_TYPE": cast(JsonScalar, seal["media_type"]),
        "AUTHORITY": cast(JsonScalar, seal["authority_digest"]),
        "ALLOWED_TASKS": cast(JsonValue, name["allowed_tasks"]),
        "RETENTION": cast(JsonScalar, seal["retention"]),
        "CUSTODY": cast(JsonScalar, seal["custody"]),
        "RECOVERY_STATUS": "NOT_REQUIRED",
        "BACKUP_STATUS": "TWO_LOGICAL_COPIES_SAME_ROOT_REQUIRED",
        "CLEANUP_STATUS": "RETAINED",
        "NAME_RECEIPT_DIGEST": cast(JsonScalar, name["name_receipt_digest"]),
        "SEAL_RECEIPT_DIGEST": cast(JsonScalar, seal["seal_digest"]),
        "TRANSACTION_ID": transaction_id,
        "SEQUENCE": expected_sequence,
        "PREVIOUS_EVENT_DIGEST": previous_head,
    }
    expected_event["EVENT_DIGEST"] = mirror_demo_digest(
        private_registry.REGISTRY_EVENT_SCHEMA, expected_event
    )
    if not _strict_equal(dict(event), expected_event):
        _fail("projected canonical registry event does not replay from name and seal")

    event_bytes = canonical_json_bytes(expected_event)
    expected_intent: JsonObject = {
        "schema_version": private_registry.REGISTRY_INTENT_SCHEMA,
        "evidence_root_id": cast(JsonScalar, name["evidence_root_id"]),
        "root_name_receipt_digest": cast(JsonScalar, name["root_name_receipt_digest"]),
        "execution_contract_digest": cast(JsonScalar, name["execution_contract_digest"]),
        "transaction_id": transaction_id,
        "output_id": cast(JsonScalar, name["output_id"]),
        "semantic_role": cast(JsonScalar, name["semantic_role"]),
        "authority_digest": cast(JsonScalar, seal["authority_digest"]),
        "name_receipt_digest": cast(JsonScalar, name["name_receipt_digest"]),
        "seal_receipt_digest": cast(JsonScalar, seal["seal_digest"]),
        "canonical_event_digest": cast(JsonScalar, expected_event["EVENT_DIGEST"]),
        "canonical_event_json_b64": base64.b64encode(event_bytes).decode("ascii"),
        "expected_copy_a_previous_head": previous_head,
        "expected_copy_b_previous_head": previous_head,
        "expected_sequence": expected_sequence,
        "commit_receipt_logical_name": (f"D02_R2_REGISTRY_COMMIT_RECEIPT__{transaction_id}.json"),
        "commit_receipt_created_at_utc": created_at,
        "intent_created_at_utc": created_at,
    }
    expected_intent["intent_digest"] = mirror_demo_digest(
        private_registry.REGISTRY_INTENT_SCHEMA, expected_intent
    )
    if not _strict_equal(dict(transaction_intent), expected_intent):
        _fail("projected registry intent does not replay from the canonical event")

    if (
        type(snapshot_a) is not private_registry.RegistrySnapshot
        or type(snapshot_b) is not private_registry.RegistrySnapshot
        or snapshot_a != snapshot_b
        or snapshot_a.event_count != expected_sequence
        or len(snapshot_a.ordered_events) != expected_sequence
        or snapshot_a.head_event_digest != expected_event["EVENT_DIGEST"]
    ):
        _fail("projected registry snapshots do not prove the committed event")
    event_projection: JsonObject = {
        "sequence": expected_sequence,
        "transaction_id": transaction_id,
        "output_id": cast(JsonScalar, name["output_id"]),
        "semantic_role": cast(JsonScalar, name["semantic_role"]),
        "authority_digest": cast(JsonScalar, seal["authority_digest"]),
        "event_digest": cast(JsonScalar, expected_event["EVENT_DIGEST"]),
    }
    if not _strict_equal(snapshot_a.ordered_events[-1], event_projection):
        _fail("projected registry snapshots end at a different event")
    if expected_sequence > 1:
        prior = snapshot_a.ordered_events[-2]
        if prior.get("event_digest") != previous_head:
            _fail("projected registry snapshot previous head is discontinuous")
    for snapshot_digest, label in (
        (snapshot_a.head_event_digest, "registry snapshot head"),
        (snapshot_a.semantic_snapshot_digest, "registry semantic snapshot"),
    ):
        _digest(snapshot_digest, label)

    expected_commit: JsonObject = {
        "schema_version": private_registry.REGISTRY_COMMIT_SCHEMA,
        "evidence_root_id": cast(JsonScalar, name["evidence_root_id"]),
        "root_name_receipt_digest": cast(JsonScalar, name["root_name_receipt_digest"]),
        "execution_contract_digest": cast(JsonScalar, name["execution_contract_digest"]),
        "transaction_id": transaction_id,
        "intent_digest": cast(JsonScalar, expected_intent["intent_digest"]),
        "output_id": cast(JsonScalar, name["output_id"]),
        "canonical_event_digest": cast(JsonScalar, expected_event["EVENT_DIGEST"]),
        "copy_a_event_count": snapshot_a.event_count,
        "copy_a_head_event_digest": snapshot_a.head_event_digest,
        "copy_a_semantic_snapshot_digest": snapshot_a.semantic_snapshot_digest,
        "copy_b_event_count": snapshot_b.event_count,
        "copy_b_head_event_digest": snapshot_b.head_event_digest,
        "copy_b_semantic_snapshot_digest": snapshot_b.semantic_snapshot_digest,
        "commit_state": "COMMITTED_BOTH_COPIES",
        "created_at_utc": created_at,
    }
    expected_commit["commit_receipt_digest"] = mirror_demo_digest(
        private_registry.REGISTRY_COMMIT_SCHEMA, expected_commit
    )
    if not _strict_equal(dict(commit), expected_commit):
        _fail("projected registry commit does not replay from intent, event, and snapshots")
    return CommittedRegistryOutputProjection(
        name_receipt=name,
        seal_receipt=seal,
        commit_receipt=commit,
        _factory_token=_COMMITTED_PROJECTION_TOKEN,
    )


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
        or receipt["canonical_event_digest"] != receipt["copy_a_head_event_digest"]
    ):
        _fail("registry commit receipt does not end both copies at its canonical event")
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
    source_commit_projection: CommittedRegistryOutputProjection,
    provenance_name_receipt: Mapping[str, object],
    received_png: ReceivedPng,
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
    if type(source_commit_projection) is not CommittedRegistryOutputProjection:
        _fail("source commit must be a completely validated registry projection")
    if type(received_png) is not ReceivedPng:
        _fail("source Asset facts must come from the PNG receiver")
    source_name_receipt = source_commit_projection.name_receipt()
    source_seal_receipt = source_commit_projection.seal_receipt()
    source_commit_receipt = source_commit_projection.commit_receipt()
    ordinal, source_name, _ = _source_and_provenance_names(
        request=request,
        preregistration=preregistration,
        source_name_receipt=source_name_receipt,
        provenance_name_receipt=provenance_name_receipt,
    )
    source_sha = _digest(received_png.sha256, "source Asset checksum")
    source_size = _positive_int(
        received_png.byte_size, "source Asset byte size", PREFLIGHT_SOURCE_MAXIMUM_BYTES
    )
    width = _positive_int(received_png.width, "source Asset width", 8_192)
    height = _positive_int(received_png.height, "source Asset height", 8_192)
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
    source_commit_projection: CommittedRegistryOutputProjection,
    provenance_name_receipt: Mapping[str, object],
    received_png: ReceivedPng,
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
        source_commit_projection=source_commit_projection,
        provenance_name_receipt=provenance_name_receipt,
        received_png=received_png,
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
    source_commit_projection: CommittedRegistryOutputProjection,
    provenance: Mapping[str, object],
    provenance_commit_projection: CommittedRegistryOutputProjection,
    received_png: ReceivedPng,
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
    if (
        type(source_commit_projection) is not CommittedRegistryOutputProjection
        or type(provenance_commit_projection) is not CommittedRegistryOutputProjection
    ):
        _fail("source and provenance must be completely validated registry projections")
    source_name_receipt = source_commit_projection.name_receipt()
    source_seal_receipt = source_commit_projection.seal_receipt()
    source_commit_receipt = source_commit_projection.commit_receipt()
    provenance_name_receipt = provenance_commit_projection.name_receipt()
    provenance_seal_receipt = provenance_commit_projection.seal_receipt()
    provenance_commit_receipt = provenance_commit_projection.commit_receipt()
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
        source_commit_projection=source_commit_projection,
        provenance_name_receipt=provenance_name_receipt,
        received_png=received_png,
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
    source_commit_projection: CommittedRegistryOutputProjection,
    provenance: Mapping[str, object],
    provenance_commit_projection: CommittedRegistryOutputProjection,
    received_png: ReceivedPng,
) -> ValidatedSourceGenerationReceipt:
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
        source_commit_projection=source_commit_projection,
        provenance=provenance,
        provenance_commit_projection=provenance_commit_projection,
        received_png=received_png,
    )
    if not _strict_equal(dict(receipt), rebuilt):
        _fail("E2 source generation receipt binding drifted")
    return ValidatedSourceGenerationReceipt(
        payload=receipt,
        _factory_token=_VALIDATED_GENERATION_RECEIPT_TOKEN,
    )


def project_generation_receipt_name_receipt(
    *,
    validated_generation_receipt: ValidatedSourceGenerationReceipt,
    output_id: str,
    logical_name: str,
    allocated_at_utc: str,
) -> JsonObject:
    """Project allocation 13..16 only after the provenance commit is present."""

    if type(validated_generation_receipt) is not ValidatedSourceGenerationReceipt:
        _fail("generation receipt allocation requires a completely validated receipt")
    receipt = validated_generation_receipt.payload()
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
    validated_generation_receipt: ValidatedSourceGenerationReceipt,
) -> Mapping[str, object]:
    name_receipt = _exact(value, _NAME_RECEIPT_KEYS, "generation receipt name receipt")
    rebuilt = project_generation_receipt_name_receipt(
        validated_generation_receipt=validated_generation_receipt,
        output_id=_output_id(name_receipt["output_id"], "generation receipt output ID"),
        logical_name=cast(str, name_receipt["logical_name"]),
        allocated_at_utc=_timestamp(
            name_receipt["allocated_at_utc"], "generation receipt allocation timestamp"
        ),
    )
    if not _strict_equal(dict(name_receipt), rebuilt):
        _fail("generation receipt name allocation binding drifted")
    return name_receipt
