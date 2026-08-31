from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from mirror_api import demo_d02_r2_generation_execution as subject
from mirror_api.demo_d02_r2_generation_capability import (
    build_generation_capability_authority,
    build_generation_request_policy,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest

EXPECTED_PREREGISTRATION_KEYS = (
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
EXPECTED_MANIFEST_KEYS = (
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
EXPECTED_ENTRY_KEYS = (
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
EXPECTED_DISPATCH_KEYS = (
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

EXECUTION = "1" * 64
ROOT = "2" * 64
COHORT = "3" * 64


def _resign(value: subject.JsonObject, schema: str, digest_key: str) -> None:
    value[digest_key] = mirror_demo_digest(
        schema,
        cast(
            Mapping[str, subject.JsonValue],
            {key: item for key, item in value.items() if key != digest_key},
        ),
    )


def _allocation_entries(value: Mapping[str, object]) -> list[subject.JsonObject]:
    entries = value["ordered_allocations"]
    assert isinstance(entries, list)
    assert all(isinstance(entry, dict) for entry in entries)
    return cast(list[subject.JsonObject], entries)


def _preregistration() -> subject.JsonObject:
    return subject.build_source_generation_preregistration_authority(
        execution_contract_digest=EXECUTION,
        root_name_receipt_digest=ROOT,
        cohort_policy_digest=COHORT,
    )


def _requests(preregistration: Mapping[str, object]) -> list[subject.JsonObject]:
    digest = cast(str, preregistration["generation_preregistration_digest"])
    output_name_chars = ("a", "b", "c", "d")
    provenance_name_chars = ("e", "f", "0", "1")
    prompt_chars = ("2", "3", "4", "5")
    return [
        build_generation_request_policy(
            candidate_ordinal=ordinal,
            source_output_id=f"source-{ordinal}",
            output_name_receipt_digest=(output_name_chars[ordinal - 1] * 64),
            source_provenance_output_id=f"provenance-{ordinal}",
            source_provenance_name_receipt_digest=(provenance_name_chars[ordinal - 1] * 64),
            prompt_material_digest=(prompt_chars[ordinal - 1] * 64),
            root_name_receipt_digest=ROOT,
            generation_preregistration_digest=digest,
        )
        for ordinal in (1, 2, 3, 4)
    ]


def _manifest(
    preregistration: Mapping[str, object], requests: list[subject.JsonObject]
) -> subject.JsonObject:
    return subject.build_source_allocation_manifest(
        execution_contract_digest=EXECUTION,
        root_name_receipt_digest=ROOT,
        generation_preregistration_digest=cast(
            str, preregistration["generation_preregistration_digest"]
        ),
        generation_request_policies=requests,
    )


def _dispatch(
    preregistration: Mapping[str, object], manifest: Mapping[str, object]
) -> subject.JsonObject:
    return subject.build_source_producer_dispatch_receipt(
        execution_contract_digest=EXECUTION,
        root_name_receipt_digest=ROOT,
        generation_preregistration_digest=cast(
            str, preregistration["generation_preregistration_digest"]
        ),
        source_allocation_manifest_digest=cast(str, manifest["source_allocation_manifest_digest"]),
    )


def _validate_preregistration(value: Mapping[str, object]) -> None:
    capability = build_generation_capability_authority()
    subject.validate_source_generation_preregistration_authority(
        value,
        expected_execution_contract_digest=EXECUTION,
        expected_root_name_receipt_digest=ROOT,
        expected_parent_authority_digest=cast(
            str, capability["generation_capability_authority_digest"]
        ),
        expected_cohort_policy_digest=COHORT,
    )


def _validate_manifest(
    value: Mapping[str, object],
    preregistration: Mapping[str, object],
    requests: list[subject.JsonObject],
) -> None:
    subject.validate_source_allocation_manifest(
        value,
        expected_execution_contract_digest=EXECUTION,
        expected_root_name_receipt_digest=ROOT,
        expected_parent_authority_digest=cast(
            str, preregistration["generation_preregistration_digest"]
        ),
        generation_request_policies=requests,
    )


def _validate_dispatch(
    value: Mapping[str, object],
    preregistration: Mapping[str, object],
    manifest: Mapping[str, object],
) -> None:
    subject.validate_source_producer_dispatch_receipt(
        value,
        expected_execution_contract_digest=EXECUTION,
        expected_root_name_receipt_digest=ROOT,
        expected_parent_authority_digest=cast(str, manifest["source_allocation_manifest_digest"]),
        expected_generation_preregistration_digest=cast(
            str, preregistration["generation_preregistration_digest"]
        ),
    )


def test_builders_are_deterministic_exactly_ordered_and_replay() -> None:
    preregistration = _preregistration()
    requests = _requests(preregistration)
    manifest = _manifest(preregistration, requests)
    dispatch = _dispatch(preregistration, manifest)

    assert tuple(preregistration) == EXPECTED_PREREGISTRATION_KEYS
    assert tuple(manifest) == EXPECTED_MANIFEST_KEYS
    assert tuple(_allocation_entries(manifest)[0]) == EXPECTED_ENTRY_KEYS
    assert tuple(dispatch) == EXPECTED_DISPATCH_KEYS
    assert preregistration == _preregistration()
    assert manifest == _manifest(preregistration, requests)
    assert dispatch == _dispatch(preregistration, manifest)
    _validate_preregistration(preregistration)
    _validate_manifest(manifest, preregistration, requests)
    _validate_dispatch(dispatch, preregistration, manifest)


def test_builders_return_fresh_values() -> None:
    first = _preregistration()
    second = _preregistration()
    cast(list[subject.JsonValue], first["ordered_candidate_ordinals"]).append(99)
    assert second["ordered_candidate_ordinals"] == [1, 2, 3, 4]

    first_requests = _requests(second)
    first_manifest = _manifest(second, first_requests)
    second_manifest = _manifest(second, _requests(second))
    _allocation_entries(first_manifest)[0]["source_output_id"] = "mutated"
    assert _allocation_entries(second_manifest)[0]["source_output_id"] == "source-1"


@pytest.mark.parametrize(
    "key,replacement",
    (("source_count", True), ("ordered_candidate_ordinals", [1, 2, 4, 3])),
)
def test_preregistration_rejects_type_and_order_drift_after_resign(
    key: str, replacement: subject.JsonValue
) -> None:
    value = _preregistration()
    value[key] = replacement
    _resign(
        value,
        "mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1",
        "generation_preregistration_digest",
    )
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_preregistration(value)


def test_preregistration_rejects_fully_resigned_execution_root_and_capability_drift() -> None:
    for key, replacement in (
        ("execution_contract_digest", "a" * 64),
        ("root_name_receipt_digest", "b" * 64),
        ("generation_capability_authority_digest", "c" * 64),
    ):
        value = _preregistration()
        value[key] = replacement
        _resign(
            value,
            "mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1",
            "generation_preregistration_digest",
        )
        with pytest.raises(subject.D02R2GenerationExecutionError):
            _validate_preregistration(value)


def test_preregistration_rejects_fully_resigned_cohort_policy_splice() -> None:
    value = _preregistration()
    value["cohort_policy_digest"] = "d" * 64
    _resign(
        value,
        "mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1",
        "generation_preregistration_digest",
    )

    with pytest.raises(
        subject.D02R2GenerationExecutionError,
        match="cohort policy differs from expected authority",
    ):
        _validate_preregistration(value)


def test_manifest_rejects_reordered_and_duplicate_allocations_after_resign() -> None:
    preregistration = _preregistration()
    requests = _requests(preregistration)
    manifest = _manifest(preregistration, requests)
    _allocation_entries(manifest).reverse()
    _resign(
        manifest,
        "mirror.demo/D02R2SourceAllocationManifest/v1",
        "source_allocation_manifest_digest",
    )
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_manifest(manifest, preregistration, requests)

    manifest = _manifest(preregistration, requests)
    entries = _allocation_entries(manifest)
    entries[1] = dict(entries[0])
    _resign(
        manifest,
        "mirror.demo/D02R2SourceAllocationManifest/v1",
        "source_allocation_manifest_digest",
    )
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_manifest(manifest, preregistration, requests)


@pytest.mark.parametrize(
    "entry_key",
    (
        "source_output_id",
        "source_provenance_output_id",
        "output_name_receipt_digest",
        "source_provenance_name_receipt_digest",
        "generation_request_policy_digest",
    ),
)
def test_manifest_rejects_every_cross_entry_duplicate(entry_key: str) -> None:
    preregistration = _preregistration()
    requests = _requests(preregistration)
    manifest = _manifest(preregistration, requests)
    entries = _allocation_entries(manifest)
    entries[1][entry_key] = entries[0][entry_key]
    _resign(
        manifest,
        "mirror.demo/D02R2SourceAllocationManifest/v1",
        "source_allocation_manifest_digest",
    )
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_manifest(manifest, preregistration, requests)


def test_manifest_rejects_fully_resigned_entry_request_and_parent_drift() -> None:
    preregistration = _preregistration()
    requests = _requests(preregistration)
    manifest = _manifest(preregistration, requests)
    entries = _allocation_entries(manifest)
    entries[0]["source_maximum_bytes"] = 1
    _resign(
        manifest,
        "mirror.demo/D02R2SourceAllocationManifest/v1",
        "source_allocation_manifest_digest",
    )
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_manifest(manifest, preregistration, requests)

    manifest = _manifest(preregistration, requests)
    manifest["generation_preregistration_digest"] = "d" * 64
    _resign(
        manifest,
        "mirror.demo/D02R2SourceAllocationManifest/v1",
        "source_allocation_manifest_digest",
    )
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_manifest(manifest, preregistration, requests)


def test_dispatch_rejects_all_resigned_authority_and_policy_drift() -> None:
    preregistration = _preregistration()
    requests = _requests(preregistration)
    manifest = _manifest(preregistration, requests)
    for key, replacement in (
        ("execution_contract_digest", "a" * 64),
        ("root_name_receipt_digest", "b" * 64),
        ("source_allocation_manifest_digest", "c" * 64),
        ("generation_preregistration_digest", "d" * 64),
        ("generation_capability_authority_digest", "e" * 64),
        ("approved_endpoint_policy_digest", "f" * 64),
        ("call_ceiling", 5),
    ):
        dispatch = _dispatch(preregistration, manifest)
        dispatch[key] = replacement
        _resign(
            dispatch,
            "mirror.demo/D02R2SourceProducerDispatchReceipt/v1",
            "source_producer_dispatch_digest",
        )
        with pytest.raises(subject.D02R2GenerationExecutionError):
            _validate_dispatch(dispatch, preregistration, manifest)


def test_uppercase_digest_extra_key_and_raw_float_fail_closed() -> None:
    preregistration = _preregistration()
    preregistration["cohort_policy_digest"] = "A" * 64
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_preregistration(preregistration)

    manifest = _manifest(_preregistration(), _requests(_preregistration()))
    manifest["extra"] = "nope"
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_manifest(manifest, _preregistration(), _requests(_preregistration()))

    dispatch = _dispatch(
        _preregistration(), _manifest(_preregistration(), _requests(_preregistration()))
    )
    cast(dict[str, object], dispatch)["call_ceiling"] = 4.0
    with pytest.raises(subject.D02R2GenerationExecutionError):
        _validate_dispatch(
            dispatch,
            _preregistration(),
            _manifest(_preregistration(), _requests(_preregistration())),
        )
