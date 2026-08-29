from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from io import BytesIO
from typing import Any, TypedDict, cast

import pytest
from PIL import Image

from mirror_api import demo_d02_r2_generation_receiver as generation_receiver
from mirror_api import demo_d02_r2_private_registry_e2 as private_registry
from mirror_api.demo_d02_r2_epoch2_generation_receipt import (
    CONTROL_PLANE_LEASE_STATE,
    GENERATION_RECEIPT_SCHEMA,
    PROVENANCE_SCHEMA,
    PUBLIC_EGRESS_AFTER_CALL,
    PUBLIC_EGRESS_DURING_CALL,
    CommittedRegistryOutputProjection,
    ValidatedSourceGenerationReceipt,
    build_generation_result_provenance,
    build_source_generation_receipt,
    project_generation_receipt_name_receipt,
    validate_committed_registry_output_projection,
    validate_generation_receipt_name_receipt,
    validate_generation_result_provenance,
    validate_source_generation_receipt,
)
from mirror_api.demo_d02_r2_epoch2_request_bridge import (
    PREFLIGHT_JSON_MAXIMUM_BYTES,
    PREFLIGHT_SOURCE_MAXIMUM_BYTES,
    build_generation_preregistration_authority,
    build_source_allocation_manifest,
    build_source_producer_dispatch,
    validate_generation_receipt_request_binding,
)
from mirror_api.demo_d02_r2_generation_epoch2 import (
    Epoch2Allocation,
    build_generation_request,
    build_reserve_activation_authority,
    expected_e1_terminal_binding,
)
from mirror_api.demo_d02_r2_generation_receiver import ReceivedPng
from mirror_api.demo_measurement_quality import (
    JsonValue,
    canonical_json_bytes,
    mirror_demo_digest,
)


class ProvenanceKwargs(TypedDict):
    generation_request: Mapping[str, object]
    preregistration: Mapping[str, object]
    reserve_activation: Mapping[str, object]
    generation_requests: Sequence[Mapping[str, object]]
    allocation_manifest: Mapping[str, object]
    producer_dispatch: Mapping[str, object]
    source_commit_projection: CommittedRegistryOutputProjection
    provenance_name_receipt: Mapping[str, object]
    received_png: ReceivedPng


class ReceiptKwargs(TypedDict):
    generation_request: Mapping[str, object]
    preregistration: Mapping[str, object]
    reserve_activation: Mapping[str, object]
    generation_requests: Sequence[Mapping[str, object]]
    allocation_manifest: Mapping[str, object]
    producer_dispatch: Mapping[str, object]
    source_commit_projection: CommittedRegistryOutputProjection
    provenance: Mapping[str, object]
    provenance_commit_projection: CommittedRegistryOutputProjection
    received_png: ReceivedPng


def digest(character: str) -> str:
    return character * 64


def _name_receipt(
    *,
    output_id: str,
    sequence: int,
    semantic_role: str,
    logical_name: str,
    parent: str,
    media_type: str,
    maximum_bytes: int,
    producer_task_id: str,
) -> dict[str, object]:
    allowed_tasks = (
        [
            private_registry.TASK_ID,
            private_registry.SOURCE_PRODUCER_TASK_ID,
            private_registry.REVIEW_TASK_ID,
        ]
        if semantic_role in {"SOURCE_CANDIDATE", "SOURCE_PROVENANCE"}
        else [private_registry.TASK_ID, private_registry.REVIEW_TASK_ID]
    )
    payload: dict[str, JsonValue] = {
        "schema_version": private_registry.OUTPUT_NAME_RECEIPT_SCHEMA,
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": digest("a"),
        "execution_contract_digest": digest("b"),
        "output_id": output_id,
        "allocation_sequence": sequence,
        "semantic_role": semantic_role,
        "logical_name": logical_name,
        "producer_task_id": producer_task_id,
        "dispatch_epoch": private_registry.DISPATCH_EPOCH,
        "allowed_tasks": cast(list[JsonValue], allowed_tasks),
        "expected_parent_authority": parent,
        "expected_media_type": media_type,
        "maximum_bytes": maximum_bytes,
        "relative_destination_class": private_registry.ROLE_DESTINATIONS[semantic_role][0],
        "allocated_at_utc": "2026-08-29T01:00:00.000000Z",
    }
    payload["name_receipt_digest"] = mirror_demo_digest(
        private_registry.OUTPUT_NAME_RECEIPT_SCHEMA, payload
    )
    return cast(dict[str, object], payload)


def _seal_receipt(
    *,
    name_receipt: Mapping[str, object],
    actual_sha256: str,
    byte_size: int,
    media_type: str,
    authority_digest: str,
) -> dict[str, object]:
    payload: dict[str, JsonValue] = {
        "schema_version": private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA,
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": cast(str, name_receipt["root_name_receipt_digest"]),
        "execution_contract_digest": cast(str, name_receipt["execution_contract_digest"]),
        "output_id": cast(str, name_receipt["output_id"]),
        "name_receipt_digest": cast(str, name_receipt["name_receipt_digest"]),
        "semantic_role": cast(str, name_receipt["semantic_role"]),
        "producer_task_id": cast(str, name_receipt["producer_task_id"]),
        "actual_sha256": actual_sha256,
        "byte_size": byte_size,
        "media_type": media_type,
        "authority_digest": authority_digest,
        "retention": private_registry.RETENTION_POLICY,
        "custody": private_registry.DEFAULT_CUSTODY,
        "sealed_at_utc": "2026-08-29T01:01:00.000000Z",
    }
    payload["seal_digest"] = mirror_demo_digest(
        private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA, payload
    )
    return cast(dict[str, object], payload)


def _committed_projection(
    *,
    name_receipt: Mapping[str, object],
    seal_receipt: Mapping[str, object],
    event_count: int,
) -> tuple[CommittedRegistryOutputProjection, dict[str, object]]:
    transaction_id = mirror_demo_digest(
        private_registry.REGISTRY_TRANSACTION_ID_SCHEMA,
        {
            "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
            "root_name_receipt_digest": cast(JsonValue, name_receipt["root_name_receipt_digest"]),
            "execution_contract_digest": cast(JsonValue, name_receipt["execution_contract_digest"]),
            "output_id": cast(JsonValue, name_receipt["output_id"]),
            "name_receipt_digest": cast(JsonValue, name_receipt["name_receipt_digest"]),
            "seal_receipt_digest": cast(JsonValue, seal_receipt["seal_digest"]),
        },
    )
    prior_events: list[dict[str, JsonValue]] = []
    for sequence in range(1, event_count):
        prior_events.append(
            {
                "sequence": sequence,
                "transaction_id": hashlib.sha256(f"prior-tx-{sequence}".encode()).hexdigest(),
                "output_id": f"prior-output-{sequence}",
                "semantic_role": "SOURCE_GENERATION_PREREGISTRATION",
                "authority_digest": hashlib.sha256(
                    f"prior-authority-{sequence}".encode()
                ).hexdigest(),
                "event_digest": hashlib.sha256(f"prior-event-{sequence}".encode()).hexdigest(),
            }
        )
    previous_head = cast(str, prior_events[-1]["event_digest"])
    role_path = private_registry.ROLE_DESTINATIONS[cast(str, name_receipt["semantic_role"])][1]
    relative = f"{role_path}/{name_receipt['logical_name']}"
    event: dict[str, JsonValue] = {
        "SCHEMA_VERSION": private_registry.REGISTRY_EVENT_SCHEMA,
        "EVIDENCE_ROOT_ID": private_registry.EVIDENCE_ROOT_ID,
        "ROOT_NAME_RECEIPT_DIGEST": cast(str, name_receipt["root_name_receipt_digest"]),
        "EXECUTION_CONTRACT_DIGEST": cast(str, name_receipt["execution_contract_digest"]),
        "OUTPUT_ID": cast(str, name_receipt["output_id"]),
        "SEMANTIC_ROLE": cast(str, name_receipt["semantic_role"]),
        "CREATING_TASK": cast(str, name_receipt["producer_task_id"]),
        "OPAQUE_LOCATOR": "r2rel1:"
        + base64.urlsafe_b64encode(relative.encode()).decode().rstrip("="),
        "EXPECTED_DIGEST": cast(str, seal_receipt["actual_sha256"]),
        "ACTUAL_DIGEST": cast(str, seal_receipt["actual_sha256"]),
        "BYTE_SIZE": cast(int, seal_receipt["byte_size"]),
        "MEDIA_TYPE": cast(str, seal_receipt["media_type"]),
        "AUTHORITY": cast(str, seal_receipt["authority_digest"]),
        "ALLOWED_TASKS": cast(list[JsonValue], name_receipt["allowed_tasks"]),
        "RETENTION": cast(str, seal_receipt["retention"]),
        "CUSTODY": cast(str, seal_receipt["custody"]),
        "RECOVERY_STATUS": "NOT_REQUIRED",
        "BACKUP_STATUS": "TWO_LOGICAL_COPIES_SAME_ROOT_REQUIRED",
        "CLEANUP_STATUS": "RETAINED",
        "NAME_RECEIPT_DIGEST": cast(str, name_receipt["name_receipt_digest"]),
        "SEAL_RECEIPT_DIGEST": cast(str, seal_receipt["seal_digest"]),
        "TRANSACTION_ID": transaction_id,
        "SEQUENCE": event_count,
        "PREVIOUS_EVENT_DIGEST": previous_head,
    }
    event["EVENT_DIGEST"] = mirror_demo_digest(private_registry.REGISTRY_EVENT_SCHEMA, event)
    event_projection: dict[str, JsonValue] = {
        "sequence": event_count,
        "transaction_id": transaction_id,
        "output_id": cast(str, name_receipt["output_id"]),
        "semantic_role": cast(str, name_receipt["semantic_role"]),
        "authority_digest": cast(str, seal_receipt["authority_digest"]),
        "event_digest": cast(str, event["EVENT_DIGEST"]),
    }
    ordered_events = [*prior_events, event_projection]
    snapshot_digest = hashlib.sha256(canonical_json_bytes({"events": ordered_events})).hexdigest()
    snapshot_a = private_registry.RegistrySnapshot(
        event_count=event_count,
        head_event_digest=cast(str, event["EVENT_DIGEST"]),
        semantic_snapshot_digest=snapshot_digest,
        ordered_events=tuple(ordered_events),
    )
    snapshot_b = private_registry.RegistrySnapshot(
        event_count=snapshot_a.event_count,
        head_event_digest=snapshot_a.head_event_digest,
        semantic_snapshot_digest=snapshot_a.semantic_snapshot_digest,
        ordered_events=snapshot_a.ordered_events,
    )
    created_at = "2026-08-29T01:02:00.000000Z"
    intent: dict[str, JsonValue] = {
        "schema_version": private_registry.REGISTRY_INTENT_SCHEMA,
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": cast(str, name_receipt["root_name_receipt_digest"]),
        "execution_contract_digest": cast(str, name_receipt["execution_contract_digest"]),
        "transaction_id": transaction_id,
        "output_id": cast(str, name_receipt["output_id"]),
        "semantic_role": cast(str, name_receipt["semantic_role"]),
        "authority_digest": cast(str, seal_receipt["authority_digest"]),
        "name_receipt_digest": cast(str, name_receipt["name_receipt_digest"]),
        "seal_receipt_digest": cast(str, seal_receipt["seal_digest"]),
        "canonical_event_digest": cast(str, event["EVENT_DIGEST"]),
        "canonical_event_json_b64": base64.b64encode(canonical_json_bytes(event)).decode(),
        "expected_copy_a_previous_head": previous_head,
        "expected_copy_b_previous_head": previous_head,
        "expected_sequence": event_count,
        "commit_receipt_logical_name": (f"D02_R2_REGISTRY_COMMIT_RECEIPT__{transaction_id}.json"),
        "commit_receipt_created_at_utc": created_at,
        "intent_created_at_utc": created_at,
    }
    intent["intent_digest"] = mirror_demo_digest(private_registry.REGISTRY_INTENT_SCHEMA, intent)
    commit: dict[str, JsonValue] = {
        "schema_version": private_registry.REGISTRY_COMMIT_SCHEMA,
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": cast(str, name_receipt["root_name_receipt_digest"]),
        "execution_contract_digest": cast(str, name_receipt["execution_contract_digest"]),
        "transaction_id": transaction_id,
        "intent_digest": cast(str, intent["intent_digest"]),
        "output_id": cast(str, name_receipt["output_id"]),
        "canonical_event_digest": cast(str, event["EVENT_DIGEST"]),
        "copy_a_event_count": event_count,
        "copy_a_head_event_digest": snapshot_a.head_event_digest,
        "copy_a_semantic_snapshot_digest": snapshot_a.semantic_snapshot_digest,
        "copy_b_event_count": event_count,
        "copy_b_head_event_digest": snapshot_b.head_event_digest,
        "copy_b_semantic_snapshot_digest": snapshot_b.semantic_snapshot_digest,
        "commit_state": "COMMITTED_BOTH_COPIES",
        "created_at_utc": created_at,
    }
    commit["commit_receipt_digest"] = mirror_demo_digest(
        private_registry.REGISTRY_COMMIT_SCHEMA, commit
    )
    projection = validate_committed_registry_output_projection(
        name_receipt=name_receipt,
        seal_receipt=seal_receipt,
        intent=cast(dict[str, object], intent),
        canonical_event=cast(dict[str, object], event),
        snapshot_a=snapshot_a,
        snapshot_b=snapshot_b,
        commit_receipt=cast(dict[str, object], commit),
    )
    parts: dict[str, object] = {
        "name_receipt": name_receipt,
        "seal_receipt": seal_receipt,
        "intent": intent,
        "canonical_event": event,
        "snapshot_a": snapshot_a,
        "snapshot_b": snapshot_b,
        "commit_receipt": commit,
    }
    return projection, parts


def _resign(value: dict[str, object], schema: str, digest_key: str) -> None:
    value[digest_key] = mirror_demo_digest(
        schema,
        cast(
            dict[str, JsonValue],
            {key: item for key, item in value.items() if key != digest_key},
        ),
    )


def prepared(ordinal: int = 1) -> dict[str, object]:
    preregistration = build_generation_preregistration_authority(
        execution_contract_digest=digest("b"),
        root_name_receipt_digest=digest("a"),
        cohort_policy_digest=digest("c"),
    )
    preregistration_digest = cast(str, preregistration["generation_preregistration_digest"])
    source_names = [
        _name_receipt(
            output_id=f"source-{index}",
            sequence=4 + (index - 1) * 2,
            semantic_role="SOURCE_CANDIDATE",
            logical_name=f"source-{index}.png",
            parent=preregistration_digest,
            media_type="image/png",
            maximum_bytes=PREFLIGHT_SOURCE_MAXIMUM_BYTES,
            producer_task_id=private_registry.SOURCE_PRODUCER_TASK_ID,
        )
        for index in range(1, 5)
    ]
    provenance_names = [
        _name_receipt(
            output_id=f"provenance-{index}",
            sequence=5 + (index - 1) * 2,
            semantic_role="SOURCE_PROVENANCE",
            logical_name=f"provenance-{index}.json",
            parent=preregistration_digest,
            media_type="application/json",
            maximum_bytes=PREFLIGHT_JSON_MAXIMUM_BYTES,
            producer_task_id=private_registry.SOURCE_PRODUCER_TASK_ID,
        )
        for index in range(1, 5)
    ]
    allocations = [
        Epoch2Allocation(
            candidate_ordinal=index,
            source_output_id=f"source-{index}",
            source_name_receipt_digest=cast(str, source_names[index - 1]["name_receipt_digest"]),
            provenance_output_id=f"provenance-{index}",
            provenance_name_receipt_digest=cast(
                str, provenance_names[index - 1]["name_receipt_digest"]
            ),
            prompt_material_digest=hashlib.sha256(f"prompt-{index}".encode()).hexdigest(),
        )
        for index in range(1, 5)
    ]
    activation = build_reserve_activation_authority(
        terminal_binding=expected_e1_terminal_binding(),
        root_name_receipt_digest=digest("a"),
        allocations=allocations,
    )
    requests = [
        build_generation_request(
            reserve_activation=activation,
            generation_preregistration_digest=preregistration_digest,
            candidate_ordinal=index,
        )
        for index in range(1, 5)
    ]
    manifest = build_source_allocation_manifest(
        execution_contract_digest=digest("b"),
        preregistration=preregistration,
        reserve_activation=activation,
        generation_requests=requests,
    )
    dispatch = build_source_producer_dispatch(
        execution_contract_digest=digest("b"),
        preregistration=preregistration,
        allocation_manifest=manifest,
        reserve_activation=activation,
        generation_requests=requests,
    )
    request = cast(dict[str, object], requests[ordinal - 1])
    source_name = source_names[ordinal - 1]
    provenance_name = provenance_names[ordinal - 1]
    source_buffer = BytesIO()
    Image.new("RGB", (64, 64), color=(ordinal, ordinal * 2, ordinal * 3)).save(
        source_buffer,
        format="PNG",
        optimize=False,
        compress_level=9,
    )
    received_png = generation_receiver._validate_png_bytes(source_buffer.getvalue())
    source_sha = received_png.sha256
    source_size = received_png.byte_size
    source_binary_authority = mirror_demo_digest(
        private_registry.SEALED_BINARY_AUTHORITY_SCHEMA,
        {
            "semantic_role": "SOURCE_CANDIDATE",
            "actual_sha256": source_sha,
            "byte_size": source_size,
            "media_type": "image/png",
            "name_receipt_digest": cast(JsonValue, source_name["name_receipt_digest"]),
        },
    )
    source_seal = _seal_receipt(
        name_receipt=source_name,
        actual_sha256=source_sha,
        byte_size=source_size,
        media_type="image/png",
        authority_digest=source_binary_authority,
    )
    source_projection, source_projection_parts = _committed_projection(
        name_receipt=source_name,
        seal_receipt=source_seal,
        event_count=3 * ordinal + 1,
    )
    provenance = build_generation_result_provenance(
        generation_request=request,
        preregistration=preregistration,
        reserve_activation=activation,
        generation_requests=requests,
        allocation_manifest=manifest,
        producer_dispatch=dispatch,
        source_commit_projection=source_projection,
        provenance_name_receipt=provenance_name,
        received_png=received_png,
    )
    provenance_bytes = canonical_json_bytes(provenance)
    provenance_seal = _seal_receipt(
        name_receipt=provenance_name,
        actual_sha256=hashlib.sha256(provenance_bytes).hexdigest(),
        byte_size=len(provenance_bytes),
        media_type="application/json",
        authority_digest=cast(str, provenance["provenance_digest"]),
    )
    provenance_projection, provenance_projection_parts = _committed_projection(
        name_receipt=provenance_name,
        seal_receipt=provenance_seal,
        event_count=3 * ordinal + 2,
    )
    receipt = build_source_generation_receipt(
        generation_request=request,
        preregistration=preregistration,
        reserve_activation=activation,
        generation_requests=requests,
        allocation_manifest=manifest,
        producer_dispatch=dispatch,
        source_commit_projection=source_projection,
        provenance=provenance,
        provenance_commit_projection=provenance_projection,
        received_png=received_png,
    )
    validated_receipt = validate_source_generation_receipt(
        receipt,
        generation_request=request,
        preregistration=preregistration,
        reserve_activation=activation,
        generation_requests=requests,
        allocation_manifest=manifest,
        producer_dispatch=dispatch,
        source_commit_projection=source_projection,
        provenance=provenance,
        provenance_commit_projection=provenance_projection,
        received_png=received_png,
    )
    return {
        "activation": activation,
        "preregistration": preregistration,
        "requests": requests,
        "manifest": manifest,
        "dispatch": dispatch,
        "request": request,
        "source_name": source_name,
        "source_seal": source_seal,
        "source_projection": source_projection,
        "source_projection_parts": source_projection_parts,
        "provenance_name": provenance_name,
        "provenance": provenance,
        "provenance_seal": provenance_seal,
        "provenance_projection": provenance_projection,
        "provenance_projection_parts": provenance_projection_parts,
        "received_png": received_png,
        "receipt": receipt,
        "validated_receipt": validated_receipt,
    }


def _provenance_kwargs(bundle: Mapping[str, object]) -> ProvenanceKwargs:
    return {
        "generation_request": cast(Mapping[str, object], bundle["request"]),
        "preregistration": cast(Mapping[str, object], bundle["preregistration"]),
        "reserve_activation": cast(Mapping[str, object], bundle["activation"]),
        "generation_requests": cast(Sequence[Mapping[str, object]], bundle["requests"]),
        "allocation_manifest": cast(Mapping[str, object], bundle["manifest"]),
        "producer_dispatch": cast(Mapping[str, object], bundle["dispatch"]),
        "source_commit_projection": cast(
            CommittedRegistryOutputProjection, bundle["source_projection"]
        ),
        "provenance_name_receipt": cast(Mapping[str, object], bundle["provenance_name"]),
        "received_png": cast(ReceivedPng, bundle["received_png"]),
    }


def _receipt_kwargs(bundle: Mapping[str, object]) -> ReceiptKwargs:
    return {
        "generation_request": cast(Mapping[str, object], bundle["request"]),
        "preregistration": cast(Mapping[str, object], bundle["preregistration"]),
        "reserve_activation": cast(Mapping[str, object], bundle["activation"]),
        "generation_requests": cast(Sequence[Mapping[str, object]], bundle["requests"]),
        "allocation_manifest": cast(Mapping[str, object], bundle["manifest"]),
        "producer_dispatch": cast(Mapping[str, object], bundle["dispatch"]),
        "source_commit_projection": cast(
            CommittedRegistryOutputProjection, bundle["source_projection"]
        ),
        "provenance": cast(Mapping[str, object], bundle["provenance"]),
        "provenance_commit_projection": cast(
            CommittedRegistryOutputProjection, bundle["provenance_projection"]
        ),
        "received_png": cast(ReceivedPng, bundle["received_png"]),
    }


@pytest.mark.parametrize("ordinal", [1, 2, 3, 4])
def test_exact_provenance_and_receipt_replay_for_all_ordinals(ordinal: int) -> None:
    bundle = prepared(ordinal)
    provenance = cast(dict[str, object], bundle["provenance"])
    receipt = cast(dict[str, object], bundle["receipt"])
    assert (
        validate_generation_result_provenance(
            json.loads(canonical_json_bytes(provenance)), **_provenance_kwargs(bundle)
        )
        == provenance
    )
    assert (
        validate_source_generation_receipt(
            json.loads(canonical_json_bytes(receipt)), **_receipt_kwargs(bundle)
        ).payload()
        == receipt
    )
    assert receipt["producer_task_id"] == private_registry.TASK_ID
    assert receipt["source_producer_task_id"] == private_registry.SOURCE_PRODUCER_TASK_ID


def test_provenance_freezes_offline_post_call_and_unknown_provider_metadata() -> None:
    provenance = cast(dict[str, object], prepared()["provenance"])
    assert provenance["public_internet_egress_during_call"] == PUBLIC_EGRESS_DURING_CALL
    assert provenance["public_internet_egress_after_call"] == PUBLIC_EGRESS_AFTER_CALL
    assert provenance["control_plane_lease_state"] == CONTROL_PLANE_LEASE_STATE
    assert all(
        provenance[key] is None
        for key in ("provider_id", "model_id", "model_version", "seed", "usage", "cost")
    )
    assert not any(
        forbidden in key.lower()
        for key in provenance
        for forbidden in ("prompt", "locator", "image_bytes", "output_hint")
    )


def test_received_png_facts_cannot_be_freely_reconstructed() -> None:
    constructor = cast(Any, ReceivedPng)
    with pytest.raises(TypeError):
        constructor(byte_size=1, sha256=digest("a"), width=64, height=64)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("producer_task_id", private_registry.SOURCE_PRODUCER_TASK_ID),
        ("source_producer_task_id", private_registry.TASK_ID),
        ("source_asset_mime_type", "image/jpeg"),
        ("synthetic_only_attested", False),
        ("real_person_reference_used", True),
    ],
)
def test_fully_resigned_generation_receipt_semantic_splices_fail(
    field: str, replacement: object
) -> None:
    bundle = prepared()
    changed = deepcopy(cast(dict[str, object], bundle["receipt"]))
    changed[field] = replacement
    _resign(changed, GENERATION_RECEIPT_SCHEMA, "receipt_digest")
    with pytest.raises(ValueError, match="binding drifted"):
        validate_source_generation_receipt(changed, **_receipt_kwargs(bundle))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("public_internet_egress_during_call", "DENIED"),
        ("public_internet_egress_after_call", "ALLOWED"),
        ("control_plane_lease_state", "ACTIVE"),
        ("provider_id", "guessed-provider"),
        ("retry_count", 1),
        ("reference_image_count", 1),
        ("source_asset_width", 65),
        ("source_asset_height", 65),
    ],
)
def test_fully_resigned_provenance_policy_splices_fail(field: str, replacement: object) -> None:
    bundle = prepared()
    changed = deepcopy(cast(dict[str, object], bundle["provenance"]))
    changed[field] = replacement
    _resign(changed, PROVENANCE_SCHEMA, "provenance_digest")
    with pytest.raises(ValueError, match="binding drifted"):
        validate_generation_result_provenance(changed, **_provenance_kwargs(bundle))


def test_extra_keys_and_digest_tampering_fail_closed() -> None:
    bundle = prepared()
    provenance = deepcopy(cast(dict[str, object], bundle["provenance"]))
    provenance["prompt"] = "forbidden"
    with pytest.raises(ValueError, match="keys drifted"):
        validate_generation_result_provenance(provenance, **_provenance_kwargs(bundle))
    receipt = deepcopy(cast(dict[str, object], bundle["receipt"]))
    receipt["receipt_digest"] = digest("f")
    with pytest.raises(ValueError, match="does not replay"):
        validate_source_generation_receipt(receipt, **_receipt_kwargs(bundle))


@pytest.mark.parametrize(
    ("projection_name", "component", "field", "replacement"),
    [
        ("source", "name_receipt", "expected_parent_authority", digest("f")),
        ("source", "seal_receipt", "actual_sha256", digest("f")),
        ("source", "commit_receipt", "canonical_event_digest", digest("f")),
        ("source", "intent", "canonical_event_digest", digest("f")),
        ("source", "canonical_event", "ACTUAL_DIGEST", digest("f")),
        ("provenance", "commit_receipt", "commit_state", "NOT_COMMITTED"),
        ("provenance", "snapshot_b", "head_event_digest", digest("f")),
    ],
)
def test_complete_registry_projection_splices_fail_closed(
    projection_name: str, component: str, field: str, replacement: object
) -> None:
    bundle = prepared()
    parts = deepcopy(cast(dict[str, object], bundle[f"{projection_name}_projection_parts"]))
    if component.startswith("snapshot_"):
        snapshot = cast(private_registry.RegistrySnapshot, parts[component])
        parts[component] = private_registry.RegistrySnapshot(
            event_count=(
                cast(int, replacement) if field == "event_count" else snapshot.event_count
            ),
            head_event_digest=(
                cast(str, replacement)
                if field == "head_event_digest"
                else snapshot.head_event_digest
            ),
            semantic_snapshot_digest=snapshot.semantic_snapshot_digest,
            ordered_events=snapshot.ordered_events,
        )
    else:
        changed = deepcopy(cast(dict[str, object], parts[component]))
        changed[field] = replacement
        digest_key, schema = {
            "name_receipt": (
                "name_receipt_digest",
                private_registry.OUTPUT_NAME_RECEIPT_SCHEMA,
            ),
            "seal_receipt": ("seal_digest", private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA),
            "intent": ("intent_digest", private_registry.REGISTRY_INTENT_SCHEMA),
            "canonical_event": ("EVENT_DIGEST", private_registry.REGISTRY_EVENT_SCHEMA),
            "commit_receipt": (
                "commit_receipt_digest",
                private_registry.REGISTRY_COMMIT_SCHEMA,
            ),
        }[component]
        _resign(changed, schema, digest_key)
        parts[component] = changed
    with pytest.raises(ValueError):
        validate_committed_registry_output_projection(
            name_receipt=cast(Mapping[str, object], parts["name_receipt"]),
            seal_receipt=cast(Mapping[str, object], parts["seal_receipt"]),
            intent=cast(Mapping[str, object], parts["intent"]),
            canonical_event=cast(Mapping[str, object], parts["canonical_event"]),
            snapshot_a=cast(private_registry.RegistrySnapshot, parts["snapshot_a"]),
            snapshot_b=cast(private_registry.RegistrySnapshot, parts["snapshot_b"]),
            commit_receipt=cast(Mapping[str, object], parts["commit_receipt"]),
        )


def test_receipt_name_allocation_is_13_through_16_and_execution_owned() -> None:
    for ordinal in range(1, 5):
        bundle = prepared(ordinal)
        projected = project_generation_receipt_name_receipt(
            validated_generation_receipt=cast(
                ValidatedSourceGenerationReceipt, bundle["validated_receipt"]
            ),
            output_id=f"generation-receipt-{ordinal}",
            logical_name=f"generation-receipt-{ordinal}.json",
            allocated_at_utc="2026-08-29T01:03:00.000000Z",
        )
        assert projected["allocation_sequence"] == 12 + ordinal
        assert projected["semantic_role"] == "SOURCE_GENERATION_RECEIPT"
        assert projected["producer_task_id"] == private_registry.TASK_ID
        assert projected["allowed_tasks"] == [
            private_registry.TASK_ID,
            private_registry.REVIEW_TASK_ID,
        ]
        assert (
            projected["expected_parent_authority"]
            == cast(Mapping[str, object], bundle["provenance"])["provenance_digest"]
        )
        assert (
            validate_generation_receipt_name_receipt(
                json.loads(canonical_json_bytes(projected)),
                validated_generation_receipt=cast(
                    ValidatedSourceGenerationReceipt, bundle["validated_receipt"]
                ),
            )
            == projected
        )


def test_receipt_name_allocation_rejects_raw_self_signed_receipt() -> None:
    bundle = prepared(1)
    with pytest.raises(ValueError, match="completely validated receipt"):
        project_generation_receipt_name_receipt(
            validated_generation_receipt=cast(ValidatedSourceGenerationReceipt, bundle["receipt"]),
            output_id="generation-receipt-1",
            logical_name="generation-receipt-1.json",
            allocated_at_utc="2026-08-29T01:03:00.000000Z",
        )


def test_bridge_creator_and_source_producer_are_distinct_authorities() -> None:
    bundle = prepared()
    receipt = cast(dict[str, object], bundle["receipt"])
    validate_generation_receipt_request_binding(
        receipt,
        generation_request=cast(Mapping[str, object], bundle["request"]),
        preregistration=cast(Mapping[str, object], bundle["preregistration"]),
        reserve_activation=cast(Mapping[str, object], bundle["activation"]),
        generation_requests=cast(list[Mapping[str, object]], bundle["requests"]),
        allocation_manifest=cast(Mapping[str, object], bundle["manifest"]),
        producer_dispatch=cast(Mapping[str, object], bundle["dispatch"]),
    )
    receipt["producer_task_id"] = private_registry.SOURCE_PRODUCER_TASK_ID
    with pytest.raises(ValueError, match="producer_task_id"):
        validate_generation_receipt_request_binding(
            receipt,
            generation_request=cast(Mapping[str, object], bundle["request"]),
            preregistration=cast(Mapping[str, object], bundle["preregistration"]),
            reserve_activation=cast(Mapping[str, object], bundle["activation"]),
            generation_requests=cast(list[Mapping[str, object]], bundle["requests"]),
            allocation_manifest=cast(Mapping[str, object], bundle["manifest"]),
            producer_dispatch=cast(Mapping[str, object], bundle["dispatch"]),
        )
