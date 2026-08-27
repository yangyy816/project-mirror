from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from mirror_api import demo_d02_r2_generation_capability as subject
from mirror_api.demo_measurement_quality import mirror_demo_digest

EXPECTED_AUTHORITY_KEYS = (
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

EXPECTED_REQUEST_KEYS = (
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

EXPECTED_STOP_RULES = (
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

POLICY_SPECS = (
    (
        "approved_endpoint_policy",
        "approved_endpoint_policy_digest",
        subject.ENDPOINT_POLICY_SCHEMA,
    ),
    (
        "credential_process_boundary",
        "credential_process_boundary_digest",
        subject.CREDENTIAL_BOUNDARY_SCHEMA,
    ),
    (
        "provider_retention_policy",
        "provider_retention_policy_digest",
        subject.RETENTION_POLICY_SCHEMA,
    ),
    (
        "prompt_policy",
        "prompt_policy_digest",
        subject.PROMPT_POLICY_SCHEMA,
    ),
    (
        "create_new_sink_policy",
        "create_new_sink_policy_digest",
        subject.SINK_POLICY_SCHEMA,
    ),
)


def _object(value: subject.JsonValue) -> subject.JsonObject:
    assert isinstance(value, dict)
    return value


def _list(value: subject.JsonValue) -> list[subject.JsonValue]:
    assert isinstance(value, list)
    return value


def _request() -> subject.JsonObject:
    return subject.build_generation_request_policy(
        candidate_ordinal=1,
        source_output_id="source-1",
        output_name_receipt_digest="a" * 64,
        source_provenance_output_id="provenance-1",
        source_provenance_name_receipt_digest="b" * 64,
        prompt_material_digest="c" * 64,
        root_name_receipt_digest="d" * 64,
        generation_preregistration_digest="e" * 64,
    )


def _resign_authority(value: subject.JsonObject) -> None:
    value["generation_capability_authority_digest"] = mirror_demo_digest(
        subject.GENERATION_CAPABILITY_AUTHORITY_SCHEMA,
        {
            key: item
            for key, item in value.items()
            if key != "generation_capability_authority_digest"
        },
    )


def _resign_request(value: subject.JsonObject) -> None:
    value["generation_request_policy_digest"] = mirror_demo_digest(
        subject.GENERATION_REQUEST_POLICY_SCHEMA,
        {key: item for key, item in value.items() if key != "generation_request_policy_digest"},
    )


def test_authority_is_deterministic_and_exactly_ordered() -> None:
    first = subject.build_generation_capability_authority()
    second = subject.build_generation_capability_authority()

    assert tuple(first) == EXPECTED_AUTHORITY_KEYS == subject.AUTHORITY_KEYS
    assert first == second
    assert "root_name_receipt_digest" not in first
    assert subject.validate_generation_capability_authority(first) == first


def test_capability_scope_disclosure_and_known_nulls_are_exact() -> None:
    authority = subject.build_generation_capability_authority()
    binding = _object(authority["capability_binding"])
    qualification = _object(authority["qualification"])
    disclosure = _object(authority["disclosure"])

    assert binding["tool"] == "CODEX_NATIVE_IMAGEGEN"
    assert binding["invocation"] == "image_gen.imagegen"
    assert binding["purpose"] == "DEMO_ONLY_SYNTHETIC_SOURCE_PRODUCTION"
    assert binding["source_kind"] == "CODEX_NATIVE_IMAGEGEN"
    assert binding["provenance_level"] == "PROVENANCE_ONLY"
    assert binding["production_provider"] is False
    assert binding["questionnaire_runtime_generative_calls"] == 0
    assert qualification["qualification_tier"] == "RESEARCH_QUALIFIED"
    assert qualification["approved_scope"] == ["DEMO_ONLY_SYNTHETIC_SOURCE_PRODUCTION"]
    for key in (
        "provider",
        "model",
        "model_version",
        "request_id",
        "seed",
        "usage",
        "cost",
        "reported_cost_currency",
    ):
        assert disclosure[key] is None
    assert disclosure["provider_state"] == "OPAQUE_ACCEPTED_FOR_DEMO_ONLY"
    assert disclosure["model_state"] == "OPAQUE_ACCEPTED_FOR_DEMO_ONLY"
    assert disclosure["model_version_state"] == "OPAQUE_ACCEPTED_FOR_DEMO_ONLY"


def test_endpoint_reserve_prompt_and_sink_boundaries_are_exact() -> None:
    authority = subject.build_generation_capability_authority()
    endpoint = _object(authority["approved_endpoint_policy"])
    budget = _object(authority["execution_budget"])
    prompt = _object(authority["prompt_policy"])
    sink = _object(authority["create_new_sink_policy"])

    assert endpoint["approved_control_plane_invocations"] == ["image_gen.imagegen"]
    assert endpoint["built_in_remote_control_plane_allowed"] is True
    assert endpoint["approved_direct_network_endpoints"] == []
    assert endpoint["direct_http_allowed"] is False
    assert endpoint["direct_sdk_allowed"] is False
    assert endpoint["url_input_allowed"] is False
    assert endpoint["external_network_client_allowed"] is False
    assert endpoint["core_runtime_public_internet_egress"] == "DENIED"
    assert budget["primary_calls_authorized"] == 4
    assert budget["effective_call_ceiling_current_dispatch"] == 4
    assert budget["maximum_total_call_capacity"] == 8
    assert budget["reserve_calls_authorized"] == 0
    assert budget["reserve_state"] == "DISABLED"
    assert budget["ordered_reserve_activation_requirements"] == [
        "ACCEPTED_FORWARD_CHANGE_CONTROL",
        "NEW_DISPATCH_EPOCH",
        "NEW_OUTPUT_IDS",
        "NEW_ALLOCATIONS",
    ]
    assert prompt["prompt_custody"] == "PRINCIPAL_CUSTODIAN"
    assert prompt["prompt_delivery_mode"] == "MINIMAL_TASK_SCOPED_PRODUCER_HANDOFF"
    assert prompt["prompt_text_in_git_allowed"] is False
    assert prompt["reference_images_allowed"] is False
    assert sink["native_path_parameter_allowed"] is False
    assert sink["preallocated_root_scoped_handle_required"] is True
    assert sink["create_new_exclusive_required"] is True
    assert sink["overwrite_allowed"] is False
    assert sink["producer_allocate_allowed"] is False
    assert sink["producer_register_allowed"] is False


def test_stop_rules_are_the_exact_ordered_34_rule_contract() -> None:
    authority = subject.build_generation_capability_authority()

    assert tuple(subject.STOP_RULES) == EXPECTED_STOP_RULES
    assert _list(authority["stop_rules"]) == list(EXPECTED_STOP_RULES)
    assert len(EXPECTED_STOP_RULES) == 34


def test_builders_return_fresh_nested_values_without_global_contamination() -> None:
    first = subject.build_generation_capability_authority()
    second = subject.build_generation_capability_authority()
    first_prompt = _object(first["prompt_policy"])
    second_prompt = _object(second["prompt_policy"])
    first_stops = _list(first["stop_rules"])
    second_stops = _list(second["stop_rules"])

    assert first_prompt is not second_prompt
    assert first_stops is not second_stops
    first_prompt["prompt_custody"] = "CALLER_MUTATION"
    first_stops.append("CALLER_MUTATION")
    third = subject.build_generation_capability_authority()
    assert second_prompt["prompt_custody"] == "PRINCIPAL_CUSTODIAN"
    assert second_stops == list(EXPECTED_STOP_RULES)
    assert _object(third["prompt_policy"])["prompt_custody"] == "PRINCIPAL_CUSTODIAN"
    assert _list(third["stop_rules"]) == list(EXPECTED_STOP_RULES)


@pytest.mark.parametrize("policy_key,digest_key,schema_version", POLICY_SPECS)
def test_each_stale_embedded_digest_is_rejected_even_with_resigned_top_level(
    policy_key: str,
    digest_key: str,
    schema_version: str,
) -> None:
    del policy_key, schema_version
    authority = subject.build_generation_capability_authority()
    authority[digest_key] = "0" * 64
    _resign_authority(authority)

    with pytest.raises(subject.D02R2GenerationCapabilityError, match="digest does not replay"):
        subject.validate_generation_capability_authority(authority)


@pytest.mark.parametrize("policy_key,digest_key,schema_version", POLICY_SPECS)
def test_each_changed_policy_is_rejected_after_embedded_and_top_level_resign(
    policy_key: str,
    digest_key: str,
    schema_version: str,
) -> None:
    authority = subject.build_generation_capability_authority()
    policy = _object(authority[policy_key])
    drift_key = next(key for key in policy if key != "schema_version")
    policy[drift_key] = "FULLY_RESIGNED_DRIFT"
    authority[digest_key] = mirror_demo_digest(schema_version, policy)
    _resign_authority(authority)

    with pytest.raises(
        subject.D02R2GenerationCapabilityError, match="differs from the frozen policy"
    ):
        subject.validate_generation_capability_authority(authority)


@pytest.mark.parametrize(
    "key,replacement",
    (("change_control_id", "P3_P7_D02_CC_09"), ("dispatch_epoch", True)),
)
def test_resigned_top_level_authority_drift_is_rejected(
    key: str, replacement: subject.JsonValue
) -> None:
    authority = subject.build_generation_capability_authority()
    authority[key] = replacement
    _resign_authority(authority)

    with pytest.raises(
        subject.D02R2GenerationCapabilityError,
        match="differs from the frozen authority",
    ):
        subject.validate_generation_capability_authority(authority)


def test_reordered_stop_rules_are_rejected_after_resign() -> None:
    authority = subject.build_generation_capability_authority()
    _list(authority["stop_rules"]).reverse()
    _resign_authority(authority)

    with pytest.raises(subject.D02R2GenerationCapabilityError):
        subject.validate_generation_capability_authority(authority)


def test_request_has_exact_order_and_actual_root_preregistration_bindings() -> None:
    request = _request()

    assert tuple(request) == EXPECTED_REQUEST_KEYS == subject.REQUEST_POLICY_KEYS
    assert request["root_name_receipt_digest"] == "d" * 64
    assert request["generation_preregistration_digest"] == "e" * 64
    assert request["prompt_material_digest"] == "c" * 64
    assert request["source_output_id"] == "source-1"
    assert request["source_provenance_output_id"] == "provenance-1"
    assert subject.validate_generation_request_policy(request) == request


@pytest.mark.parametrize("key", ("root_name_receipt_digest", "generation_preregistration_digest"))
def test_request_rejects_unresigned_root_or_preregistration_drift(key: str) -> None:
    request = _request()
    request[key] = "f" * 64

    with pytest.raises(subject.D02R2GenerationCapabilityError):
        subject.validate_generation_request_policy(request)


@pytest.mark.parametrize(
    "key,replacement",
    (("producer_task_id", "OTHER_TASK"), ("dispatch_epoch", True)),
)
def test_request_rejects_fully_resigned_frozen_binding_drift(
    key: str, replacement: subject.JsonValue
) -> None:
    request = _request()
    request[key] = replacement
    _resign_request(request)

    with pytest.raises(
        subject.D02R2GenerationCapabilityError,
        match="differs from the frozen binding",
    ):
        subject.validate_generation_request_policy(request)


@pytest.mark.parametrize("ordinal", (True, 0, 5))
def test_request_rejects_boolean_or_out_of_range_ordinal(
    ordinal: bool | int,
) -> None:
    request = _request()
    request["candidate_ordinal"] = ordinal

    with pytest.raises(subject.D02R2GenerationCapabilityError):
        subject.validate_generation_request_policy(request)


def test_request_rejects_uppercase_digest_and_duplicate_output_ids() -> None:
    request = _request()
    request["root_name_receipt_digest"] = "A" * 64
    with pytest.raises(subject.D02R2GenerationCapabilityError):
        subject.validate_generation_request_policy(request)

    with pytest.raises(subject.D02R2GenerationCapabilityError):
        subject.build_generation_request_policy(
            candidate_ordinal=1,
            source_output_id="same",
            source_provenance_output_id="same",
            output_name_receipt_digest="a" * 64,
            source_provenance_name_receipt_digest="b" * 64,
            prompt_material_digest="c" * 64,
            root_name_receipt_digest="d" * 64,
            generation_preregistration_digest="e" * 64,
        )


def test_tracked_authority_json_equals_the_builder_result() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    authority_path = (
        repository_root
        / "docs"
        / "operations"
        / "P3_P7_D02_R2_GENERATION_CAPABILITY_AUTHORITY.json"
    )
    tracked = cast(subject.JsonObject, json.loads(authority_path.read_text("utf-8")))

    assert tracked == subject.build_generation_capability_authority()
    assert tuple(tracked) == EXPECTED_AUTHORITY_KEYS
    assert subject.validate_generation_capability_authority(tracked) == tracked
