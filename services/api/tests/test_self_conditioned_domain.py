from __future__ import annotations

from dataclasses import asdict

import pytest

from mirror_api.aesthetic_domain import (
    DeltaEvidence,
    EvidencePriority,
    RouteVersions,
    RoutingTemplate,
    compute_relative_target,
    infer_desired_delta,
    route_questionnaire,
    validate_variable_isolation,
)


def evidence(source: EvidencePriority, delta: float, **kwargs: bool) -> DeltaEvidence:
    return DeltaEvidence(
        source=source,
        direction=1 if delta > 0 else -1 if delta < 0 else 0,
        magnitude=abs(delta),
        preference_confidence=0.8,
        generalized=kwargs.get("generalized", False),
        transferred=kwargs.get("transferred", False),
    )


def test_same_relative_delta_keeps_different_baselines_anchored() -> None:
    delta = infer_desired_delta([evidence(EvidencePriority.SYNTHETIC_QUESTIONNAIRE, -0.1)])
    target_a = compute_relative_target({"jaw_width": 0.35}, {"jaw_width": delta})
    target_b = compute_relative_target({"jaw_width": 0.55}, {"jaw_width": delta})
    assert target_a["jaw_width"] == pytest.approx(0.25)
    assert target_b["jaw_width"] == pytest.approx(0.45)


def test_identical_answers_do_not_collapse_absolute_targets() -> None:
    answers = [evidence(EvidencePriority.SYNTHETIC_QUESTIONNAIRE, 0.07)]
    delta_a = infer_desired_delta(answers)
    delta_b = infer_desired_delta(answers)
    target_a = compute_relative_target({"eye_width": 0.31}, {"eye_width": delta_a})
    target_b = compute_relative_target({"eye_width": 0.48}, {"eye_width": delta_b})
    assert target_a["eye_width"] != target_b["eye_width"]


def test_no_user_evidence_or_population_prior_means_zero_delta_high_uncertainty() -> None:
    no_evidence = infer_desired_delta([])
    population_only = infer_desired_delta([evidence(EvidencePriority.POPULATION_PRIOR, 0.4)])
    assert no_evidence.signed_value == population_only.signed_value == 0
    assert no_evidence.uncertainty == population_only.uncertainty == 1


def test_explicit_preserve_lock_overrides_inferred_delta() -> None:
    locked = infer_desired_delta(
        [evidence(EvidencePriority.EXPLICIT_INSTRUCTION, -0.3)], preserve_lock=True
    )
    assert locked.preserve_lock
    assert locked.signed_value == 0


def test_self_transfer_overrides_conflicting_synthetic_evidence() -> None:
    fused = infer_desired_delta(
        [
            evidence(EvidencePriority.SYNTHETIC_QUESTIONNAIRE, -0.2),
            evidence(EvidencePriority.ACCEPTED_SELF_TRANSFER, 0.05, transferred=True),
        ]
    )
    assert fused.source == EvidencePriority.ACCEPTED_SELF_TRANSFER
    assert fused.signed_value > 0
    assert fused.transfer_confidence > 0


def versions() -> RouteVersions:
    return RouteVersions(
        routing_algorithm_version="route-v1",
        question_bank_version="bank-safe-fixture-v1",
        self_state_version_id="self-state-v3",
        baseline_face_model_id="baseline-v2",
        analysis_schema_version="analysis-v1",
        measurement_normalization_version="normalization-v2",
        morphology_descriptor_version="descriptor-v1",
        neighborhood_metric_version="distance-v1",
        stimulus_generator_version="stimulus-v4",
        route_seed="deterministic-seed",
    )


def test_route_is_self_state_conditioned_and_reproducible() -> None:
    templates = [RoutingTemplate("jaw-template", "jaw"), RoutingTemplate("eye-template", "eye")]
    common = {"reliability": {"jaw": 1.0, "eye": 1.0}, "uncertainty": {"jaw": 0.2, "eye": 0.2}}
    jaw_route = route_questionnaire(
        self_state={"jaw": 0.9, "eye": 0.1},
        templates=templates,
        versions=versions(),
        limit=1,
        **common,
    )
    eye_route = route_questionnaire(
        self_state={"jaw": 0.1, "eye": 0.9},
        templates=templates,
        versions=versions(),
        limit=1,
        **common,
    )
    assert jaw_route.selected_template_ids == ("jaw-template",)
    assert eye_route.selected_template_ids == ("eye-template",)
    assert jaw_route == route_questionnaire(
        self_state={"jaw": 0.9, "eye": 0.1},
        templates=templates,
        versions=versions(),
        limit=1,
        **common,
    )
    assert set(jaw_route.metadata) == set(asdict(versions()))
    assert not ({"race", "ethnicity", "nationality"} & set(jaw_route.metadata))


def test_variable_isolation_fixture_rejects_non_target_drift() -> None:
    passed = validate_variable_isolation(
        {"jaw": 0.4, "eye": 0.3},
        {"jaw": 0.3, "eye": 0.301},
        target_dimension="jaw",
        isolation_threshold=0.01,
    )
    failed = validate_variable_isolation(
        {"jaw": 0.4, "eye": 0.3},
        {"jaw": 0.3, "eye": 0.35},
        target_dimension="jaw",
        isolation_threshold=0.01,
    )
    assert passed.validation_status == "pass"
    assert failed.validation_status == "fail"
