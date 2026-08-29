from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import TypedDict, cast

import pytest

from mirror_api import demo_d02_r2_private_registry_e2 as private_registry
from mirror_api.demo_d02_r2_epoch2_generation_receipt import (
    CONTROL_PLANE_LEASE_STATE,
    GENERATION_RECEIPT_SCHEMA,
    PROVENANCE_SCHEMA,
    PUBLIC_EGRESS_AFTER_CALL,
    PUBLIC_EGRESS_DURING_CALL,
    build_generation_result_provenance,
    build_source_generation_receipt,
    project_generation_receipt_name_receipt,
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
    source_name_receipt: Mapping[str, object]
    source_seal_receipt: Mapping[str, object]
    source_commit_receipt: Mapping[str, object]
    provenance_name_receipt: Mapping[str, object]


class ReceiptKwargs(ProvenanceKwargs):
    provenance: Mapping[str, object]
    provenance_seal_receipt: Mapping[str, object]
    provenance_commit_receipt: Mapping[str, object]


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


def _commit_receipt(
    *,
    name_receipt: Mapping[str, object],
    seal_receipt: Mapping[str, object],
    event_count: int,
) -> dict[str, object]:
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
    head = hashlib.sha256(f"head-{event_count}".encode()).hexdigest()
    snapshot = hashlib.sha256(f"snapshot-{event_count}".encode()).hexdigest()
    payload: dict[str, JsonValue] = {
        "schema_version": private_registry.REGISTRY_COMMIT_SCHEMA,
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": cast(str, name_receipt["root_name_receipt_digest"]),
        "execution_contract_digest": cast(str, name_receipt["execution_contract_digest"]),
        "transaction_id": transaction_id,
        "intent_digest": hashlib.sha256(f"intent-{event_count}".encode()).hexdigest(),
        "output_id": cast(str, name_receipt["output_id"]),
        "canonical_event_digest": hashlib.sha256(f"event-{event_count}".encode()).hexdigest(),
        "copy_a_event_count": event_count,
        "copy_a_head_event_digest": head,
        "copy_a_semantic_snapshot_digest": snapshot,
        "copy_b_event_count": event_count,
        "copy_b_head_event_digest": head,
        "copy_b_semantic_snapshot_digest": snapshot,
        "commit_state": "COMMITTED_BOTH_COPIES",
        "created_at_utc": "2026-08-29T01:02:00.000000Z",
    }
    payload["commit_receipt_digest"] = mirror_demo_digest(
        private_registry.REGISTRY_COMMIT_SCHEMA, payload
    )
    return cast(dict[str, object], payload)


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
    source_sha = hashlib.sha256(f"source-bytes-{ordinal}".encode()).hexdigest()
    source_size = 10_000 + ordinal
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
    source_commit = _commit_receipt(
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
        source_name_receipt=source_name,
        source_seal_receipt=source_seal,
        source_commit_receipt=source_commit,
        provenance_name_receipt=provenance_name,
        source_asset_sha256=source_sha,
        source_asset_byte_size=source_size,
        source_asset_width=1024,
        source_asset_height=1024,
    )
    provenance_bytes = canonical_json_bytes(provenance)
    provenance_seal = _seal_receipt(
        name_receipt=provenance_name,
        actual_sha256=hashlib.sha256(provenance_bytes).hexdigest(),
        byte_size=len(provenance_bytes),
        media_type="application/json",
        authority_digest=cast(str, provenance["provenance_digest"]),
    )
    provenance_commit = _commit_receipt(
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
        source_name_receipt=source_name,
        source_seal_receipt=source_seal,
        source_commit_receipt=source_commit,
        provenance=provenance,
        provenance_name_receipt=provenance_name,
        provenance_seal_receipt=provenance_seal,
        provenance_commit_receipt=provenance_commit,
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
        "source_commit": source_commit,
        "provenance_name": provenance_name,
        "provenance": provenance,
        "provenance_seal": provenance_seal,
        "provenance_commit": provenance_commit,
        "receipt": receipt,
    }


def _provenance_kwargs(bundle: Mapping[str, object]) -> ProvenanceKwargs:
    return {
        "generation_request": cast(Mapping[str, object], bundle["request"]),
        "preregistration": cast(Mapping[str, object], bundle["preregistration"]),
        "reserve_activation": cast(Mapping[str, object], bundle["activation"]),
        "generation_requests": cast(Sequence[Mapping[str, object]], bundle["requests"]),
        "allocation_manifest": cast(Mapping[str, object], bundle["manifest"]),
        "producer_dispatch": cast(Mapping[str, object], bundle["dispatch"]),
        "source_name_receipt": cast(Mapping[str, object], bundle["source_name"]),
        "source_seal_receipt": cast(Mapping[str, object], bundle["source_seal"]),
        "source_commit_receipt": cast(Mapping[str, object], bundle["source_commit"]),
        "provenance_name_receipt": cast(Mapping[str, object], bundle["provenance_name"]),
    }


def _receipt_kwargs(bundle: Mapping[str, object]) -> ReceiptKwargs:
    return {
        **_provenance_kwargs(bundle),
        "provenance": cast(Mapping[str, object], bundle["provenance"]),
        "provenance_seal_receipt": cast(Mapping[str, object], bundle["provenance_seal"]),
        "provenance_commit_receipt": cast(Mapping[str, object], bundle["provenance_commit"]),
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
        )
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
    ("component", "field", "replacement"),
    [
        ("source_name", "expected_parent_authority", digest("f")),
        ("source_seal", "actual_sha256", digest("f")),
        ("source_commit", "copy_b_event_count", 99),
        ("provenance_seal", "authority_digest", digest("f")),
        ("provenance_commit", "copy_b_head_event_digest", digest("f")),
    ],
)
def test_registry_chain_splices_fail_closed(
    component: str, field: str, replacement: object
) -> None:
    bundle = prepared()
    changed = deepcopy(cast(dict[str, object], bundle[component]))
    changed[field] = replacement
    digest_key, schema = (
        ("name_receipt_digest", private_registry.OUTPUT_NAME_RECEIPT_SCHEMA)
        if component.endswith("name")
        else (
            ("seal_digest", private_registry.OUTPUT_SEAL_RECEIPT_SCHEMA)
            if component.endswith("seal")
            else ("commit_receipt_digest", private_registry.REGISTRY_COMMIT_SCHEMA)
        )
    )
    _resign(changed, schema, digest_key)
    bundle[component] = changed
    with pytest.raises(ValueError):
        if component.startswith("source"):
            validate_generation_result_provenance(
                bundle["provenance"], **_provenance_kwargs(bundle)
            )
        else:
            validate_source_generation_receipt(bundle["receipt"], **_receipt_kwargs(bundle))


def test_receipt_name_allocation_is_13_through_16_and_execution_owned() -> None:
    for ordinal in range(1, 5):
        bundle = prepared(ordinal)
        projected = project_generation_receipt_name_receipt(
            generation_receipt=cast(Mapping[str, object], bundle["receipt"]),
            provenance_commit_receipt=cast(Mapping[str, object], bundle["provenance_commit"]),
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
                generation_receipt=cast(Mapping[str, object], bundle["receipt"]),
                provenance_commit_receipt=cast(Mapping[str, object], bundle["provenance_commit"]),
            )
            == projected
        )


def test_receipt_name_allocation_rejects_unrelated_provenance_commit() -> None:
    first = prepared(1)
    second = prepared(2)
    with pytest.raises(ValueError, match="committed provenance"):
        project_generation_receipt_name_receipt(
            generation_receipt=cast(Mapping[str, object], first["receipt"]),
            provenance_commit_receipt=cast(Mapping[str, object], second["provenance_commit"]),
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
