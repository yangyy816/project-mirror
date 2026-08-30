"""Pure, versioned E3 generation contract for the D02-R2 demo.

This module contains no provider, filesystem, prompt, or database access.
It pre-registers the four serial calls and validates only public, opaque
identifiers and typed digests.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, NoReturn, cast

from mirror_api.demo_measurement_quality import mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

PROMPT_POLICY_VERSION: Final = "project-mirror-synthetic-face-generation-v2"
PRIMARY_CALLS: Final = 4
OUTPUTS_PER_CALL: Final = 1
CONCURRENCY: Final = 1
RETRY_CEILING: Final = 0
RESERVE_CALLS: Final = 0
ADULT_STATUS: Final = "VERIFIED_SYNTHETIC_ADULT"
AGE_BAND_18_19: Final = "ADULT_18_19"
AGE_BAND_20_25: Final = "ADULT_20_25"
VISUAL_CONTEXT: Final = "EAST_ASIAN_PRESENTING_SYNTHETIC"
GENERATION_PROVIDER: Final = "CODEX_NATIVE_IMAGEGEN"


@dataclass(frozen=True, slots=True)
class GenerationExecutionContext:
    """Frozen lineage and schema family for one forward-only source cohort."""

    cohort_label: str
    contract_schema: str
    allocation_schema: str
    source_policy_profile_schema: str
    source_generation_receipt_schema: str
    terminal_source_receipt_schema: str
    source_authority_schema: str
    source_qa_schema: str
    source_record_schema: str
    source_record_id_domain: str
    admission_schema: str
    admission_id_domain: str
    source_normalization_schema: str
    source_normalization_version: str
    source_policy_metadata_schema: str
    runtime_recipe_version: str
    task_id: str
    producer_task_id: str
    private_namespace_id: str
    root_id: str
    dispatch_epoch: int
    execution_epoch: str
    generation_version: str


E3_CONTEXT: Final = GenerationExecutionContext(
    cohort_label="E3",
    contract_schema="mirror.demo/D02R2Epoch3GenerationContract/v1",
    allocation_schema="mirror.demo/D02R2Epoch3GenerationAllocation/v1",
    source_policy_profile_schema="mirror.demo/D02R2Epoch3SourcePolicyProfile/v1",
    source_generation_receipt_schema="mirror.demo/D02R2Epoch3GenerationReceipt/v1",
    terminal_source_receipt_schema="mirror.demo/D02R2Epoch3TerminalSourceReceipt/v1",
    source_authority_schema="mirror.demo/D02R2Epoch3SourceAuthority/v1",
    source_qa_schema="mirror.demo/D02R2Epoch3SourceQASnapshot/v1",
    source_record_schema="mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1",
    source_record_id_domain="mirror.demo/D02R2Epoch3SourceAuthorityRecordId/v1",
    admission_schema="mirror.demo/D02R2Epoch3Admission/v1",
    admission_id_domain="mirror.demo/D02R2Epoch3AdmissionId/v1",
    source_normalization_schema="mirror.demo/D02R2Epoch3SourceNormalizationReceipt/v1",
    source_normalization_version="demo-d02-r2-e3-png-to-jpeg-v1",
    source_policy_metadata_schema="mirror.demo/D02R2Epoch3GenerationPolicyMetadata/v1",
    runtime_recipe_version="demo-m3-m4-runtime-recipe-e3-v1",
    task_id="P3_P7_D02_R2_EXECUTION_03",
    producer_task_id="P3_P7_D02_R2_SOURCE_COHORT_03",
    private_namespace_id="pm-p3p7-d02-r2-e3",
    root_id="P3_P7_D02_R2_E3_EVIDENCE_ROOT",
    dispatch_epoch=3,
    execution_epoch="D02_R2_EPOCH_03",
    generation_version="d02-r2-e3-imagegen-v1",
)
E4_CONTEXT: Final = GenerationExecutionContext(
    cohort_label="E4",
    contract_schema="mirror.demo/D02R2Epoch4GenerationContract/v1",
    allocation_schema="mirror.demo/D02R2Epoch4GenerationAllocation/v1",
    source_policy_profile_schema="mirror.demo/D02R2Epoch4SourcePolicyProfile/v1",
    source_generation_receipt_schema="mirror.demo/D02R2Epoch4GenerationReceipt/v1",
    terminal_source_receipt_schema="mirror.demo/D02R2Epoch4TerminalSourceReceipt/v1",
    source_authority_schema="mirror.demo/D02R2Epoch4SourceAuthority/v1",
    source_qa_schema="mirror.demo/D02R2Epoch4SourceQASnapshot/v1",
    source_record_schema="mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1",
    source_record_id_domain="mirror.demo/D02R2Epoch4SourceAuthorityRecordId/v1",
    admission_schema="mirror.demo/D02R2Epoch4Admission/v1",
    admission_id_domain="mirror.demo/D02R2Epoch4AdmissionId/v1",
    source_normalization_schema="mirror.demo/D02R2Epoch4SourceNormalizationReceipt/v1",
    source_normalization_version="demo-d02-r2-e4-png-to-jpeg-v1",
    source_policy_metadata_schema="mirror.demo/D02R2Epoch4GenerationPolicyMetadata/v1",
    runtime_recipe_version="demo-m3-m4-runtime-recipe-e4-v1",
    task_id="P3_P7_D02_R2_EXECUTION_04",
    producer_task_id="P3_P7_D02_R2_SOURCE_COHORT_04",
    private_namespace_id="pm-p3p7-d02-r2-e4",
    root_id="P3_P7_D02_R2_E4_EVIDENCE_ROOT",
    dispatch_epoch=4,
    execution_epoch="D02_R2_EPOCH_04",
    generation_version="d02-r2-e4-imagegen-v1",
)

E3_CONTRACT_SCHEMA: Final = E3_CONTEXT.contract_schema
E3_ALLOCATION_SCHEMA: Final = E3_CONTEXT.allocation_schema
SOURCE_POLICY_PROFILE_SCHEMA: Final = E3_CONTEXT.source_policy_profile_schema
TASK_ID: Final = E3_CONTEXT.task_id
PRODUCER_TASK_ID: Final = E3_CONTEXT.producer_task_id
PRIVATE_NAMESPACE_ID: Final = E3_CONTEXT.private_namespace_id
ROOT_ID: Final = E3_CONTEXT.root_id
DISPATCH_EPOCH: Final = E3_CONTEXT.dispatch_epoch
EXECUTION_EPOCH: Final = E3_CONTEXT.execution_epoch
GENERATION_VERSION: Final = E3_CONTEXT.generation_version

_GEOMETRY_DIMENSIONS: Final = ["jaw_width", "chin_height", "eye_spacing"]
_CONTROLLED_VARIABLES: Final = [
    "camera",
    "pose",
    "gaze",
    "expression",
    "lighting",
    "background",
    "framing",
    "makeup",
    "clothing",
]
_PRESERVED_VARIABLES: Final = [
    "natural_anatomy",
    "unobstructed_features",
    "neutral_expression",
    "front_facing_capture",
    "soft_stable_lighting",
    "clean_neutral_background",
]
_SOURCE_PROFILE_BY_ORDINAL: Final = {
    1: (AGE_BAND_20_25, "CLEAR_NATURAL"),
    2: (AGE_BAND_20_25, "REFINED_COOL"),
    3: (AGE_BAND_20_25, "GENTLE_SWEET"),
    4: (AGE_BAND_18_19, "FRESH_NATURAL"),
}

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_FORBIDDEN_FIELD_PART = re.compile(r"(?:path|locator|secret|token|password)", re.I)
_ALLOCATION_KEYS: Final = (
    "schema_version",
    "ordinal",
    "source_output_id",
    "provenance_output_id",
    "normalized_jpeg_output_id",
    "source_policy_profile",
    "allocation_digest",
)
_SOURCE_POLICY_PROFILE_KEYS: Final = (
    "schema_version",
    "source_ordinal",
    "declared_age_band",
    "required_adult_status",
    "visual_context",
    "style_family",
    "geometry_dimensions",
    "controlled_variables",
    "preserved_variables",
    "generation_provider",
    "generation_version",
    "prompt_policy_version",
    "base_identity_family",
    "pair_id",
    "pair_side",
    "sexualized_context_allowed",
    "profile_digest",
)
_CONTRACT_KEYS: Final = (
    "schema_version",
    "task_id",
    "producer_task_id",
    "private_namespace_id",
    "root_id",
    "dispatch_epoch",
    "execution_epoch",
    "prompt_policy_version",
    "prompt_materials_tracked",
    "primary_calls",
    "ordinal_start",
    "ordinal_end",
    "outputs_per_call",
    "concurrency",
    "retry_ceiling",
    "reserve_calls",
    "source_media_type",
    "normalized_media_type",
    "allocations",
    "contract_digest",
)


class Epoch3GenerationError(ValueError):
    """Raised when E3 public generation authority fails closed."""


def _fail(message: str) -> NoReturn:
    raise Epoch3GenerationError(message)


def _exact(value: object, keys: tuple[str, ...], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value) != keys:
        _fail(f"{label} keys or key order are not exact")
    return cast(Mapping[str, object], value)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT_ID.fullmatch(value) is None:
        _fail(f"{label} must be an opaque output ID")
    return value


def _guard_private_fields(value: object, label: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(f"{label} has a non-string key")
            if _FORBIDDEN_FIELD_PART.search(key) is not None:
                _fail(f"{label} contains a forbidden private field")
            _guard_private_fields(item, key)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _guard_private_fields(item, label)


def _typed_digest(schema: str, payload: Mapping[str, object], label: str) -> str:
    try:
        return mirror_demo_digest(schema, cast(Mapping[str, JsonValue], payload))
    except (TypeError, ValueError) as error:
        raise Epoch3GenerationError(f"{label} is not canonical JSON") from error


def build_epoch3_source_policy_profile(
    *, ordinal: int, context: GenerationExecutionContext = E3_CONTEXT
) -> JsonObject:
    """Return the public, prompt-free policy projection for one source."""

    profile_values = _SOURCE_PROFILE_BY_ORDINAL.get(ordinal)
    if profile_values is None:
        _fail(f"source policy profile ordinal is outside the {context.cohort_label} envelope")
    age_band, style_family = profile_values
    profile: JsonObject = {
        "schema_version": context.source_policy_profile_schema,
        "source_ordinal": ordinal,
        "declared_age_band": age_band,
        "required_adult_status": ADULT_STATUS,
        "visual_context": VISUAL_CONTEXT,
        "style_family": style_family,
        "geometry_dimensions": list(_GEOMETRY_DIMENSIONS),
        "controlled_variables": list(_CONTROLLED_VARIABLES),
        "preserved_variables": list(_PRESERVED_VARIABLES),
        "generation_provider": GENERATION_PROVIDER,
        "generation_version": context.generation_version,
        "prompt_policy_version": PROMPT_POLICY_VERSION,
        "base_identity_family": f"{context.cohort_label}_IDENTITY_FAMILY_{ordinal:02d}",
        "pair_id": None,
        "pair_side": "SOURCE_BASELINE",
        "sexualized_context_allowed": False,
        "profile_digest": "",
    }
    profile["profile_digest"] = _typed_digest(
        context.source_policy_profile_schema,
        {key: value for key, value in profile.items() if key != "profile_digest"},
        f"{context.cohort_label} source policy profile",
    )
    return profile


def validate_epoch3_source_policy_profile(
    value: object,
    *,
    ordinal: int,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    profile = _exact(
        value,
        _SOURCE_POLICY_PROFILE_KEYS,
        f"{context.cohort_label} source policy profile",
    )
    expected = build_epoch3_source_policy_profile(ordinal=ordinal, context=context)
    if (
        dict(profile) != expected
        or _digest(profile["profile_digest"], "source policy profile digest")
        != expected["profile_digest"]
    ):
        _fail(f"{context.cohort_label} source policy profile does not replay")
    return profile


def build_epoch3_allocation(
    *,
    ordinal: int,
    source_output_id: str,
    provenance_output_id: str,
    normalized_jpeg_output_id: str,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    if type(ordinal) is not int or ordinal not in range(1, PRIMARY_CALLS + 1):
        _fail(f"allocation ordinal is outside the {context.cohort_label} envelope")
    payload: JsonObject = {
        "schema_version": context.allocation_schema,
        "ordinal": ordinal,
        "source_output_id": _output_id(source_output_id, "source output ID"),
        "provenance_output_id": _output_id(provenance_output_id, "provenance output ID"),
        "normalized_jpeg_output_id": _output_id(
            normalized_jpeg_output_id, "normalized JPEG output ID"
        ),
        "source_policy_profile": build_epoch3_source_policy_profile(
            ordinal=ordinal, context=context
        ),
        "allocation_digest": "",
    }
    payload["allocation_digest"] = _typed_digest(
        context.allocation_schema,
        {key: value for key, value in payload.items() if key != "allocation_digest"},
        f"{context.cohort_label} allocation",
    )
    return payload


def validate_epoch3_allocation(
    value: object,
    *,
    ordinal: int,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    allocation = _exact(value, _ALLOCATION_KEYS, f"{context.cohort_label} allocation")
    if (
        allocation["schema_version"] != context.allocation_schema
        or allocation["ordinal"] != ordinal
    ):
        _fail(f"{context.cohort_label} allocation schema or ordinal is invalid")
    rebuilt = build_epoch3_allocation(
        ordinal=ordinal,
        source_output_id=_output_id(allocation["source_output_id"], "source output ID"),
        provenance_output_id=_output_id(allocation["provenance_output_id"], "provenance output ID"),
        normalized_jpeg_output_id=_output_id(
            allocation["normalized_jpeg_output_id"], "normalized JPEG output ID"
        ),
        context=context,
    )
    validate_epoch3_source_policy_profile(
        allocation["source_policy_profile"], ordinal=ordinal, context=context
    )
    if (
        dict(allocation) != rebuilt
        or _digest(allocation["allocation_digest"], "allocation digest")
        != rebuilt["allocation_digest"]
    ):
        _fail(f"{context.cohort_label} allocation does not replay")
    return allocation


def build_epoch3_generation_contract(
    *,
    allocations: Sequence[Mapping[str, object]],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    if len(allocations) != PRIMARY_CALLS:
        _fail(f"{context.cohort_label} requires exactly four allocations")
    rebuilt_allocations: list[JsonValue] = []
    all_ids: list[str] = []
    for ordinal, allocation in enumerate(allocations, start=1):
        validated = validate_epoch3_allocation(allocation, ordinal=ordinal, context=context)
        rebuilt_allocations.append(cast(JsonValue, dict(validated)))
        all_ids.extend(
            cast(str, validated[key])
            for key in ("source_output_id", "provenance_output_id", "normalized_jpeg_output_id")
        )
    if len(set(all_ids)) != len(all_ids):
        _fail(f"{context.cohort_label} allocations must preallocate globally unique output IDs")
    contract: JsonObject = {
        "schema_version": context.contract_schema,
        "task_id": context.task_id,
        "producer_task_id": context.producer_task_id,
        "private_namespace_id": context.private_namespace_id,
        "root_id": context.root_id,
        "dispatch_epoch": context.dispatch_epoch,
        "execution_epoch": context.execution_epoch,
        "prompt_policy_version": PROMPT_POLICY_VERSION,
        "prompt_materials_tracked": False,
        "primary_calls": PRIMARY_CALLS,
        "ordinal_start": 1,
        "ordinal_end": PRIMARY_CALLS,
        "outputs_per_call": OUTPUTS_PER_CALL,
        "concurrency": CONCURRENCY,
        "retry_ceiling": RETRY_CEILING,
        "reserve_calls": RESERVE_CALLS,
        "source_media_type": "image/png",
        "normalized_media_type": "image/jpeg",
        "allocations": rebuilt_allocations,
        "contract_digest": "",
    }
    contract["contract_digest"] = _typed_digest(
        context.contract_schema,
        {key: value for key, value in contract.items() if key != "contract_digest"},
        f"{context.cohort_label} contract",
    )
    return contract


def validate_epoch3_generation_contract(
    value: object, *, context: GenerationExecutionContext = E3_CONTEXT
) -> Mapping[str, object]:
    _guard_private_fields(value)
    contract = _exact(value, _CONTRACT_KEYS, f"{context.cohort_label} contract")
    if contract["schema_version"] != context.contract_schema:
        if context == E3_CONTEXT:
            _fail("E2 or unknown generation contract schema is rejected")
        _fail(f"foreign generation contract schema is rejected by {context.cohort_label}")
    expected_scalars = {
        "task_id": context.task_id,
        "producer_task_id": context.producer_task_id,
        "private_namespace_id": context.private_namespace_id,
        "root_id": context.root_id,
        "dispatch_epoch": context.dispatch_epoch,
        "execution_epoch": context.execution_epoch,
        "prompt_policy_version": PROMPT_POLICY_VERSION,
        "prompt_materials_tracked": False,
        "primary_calls": PRIMARY_CALLS,
        "ordinal_start": 1,
        "ordinal_end": PRIMARY_CALLS,
        "outputs_per_call": OUTPUTS_PER_CALL,
        "concurrency": CONCURRENCY,
        "retry_ceiling": RETRY_CEILING,
        "reserve_calls": RESERVE_CALLS,
        "source_media_type": "image/png",
        "normalized_media_type": "image/jpeg",
    }
    if any(contract[key] != expected for key, expected in expected_scalars.items()):
        _fail(f"{context.cohort_label} contract frozen scalar differs")
    raw_allocations = contract["allocations"]
    if not isinstance(raw_allocations, list):
        _fail(f"{context.cohort_label} allocations must be a list")
    rebuilt = build_epoch3_generation_contract(
        allocations=[cast(Mapping[str, object], item) for item in raw_allocations],
        context=context,
    )
    if (
        dict(contract) != rebuilt
        or _digest(contract["contract_digest"], "contract digest") != rebuilt["contract_digest"]
    ):
        _fail(f"{context.cohort_label} contract does not replay")
    return contract
