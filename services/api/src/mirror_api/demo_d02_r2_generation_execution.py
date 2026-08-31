"""Pure, deterministic D02-R2 source-generation execution authority.

The builders freeze public scalar projections only.  They neither resolve a
private evidence root nor perform registry, provider, network, Prompt, or
image-generation I/O.  Callers must bind the dynamic execution/root/parent
authority digests at each validation boundary.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_r2_generation_capability as capability
from mirror_api.demo_measurement_quality import mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

GENERATION_PREREGISTRATION_SCHEMA: Final = (
    "mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1"
)
SOURCE_ALLOCATION_MANIFEST_SCHEMA: Final = "mirror.demo/D02R2SourceAllocationManifest/v1"
SOURCE_PRODUCER_DISPATCH_SCHEMA: Final = "mirror.demo/D02R2SourceProducerDispatchReceipt/v1"

PREREGISTRATION_KEYS: Final[tuple[str, ...]] = (
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
ALLOCATION_MANIFEST_KEYS: Final[tuple[str, ...]] = (
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
ALLOCATION_ENTRY_KEYS: Final[tuple[str, ...]] = (
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
PRODUCER_DISPATCH_KEYS: Final[tuple[str, ...]] = (
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

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ORDINALS: Final = (1, 2, 3, 4)
_WRITABLE_CLASSES: Final = ("DATA_SOURCE_CANDIDATES", "DATA_SOURCE_PROVENANCE")


class D02R2GenerationExecutionError(ValueError):
    """A D02-R2 generation execution authority did not replay exactly."""


def _fail(message: str) -> NoReturn:
    raise D02R2GenerationExecutionError(message)


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT_ID_RE.fullmatch(value) is None:
        _fail(f"{label} is not an allowed opaque output ID")
    return value


def _require_exact_mapping(
    value: object, expected_keys: tuple[str, ...], label: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value) != expected_keys:
        _fail(f"{label} keys or key order are not exact")
    return cast(Mapping[str, object], value)


def _require_int(value: object, expected: int, label: str) -> int:
    if type(value) is not int or value != expected:
        _fail(f"{label} must be exactly {expected}")
    return value


def _strict_json_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and tuple(actual) == tuple(expected)
            and all(_strict_json_equal(actual[key], item) for key, item in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _strict_json_equal(item, expected_item)
                for item, expected_item in zip(actual, expected, strict=True)
            )
        )
    return actual == expected


def _typed_digest(schema: str, payload: Mapping[str, object], label: str) -> str:
    try:
        return mirror_demo_digest(schema, cast(Mapping[str, JsonValue], payload))
    except (TypeError, ValueError) as error:
        raise D02R2GenerationExecutionError(f"{label} is not canonical JSON") from error


def _accepted_capability() -> Mapping[str, object]:
    return capability.validate_generation_capability_authority(
        capability.build_generation_capability_authority()
    )


def _capability_digest() -> str:
    return _require_digest(
        _accepted_capability()["generation_capability_authority_digest"],
        "accepted generation capability authority digest",
    )


def _expected_capability_value(key: str) -> object:
    return _accepted_capability()[key]


def _validate_execution_root_parent(
    value: Mapping[str, object],
    *,
    expected_execution_contract_digest: str,
    expected_root_name_receipt_digest: str,
    expected_parent_authority_digest: str,
    parent_key: str,
    label: str,
) -> None:
    expected_execution_contract_digest = _require_digest(
        expected_execution_contract_digest, "expected execution contract digest"
    )
    expected_root_name_receipt_digest = _require_digest(
        expected_root_name_receipt_digest, "expected root name receipt digest"
    )
    expected_parent_authority_digest = _require_digest(
        expected_parent_authority_digest, "expected parent authority digest"
    )
    if _require_digest(value["execution_contract_digest"], "execution contract digest") != (
        expected_execution_contract_digest
    ):
        _fail(f"{label} execution contract differs from expected authority")
    if value["evidence_root_id"] != capability.EVIDENCE_ROOT_ID:
        _fail(f"{label} evidence root differs from accepted capability")
    if _require_digest(value["root_name_receipt_digest"], "root name receipt digest") != (
        expected_root_name_receipt_digest
    ):
        _fail(f"{label} root name receipt differs from expected authority")
    if _require_digest(value[parent_key], parent_key) != expected_parent_authority_digest:
        _fail(f"{label} parent authority differs from expected authority")


def _validate_frozen_producer(value: Mapping[str, object], label: str) -> None:
    if value["producer_task_id"] != capability.PRODUCER_TASK_ID:
        _fail(f"{label} producer task differs from accepted capability")
    _require_int(value["dispatch_epoch"], capability.DISPATCH_EPOCH, f"{label} dispatch epoch")


def _replay_digest(value: Mapping[str, object], digest_key: str, schema: str, label: str) -> None:
    submitted = _require_digest(value[digest_key], digest_key)
    replayed = _typed_digest(
        schema, {key: item for key, item in value.items() if key != digest_key}, label
    )
    if submitted != replayed:
        _fail(f"{label} digest does not replay")


def build_source_generation_preregistration_authority(
    *,
    execution_contract_digest: str,
    root_name_receipt_digest: str,
    cohort_policy_digest: str,
) -> JsonObject:
    """Freeze the four-call source-generation preregistration before allocation."""

    preregistration: JsonObject = {
        "schema_version": GENERATION_PREREGISTRATION_SCHEMA,
        "execution_contract_digest": _require_digest(
            execution_contract_digest, "execution contract digest"
        ),
        "evidence_root_id": capability.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": _require_digest(
            root_name_receipt_digest, "root name receipt digest"
        ),
        "generation_capability_authority_digest": _capability_digest(),
        "cohort_policy_digest": _require_digest(cohort_policy_digest, "cohort policy digest"),
        "producer_task_id": capability.PRODUCER_TASK_ID,
        "dispatch_epoch": capability.DISPATCH_EPOCH,
        "source_count": 4,
        "ordered_candidate_ordinals": list(_ORDINALS),
        "generation_preregistration_digest": "",
    }
    preregistration["generation_preregistration_digest"] = _typed_digest(
        GENERATION_PREREGISTRATION_SCHEMA,
        {
            key: item
            for key, item in preregistration.items()
            if key != "generation_preregistration_digest"
        },
        "generation preregistration",
    )
    if tuple(preregistration) != PREREGISTRATION_KEYS:
        _fail("generation preregistration construction order drifted")
    return preregistration


def validate_source_generation_preregistration_authority(
    value: object,
    *,
    expected_execution_contract_digest: str,
    expected_root_name_receipt_digest: str,
    expected_parent_authority_digest: str,
    expected_cohort_policy_digest: str,
) -> Mapping[str, object]:
    """Replay preregistration against caller-supplied execution/root/capability authority."""

    preregistration = _require_exact_mapping(
        value, PREREGISTRATION_KEYS, "generation preregistration"
    )
    if preregistration["schema_version"] != GENERATION_PREREGISTRATION_SCHEMA:
        _fail("generation preregistration schema is invalid")
    _validate_execution_root_parent(
        preregistration,
        expected_execution_contract_digest=expected_execution_contract_digest,
        expected_root_name_receipt_digest=expected_root_name_receipt_digest,
        expected_parent_authority_digest=expected_parent_authority_digest,
        parent_key="generation_capability_authority_digest",
        label="generation preregistration",
    )
    if expected_parent_authority_digest != _capability_digest():
        _fail("expected preregistration parent is not the accepted capability authority")
    if _require_digest(preregistration["cohort_policy_digest"], "cohort policy digest") != (
        _require_digest(expected_cohort_policy_digest, "expected cohort policy digest")
    ):
        _fail("generation preregistration cohort policy differs from expected authority")
    _validate_frozen_producer(preregistration, "generation preregistration")
    _require_int(preregistration["source_count"], 4, "generation preregistration source count")
    ordinals = preregistration["ordered_candidate_ordinals"]
    if not isinstance(ordinals, list) or any(type(item) is not int for item in ordinals):
        _fail("generation preregistration ordinals are not integer list")
    if tuple(ordinals) != _ORDINALS:
        _fail("generation preregistration ordinals are not exactly 1..4")
    _replay_digest(
        preregistration,
        "generation_preregistration_digest",
        GENERATION_PREREGISTRATION_SCHEMA,
        "generation preregistration",
    )
    return preregistration


def _validated_request_policies(
    policies: Sequence[Mapping[str, object]],
    *,
    expected_root_name_receipt_digest: str,
    expected_preregistration_digest: str,
) -> dict[int, Mapping[str, object]]:
    if isinstance(policies, (str, bytes, bytearray)) or len(policies) != 4:
        _fail("generation request policies must contain exactly four entries")
    result: dict[int, Mapping[str, object]] = {}
    capability_digest = _capability_digest()
    for policy in policies:
        validated = capability.validate_generation_request_policy(policy)
        ordinal = validated["candidate_ordinal"]
        if type(ordinal) is not int or ordinal not in _ORDINALS or ordinal in result:
            _fail("generation request policy ordinals are not exactly unique 1..4")
        if validated["generation_capability_authority_digest"] != capability_digest:
            _fail("generation request policy capability differs from accepted authority")
        if validated["evidence_root_id"] != capability.EVIDENCE_ROOT_ID:
            _fail("generation request policy evidence root differs from accepted capability")
        if validated["root_name_receipt_digest"] != expected_root_name_receipt_digest:
            _fail("generation request policy root differs from expected authority")
        if validated["generation_preregistration_digest"] != expected_preregistration_digest:
            _fail("generation request policy preregistration differs from expected authority")
        result[ordinal] = validated
    if tuple(sorted(result)) != _ORDINALS:
        _fail("generation request policy ordinals are not exactly 1..4")
    return result


def _entry_from_request(policy: Mapping[str, object]) -> JsonObject:
    return cast(
        JsonObject,
        {
            "candidate_ordinal": policy["candidate_ordinal"],
            "source_output_id": policy["source_output_id"],
            "output_name_receipt_digest": policy["output_name_receipt_digest"],
            "source_provenance_output_id": policy["source_provenance_output_id"],
            "source_provenance_name_receipt_digest": policy[
                "source_provenance_name_receipt_digest"
            ],
            "generation_request_policy_digest": policy["generation_request_policy_digest"],
            "producer_task_id": policy["producer_task_id"],
            "dispatch_epoch": policy["dispatch_epoch"],
            "source_maximum_bytes": policy["source_maximum_bytes"],
            "source_expected_media_type": policy["source_expected_media_type"],
            "provenance_maximum_bytes": policy["provenance_maximum_bytes"],
            "provenance_expected_media_type": policy["provenance_expected_media_type"],
        },
    )


def build_source_allocation_manifest(
    *,
    execution_contract_digest: str,
    root_name_receipt_digest: str,
    generation_preregistration_digest: str,
    generation_request_policies: Sequence[Mapping[str, object]],
) -> JsonObject:
    """Freeze exactly four Principal-preallocated request policy projections."""

    execution_contract_digest = _require_digest(
        execution_contract_digest, "execution contract digest"
    )
    root_name_receipt_digest = _require_digest(root_name_receipt_digest, "root name receipt digest")
    generation_preregistration_digest = _require_digest(
        generation_preregistration_digest, "generation preregistration digest"
    )
    requests = _validated_request_policies(
        generation_request_policies,
        expected_root_name_receipt_digest=root_name_receipt_digest,
        expected_preregistration_digest=generation_preregistration_digest,
    )
    allocations = [_entry_from_request(requests[ordinal]) for ordinal in _ORDINALS]
    manifest: JsonObject = {
        "schema_version": SOURCE_ALLOCATION_MANIFEST_SCHEMA,
        "execution_contract_digest": execution_contract_digest,
        "evidence_root_id": capability.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_name_receipt_digest,
        "generation_preregistration_digest": generation_preregistration_digest,
        "producer_task_id": capability.PRODUCER_TASK_ID,
        "dispatch_epoch": capability.DISPATCH_EPOCH,
        "source_count": 4,
        "ordered_allocations": cast(list[JsonValue], allocations),
        "source_allocation_manifest_digest": "",
    }
    manifest["source_allocation_manifest_digest"] = _typed_digest(
        SOURCE_ALLOCATION_MANIFEST_SCHEMA,
        {key: item for key, item in manifest.items() if key != "source_allocation_manifest_digest"},
        "source allocation manifest",
    )
    if tuple(manifest) != ALLOCATION_MANIFEST_KEYS:
        _fail("source allocation manifest construction order drifted")
    return manifest


def _validate_allocation_entry(
    entry: object,
    *,
    ordinal: int,
    request: Mapping[str, object],
) -> Mapping[str, object]:
    allocation = _require_exact_mapping(entry, ALLOCATION_ENTRY_KEYS, "source allocation entry")
    _require_int(allocation["candidate_ordinal"], ordinal, "source allocation ordinal")
    for key in (
        "source_output_id",
        "source_provenance_output_id",
    ):
        _require_output_id(allocation[key], key)
    for key in (
        "output_name_receipt_digest",
        "source_provenance_name_receipt_digest",
        "generation_request_policy_digest",
    ):
        _require_digest(allocation[key], key)
    expected = _entry_from_request(request)
    if not _strict_json_equal(dict(allocation), expected):
        _fail("source allocation entry differs from its accepted request policy")
    return allocation


def _validate_allocation_uniqueness(entries: Sequence[Mapping[str, object]]) -> None:
    projections = {
        "source output IDs": [entry["source_output_id"] for entry in entries],
        "provenance output IDs": [entry["source_provenance_output_id"] for entry in entries],
        "output name receipt digests": [entry["output_name_receipt_digest"] for entry in entries],
        "provenance name receipt digests": [
            entry["source_provenance_name_receipt_digest"] for entry in entries
        ],
        "generation request policy digests": [
            entry["generation_request_policy_digest"] for entry in entries
        ],
    }
    for label, values in projections.items():
        if len(set(values)) != 4:
            _fail(f"{label} are not unique across the four allocations")
    all_output_ids = projections["source output IDs"] + projections["provenance output IDs"]
    all_name_receipts = (
        projections["output name receipt digests"] + projections["provenance name receipt digests"]
    )
    if len(set(all_output_ids)) != 8:
        _fail("source and provenance output IDs must be globally unique")
    if len(set(all_name_receipts)) != 8:
        _fail("source and provenance name receipts must be globally unique")


def validate_source_allocation_manifest(
    value: object,
    *,
    expected_execution_contract_digest: str,
    expected_root_name_receipt_digest: str,
    expected_parent_authority_digest: str,
    generation_request_policies: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    """Replay all four allocation entries against exact accepted request policies."""

    manifest = _require_exact_mapping(value, ALLOCATION_MANIFEST_KEYS, "source allocation manifest")
    if manifest["schema_version"] != SOURCE_ALLOCATION_MANIFEST_SCHEMA:
        _fail("source allocation manifest schema is invalid")
    _validate_execution_root_parent(
        manifest,
        expected_execution_contract_digest=expected_execution_contract_digest,
        expected_root_name_receipt_digest=expected_root_name_receipt_digest,
        expected_parent_authority_digest=expected_parent_authority_digest,
        parent_key="generation_preregistration_digest",
        label="source allocation manifest",
    )
    _validate_frozen_producer(manifest, "source allocation manifest")
    _require_int(manifest["source_count"], 4, "source allocation manifest source count")
    requests = _validated_request_policies(
        generation_request_policies,
        expected_root_name_receipt_digest=expected_root_name_receipt_digest,
        expected_preregistration_digest=expected_parent_authority_digest,
    )
    allocations = manifest["ordered_allocations"]
    if not isinstance(allocations, list) or len(allocations) != 4:
        _fail("source allocation manifest must contain exactly four ordered allocations")
    validated_allocations = [
        _validate_allocation_entry(entry, ordinal=ordinal, request=requests[ordinal])
        for ordinal, entry in zip(_ORDINALS, allocations, strict=True)
    ]
    _validate_allocation_uniqueness(validated_allocations)
    _replay_digest(
        manifest,
        "source_allocation_manifest_digest",
        SOURCE_ALLOCATION_MANIFEST_SCHEMA,
        "source allocation manifest",
    )
    return manifest


def build_source_producer_dispatch_receipt(
    *,
    execution_contract_digest: str,
    root_name_receipt_digest: str,
    generation_preregistration_digest: str,
    source_allocation_manifest_digest: str,
) -> JsonObject:
    """Freeze the exact four-call producer dispatch after allocation is sealed."""

    accepted = _accepted_capability()
    dispatch: JsonObject = {
        "schema_version": SOURCE_PRODUCER_DISPATCH_SCHEMA,
        "execution_contract_digest": _require_digest(
            execution_contract_digest, "execution contract digest"
        ),
        "evidence_root_id": capability.EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": _require_digest(
            root_name_receipt_digest, "root name receipt digest"
        ),
        "generation_capability_authority_digest": _capability_digest(),
        "generation_preregistration_digest": _require_digest(
            generation_preregistration_digest, "generation preregistration digest"
        ),
        "source_allocation_manifest_digest": _require_digest(
            source_allocation_manifest_digest, "source allocation manifest digest"
        ),
        "producer_task_id": capability.PRODUCER_TASK_ID,
        "dispatch_epoch": capability.DISPATCH_EPOCH,
        "call_ceiling": 4,
        "retry_ceiling": 0,
        "concurrency": 1,
        "approved_endpoint_policy_digest": cast(
            JsonValue, accepted["approved_endpoint_policy_digest"]
        ),
        "credential_process_boundary_digest": cast(
            JsonValue, accepted["credential_process_boundary_digest"]
        ),
        "provider_retention_policy_digest": cast(
            JsonValue, accepted["provider_retention_policy_digest"]
        ),
        "producer_writable_classes": list(_WRITABLE_CLASSES),
        "dispatch_state": "AUTHORIZED_EXACT_ALLOCATIONS_ONLY",
        "source_producer_dispatch_digest": "",
    }
    dispatch["source_producer_dispatch_digest"] = _typed_digest(
        SOURCE_PRODUCER_DISPATCH_SCHEMA,
        {key: item for key, item in dispatch.items() if key != "source_producer_dispatch_digest"},
        "source producer dispatch",
    )
    if tuple(dispatch) != PRODUCER_DISPATCH_KEYS:
        _fail("source producer dispatch construction order drifted")
    return dispatch


def validate_source_producer_dispatch_receipt(
    value: object,
    *,
    expected_execution_contract_digest: str,
    expected_root_name_receipt_digest: str,
    expected_parent_authority_digest: str,
    expected_generation_preregistration_digest: str,
) -> Mapping[str, object]:
    """Replay dispatch against exact allocation parent and preregistration sibling."""

    dispatch = _require_exact_mapping(value, PRODUCER_DISPATCH_KEYS, "source producer dispatch")
    if dispatch["schema_version"] != SOURCE_PRODUCER_DISPATCH_SCHEMA:
        _fail("source producer dispatch schema is invalid")
    _validate_execution_root_parent(
        dispatch,
        expected_execution_contract_digest=expected_execution_contract_digest,
        expected_root_name_receipt_digest=expected_root_name_receipt_digest,
        expected_parent_authority_digest=expected_parent_authority_digest,
        parent_key="source_allocation_manifest_digest",
        label="source producer dispatch",
    )
    if _require_digest(
        dispatch["generation_preregistration_digest"], "generation preregistration digest"
    ) != _require_digest(
        expected_generation_preregistration_digest, "expected generation preregistration digest"
    ):
        _fail("source producer dispatch preregistration differs from expected authority")
    if (
        _require_digest(
            dispatch["generation_capability_authority_digest"],
            "generation capability authority digest",
        )
        != _capability_digest()
    ):
        _fail("source producer dispatch capability differs from accepted authority")
    _validate_frozen_producer(dispatch, "source producer dispatch")
    _require_int(dispatch["call_ceiling"], 4, "source producer dispatch call ceiling")
    _require_int(dispatch["retry_ceiling"], 0, "source producer dispatch retry ceiling")
    _require_int(dispatch["concurrency"], 1, "source producer dispatch concurrency")
    accepted = _accepted_capability()
    for key in (
        "approved_endpoint_policy_digest",
        "credential_process_boundary_digest",
        "provider_retention_policy_digest",
    ):
        if _require_digest(dispatch[key], key) != _require_digest(accepted[key], f"accepted {key}"):
            _fail(f"source producer dispatch {key} differs from accepted capability")
    classes = dispatch["producer_writable_classes"]
    if not isinstance(classes, list) or tuple(classes) != _WRITABLE_CLASSES:
        _fail("source producer dispatch writable classes are not exact")
    if dispatch["dispatch_state"] != "AUTHORIZED_EXACT_ALLOCATIONS_ONLY":
        _fail("source producer dispatch state is invalid")
    _replay_digest(
        dispatch,
        "source_producer_dispatch_digest",
        SOURCE_PRODUCER_DISPATCH_SCHEMA,
        "source producer dispatch",
    )
    return dispatch


# Concise aliases retain the names used by the CC08 prose while preserving the
# complete schema names above for callers that need explicit authority types.
build_generation_preregistration = build_source_generation_preregistration_authority
validate_generation_preregistration = validate_source_generation_preregistration_authority
