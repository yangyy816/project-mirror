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
R44_REPAIR_PATH = ROOT / "docs" / "operations" / "P2_M5_R44_R43_GATE_CLOSURE_REPAIR.md"
R45_REPAIR_PATH = ROOT / "docs" / "operations" / "P2_M5_R45_R44_GATE_CLOSURE_REPAIR.md"
R46_REPAIR_PATH = ROOT / "docs" / "operations" / "P2_M5_R46_R45_CI_PLATFORM_TYPING_REPAIR.md"
CC05_B_CHANGE_CONTROL_PATH = (
    ROOT / "docs" / "operations" / "P2_M5_CC05_B_EPOCH3_EVIDENCE_LOCATION_LOSS.md"
)
CC05_C0_CHANGE_CONTROL_PATH = (
    ROOT
    / "docs"
    / "operations"
    / "P2_M5_CC05_C0_E01_PRIVATE_STATE_EPOCH_4_ROLLOVER_CHANGE_CONTROL.md"
)
CC05_C_EVIDENCE_PATH = (
    ROOT
    / "docs"
    / "operations"
    / "P2_M5_CC05_C_E01_PRIVATE_POLICY_MATERIALIZATION_REDACTED_EVIDENCE.json"
)
CC05_C_EVIDENCE_DOC_PATH = (
    ROOT / "docs" / "operations" / "P2_M5_CC05_C_E01_PRIVATE_POLICY_MATERIALIZATION_EVIDENCE.md"
)
R43_Q01_EVIDENCE_PATH = (
    ROOT
    / "docs"
    / "operations"
    / "P2_M5_R43_Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION_REDACTED_EVIDENCE.json"
)
R43_Q01_EVIDENCE_DOC_PATH = (
    ROOT
    / "docs"
    / "operations"
    / "P2_M5_R43_Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION_EVIDENCE.md"
)
D0_ADR_PATH = (
    ROOT / "docs" / "adr" / "ADR-053-project-local-private-custody-and-imagegen-output-bridge.md"
)
D0_CHANGE_CONTROL_PATH = (
    ROOT / "docs" / "operations" / "P2_M5_CC05_D0_IMAGEGEN_OUTPUT_BRIDGE_CHANGE_CONTROL.md"
)
R50_CONTRACT_PATH = ROOT / "docs" / "operations" / "P2_M5_R50_IMAGEGEN_OUTPUT_BRIDGE_CONTRACT.md"
ACCEPTANCE_PATH = ROOT / "docs" / "operations" / "P2_M5_ACCEPTANCE.md"
EXECUTION_PROTOCOL_PATH = ROOT / "docs" / "operations" / "P2_M5_EXECUTION_PROTOCOL.md"
R52_CONTRACT_PATH = (
    ROOT / "docs" / "operations" / "P2_M5_R52_PRIVATE_IMAGEGEN_TRANSPORT_RUNNER_CONTRACT.md"
)
R54_CONTRACT_PATH = (
    ROOT / "docs" / "operations" / "P2_M5_R54_ROLLOVER_EMPTY_DIRECTORY_INTEGRITY_CONTRACT.md"
)

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


def _last_r44_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r44-r43-gate-closure-repair-eof/v1",
        sentinel="P2_M5_R44_R43_GATE_CLOSURE_REPAIR_TRUE_EOF",
    )


def _last_r45_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r45-r44-gate-closure-repair-eof/v1",
        sentinel="P2_M5_R45_R44_GATE_CLOSURE_REPAIR_TRUE_EOF",
    )


def _last_r46_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r46-r45-ci-platform-typing-repair-eof/v1",
        sentinel="P2_M5_R46_R45_CI_PLATFORM_TYPING_REPAIR_TRUE_EOF",
    )


def _last_cc05_b_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-b-epoch3-evidence-location-loss-eof/v1",
        sentinel="P2_M5_CC05_B_EPOCH3_EVIDENCE_LOCATION_LOSS_TRUE_EOF",
    )


def _last_cc05_c0_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-c0-e01-private-state-epoch4-rollover-eof/v1",
        sentinel="P2_M5_CC05_C0_E01_PRIVATE_STATE_EPOCH4_ROLLOVER_TRUE_EOF",
    )


def _last_cc05_c_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-c-e01-epoch4-private-materialization-eof/v1",
        sentinel="P2_M5_CC05_C_E01_EPOCH4_PRIVATE_POLICY_MATERIALIZATION_TRUE_EOF",
    )


def _last_r49_q01_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r49-q01-post-acceptance-next-ready-task-repair-eof/v1",
        sentinel="P2_M5_R49_Q01_POST_ACCEPTANCE_NEXT_READY_TASK_AUTHORITY_REPAIR_TRUE_EOF",
    )


def _last_cc05_d0_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-d0-built-in-output-contract-recovery-eof/v1",
        sentinel="P2_M5_CC05_D0_BUILT_IN_OUTPUT_CONTRACT_RECOVERY_TRUE_EOF",
    )


def _last_cc05_d0_acceptance_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-cc05-d0-principal-acceptance-checkpoint-eof/v1",
        sentinel="P2_M5_CC05_D0_PRINCIPAL_ACCEPTANCE_CHECKPOINT_TRUE_EOF",
    )


def _last_r50_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r50-imagegen-data-url-custody-bridge-eof/v1",
        sentinel="P2_M5_R50_IMAGEGEN_DATA_URL_CUSTODY_BRIDGE_TRUE_EOF",
    )


def _last_r51_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r51-r50-post-acceptance-successor-authority-eof/v1",
        sentinel="P2_M5_R51_R50_POST_ACCEPTANCE_SUCCESSOR_AUTHORITY_REPAIR_TRUE_EOF",
    )


def _last_r52_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r52-private-imagegen-no-echo-transport-eof/v1",
        sentinel="P2_M5_R52_PRIVATE_IMAGEGEN_NO_ECHO_TRANSPORT_TRUE_EOF",
    )


def _last_r53_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r53-cal-req-004-ready-rollover-eof/v1",
        sentinel="P2_M5_R53_CAL_REQ_004_READY_ROLLOVER_TRUE_EOF",
    )


def _last_r54_key_block(path: Path) -> list[tuple[str, str]]:
    return _last_key_block(
        path,
        authority_version="p2-m5-r54-rollover-empty-directory-integrity-eof/v1",
        sentinel="P2_M5_R54_ROLLOVER_EMPTY_DIRECTORY_INTEGRITY_TRUE_EOF",
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


def test_r44_execution_transition_overlay_is_complete_mirrored_and_fail_closed() -> None:
    canonical = _last_r44_key_block(ACCEPTANCE_PATH)
    mirror = _last_r44_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_cc05_a_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)

    assert canonical == mirror
    assert len(canonical) == 375
    assert len(values) == len(canonical)
    assert len(predecessor) == 317
    assert set(predecessor_values) <= values.keys()

    expected_overrides = {
        "CC04_B_EXECUTION": "SUSPENDED_PENDING_R44_AND_R43_Q01_EXECUTION_OVERLAY_ACCEPTANCE",
        "CURRENT_AUTHORITY_TAIL_END": "P2_M5_R44_R43_GATE_CLOSURE_REPAIR_TRUE_EOF",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_CC05_A_FOR_THE_COMPLETE_"
            "LISTED_KEYSET_ONLY_AFTER_R44_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_CHECKS_"
            "SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_AUTHORITY_VERSION": ("p2-m5-r44-r43-gate-closure-repair-eof/v1"),
        "CURRENT_STATE_KEY_COVERAGE": (
            "COMPLETE_CC05_A_PREDECESSOR_KEYSET_PLUS_R43_AND_R44_EXECUTION_TRANSITION_REPAIR_KEYS"
        ),
        "CURRENT_STATE_MIRROR_RULE": (
            "MUST_MATCH_CANONICAL_ACCEPTANCE_R44_KEY_SET_ORDER_AND_VALUES"
        ),
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_CC05_A_TRUE_EOF_REMAINS_CURRENT_UNTIL_R44_AUTHORITY_CONDITION_IS_SATISFIED"
        ),
        "EARLIER_STATUS_SECTIONS": (
            "PRESERVED_HISTORICAL_EVIDENCE_NON_CURRENT_FOR_THE_COMPLETE_LISTED_KEYSET_"
            "AFTER_R44_ACCEPTANCE"
        ),
        "FORMAL_E01_EXECUTION_AUTHORITY": (
            "NOT_EFFECTIVE_UNTIL_R44_AND_R43_Q01_REDACTED_EVIDENCE_ALL_GATES_AND_"
            "PRINCIPAL_ACCEPTANCE"
        ),
        "FORMAL_E01_STATUS": (
            "SUSPENDED_PENDING_R44_ACCEPTANCE_AND_PRIVATE_OVERLAY_MATERIALIZATION"
        ),
        "NEXT_READY_TASK": "P2_M5_R44_SAME_SHA_GATES",
        "P2_M5_NEXT_ACTION": (
            "COMPLETE_R44_SAME_SHA_GATES_THEN_R43_Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"
        ),
        "STOP_OUTCOME": (
            "CAL_REQ_002_NOT_DISPATCHED_PENDING_ACCEPTED_R44_EXECUTION_OVERLAY_AUTHORITY"
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
            "EFFECTIVE_ONLY_WITH_R44_AFTER_R44_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_"
            "CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
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
        "P2_M5_R43_RECOVERY_MODEL": (
            "EXACT_RECEIPT_HANDLE_CREATE_OR_VERIFY_EXACT_REPLAY_NO_LIST_GLOB_SEARCH_OR_"
            "LATEST_POINTER"
        ),
        "P2_M5_R43_REGISTER_BEFORE_DECODE": "REQUIRED_AND_TESTED",
        "P2_M5_R43_RETRY": "0",
        "P2_M5_R43_SCHEMA_OR_MIGRATION_CHANGE": "NONE",
        "P2_M5_R43_STATE_MACHINE": (
            "READY_TO_DISPATCH_PREPARED_TO_DISPATCH_STARTED_CONSUMED_TO_OUTPUT_RETURNED_"
            "UNREGISTERED_TO_OUTPUT_RETURNED_RECEIPT_BOUND_TO_OUTPUT_REGISTRATION_ATTEMPT_"
            "BOUND_TO_OUTPUT_REGISTERED_PRE_DECODE"
        ),
        "P2_M5_R43_STATUS": (
            "REJECTED_AT_8BECAE2_SECURITY_AND_SOL_HIGH_FINDINGS_REPAIRED_ONLY_WITH_R44_ACCEPTANCE"
        ),
        "P2_M5_R44_STATUS": ("PASS_AFTER_R44_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"),
        "P2_M5_R44_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_AFTER_R44_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_"
            "CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R44_POST_ACCEPTANCE_COMMIT_REQUIRED": "NO",
        "P2_M5_R44_PARENT_SHA": "8BECAE2C9F81794B0E7AE0D46E4DF155CE072B64",
        "P2_M5_R44_REJECTED_CANDIDATE_SHA": ("8BECAE2C9F81794B0E7AE0D46E4DF155CE072B64"),
        "P2_M5_R44_SECURITY_REVIEW_AT_PARENT": "FAIL_TWO_HIGH_FINDINGS",
        "P2_M5_R44_SOL_HIGH_REVIEW_AT_PARENT": "FAIL_TWO_BLOCKING_FINDINGS",
        "P2_M5_R44_FINDINGS": (
            "RECEIPT_SOURCE_BINDING;AUTOMATIC_REGISTRATION_HARD_STOP;PARTIAL_TRANSITION_"
            "FRESH_PROCESS_RECOVERY;REQUEST_ORDINAL_PLACEHOLDER"
        ),
        "P2_M5_R44_TRANSITION_RECOVERY": (
            "EXACT_PREDECESSOR_SAME_INPUT_CREATE_OR_VERIFY_EVENT_STATE_RECEIPT"
        ),
        "P2_M5_R44_EXISTING_CONTENT_RULE": (
            "BYTE_EXACT_CANONICAL_MATCH_OR_HARD_CONFLICT_NO_OVERWRITE"
        ),
        "P2_M5_R44_RETURNED_COUNTER_ORDER": (
            "COUNTERS_COMMITTED_BEFORE_OUTPUT_HINT_DIGEST_OR_SOURCE_ACCESS"
        ),
        "P2_M5_R44_OUTPUT_HINT_BINDING": (
            "ACTION_ORDINAL_PREDECLARED_OUTPUT_ID_AND_EXACT_HINT_SHA256"
        ),
        "P2_M5_R44_REGISTRATION_ATTEMPT": (
            "SINGLE_ATTEMPT_DURABLY_BOUND_BEFORE_PATH_VALIDATION_OR_BYTE_READ"
        ),
        "P2_M5_R44_REGISTRATION_FAILURE": (
            "AUTOMATIC_OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE_TERMINAL"
        ),
        "P2_M5_R44_SOURCE_PATH_SELECTION": (
            "DERIVED_ONLY_FROM_BOUND_EXACT_PRINCIPAL_IMAGEGEN_OUTPUT_HINT"
        ),
        "P2_M5_R44_PROMPT_PLACEHOLDER": "REQUEST_ORDINAL_INCLUDED_AND_TESTED",
        "P2_M5_R44_RETRY": "0",
        "P2_M5_R44_CONCURRENCY": "1",
        "P2_M5_R44_IMAGEGEN_CALLS_EXECUTED": "0",
        "P2_M5_R44_ORDINALS_CONSUMED": "0",
        "P2_M5_R44_RAW_OUTPUTS_CREATED": "0",
        "P2_M5_R44_PRIVATE_ROOTS_CREATED": "0",
        "P2_M5_R44_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN": "0",
        "P2_M5_R44_PUBLIC_API_CHANGE": "NONE",
        "P2_M5_R44_SCHEMA_OR_MIGRATION_CHANGE": "NONE",
        "P2_M5_R44_DEPENDENCY_MODEL_OR_WORKFLOW_CHANGE": "NONE",
        "P2_M5_R44_NEXT_PRIVATE_TASK": ("P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"),
        "P2_M5_R44_Q01_IMAGEGEN_CALLS": "0",
        "P2_M5_R44_Q01_ORDINALS_CONSUMED": "0",
        "P2_M5_R44_Q01_REDACTED_EVIDENCE_REQUIRED": ("YES_BEFORE_CAL_REQ_002_DISPATCH"),
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
        "P2_M5_R44_R43_GATE_CLOSURE_REPAIR_TRUE_EOF",
    )
    tracked = "\n".join(
        (
            R43_REPAIR_PATH.read_text(encoding="utf-8"),
            R44_REPAIR_PATH.read_text(encoding="utf-8"),
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


def test_cc05_c0_epoch4_rollover_is_complete_mirrored_zero_generation_and_fail_closed() -> None:
    canonical = _last_cc05_c0_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_c0_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_cc05_b_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)

    assert canonical == mirror
    assert len(canonical) == len(values) == 532
    assert len(predecessor) == len(predecessor_values) == 471
    assert set(predecessor_values) <= values.keys()
    changed_keys = {
        "CURRENT_STATE_AUTHORITY_VERSION",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE",
        "CURRENT_STATE_MIRROR_RULE",
        "EARLIER_STATUS_SECTIONS",
        "CC04_B_E01",
        "CC04_B_EXECUTION",
        "E01_PRIVATE_STATE_EPOCH",
        "DURABLE_BOOTSTRAP",
        "PRIVATE_REGISTRY_VERSION",
        "GENERATION_SPECIFICATION_VERSION",
        "ASSIGNMENT_LEDGER_VERSION",
        "REQUEST_LEDGER_VERSION",
        "OUTPUT_LEDGER_VERSION",
        "GENERATION_SPECIFICATION_EFFECTIVE_RANGE",
        "EFFECTIVE_ORDINAL_RANGE",
        "FORMAL_E01_STATUS",
        "FORMAL_E01_EXECUTION_AUTHORITY",
        "CURRENT_STATE_PRECONDITION_FALLBACK",
        "E01_ACTIVE_EXECUTION_CUSTODY",
        "E01_PROSPECTIVE_PRIVATE_STATE_EPOCH",
        "E01_EPOCH_3_STATUS",
        "P2_M5_NEXT_ACTION",
        "NEXT_READY_TASK",
        "CURRENT_STATE_KEY_COVERAGE",
        "STOP_OUTCOME",
        "CC_P2_M5_05_B_STATUS",
        "CC_P2_M5_05_B_AUTHORITY_CONDITION",
        "CURRENT_AUTHORITY_TAIL_END",
    }
    assert changed_keys == {
        key
        for key, predecessor_value in predecessor_values.items()
        if values[key] != predecessor_value
    }
    added_keys = {
        "CC_P2_M5_05_B_CANDIDATE_SHA",
        "CC_P2_M5_05_B_CI_RUN",
        "CC_P2_M5_05_B_CI_RESULTS",
        "CC_P2_M5_05_B_ARTIFACT_INSPECTION",
        "CC_P2_M5_05_B_FULL_PYTHON",
        "CC_P2_M5_05_B_FROZEN_REGRESSION",
        "CC_P2_M5_05_B_GITLEAKS",
        "CC_P2_M5_05_B_BROWSER_INTEGRATION",
        "CC_P2_M5_05_B_SECURITY_REVIEW",
        "CC_P2_M5_05_B_SOL_HIGH_FINAL_REVIEW",
        "CC_P2_M5_05_B_PRINCIPAL_ACCEPTANCE",
        "CC_P2_M5_05_B_RESUME_PREDICATE_STATUS",
        "CC_P2_M5_05_C0_STATUS",
        "CC_P2_M5_05_C0_AUTHORITY_CONDITION",
        "CC_P2_M5_05_C0_POST_ACCEPTANCE_COMMIT_REQUIRED",
        "CC_P2_M5_05_C0_OWNER_AUTHORITY",
        "CC_P2_M5_05_C0_PREDECESSOR",
        "CC_P2_M5_05_C0_CHANGE_CLASS",
        "CC_P2_M5_05_C0_CC05_B_RESUME_PREDICATE",
        "CC_P2_M5_05_C0_SINGLE_SUCCESSOR",
        "CC_P2_M5_05_C0_IMAGEGEN_CALLS_EXECUTED",
        "CC_P2_M5_05_C0_ORDINALS_CONSUMED",
        "CC_P2_M5_05_C0_RAW_OUTPUTS_CREATED",
        "CC_P2_M5_05_C0_PRIVATE_ROOTS_CREATED",
        "CC_P2_M5_05_C0_PRIVATE_BYTES_CREATED_READ_OR_COPIED",
        "CC_P2_M5_05_C0_PROMPT_POLICY_RUBRIC_MATERIALIZATION",
        "CC_P2_M5_05_C0_DECODE_QA_SCREENING_ADMISSION",
        "E01_EPOCH_3_EXECUTION_CUSTODY",
        "E01_EPOCH_3_HISTORICAL_EVIDENCE",
        "E01_EPOCH_3_RECOVERY",
        "E01_EPOCH_3_REUSE",
        "E01_EPOCH_3_PRIVATE_LOCATOR",
        "E01_EPOCH_3_PRIVATE_REGISTRY_LOCATOR",
        "E01_EPOCH_3_GENERATION_SPECIFICATION_LOCATOR",
        "E01_EPOCH_3_ASSIGNMENT_LEDGER_LOCATOR",
        "E01_EPOCH_3_CLEANUP_STATUS",
        "E01_EPOCH_3_BYTES_ABSENCE_CLAIM",
        "E01_EPOCH_3_PRIVATE_DIGEST_REUSE",
        "E01_EPOCH_3_PRIVATE_BYTES_READ_OR_COPIED_IN_C0",
        "E01_EPOCH_4_STATUS",
        "E01_EPOCH_4_CREATE_MODE",
        "E01_EPOCH_4_AUTHORIZED_ROOT_COUNT",
        "E01_EPOCH_4_PRIVATE_STATE_CREATED_IN_C0",
        "E01_EPOCH_4_PRIVATE_ROOTS_CREATED_IN_C0",
        "E01_EPOCH_4_PROMPT_POLICY_RUBRIC_MATERIALIZED_IN_C0",
        "E01_EPOCH_4_IMAGEGEN_CALLS_EXECUTED_IN_C0",
        "E01_EPOCH_4_ORDINALS_CONSUMED_IN_C0",
        "E01_EPOCH_4_RAW_OUTPUTS_CREATED_IN_C0",
        "E01_EPOCH_4_IMAGE_BYTES_READ_IN_C0",
        "E01_EPOCH_4_DECODE_QA_SCREENING_ADMISSION_IN_C0",
        "E01_EPOCH_4_REQUIRED_PRIVATE_VERSION_SET",
        "E01_EPOCH_4_PRIVATE_DIGEST_INHERITANCE",
        "E01_EPOCH_4_MATERIALIZATION_TASK",
        "E01_EPOCH_4_MATERIALIZATION_PRECONDITION",
        "E01_EPOCH_4_MATERIALIZATION_OUTPUT_REQUIRED",
        "E01_EPOCH_4_RESOURCE_LEDGER",
        "E01_EPOCH_4_CAL_REQ_001_STATUS",
        "E01_EPOCH_4_CAL_REQ_002_STATUS",
        "E01_EPOCH_4_FORMAL_CALLS_REMAINING",
        "E01_EPOCH_4_FORMAL_RAW_CAPACITY_REMAINING",
        "E01_EPOCH_4_GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING",
    }
    assert len(added_keys) == 61
    assert set(values) - set(predecessor_values) == added_keys

    assert values["CC_P2_M5_05_B_STATUS"] == (
        "TASK_ACCEPTED_AT_40F7C6BEE88196E8730F8DF1A521C46775B77F5C_RUN_33251230684"
    )
    assert values["CC_P2_M5_05_B_CI_RESULTS"] == (
        "QUALITY_AND_INTEGRATION_PASS;SECRET_SCAN_PASS;DOCKER_VALIDATION_PASS"
    )
    assert values["CC_P2_M5_05_B_ARTIFACT_INSPECTION"] == (
        "PASS_8_FAMILIES_11_FILES_EXACT_SHA_BOUND_UNEXPIRED"
    )
    assert values["CC_P2_M5_05_C0_STATUS"] == (
        "PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["CC_P2_M5_05_C0_CC05_B_RESUME_PREDICATE"] == (
        "NOT_SATISFIED_C0_CREATES_NO_RECOVERABLE_HANDLE"
    )
    assert values["E01_EPOCH_3_EXECUTION_CUSTODY"] == (
        "RETIRED_EVIDENCE_LOCATION_LOST_AFTER_CC05_B_ACCEPTANCE"
    )
    assert values["E01_EPOCH_3_RECOVERY"] == (
        "ABANDONED_NO_SCAN_NO_GUESS_NO_COPY_NO_RECONSTRUCTION"
    )
    assert values["E01_EPOCH_4_STATUS"] == (
        "PROSPECTIVE_AUTHORIZED_NOT_CREATED_AFTER_CC05_C0_ACCEPTANCE"
    )
    assert values["E01_ACTIVE_EXECUTION_CUSTODY"] == ("NONE_EPOCH3_RETIRED_EPOCH4_NOT_CREATED")
    assert values["CC_P2_M5_05_C0_IMAGEGEN_CALLS_EXECUTED"] == "0"
    assert values["CC_P2_M5_05_C0_ORDINALS_CONSUMED"] == "0"
    assert values["CC_P2_M5_05_C0_RAW_OUTPUTS_CREATED"] == "0"
    assert values["CC_P2_M5_05_C0_PRIVATE_ROOTS_CREATED"] == "0"
    assert values["CC_P2_M5_05_C0_PRIVATE_BYTES_CREATED_READ_OR_COPIED"] == "0"
    assert values["CC_P2_M5_05_C0_PROMPT_POLICY_RUBRIC_MATERIALIZATION"] == "0"
    assert values["CC_P2_M5_05_C0_DECODE_QA_SCREENING_ADMISSION"] == "0"
    assert values["E01_EPOCH_4_PRIVATE_STATE_CREATED_IN_C0"] == "0"
    assert values["E01_EPOCH_4_PRIVATE_ROOTS_CREATED_IN_C0"] == "0"
    assert values["E01_EPOCH_4_PROMPT_POLICY_RUBRIC_MATERIALIZED_IN_C0"] == "0"
    assert values["E01_EPOCH_4_IMAGEGEN_CALLS_EXECUTED_IN_C0"] == "0"
    assert values["E01_EPOCH_4_ORDINALS_CONSUMED_IN_C0"] == "0"
    assert values["E01_EPOCH_4_RAW_OUTPUTS_CREATED_IN_C0"] == "0"
    assert values["E01_EPOCH_4_IMAGE_BYTES_READ_IN_C0"] == "0"
    assert values["E01_EPOCH_4_DECODE_QA_SCREENING_ADMISSION_IN_C0"] == "0"
    assert values["CAL_REQ_001_STATUS"] == "CONSUMED_FAILED_NO_RETRY"
    assert values["CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["FORMAL_E01_GENERATION_CALLS_EXECUTED"] == "1"
    assert values["FORMAL_E01_RAW_OUTPUTS_CREATED"] == "1"
    assert values["FORMAL_CALLS_REMAINING"] == "31"
    assert values["FORMAL_RAW_CAPACITY_REMAINING"] == "31"
    assert values["GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "62"
    successor_task = "CC-P2-M5-05-C_PRIVATE_POLICY_MATERIALIZATION"
    assert values["NEXT_READY_TASK"] == successor_task
    assert values["CC_P2_M5_05_C0_SINGLE_SUCCESSOR"] == successor_task
    assert values["E01_EPOCH_4_MATERIALIZATION_TASK"] == successor_task
    assert values["P2_M5_TECHNICAL_GATE"] == "NOT_EVALUATED"
    assert values["P2_MVR_V1_RESULT"] == "NOT_EVALUATED"
    assert values["P2_M6_ENTRY"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_CC05_C0_E01_PRIVATE_STATE_EPOCH4_ROLLOVER_TRUE_EOF",
    )
    assert ACCEPTANCE_PATH.read_text(encoding="utf-8").count(canonical[-1][1]) == 1
    assert EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8").count(mirror[-1][1]) == 1

    tracked = "\n".join(
        (
            CC05_C0_CHANGE_CONTROL_PATH.read_text(encoding="utf-8"),
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-225_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-225_000:],
        )
    )
    assert "EVIDENCE_LOCATION_LOST" in tracked
    assert "CAL-REQ-002: NOT_CONSUMED" in tracked
    assert ".private-handoff" not in tracked
    assert ".local-storage" not in tracked
    assert "data:image/" not in tracked
    assert "provider_raw_payload" not in tracked.lower()
    assert "C:\\" not in tracked
    assert "D:\\" not in tracked


def test_cc05_c_redacted_evidence_is_exact_zero_generation_and_contains_no_locator() -> None:
    evidence = cast(
        dict[str, Any],
        json.loads(CC05_C_EVIDENCE_PATH.read_text(encoding="utf-8")),
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
        "decode_qa_screening_admission_in_cc05_c",
        "dependency_or_model_artifact_change",
        "detached_bootstrap_digest",
        "epoch3_private_bytes_or_digests_read_copied_reused",
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
        "image_bytes_read_in_cc05_c",
        "imagegen_calls_in_cc05_c",
        "next_ready_task_after_acceptance",
        "next_unused_formal_ordinal",
        "ordinals_consumed_in_cc05_c",
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
        "prompt_render_field_validation",
        "prompt_render_fields",
        "public_api_change",
        "public_assignment_semantics_sha256",
        "question_bank_release_authorized",
        "questionbank_generation_policy_digest",
        "raw_outputs_created_in_cc05_c",
        "real_user_facial_processing_authorized",
        "real_user_runtime_generation_calls",
        "request_ledger_sha256",
        "request_ledger_version",
        "schema_or_migration_change",
        "schema_version",
        "status",
        "task_id",
    }
    assert evidence["schema_version"] == ("mirror.p2-m5/CC05CEpoch4MaterializationEvidence/v1")
    assert evidence["task_id"] == "CC-P2-M5-05-C"
    assert evidence["status"] == ("LOCAL_PRIVATE_MATERIALIZATION_PASS_PENDING_TRACKED_GATES")
    assert re.fullmatch(r"P2M5-CC05C-E4-[0-9a-f]{32}", evidence["output_id"])
    assert evidence["private_receipt_id"] == f"{evidence['output_id']}-RECEIPT"
    assert evidence["private_root_count"] == 1
    assert evidence["create_mode"] == "CREATE_NEW_NO_OVERWRITE"
    assert evidence["private_root_containment"] == "PASS"
    assert evidence["private_root_non_reparse"] == "PASS"
    assert evidence["detached_bootstrap_digest"] == "PASS"
    assert evidence["atomic_write_flush_close_reread_digest"] == "PASS"
    assert evidence["fixed_entrypoint_fresh_process_recovery"] == "PASS"
    assert evidence["prompt_render_fields"] == [
        "REQUEST_ORDINAL",
        "DECLARED_AGE_BAND",
        "MORPHOLOGY_DESCRIPTOR",
        "STYLE_DESCRIPTOR",
    ]
    assert evidence["prompt_render_field_validation"] == (
        "PASS_EXACT_FOUR_NO_COMPOSITE_NO_FORMAT_SPEC"
    )

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
    assert evidence["public_assignment_semantics_sha256"] == (
        "39f7cda65a92e6be5c05e97b1ad49de4da608de227ee664d9f2407cd40d56f78"
    )
    assert evidence["adult_age_assignment_sha256"] != (
        "f966470c4ff3f79d9417af95549fc020e95847249502e41dccfffa53cb5c9b51"
    )
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
    assert evidence["imagegen_calls_in_cc05_c"] == 0
    assert evidence["ordinals_consumed_in_cc05_c"] == 0
    assert evidence["raw_outputs_created_in_cc05_c"] == 0
    assert evidence["image_bytes_read_in_cc05_c"] == 0
    assert evidence["decode_qa_screening_admission_in_cc05_c"] == 0
    assert evidence["epoch3_private_bytes_or_digests_read_copied_reused"] == 0
    assert evidence["private_prompt_or_locator_in_tracked_evidence"] is False
    for field in (
        "public_api_change",
        "schema_or_migration_change",
        "dependency_or_model_artifact_change",
        "question_bank_release_authorized",
        "production_provider_approved",
        "production_geometry_approved",
        "real_user_facial_processing_authorized",
    ):
        assert evidence[field] is False
    assert evidence["real_user_runtime_generation_calls"] == 0
    assert evidence["p2_m5_technical_gate"] == "NOT_EVALUATED"
    assert evidence["p2_mvr_v1_result"] == "NOT_EVALUATED"
    assert evidence["p2_m6_entry"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert evidence["next_ready_task_after_acceptance"] == (
        "P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"
    )

    tracked = "\n".join(
        (
            CC05_C_EVIDENCE_PATH.read_text(encoding="utf-8"),
            CC05_C_EVIDENCE_DOC_PATH.read_text(encoding="utf-8"),
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


def test_cc05_c_true_eof_overlay_is_complete_mirrored_and_binds_redacted_evidence() -> None:
    canonical = _last_cc05_c_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_c_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_cc05_c0_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)
    evidence = cast(
        dict[str, Any],
        json.loads(CC05_C_EVIDENCE_PATH.read_text(encoding="utf-8")),
    )

    assert canonical == mirror
    assert len(canonical) == len(values) == 610
    assert len(predecessor) == len(predecessor_values) == 532
    assert set(predecessor_values) <= values.keys()
    changed_keys = {
        "CURRENT_STATE_AUTHORITY_VERSION",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE",
        "CURRENT_STATE_MIRROR_RULE",
        "EARLIER_STATUS_SECTIONS",
        "CC04_B_E01",
        "CC04_B_EXECUTION",
        "E01_PRIVATE_STATE_EPOCH",
        "DURABLE_BOOTSTRAP",
        "PRIVATE_REGISTRY_VERSION",
        "GENERATION_SPECIFICATION_VERSION",
        "ASSIGNMENT_LEDGER_VERSION",
        "REQUEST_LEDGER_VERSION",
        "OUTPUT_LEDGER_VERSION",
        "GENERATION_SPECIFICATION_EFFECTIVE_RANGE",
        "EFFECTIVE_ORDINAL_RANGE",
        "FORMAL_E01_STATUS",
        "FORMAL_E01_EXECUTION_AUTHORITY",
        "CURRENT_STATE_PRECONDITION_FALLBACK",
        "E01_ACTIVE_EXECUTION_CUSTODY",
        "E01_PROSPECTIVE_PRIVATE_STATE_EPOCH",
        "P2_M5_NEXT_ACTION",
        "NEXT_READY_TASK",
        "CURRENT_STATE_KEY_COVERAGE",
        "STOP_OUTCOME",
        "CC_P2_M5_05_B_RESUME_PREDICATE_STATUS",
        "CC_P2_M5_05_C0_STATUS",
        "CC_P2_M5_05_C0_AUTHORITY_CONDITION",
        "E01_EPOCH_4_STATUS",
        "CURRENT_AUTHORITY_TAIL_END",
    }
    assert changed_keys == {
        key
        for key, predecessor_value in predecessor_values.items()
        if values[key] != predecessor_value
    }
    added_keys = {
        "CC_P2_M5_05_C0_CANDIDATE_SHA",
        "CC_P2_M5_05_C0_CI_RUN",
        "CC_P2_M5_05_C0_CI_RESULTS",
        "CC_P2_M5_05_C0_ARTIFACT_INSPECTION",
        "CC_P2_M5_05_C0_FULL_PYTHON",
        "CC_P2_M5_05_C0_FROZEN_REGRESSION",
        "CC_P2_M5_05_C0_GITLEAKS",
        "CC_P2_M5_05_C0_BROWSER_INTEGRATION",
        "CC_P2_M5_05_C0_SECURITY_REVIEW",
        "CC_P2_M5_05_C0_SOL_HIGH_FINAL_REVIEW",
        "CC_P2_M5_05_C0_PRINCIPAL_ACCEPTANCE",
        "CC_P2_M5_05_C_STATUS",
        "CC_P2_M5_05_C_AUTHORITY_CONDITION",
        "CC_P2_M5_05_C_POST_ACCEPTANCE_COMMIT_REQUIRED",
        "CC_P2_M5_05_C_OWNER_AUTHORITY",
        "CC_P2_M5_05_C_PREDECESSOR",
        "CC_P2_M5_05_C_CHANGE_CLASS",
        "CC_P2_M5_05_C_OUTPUT_ID",
        "CC_P2_M5_05_C_PRIVATE_RECEIPT_ID",
        "CC_P2_M5_05_C_PRIVATE_RECEIPT_SHA256",
        "CC_P2_M5_05_C_PRIVATE_ROOTS_CREATED",
        "CC_P2_M5_05_C_CREATE_MODE",
        "CC_P2_M5_05_C_PRIVATE_ROOT_CONTAINMENT",
        "CC_P2_M5_05_C_PRIVATE_ROOT_NON_REPARSE",
        "CC_P2_M5_05_C_EPOCH3_PRIVATE_BYTES_OR_DIGESTS_READ_COPIED_REUSED",
        "CC_P2_M5_05_C_IMAGEGEN_CALLS_EXECUTED",
        "CC_P2_M5_05_C_ORDINALS_CONSUMED",
        "CC_P2_M5_05_C_RAW_OUTPUTS_CREATED",
        "CC_P2_M5_05_C_IMAGE_BYTES_READ",
        "CC_P2_M5_05_C_DECODE_QA_SCREENING_ADMISSION",
        "CC_P2_M5_05_C_PRIVATE_LOCATOR_IN_TRACKED_EVIDENCE",
        "CC_P2_M5_05_C_PROMPT_PLAINTEXT_IN_TRACKED_EVIDENCE",
        "CC_P2_M5_05_C_PRIVATE_DIGEST_INHERITANCE",
        "CC_P2_M5_05_C_BOOTSTRAP_SHA256",
        "CC_P2_M5_05_C_PRIVATE_REGISTRY_SHA256",
        "CC_P2_M5_05_C_GENERATION_SPECIFICATION_SHA256",
        "CC_P2_M5_05_C_POLICY_ENVELOPE_SHA256",
        "CC_P2_M5_05_C_PRIVATE_PROMPT_TEMPLATE_SHA256",
        "CC_P2_M5_05_C_ADMISSION_RUBRIC_SHA256",
        "CC_P2_M5_05_C_ASSIGNMENT_LEDGER_SHA256",
        "CC_P2_M5_05_C_REQUEST_LEDGER_SHA256",
        "CC_P2_M5_05_C_OUTPUT_LEDGER_SHA256",
        "CC_P2_M5_05_C_PUBLIC_ASSIGNMENT_SEMANTICS_SHA256",
        "CC_P2_M5_05_C_ADULT_AGE_ASSIGNMENT_SHA256",
        "CC_P2_M5_05_C_REDACTED_EVIDENCE_SHA256",
        "CC_P2_M5_05_C_ADULT_18_19_ASSIGNMENT_COUNT",
        "CC_P2_M5_05_C_ADULT_20_25_ASSIGNMENT_COUNT",
        "CC_P2_M5_05_C_CAL_REQ_001_STATUS",
        "CC_P2_M5_05_C_CAL_REQ_002_STATUS",
        "CC_P2_M5_05_C_FIXED_ENTRYPOINT_RECOVERY",
        "CC_P2_M5_05_C_RESUME_PREDICATE_EFFECT",
        "CC_P2_M5_05_C_NEXT_PRIVATE_TASK",
        "E01_EPOCH_4_BOOTSTRAP_VERSION",
        "E01_EPOCH_4_BOOTSTRAP_DIGEST",
        "E01_EPOCH_4_PRIVATE_REGISTRY_VERSION",
        "E01_EPOCH_4_GENERATION_SPECIFICATION_VERSION",
        "E01_EPOCH_4_POLICY_ENVELOPE_VERSION",
        "E01_EPOCH_4_PROMPT_TEMPLATE_VERSION",
        "E01_EPOCH_4_ADMISSION_RUBRIC_VERSION",
        "E01_EPOCH_4_ASSIGNMENT_LEDGER_VERSION",
        "E01_EPOCH_4_REQUEST_LEDGER_VERSION",
        "E01_EPOCH_4_OUTPUT_LEDGER_VERSION",
        "E01_EPOCH_4_ADULT_AGE_ASSIGNMENT_MANIFEST",
        "E01_EPOCH_4_FIXED_ENTRYPOINT_RECOVERY",
        "E01_EPOCH_4_PRIVATE_OUTPUT_REGISTRY_RECEIPT",
        "P2_M5_R48",
        "P2_M5_R48_PARENT_SHA",
        "P2_M5_R48_PARENT_CI_RUN",
        "P2_M5_R48_PARENT_CI_RESULTS",
        "P2_M5_R48_FAILURE_CLASS",
        "P2_M5_R48_FAILED_FILES",
        "P2_M5_R48_REPAIR_SCOPE",
        "P2_M5_R48_RUNTIME_SCHEMA_API_SECURITY_CHANGE",
        "P2_M5_R48_IMAGEGEN_CALLS_EXECUTED",
        "P2_M5_R48_ORDINALS_CONSUMED",
        "P2_M5_R48_CAL_REQ_002_STATUS",
        "P2_M5_R48_PLAYWRIGHT_STATUS",
        "P2_M5_R48_POST_ACCEPTANCE_COMMIT_REQUIRED",
    }
    assert len(added_keys) == 78
    assert set(values) - set(predecessor_values) == added_keys

    assert values["CC_P2_M5_05_C0_STATUS"] == (
        "TASK_ACCEPTED_AT_D50AA8B2FBB39FA4794DD46ECFAFA07EF8614D8E_RUN_33252998303"
    )
    assert values["CC_P2_M5_05_C0_CI_RESULTS"] == (
        "QUALITY_AND_INTEGRATION_PASS;SECRET_SCAN_PASS;DOCKER_VALIDATION_PASS"
    )
    assert values["CC_P2_M5_05_C_STATUS"] == (
        "PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["CC_P2_M5_05_C_OUTPUT_ID"].lower() == evidence["output_id"].lower()
    assert values["CC_P2_M5_05_C_PRIVATE_RECEIPT_ID"].lower() == (
        evidence["private_receipt_id"].lower()
    )
    digest_bindings = {
        "CC_P2_M5_05_C_BOOTSTRAP_SHA256": "bootstrap_sha256",
        "CC_P2_M5_05_C_PRIVATE_REGISTRY_SHA256": "private_registry_sha256",
        "CC_P2_M5_05_C_GENERATION_SPECIFICATION_SHA256": ("generation_specification_sha256"),
        "CC_P2_M5_05_C_POLICY_ENVELOPE_SHA256": "policy_envelope_sha256",
        "CC_P2_M5_05_C_PRIVATE_PROMPT_TEMPLATE_SHA256": "prompt_template_sha256",
        "CC_P2_M5_05_C_ADMISSION_RUBRIC_SHA256": "admission_rubric_sha256",
        "CC_P2_M5_05_C_ASSIGNMENT_LEDGER_SHA256": "assignment_ledger_sha256",
        "CC_P2_M5_05_C_REQUEST_LEDGER_SHA256": "request_ledger_sha256",
        "CC_P2_M5_05_C_OUTPUT_LEDGER_SHA256": "output_ledger_sha256",
        "CC_P2_M5_05_C_PRIVATE_RECEIPT_SHA256": "private_receipt_sha256",
        "CC_P2_M5_05_C_PUBLIC_ASSIGNMENT_SEMANTICS_SHA256": ("public_assignment_semantics_sha256"),
        "CC_P2_M5_05_C_ADULT_AGE_ASSIGNMENT_SHA256": "adult_age_assignment_sha256",
    }
    assert {key: values[key] for key in digest_bindings} == {
        key: evidence[field].upper() for key, field in digest_bindings.items()
    }
    assert values["CC_P2_M5_05_C_REDACTED_EVIDENCE_SHA256"] == (
        hashlib.sha256(CC05_C_EVIDENCE_PATH.read_bytes()).hexdigest().upper()
    )
    assert values["CC_P2_M5_05_C_ADULT_18_19_ASSIGNMENT_COUNT"] == "7"
    assert values["CC_P2_M5_05_C_ADULT_20_25_ASSIGNMENT_COUNT"] == "24"
    assert values["CC_P2_M5_05_C_CAL_REQ_001_STATUS"] == "CONSUMED_FAILED_NO_RETRY"
    assert values["CC_P2_M5_05_C_CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["P2_M5_R48_PARENT_SHA"] == "9D31A32D5C2863D0866B6BD4BA8B8F8894B45D24"
    assert values["P2_M5_R48_PARENT_CI_RUN"] == "33254856895_ATTEMPT_1"
    assert values["P2_M5_R48_FAILURE_CLASS"] == "DETERMINISTIC_PRETTIER_FORMAT_DRIFT"
    assert values["P2_M5_R48_IMAGEGEN_CALLS_EXECUTED"] == "0"
    assert values["P2_M5_R48_ORDINALS_CONSUMED"] == "0"
    assert values["P2_M5_R48_CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["P2_M5_R48_PLAYWRIGHT_STATUS"] == (
        "NOT_RUN_DEPENDENCY_SKIPPED_NOT_A_PLAYWRIGHT_FAILURE"
    )
    assert values["CC_P2_M5_05_C_IMAGEGEN_CALLS_EXECUTED"] == "0"
    assert values["CC_P2_M5_05_C_ORDINALS_CONSUMED"] == "0"
    assert values["CC_P2_M5_05_C_RAW_OUTPUTS_CREATED"] == "0"
    assert values["CC_P2_M5_05_C_IMAGE_BYTES_READ"] == "0"
    assert values["CC_P2_M5_05_C_DECODE_QA_SCREENING_ADMISSION"] == "0"
    assert values["CC_P2_M5_05_C_EPOCH3_PRIVATE_BYTES_OR_DIGESTS_READ_COPIED_REUSED"] == ("0")
    assert values["CAL_REQ_001_STATUS"] == "CONSUMED_FAILED_NO_RETRY"
    assert values["CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["FORMAL_E01_GENERATION_CALLS_EXECUTED"] == "1"
    assert values["FORMAL_E01_RAW_OUTPUTS_CREATED"] == "1"
    assert values["FORMAL_CALLS_REMAINING"] == "31"
    assert values["FORMAL_RAW_CAPACITY_REMAINING"] == "31"
    assert values["GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "62"
    assert values["E01_ACTIVE_EXECUTION_CUSTODY"] == (
        "E01_EPOCH_4_PRINCIPAL_PRIVATE_CUSTODY_ACTIVE_AFTER_CC05_C_ACCEPTANCE"
    )
    assert values["E01_EPOCH_4_STATUS"] == (
        "MATERIALIZED_RECOVERABLE_AND_BOUND_TO_V3_AFTER_CC05_C_ACCEPTANCE"
    )
    assert values["FORMAL_E01_EXECUTION_AUTHORITY"].startswith("NOT_EFFECTIVE_UNTIL_")
    assert values["NEXT_READY_TASK"] == ("P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION")
    assert values["P2_M5_TECHNICAL_GATE"] == "NOT_EVALUATED"
    assert values["P2_MVR_V1_RESULT"] == "NOT_EVALUATED"
    assert values["P2_M6_ENTRY"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_CC05_C_E01_EPOCH4_PRIVATE_POLICY_MATERIALIZATION_TRUE_EOF",
    )
    assert ACCEPTANCE_PATH.read_text(encoding="utf-8").count(canonical[-1][1]) == 1
    assert EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8").count(mirror[-1][1]) == 1

    tracked = "\n".join(
        (
            CC05_C_EVIDENCE_PATH.read_text(encoding="utf-8"),
            CC05_C_EVIDENCE_DOC_PATH.read_text(encoding="utf-8"),
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-300_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-300_000:],
        )
    )
    assert ".private-handoff" not in tracked
    assert ".local-storage" not in tracked
    assert "data:image/" not in tracked
    assert "private_template_nonce" not in tracked
    assert "positive_segments" not in tracked
    assert "negative_segments" not in tracked
    assert "provider_raw_payload" not in tracked.lower()
    assert "C:\\" not in tracked
    assert "D:\\" not in tracked


def test_r46_ci_platform_typing_overlay_is_complete_mirrored_and_true_eof() -> None:
    canonical = _last_r46_key_block(ACCEPTANCE_PATH)
    mirror = _last_r46_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_r45_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)

    assert canonical == mirror
    assert len(canonical) == len(values) == 441
    assert len(predecessor) == len(predecessor_values) == 405
    assert set(predecessor_values) <= values.keys()

    expected_overrides = {
        "CURRENT_STATE_AUTHORITY_VERSION": "p2-m5-r46-r45-ci-platform-typing-repair-eof/v1",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_CC05_A_FOR_THE_COMPLETE_"
            "LISTED_KEYSET_ONLY_AFTER_R46_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_CHECKS_"
            "SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_MIRROR_RULE": (
            "MUST_MATCH_CANONICAL_ACCEPTANCE_R46_KEY_SET_ORDER_AND_VALUES"
        ),
        "EARLIER_STATUS_SECTIONS": (
            "PRESERVED_HISTORICAL_EVIDENCE_NON_CURRENT_FOR_THE_COMPLETE_LISTED_KEYSET_"
            "AFTER_R46_ACCEPTANCE"
        ),
        "CC04_B_EXECUTION": "SUSPENDED_PENDING_R46_AND_R43_Q01_EXECUTION_OVERLAY_ACCEPTANCE",
        "FORMAL_E01_STATUS": (
            "SUSPENDED_PENDING_R46_ACCEPTANCE_AND_PRIVATE_OVERLAY_MATERIALIZATION"
        ),
        "FORMAL_E01_EXECUTION_AUTHORITY": (
            "NOT_EFFECTIVE_UNTIL_R46_AND_R43_Q01_REDACTED_EVIDENCE_ALL_GATES_AND_"
            "PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_KEY_COVERAGE": (
            "COMPLETE_CC05_A_PREDECESSOR_KEYSET_PLUS_R43_R44_R45_AND_R46_CI_PLATFORM_"
            "TYPING_REPAIR_KEYS"
        ),
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_CC05_A_TRUE_EOF_REMAINS_CURRENT_UNTIL_R46_AUTHORITY_CONDITION_IS_SATISFIED"
        ),
        "P2_M5_NEXT_ACTION": (
            "COMPLETE_R46_SAME_SHA_GATES_THEN_R43_Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"
        ),
        "NEXT_READY_TASK": "P2_M5_R46_SAME_SHA_GATES",
        "STOP_OUTCOME": (
            "CAL_REQ_002_NOT_DISPATCHED_PENDING_ACCEPTED_R46_EXECUTION_OVERLAY_AUTHORITY"
        ),
        "P2_M5_R43_STATUS": (
            "REJECTED_AT_8BECAE2_SECURITY_AND_SOL_HIGH_FINDINGS_REPAIRED_ONLY_WITH_R46_ACCEPTANCE"
        ),
        "P2_M5_R43_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_WITH_R46_AFTER_R46_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_"
            "CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R44_STATUS": (
            "REJECTED_AT_50B1DE2_SECURITY_AND_SOL_HIGH_TOCTOU_AND_PROMPT_FORMAT_FINDINGS_"
            "REPAIRED_ONLY_WITH_R46_ACCEPTANCE"
        ),
        "P2_M5_R44_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_WITH_R46_AFTER_R46_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_"
            "CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R43_Q01_STATUS": "CLOSED_PENDING_ACCEPTED_R46_EXECUTION_OVERLAY_AUTHORITY",
        "P2_M5_R45_STATUS": (
            "REJECTED_AT_2ED324237DEC074B9BD3412B4458FB715DA95899_RUN_33249622650_"
            "LINUX_STRICT_MYPY_PLATFORM_TYPING_FAILURE"
        ),
        "P2_M5_R45_AUTHORITY_CONDITION": (
            "NOT_SATISFIED_AT_2ED324237DEC074B9BD3412B4458FB715DA95899_RUN_33249622650_"
            "SUPERSEDED_BY_R46"
        ),
        "CURRENT_AUTHORITY_TAIL_END": "P2_M5_R46_R45_CI_PLATFORM_TYPING_REPAIR_TRUE_EOF",
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
        "P2_M5_R45_CANDIDATE_SHA": "2ED324237DEC074B9BD3412B4458FB715DA95899",
        "P2_M5_R45_CI_RUN": "33249622650_ATTEMPT_1",
        "P2_M5_R45_CI_RESULTS": (
            "QUALITY_AND_INTEGRATION_FAIL_LINUX_STRICT_MYPY;SECRET_SCAN_PASS;DOCKER_VALIDATION_PASS"
        ),
        "P2_M5_R45_ARTIFACT_ACCEPTANCE": "NOT_EVALUATED_INCOMPLETE_CI",
        "P2_M5_R45_INDEPENDENT_REVIEWS": "NOT_STARTED_CI_PRECONDITION_FAILED",
        "P2_M5_R45_PRINCIPAL_ACCEPTANCE": (
            "DENIED_AT_2ED324237DEC074B9BD3412B4458FB715DA95899_RUN_33249622650"
        ),
        "P2_M5_R46_STATUS": "READY_FOR_TRACKED_EVIDENCE",
        "P2_M5_R46_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_AFTER_R46_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_"
            "CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R46_POST_ACCEPTANCE_COMMIT_REQUIRED": "NO",
        "P2_M5_R46_PARENT_SHA": "2ED324237DEC074B9BD3412B4458FB715DA95899",
        "P2_M5_R46_REJECTED_PARENT_RUN": "33249622650_ATTEMPT_1",
        "P2_M5_R46_ACCEPTED_FALLBACK": ("CC05_A_AT_40A239831985B76DD55788A4EDE6D98D60438F3D"),
        "P2_M5_R46_FAILURE_CLASS": "DETERMINISTIC_LINUX_STRICT_MYPY_PLATFORM_STUB_TYPING",
        "P2_M5_R46_FINDINGS": (
            "POSIX_FLAG_REDUNDANT_CAST_AND_UNUSED_IGNORE;"
            "WINDOWS_ONLY_CTYPES_MSVCRT_OS_STUB_ATTRIBUTES"
        ),
        "P2_M5_R46_REPAIR_SCOPE": (
            "PLATFORM_NEUTRAL_RUNTIME_CAPABILITY_LOOKUP_AND_TYPE_NARROWING_ONLY"
        ),
        "P2_M5_R46_POSIX_CAPABILITY_BOUNDARY": (
            "GETATTR_O_DIRECTORY_AND_O_NOFOLLOW_INTEGER_GUARD_FAIL_CLOSED"
        ),
        "P2_M5_R46_WINDOWS_CAPABILITY_BOUNDARY": (
            "GETATTR_WINDLL_OPEN_OSFHANDLE_AND_O_BINARY_GUARD_FAIL_CLOSED"
        ),
        "P2_M5_R46_MYPY_TARGETS": "WINDOWS_DEFAULT_AND_EXPLICIT_LINUX",
        "P2_M5_R46_RUNTIME_BEHAVIOR_CHANGE": "NONE",
        "P2_M5_R46_SOURCE_READ_BOUNDARY": (
            "UNCHANGED_FROM_R45_HANDLE_BOUND_NO_FOLLOW_COMPONENT_OPEN"
        ),
        "P2_M5_R46_PROMPT_BOUNDARY": "UNCHANGED_FROM_R45_EXACT_FOUR_FIELD_FORMATTER_PARSE",
        "P2_M5_R46_REGISTRATION_FAILURE": (
            "AUTOMATIC_OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE_TERMINAL"
        ),
        "P2_M5_R46_STATE_MACHINE_CHANGE": "NONE",
        "P2_M5_R46_SCHEMA_OR_MIGRATION_CHANGE": "NONE",
        "P2_M5_R46_PUBLIC_API_CHANGE": "NONE",
        "P2_M5_R46_DEPENDENCY_MODEL_OR_WORKFLOW_CHANGE": "NONE",
        "P2_M5_R46_IMAGEGEN_CALLS_EXECUTED": "0",
        "P2_M5_R46_ORDINALS_CONSUMED": "0",
        "P2_M5_R46_RAW_OUTPUTS_CREATED": "0",
        "P2_M5_R46_PRIVATE_ROOTS_CREATED": "0",
        "P2_M5_R46_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN": "0",
        "P2_M5_R46_DECODE_QA_SCREENING_ADMISSION": "0",
        "P2_M5_R46_NEXT_PRIVATE_TASK": ("P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"),
        "P2_M5_R46_Q01_IMAGEGEN_CALLS": "0",
        "P2_M5_R46_Q01_ORDINALS_CONSUMED": "0",
        "P2_M5_R46_Q01_REDACTED_EVIDENCE_REQUIRED": "YES_BEFORE_CAL_REQ_002_DISPATCH",
    }
    assert len(additions) == 36
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
        "P2_M5_R46_R45_CI_PLATFORM_TYPING_REPAIR_TRUE_EOF",
    )

    tracked = "\n".join(
        (
            R45_REPAIR_PATH.read_text(encoding="utf-8"),
            R46_REPAIR_PATH.read_text(encoding="utf-8"),
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-175_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-175_000:],
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


def test_cc05_b_evidence_location_loss_overlay_is_complete_mirrored_and_true_eof() -> None:
    canonical = _last_cc05_b_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_b_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_r46_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)

    assert canonical == mirror
    assert len(canonical) == len(values) == 471
    assert len(predecessor) == len(predecessor_values) == 441
    assert set(predecessor_values) <= values.keys()

    expected_overrides = {
        "CURRENT_STATE_AUTHORITY_VERSION": ("p2-m5-cc05-b-epoch3-evidence-location-loss-eof/v1"),
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_R46_FOR_THE_COMPLETE_"
            "LISTED_KEYSET_ONLY_AFTER_CC05_B_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_CHECKS_"
            "SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_MIRROR_RULE": (
            "MUST_MATCH_CANONICAL_ACCEPTANCE_CC05_B_KEY_SET_ORDER_AND_VALUES"
        ),
        "EARLIER_STATUS_SECTIONS": (
            "PRESERVED_HISTORICAL_EVIDENCE_NON_CURRENT_FOR_THE_COMPLETE_LISTED_KEYSET_"
            "AFTER_CC05_B_ACCEPTANCE"
        ),
        "CC04_B_EXECUTION": "SUSPENDED_EVIDENCE_LOCATION_LOST_NO_DISPATCH",
        "FORMAL_E01_STATUS": "SUSPENDED_EVIDENCE_LOCATION_LOST",
        "FORMAL_E01_EXECUTION_AUTHORITY": (
            "NOT_EFFECTIVE_WITHOUT_RECOVERABLE_EXACT_TASK_SCOPED_RECEIPT_HANDLE"
        ),
        "CURRENT_STATE_KEY_COVERAGE": (
            "COMPLETE_R46_PREDECESSOR_KEYSET_PLUS_R46_ACCEPTANCE_AND_CC05_B_"
            "EVIDENCE_LOCATION_LOSS_KEYS"
        ),
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_R46_TRUE_EOF_REMAINS_CURRENT_UNTIL_CC05_B_AUTHORITY_CONDITION_IS_SATISFIED"
        ),
        "P2_M5_NEXT_ACTION": ("COMPLETE_CC05_B_SAME_SHA_GATES_THEN_HOLD_AT_EVIDENCE_LOCATION_LOST"),
        "NEXT_READY_TASK": "CC_P2_M5_05_B_SAME_SHA_GATES",
        "STOP_OUTCOME": "CAL_REQ_002_NOT_DISPATCHED_EVIDENCE_LOCATION_LOST",
        "P2_M5_R43_STATUS": ("TASK_ACCEPTED_WITH_R46_AT_31F4ECDB598E0796C1939C6B17F5CE70C07B5793"),
        "P2_M5_R43_AUTHORITY_CONDITION": (
            "SATISFIED_WITH_R46_AT_31F4ECDB598E0796C1939C6B17F5CE70C07B5793_RUN_33250016931"
        ),
        "P2_M5_R43_Q01_STATUS": ("CLOSED_UNAVAILABLE_WITH_CURRENT_TASK_SCOPED_EVIDENCE"),
        "P2_M5_R46_STATUS": (
            "TASK_ACCEPTED_AT_31F4ECDB598E0796C1939C6B17F5CE70C07B5793_RUN_33250016931"
        ),
        "P2_M5_R46_AUTHORITY_CONDITION": (
            "SATISFIED_AT_31F4ECDB598E0796C1939C6B17F5CE70C07B5793_RUN_33250016931_"
            "AFTER_EIGHT_ARTIFACT_INSPECTION_SECURITY_AND_SOL_HIGH_REVIEW"
        ),
        "CURRENT_AUTHORITY_TAIL_END": ("P2_M5_CC05_B_EPOCH3_EVIDENCE_LOCATION_LOSS_TRUE_EOF"),
    }
    actual_overrides = {
        key: values[key]
        for key, predecessor_value in predecessor_values.items()
        if values[key] != predecessor_value
    }
    assert actual_overrides == expected_overrides

    additions = {
        "P2_M5_R46_CANDIDATE_SHA": "31F4ECDB598E0796C1939C6B17F5CE70C07B5793",
        "P2_M5_R46_CI_RUN": "33250016931_ATTEMPT_1",
        "P2_M5_R46_CI_RESULTS": (
            "QUALITY_AND_INTEGRATION_PASS;SECRET_SCAN_PASS;DOCKER_VALIDATION_PASS"
        ),
        "P2_M5_R46_ARTIFACT_INSPECTION": ("PASS_8_FAMILIES_11_FILES_EXACT_SHA_BOUND_UNEXPIRED"),
        "P2_M5_R46_FROZEN_REGRESSION": ("PHASE1_1_M1_98_M2_52_M3_46_ZERO_FAILURE_ERROR_SKIP"),
        "P2_M5_R46_GITLEAKS": "PASS_ZERO_RESULTS",
        "P2_M5_R46_BROWSER_INTEGRATION": "PASS_5_OF_5",
        "P2_M5_R46_PLAYWRIGHT": (
            "VERSION_1_62_1_SYSTEM_DEPS_17_SECONDS_CHROMIUM_12_SECONDS_FIRST_ATTEMPT"
        ),
        "P2_M5_R46_SECURITY_REVIEW": "PASS",
        "P2_M5_R46_SOL_HIGH_FINAL_REVIEW": "PASS",
        "P2_M5_R46_PRINCIPAL_ACCEPTANCE": (
            "GRANTED_AFTER_ACTUAL_DIFF_ARTIFACT_SECURITY_AND_FINAL_REVIEW"
        ),
        "CC_P2_M5_05_B_STATUS": "READY_FOR_TRACKED_EVIDENCE",
        "CC_P2_M5_05_B_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_AFTER_CC05_B_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_"
            "CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CC_P2_M5_05_B_POST_ACCEPTANCE_COMMIT_REQUIRED": "NO",
        "CC_P2_M5_05_B_EVIDENCE_LOCATION_STATUS": "EVIDENCE_LOCATION_LOST",
        "CC_P2_M5_05_B_HANDLE_SEARCH_STATUS": "CLOSED_NEGATIVE_EVIDENCE",
        "CC_P2_M5_05_B_RETRY_WITHOUT_NEW_INPUT": "PROHIBITED",
        "CC_P2_M5_05_B_OWNER_UPLOAD_OBLIGATION": ("NONE_PRINCIPAL_RETAINS_CUSTODY_RESPONSIBILITY"),
        "CC_P2_M5_05_B_REPLACEMENT_ROOT": "PROHIBITED",
        "CC_P2_M5_05_B_SINGLE_RESUME_PREDICATE": (
            "NEW_ACCEPTED_FORWARD_EXECUTION_AUTHORITY_WITH_RECOVERABLE_EXACT_TASK_SCOPED_"
            "HANDLE_AND_COMPLETE_RESOURCE_LEDGER"
        ),
        "CC_P2_M5_05_B_IMAGEGEN_CALLS_EXECUTED": "0",
        "CC_P2_M5_05_B_ORDINALS_CONSUMED": "0",
        "CC_P2_M5_05_B_RAW_OUTPUTS_CREATED": "0",
        "CC_P2_M5_05_B_PRIVATE_ROOTS_CREATED": "0",
        "CC_P2_M5_05_B_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN": "0",
        "CC_P2_M5_05_B_DECODE_QA_SCREENING_ADMISSION": "0",
        "D02_R2_EXACT_TASK_SCOPED_HANDLE_RESULT": "NO_EXACT_TASK_SCOPED_HANDLE",
        "D02_R2_HANDLE_SEARCH_STATUS": "CLOSED_NEGATIVE_EVIDENCE",
        "D02_R2_REPEATED_HANDLE_SEARCH": "NO",
        "OWNER_ACTION_REQUIRED": "NO",
    }
    assert len(additions) == 30
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
        "P2_M5_CC05_B_EPOCH3_EVIDENCE_LOCATION_LOSS_TRUE_EOF",
    )
    assert ACCEPTANCE_PATH.read_text(encoding="utf-8").count(canonical[-1][1]) == 1
    assert EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8").count(mirror[-1][1]) == 1

    tracked = "\n".join(
        (
            CC05_B_CHANGE_CONTROL_PATH.read_text(encoding="utf-8"),
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-190_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-190_000:],
        )
    )
    assert "EVIDENCE_LOCATION_LOST" in tracked
    assert ".private-handoff" not in tracked
    assert ".local-storage" not in tracked
    assert "data:image/" not in tracked
    assert "provider_raw_payload" not in tracked.lower()
    assert "C:\\" not in tracked
    assert "D:\\" not in tracked


def test_r45_gate_closure_overlay_is_complete_mirrored_and_true_eof() -> None:
    canonical = _last_r45_key_block(ACCEPTANCE_PATH)
    mirror = _last_r45_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_r44_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)

    assert canonical == mirror
    assert len(canonical) == len(values) == 405
    assert len(predecessor) == len(predecessor_values) == 375
    assert set(predecessor_values) <= values.keys()

    expected_overrides = {
        "CURRENT_STATE_AUTHORITY_VERSION": "p2-m5-r45-r44-gate-closure-repair-eof/v1",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_CC05_A_FOR_THE_COMPLETE_"
            "LISTED_KEYSET_ONLY_AFTER_R45_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_CHECKS_"
            "SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_MIRROR_RULE": (
            "MUST_MATCH_CANONICAL_ACCEPTANCE_R45_KEY_SET_ORDER_AND_VALUES"
        ),
        "EARLIER_STATUS_SECTIONS": (
            "PRESERVED_HISTORICAL_EVIDENCE_NON_CURRENT_FOR_THE_COMPLETE_LISTED_KEYSET_"
            "AFTER_R45_ACCEPTANCE"
        ),
        "CC04_B_EXECUTION": "SUSPENDED_PENDING_R45_AND_R43_Q01_EXECUTION_OVERLAY_ACCEPTANCE",
        "FORMAL_E01_STATUS": (
            "SUSPENDED_PENDING_R45_ACCEPTANCE_AND_PRIVATE_OVERLAY_MATERIALIZATION"
        ),
        "FORMAL_E01_EXECUTION_AUTHORITY": (
            "NOT_EFFECTIVE_UNTIL_R45_AND_R43_Q01_REDACTED_EVIDENCE_ALL_GATES_AND_"
            "PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_KEY_COVERAGE": (
            "COMPLETE_CC05_A_PREDECESSOR_KEYSET_PLUS_R43_R44_AND_R45_GATE_CLOSURE_REPAIR_KEYS"
        ),
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_CC05_A_TRUE_EOF_REMAINS_CURRENT_UNTIL_R45_AUTHORITY_CONDITION_IS_SATISFIED"
        ),
        "P2_M5_NEXT_ACTION": (
            "COMPLETE_R45_SAME_SHA_GATES_THEN_R43_Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"
        ),
        "NEXT_READY_TASK": "P2_M5_R45_SAME_SHA_GATES",
        "STOP_OUTCOME": (
            "CAL_REQ_002_NOT_DISPATCHED_PENDING_ACCEPTED_R45_EXECUTION_OVERLAY_AUTHORITY"
        ),
        "P2_M5_R43_STATUS": (
            "REJECTED_AT_8BECAE2_SECURITY_AND_SOL_HIGH_FINDINGS_REPAIRED_ONLY_WITH_R45_ACCEPTANCE"
        ),
        "P2_M5_R43_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_WITH_R45_AFTER_R45_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_"
            "CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R44_STATUS": (
            "REJECTED_AT_50B1DE2_SECURITY_AND_SOL_HIGH_TOCTOU_AND_PROMPT_FORMAT_FINDINGS"
        ),
        "P2_M5_R44_AUTHORITY_CONDITION": (
            "NOT_SATISFIED_AT_50B1DE2_SECURITY_AND_SOL_HIGH_REVIEW_SUPERSEDED_BY_R45"
        ),
        "CURRENT_AUTHORITY_TAIL_END": "P2_M5_R45_R44_GATE_CLOSURE_REPAIR_TRUE_EOF",
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
        "P2_M5_R43_Q01_STATUS": "CLOSED_PENDING_ACCEPTED_R45_EXECUTION_OVERLAY_AUTHORITY",
        "P2_M5_R44_CANDIDATE_SHA": "50B1DE2C9FEDFD0DD6997560F3C3C3A1C404E575",
        "P2_M5_R44_PRINCIPAL_ACCEPTANCE": (
            "DENIED_AT_50B1DE2_AFTER_INDEPENDENT_SECURITY_AND_SOL_HIGH_REVIEW"
        ),
        "P2_M5_R45_STATUS": "READY_FOR_TRACKED_EVIDENCE",
        "P2_M5_R45_AUTHORITY_CONDITION": (
            "EFFECTIVE_ONLY_AFTER_R45_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_"
            "CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R45_POST_ACCEPTANCE_COMMIT_REQUIRED": "NO",
        "P2_M5_R45_PARENT_SHA": "50B1DE2C9FEDFD0DD6997560F3C3C3A1C404E575",
        "P2_M5_R45_ACCEPTED_FALLBACK": ("CC05_A_AT_40A239831985B76DD55788A4EDE6D98D60438F3D"),
        "P2_M5_R45_SECURITY_REVIEW_AT_PARENT": "FAIL_HIGH_VALIDATE_OPEN_TOCTOU",
        "P2_M5_R45_SOL_HIGH_REVIEW_AT_PARENT": "FAIL_PRIVATE_PROMPT_COMPOSITE_FIELDS",
        "P2_M5_R45_FINDINGS": (
            "SOURCE_ALLOWED_ROOT_VALIDATE_OPEN_TOCTOU;PRIVATE_PROMPT_COMPOSITE_FIELD_VALIDATION"
        ),
        "P2_M5_R45_SOURCE_READ_BOUNDARY": (
            "HANDLE_BOUND_NO_FOLLOW_COMPONENT_OPEN_ROOT_IDENTITY_RECHECK_AND_DESCRIPTOR_READ"
        ),
        "P2_M5_R45_WINDOWS_BOUNDARY": (
            "CREATEFILEW_OPEN_REPARSE_POINT_HANDLE_TYPE_FINAL_PATH_AND_NO_WRITE_DELETE_SHARING"
        ),
        "P2_M5_R45_POSIX_BOUNDARY": (
            "DIR_FD_COMPONENT_OPEN_O_NOFOLLOW_FSTAT_AND_ROOT_IDENTITY_RECHECK"
        ),
        "P2_M5_R45_PROMPT_BOUNDARY": (
            "EXACT_FOUR_FIELD_FORMATTER_PARSE_NO_COMPOSITE_CONVERSION_OR_FORMAT_SPEC"
        ),
        "P2_M5_R45_REGISTRATION_FAILURE": (
            "AUTOMATIC_OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE_TERMINAL"
        ),
        "P2_M5_R45_STATE_MACHINE_CHANGE": "NONE",
        "P2_M5_R45_SCHEMA_OR_MIGRATION_CHANGE": "NONE",
        "P2_M5_R45_PUBLIC_API_CHANGE": "NONE",
        "P2_M5_R45_DEPENDENCY_MODEL_OR_WORKFLOW_CHANGE": "NONE",
        "P2_M5_R45_IMAGEGEN_CALLS_EXECUTED": "0",
        "P2_M5_R45_ORDINALS_CONSUMED": "0",
        "P2_M5_R45_RAW_OUTPUTS_CREATED": "0",
        "P2_M5_R45_PRIVATE_ROOTS_CREATED": "0",
        "P2_M5_R45_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN": "0",
        "P2_M5_R45_DECODE_QA_SCREENING_ADMISSION": "0",
        "P2_M5_R45_NEXT_PRIVATE_TASK": ("P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION"),
        "P2_M5_R45_Q01_IMAGEGEN_CALLS": "0",
        "P2_M5_R45_Q01_ORDINALS_CONSUMED": "0",
        "P2_M5_R45_Q01_REDACTED_EVIDENCE_REQUIRED": "YES_BEFORE_CAL_REQ_002_DISPATCH",
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
        "P2_M5_R45_R44_GATE_CLOSURE_REPAIR_TRUE_EOF",
    )
    tracked = "\n".join(
        (
            R44_REPAIR_PATH.read_text(encoding="utf-8"),
            R45_REPAIR_PATH.read_text(encoding="utf-8"),
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-150_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-150_000:],
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


def test_r43_q01_redacted_evidence_is_complete_zero_generation_and_path_free() -> None:
    evidence = cast(
        dict[str, Any],
        json.loads(R43_Q01_EVIDENCE_PATH.read_text(encoding="utf-8")),
    )

    assert evidence["schema_version"] == ("mirror.p2-m5/R43Q01OverlayMaterializationEvidence/v1")
    assert evidence["task_id"] == ("P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION")
    assert evidence["status"] == (
        "LOCAL_PRIVATE_OVERLAY_MATERIALIZATION_PASS_PENDING_TRACKED_GATES"
    )
    assert evidence["overlay_create_mode"] == "CREATE_NEW_NO_OVERWRITE"
    assert evidence["overlay_root_count"] == 1
    assert evidence["overlay_sequence"] == 0
    assert evidence["overlay_phase"] == "READY"
    assert evidence["decode_authorized"] is False
    assert evidence["hard_stop"] is False
    assert evidence["fresh_process_handle_recovery"] == "PASS"
    assert evidence["project_private_recoverable_custody"] == (
        "PASS_DEDICATED_GIT_IGNORED_PROJECT_FOLDER"
    )
    assert evidence["receipt_graph_document_count"] == 10
    assert evidence["control_digest_match_count"] == 8
    assert evidence["control_digest_expected_count"] == 8
    assert evidence["prompt_render_validation"] == ("PASS_IN_MEMORY_EXACT_FOUR_FIELDS_NOT_EXPORTED")

    for field in (
        "controller_sha256",
        "materialization_intent_sha256",
        "overlay_handle_sha256",
        "overlay_receipt_sha256",
        "overlay_state_sha256",
        "source_receipt_sha256",
    ):
        assert isinstance(evidence[field], str)
        assert re.fullmatch(r"[0-9a-f]{64}", evidence[field])

    assert evidence["request_call_count"] == 1
    assert evidence["requested_output_count"] == 1
    assert evidence["returned_output_count"] == 1
    assert evidence["raw_output_count"] == 1
    assert evidence["failed_call_count"] == 0
    assert evidence["rejected_output_count"] == 0
    assert evidence["admitted_identity_count"] == 0
    assert evidence["formal_calls_remaining"] == 31
    assert evidence["formal_raw_capacity_remaining"] == 31
    assert evidence["global_native_output_capacity_remaining"] == 62
    assert evidence["global_native_output_consumed"] == 2
    assert evidence["active_calls"] == 0
    assert evidence["cal_req_001_status"] == "CONSUMED_FAILED_NO_RETRY"
    assert evidence["cal_req_002_status"] == "NOT_CONSUMED"
    assert evidence["next_unused_formal_ordinal"] == "CAL-REQ-002"

    for field in (
        "generation_or_provider_calls_in_q01",
        "ordinals_consumed_in_q01",
        "raw_outputs_created_in_q01",
        "image_bytes_read_in_q01",
        "decode_qa_screening_admission_in_q01",
        "real_user_runtime_generation_calls",
    ):
        assert evidence[field] == 0
    for field in (
        "cal_req_002_dispatch_authorized_in_q01",
        "private_prompt_or_locator_in_tracked_evidence",
        "public_api_change",
        "schema_or_migration_change",
        "dependency_model_or_workflow_change",
        "question_bank_release_authorized",
        "real_user_facial_processing_authorized",
    ):
        assert evidence[field] is False
    assert evidence["p2_m5_technical_gate"] == "NOT_EVALUATED"
    assert evidence["p2_mvr_v1_result"] == "NOT_EVALUATED"
    assert evidence["p2_m6_entry"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert evidence["next_ready_task_after_acceptance"] == "EXECUTE_CAL_REQ_002"

    tracked = "\n".join(
        (
            R43_Q01_EVIDENCE_PATH.read_text(encoding="utf-8"),
            R43_Q01_EVIDENCE_DOC_PATH.read_text(encoding="utf-8"),
        )
    )
    for forbidden in (
        ".private-handoff",
        ".local-storage",
        "receipt_locator",
        "overlay_receipt_relative",
        "private_template_nonce",
        "positive_segments",
        "negative_segments",
        "prompt_text",
        "prompt_plaintext",
        "seed_value",
        "object_key",
        "signed_url",
        "data:image/",
        "C:\\",
        "D:\\",
    ):
        assert forbidden not in tracked
    assert "provider_raw_payload" not in tracked.lower()


def test_r49_q01_true_eof_is_complete_mirrored_and_binds_redacted_evidence() -> None:
    canonical = _last_r49_q01_key_block(ACCEPTANCE_PATH)
    mirror = _last_r49_q01_key_block(EXECUTION_PROTOCOL_PATH)
    predecessor = _last_cc05_c_key_block(ACCEPTANCE_PATH)
    values = dict(canonical)
    predecessor_values = dict(predecessor)
    evidence = cast(
        dict[str, Any],
        json.loads(R43_Q01_EVIDENCE_PATH.read_text(encoding="utf-8")),
    )

    assert canonical == mirror
    assert len(canonical) == len(values) == 683
    assert len(predecessor) == len(predecessor_values) == 610
    assert set(predecessor_values) <= values.keys()

    expected_changed_keys = {
        "CURRENT_STATE_AUTHORITY_VERSION",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE",
        "CURRENT_STATE_MIRROR_RULE",
        "EARLIER_STATUS_SECTIONS",
        "CC04_B_EXECUTION",
        "FORMAL_E01_STATUS",
        "FORMAL_E01_EXECUTION_AUTHORITY",
        "CURRENT_STATE_PRECONDITION_FALLBACK",
        "E01_ACTIVE_EXECUTION_CUSTODY",
        "E01_EPOCH_4_STATUS",
        "P2_M5_NEXT_ACTION",
        "NEXT_READY_TASK",
        "CURRENT_STATE_KEY_COVERAGE",
        "STOP_OUTCOME",
        "P2_M5_R43_Q01_STATUS",
        "P2_M5_R43_Q01_REDACTED_EVIDENCE_REQUIRED",
        "CURRENT_AUTHORITY_TAIL_END",
    }
    assert expected_changed_keys == {
        key
        for key, predecessor_value in predecessor_values.items()
        if values[key] != predecessor_value
    }

    added_keys = {
        "P2_M5_R43_Q01_AUTHORITY_CONDITION",
        "P2_M5_R43_Q01_POST_ACCEPTANCE_COMMIT_REQUIRED",
        "P2_M5_R43_Q01_PREDECESSOR_SHA",
        "P2_M5_R43_Q01_CHANGE_CLASS",
        "P2_M5_R43_Q01_SOURCE_OUTPUT_ID",
        "P2_M5_R43_Q01_SOURCE_RECEIPT_SHA256",
        "P2_M5_R43_Q01_CONTROLLER_SHA256",
        "P2_M5_R43_Q01_MATERIALIZATION_INTENT_SHA256",
        "P2_M5_R43_Q01_OVERLAY_OUTPUT_ID",
        "P2_M5_R43_Q01_OVERLAY_HANDLE_SHA256",
        "P2_M5_R43_Q01_OVERLAY_RECEIPT_SHA256",
        "P2_M5_R43_Q01_OVERLAY_STATE_SHA256",
        "P2_M5_R43_Q01_REDACTED_EVIDENCE_SHA256",
        "P2_M5_R43_Q01_OVERLAY_CREATE_MODE",
        "P2_M5_R43_Q01_OVERLAY_ROOT_COUNT",
        "P2_M5_R43_Q01_PROJECT_PRIVATE_RECOVERABLE_CUSTODY",
        "P2_M5_R43_Q01_RECEIPT_GRAPH_DOCUMENT_COUNT",
        "P2_M5_R43_Q01_CONTROL_DIGEST_MATCH",
        "P2_M5_R43_Q01_PROMPT_RENDER_VALIDATION",
        "P2_M5_R43_Q01_OVERLAY_SEQUENCE",
        "P2_M5_R43_Q01_OVERLAY_PHASE",
        "P2_M5_R43_Q01_DECODE_AUTHORIZED",
        "P2_M5_R43_Q01_HARD_STOP",
        "P2_M5_R43_Q01_FRESH_PROCESS_HANDLE_RECOVERY",
        "P2_M5_R43_Q01_REQUEST_CALL_COUNT",
        "P2_M5_R43_Q01_REQUESTED_OUTPUT_COUNT",
        "P2_M5_R43_Q01_RETURNED_OUTPUT_COUNT",
        "P2_M5_R43_Q01_RAW_OUTPUT_COUNT",
        "P2_M5_R43_Q01_FAILED_CALL_COUNT",
        "P2_M5_R43_Q01_REJECTED_OUTPUT_COUNT",
        "P2_M5_R43_Q01_ADMITTED_IDENTITY_COUNT",
        "P2_M5_R43_Q01_FORMAL_CALLS_REMAINING",
        "P2_M5_R43_Q01_FORMAL_RAW_CAPACITY_REMAINING",
        "P2_M5_R43_Q01_GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING",
        "P2_M5_R43_Q01_GLOBAL_NATIVE_OUTPUT_CONSUMED",
        "P2_M5_R43_Q01_ACTIVE_CALLS",
        "P2_M5_R43_Q01_CAL_REQ_001_STATUS",
        "P2_M5_R43_Q01_CAL_REQ_002_STATUS",
        "P2_M5_R43_Q01_CAL_REQ_002_DISPATCH_AUTHORIZED_IN_Q01",
        "P2_M5_R43_Q01_GENERATION_OR_PROVIDER_CALLS",
        "P2_M5_R43_Q01_RAW_OUTPUTS_CREATED",
        "P2_M5_R43_Q01_IMAGE_BYTES_READ",
        "P2_M5_R43_Q01_DECODE_QA_SCREENING_ADMISSION",
        "P2_M5_R43_Q01_PRIVATE_PROMPT_OR_LOCATOR_IN_TRACKED_EVIDENCE",
        "P2_M5_R43_Q01_PUBLIC_API_CHANGE",
        "P2_M5_R43_Q01_SCHEMA_OR_MIGRATION_CHANGE",
        "P2_M5_R43_Q01_DEPENDENCY_MODEL_OR_WORKFLOW_CHANGE",
        "P2_M5_R43_Q01_QUESTION_BANK_RELEASE_AUTHORIZED",
        "P2_M5_R43_Q01_PRODUCTION_PROVIDER_OR_GEOMETRY_APPROVED",
        "P2_M5_R43_Q01_REAL_USER_FACIAL_PROCESSING_AUTHORIZED",
        "P2_M5_R43_Q01_NEXT_TASK_AFTER_ACCEPTANCE",
        "P2_M5_R49_STATUS",
        "P2_M5_R49_TASK_ID",
        "P2_M5_R49_PARENT_CANDIDATE_SHA",
        "P2_M5_R49_PARENT_CI_RUN",
        "P2_M5_R49_PARENT_CI_RESULTS",
        "P2_M5_R49_PARENT_ARTIFACT_INSPECTION",
        "P2_M5_R49_PARENT_SECURITY_REVIEW",
        "P2_M5_R49_PARENT_SOL_HIGH_FINAL_REVIEW",
        "P2_M5_R49_PARENT_PRINCIPAL_ACCEPTANCE",
        "P2_M5_R49_FAILURE_CLASS",
        "P2_M5_R49_REPAIR_SCOPE",
        "P2_M5_R49_AUTHORITY_CONDITION",
        "P2_M5_R49_POST_ACCEPTANCE_AUTOMATIC_NEXT_READY_TASK",
        "P2_M5_R49_POST_ACCEPTANCE_COMMIT_REQUIRED",
        "P2_M5_R49_PRINCIPAL_ACCEPTANCE",
        "P2_M5_R49_IMAGEGEN_CALLS_EXECUTED",
        "P2_M5_R49_ORDINALS_CONSUMED",
        "P2_M5_R49_RAW_OUTPUTS_CREATED",
        "P2_M5_R49_IMAGE_BYTES_READ",
        "P2_M5_R49_DECODE_QA_SCREENING_ADMISSION",
        "P2_M5_R49_CAL_REQ_002_STATUS",
        "P2_M5_R49_RUNTIME_SCHEMA_API_DEPENDENCY_WORKFLOW_CHANGE",
    }
    assert len(added_keys) == 73
    assert set(values) - set(predecessor_values) == added_keys

    digest_bindings = {
        "P2_M5_R43_Q01_SOURCE_RECEIPT_SHA256": "source_receipt_sha256",
        "P2_M5_R43_Q01_CONTROLLER_SHA256": "controller_sha256",
        "P2_M5_R43_Q01_MATERIALIZATION_INTENT_SHA256": "materialization_intent_sha256",
        "P2_M5_R43_Q01_OVERLAY_HANDLE_SHA256": "overlay_handle_sha256",
        "P2_M5_R43_Q01_OVERLAY_RECEIPT_SHA256": "overlay_receipt_sha256",
        "P2_M5_R43_Q01_OVERLAY_STATE_SHA256": "overlay_state_sha256",
    }
    assert {key: values[key] for key in digest_bindings} == {
        key: evidence[field].upper() for key, field in digest_bindings.items()
    }
    assert values["P2_M5_R43_Q01_REDACTED_EVIDENCE_SHA256"] == (
        hashlib.sha256(R43_Q01_EVIDENCE_PATH.read_bytes()).hexdigest().upper()
    )
    assert values["P2_M5_R43_Q01_OVERLAY_OUTPUT_ID"].lower() == (
        evidence["overlay_output_id"].lower()
    )
    assert values["P2_M5_R43_Q01_STATUS"] == (
        "PASS_AFTER_P2_M5_R49_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["P2_M5_R49_PARENT_CANDIDATE_SHA"] == ("A710FF19A43C28AC0954B39572F3F16FC3C5884C")
    assert values["P2_M5_R49_PARENT_CI_RUN"] == "33259731211_ATTEMPT_1"
    assert values["P2_M5_R49_FAILURE_CLASS"] == (
        "POST_ACCEPTANCE_CURRENT_AUTHORITY_NEXT_TASK_CONFLICT"
    )
    assert values["P2_M5_R49_PARENT_SECURITY_REVIEW"] == "PASS"
    assert values["P2_M5_R49_PARENT_SOL_HIGH_FINAL_REVIEW"] == (
        "FAIL_POST_ACCEPTANCE_CURRENT_AUTHORITY_NEXT_TASK_CONFLICT"
    )
    assert values["P2_M5_R43_Q01_OVERLAY_PHASE"] == "READY"
    assert values["P2_M5_R43_Q01_OVERLAY_SEQUENCE"] == "0"
    assert values["P2_M5_R43_Q01_CONTROL_DIGEST_MATCH"] == "PASS_8_OF_8"
    assert values["P2_M5_R43_Q01_REQUEST_CALL_COUNT"] == "1"
    assert values["P2_M5_R43_Q01_REQUESTED_OUTPUT_COUNT"] == "1"
    assert values["P2_M5_R43_Q01_RETURNED_OUTPUT_COUNT"] == "1"
    assert values["P2_M5_R43_Q01_RAW_OUTPUT_COUNT"] == "1"
    assert values["P2_M5_R43_Q01_FORMAL_CALLS_REMAINING"] == "31"
    assert values["P2_M5_R43_Q01_FORMAL_RAW_CAPACITY_REMAINING"] == "31"
    assert values["P2_M5_R43_Q01_GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "62"
    assert values["P2_M5_R43_Q01_ACTIVE_CALLS"] == "0"
    assert values["P2_M5_R43_Q01_CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["P2_M5_R43_Q01_GENERATION_OR_PROVIDER_CALLS"] == "0"
    assert values["P2_M5_R43_Q01_IMAGEGEN_CALLS"] == "0"
    assert values["P2_M5_R43_Q01_ORDINALS_CONSUMED"] == "0"
    assert values["P2_M5_R43_Q01_RAW_OUTPUTS_CREATED"] == "0"
    assert values["P2_M5_R43_Q01_IMAGE_BYTES_READ"] == "0"
    assert values["CAL_REQ_002_STATUS"] == "NOT_CONSUMED"
    assert values["FORMAL_CALLS_REMAINING"] == "31"
    assert values["FORMAL_RAW_CAPACITY_REMAINING"] == "31"
    assert values["GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "62"
    assert (
        values["P2_M5_R49_POST_ACCEPTANCE_AUTOMATIC_NEXT_READY_TASK"]
        == values["NEXT_READY_TASK"]
        == evidence["next_ready_task_after_acceptance"]
        == "EXECUTE_CAL_REQ_002"
    )
    assert values["P2_M5_TECHNICAL_GATE"] == "NOT_EVALUATED"
    assert values["P2_MVR_V1_RESULT"] == "NOT_EVALUATED"
    assert values["P2_M6_ENTRY"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_R49_Q01_POST_ACCEPTANCE_NEXT_READY_TASK_AUTHORITY_REPAIR_TRUE_EOF",
    )
    acceptance_text = ACCEPTANCE_PATH.read_text(encoding="utf-8")
    protocol_text = EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")
    assert acceptance_text.count(canonical[-1][1]) == 1
    assert protocol_text.count(mirror[-1][1]) == 1
    assert acceptance_text.index(canonical[-1][1]) < acceptance_text.index(
        "p2-m5-cc05-d0-built-in-output-contract-recovery-eof/v1"
    )
    assert protocol_text.index(mirror[-1][1]) < protocol_text.index(
        "p2-m5-cc05-d0-built-in-output-contract-recovery-eof/v1"
    )

    tracked = "\n".join(
        (
            R43_Q01_EVIDENCE_PATH.read_text(encoding="utf-8"),
            R43_Q01_EVIDENCE_DOC_PATH.read_text(encoding="utf-8"),
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-350_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-350_000:],
        )
    )
    for forbidden in (
        ".private-handoff",
        ".local-storage",
        "receipt_locator",
        "overlay_receipt_relative",
        "positive_segments",
        "negative_segments",
        "provider_raw_payload",
        "data:image/",
        "C:\\",
        "D:\\",
    ):
        assert forbidden not in tracked


def test_cc05_d0_true_eof_is_mirrored_and_freezes_consumed_failure() -> None:
    canonical = _last_cc05_d0_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_d0_key_block(EXECUTION_PROTOCOL_PATH)
    values = dict(canonical)

    assert canonical == mirror
    assert len(canonical) == len(values) == 32
    assert values == {
        "CURRENT_STATE_AUTHORITY_VERSION": (
            "p2-m5-cc05-d0-built-in-output-contract-recovery-eof/v1"
        ),
        "CURRENT_STATE_CANONICAL_SOURCE": ("docs/operations/P2_M5_ACCEPTANCE.md_TRUE_EOF"),
        "CURRENT_STATE_MIRROR_SOURCE": ("docs/operations/P2_M5_EXECUTION_PROTOCOL.md_TRUE_EOF"),
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_R49_ONLY_FOR_THE_"
            "COMPLETE_LISTED_KEYSET_AFTER_D0_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_"
            "CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_MIRROR_RULE": "MUST_MATCH_CANONICAL_D0_KEY_SET_ORDER_AND_VALUES",
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_R49_REMAINS_TRACKED_CURRENT_UNTIL_D0_GATES_BUT_EXECUTION_IS_"
            "HARD_STOPPED_BY_VERIFIED_CONSUMED_FAILURE"
        ),
        "P2_M5_STATE": "EXECUTING",
        "CAL_REQ_002_STATUS": "CONSUMED_FAILED_NO_RETRY",
        "CAL_REQ_002_FINAL_DISPOSITION": "FAILED_NON_ADMISSIBLE_NO_RETRY",
        "CAL_REQ_002_FAILURE_PHASE": "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE",
        "CAL_REQ_002_FAILURE_REASON": "GENERATED_ARTIFACT_RECEIPT_INVALID",
        "CAL_REQ_002_ATTEMPT_FAILURE_EVIDENCE": ("RECOVERABLE_PROJECT_LOCAL_PRIVATE_CUSTODY"),
        "CAL_REQ_002_RAW_OUTPUT_CUSTODY": "EVIDENCE_LOCATION_LOST",
        "CAL_REQ_002_RETRY": "PROHIBITED",
        "NEXT_UNUSED_FORMAL_ORDINAL": "CAL-REQ-003",
        "FORMAL_CALLS_REMAINING": "30",
        "FORMAL_RAW_CAPACITY_REMAINING": "30",
        "GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING": "61",
        "GLOBAL_NATIVE_OUTPUT_CONSUMED": "3",
        "P2_M5_R49_STATUS": (
            "HISTORICAL_ACCEPTED_SUPERSEDED_FOR_D0_LISTED_KEYS_ONLY_AFTER_D0_ACCEPTANCE"
        ),
        "D0_GENERATION_CALLS": "0",
        "D0_RAW_OUTPUTS_CREATED": "0",
        "D0_IMAGE_BYTES_READ": "0",
        "D0_DECODE_QA_SCREENING_ADMISSION": "0",
        "D0_PRIVATE_ROOTS_CREATED": "0",
        "D0_PRIVATE_CUSTODY_RULE": ("PROJECT_LOCAL_GIT_IGNORED_RECOVERABLE_COPY_REQUIRED"),
        "D0_IMPLEMENTATION_TASK": "P2-M5-R50_AFTER_D0_ACCEPTANCE",
        "D0_NEXT_TASK": "CC_P2_M5_05_D0_SAME_SHA_GATES",
        "P2_M5_TECHNICAL_GATE": "NOT_EVALUATED",
        "P2_MVR_V1_RESULT": "NOT_EVALUATED",
        "P2_M6_ENTRY": "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS",
        "CURRENT_AUTHORITY_TAIL_END": ("P2_M5_CC05_D0_BUILT_IN_OUTPUT_CONTRACT_RECOVERY_TRUE_EOF"),
    }
    assert ACCEPTANCE_PATH.read_text(encoding="utf-8").count(canonical[-1][1]) == 1
    assert EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8").count(mirror[-1][1]) == 1
    assert D0_ADR_PATH.is_file()
    assert D0_CHANGE_CONTROL_PATH.is_file()
    assert R50_CONTRACT_PATH.is_file()

    tracked = "\n".join(
        (
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-20_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-20_000:],
        )
    )
    for forbidden in (
        ".private-handoff",
        "receipt_locator",
        "prompt_plaintext",
        "provider_raw_payload",
        "data:image/",
        "C:\\",
        "D:\\",
    ):
        assert forbidden not in tracked


def test_cc05_d0_principal_acceptance_checkpoint_is_mirrored_and_opens_only_r50() -> None:
    canonical = _last_cc05_d0_acceptance_key_block(ACCEPTANCE_PATH)
    mirror = _last_cc05_d0_acceptance_key_block(EXECUTION_PROTOCOL_PATH)
    values = dict(canonical)

    assert canonical == mirror
    assert len(canonical) == len(values) == 49
    assert values == {
        "CURRENT_STATE_AUTHORITY_VERSION": ("p2-m5-cc05-d0-principal-acceptance-checkpoint-eof/v1"),
        "CURRENT_STATE_CANONICAL_SOURCE": "docs/operations/P2_M5_ACCEPTANCE.md_TRUE_EOF",
        "CURRENT_STATE_MIRROR_SOURCE": ("docs/operations/P2_M5_EXECUTION_PROTOCOL.md_TRUE_EOF"),
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_TRUE_EOF_OVERLAY_SUPERSEDES_CONDITIONAL_D0_AFTER_"
            "E444130A36CDDB06FCA984F55D2BC2F13EAD991_RUN_33265651722_AND_EIGHT_"
            "ARTIFACT_SECURITY_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_MIRROR_RULE": (
            "MUST_MATCH_CANONICAL_D0_ACCEPTANCE_KEY_SET_ORDER_AND_VALUES"
        ),
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "NOT_APPLICABLE_D0_ACCEPTED_R50_IMPLEMENTATION_ONLY_OPEN"
        ),
        "P2_M5_STATE": "EXECUTING",
        "CC_P2_M5_05_D0_STATUS": (
            "TASK_ACCEPTED_AT_E444130A36CDDB06FCA984F55D2BC2F13EAD991_RUN_33265651722"
        ),
        "CC_P2_M5_05_D0_AUTHORITY_CONDITION": (
            "SATISFIED_AFTER_EIGHT_ARTIFACT_INSPECTION_SECURITY_AND_SOL_HIGH_REVIEW"
        ),
        "D0_CANDIDATE_SHA": "E444130A36CDDB06FCA984F55D2BC2F13EAD991",
        "D0_BASELINE_SHA": "F7E4599512A817065B7DBC6D493663409D5D17EF",
        "D0_CI_RUN": "33265651722",
        "D0_CI_ATTEMPT": "1",
        "D0_CI_RESULTS": ("QUALITY_AND_INTEGRATION_PASS;SECRET_SCAN_PASS;DOCKER_VALIDATION_PASS"),
        "D0_ARTIFACT_INSPECTION": ("PASS_8_FAMILIES_11_FILES_EXACT_SHA_BOUND_UNEXPIRED"),
        "D0_FULL_PYTHON": "PASS_768_WITH_1_EXISTING_OPTIONAL_PRIVATE_RUNTIME_SKIP",
        "D0_FROZEN_REGRESSION": ("PHASE1_1_M1_98_M2_52_M3_46_ZERO_FAILURE_ERROR_SKIP"),
        "D0_BROWSER_INTEGRATION": "PASS_5_OF_5",
        "D0_GITLEAKS": "PASS_ZERO_RESULTS",
        "D0_SECURITY_REVIEW": "PASS",
        "D0_SOL_HIGH_FINAL_REVIEW": "PASS",
        "D0_PRINCIPAL_ACCEPTANCE": ("GRANTED_AFTER_ACTUAL_DIFF_ARTIFACT_SECURITY_AND_FINAL_REVIEW"),
        "D0_PRIVATE_CUSTODY_MANIFEST": (
            "PASS_12_FILES_373860_BYTES_SHA256_"
            "EE66BF3C9919B7C62B8D841561E2D559F789F7E69227F5DD050BB93BCB1F285D"
        ),
        "D0_PRIVATE_LOCATOR_IN_TRACKED_EVIDENCE": "FALSE",
        "CAL_REQ_002_STATUS": "CONSUMED_FAILED_NO_RETRY",
        "CAL_REQ_002_FINAL_DISPOSITION": "FAILED_NON_ADMISSIBLE_NO_RETRY",
        "CAL_REQ_002_FAILURE_PHASE": "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE",
        "CAL_REQ_002_FAILURE_REASON": "GENERATED_ARTIFACT_RECEIPT_INVALID",
        "CAL_REQ_002_ATTEMPT_FAILURE_EVIDENCE": ("RECOVERABLE_PROJECT_LOCAL_PRIVATE_CUSTODY"),
        "CAL_REQ_002_RAW_OUTPUT_CUSTODY": "EVIDENCE_LOCATION_LOST",
        "CAL_REQ_002_RETRY": "PROHIBITED",
        "NEXT_UNUSED_FORMAL_ORDINAL": "CAL-REQ-003",
        "FORMAL_CALLS_REMAINING": "30",
        "FORMAL_RAW_CAPACITY_REMAINING": "30",
        "GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING": "61",
        "GLOBAL_NATIVE_OUTPUT_CONSUMED": "3",
        "D0_GENERATION_CALLS": "0",
        "D0_RAW_OUTPUTS_CREATED": "0",
        "D0_IMAGE_BYTES_READ": "0",
        "D0_DECODE_QA_SCREENING_ADMISSION": "0",
        "D0_PRIVATE_ROOTS_CREATED": "0",
        "D0_IMPLEMENTATION_TASK": "P2-M5-R50",
        "D0_NEXT_TASK": "P2-M5-R50_IMPLEMENTATION_ONLY",
        "R50_STATUS": "EXECUTION_READY_IMPLEMENTATION_ONLY",
        "CAL_REQ_003_DISPATCH_AUTHORIZED": "FALSE",
        "P2_M5_TECHNICAL_GATE": "NOT_EVALUATED",
        "P2_MVR_V1_RESULT": "NOT_EVALUATED",
        "P2_M6_ENTRY": "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS",
        "CURRENT_AUTHORITY_TAIL_END": ("P2_M5_CC05_D0_PRINCIPAL_ACCEPTANCE_CHECKPOINT_TRUE_EOF"),
    }
    acceptance_text = ACCEPTANCE_PATH.read_text(encoding="utf-8")
    protocol_text = EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")
    assert acceptance_text.count(canonical[-1][1]) == 1
    assert protocol_text.count(mirror[-1][1]) == 1
    assert acceptance_text.index(canonical[-1][1]) < acceptance_text.index(
        "p2-m5-r50-imagegen-data-url-custody-bridge-eof/v1"
    )
    assert protocol_text.index(mirror[-1][1]) < protocol_text.index(
        "p2-m5-r50-imagegen-data-url-custody-bridge-eof/v1"
    )

    tracked = "\n".join(
        (
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-20_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-20_000:],
        )
    )
    for forbidden in (
        ".private-handoff",
        ".local-storage",
        "receipt_locator",
        "prompt_plaintext",
        "provider_raw_payload",
        "data:image/",
        "C:\\",
        "D:\\",
    ):
        assert forbidden not in tracked


def test_r50_imagegen_data_url_bridge_is_mirrored_conditional_true_eof() -> None:
    canonical = _last_r50_key_block(ACCEPTANCE_PATH)
    mirror = _last_r50_key_block(EXECUTION_PROTOCOL_PATH)
    values = dict(canonical)

    assert canonical == mirror
    assert len(canonical) == len(values) == 60
    assert values == {
        "CURRENT_STATE_AUTHORITY_VERSION": ("p2-m5-r50-imagegen-data-url-custody-bridge-eof/v1"),
        "CURRENT_STATE_CANONICAL_SOURCE": "docs/operations/P2_M5_ACCEPTANCE.md_TRUE_EOF",
        "CURRENT_STATE_MIRROR_SOURCE": ("docs/operations/P2_M5_EXECUTION_PROTOCOL.md_TRUE_EOF"),
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_ACCEPTED_D0_FOR_THE_COMPLETE_"
            "LISTED_KEYSET_ONLY_AFTER_R50_CANDIDATE_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_"
            "CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "CURRENT_STATE_MIRROR_RULE": "MUST_MATCH_CANONICAL_R50_KEY_SET_ORDER_AND_VALUES",
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_D0_REMAINS_CURRENT_UNTIL_R50_AUTHORITY_CONDITION_IS_SATISFIED"
        ),
        "P2_M5_STATE": "EXECUTING",
        "P2_M5_R50": "PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE",
        "P2_M5_R50_BASELINE_SHA": "9243E7F1A74E2A5378DC2F06A04EBA614579CEAD",
        "P2_M5_R50_CHANGE_CLASS": "IMPLEMENTATION_ONLY_ZERO_GENERATION",
        "P2_M5_R50_DIRECT_PATH_API": "PRESERVED",
        "P2_M5_R50_DATA_URL_GRAMMAR": "PASS_STRICT_PNG_JPEG_WEBP_BASE64_ONLY",
        "P2_M5_R50_ENCODED_DECODED_BOUNDS": "PASS",
        "P2_M5_R50_MIME_MAGIC_BINDING": "PASS",
        "P2_M5_R50_DATA_URL_PLAINTEXT_PERSISTED_OR_LOGGED": "FALSE",
        "P2_M5_R50_CAPTURE_STAGING": ("PASS_PROJECT_LOCAL_CREATE_NEW_OR_VERIFY_EXACT"),
        "P2_M5_R50_CAPTURE_SIDECAR": "PASS_MANDATORY_VERIFIED_PRE_DECODE",
        "P2_M5_R50_CRASH_RECOVERY": ("PASS_EXACT_PREDECESSOR_NO_DUPLICATE_COUNTERS"),
        "P2_M5_R50_TERMINAL_ROLLOVER": "PASS_CROSS_ROOT_DERIVED_ONLY",
        "P2_M5_R50_PREDECESSOR_REOPENED": "FALSE",
        "P2_M5_R50_SUCCESSOR_NEXT_UNUSED_ORDINAL": "CAL-REQ-003",
        "P2_M5_R50_FORMAL_CALLS_REMAINING": "30",
        "P2_M5_R50_FORMAL_RAW_CAPACITY_REMAINING": "30",
        "P2_M5_R50_GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING": "61",
        "P2_M5_R50_GLOBAL_NATIVE_OUTPUT_CONSUMED": "3",
        "P2_M5_R50_WINDOWS_FOCUSED": "PASS_65_WITH_2_POSIX_ONLY_SKIPS",
        "P2_M5_R50_LINUX_FOCUSED": ("PASS_67_ZERO_SKIP_NETWORK_NONE_READ_ONLY_SOURCE"),
        "P2_M5_R50_FULL_PYTHON": ("PASS_822_WITH_1_EXISTING_OPTIONAL_PRIVATE_M4_RUNTIME_SKIP"),
        "P2_M5_R50_POSTGRESQL_MIGRATION_LIFECYCLE": ("PASS_BASE_HEAD_BASE_HEAD_CHECK"),
        "P2_M5_R50_RUFF": "PASS_222_FORMATTED_LINT_ZERO",
        "P2_M5_R50_MYPY": "PASS_125_SOURCES",
        "P2_M5_R50_NODE": ("PASS_PRETTIER_ESLINT_TYPESCRIPT_56_VITEST_AND_PRODUCTION_BUILD"),
        "P2_M5_R50_CONTRACT_DRIFT": "PASS_ZERO",
        "P2_M5_R50_LOCAL_PRIVATE_EVIDENCE": ("PASS_PROJECT_LOCAL_GIT_IGNORED_RECOVERABLE_COPY"),
        "P2_M5_R50_PRIVATE_LOCATOR_IN_TRACKED_EVIDENCE": "FALSE",
        "P2_M5_R50_GENERATION_CALLS": "0",
        "P2_M5_R50_RAW_OUTPUTS_CREATED": "0",
        "P2_M5_R50_IMAGE_DECODE_CALLS": "0",
        "P2_M5_R50_DIMENSIONS_READ": "0",
        "P2_M5_R50_QA_SCREENING_ADMISSION": "0",
        "P2_M5_R50_SECURITY_REVIEW": "REQUIRED_BEFORE_PRINCIPAL_ACCEPTANCE",
        "P2_M5_R50_SOL_HIGH_FINAL_REVIEW": "REQUIRED_BEFORE_PRINCIPAL_ACCEPTANCE",
        "P2_M5_R50_PRINCIPAL_ACCEPTANCE": "NOT_GRANTED",
        "CAL_REQ_002_STATUS": "CONSUMED_FAILED_NO_RETRY",
        "CAL_REQ_002_FINAL_DISPOSITION": "FAILED_NON_ADMISSIBLE_NO_RETRY",
        "CAL_REQ_002_FAILURE_PHASE": "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE",
        "CAL_REQ_002_FAILURE_REASON": "GENERATED_ARTIFACT_RECEIPT_INVALID",
        "CAL_REQ_002_RAW_OUTPUT_CUSTODY": "EVIDENCE_LOCATION_LOST",
        "CAL_REQ_002_RETRY": "PROHIBITED",
        "NEXT_UNUSED_FORMAL_ORDINAL": "CAL-REQ-003",
        "FORMAL_CALLS_REMAINING": "30",
        "FORMAL_RAW_CAPACITY_REMAINING": "30",
        "GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING": "61",
        "GLOBAL_NATIVE_OUTPUT_CONSUMED": "3",
        "CAL_REQ_003_DISPATCH_AUTHORIZED": "FALSE",
        "P2_M5_TECHNICAL_GATE": "NOT_EVALUATED",
        "P2_MVR_V1_RESULT": "NOT_EVALUATED",
        "P2_M6_ENTRY": "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS",
        "P2_M5_R50_NEXT_TASK": "R50_CANDIDATE_SAME_SHA_GATES",
        "CURRENT_AUTHORITY_TAIL_END": ("P2_M5_R50_IMAGEGEN_DATA_URL_CUSTODY_BRIDGE_TRUE_EOF"),
    }
    tracked = "\n".join(
        (
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-25_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-25_000:],
        )
    )
    for forbidden in (
        ".private-handoff",
        ".local-storage",
        "receipt_locator",
        "prompt_plaintext",
        "provider_raw_payload",
        "data:image/",
        "C:\\",
        "D:\\",
    ):
        assert forbidden not in tracked


def test_r51_freezes_one_exact_post_acceptance_successor_at_true_eof() -> None:
    canonical = _last_r51_key_block(ACCEPTANCE_PATH)
    mirror = _last_r51_key_block(EXECUTION_PROTOCOL_PATH)
    values = dict(canonical)

    assert canonical == mirror
    assert len(canonical) == len(values) == 41
    assert values == {
        "CURRENT_STATE_AUTHORITY_VERSION": (
            "p2-m5-r51-r50-post-acceptance-successor-authority-eof/v1"
        ),
        "CURRENT_STATE_CANONICAL_SOURCE": "docs/operations/P2_M5_ACCEPTANCE.md_TRUE_EOF",
        "CURRENT_STATE_MIRROR_SOURCE": "docs/operations/P2_M5_EXECUTION_PROTOCOL.md_TRUE_EOF",
        "CURRENT_STATE_AUTHORITY_PRECEDENCE": (
            "THIS_CONDITIONAL_TRUE_EOF_OVERLAY_SUPERSEDES_REJECTED_R50_SUCCESSOR_TAIL_FOR_"
            "THE_COMPLETE_LISTED_KEYSET_ONLY_AFTER_R51_CANDIDATE_SAME_SHA_CI_EIGHT_"
            "ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_"
            "ACCEPTANCE"
        ),
        "CURRENT_STATE_MIRROR_RULE": "MUST_MATCH_CANONICAL_R51_KEY_SET_ORDER_AND_VALUES",
        "CURRENT_STATE_PRECONDITION_FALLBACK": (
            "ACCEPTED_D0_REMAINS_CURRENT_AND_CAL_REQ_003_DISPATCH_UNAUTHORIZED_UNTIL_R51_"
            "AUTHORITY_CONDITION_IS_SATISFIED"
        ),
        "P2_M5_STATE": "EXECUTING",
        "P2_M5_R50": "TASK_ACCEPTED_WITH_R51_AFTER_R51_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE",
        "P2_M5_R50_PRINCIPAL_ACCEPTANCE": (
            "GRANTED_WITH_R51_AFTER_R51_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "P2_M5_R51": "PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE",
        "P2_M5_R51_TASK_ID": "P2-M5-R51",
        "P2_M5_R51_PARENT_CANDIDATE_SHA": "9D2DDB103F774128E3515A4261983F91C1B5F2F9",
        "P2_M5_R51_PARENT_CI_RUN": "33290944703_ATTEMPT_1",
        "P2_M5_R51_PARENT_CI_RESULTS": (
            "QUALITY_AND_INTEGRATION_PASS;SECRET_SCAN_PASS;DOCKER_VALIDATION_PASS"
        ),
        "P2_M5_R51_PARENT_ARTIFACT_INSPECTION": (
            "PASS_8_FAMILIES_11_FILES_EXACT_SHA_BOUND_UNEXPIRED"
        ),
        "P2_M5_R51_PARENT_SECURITY_REVIEW": "PASS",
        "P2_M5_R51_PARENT_SOL_HIGH_FINAL_REVIEW": ("FAIL_POST_ACCEPTANCE_SUCCESSOR_AUTHORITY"),
        "P2_M5_R51_PARENT_PRINCIPAL_ACCEPTANCE": ("DENIED_PENDING_R51_CURRENT_AUTHORITY_REPAIR"),
        "P2_M5_R51_FAILURE_CLASS": "POST_ACCEPTANCE_SUCCESSOR_AUTHORITY_CONFLICT",
        "P2_M5_R51_REPAIR_SCOPE": "R50_POST_ACCEPTANCE_SUCCESSOR_AUTHORITY_ONLY",
        "P2_M5_R51_SUCCESSOR_SELECTION": "A_DIRECT_ONE_EXACT_CALL",
        "P2_M5_R51_POST_ACCEPTANCE_COMMIT_REQUIRED": "NO",
        "P2_M5_R51_GENERATION_CALLS": "0",
        "P2_M5_R51_ORDINALS_CONSUMED": "0",
        "P2_M5_R51_RAW_OUTPUTS_CREATED": "0",
        "P2_M5_R51_IMAGE_BYTES_READ": "0",
        "P2_M5_R51_DECODE_QA_SCREENING_ADMISSION": "0",
        "P2_M5_R51_RUNTIME_SCHEMA_API_DEPENDENCY_WORKFLOW_CHANGE": "NONE",
        "CAL_REQ_002_STATUS": "CONSUMED_FAILED_NO_RETRY",
        "CAL_REQ_002_RETRY": "PROHIBITED",
        "NEXT_UNUSED_FORMAL_ORDINAL": "CAL-REQ-003",
        "FORMAL_CALLS_REMAINING": "30",
        "FORMAL_RAW_CAPACITY_REMAINING": "30",
        "GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING": "61",
        "GLOBAL_NATIVE_OUTPUT_CONSUMED": "3",
        "CAL_REQ_003_DISPATCH_AUTHORIZED": "TRUE_FOR_ONE_EXACT_CALL",
        "NEXT_READY_TASK": "EXECUTE_CAL_REQ_003",
        "P2_M5_TECHNICAL_GATE": "NOT_EVALUATED",
        "P2_MVR_V1_RESULT": "NOT_EVALUATED",
        "P2_M6_ENTRY": "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS",
        "CURRENT_AUTHORITY_TAIL_END": (
            "P2_M5_R51_R50_POST_ACCEPTANCE_SUCCESSOR_AUTHORITY_REPAIR_TRUE_EOF"
        ),
    }
    acceptance_text = ACCEPTANCE_PATH.read_text(encoding="utf-8")
    execution_text = EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")
    assert (
        canonical[-1][1]
        + "\n\n## Current authoritative state — P2-M5-R52 no-echo private ImageGen transport repair"
        in acceptance_text
    )
    assert (
        mirror[-1][1] + "\n\n## Current authoritative state mirror — P2-M5-R52 "
        "no-echo private ImageGen transport repair" in execution_text
    )


def test_r52_records_cal_req_003_failure_and_freezes_exact_post_acceptance_successor() -> None:
    canonical = _last_r52_key_block(ACCEPTANCE_PATH)
    mirror = _last_r52_key_block(EXECUTION_PROTOCOL_PATH)
    values = dict(canonical)

    assert canonical == mirror
    assert len(canonical) == len(values) == 63
    assert values["CURRENT_STATE_PRECONDITION_FALLBACK"] == (
        "CAL_REQ_003_TERMINAL_FAILURE_IS_CURRENT_R52_REPAIR_EXECUTES_ZERO_GENERATION_AND_"
        "CAL_REQ_004_REMAINS_UNAUTHORIZED_UNTIL_R52_AUTHORITY_CONDITION_IS_SATISFIED"
    )
    assert values["P2_M5_R50"] == ("TASK_ACCEPTED_AT_7EA62E9184EA163075043A9AE87BA7284B3F4772")
    assert values["P2_M5_R51_PRINCIPAL_ACCEPTANCE"] == "GRANTED"
    assert values["CAL_REQ_003_STATUS"] == "CONSUMED_FAILED_NO_RETRY"
    assert values["CAL_REQ_003_FAILURE_PHASE"] == ("OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE")
    assert values["CAL_REQ_003_FAILURE_REASON"] == "IMAGEGEN_DATA_URL_HEADER_INVALID"
    assert values["CAL_REQ_003_RAW_OUTPUT_CUSTODY"] == "EVIDENCE_LOCATION_LOST"
    assert values["CAL_REQ_003_RETRY"] == "PROHIBITED"
    assert values["CAL_REQ_003_DECODE_PERFORMED"] == "FALSE"
    assert values["CAL_REQ_003_DIMENSIONS_READ"] == "FALSE"
    assert values["CAL_REQ_003_QA_SCREENING_ADMISSION"] == "0"
    assert values["NEXT_UNUSED_FORMAL_ORDINAL"] == "CAL-REQ-004"
    assert values["FORMAL_CALLS_REMAINING"] == "29"
    assert values["FORMAL_RAW_CAPACITY_REMAINING"] == "29"
    assert values["GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING"] == "60"
    assert values["GLOBAL_NATIVE_OUTPUT_CONSUMED"] == "4"
    assert values["P2_M5_R52_CHANGE_CLASS"] == ("BOUNDED_PRIVATE_TRANSPORT_ORCHESTRATION_REPAIR")
    assert values["P2_M5_R52_TRANSPORT"] == ("TTY_REQUIRED_NO_ECHO_BOUNDED_COMPLETE_ASCII_ONE_LINE")
    assert values["P2_M5_R52_FOCUSED_TESTS"] == "PASS_35_ZERO_SKIP"
    assert values["P2_M5_R52_FULL_REGRESSION"] == "PASS_CANONICAL_LF_CHECKOUT"
    assert values["P2_M5_R52_DATA_URL_PLAINTEXT_PERSISTED_OR_LOGGED"] == "FALSE"
    assert values["P2_M5_R52_GENERATION_CALLS"] == "0"
    assert values["P2_M5_R52_RAW_OUTPUTS_CREATED"] == "0"
    assert values["P2_M5_R52_IMAGE_DECODE_CALLS"] == "0"
    assert values["P2_M5_R52_QA_SCREENING_ADMISSION"] == "0"
    assert values["P2_M5_R52_PRINCIPAL_ACCEPTANCE"] == "NOT_GRANTED"
    assert values["P2_M5_R52"] == ("PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE")
    assert values["CAL_REQ_004_DISPATCH_AUTHORIZED"] == (
        "TRUE_FOR_ONE_EXACT_CALL_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["CC04_B_EXECUTION"] == (
        "READY_FOR_ONE_EXACT_CAL_REQ_004_CALL_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["FORMAL_E01_STATUS"] == (
        "READY_TO_EXECUTE_CAL_REQ_004_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["P2_M5_NEXT_ACTION"] == "EXECUTE_CAL_REQ_004"
    assert values["NEXT_READY_TASK"] == "EXECUTE_CAL_REQ_004"
    assert values["STOP_OUTCOME"] == (
        "NONE_AFTER_R52_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE_ELSE_R52_PENDING_GATES"
    )
    assert values["POST_ACCEPTANCE_COMMIT_REQUIRED"] == "NO"
    contract_text = R52_CONTRACT_PATH.read_text(encoding="utf-8")
    assert (
        "CAL_REQ_004_DISPATCH_AUTHORIZED: "
        "TRUE_FOR_ONE_EXACT_CALL_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
        in contract_text
    )
    assert values["P2_M5_TECHNICAL_GATE"] == "NOT_EVALUATED"
    assert values["P2_MVR_V1_RESULT"] == "NOT_EVALUATED"
    assert values["P2_M6_ENTRY"] == "CLOSED_PENDING_TECHNICAL_AND_MVR_PASS"
    assert values["CURRENT_AUTHORITY_TAIL_END"] == (
        "P2_M5_R52_PRIVATE_IMAGEGEN_NO_ECHO_TRANSPORT_TRUE_EOF"
    )
    acceptance_text = ACCEPTANCE_PATH.read_text(encoding="utf-8")
    protocol_text = EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")
    assert canonical[-1][1] + "\n\n## Current authoritative state — P2-M5-R53" in acceptance_text
    assert mirror[-1][1] + "\n\n## Current authoritative state mirror — P2-M5-R53" in protocol_text

    tracked = "\n".join(
        (
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-30_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-30_000:],
        )
    )
    for forbidden in (
        "data:image/",
        "prompt_plaintext",
        "signed_url",
        "object_key",
        "D:\\p-worktrees\\",
    ):
        assert forbidden not in tracked


def test_r53_v2_rollover_authority_is_mirrored_at_true_eof_without_private_data() -> None:
    canonical = _last_r53_key_block(ACCEPTANCE_PATH)
    mirror = _last_r53_key_block(EXECUTION_PROTOCOL_PATH)
    values = dict(canonical)

    assert canonical == mirror
    assert len(canonical) == len(values)
    assert values["CURRENT_STATE_PRECONDITION_FALLBACK"] == (
        "CAL_REQ_003_TERMINAL_FAILURE_REMAINS_CURRENT_CAL_REQ_004_READY_OVERLAY_IS_NON_"
        "AUTHORIZING_AND_CAL_REQ_004_DISPATCH_REMAINS_UNAUTHORIZED_UNTIL_R53_AUTHORITY_"
        "CONDITION_IS_SATISFIED"
    )
    assert values["P2_M5_R52"] == (
        "TASK_ACCEPTED_WITH_R53_AFTER_R53_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["P2_M5_R52_PARENT_CANDIDATE_SHA"] == ("ACFA47D9DACFA76C38EADB11D5882F5D9A72B3BA")
    assert values["P2_M5_R52_PARENT_CI_ARTIFACTS_SECURITY"] == "PASS"
    assert values["P2_M5_R52_PARENT_SOL_HIGH_FINAL_REVIEW"] == (
        "FAIL_POST_ACCEPTANCE_PRE_READY_AUTHORITY"
    )
    assert values["P2_M5_R53_FOCUSED_TESTS"] == "PASS_119_ZERO_SKIP"
    assert values["P2_M5_R53_FULL_REGRESSION"] == (
        "PASS_CANONICAL_LF_851_TOTAL_689_PASS_162_ENVIRONMENT_GATED_SKIP_ZERO_FAILURE_ERROR"
    )
    assert values["P2_M5_R53_GENERATION_CALLS"] == "0"
    assert values["P2_M5_R53_ORDINALS_CONSUMED"] == "0"
    assert values["P2_M5_R53_IMAGE_BYTES_READ"] == "0"
    assert values["P2_M5_R53_IMAGE_DECODE_CALLS"] == "0"
    assert values["P2_M5_R53_QA_SCREENING_ADMISSION"] == "0"
    assert values["NEXT_UNUSED_FORMAL_ORDINAL"] == "CAL-REQ-004"
    assert values["CAL_REQ_004_STATUS"] == "NOT_CONSUMED"
    assert values["CAL_REQ_004_DISPATCH_AUTHORIZED"] == (
        "TRUE_FOR_ONE_EXACT_CALL_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_R53_CAL_REQ_004_READY_ROLLOVER_TRUE_EOF",
    )
    acceptance_text = ACCEPTANCE_PATH.read_text(encoding="utf-8")
    protocol_text = EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")
    assert canonical[-1][1] + "\n\n## Current authoritative state — P2-M5-R54" in acceptance_text
    assert mirror[-1][1] + "\n\n## Current authoritative state mirror — P2-M5-R54" in protocol_text
    tracked = "\n".join(
        (
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-20_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-20_000:],
        )
    )
    for forbidden in (
        "data:image/",
        "prompt_plaintext",
        "signed_url",
        "object_key",
        "D:\\p-worktrees\\",
    ):
        assert forbidden not in tracked


def test_r54_empty_directory_integrity_authority_is_mirrored_at_true_eof() -> None:
    canonical = _last_r54_key_block(ACCEPTANCE_PATH)
    mirror = _last_r54_key_block(EXECUTION_PROTOCOL_PATH)
    values = dict(canonical)

    assert canonical == mirror
    assert len(canonical) == len(values)
    assert values["P2_M5_R53_PARENT_CANDIDATE_SHA"] == ("89136D12CB6C3666680C3128AEF2FD55C978CC8D")
    assert values["P2_M5_R53_PARENT_SECURITY_REVIEW"] == (
        "FAIL_SUCCESSOR_WORK_DIRECTORIES_NOT_PROVEN_EMPTY"
    )
    assert values["P2_M5_R53_PARENT_SOL_HIGH_FINAL_REVIEW"] == "PASS"
    assert values["P2_M5_R54_REPAIR_SCOPE"] == (
        "STAGING_RECORDS_BOUNDED_ZERO_ENTRY_PROOF_CREATE_RECOVER_VERIFY_AND_TRUE_EOF_ONLY"
    )
    assert values["P2_M5_R54_DIRECTORY_PROBE"] == (
        "BOUNDED_FIRST_ENTRY_EXISTENCE_ONLY_NO_NAME_ATTRIBUTE_OR_PAYLOAD_ACCESS"
    )
    assert values["P2_M5_R54_PREPOPULATED_PARTIAL_RECOVERY"] == ("REJECTED_BEFORE_SEQUENCE_ZERO")
    assert values["P2_M5_R54_GENERATION_CALLS"] == "0"
    assert values["P2_M5_R54_ORDINALS_CONSUMED"] == "0"
    assert values["P2_M5_R54_IMAGE_BYTES_READ"] == "0"
    assert values["P2_M5_R54_DIRECTORY_PAYLOAD_BYTES_READ"] == "0"
    assert values["P2_M5_R54_FOCUSED_TESTS"] == "PASS_125_ZERO_SKIP"
    assert values["P2_M5_R54_FULL_REGRESSION"] == (
        "PASS_CANONICAL_LF_857_TOTAL_695_PASS_162_ENVIRONMENT_GATED_SKIP_ZERO_FAILURE_ERROR"
    )
    assert values["NEXT_UNUSED_FORMAL_ORDINAL"] == "CAL-REQ-004"
    assert values["CAL_REQ_004_STATUS"] == "NOT_CONSUMED"
    assert values["CAL_REQ_004_DISPATCH_AUTHORIZED"] == (
        "TRUE_FOR_ONE_EXACT_CALL_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE"
    )
    assert values["NEXT_READY_TASK"] == "EXECUTE_CAL_REQ_004"
    assert values["POST_ACCEPTANCE_COMMIT_REQUIRED"] == "NO"
    assert canonical[-1] == (
        "CURRENT_AUTHORITY_TAIL_END",
        "P2_M5_R54_ROLLOVER_EMPTY_DIRECTORY_INTEGRITY_TRUE_EOF",
    )
    assert ACCEPTANCE_PATH.read_text(encoding="utf-8").rstrip().endswith(canonical[-1][1])
    assert EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8").rstrip().endswith(mirror[-1][1])

    contract = R54_CONTRACT_PATH.read_text(encoding="utf-8")
    assert "never reads `DirEntry.name`, returns, logs or includes the" in contract
    assert "no post-acceptance status commit is required" in contract
    tracked = "\n".join(
        (
            ACCEPTANCE_PATH.read_text(encoding="utf-8")[-24_000:],
            EXECUTION_PROTOCOL_PATH.read_text(encoding="utf-8")[-24_000:],
            contract,
        )
    )
    for forbidden in (
        "data:image/",
        "prompt_plaintext",
        "signed_url",
        "object_key",
        "D:\\p-worktrees\\",
    ):
        assert forbidden not in tracked
