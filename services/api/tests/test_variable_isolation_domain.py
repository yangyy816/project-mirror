from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from mirror_api.synthetic_dataset import (
    COHORT_STAGES,
    CohortAssignment,
    ControlDelta,
    EvaluationDimensionRule,
    EvaluationSplit,
    IsolationConclusion,
    IsolationObservation,
    M5Outcome,
    M5ReasonCode,
    M5ValidationError,
    MvrResult,
    SyntheticEvaluationPolicy,
    TechnicalGateResult,
    effective_holdout_count,
    evaluate_isolation,
    next_cohort_stage,
    validate_split_authority,
)


def _rule(**overrides: object) -> EvaluationDimensionRule:
    values: dict[str, object] = {
        "dimension_key": "jaw_width",
        "region_group": "lower_face",
        "control_dimensions": ("eye_spacing", "nose_width"),
        "target_error_tolerance_ppm": 20_000,
        "control_drift_tolerance_ppm": 10_000,
        "repeat_variance_tolerance_ppm": 100,
        "platform_variance_tolerance_ppm": 200,
    }
    values.update(overrides)
    return EvaluationDimensionRule(**values)  # type: ignore[arg-type]


def _policy(**overrides: object) -> SyntheticEvaluationPolicy:
    values: dict[str, object] = {
        "version": "synthetic-evaluation-v1",
        "ontology_version": "geometry-ontology-v2",
        "ontology_digest": "a" * 64,
        "measurement_policy_version": "geometry-measurement-v1",
        "isolation_algorithm_version": "variable-isolation-v1",
        "duplicate_algorithm_version": "first-party-phash-v1",
        "split_rule_version": "identity-cluster-split-v1",
        "dimension_rules": (_rule(),),
    }
    values.update(overrides)
    return SyntheticEvaluationPolicy.create(**values)  # type: ignore[arg-type]


def _observation(policy: SyntheticEvaluationPolicy, **overrides: object) -> IsolationObservation:
    values: dict[str, object] = {
        "transform_run_reference": "transform-run-01",
        "policy_version": policy.version,
        "policy_digest": policy.content_digest,
        "target_dimension": "jaw_width",
        "requested_delta_ppm": 30_000,
        "measured_delta_ppm": 28_000,
        "control_deltas": (
            ControlDelta("eye_spacing", 2_000),
            ControlDelta("nose_width", 3_000),
        ),
        "repeat_variance_ppm": 50,
        "platform_variance_ppm": 75,
        "artifact_gate_passed": True,
        "reliability_gate_passed": True,
    }
    values.update(overrides)
    return IsolationObservation(**values)  # type: ignore[arg-type]


def _assignment(
    suffix: str,
    *,
    split: EvaluationSplit = EvaluationSplit.HOLDOUT,
    cluster: str | None = None,
    identity: str | None = None,
    asset: str | None = None,
    sha256: str | None = None,
    dimensions: tuple[str, ...] = ("jaw_width",),
) -> CohortAssignment:
    return CohortAssignment(
        assignment_reference=f"assignment-{suffix}",
        identity_reference=identity or f"identity-{suffix}",
        source_asset_reference=asset or f"asset-{suffix}",
        source_asset_sha256=sha256 or (suffix[-1].lower() * 64),
        duplicate_cluster_reference=cluster,
        split=split,
        dimension_keys=dimensions,
    )


def test_policy_digest_is_deterministic_and_rules_are_canonical() -> None:
    jaw = _rule()
    eye = _rule(
        dimension_key="eye_spacing",
        region_group="eye_region",
        control_dimensions=("jaw_width", "nose_width"),
    )

    first = _policy(dimension_rules=(jaw, eye))
    second = _policy(dimension_rules=(eye, jaw))

    assert first == second
    assert tuple(rule.dimension_key for rule in first.dimension_rules) == (
        "eye_spacing",
        "jaw_width",
    )
    assert first.cohort_stages == COHORT_STAGES
    assert len(first.content_digest) == 64


def test_policy_tampering_fails_without_echoing_submitted_content() -> None:
    policy = _policy()
    marker = "private-policy-marker"

    with pytest.raises(M5ValidationError) as error:
        replace(policy, split_rule_version=marker, content_digest="f" * 64)

    assert error.value.reason_code in {
        M5ReasonCode.INVALID_POLICY,
        M5ReasonCode.CONTENT_DIGEST_MISMATCH,
    }
    assert marker not in str(error.value)


@pytest.mark.parametrize(
    "region_group",
    [
        "race_group",
        "beauty_region",
        "nationality_group",
        "age_region",
        "adult_group",
        "UpperFace",
        "",
    ],
)
def test_region_group_is_non_sensitive_and_canonical(region_group: str) -> None:
    with pytest.raises(M5ValidationError) as error:
        _rule(region_group=region_group)
    assert error.value.reason_code is M5ReasonCode.INVALID_REGION_GROUP


@pytest.mark.parametrize("value", [-1, 1_000_001, True, float("nan")])
def test_thresholds_are_integer_ppm_and_bounded(value: object) -> None:
    with pytest.raises(M5ValidationError) as error:
        _rule(target_error_tolerance_ppm=value)
    assert error.value.reason_code is M5ReasonCode.INVALID_POLICY


def test_policy_requires_fixed_cohort_stages_and_unique_dimensions() -> None:
    policy = _policy()
    with pytest.raises(M5ValidationError) as stages:
        replace(policy, cohort_stages=(24, 48), content_digest="f" * 64)
    assert stages.value.reason_code is M5ReasonCode.INVALID_COHORT_STAGE

    with pytest.raises(M5ValidationError) as duplicate:
        _policy(dimension_rules=(_rule(), _rule()))
    assert duplicate.value.reason_code is M5ReasonCode.INVALID_POLICY


@pytest.mark.parametrize("leak_key", ["identity", "asset", "sha256", "cluster"])
def test_split_authority_rejects_all_leakage_axes(leak_key: str) -> None:
    shared: dict[str, object] = {}
    if leak_key == "identity":
        shared["identity"] = "identity-shared"
    elif leak_key == "asset":
        shared["asset"] = "asset-shared"
    elif leak_key == "sha256":
        shared["sha256"] = "a" * 64
    else:
        shared["cluster"] = "cluster-shared"
    calibration = _assignment(
        "a",
        split=EvaluationSplit.CALIBRATION,
        **shared,  # type: ignore[arg-type]
    )
    holdout = _assignment(
        "b",
        split=EvaluationSplit.HOLDOUT,
        **shared,  # type: ignore[arg-type]
    )

    with pytest.raises(M5ValidationError) as error:
        validate_split_authority((calibration, holdout))
    assert error.value.reason_code is M5ReasonCode.SPLIT_LEAKAGE


def test_effective_holdout_count_is_per_dimension_and_cluster_adjusted() -> None:
    assignments = (
        _assignment("a", cluster="cluster-one"),
        _assignment("b", cluster="cluster-one"),
        _assignment("c"),
        _assignment(
            "d",
            split=EvaluationSplit.CALIBRATION,
            dimensions=("jaw_width", "nose_width"),
        ),
        _assignment("e", dimensions=("nose_width",)),
    )

    assert effective_holdout_count(assignments, dimension_key="jaw_width") == 2
    assert effective_holdout_count(assignments, dimension_key="nose_width") == 1


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 24), (23, 24), (24, 48), (47, 48), (48, 96), (95, 96), (96, None)],
)
def test_cohort_progression_is_fixed_and_stops_at_96(count: int, expected: int | None) -> None:
    assert next_cohort_stage(count) == expected


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_invalid_cohort_counts_fail_closed(count: object) -> None:
    with pytest.raises(M5ValidationError) as error:
        next_cohort_stage(count)  # type: ignore[arg-type]
    assert error.value.reason_code is M5ReasonCode.INVALID_COHORT_STAGE


def test_isolation_pass_retains_actual_measurements_and_is_deterministic() -> None:
    policy = _policy()
    observation = _observation(policy)

    first = evaluate_isolation(policy=policy, observation=observation)
    second = evaluate_isolation(policy=policy, observation=observation)

    assert first == second
    assert first.conclusion is IsolationConclusion.PASSED
    assert first.target_error_ppm == 2_000
    assert first.non_target_drift_ppm == 3_000
    assert first.reason_codes == ()


def test_extreme_opposite_direction_is_a_rejection_not_an_evaluator_crash() -> None:
    policy = _policy()
    observation = _observation(
        policy,
        requested_delta_ppm=5_000_000,
        measured_delta_ppm=-5_000_000,
    )

    result = evaluate_isolation(policy=policy, observation=observation)

    assert result.conclusion is IsolationConclusion.REJECTED
    assert result.target_error_ppm == 10_000_000
    assert M5ReasonCode.TARGET_DIRECTION_MISMATCH in result.reason_codes
    assert M5ReasonCode.TARGET_ERROR_EXCEEDED in result.reason_codes


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"measured_delta_ppm": -28_000}, M5ReasonCode.TARGET_DIRECTION_MISMATCH),
        ({"measured_delta_ppm": 1_000}, M5ReasonCode.TARGET_ERROR_EXCEEDED),
        (
            {
                "control_deltas": (
                    ControlDelta("eye_spacing", 2_000),
                    ControlDelta("nose_width", 20_000),
                )
            },
            M5ReasonCode.CONTROL_DRIFT_EXCEEDED,
        ),
        ({"repeat_variance_ppm": 101}, M5ReasonCode.REPEAT_VARIANCE_EXCEEDED),
        ({"platform_variance_ppm": 201}, M5ReasonCode.PLATFORM_VARIANCE_EXCEEDED),
        ({"artifact_gate_passed": False}, M5ReasonCode.ARTIFACT_GATE_FAILED),
        ({"reliability_gate_passed": False}, M5ReasonCode.RELIABILITY_GATE_FAILED),
    ],
)
def test_isolation_failures_are_explicit_and_non_overridable(
    overrides: dict[str, object], reason: M5ReasonCode
) -> None:
    policy = _policy()
    result = evaluate_isolation(policy=policy, observation=_observation(policy, **overrides))

    assert result.conclusion is IsolationConclusion.REJECTED
    assert reason in result.reason_codes


def test_isolation_rejects_policy_mismatch_and_incomplete_controls() -> None:
    policy = _policy()
    with pytest.raises(M5ValidationError) as mismatch:
        evaluate_isolation(
            policy=policy,
            observation=_observation(policy, policy_digest="b" * 64),
        )
    assert mismatch.value.reason_code is M5ReasonCode.CONTENT_DIGEST_MISMATCH

    incomplete = _observation(policy, control_deltas=(ControlDelta("eye_spacing", 1_000),))
    with pytest.raises(M5ValidationError) as controls:
        evaluate_isolation(policy=policy, observation=incomplete)
    assert controls.value.reason_code is M5ReasonCode.MISSING_CONTROL_MEASUREMENT


def test_observation_requires_nonzero_bounded_integer_measurements() -> None:
    policy = _policy()
    for value in (0, True, 5_000_001):
        with pytest.raises(M5ValidationError) as error:
            _observation(policy, requested_delta_ppm=value)
        assert error.value.reason_code is M5ReasonCode.INVALID_MEASUREMENT


def test_technical_and_mvr_results_are_distinct_types() -> None:
    outcome = M5Outcome(
        technical_gate=TechnicalGateResult.PASS,
        mvr_result=MvrResult.FURTHER_RESEARCH,
    )
    assert outcome.technical_gate is TechnicalGateResult.PASS
    assert outcome.mvr_result is MvrResult.FURTHER_RESEARCH

    with pytest.raises(M5ValidationError) as invalid:
        M5Outcome(
            technical_gate=TechnicalGateResult.FAIL,
            mvr_result=MvrResult.PASS,
        )
    assert invalid.value.reason_code is M5ReasonCode.INVALID_OUTCOME

    with pytest.raises(M5ValidationError) as untyped:
        M5Outcome(
            technical_gate=cast(TechnicalGateResult, "PASS"),
            mvr_result=MvrResult.NOT_EVALUATED,
        )
    assert untyped.value.reason_code is M5ReasonCode.INVALID_OUTCOME
