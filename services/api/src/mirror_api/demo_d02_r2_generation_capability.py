"""Deterministic, fail-closed D02-R2 generation capability authority.

This module only builds and replays tracked/private authority payloads. It
does not invoke ImageGen, handle Prompt bytes, resolve private paths, or write
outputs. The pre-root capability intentionally binds only the public root ID;
per-candidate request policies bind the durable root receipt later.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Final, NoReturn, cast

from mirror_api.demo_measurement_quality import mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type PolicyBuilder = Callable[[], JsonObject]

GENERATION_CAPABILITY_AUTHORITY_SCHEMA: Final = "mirror.demo/D02R2GenerationCapabilityAuthority/v1"
GENERATION_REQUEST_POLICY_SCHEMA: Final = "mirror.demo/D02R2GenerationRequestPolicy/v1"
ENDPOINT_POLICY_SCHEMA: Final = "mirror.demo/D02R2GenerationEndpointPolicy/v1"
CREDENTIAL_BOUNDARY_SCHEMA: Final = "mirror.demo/D02R2GenerationCredentialProcessBoundary/v1"
RETENTION_POLICY_SCHEMA: Final = "mirror.demo/D02R2GenerationProviderRetentionPolicy/v1"
PROMPT_POLICY_SCHEMA: Final = "mirror.demo/D02R2GenerationPromptPolicy/v1"
SINK_POLICY_SCHEMA: Final = "mirror.demo/D02R2GenerationCreateNewSinkPolicy/v1"

AUTHORITY_ID: Final = "P3_P7_D02_R2_GENERATION_CAPABILITY_AUTHORITY_01"
CHANGE_CONTROL_ID: Final = "P3_P7_D02_CC_08"
GOAL_EPOCH_ID: Final = "P3_P7_COMPLETE_DEMO_EPOCH_02"
ACCEPTED_PLAN_SHA: Final = "218f4b5a5ee4e6e2223995d232da61496dd47de3"
ACCEPTED_PLAN_TREE: Final = "1cff56bd1f1127a310622d5b8a72045b39290549"
EVIDENCE_ROOT_ID: Final = "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"
PRODUCER_TASK_ID: Final = "P3_P7_D02_R2_SOURCE_COHORT_01"
DISPATCH_EPOCH: Final = 1

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class D02R2GenerationCapabilityError(ValueError):
    """A generation capability or request authority failed exact replay."""


def _fail(message: str) -> NoReturn:
    raise D02R2GenerationCapabilityError(message)


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT_ID_RE.fullmatch(value) is None:
        _fail(f"{label} is not an allowed opaque output ID")
    return value


def _require_exact_mapping(
    value: object,
    expected_keys: tuple[str, ...],
    label: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value) != expected_keys:
        _fail(f"{label} keys or key order are not exact")
    return cast(Mapping[str, object], value)


def _strict_json_equal(actual: object, expected: object) -> bool:
    """Compare JSON recursively without admitting bool-as-int equality."""

    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or list(actual) != list(expected):
            return False
        return all(_strict_json_equal(actual[key], item) for key, item in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(
            _strict_json_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected, strict=True)
        )
    return actual == expected


def _typed_digest(schema_version: str, payload: Mapping[str, object], label: str) -> str:
    try:
        return mirror_demo_digest(schema_version, cast(Mapping[str, JsonValue], payload))
    except (TypeError, ValueError) as error:
        raise D02R2GenerationCapabilityError(f"{label} is not canonical JSON") from error


def _endpoint_policy() -> JsonObject:
    return {
        "schema_version": ENDPOINT_POLICY_SCHEMA,
        "approved_control_plane_invocations": ["image_gen.imagegen"],
        "built_in_remote_control_plane_allowed": True,
        "approved_direct_network_endpoints": [],
        "direct_http_allowed": False,
        "direct_sdk_allowed": False,
        "url_input_allowed": False,
        "external_network_client_allowed": False,
        "operator_public_internet_egress": ("DENIED_EXCEPT_APPROVED_CODEX_BUILTIN_CONTROL_PLANE"),
        "core_runtime_public_internet_egress": "DENIED",
    }


def _credential_boundary() -> JsonObject:
    return {
        "schema_version": CREDENTIAL_BOUNDARY_SCHEMA,
        "credential_mode": "CODEX_HOST_MANAGED_OPAQUE_NOT_EXPOSED",
        "caller_supplied_credential": None,
        "caller_secret_allowed": False,
        "environment_secret_allowed": False,
        "producer_secret_value_access_allowed": False,
        "credential_persistence_allowed": False,
        "credential_logging_allowed": False,
        "credential_handoff_allowed": False,
        "approved_process_boundary": "CODEX_NATIVE_IMAGEGEN_CONTROL_PLANE_ONLY",
    }


def _retention_policy() -> JsonObject:
    return {
        "schema_version": RETENTION_POLICY_SCHEMA,
        "provider_terms": None,
        "provider_terms_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "license": None,
        "license_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "output_rights": None,
        "output_rights_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "provider_input_retention": None,
        "provider_input_retention_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "provider_output_retention": None,
        "provider_output_retention_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "provider_training_use": None,
        "provider_training_use_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "provider_deletion_sla": None,
        "provider_deletion_sla_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "approved_use": "PRIVATE_INTERNAL_D02_R2_DEMO_ONLY",
        "real_user_data_allowed": False,
        "redistribution_allowed": False,
        "production_allowed": False,
        "public_distribution_allowed": False,
    }


def _prompt_policy() -> JsonObject:
    return {
        "schema_version": PROMPT_POLICY_SCHEMA,
        "prompt_material_digest_algorithm": "SHA256_EXACT_UTF8_BYTES",
        "prompt_custody": "PRINCIPAL_CUSTODIAN",
        "prompt_delivery_mode": "MINIMAL_TASK_SCOPED_PRODUCER_HANDOFF",
        "producer_prompt_access": "EXACT_CANDIDATE_REQUEST_ONLY",
        "prompt_non_propagation_required": True,
        "prompt_cleanup_required": True,
        "prompt_text_in_authority_allowed": False,
        "prompt_text_in_git_allowed": False,
        "prompt_locator_in_git_allowed": False,
        "prompt_text_in_registry_allowed": False,
        "prompt_text_in_logs_allowed": False,
        "prompt_text_in_coordination_allowed": False,
        "reference_images_allowed": False,
        "real_user_content_allowed": False,
        "synthetic_only_prompt_required": True,
        "clearly_adult_prompt_required": True,
        "real_person_reference_forbidden": True,
        "celebrity_imitation_forbidden": True,
        "sensitive_trait_prompting_forbidden": True,
        "beauty_scoring_prompt_forbidden": True,
        "minor_or_student_context_forbidden": True,
    }


def _sink_policy() -> JsonObject:
    return {
        "schema_version": SINK_POLICY_SCHEMA,
        "native_path_parameter_allowed": False,
        "write_actor_policy": (
            "PRODUCER_DIRECT_PREALLOCATED_ROOT_SCOPED_HANDLE_ELSE_PRINCIPAL_EXECUTES_SENSITIVE_STEP"
        ),
        "principal_copy_required": False,
        "preallocated_root_scoped_handle_required": True,
        "source_output_id_preallocated_required": True,
        "source_name_receipt_preallocated_required": True,
        "provenance_output_id_preallocated_required": True,
        "provenance_name_receipt_preallocated_required": True,
        "create_new_exclusive_required": True,
        "overwrite_allowed": False,
        "automatic_suffix_allowed": False,
        "os_temp_allowed": False,
        "external_storage_allowed": False,
        "producer_allocate_allowed": False,
        "producer_seal_allowed": False,
        "producer_register_allowed": False,
        "allowed_destination_classes": [
            "DATA_SOURCE_CANDIDATES",
            "DATA_SOURCE_PROVENANCE",
        ],
        "failed_or_unregistered_output_policy": ("ORDINAL_CONSUMED_COHORT_FAILED_NO_REPLACEMENT"),
    }


_POLICY_SPECS: Final[tuple[tuple[str, str, str, PolicyBuilder], ...]] = (
    (
        "approved_endpoint_policy",
        "approved_endpoint_policy_digest",
        ENDPOINT_POLICY_SCHEMA,
        _endpoint_policy,
    ),
    (
        "credential_process_boundary",
        "credential_process_boundary_digest",
        CREDENTIAL_BOUNDARY_SCHEMA,
        _credential_boundary,
    ),
    (
        "provider_retention_policy",
        "provider_retention_policy_digest",
        RETENTION_POLICY_SCHEMA,
        _retention_policy,
    ),
    (
        "prompt_policy",
        "prompt_policy_digest",
        PROMPT_POLICY_SCHEMA,
        _prompt_policy,
    ),
    (
        "create_new_sink_policy",
        "create_new_sink_policy_digest",
        SINK_POLICY_SCHEMA,
        _sink_policy,
    ),
)

STOP_RULES: Final[tuple[str, ...]] = (
    "GENERATION_CAPABILITY_AUTHORITY_MISSING",
    "GENERATION_CAPABILITY_AUTHORITY_MISMATCH_STOP",
    "GENERATION_CAPABILITY_SCOPE_MISMATCH_STOP",
    "GENERATION_DISCLOSURE_STATE_MISMATCH_STOP",
    "GENERATION_ENDPOINT_POLICY_VIOLATION_STOP",
    "GENERATION_CREDENTIAL_PROCESS_BOUNDARY_VIOLATION_STOP",
    "GENERATION_PROVIDER_RETENTION_POLICY_VIOLATION_STOP",
    "GENERATION_PROMPT_POLICY_VIOLATION_STOP",
    "GENERATION_SAFETY_SCOPE_VIOLATION_STOP",
    "EVIDENCE_ROOT_NOT_READY_STOP",
    "EVIDENCE_ROOT_NAME_COLLISION_STOP",
    "OUTPUT_NAME_OR_ID_COLLISION_STOP",
    "OUTPUT_NAME_RECEIPT_PARTIAL_OR_CORRUPT_STOP",
    "REGISTRY_INCONSISTENT_STOP",
    "GENERATION_PREREGISTRATION_MISMATCH_STOP",
    "GENERATION_REQUEST_POLICY_MISSING_OR_MISMATCH_STOP",
    "GENERATION_ALLOCATION_MISMATCH_STOP",
    "GENERATION_CREATE_NEW_SINK_POLICY_VIOLATION_STOP",
    "GENERATION_PRIMARY_CALL_CEILING_STOP",
    "GENERATION_RETRY_CEILING_STOP",
    "GENERATION_CONCURRENCY_CEILING_STOP",
    "GENERATION_RESERVE_CALL_NOT_AUTHORIZED_STOP",
    "GENERATION_MAX_TOTAL_CALL_CAPACITY_STOP",
    "GENERATION_OUTPUT_COUNT_STOP",
    "GENERATION_SOURCE_MEDIA_TYPE_STOP",
    "GENERATION_SOURCE_BYTE_CEILING_STOP",
    "GENERATION_PROVENANCE_MEDIA_TYPE_STOP",
    "GENERATION_PROVENANCE_BYTE_CEILING_STOP",
    "GENERATION_RESULT_PROVENANCE_MISSING_STOP",
    "SOURCE_OUTPUT_REGISTRATION_FAILED",
    "GENERATION_ORDINAL_CONSUMED_COHORT_FAILED_STOP",
    "QUESTIONNAIRE_RUNTIME_GENERATION_FORBIDDEN_STOP",
    "PRODUCTION_PROVIDER_CLASSIFICATION_FORBIDDEN_STOP",
    "EXTERNAL_RUNTIME_DEPENDENCY_FOUND",
)

AUTHORITY_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "authority_id",
    "change_control_id",
    "goal_epoch_id",
    "track",
    "authority_state",
    "accepted_plan_sha",
    "accepted_plan_tree",
    "evidence_root_id",
    "producer_task_id",
    "dispatch_epoch",
    "capability_binding",
    "qualification",
    "disclosure",
    "execution_budget",
    "output_envelope",
    "safety_scope",
    "approved_endpoint_policy",
    "approved_endpoint_policy_digest",
    "credential_process_boundary",
    "credential_process_boundary_digest",
    "provider_retention_policy",
    "provider_retention_policy_digest",
    "prompt_policy",
    "prompt_policy_digest",
    "create_new_sink_policy",
    "create_new_sink_policy_digest",
    "generation_request_policy_schema_version",
    "stop_rules",
    "generation_capability_authority_digest",
)

REQUEST_POLICY_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "generation_capability_authority_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "prompt_policy_digest",
    "create_new_sink_policy_digest",
    "candidate_ordinal",
    "source_output_id",
    "output_name_receipt_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "prompt_material_digest",
    "producer_task_id",
    "dispatch_epoch",
    "request_state",
    "requested_call_count",
    "retry_ceiling",
    "source_maximum_bytes",
    "source_expected_media_type",
    "provenance_maximum_bytes",
    "provenance_expected_media_type",
    "generation_request_policy_digest",
)


def _capability_binding() -> JsonObject:
    return {
        "tool": "CODEX_NATIVE_IMAGEGEN",
        "invocation": "image_gen.imagegen",
        "purpose": "DEMO_ONLY_SYNTHETIC_SOURCE_PRODUCTION",
        "source_kind": "CODEX_NATIVE_IMAGEGEN",
        "control_plane_kind": "CODEX_BUILTIN_REMOTE_CONTROL_PLANE",
        "execution_mode": "DISPATCHED_OPERATOR_ASSISTED_PRE_RUNTIME_CREATE_NEW",
        "provider_adapter_classification": (
            "OPERATOR_ASSISTED_PRE_RUNTIME_TOOL_NOT_RUNTIME_PROVIDER"
        ),
        "production_provider": False,
        "formal_phase_authority": False,
        "questionnaire_runtime_generative_calls": 0,
        "provenance_level": "PROVENANCE_ONLY",
        "input_mode": "TEXT_ONLY_CREATE_NEW",
        "referenced_image_paths_allowed": False,
        "num_last_images_to_include_allowed": False,
    }


def _qualification() -> JsonObject:
    return {
        "qualification_tier": "RESEARCH_QUALIFIED",
        "current_status": "OWNER_AUTHORIZED_FOR_EXACT_D02_R2_DEMO_ONLY",
        "approved_scope": ["DEMO_ONLY_SYNTHETIC_SOURCE_PRODUCTION"],
        "prohibited_scope": [
            "REAL_USER_INPUT",
            "REFERENCE_IMAGE_INPUT",
            "QUESTIONNAIRE_RUNTIME",
            "GENERATIVE_EDITOR",
            "RUNTIME_PROVIDER",
            "FORMAL_PHASE_AUTHORITY",
            "PRODUCTION_DISTRIBUTION",
            "PUBLIC_DISTRIBUTION",
            "TRAINING",
            "MODEL_DOWNLOAD",
            "RETRY_WITHIN_DISPATCH_EPOCH",
            "REPLACEMENT_OUTPUT_WITHIN_DISPATCH_EPOCH",
        ],
    }


def _disclosure() -> JsonObject:
    return {
        "provider": None,
        "provider_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "model": None,
        "model_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "model_version": None,
        "model_version_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "request_id": None,
        "request_id_state": "NOT_EXPOSED_NULL_REQUIRED",
        "seed": None,
        "seed_state": "NOT_EXPOSED_NULL_REQUIRED",
        "usage": None,
        "usage_state": "NOT_EXPOSED_NULL_REQUIRED",
        "cost": None,
        "cost_state": "NOT_EXPOSED_NULL_REQUIRED",
        "reported_cost_currency": None,
        "reported_cost_currency_state": "NOT_EXPOSED_NULL_REQUIRED",
    }


def _execution_budget() -> JsonObject:
    return {
        "primary_calls_authorized": 4,
        "retry_ceiling": 0,
        "concurrency": 1,
        "outputs_per_call_ceiling": 1,
        "primary_output_ceiling": 4,
        "maximum_total_call_capacity": 8,
        "reserve_call_capacity": 4,
        "reserve_calls_authorized": 0,
        "effective_call_ceiling_current_dispatch": 4,
        "reserve_state": "DISABLED",
        "reserve_activation_requires_all": True,
        "ordered_reserve_activation_requirements": [
            "ACCEPTED_FORWARD_CHANGE_CONTROL",
            "NEW_DISPATCH_EPOCH",
            "NEW_OUTPUT_IDS",
            "NEW_ALLOCATIONS",
        ],
        "cost_accounting_mode": "REQUEST_COUNT_ONLY",
        "provider_cost_ceiling": None,
        "provider_cost_currency": None,
        "incremental_purchase_ceiling_minor_units": 0,
        "paid_upgrade_or_credit_purchase_allowed": False,
    }


def _output_envelope() -> JsonObject:
    return {
        "source_count": 4,
        "source_outputs_per_call": 1,
        "source_expected_media_type": "image/png",
        "per_source_maximum_bytes": 20_971_520,
        "aggregate_source_maximum_bytes": 83_886_080,
        "provenance_outputs_per_source": 1,
        "provenance_expected_media_type": "application/json",
        "per_provenance_maximum_bytes": 262_144,
        "aggregate_provenance_maximum_bytes": 1_048_576,
    }


def _safety_scope() -> JsonObject:
    return {
        "synthetic_only_required": True,
        "clearly_adult_required": True,
        "real_person_reference_forbidden": True,
        "user_image_forbidden": True,
        "reference_image_forbidden": True,
        "celebrity_imitation_forbidden": True,
        "one_to_one_identity_reproduction_forbidden": True,
        "sensitive_inference_forbidden": True,
        "beauty_score_forbidden": True,
        "global_ideal_face_forbidden": True,
        "questionnaire_runtime_generation_forbidden": True,
    }


def build_generation_capability_authority() -> JsonObject:
    """Build the sole pre-root capability with fresh nested values."""

    authority: JsonObject = {
        "schema_version": GENERATION_CAPABILITY_AUTHORITY_SCHEMA,
        "authority_id": AUTHORITY_ID,
        "change_control_id": CHANGE_CONTROL_ID,
        "goal_epoch_id": GOAL_EPOCH_ID,
        "track": "DEMO_PROTOTYPE",
        "authority_state": "OWNER_AUTHORIZED",
        "accepted_plan_sha": ACCEPTED_PLAN_SHA,
        "accepted_plan_tree": ACCEPTED_PLAN_TREE,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "producer_task_id": PRODUCER_TASK_ID,
        "dispatch_epoch": DISPATCH_EPOCH,
        "capability_binding": _capability_binding(),
        "qualification": _qualification(),
        "disclosure": _disclosure(),
        "execution_budget": _execution_budget(),
        "output_envelope": _output_envelope(),
        "safety_scope": _safety_scope(),
    }
    for policy_key, digest_key, schema_version, builder in _POLICY_SPECS:
        policy = builder()
        authority[policy_key] = policy
        authority[digest_key] = _typed_digest(schema_version, policy, policy_key)
    authority["generation_request_policy_schema_version"] = GENERATION_REQUEST_POLICY_SCHEMA
    authority["stop_rules"] = list(STOP_RULES)
    authority["generation_capability_authority_digest"] = ""
    authority["generation_capability_authority_digest"] = _typed_digest(
        GENERATION_CAPABILITY_AUTHORITY_SCHEMA,
        {
            key: value
            for key, value in authority.items()
            if key != "generation_capability_authority_digest"
        },
        "generation capability authority",
    )
    if tuple(authority) != AUTHORITY_KEYS:
        _fail("generation capability authority construction order drifted")
    return authority


def _validate_embedded_policies(authority: Mapping[str, object]) -> None:
    for policy_key, digest_key, schema_version, builder in _POLICY_SPECS:
        expected_policy = builder()
        submitted_policy = _require_exact_mapping(
            authority[policy_key], tuple(expected_policy), policy_key
        )
        if not _strict_json_equal(dict(submitted_policy), expected_policy):
            _fail(f"{policy_key} differs from the frozen policy")
        submitted_digest = _require_digest(authority[digest_key], digest_key)
        replayed_digest = _typed_digest(schema_version, submitted_policy, policy_key)
        if submitted_digest != replayed_digest:
            _fail(f"{policy_key} digest does not replay")


def validate_generation_capability_authority(value: object) -> Mapping[str, object]:
    """Validate embedded policies first, then exact values and top-level digest."""

    authority = _require_exact_mapping(value, AUTHORITY_KEYS, "generation capability")
    _validate_embedded_policies(authority)
    expected = build_generation_capability_authority()
    if not _strict_json_equal(dict(authority), expected):
        _fail("generation capability differs from the frozen authority")
    submitted_digest = _require_digest(
        authority["generation_capability_authority_digest"],
        "generation capability authority digest",
    )
    replayed_digest = _typed_digest(
        GENERATION_CAPABILITY_AUTHORITY_SCHEMA,
        {
            key: value
            for key, value in authority.items()
            if key != "generation_capability_authority_digest"
        },
        "generation capability authority",
    )
    if submitted_digest != replayed_digest:
        _fail("generation capability authority digest does not replay")
    return authority


def build_generation_request_policy(
    *,
    candidate_ordinal: int,
    source_output_id: str,
    output_name_receipt_digest: str,
    source_provenance_output_id: str,
    source_provenance_name_receipt_digest: str,
    prompt_material_digest: str,
    root_name_receipt_digest: str,
    generation_preregistration_digest: str,
) -> JsonObject:
    """Build one post-root request for an exact preallocated source/provenance pair."""

    if type(candidate_ordinal) is not int or candidate_ordinal not in {1, 2, 3, 4}:
        _fail("candidate ordinal must be one of 1, 2, 3, or 4")
    source_output_id = _require_output_id(source_output_id, "source output ID")
    source_provenance_output_id = _require_output_id(
        source_provenance_output_id, "source provenance output ID"
    )
    if source_output_id == source_provenance_output_id:
        _fail("source and provenance output IDs must be distinct")
    output_name_receipt_digest = _require_digest(
        output_name_receipt_digest, "output name receipt digest"
    )
    source_provenance_name_receipt_digest = _require_digest(
        source_provenance_name_receipt_digest,
        "source provenance name receipt digest",
    )
    prompt_material_digest = _require_digest(prompt_material_digest, "prompt material digest")
    root_name_receipt_digest = _require_digest(root_name_receipt_digest, "root name receipt digest")
    generation_preregistration_digest = _require_digest(
        generation_preregistration_digest,
        "generation preregistration digest",
    )

    capability = build_generation_capability_authority()
    request: JsonObject = {
        "schema_version": GENERATION_REQUEST_POLICY_SCHEMA,
        "generation_capability_authority_digest": capability[
            "generation_capability_authority_digest"
        ],
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_name_receipt_digest,
        "generation_preregistration_digest": generation_preregistration_digest,
        "prompt_policy_digest": capability["prompt_policy_digest"],
        "create_new_sink_policy_digest": capability["create_new_sink_policy_digest"],
        "candidate_ordinal": candidate_ordinal,
        "source_output_id": source_output_id,
        "output_name_receipt_digest": output_name_receipt_digest,
        "source_provenance_output_id": source_provenance_output_id,
        "source_provenance_name_receipt_digest": (source_provenance_name_receipt_digest),
        "prompt_material_digest": prompt_material_digest,
        "producer_task_id": PRODUCER_TASK_ID,
        "dispatch_epoch": DISPATCH_EPOCH,
        "request_state": "AUTHORIZED_PREALLOCATED_CREATE_NEW_ONLY",
        "requested_call_count": 1,
        "retry_ceiling": 0,
        "source_maximum_bytes": 20_971_520,
        "source_expected_media_type": "image/png",
        "provenance_maximum_bytes": 262_144,
        "provenance_expected_media_type": "application/json",
        "generation_request_policy_digest": "",
    }
    request["generation_request_policy_digest"] = _typed_digest(
        GENERATION_REQUEST_POLICY_SCHEMA,
        {key: value for key, value in request.items() if key != "generation_request_policy_digest"},
        "generation request policy",
    )
    if tuple(request) != REQUEST_POLICY_KEYS:
        _fail("generation request policy construction order drifted")
    return request


def validate_generation_request_policy(value: object) -> Mapping[str, object]:
    """Replay a post-root per-candidate request against the frozen capability."""

    request = _require_exact_mapping(value, REQUEST_POLICY_KEYS, "generation request policy")
    candidate_ordinal = request["candidate_ordinal"]
    if type(candidate_ordinal) is not int:
        _fail("candidate ordinal must be an integer")
    rebuilt = build_generation_request_policy(
        candidate_ordinal=candidate_ordinal,
        source_output_id=_require_output_id(request["source_output_id"], "source output ID"),
        output_name_receipt_digest=_require_digest(
            request["output_name_receipt_digest"],
            "output name receipt digest",
        ),
        source_provenance_output_id=_require_output_id(
            request["source_provenance_output_id"],
            "source provenance output ID",
        ),
        source_provenance_name_receipt_digest=_require_digest(
            request["source_provenance_name_receipt_digest"],
            "source provenance name receipt digest",
        ),
        prompt_material_digest=_require_digest(
            request["prompt_material_digest"], "prompt material digest"
        ),
        root_name_receipt_digest=_require_digest(
            request["root_name_receipt_digest"], "root name receipt digest"
        ),
        generation_preregistration_digest=_require_digest(
            request["generation_preregistration_digest"],
            "generation preregistration digest",
        ),
    )
    if not _strict_json_equal(dict(request), rebuilt):
        _fail("generation request policy differs from the frozen binding")
    submitted_digest = _require_digest(
        request["generation_request_policy_digest"],
        "generation request policy digest",
    )
    replayed_digest = _typed_digest(
        GENERATION_REQUEST_POLICY_SCHEMA,
        {key: item for key, item in request.items() if key != "generation_request_policy_digest"},
        "generation request policy",
    )
    if submitted_digest != replayed_digest:
        _fail("generation request policy digest does not replay")
    return request
