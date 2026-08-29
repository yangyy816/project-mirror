from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from mirror_api import demo_d02_r2_private_registry_e2 as private_registry
from mirror_api.demo_d02_r2_epoch2_request_bridge import (
    ALLOCATION_MANIFEST_SCHEMA,
    PREFLIGHT_JSON_MAXIMUM_BYTES,
    PREFLIGHT_JSON_MEDIA_TYPE,
    PREFLIGHT_SEMANTIC_ROLES_BY_SEQUENCE,
    PREFLIGHT_SOURCE_MAXIMUM_BYTES,
    PREFLIGHT_SOURCE_MEDIA_TYPE,
    PreflightOutputNameBinding,
    build_generation_preregistration_authority,
    build_source_allocation_manifest,
    build_source_producer_dispatch,
    project_preflight_output_name_receipt,
    resolve_preflight_output_name_binding,
    validate_generation_preregistration_authority,
    validate_generation_receipt_request_binding,
    validate_source_allocation_manifest,
    validate_source_producer_dispatch,
)
from mirror_api.demo_d02_r2_generation_epoch2 import (
    GENERATION_REQUEST_SCHEMA,
    Epoch2Allocation,
    build_generation_request,
    build_reserve_activation_authority,
    expected_e1_terminal_binding,
)
from mirror_api.demo_measurement_quality import JsonValue, canonical_json_bytes, mirror_demo_digest


def digest(character: str) -> str:
    return character * 64


def canonical_round_trip(value: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(canonical_json_bytes(value)))


def prepared() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    allocations = [
        Epoch2Allocation(
            index,
            f"source-{index}",
            digest("1234"[index - 1]),
            f"prov-{index}",
            digest("5678"[index - 1]),
            digest("9abc"[index - 1]),
        )
        for index in range(1, 5)
    ]
    activation = build_reserve_activation_authority(
        terminal_binding=expected_e1_terminal_binding(),
        root_name_receipt_digest=digest("a"),
        allocations=allocations,
    )
    prereg = build_generation_preregistration_authority(
        execution_contract_digest=digest("b"),
        root_name_receipt_digest=digest("a"),
        cohort_policy_digest=digest("c"),
    )
    preregistration_digest = cast(str, prereg["generation_preregistration_digest"])
    requests = [
        build_generation_request(
            reserve_activation=activation,
            generation_preregistration_digest=preregistration_digest,
            candidate_ordinal=index,
        )
        for index in range(1, 5)
    ]
    return (
        cast(dict[str, object], activation),
        cast(dict[str, object], prereg),
        cast(list[dict[str, object]], requests),
    )


def test_preflight_binding_matrix_is_exact_and_acyclic() -> None:
    capability = digest("1")
    preregistration = digest("2")
    manifest = digest("3")
    dispatch = digest("4")

    prereg = resolve_preflight_output_name_binding(
        "SOURCE_GENERATION_PREREGISTRATION",
        generation_capability_authority_digest=capability,
    )
    allocation = resolve_preflight_output_name_binding(
        "SOURCE_ALLOCATION_MANIFEST",
        generation_preregistration_digest=preregistration,
    )
    producer_dispatch = resolve_preflight_output_name_binding(
        "SOURCE_PRODUCER_DISPATCH_RECEIPT",
        source_allocation_manifest_digest=manifest,
    )
    source = resolve_preflight_output_name_binding(
        "SOURCE_CANDIDATE",
        generation_preregistration_digest=preregistration,
    )
    provenance = resolve_preflight_output_name_binding(
        "SOURCE_PROVENANCE",
        generation_preregistration_digest=preregistration,
    )
    negative = resolve_preflight_output_name_binding(
        "NEGATIVE_RECEIPT",
        source_producer_dispatch_digest=dispatch,
    )

    assert prereg.expected_parent_authority == capability
    assert allocation.expected_parent_authority == preregistration
    assert producer_dispatch.expected_parent_authority == manifest
    assert source.expected_parent_authority == preregistration
    assert provenance.expected_parent_authority == preregistration
    assert negative.expected_parent_authority == dispatch
    assert source.producer_task_id == private_registry.SOURCE_PRODUCER_TASK_ID
    assert provenance.producer_task_id == private_registry.SOURCE_PRODUCER_TASK_ID
    assert all(
        item.producer_task_id == private_registry.TASK_ID
        for item in (prereg, allocation, producer_dispatch, negative)
    )
    assert (source.expected_media_type, source.maximum_bytes) == (
        PREFLIGHT_SOURCE_MEDIA_TYPE,
        PREFLIGHT_SOURCE_MAXIMUM_BYTES,
    )
    assert all(
        (item.expected_media_type, item.maximum_bytes)
        == (PREFLIGHT_JSON_MEDIA_TYPE, PREFLIGHT_JSON_MAXIMUM_BYTES)
        for item in (prereg, allocation, producer_dispatch, provenance, negative)
    )

    with pytest.raises(ValueError, match="semantic role"):
        resolve_preflight_output_name_binding("SOURCE_GENERATION_RECEIPT")
    with pytest.raises(ValueError, match="dispatch digest"):
        resolve_preflight_output_name_binding("NEGATIVE_RECEIPT")

    root_receipt: dict[str, object] = {
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "dispatch_epoch": private_registry.DISPATCH_EPOCH,
        "receipt_digest": digest("a"),
        "contract_digest": digest("b"),
    }
    for sequence, semantic_role in enumerate(PREFLIGHT_SEMANTIC_ROLES_BY_SEQUENCE, start=1):
        binding = resolve_preflight_output_name_binding(
            semantic_role,
            generation_capability_authority_digest=capability,
            generation_preregistration_digest=preregistration,
            source_allocation_manifest_digest=manifest,
            source_producer_dispatch_digest=dispatch,
        )
        projected = project_preflight_output_name_receipt(
            root_receipt=root_receipt,
            output_id=f"e2-preflight-{sequence}",
            allocation_sequence=sequence,
            semantic_role=semantic_role,
            logical_name=(
                f"e2-preflight-{sequence}.png"
                if semantic_role == "SOURCE_CANDIDATE"
                else f"e2-preflight-{sequence}.json"
            ),
            binding=binding,
            allocated_at_utc="2026-08-29T00:00:00.000000Z",
        )
        assert projected["allocation_sequence"] == sequence
        assert projected["semantic_role"] == semantic_role

    with pytest.raises(ValueError, match="sequence and semantic role"):
        project_preflight_output_name_receipt(
            root_receipt=root_receipt,
            output_id="e2-preflight-wrong-sequence",
            allocation_sequence=5,
            semantic_role="SOURCE_CANDIDATE",
            logical_name="e2-preflight-wrong-sequence.png",
            binding=source,
            allocated_at_utc="2026-08-29T00:00:00.000000Z",
        )
    with pytest.raises(ValueError, match="role envelope"):
        project_preflight_output_name_receipt(
            root_receipt=root_receipt,
            output_id="e2-preflight-wrong-envelope",
            allocation_sequence=4,
            semantic_role="SOURCE_CANDIDATE",
            logical_name="e2-preflight-wrong-envelope.png",
            binding=PreflightOutputNameBinding(
                producer_task_id=source.producer_task_id,
                expected_parent_authority=source.expected_parent_authority,
                expected_media_type=PREFLIGHT_JSON_MEDIA_TYPE,
                maximum_bytes=source.maximum_bytes,
            ),
            allocated_at_utc="2026-08-29T00:00:00.000000Z",
        )


def test_pure_name_receipt_projection_matches_registry_write_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root_receipt: dict[str, object] = {
        "evidence_root_id": private_registry.EVIDENCE_ROOT_ID,
        "dispatch_epoch": private_registry.DISPATCH_EPOCH,
        "receipt_digest": digest("a"),
        "contract_digest": digest("b"),
    }
    binding = resolve_preflight_output_name_binding(
        "SOURCE_CANDIDATE",
        generation_preregistration_digest=digest("c"),
    )
    arguments = {
        "output_id": "e2-source-projection-1",
        "allocation_sequence": 4,
        "semantic_role": "SOURCE_CANDIDATE",
        "logical_name": "e2-source-projection-1.png",
        "producer_task_id": binding.producer_task_id,
        "expected_parent_authority": binding.expected_parent_authority,
        "expected_media_type": binding.expected_media_type,
        "maximum_bytes": binding.maximum_bytes,
        "allocated_at_utc": "2026-08-29T00:00:00.000000Z",
    }
    projected = project_preflight_output_name_receipt(
        root_receipt=root_receipt,
        output_id=cast(str, arguments["output_id"]),
        allocation_sequence=cast(int, arguments["allocation_sequence"]),
        semantic_role=cast(str, arguments["semantic_role"]),
        logical_name=cast(str, arguments["logical_name"]),
        binding=binding,
        allocated_at_utc=cast(str, arguments["allocated_at_utc"]),
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        private_registry,
        "load_root_name_receipt",
        lambda _root, _authority: root_receipt,
    )
    monkeypatch.setattr(private_registry, "_principal_mutex", lambda _root: nullcontext())
    monkeypatch.setattr(
        private_registry,
        "_initialize_registry_pair_locked",
        lambda _root, _receipt: None,
    )
    monkeypatch.setattr(
        private_registry,
        "_control_path",
        lambda _root, _destination, _name: tmp_path / "projected-receipt.json",
    )
    monkeypatch.setattr(
        private_registry,
        "_validate_name_allocation_uniqueness",
        lambda _root, _receipt, _payload, _path: None,
    )
    monkeypatch.setattr(
        private_registry,
        "_write_exclusive_json",
        lambda _root, _path, payload, maximum_bytes: captured.update(payload),
    )
    monkeypatch.setattr(
        private_registry,
        "_load_name_receipt",
        lambda _path, _receipt: cast(private_registry.JsonObject, captured.copy()),
    )

    authority = cast(private_registry.RootReceiptAuthority, object())
    observed = private_registry.allocate_output_name_receipt(
        tmp_path,
        authority,
        output_id=cast(str, arguments["output_id"]),
        allocation_sequence=cast(int, arguments["allocation_sequence"]),
        semantic_role=cast(str, arguments["semantic_role"]),
        logical_name=cast(str, arguments["logical_name"]),
        producer_task_id=cast(str, arguments["producer_task_id"]),
        expected_parent_authority=cast(str, arguments["expected_parent_authority"]),
        expected_media_type=cast(str, arguments["expected_media_type"]),
        maximum_bytes=cast(int, arguments["maximum_bytes"]),
        allocated_at_utc=cast(str, arguments["allocated_at_utc"]),
    )
    assert observed == projected
    assert not (tmp_path / "projected-receipt.json").exists()


def test_exact_bridge_happy_path_and_deterministic_replay() -> None:
    activation, prereg, requests = prepared()
    manifest = build_source_allocation_manifest(
        execution_contract_digest=digest("b"),
        preregistration=prereg,
        reserve_activation=activation,
        generation_requests=requests,
    )
    dispatch = build_source_producer_dispatch(
        execution_contract_digest=digest("b"),
        preregistration=prereg,
        allocation_manifest=manifest,
        reserve_activation=activation,
        generation_requests=requests,
    )
    assert (
        build_generation_preregistration_authority(
            execution_contract_digest=digest("b"),
            root_name_receipt_digest=digest("a"),
            cohort_policy_digest=digest("c"),
        )
        == prereg
    )
    assert (
        build_source_allocation_manifest(
            execution_contract_digest=digest("b"),
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=requests,
        )
        == manifest
    )
    assert validate_generation_preregistration_authority(prereg) == prereg
    assert (
        validate_source_allocation_manifest(
            manifest,
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=requests,
        )
        == manifest
    )
    assert (
        validate_source_producer_dispatch(
            dispatch,
            preregistration=prereg,
            allocation_manifest=manifest,
            reserve_activation=activation,
            generation_requests=requests,
        )
        == dispatch
    )
    assert dispatch["dispatch_state"] == "AUTHORIZED_EXACT_ALLOCATIONS_ONLY"
    entries = cast(list[dict[str, object]], manifest["ordered_allocations"])
    for request, entry in zip(requests, entries, strict=True):
        assert entry["generation_request_policy_digest"] == request["generation_request_digest"]
    canonical_activation = canonical_round_trip(activation)
    canonical_prereg = canonical_round_trip(prereg)
    canonical_requests = [canonical_round_trip(request) for request in requests]
    assert (
        build_source_allocation_manifest(
            execution_contract_digest=digest("b"),
            preregistration=canonical_prereg,
            reserve_activation=canonical_activation,
            generation_requests=canonical_requests,
        )
        == manifest
    )
    canonical_manifest = canonical_round_trip(manifest)
    assert (
        build_source_producer_dispatch(
            execution_contract_digest=digest("b"),
            preregistration=canonical_prereg,
            allocation_manifest=canonical_manifest,
            reserve_activation=canonical_activation,
            generation_requests=canonical_requests,
        )
        == dispatch
    )
    canonical_dispatch = canonical_round_trip(dispatch)
    assert validate_generation_preregistration_authority(canonical_prereg) == canonical_prereg
    assert (
        validate_source_allocation_manifest(
            canonical_manifest,
            preregistration=canonical_prereg,
            reserve_activation=canonical_activation,
            generation_requests=canonical_requests,
        )
        == canonical_manifest
    )
    assert (
        validate_source_producer_dispatch(
            canonical_dispatch,
            preregistration=canonical_prereg,
            allocation_manifest=canonical_manifest,
            reserve_activation=canonical_activation,
            generation_requests=canonical_requests,
        )
        == canonical_dispatch
    )
    request = canonical_requests[0]
    receipt = canonical_round_trip(
        {
            "generation_request_policy_digest": request["generation_request_digest"],
            "candidate_ordinal": request["candidate_ordinal"],
            "execution_contract_digest": canonical_manifest["execution_contract_digest"],
            "evidence_root_id": request["e2_root_id"],
            "root_name_receipt_digest": canonical_prereg["root_name_receipt_digest"],
            "generation_capability_authority_digest": request[
                "generation_capability_authority_digest"
            ],
            "generation_preregistration_digest": request["generation_preregistration_digest"],
            "source_allocation_manifest_digest": canonical_manifest[
                "source_allocation_manifest_digest"
            ],
            "source_producer_dispatch_digest": canonical_dispatch[
                "source_producer_dispatch_digest"
            ],
            "producer_task_id": request["producer_task_id"],
            "dispatch_epoch": request["dispatch_epoch"],
            "source_output_id": request["source_output_id"],
            "output_name_receipt_digest": request["source_name_receipt_digest"],
            "source_provenance_output_id": request["provenance_output_id"],
            "source_provenance_name_receipt_digest": request["provenance_name_receipt_digest"],
        }
    )
    validate_generation_receipt_request_binding(
        receipt,
        generation_request=request,
        preregistration=canonical_prereg,
        reserve_activation=canonical_activation,
        generation_requests=canonical_requests,
        allocation_manifest=canonical_manifest,
        producer_dispatch=canonical_dispatch,
    )


@pytest.mark.parametrize(
    "field",
    [
        "candidate_ordinal",
        "source_output_id",
        "output_name_receipt_digest",
        "source_provenance_output_id",
        "source_provenance_name_receipt_digest",
        "source_expected_media_type",
    ],
)
def test_fully_resigned_manifest_still_rejects_request_mismatch(field: str) -> None:
    activation, prereg, requests = prepared()
    manifest = build_source_allocation_manifest(
        execution_contract_digest=digest("b"),
        preregistration=prereg,
        reserve_activation=activation,
        generation_requests=requests,
    )
    changed = deepcopy(manifest)
    entries = cast(list[dict[str, object]], changed["ordered_allocations"])
    entries[0][field] = "wrong" if field != "candidate_ordinal" else 4
    changed["source_allocation_manifest_digest"] = mirror_demo_digest(
        ALLOCATION_MANIFEST_SCHEMA,
        cast(
            dict[str, JsonValue],
            {
                key: value
                for key, value in changed.items()
                if key != "source_allocation_manifest_digest"
            },
        ),
    )
    canonical_activation = canonical_round_trip(activation)
    canonical_requests = [canonical_round_trip(request) for request in requests]
    canonical_changed = canonical_round_trip(changed)
    with pytest.raises(ValueError):
        validate_source_allocation_manifest(
            canonical_changed,
            preregistration=prereg,
            reserve_activation=canonical_activation,
            generation_requests=canonical_requests,
        )


def test_wrong_legacy_e1_digest_and_order_cardinality_reject() -> None:
    activation, prereg, requests = prepared()
    bad_requests = deepcopy(requests)
    bad_requests[0]["generation_request_digest"] = digest("e")
    with pytest.raises(ValueError):
        build_source_allocation_manifest(
            execution_contract_digest=digest("b"),
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=bad_requests,
        )
    with pytest.raises(ValueError):
        build_source_allocation_manifest(
            execution_contract_digest=digest("b"),
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=requests[:3],
        )
    with pytest.raises(ValueError):
        build_source_allocation_manifest(
            execution_contract_digest=digest("b"),
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=list(reversed(requests)),
        )


def test_fully_resigned_request_and_contract_drift_fail_closed() -> None:
    activation, prereg, requests = prepared()
    changed_request = deepcopy(requests[0])
    changed_request["prompt_material_digest"] = digest("f")
    changed_request["generation_request_digest"] = mirror_demo_digest(
        GENERATION_REQUEST_SCHEMA,
        cast(
            dict[str, JsonValue],
            {
                key: value
                for key, value in changed_request.items()
                if key != "generation_request_digest"
            },
        ),
    )
    canonical_activation = canonical_round_trip(activation)
    changed_requests = [
        canonical_round_trip(changed_request),
        *[canonical_round_trip(request) for request in requests[1:]],
    ]
    with pytest.raises(ValueError):
        build_source_allocation_manifest(
            execution_contract_digest=digest("b"),
            preregistration=prereg,
            reserve_activation=canonical_activation,
            generation_requests=changed_requests,
        )
    with pytest.raises(ValueError):
        build_source_allocation_manifest(
            execution_contract_digest=digest("d"),
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=requests,
        )


def test_unknown_keys_and_receipt_core_tuple_binding() -> None:
    activation, prereg, requests = prepared()
    bad = deepcopy(prereg)
    bad["unknown"] = True
    with pytest.raises(ValueError):
        validate_generation_preregistration_authority(bad)
    manifest = build_source_allocation_manifest(
        execution_contract_digest=digest("b"),
        preregistration=prereg,
        reserve_activation=activation,
        generation_requests=requests,
    )
    dispatch = build_source_producer_dispatch(
        execution_contract_digest=digest("b"),
        preregistration=prereg,
        allocation_manifest=manifest,
        reserve_activation=activation,
        generation_requests=requests,
    )
    request = requests[0]
    receipt = {
        "generation_request_policy_digest": request["generation_request_digest"],
        "candidate_ordinal": request["candidate_ordinal"],
        "execution_contract_digest": manifest["execution_contract_digest"],
        "evidence_root_id": request["e2_root_id"],
        "root_name_receipt_digest": prereg["root_name_receipt_digest"],
        "generation_capability_authority_digest": request["generation_capability_authority_digest"],
        "generation_preregistration_digest": request["generation_preregistration_digest"],
        "source_allocation_manifest_digest": manifest["source_allocation_manifest_digest"],
        "source_producer_dispatch_digest": dispatch["source_producer_dispatch_digest"],
        "producer_task_id": request["producer_task_id"],
        "dispatch_epoch": request["dispatch_epoch"],
        "source_output_id": request["source_output_id"],
        "output_name_receipt_digest": request["source_name_receipt_digest"],
        "source_provenance_output_id": request["provenance_output_id"],
        "source_provenance_name_receipt_digest": request["provenance_name_receipt_digest"],
    }
    validate_generation_receipt_request_binding(
        receipt,
        generation_request=request,
        preregistration=prereg,
        reserve_activation=activation,
        generation_requests=requests,
        allocation_manifest=manifest,
        producer_dispatch=dispatch,
    )
    receipt["generation_request_policy_digest"] = digest("f")
    with pytest.raises(ValueError):
        validate_generation_receipt_request_binding(
            receipt,
            generation_request=request,
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=requests,
            allocation_manifest=manifest,
            producer_dispatch=dispatch,
        )


def test_receipt_rejects_valid_request_from_wrong_manifest_member() -> None:
    activation, prereg, requests = prepared()
    manifest = build_source_allocation_manifest(
        execution_contract_digest=digest("b"),
        preregistration=prereg,
        reserve_activation=activation,
        generation_requests=requests,
    )
    dispatch = build_source_producer_dispatch(
        execution_contract_digest=digest("b"),
        preregistration=prereg,
        allocation_manifest=manifest,
        reserve_activation=activation,
        generation_requests=requests,
    )
    request = requests[0]
    receipt = {
        "generation_request_policy_digest": request["generation_request_digest"],
        "candidate_ordinal": request["candidate_ordinal"],
        "execution_contract_digest": manifest["execution_contract_digest"],
        "evidence_root_id": request["e2_root_id"],
        "root_name_receipt_digest": prereg["root_name_receipt_digest"],
        "generation_capability_authority_digest": request["generation_capability_authority_digest"],
        "generation_preregistration_digest": request["generation_preregistration_digest"],
        "source_allocation_manifest_digest": manifest["source_allocation_manifest_digest"],
        "source_producer_dispatch_digest": dispatch["source_producer_dispatch_digest"],
        "producer_task_id": request["producer_task_id"],
        "dispatch_epoch": request["dispatch_epoch"],
        "source_output_id": request["source_output_id"],
        "output_name_receipt_digest": request["source_name_receipt_digest"],
        "source_provenance_output_id": request["provenance_output_id"],
        "source_provenance_name_receipt_digest": request["provenance_name_receipt_digest"],
    }
    with pytest.raises(ValueError):
        validate_generation_receipt_request_binding(
            receipt,
            generation_request=requests[1],
            preregistration=prereg,
            reserve_activation=activation,
            generation_requests=requests,
            allocation_manifest=manifest,
            producer_dispatch=dispatch,
        )
