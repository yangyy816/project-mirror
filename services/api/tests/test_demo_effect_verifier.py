import hashlib

import pytest

from mirror_api.demo_effect_verifier import (
    EffectVerificationInput,
    EffectVerifierPolicy,
    VerificationCategory,
    VerificationStatus,
    verify_effect,
)


def _policy() -> EffectVerifierPolicy:
    return EffectVerifierPolicy(
        target_tolerance_ppm=5,
        structural_drift_thresholds_ppm={"chin_height": 3, "eye_spacing": 3, "jaw_width": 3},
        locked_drift_thresholds_ppm={"chin_height": 2, "eye_spacing": 2, "jaw_width": 2},
        non_target_drift_threshold_ppm=4,
        allowed_media_types=("image/jpeg", "image/png"),
    )


def _facts(**changes: object) -> EffectVerificationInput:
    content = b"verified-result"
    values: dict[str, object] = {
        "source_asset_id": "source.asset",
        "result_asset_id": "result.asset",
        "target_dimension_key": "jaw_width",
        "operation_digest": "c" * 64,
        "requested_delta_ppm": 20,
        "measured_delta_ppm": 25,
        "structural_drifts_ppm": {"jaw_width": 1, "chin_height": -2, "eye_spacing": 0},
        "locked_drifts_ppm": {"jaw_width": 1, "chin_height": -2, "eye_spacing": 0},
        "non_target_drift_ppm": -4,
        "artifact_status": "PASS",
        "artifact_codes": (),
        "original_before_sha256": "a" * 64,
        "original_after_sha256": "a" * 64,
        "result_bytes": content,
        "declared_result_sha256": hashlib.sha256(content).hexdigest(),
        "decode_valid": True,
        "width": 10,
        "height": 11,
        "media_type": "image/png",
    }
    values.update(changes)
    return EffectVerificationInput(**values)


def _category(result: object, category: VerificationCategory):
    return next(item for item in result.categories if item.category is category)


def test_all_categories_pass_and_only_pass_is_publishable() -> None:
    result = verify_effect(_policy(), _facts())
    assert result.status is VerificationStatus.PASS
    assert result.publishable is True
    assert result.identity_claim_scope == "STRUCTURAL_ONLY_NOT_BIOMETRIC_IDENTITY_VERIFICATION"
    assert [item.category.value for item in result.categories] == [
        item.value for item in VerificationCategory
    ]
    assert all(item.status is VerificationStatus.PASS for item in result.categories)


@pytest.mark.parametrize(
    ("change", "category"),
    [
        (
            {"structural_drifts_ppm": {"jaw_width": 4, "chin_height": 0, "eye_spacing": 0}},
            VerificationCategory.STRUCTURAL_IDENTITY_CONSTRAINTS,
        ),
        (
            {"locked_drifts_ppm": {"jaw_width": 3, "chin_height": 0, "eye_spacing": 0}},
            VerificationCategory.LOCK_PRESERVATION,
        ),
        ({"measured_delta_ppm": -20}, VerificationCategory.TARGET_DELTA),
        ({"non_target_drift_ppm": 5}, VerificationCategory.NON_TARGET_DRIFT),
        ({"artifact_codes": ("RINGING",)}, VerificationCategory.ARTIFACT),
        ({"original_after_sha256": "b" * 64}, VerificationCategory.ORIGINAL_IMMUTABILITY),
        ({"decode_valid": False}, VerificationCategory.DECODE_VALIDITY),
    ],
)
def test_each_category_fails_closed(
    change: dict[str, object], category: VerificationCategory
) -> None:
    result = verify_effect(_policy(), _facts(**change))
    assert _category(result, category).status is VerificationStatus.FAIL
    assert result.status is VerificationStatus.FAIL
    assert result.publishable is False


def test_artifact_human_review_is_not_publishable_and_fail_wins() -> None:
    review = verify_effect(_policy(), _facts(artifact_status="HUMAN_REVIEW"))
    assert (
        _category(review, VerificationCategory.ARTIFACT).status is VerificationStatus.HUMAN_REVIEW
    )
    assert review.status is VerificationStatus.HUMAN_REVIEW
    assert review.publishable is False
    codes_win = verify_effect(
        _policy(), _facts(artifact_status="HUMAN_REVIEW", artifact_codes=("RINGING",))
    )
    assert _category(codes_win, VerificationCategory.ARTIFACT).status is VerificationStatus.FAIL
    failed = verify_effect(_policy(), _facts(artifact_status="HUMAN_REVIEW", width=0))
    assert failed.status is VerificationStatus.FAIL


def test_boundaries_zero_target_invalid_facts_and_tamper_fail_closed() -> None:
    assert (
        verify_effect(_policy(), _facts(requested_delta_ppm=0, measured_delta_ppm=-5)).status
        is VerificationStatus.PASS
    )
    assert (
        verify_effect(_policy(), _facts(requested_delta_ppm=0, measured_delta_ppm=6)).status
        is VerificationStatus.FAIL
    )
    assert (
        verify_effect(_policy(), _facts(measured_delta_ppm=True)).status is VerificationStatus.FAIL
    )
    assert (
        verify_effect(_policy(), _facts(structural_drifts_ppm={"jaw_width": 0.0})).status
        is VerificationStatus.FAIL
    )
    assert (
        verify_effect(_policy(), _facts(declared_result_sha256="0" * 64)).status
        is VerificationStatus.FAIL
    )
    assert (
        verify_effect(_policy(), _facts(source_asset_id="same", result_asset_id="same")).status
        is VerificationStatus.FAIL
    )
    assert (
        verify_effect(_policy(), _facts(media_type="image/gif")).status is VerificationStatus.FAIL
    )


@pytest.mark.parametrize("dimension", ("jaw_width", "chin_height", "eye_spacing"))
def test_target_delta_accepts_each_supported_dimension(dimension: str) -> None:
    assert (
        verify_effect(_policy(), _facts(target_dimension_key=dimension)).status
        is VerificationStatus.PASS
    )


def test_target_delta_rejects_unknown_dimension_and_invalid_operation_digest() -> None:
    unknown = verify_effect(_policy(), _facts(target_dimension_key="nose_width"))
    invalid_digest = verify_effect(_policy(), _facts(operation_digest="not-a-digest"))
    assert _category(unknown, VerificationCategory.TARGET_DELTA).status is VerificationStatus.FAIL
    assert (
        _category(invalid_digest, VerificationCategory.TARGET_DELTA).status
        is VerificationStatus.FAIL
    )


def test_empty_lock_set_is_a_normal_pass_state() -> None:
    policy = EffectVerifierPolicy(
        target_tolerance_ppm=5,
        structural_drift_thresholds_ppm={"jaw_width": 3},
        locked_drift_thresholds_ppm={},
        non_target_drift_threshold_ppm=4,
        allowed_media_types=("image/png",),
    )
    result = verify_effect(
        policy,
        _facts(
            structural_drifts_ppm={"jaw_width": 1},
            locked_drifts_ppm={},
        ),
    )
    assert (
        _category(result, VerificationCategory.LOCK_PRESERVATION).status is VerificationStatus.PASS
    )


def test_digests_are_deterministic_and_policy_is_immutable() -> None:
    facts = _facts()
    first = verify_effect(_policy(), facts)
    second = verify_effect(_policy(), facts)
    assert first.content_digest() == second.content_digest()
    assert first.request_digest == second.request_digest
    with pytest.raises(TypeError):
        _policy().structural_drift_thresholds_ppm["jaw_width"] = 99  # type: ignore[index]
