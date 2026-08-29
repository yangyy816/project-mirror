from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "docs" / "research" / "P2_QUESTIONBANK_GENERATION_POLICY_V3.json"
POLICY_DOC_PATH = ROOT / "docs" / "research" / "P2_QUESTIONBANK_GENERATION_POLICY_V3.md"
ADR_PATH = (
    ROOT / "docs" / "adr" / "ADR-052-formal-adult-synthetic-stimulus-and-pairwise-admission.md"
)
OPENAPI_PATH = ROOT / "packages" / "contracts" / "openapi.json"
CHANGE_CONTROL_PATH = (
    ROOT
    / "docs"
    / "operations"
    / "P2_M5_CC05_FORMAL_QUESTIONBANK_GENERATION_POLICY_V3_CHANGE_CONTROL.md"
)
CC05_A_EVIDENCE_PATH = (
    ROOT
    / "docs"
    / "operations"
    / "P2_M5_CC05_A_E01_PRIVATE_POLICY_MATERIALIZATION_REDACTED_EVIDENCE.json"
)
CC05_A_EVIDENCE_DOC_PATH = (
    ROOT / "docs" / "operations" / "P2_M5_CC05_A_E01_PRIVATE_POLICY_MATERIALIZATION_EVIDENCE.md"
)
R43_REPAIR_PATH = ROOT / "docs" / "operations" / "P2_M5_R43_EPOCH3_EXECUTION_TRANSITION_REPAIR.md"
ACCEPTANCE_PATH = ROOT / "docs" / "operations" / "P2_M5_ACCEPTANCE.md"
EXECUTION_PROTOCOL_PATH = ROOT / "docs" / "operations" / "P2_M5_EXECUTION_PROTOCOL.md"

_CC05_A_AUTHORIZED_A0_OVERRIDES = {
    "ASSIGNMENT_LEDGER_VERSION": ("p2-m5-cc05a-calibration-assignment-v3-cal-req-002-forward"),
    "CC04_B_E01": "READY_TO_RESUME_AT_CAL_REQ_002_AFTER_CC05_A_ACCEPTANCE",
    "CC04_B_EXECUTION": (
        "EXECUTION_READY_FOR_EXACT_CAL_REQ_002_ONLY_AFTER_PRINCIPAL_PRIVATE_PREFLIGHT"
    ),
    "CC_P2_M5_05_A0_AUTHORITY_CONDITION": (
        "SATISFIED_AT_762B03F52A9F23450C00F7F7FEFC977DB30AB128_RUN_33240395967_"
        "AFTER_EIGHT_ARTIFACT_INSPECTION_SECURITY_AND_SOL_HIGH_REVIEW"
    ),
    "CC_P2_M5_05_A0_STATUS": ("PASS_AT_762B03F52A9F23450C00F7F7FEFC977DB30AB128_RUN_33240395967"),
    "CURRENT_AUTHORITY_TAIL_END": (
        "P2_M5_CC05_A_E01_EPOCH3_PRIVATE_POLICY_MATERIALIZATION_TRUE_EOF"
    ),
    "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
        "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_A0_FOR_THE_COMPLETE_"
        "LISTED_KEYSET_ONLY_AFTER_CC05_A_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_CHECKS_"
        "SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
    ),
    "CURRENT_STATE_AUTHORITY_VERSION": ("p2-m5-cc05-a-e01-epoch3-private-materialization-eof/v1"),
    "CURRENT_STATE_KEY_COVERAGE": (
        "COMPLETE_A0_PREDECESSOR_KEYSET_PLUS_CC05_A_EPOCH3_MATERIALIZATION_DIGEST_"
        "COUNTER_RECOVERY_AND_REDACTION_KEYS"
    ),
    "CURRENT_STATE_MIRROR_RULE": (
        "MUST_MATCH_CANONICAL_ACCEPTANCE_CC05_A_KEY_SET_ORDER_AND_VALUES"
    ),
    "CURRENT_STATE_PRECONDITION_FALLBACK": (
        "ACCEPTED_A0_TRUE_EOF_REMAINS_CURRENT_UNTIL_CC05_A_AUTHORITY_CONDITION_IS_SATISFIED"
    ),
    "DURABLE_BOOTSTRAP": (
        "p2-m5-cc05a-e01-epoch3-bootstrap-v1_SHA256_"
        "EE8BEC4F875F678BC2DBDAE0EC65E7538696D5B38898154ABCC314D03D335D52"
    ),
    "E01_ACTIVE_EXECUTION_CUSTODY": (
        "E01_EPOCH_3_PRINCIPAL_PRIVATE_CUSTODY_ACTIVE_AFTER_CC05_A_ACCEPTANCE"
    ),
    "E01_EPOCH_3_ADMISSION_RUBRIC_VERSION": (
        "formal-questionbank-admission-review-v3-private-epoch3"
    ),
    "E01_EPOCH_3_ADULT_AGE_ASSIGNMENT_MANIFEST": (
        "FROZEN_7_ADULT_18_19_24_ADULT_20_25_SHA256_"
        "F966470C4FF3F79D9417AF95549FC020E95847249502E41DCCFFFA53CB5C9B51"
    ),
    "E01_EPOCH_3_BOOTSTRAP_DIGEST": (
        "EE8BEC4F875F678BC2DBDAE0EC65E7538696D5B38898154ABCC314D03D335D52"
    ),
    "E01_EPOCH_3_BOOTSTRAP_VERSION": "p2-m5-cc05a-e01-epoch3-bootstrap-v1",
    "E01_EPOCH_3_FIXED_ENTRYPOINT_RECOVERY": "PASS",
    "E01_EPOCH_3_POLICY_ENVELOPE_VERSION": ("p2-m5-cc05a-questionbank-policy-envelope-v3"),
    "E01_EPOCH_3_PROMPT_TEMPLATE_VERSION": (
        "cn-formal-questionbank-prompt-semantics-v3-private-epoch3"
    ),
    "E01_EPOCH_3_RECEIPT_BEFORE_DECODE": "PASS_RECEIPT_PRESENT_ZERO_DECODE",
    "E01_EPOCH_3_REGISTER_BEFORE_DECODE": "PASS_REGISTERED_ZERO_DECODE",
    "E01_EPOCH_3_STATUS": ("MATERIALIZED_RECOVERABLE_AND_BOUND_TO_V3_AFTER_CC05_A_ACCEPTANCE"),
    "E01_PRIVATE_STATE_EPOCH": "E01-EPOCH-3_MATERIALIZED_AFTER_CC05_A_ACCEPTANCE",
    "EARLIER_STATUS_SECTIONS": (
        "PRESERVED_HISTORICAL_EVIDENCE_NON_CURRENT_FOR_THE_COMPLETE_LISTED_KEYSET_"
        "AFTER_CC05_A_ACCEPTANCE"
    ),
    "EFFECTIVE_ORDINAL_RANGE": "CAL-REQ-002_TO_CAL-REQ-032",
    "FORMAL_E01_EXECUTION_AUTHORITY": (
        "AUTHORIZED_FOR_CAL_REQ_002_ONLY_AFTER_EXACT_PRIVATE_BOOTSTRAP_COUNTER_AND_"
        "REGISTER_BEFORE_DECODE_PREFLIGHT"
    ),
    "FORMAL_E01_NEXT_ALLOWED_ORDINAL": "CAL-REQ-002",
    "FORMAL_E01_STATUS": "READY_TO_RESUME_AT_CAL_REQ_002_AFTER_CC05_A_ACCEPTANCE",
    "GENERATION_SPECIFICATION_EFFECTIVE_RANGE": "CAL-REQ-002_TO_CAL-REQ-032",
    "GENERATION_SPECIFICATION_VERSION": ("p2-m5-cc05a-formal-questionbank-generation-v3-epoch3"),
    "NEXT_READY_TASK": "EXECUTE_CAL_REQ_002",
    "OUTPUT_LEDGER_VERSION": "p2-m5-cc05a-e01-output-ledger-v3",
    "P2_M5_NEXT_ACTION": (
        "EXECUTE_EXACT_CAL_REQ_002_AFTER_CC05_A_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    ),
    "PRIVATE_REGISTRY_VERSION": "p2-m5-cc05a-e01-private-registry-v3",
    "REQUEST_LEDGER_VERSION": "p2-m5-cc05a-e01-request-ledger-v3",
    "STOP_OUTCOME": (
        "NONE_AFTER_CC05_A_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE_ELSE_ACCEPTED_A0_"
        "REMAINS_CURRENT_AND_CAL_REQ_002_IS_NOT_DISPATCHED"
    ),
}


def _policy() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(POLICY_PATH.read_text(encoding="utf-8")))


def _content_digest(value: dict[str, Any]) -> str:
    canonical_value = dict(value)
    canonical_value.pop("content_sha256")
    canonical = json.dumps(
        canonical_value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _accepted_record() -> dict[str, Any]:
    return {
        "adult_status": "VERIFIED_SYNTHETIC_ADULT",
        "declared_age_band": "ADULT_20_25",
        "suspected_minor": False,
        "visual_context": "EAST_ASIAN_PRESENTING_FIRST_WAVE",
        "style_family": "CLEAN_NATURAL",
        "sexualized_presentation": False,
        "age_style_compatibility": "PASS",
        "real_person_reference": False,
        "celebrity_resemblance": False,
        "source_rights": "PASS",
        "decode_qa": "PASS",
        "likeness_review": "PASS",
        "duplicate_status": "PASS",
        "pair_comparability": "PASS",
        "variable_isolation": "PASS",
        "visual_quality": "PASS",
        "anti_homogenization": "PASS",
    }


def _formal_admission_reasons(record: dict[str, Any]) -> set[str]:
    value = _policy()
    age = value["age_policy"]
    reasons: set[str] = set()

    if record["adult_status"] != age["adult_status_required"]:
        reasons.add("ADULT_STATUS_NOT_VERIFIED")
    if record["declared_age_band"] not in age["allowed_declared_age_bands"]:
        reasons.add("DECLARED_AGE_OUTSIDE_FORMAL_BANDS")
    if record["suspected_minor"] is not False:
        reasons.add("SUSPECTED_MINOR_PRESENTATION")
    if record["visual_context"] in {"CHILD_CONTEXT", "STUDENT_MINOR_CONTEXT"}:
        reasons.add("CHILD_OR_STUDENT_MINOR_CONTEXT")
    if (
        record["declared_age_band"] == "ADULT_18_19"
        and record["style_family"] not in age["adult_18_19_allowed_style_families"]
    ):
        reasons.add("AGE_BAND_PRESENTATION_MISMATCH")
    if record["age_style_compatibility"] != "PASS":
        reasons.add("AGE_BAND_PRESENTATION_MISMATCH")
    if record["sexualized_presentation"] is not False:
        reasons.add("UNEXPECTED_SEXUALIZED_CONTEXT")
    if record["real_person_reference"] is not False:
        reasons.add("REAL_PERSON_REFERENCE")
    if record["celebrity_resemblance"] is not False:
        reasons.add("CELEBRITY_OR_PUBLIC_FIGURE_RESEMBLANCE")
    if record["source_rights"] != "PASS":
        reasons.add("SOURCE_OR_RIGHTS_FAILURE")
    if record["decode_qa"] != "PASS":
        reasons.add("DECODE_OR_AUTOMATIC_QA_FAILURE")
    if record["likeness_review"] != "PASS":
        reasons.add("CELEBRITY_OR_PUBLIC_FIGURE_RESEMBLANCE")
    if record["pair_comparability"] != "PASS":
        reasons.add("PAIR_COMPARABILITY_FAILURE")
    if record["variable_isolation"] != "PASS":
        reasons.add("PAIR_VARIABLE_CONTAMINATION")
    if record["visual_quality"] != "PASS":
        reasons.add("PAIR_ONE_SIDED_VISUAL_FAILURE")
    if record["duplicate_status"] != "PASS":
        reasons.add("EXACT_DUPLICATE")
    if record["anti_homogenization"] != "PASS":
        reasons.add("HOMOGENIZATION_RISK")
    return reasons


def _last_key_block(
    path: Path,
    *,
    authority_version: str,
    sentinel: str,
) -> list[tuple[str, str]]:
    marker = f"CURRENT_STATE_AUTHORITY_VERSION: {authority_version}"
    text = path.read_text(encoding="utf-8")
    start = text.rfind(marker)
    assert start >= 0
    pairs: list[tuple[str, str]] = []
    for line in text[start:].splitlines():
        if ": " in line and not line.startswith("#"):
            key, value = line.split(": ", maxsplit=1)
            pairs.append((key, value))
            if key == "CURRENT_AUTHORITY_TAIL_END":
                assert value == sentinel
                break
    return pairs


def _last_cc05_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-formal-questionbank-generation-policy-v3-eof/v1",
        sentinel="P2_M5_CC05_FORMAL_QUESTIONBANK_GENERATION_POLICY_V3_TRUE_EOF",
    )


def _last_r39_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version=(
            "p2-m5-r39-r38-principal-acceptance-effective-state-authority-repair-eof/v1"
        ),
        sentinel=("P2_M5_R39_R38_PRINCIPAL_ACCEPTANCE_EFFECTIVE_STATE_AUTHORITY_REPAIR_TRUE_EOF"),
    )


def _last_cc05_a0_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-a0-e01-private-state-epoch3-rollover-eof/v1",
        sentinel="P2_M5_CC05_A0_E01_PRIVATE_STATE_EPOCH3_ROLLOVER_TRUE_EOF",
    )


def _last_cc05_a_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-a-e01-epoch3-private-materialization-eof/v1",
        sentinel="P2_M5_CC05_A_E01_EPOCH3_PRIVATE_POLICY_MATERIALIZATION_TRUE_EOF",
    )


def _last_r43_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r43-epoch3-execution-transition-repair-eof/v1",
        sentinel="P2_M5_R43_EPOCH3_EXECUTION_TRANSITION_REPAIR_TRUE_EOF",
    )


def test_policy_v3_has_canonical_digest_and_forward_only_scope() -> None:
    value = _policy()

    assert value["schema_version"] == ("mirror.synthetic-questionbank/GenerationAdmissionPolicy/v3")
    assert value["policy_version"] == "cn-formal-questionbank-adult-18-25-v3"
    assert value["content_sha256"] == _content_digest(value)
    assert value["status"] == "APPROVED_FORWARD_ONLY"
    assert value["historical_evidence_mutated"] is False

    scope = value["scope"]
    assert scope["real_user_runtime_generation_calls"] == 0
    assert scope["question_bank_release_authorized"] is False
    assert scope["public_api_change"] is False
    assert scope["schema_or_migration_change"] is False
    assert scope["production_provider_approved"] is False
    assert scope["real_user_facial_processing_authorized"] is False


def test_policy_v3_is_adult_only_and_resolves_the_conflicting_ten_percent_safely() -> None:
    age = _policy()["age_policy"]
    allowed_bands = age["allowed_declared_age_bands"]

    assert age["main_question_bank_age_policy"] == "ADULT_ONLY_18_TO_25"
    assert allowed_bands == ["ADULT_18_19", "ADULT_20_25"]
    assert not any("16" in band or "17" in band for band in allowed_bands)
    assert age["adult_status_required"] == "VERIFIED_SYNTHETIC_ADULT"
    assert age["suspected_minor_required"] is False
    assert age["automatic_age_estimation"] == "PROHIBITED"
    assert age["adult_18_19_style_rule"] == "NONSEXUAL_ONLY"
    assert age["adult_18_19_allowed_style_families"] == [
        "CLEAN_NATURAL",
        "KOREAN_CLEAR_RESTRAINED",
        "GENTLE_SWEET",
        "REFINED_COOL",
        "COLD_RESERVED",
    ]
    assert age["light_mature_style_allowed_band"] == "ADULT_20_25"
    assert age["sexualized_presentation"] == "PROHIBITED_FOR_FORMAL_PACK"

    distribution = age["distribution"]
    target_percent = distribution["target_percent"]
    assert target_percent == {"ADULT_20_25": 70, "ADULT_18_19": 20}
    assert distribution["adult_only_flex_percent"] == 10
    assert set(distribution["flex_allowed_age_bands"]) == set(allowed_bands)
    assert sum(target_percent.values()) + distribution["adult_only_flex_percent"] == 100
    assert distribution["majority_band"] == "ADULT_20_25"

    admission = _policy()["formal_admission"]
    assert admission["adult_status"] == "VERIFIED_SYNTHETIC_ADULT"
    assert admission["declared_age_bands"] == allowed_bands
    assert admission["suspected_minor"] is False
    assert admission["real_person_reference"] is False
    assert admission["celebrity_resemblance"] is False


def test_policy_v3_separates_geometry_and_style_pair_contracts() -> None:
    value = _policy()
    pairs = value["pair_contracts"]
    geometry = pairs["GEOMETRY_PAIR"]
    style = pairs["STYLE_PAIR"]
    shared = pairs["shared_admission"]

    assert geometry["same_base_synthetic_identity"] is True
    assert geometry["primary_geometry_dimension_count"] == 1
    assert geometry["maximum_necessary_correlated_variables"] == 1
    assert geometry["correlated_variable_must_be_preregistered"] is True
    assert geometry["variable_isolation_required"] == "PASS"
    assert geometry["unsupported_seed_fact"] is None
    assert style["same_base_synthetic_identity"] is True
    assert style["preserve_primary_facial_geometry"] is True
    assert style["style_direction_count"] == 1
    assert style["remeasure_geometry"] is True
    assert shared["both_sides_independently_pass_hard_gates"] is True
    assert shared["pair_comparability_required"] == "PASS"
    assert shared["obvious_error_answer_side"] == "HARD_REJECT_COMPLETE_PAIR"
    assert shared["one_sided_visual_failure"] == "HARD_REJECT_COMPLETE_PAIR"
    assert shared["multi_variable_contamination"] == "HARD_REJECT_COMPLETE_PAIR"

    capture = value["capture_grammar"]
    assert capture["orientation"] == "FRONT_FACING"
    assert capture["gaze"] == "DIRECT_EYE_CONTACT"
    assert capture["lighting"] == "STABLE_SOFT"
    assert capture["background"] == "CLEAN_NEUTRAL_LOW_DISTRACTION"


def test_policy_v3_has_non_scoring_admission_metadata_and_prompt_semantics() -> None:
    value = _policy()
    curation = value["product_curation"]
    record_fields = set(value["required_record_fields"])

    assert curation["mode"] == "CATEGORICAL_NON_NUMERIC"
    assert curation["per_face_numeric_rating"] is False
    assert {
        "BEAUTY_SCORE",
        "ATTRACTIVENESS_SCORE",
        "RANKING",
        "PERCENTILE",
        "UNIVERSAL_IDEAL_FACE",
    } == set(curation["forbidden_authorities"])
    assert not record_fields & {
        "beauty_score",
        "attractiveness_score",
        "rating",
        "ranking",
        "percentile",
        "estimated_age",
    }
    assert {
        "synthetic_identity_id",
        "declared_age_band",
        "adult_status",
        "suspected_minor",
        "visual_context",
        "style_family",
        "sexualized_presentation",
        "age_style_compatibility",
        "pair_type",
        "geometry_dimensions",
        "controlled_variables",
        "preserved_variables",
        "generation_source_kind",
        "generation_provider",
        "generation_version",
        "prompt_policy_version",
        "source_digest",
        "qa_result",
        "rejection_reason",
        "pair_id",
        "pair_side",
        "base_identity_family",
        "real_person_reference",
        "celebrity_resemblance",
        "source_rights",
        "decode_qa",
        "likeness_review",
        "duplicate_status",
        "pair_comparability",
        "variable_isolation",
        "visual_quality",
        "anti_homogenization",
    } <= record_fields

    prompt = value["prompt_semantics"]
    assert {
        "CLEARLY_ADULT",
        "AGE_BAND_18_TO_25",
        "EAST_ASIAN_PRESENTING_FIRST_WAVE",
        "FRONT_FACING",
        "DIRECT_EYE_CONTACT",
        "NEUTRAL_NATURAL_EXPRESSION",
        "STABLE_SOFT_LIGHTING",
        "CLEAN_NEUTRAL_BACKGROUND",
        "CONSISTENT_FRAMING",
        "NATURAL_FACIAL_ANATOMY",
        "SYNTHETIC_NON_REAL_PERSON",
        "NO_CELEBRITY_OR_PUBLIC_FIGURE_RESEMBLANCE",
    } == set(prompt["required"])
    assert prompt["full_prompt_in_git"] is False
    assert value["provider_fact_rules"]["codex_native_source_kind"] == ("CODEX_NATIVE_IMAGEGEN")
    assert value["provider_fact_rules"]["codex_native_runtime_provider"] is False
    assert value["provider_fact_rules"]["unavailable_model_request_seed_usage_cost"] is None
    unavailable_facts = value["provider_fact_rules"]["unavailable_provider_fact_defaults"]
    assert set(unavailable_facts) == {
        "provider",
        "model",
        "model_version",
        "request_reference",
        "seed",
        "usage",
        "cost",
    }
    assert all(fact is None for fact in unavailable_facts.values())

    admission = value["formal_admission"]
    assert admission == {
        "adult_status": "VERIFIED_SYNTHETIC_ADULT",
        "declared_age_bands": ["ADULT_18_19", "ADULT_20_25"],
        "suspected_minor": False,
        "sexualized_presentation": False,
        "age_style_compatibility": "PASS",
        "real_person_reference": False,
        "celebrity_resemblance": False,
        "source_rights": "PASS",
        "decode_qa": "PASS",
        "likeness_review": "PASS",
        "duplicate_status": "PASS",
        "pair_comparability": "PASS",
        "variable_isolation": "PASS",
        "visual_quality": "PASS",
        "anti_homogenization": "PASS",
    }


def test_policy_v3_negative_admission_cases_fail_closed() -> None:
    assert _formal_admission_reasons(_accepted_record()) == set()

    cases: list[tuple[str, Any, str]] = [
        ("adult_status", "UNVERIFIED", "ADULT_STATUS_NOT_VERIFIED"),
        ("declared_age_band", "MINOR_16_17", "DECLARED_AGE_OUTSIDE_FORMAL_BANDS"),
        ("suspected_minor", True, "SUSPECTED_MINOR_PRESENTATION"),
        ("visual_context", "STUDENT_MINOR_CONTEXT", "CHILD_OR_STUDENT_MINOR_CONTEXT"),
        ("sexualized_presentation", True, "UNEXPECTED_SEXUALIZED_CONTEXT"),
        ("age_style_compatibility", "FAIL", "AGE_BAND_PRESENTATION_MISMATCH"),
        ("real_person_reference", True, "REAL_PERSON_REFERENCE"),
        (
            "celebrity_resemblance",
            True,
            "CELEBRITY_OR_PUBLIC_FIGURE_RESEMBLANCE",
        ),
        ("source_rights", "FAIL", "SOURCE_OR_RIGHTS_FAILURE"),
        ("decode_qa", "FAIL", "DECODE_OR_AUTOMATIC_QA_FAILURE"),
        (
            "likeness_review",
            "FAIL",
            "CELEBRITY_OR_PUBLIC_FIGURE_RESEMBLANCE",
        ),
        ("pair_comparability", "FAIL", "PAIR_COMPARABILITY_FAILURE"),
        ("variable_isolation", "FAIL", "PAIR_VARIABLE_CONTAMINATION"),
        ("visual_quality", "FAIL", "PAIR_ONE_SIDED_VISUAL_FAILURE"),
        ("duplicate_status", "FAIL", "EXACT_DUPLICATE"),
        ("anti_homogenization", "FAIL", "HOMOGENIZATION_RISK"),
    ]
    for field, invalid_value, expected_reason in cases:
        record = _accepted_record()
        record[field] = invalid_value
        assert expected_reason in _formal_admission_reasons(record)

    restricted_style = _accepted_record()
    restricted_style["declared_age_band"] = "ADULT_18_19"
    restricted_style["style_family"] = "LIGHT_MATURE_ALLURING_NONSEXUAL"
    assert "AGE_BAND_PRESENTATION_MISMATCH" in _formal_admission_reasons(restricted_style)


def test_policy_v3_rejects_complete_pair_on_one_sided_or_contaminated_result() -> None:
    shared = _policy()["pair_contracts"]["shared_admission"]

    assert shared["both_sides_independently_pass_hard_gates"] is True
    assert shared["one_sided_visual_failure"] == "HARD_REJECT_COMPLETE_PAIR"
    assert shared["finish_imbalance"] == "HARD_REJECT_COMPLETE_PAIR"
    assert shared["multi_variable_contamination"] == "HARD_REJECT_COMPLETE_PAIR"
    assert shared["obvious_error_answer_side"] == "HARD_REJECT_COMPLETE_PAIR"


def test_policy_v3_demo_and_active_m5_transition_remain_fail_closed() -> None:
    value = _policy()
    demo = value["demo_policy"]
    transition = value["m5_transition"]

    assert demo["pregenerated_synthetic_assets_only"] is True
    assert demo["same_formal_hard_gates"] is True
    assert demo["real_user_runtime_generation_calls"] == 0
    assert demo["real_person_examples"] is False
    assert demo["production_validity_claim"] is False
    assert demo["production_training_data_claim"] is False
    assert transition["baseline_commit"] == ("5eda4cf19ca2c8f3f5b66dd4e7e2f5cbd0d51950")
    openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    canonical_openapi = json.dumps(
        openapi,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert (
        transition["baseline_contract_canonical_sha256"]
        == hashlib.sha256(canonical_openapi).hexdigest()
    )
    assert transition["migration_head"] == "0014_m5_eval_authority"
    assert transition["dependency_changes"] == 0
    assert transition["model_artifacts_added"] == 0
    assert transition["cal_req_002_consumed"] is False
    assert transition["image_generation_calls_in_policy_change"] == 0
    assert transition["dispatch_before_private_v3_binding"] == "PROHIBITED"
    assert transition["m5_technical_gate"] == "NOT_EVALUATED"
    assert transition["p2_mvr_v1"] == "NOT_EVALUATED"
    assert transition["p2_m6_entry"] == "CLOSED"


def test_policy_v3_tracked_authority_contains_no_private_material_or_public_api_change() -> None:
    value = _policy()
    serialized = POLICY_PATH.read_text(encoding="utf-8")
    markdown = POLICY_DOC_PATH.read_text(encoding="utf-8")
    adr = ADR_PATH.read_text(encoding="utf-8")

    assert "://" not in serialized
    assert "C:\\" not in serialized
    assert "D:\\" not in serialized
    assert "BEGIN PRIVATE KEY" not in serialized
    assert "CONTENT_SHA256_PLACEHOLDER" not in serialized
    assert value["private_material"]["forbidden_in_git_memory_logs_artifacts_ui"] == [
        "FULL_PROMPT",
        "SEED_VALUE",
        "IMAGE_BYTES",
        "PRIVATE_LOCATOR",
        "OBJECT_KEY",
        "SIGNED_URL",
        "PROVIDER_RAW_PAYLOAD",
        "CREDENTIAL",
    ]
    assert "UNDER_18_FORMAL_ADMISSION: PROHIBITED" in markdown
    assert "REAL_USER_RUNTIME_GENERATION_CALLS: 0" in markdown
    assert "This policy itself generates no image" in markdown
    assert "CAL-REQ-002" in adr

    tracked_v3_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (POLICY_PATH, POLICY_DOC_PATH, ADR_PATH, CHANGE_CONTROL_PATH)
    )
    assert "data:image/" not in tracked_v3_text
    assert "s3://" not in tracked_v3_text
    assert "cos://" not in tracked_v3_text
    assert "C:\\" not in tracked_v3_text
    assert "D:\\" not in tracked_v3_text
    assert (
        re.search(
            r'(?i)(prompt_text|prompt_plaintext|seed_value|private_locator|object_key|signed_url)\s*[:=]\s*["\']?[^\s,;]+',
            tracked_v3_text,
        )
        is None
    )

    openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = cast(dict[str, Any], openapi["paths"])
    assert all("synthetic-generation" not in path for path in paths)
    assert all("question-bank-release" not in path for path in paths)


def test_policy_v3_m5_true_eof_overlay_is_exactly_mirrored_and_fail_closed() -> None:
    canonical = _last_cc05_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_key_block(EXECUTION_PROTOCOL_PATH)

    assert canonical == mirror
    values = dict(canonical)
    assert len(values) == len(canonical)
    assert values["P2_M5_R39"] == (
        "PASS_AT_5EDA4CF19CA2C8F3F5B66DD4E7E2F5CBD0D51950_RUN_32830012131"
    )
    assert values["CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["CC05_IMAGEGEN_CALLS_EXECUTED"] == "0"
    assert values["QUESTIONBANK_GENERATION_POLICY_DIGEST"] == _policy()["content_sha256"].upper()
    assert values["FORMAL_E01_STATUS"] == "SUSPENDED_PENDING_PRIVATE_V3_BINDING"
    assert values["P2_M5_TECHNICAL_GATE"] == "NOT_EVALUATED"
    assert values["P2_MVR_V1_RESULT"] == "NOT_EVALUATED"
    assert values["P2_M6_ENTRY"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert values["NEXT_READY_TASK"] == ("CC-P2-M5-05-A_PRIVATE_POLICY_MATERIALIZATION")
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_CC05_FORMAL_QUESTIONBANK_GENERATION_POLICY_V3_TRUE_EOF",
    )


def test_cc05_a0_epoch3_rollover_is_mirrored_zero_output_and_fail_closed() -> None:
    canonical = _last_cc05_a0_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_a0_key_block(EXECUTION_PROTOCOL_PATH)
    r39_keys = {key for key, _ in _last_r39_key_block(ACCEPTANCE_PATH)}
    cc05_keys = {key for key, _ in _last_cc05_key_block(ACCEPTANCE_PATH)}
    predecessor_keys = r39_keys | cc05_keys

    assert canonical == mirror
    values = dict(canonical)
    assert len(values) == len(canonical)
    assert len(canonical) == 272
    assert len(r39_keys) == 204
    assert len(cc05_keys) == 58
    assert len(predecessor_keys) == 231
    assert predecessor_keys <= values.keys()
    assert values["CC_P2_M5_05_STATUS"] == (
        "PASS_AT_CDCC2591F42EAD6769107E423EECCE16FA9261D7_RUN_33238015901"
    )
    assert values["P2_M5_R40"] == (
        "PASS_AT_CDCC2591F42EAD6769107E423EECCE16FA9261D7_RUN_33238015901"
    )
    assert values["CC_P2_M5_05_A0_STATUS"] == (
        "PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["E01_EPOCH_2_EXECUTION_CUSTODY"] == (
        "RETIRED_EVIDENCE_LOCATION_LOST_AFTER_A0_ACCEPTANCE"
    )
    assert values["E01_EPOCH_2_RECOVERY"] == "ABANDONED_NO_SCAN_NO_GUESS"
    assert values["E01_EPOCH_2_PATH_SEARCH"] == "PROHIBITED"
    assert values["E01_EPOCH_2_REUSE"] == "PROHIBITED"
    assert values["E01_EPOCH_2_BYTES_ABSENCE_CLAIM"] == "PROHIBITED_NOT_MADE"
    assert values["E01_ACTIVE_EXECUTION_CUSTODY"] == "NONE_PENDING_CC05_A"
    assert values["E01_EPOCH_3_STATUS"] == (
        "PROSPECTIVE_AUTHORIZED_NOT_CREATED_AFTER_A0_ACCEPTANCE"
    )
    assert values["E01_EPOCH_3_CREATE_MODE"] == "CREATE_NEW_NO_OVERWRITE"
    assert values["E01_EPOCH_3_AUTHORIZED_ROOT_COUNT"] == "1"
    assert values["E01_EPOCH_3_PRIVATE_DIGEST_INHERITANCE"] == ("PROHIBITED_COMPUTE_ALL_NEW")
    assert values["CC_P2_M5_05_A0_IMAGEGEN_CALLS_EXECUTED"] == "0"
    assert values["CC_P2_M5_05_A0_ORDINALS_CONSUMED"] == "0"
    assert values["CC_P2_M5_05_A0_RAW_OUTPUTS_CREATED"] == "0"
    assert values["CC_P2_M5_05_A0_PRIVATE_ROOTS_CREATED"] == "0"
    assert values["CC_P2_M5_05_A0_PRIVATE_BYTES_CREATED_OR_READ"] == "0"
    assert values["FORMAL_E01_GENERATION_CALLS_EXECUTED"] == "1"
    assert values["FORMAL_E01_RAW_OUTPUTS_CREATED"] == "1"
    assert values["FORMAL_E01_PROVISIONAL_ACCEPTED_IDENTITIES"] == "0"
    assert values["FORMAL_CALLS_REMAINING"] == "31"
    assert values["FORMAL_RAW_CAPACITY_REMAINING"] == "31"
    assert values["GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "62"
    assert values["CAL_REQ_001_STATUS"] == "CONSUMED_FAILED_NO_RETRY"
    assert values["CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["QUESTIONBANK_GENERATION_POLICY_DIGEST"] == (_policy()["content_sha256"].upper())
    assert values["FORMAL_E01_STATUS"] == (
        "SUSPENDED_PENDING_CC05_A_EPOCH3_PRIVATE_V3_MATERIALIZATION"
    )
    assert values["P2_M5_TECHNICAL_GATE"] == "NOT_EVALUATED"
    assert values["P2_MVR_V1_RESULT"] == "NOT_EVALUATED"
    assert values["P2_M6_ENTRY"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert values["NEXT_READY_TASK"] == "CC-P2-M5-05-A_PRIVATE_POLICY_MATERIALIZATION"
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_CC05_A0_E01_PRIVATE_STATE_EPOCH3_ROLLOVER_TRUE_EOF",
    )
    acceptance_text = ACCEPTANCE_PATH.read_text(encoding="utf-8")
    execution_text = EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")
    assert acceptance_text.count(canonical[-1][1]) == 1
    assert execution_text.count(mirror[-1][1]) == 1


def test_cc05_a_redacted_evidence_is_exact_zero_generation_and_contains_no_locator() -> None:
    evidence = cast(
        dict[str, Any],
        json.loads(CC05_A_EVIDENCE_PATH.read_text(encoding="utf-8")),
    )

    assert set(evidence) == {
        "admission_rubric_sha256",
        "admission_rubric_version",
        "adult_age_assignment_counts",
        "adult_age_assignment_sha256",
        "assignment_ledger_sha256",
        "assignment_ledger_version",
        "atomic_write_flush_close_reread_digest",
        "bootstrap_sha256",
        "bootstrap_version",
        "cal_req_001_status",
        "cal_req_002_status",
        "create_mode",
        "decode_qa_screening_admission_in_cc05_a",
        "dependency_or_model_artifact_change",
        "detached_bootstrap_digest",
        "fixed_entrypoint_fresh_process_recovery",
        "formal_calls_remaining",
        "formal_e01_generation_calls_executed",
        "formal_e01_provisional_accepted_identities",
        "formal_e01_raw_outputs_created",
        "formal_e01_status",
        "formal_raw_capacity_remaining",
        "generation_specification_sha256",
        "generation_specification_version",
        "global_native_output_capacity_remaining",
        "image_bytes_read_in_cc05_a",
        "imagegen_calls_in_cc05_a",
        "next_ready_task_after_acceptance",
        "next_unused_formal_ordinal",
        "ordinals_consumed_in_cc05_a",
        "output_id",
        "output_ledger_sha256",
        "output_ledger_version",
        "p2_m5_technical_gate",
        "p2_m6_entry",
        "p2_mvr_v1_result",
        "policy_envelope_sha256",
        "policy_envelope_version",
        "private_prompt_or_locator_in_tracked_evidence",
        "private_receipt_id",
        "private_receipt_sha256",
        "private_registry_sha256",
        "private_registry_version",
        "private_root_containment",
        "private_root_count",
        "private_root_non_reparse",
        "production_geometry_approved",
        "production_provider_approved",
        "prompt_template_sha256",
        "prompt_template_version",
        "public_api_change",
        "public_assignment_semantics_sha256",
        "question_bank_release_authorized",
        "questionbank_generation_policy_digest",
        "raw_outputs_created_in_cc05_a",
        "real_user_facial_processing_authorized",
        "real_user_runtime_generation_calls",
        "request_ledger_sha256",
        "request_ledger_version",
        "schema_or_migration_change",
        "schema_version",
        "status",
        "task_id",
    }
    assert evidence["schema_version"] == ("mirror.p2-m5/CC05AEpoch3MaterializationEvidence/v1")
    assert evidence["task_id"] == "CC-P2-M5-05-A"
    assert evidence["status"] == ("LOCAL_PRIVATE_MATERIALIZATION_PASS_PENDING_TRACKED_GATES")
    assert re.fullmatch(r"P2M5-CC05A-E3-[0-9a-f]{32}", evidence["output_id"])
    assert evidence["private_receipt_id"] == f"{evidence['output_id']}-RECEIPT"
    assert evidence["private_root_count"] == 1
    assert evidence["create_mode"] == "CREATE_NEW_NO_OVERWRITE"
    assert evidence["private_root_containment"] == "PASS"
    assert evidence["private_root_non_reparse"] == "PASS"
    assert evidence["detached_bootstrap_digest"] == "PASS"
    assert evidence["atomic_write_flush_close_reread_digest"] == "PASS"
    assert evidence["fixed_entrypoint_fresh_process_recovery"] == "PASS"

    digest_fields = {
        "bootstrap_sha256",
        "private_registry_sha256",
        "generation_specification_sha256",
        "policy_envelope_sha256",
        "prompt_template_sha256",
        "admission_rubric_sha256",
        "assignment_ledger_sha256",
        "request_ledger_sha256",
        "output_ledger_sha256",
        "private_receipt_sha256",
        "public_assignment_semantics_sha256",
        "adult_age_assignment_sha256",
        "questionbank_generation_policy_digest",
    }
    assert all(
        isinstance(evidence[field], str) and re.fullmatch(r"[0-9a-f]{64}", evidence[field])
        for field in digest_fields
    )
    assert evidence["questionbank_generation_policy_digest"] == _policy()["content_sha256"]
    assert evidence["adult_age_assignment_counts"] == {
        "ADULT_18_19": 7,
        "ADULT_20_25": 24,
    }
    assert evidence["cal_req_001_status"] == "CONSUMED_FAILED_NO_RETRY"
    assert evidence["cal_req_002_status"] == "NOT_CONSUMED"
    assert evidence["next_unused_formal_ordinal"] == "CAL-REQ-002"
    assert evidence["formal_e01_generation_calls_executed"] == 1
    assert evidence["formal_e01_raw_outputs_created"] == 1
    assert evidence["formal_e01_provisional_accepted_identities"] == 0
    assert evidence["formal_calls_remaining"] == 31
    assert evidence["formal_raw_capacity_remaining"] == 31
    assert evidence["global_native_output_capacity_remaining"] == 62
    assert evidence["imagegen_calls_in_cc05_a"] == 0
    assert evidence["ordinals_consumed_in_cc05_a"] == 0
    assert evidence["raw_outputs_created_in_cc05_a"] == 0
    assert evidence["image_bytes_read_in_cc05_a"] == 0
    assert evidence["decode_qa_screening_admission_in_cc05_a"] == 0
    assert evidence["private_prompt_or_locator_in_tracked_evidence"] is False
    assert evidence["public_api_change"] is False
    assert evidence["schema_or_migration_change"] is False
    assert evidence["dependency_or_model_artifact_change"] is False
    assert evidence["question_bank_release_authorized"] is False
    assert evidence["production_provider_approved"] is False
    assert evidence["production_geometry_approved"] is False
    assert evidence["real_user_facial_processing_authorized"] is False
    assert evidence["real_user_runtime_generation_calls"] == 0
    assert evidence["p2_m5_technical_gate"] == "NOT_EVALUATED"
    assert evidence["p2_mvr_v1_result"] == "NOT_EVALUATED"
    assert evidence["p2_m6_entry"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert evidence["next_ready_task_after_acceptance"] == "EXECUTE_CAL_REQ_002"

    tracked = "\n".join(
        (
            CC05_A_EVIDENCE_PATH.read_text(encoding="utf-8"),
            CC05_A_EVIDENCE_DOC_PATH.read_text(encoding="utf-8"),
        )
    )
    assert ".local-storage" not in tracked
    assert "relative_private_locator" not in tracked
    assert "private_template_nonce" not in tracked
    assert "positive_segments" not in tracked
    assert "negative_segments" not in tracked
    assert "prompt_text" not in tracked
    assert "prompt_plaintext" not in tracked.lower()
    assert "seed_value" not in tracked
    assert "object_key" not in tracked
    assert "signed_url" not in tracked
    assert "provider_raw_payload" not in tracked.lower()
    assert "data:image/" not in tracked
    assert "C:\\" not in tracked
    assert "D:\\" not in tracked


def test_cc05_a_true_eof_overlay_is_complete_mirrored_and_binds_redacted_evidence() -> None:
    canonical = _last_cc05_a_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_a_key_block(EXECUTION_PROTOCOL_PATH)
    a0 = _last_cc05_a0_key_block(ACCEPTANCE_PATH)
    evidence = cast(
        dict[str, Any],
        json.loads(CC05_A_EVIDENCE_PATH.read_text(encoding="utf-8")),
    )

    assert canonical == mirror
    values = dict(canonical)
    assert len(canonical) == 317
    assert len(values) == len(canonical)
    assert len(a0) == 272
    assert {key for key, _ in a0} <= values.keys()
    a0_values = dict(a0)
    actual_a0_overrides = {
        key: values[key]
        for key, predecessor_value in a0_values.items()
        if values[key] != predecessor_value
    }
    assert len(_CC05_A_AUTHORIZED_A0_OVERRIDES) == 37
    assert actual_a0_overrides == _CC05_A_AUTHORIZED_A0_OVERRIDES
    assert {
        key: values[key] for key in a0_values.keys() - _CC05_A_AUTHORIZED_A0_OVERRIDES.keys()
    } == {key: a0_values[key] for key in a0_values.keys() - _CC05_A_AUTHORIZED_A0_OVERRIDES.keys()}
    assert values["P2_M5_R41"] == (
        "PASS_AT_762B03F52A9F23450C00F7F7FEFC977DB30AB128_RUN_33240395967"
    )
    assert values["CC_P2_M5_05_A0_STATUS"] == (
        "PASS_AT_762B03F52A9F23450C00F7F7FEFC977DB30AB128_RUN_33240395967"
    )
    assert values["CC_P2_M5_05_A_STATUS"] == (
        "PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["CC_P2_M5_05_A_OUTPUT_ID"] == evidence["output_id"]
    assert values["CC_P2_M5_05_A_PRIVATE_ROOTS_CREATED"] == "1"
    assert values["CC_P2_M5_05_A_CREATE_MODE"] == "CREATE_NEW_NO_OVERWRITE"
    assert values["CC_P2_M5_05_A_PRIVATE_EPOCH2_BYTES_READ"] == "0"
    assert values["CC_P2_M5_05_A_IMAGEGEN_CALLS_EXECUTED"] == "0"
    assert values["CC_P2_M5_05_A_ORDINALS_CONSUMED"] == "0"
    assert values["CC_P2_M5_05_A_RAW_OUTPUTS_CREATED"] == "0"
    assert values["CC_P2_M5_05_A_IMAGE_BYTES_READ"] == "0"
    assert values["CC_P2_M5_05_A_DECODE_QA_SCREENING_ADMISSION"] == "0"
    assert values["CC_P2_M5_05_A_PRIVATE_LOCATOR_IN_TRACKED_EVIDENCE"] == "FALSE"
    assert values["CC_P2_M5_05_A_PROMPT_PLAINTEXT_IN_TRACKED_EVIDENCE"] == "FALSE"
    assert values["CC_P2_M5_05_A_PRIVATE_DIGEST_INHERITANCE"] == "0"
    digest_bindings = {
        "CC_P2_M5_05_A_BOOTSTRAP_SHA256": "bootstrap_sha256",
        "CC_P2_M5_05_A_PRIVATE_REGISTRY_SHA256": "private_registry_sha256",
        "CC_P2_M5_05_A_GENERATION_SPECIFICATION_SHA256": ("generation_specification_sha256"),
        "CC_P2_M5_05_A_POLICY_ENVELOPE_SHA256": "policy_envelope_sha256",
        "CC_P2_M5_05_A_PRIVATE_PROMPT_TEMPLATE_SHA256": "prompt_template_sha256",
        "CC_P2_M5_05_A_ADMISSION_RUBRIC_SHA256": "admission_rubric_sha256",
        "CC_P2_M5_05_A_ASSIGNMENT_LEDGER_SHA256": "assignment_ledger_sha256",
        "CC_P2_M5_05_A_REQUEST_LEDGER_SHA256": "request_ledger_sha256",
        "CC_P2_M5_05_A_OUTPUT_LEDGER_SHA256": "output_ledger_sha256",
        "CC_P2_M5_05_A_PRIVATE_RECEIPT_SHA256": "private_receipt_sha256",
        "CC_P2_M5_05_A_PUBLIC_ASSIGNMENT_SEMANTICS_SHA256": ("public_assignment_semantics_sha256"),
        "CC_P2_M5_05_A_ADULT_AGE_ASSIGNMENT_SHA256": "adult_age_assignment_sha256",
    }
    assert len(digest_bindings) == 12
    assert {authority_key: values[authority_key] for authority_key in digest_bindings} == {
        authority_key: evidence[evidence_key].upper()
        for authority_key, evidence_key in digest_bindings.items()
    }
    assert values["CC_P2_M5_05_A_PRIVATE_RECEIPT_ID"] == (evidence["private_receipt_id"])
    assert (
        values["CC_P2_M5_05_A_REDACTED_EVIDENCE_SHA256"]
        == hashlib.sha256(CC05_A_EVIDENCE_PATH.read_bytes()).hexdigest().upper()
    )
    assert values["CC_P2_M5_05_A_ADULT_18_19_ASSIGNMENT_COUNT"] == "7"
    assert values["CC_P2_M5_05_A_ADULT_20_25_ASSIGNMENT_COUNT"] == "24"
    assert values["CC_P2_M5_05_A_CAL_REQ_001_STATUS"] == ("CONSUMED_FAILED_NO_RETRY")
    assert values["CC_P2_M5_05_A_CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["FORMAL_E01_GENERATION_CALLS_EXECUTED"] == "1"
    assert values["FORMAL_E01_RAW_OUTPUTS_CREATED"] == "1"
    assert values["FORMAL_E01_PROVISIONAL_ACCEPTED_IDENTITIES"] == "0"
    assert values["FORMAL_CALLS_REMAINING"] == "31"
    assert values["FORMAL_RAW_CAPACITY_REMAINING"] == "31"
    assert values["GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "62"
    assert values["E01_ACTIVE_EXECUTION_CUSTODY"] == (
        "E01_EPOCH_3_PRINCIPAL_PRIVATE_CUSTODY_ACTIVE_AFTER_CC05_A_ACCEPTANCE"
    )
    assert values["E01_EPOCH_3_STATUS"] == (
        "MATERIALIZED_RECOVERABLE_AND_BOUND_TO_V3_AFTER_CC05_A_ACCEPTANCE"
    )
    assert values["E01_EPOCH_3_FIXED_ENTRYPOINT_RECOVERY"] == "PASS"
    assert values["FORMAL_E01_STATUS"] == ("READY_TO_RESUME_AT_CAL_REQ_002_AFTER_CC05_A_ACCEPTANCE")
    assert values["CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["P2_M5_TECHNICAL_GATE"] == "NOT_EVALUATED"
    assert values["P2_MVR_V1_RESULT"] == "NOT_EVALUATED"
    assert values["P2_M6_ENTRY"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert values["NEXT_READY_TASK"] == "EXECUTE_CAL_REQ_002"
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_CC05_A_E01_EPOCH3_PRIVATE_POLICY_MATERIALIZATION_TRUE_EOF",
    )
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_CC05_A_E01_EPOCH3_PRIVATE_POLICY_MATERIALIZATION_TRUE_EOF",
    )


def test_r43_execution_transition_overlay_is_complete_mirrored_and_fail_closed() -> None:
    canonical = _last_r43_key_block(ACCEPTANCE_PATH)
    mirror = _last_r43_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_cc05_a_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)

    assert canonical == mirror
    assert len(canonical) == 345
    assert len(values) == len(canonical)
    assert len(predecessor) == 317
    assert set(predecessor_values) <= values.keys()

    expected_overrides = {
        "CC04_B_EXECUTION": "SUSPENDED_PENDING_R43_AND_R43_Q01_EXECUTION_OVERLAY_ACCEPTANCE",
        "CURRENT_AUTHORITY_TAIL_END": "P2_M5_R43_EPOCH3_EXECUTION_TRANSITION_REPAIR_TRUE_EOF",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_CC05_A_FOR_THE_COMPLETE_"
            "LISTED_KEYSET_ONLY_AFTER_R43_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_CHECKS_"
            "SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_AUTHORITY_VERSION": ("p2-m5-r43-epoch3-execution-transition-repair-eof/v1"),
        "CURRENT_STATE_KEY_COVERAGE": (
            "COMPLETE_CC05_A_PREDECESSOR_KEYSET_PLUS_R43_EXECUTION_TRANSITION_REPAIR_KEYS"
        ),
        "CURRENT_STATE_MIRROR_RULE": (
            "MUST_MATCH_CANONICAL_ACCEPTANCE_R43_KEY_SET_ORDER_AND_VALUES"
        ),
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_CC05_A_TRUE_EOF_REMAINS_CURRENT_UNTIL_R43_AUTHORITY_CONDITION_IS_SATISFIED"
        ),
        "EARLIER_STATUS_SECTIONS": (
            "PRESERVED_HISTORICAL_EVIDENCE_NON_CURRENT_FOR_THE_COMPLETE_LISTED_KEYSET_"
            "AFTER_R43_ACCEPTANCE"
        ),
        "FORMAL_E01_EXECUTION_AUTHORITY": (
            "NOT_EFFECTIVE_UNTIL_R43_AND_R43_Q01_REDACTED_EVIDENCE_ALL_GATES_AND_"
            "PRINCIPAL_ACCEPTANCE"
        ),
        "FORMAL_E01_STATUS": (
            "SUSPENDED_PENDING_R43_ACCEPTANCE_AND_PRIVATE_OVERLAY_MATERIALIZATION"
        ),
        "NEXT_READY_TASK": "P2_M5_R43_SAME_SHA_GATES",
        "P2_M5_NEXT_ACTION": (
            "COMPLETE_R43_SAME_SHA_GATES_THEN_R43_Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"
        ),
        "STOP_OUTCOME": (
            "CAL_REQ_002_NOT_DISPATCHED_PENDING_ACCEPTED_R43_EXECUTION_OVERLAY_AUTHORITY"
        ),
    }
    actual_overrides = {
        key: values[key]
        for key, predecessor_value in predecessor_values.items()
        if values[key] != predecessor_value
    }
    assert actual_overrides == expected_overrides
    assert {key: values[key] for key in predecessor_values.keys() - expected_overrides.keys()} == {
        key: predecessor_values[key]
        for key in predecessor_values.keys() - expected_overrides.keys()
    }

    additions = {
        "P2_M5_R43_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_"
            "CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R43_CONCURRENCY": "1",
        "P2_M5_R43_CONTROLLER_MODULE": (
            "services/api/src/mirror_api/synthetic_dataset/private_execution_overlay.py"
        ),
        "P2_M5_R43_CONTROLLER_SHA256_BINDING": ("COMPUTE_FROM_ACCEPTED_CANDIDATE_BYTES_AT_R43_Q01"),
        "P2_M5_R43_DECODE_QA_SCREENING_ADMISSION": "0",
        "P2_M5_R43_DEPENDENCY_MODEL_OR_WORKFLOW_CHANGE": "NONE",
        "P2_M5_R43_FAILURE_STATES": (
            "DISPATCH_FAILED_FINAL;OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
        ),
        "P2_M5_R43_GENESIS_MUTATION": "0",
        "P2_M5_R43_IMAGEGEN_CALLS_EXECUTED": "0",
        "P2_M5_R43_NEXT_PRIVATE_TASK": ("P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"),
        "P2_M5_R43_ORDINALS_CONSUMED": "0",
        "P2_M5_R43_OUTPUT_COUNT_ORDER": (
            "RETURNED_AND_RAW_COUNTERS_DURABLE_BEFORE_ANY_SOURCE_BYTE_INSPECTION"
        ),
        "P2_M5_R43_OVERLAY_MODEL": (
            "IMMUTABLE_CC05_A_GENESIS_PLUS_CREATE_NEW_HASH_CHAINED_EXECUTION_OVERLAY"
        ),
        "P2_M5_R43_PARENT_SHA": "40A239831985B76DD55788A4EDE6D98D60438F3D",
        "P2_M5_R43_POST_ACCEPTANCE_COMMIT_REQUIRED": "NO",
        "P2_M5_R43_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN": "0",
        "P2_M5_R43_PRIVATE_ROOTS_CREATED": "0",
        "P2_M5_R43_PUBLIC_API_CHANGE": "NONE",
        "P2_M5_R43_Q01_IMAGEGEN_CALLS": "0",
        "P2_M5_R43_Q01_ORDINALS_CONSUMED": "0",
        "P2_M5_R43_Q01_REDACTED_EVIDENCE_REQUIRED": ("YES_BEFORE_CAL_REQ_002_DISPATCH"),
        "P2_M5_R43_RAW_OUTPUTS_CREATED": "0",
        "P2_M5_R43_RECOVERY_MODEL": ("EXACT_RECEIPT_HANDLE_NO_LIST_GLOB_SEARCH_OR_LATEST_POINTER"),
        "P2_M5_R43_REGISTER_BEFORE_DECODE": "REQUIRED_AND_TESTED",
        "P2_M5_R43_RETRY": "0",
        "P2_M5_R43_SCHEMA_OR_MIGRATION_CHANGE": "NONE",
        "P2_M5_R43_STATE_MACHINE": (
            "READY_TO_DISPATCH_PREPARED_TO_DISPATCH_STARTED_CONSUMED_TO_OUTPUT_RETURNED_"
            "UNREGISTERED_TO_OUTPUT_REGISTERED_PRE_DECODE"
        ),
        "P2_M5_R43_STATUS": "PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE",
    }
    assert set(values) - set(predecessor_values) == set(additions)
    assert {key: values[key] for key in additions} == additions
    assert values["CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["FORMAL_E01_GENERATION_CALLS_EXECUTED"] == "1"
    assert values["FORMAL_E01_RAW_OUTPUTS_CREATED"] == "1"
    assert values["FORMAL_CALLS_REMAINING"] == "31"
    assert values["FORMAL_RAW_CAPACITY_REMAINING"] == "31"
    assert values["GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "62"
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_R43_EPOCH3_EXECUTION_TRANSITION_REPAIR_TRUE_EOF",
    )
    assert ACCEPTANCE_PATH.read_text(encoding="utf-8").rstrip().endswith(canonical[-1][1])
    assert EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8").rstrip().endswith(mirror[-1][1])

    tracked = "\n".join(
        (
            R43_REPAIR_PATH.read_text(encoding="utf-8"),
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-100_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-100_000:],
        )
    )
    assert ".local-storage" not in tracked
    assert "data:image/" not in tracked
    assert "private_template_nonce" not in tracked
    assert "positive_segments" not in tracked
    assert "negative_segments" not in tracked
    assert "provider_raw_payload" not in tracked.lower()
    assert "C:\\" not in tracked
    assert "D:\\" not in tracked
