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
ACCEPTANCE_PATH = ROOT / "docs" / "operations" / "P2_M5_ACCEPTANCE.md"
EXECUTION_PROTOCOL_PATH = ROOT / "docs" / "operations" / "P2_M5_EXECUTION_PROTOCOL.md"


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


def _last_cc05_key_block(path: Path) -> list[tuple[str, str]]:
    marker = (
        "CURRENT_STATE_AUTHORITY_VERSION: "
        "p2-m5-cc05-formal-questionbank-generation-policy-v3-eof/v1"
    )
    text = path.read_text(encoding="utf-8")
    start = text.rfind(marker)
    assert start >= 0
    pairs: list[tuple[str, str]] = []
    for line in text[start:].splitlines():
        if ": " in line and not line.startswith("#"):
            key, value = line.split(": ", maxsplit=1)
            pairs.append((key, value))
    return pairs


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
        transition["baseline_openapi_canonical_sha256"]
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
