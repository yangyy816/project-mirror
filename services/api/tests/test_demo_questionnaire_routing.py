from __future__ import annotations

from dataclasses import replace

import pytest

from mirror_api.demo_posterior import PosteriorConfig, PosteriorResult, infer_pairwise_posterior
from mirror_api.demo_questionnaire_routing import (
    QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS,
    REAL_BANK_INTEGRATION_STATUS,
    DimensionProgress,
    FixtureQuestionBank,
    QuestionPair,
    RouteStopReason,
    RoutingError,
    RoutingPolicy,
    SelfStateMeasurement,
    SelfStateSnapshot,
    decide_stop,
    desired_delta_input,
    local_morphological_neighborhood,
    schedule_questions,
)


def _posterior() -> PosteriorResult:
    return replace(infer_pairwise_posterior((), PosteriorConfig()), consistency_ppm=500_000)


def _state(*measurements: SelfStateMeasurement) -> SelfStateSnapshot:
    return SelfStateSnapshot("self-state-v1", measurements)


def _pair(
    pair_id: str,
    dimension_id: str,
    anchors: dict[str, int],
    *,
    source_identity_id: str = "synthetic-a",
    expected_fisher_information_ppm: int = 900_000,
    pair_quality_ppm: int = 900_000,
    eligible: bool = True,
) -> QuestionPair:
    return QuestionPair(
        pair_id=pair_id,
        dimension_id=dimension_id,
        magnitude_ppm=10_000,
        source_identity_id=source_identity_id,
        morphology_anchor_ppm=anchors,
        expected_fisher_information_ppm=expected_fisher_information_ppm,
        pair_quality_ppm=pair_quality_ppm,
        eligible=eligible,
    )


def _bank(*pairs: QuestionPair, scales: dict[str, int]) -> FixtureQuestionBank:
    return FixtureQuestionBank(
        pairs=pairs,
        morphology_scale_ppm=scales,
        morphology_scale_floor_ppm=10_000,
    )


def _progress(dimension_id: str, *, complete: bool = False) -> DimensionProgress:
    return DimensionProgress(
        dimension_id=dimension_id,
        posterior=_posterior(),
        valid_answers=4 if complete else 0,
        magnitude_ppm_seen=(10_000, 20_000) if complete else (),
        source_identity_ids_seen=("synthetic-a", "synthetic-b") if complete else (),
    )


def test_scheduler_is_self_state_conditioned_and_replayable() -> None:
    bank = _bank(
        _pair("jaw-near", "jaw_width", {"jaw_width": 10_000}),
        _pair("jaw-far", "jaw_width", {"jaw_width": 280_000}),
        scales={"jaw_width": 100_000},
    )
    first = schedule_questions(
        bank=bank,
        self_state=_state(SelfStateMeasurement("jaw_width", 0, 900_000)),
        progress=(_progress("jaw_width"),),
        total_questions_asked=0,
        limit=2,
    )
    second = schedule_questions(
        bank=bank,
        self_state=_state(SelfStateMeasurement("jaw_width", 300_000, 900_000)),
        progress=(_progress("jaw_width"),),
        total_questions_asked=0,
        limit=2,
    )
    assert first.selected_pair_ids[0] == "jaw-near"
    assert second.selected_pair_ids[0] == "jaw-far"
    assert first == schedule_questions(
        bank=bank,
        self_state=_state(SelfStateMeasurement("jaw_width", 0, 900_000)),
        progress=(_progress("jaw_width"),),
        total_questions_asked=0,
        limit=2,
    )


def test_lmn_uses_weighted_standardized_rms_and_gaussian_compatibility() -> None:
    pair = _pair("weighted", "jaw_width", {"jaw_width": 100_000, "eye_size": 200_000})
    bank = _bank(pair, scales={"jaw_width": 100_000, "eye_size": 100_000})
    near = local_morphological_neighborhood(
        _state(
            SelfStateMeasurement("jaw_width", 0, 900_000),
            SelfStateMeasurement("eye_size", 200_000, 900_000),
        ),
        pair,
        bank,
        RoutingPolicy(),
    )
    far = local_morphological_neighborhood(
        _state(
            SelfStateMeasurement("jaw_width", 300_000, 900_000),
            SelfStateMeasurement("eye_size", 200_000, 900_000),
        ),
        pair,
        bank,
        RoutingPolicy(),
    )
    assert near.eligible and far.eligible
    assert near.standardized_rms_ppm is not None
    assert far.standardized_rms_ppm is not None
    assert near.standardized_rms_ppm < far.standardized_rms_ppm
    assert near.factor_ppm > far.factor_ppm


def test_scale_floor_is_explicit_and_never_default_filled() -> None:
    pair = _pair("jaw", "jaw_width", {"jaw_width": 0})
    with pytest.raises(RoutingError, match="explicitly provided"):
        FixtureQuestionBank((pair,), {}, 10_000)
    with pytest.raises(RoutingError, match="nonzero floor"):
        FixtureQuestionBank((pair,), {"jaw_width": 9_999}, 10_000)


def test_target_dimension_must_be_present_and_reliable() -> None:
    with pytest.raises(RoutingError, match="target dimension"):
        _bank(
            _pair("missing-target", "jaw_width", {"eye_size": 0}),
            scales={"eye_size": 100_000},
        )
    pair = _pair("jaw", "jaw_width", {"jaw_width": 0})
    result = local_morphological_neighborhood(
        _state(SelfStateMeasurement("jaw_width", 0, 0)),
        pair,
        _bank(pair, scales={"jaw_width": 100_000}),
        RoutingPolicy(),
    )
    assert not result.eligible
    assert result.reason == "TARGET_DIMENSION_ZERO_RELIABILITY"


def test_zero_for_each_runtime_score_factor_produces_zero_score_and_no_selection() -> None:
    base = _pair("base", "jaw_width", {"jaw_width": 0})
    state = _state(SelfStateMeasurement("jaw_width", 0, 900_000))
    progress = _progress("jaw_width")

    def assert_zero(
        pair: QuestionPair = base,
        current_state: SelfStateSnapshot = state,
        current_progress: DimensionProgress = progress,
        scale_ppm: int = 100_000,
    ) -> None:
        plan = schedule_questions(
            bank=_bank(pair, scales={"jaw_width": scale_ppm}),
            self_state=current_state,
            progress=(current_progress,),
            total_questions_asked=0,
            limit=1,
        )
        assert plan.scores[0].score_ppm == 0
        assert plan.selected_pair_ids == ()

    assert_zero(
        current_progress=replace(
            progress,
            posterior=replace(_posterior(), confidence_ppm=1_000_000),
        )
    )
    assert_zero(current_state=_state(SelfStateMeasurement("jaw_width", 0, 0)))
    assert_zero(pair=replace(base, expected_fisher_information_ppm=0))
    assert_zero(
        pair=replace(base, morphology_anchor_ppm={"jaw_width": 1_000_000}), scale_ppm=10_000
    )
    assert_zero(pair=replace(base, pair_quality_ppm=0))


def test_contradiction_priority_boosts_without_zeroing_consistent_routing() -> None:
    pair = _pair("jaw", "jaw_width", {"jaw_width": 0})
    bank = _bank(pair, scales={"jaw_width": 100_000})
    state = _state(SelfStateMeasurement("jaw_width", 0, 900_000))
    consistent = schedule_questions(
        bank=bank,
        self_state=state,
        progress=(
            replace(
                _progress("jaw_width"),
                posterior=replace(_posterior(), consistency_ppm=1_000_000),
            ),
        ),
        total_questions_asked=0,
        limit=1,
    )
    contradictory = schedule_questions(
        bank=bank,
        self_state=state,
        progress=(
            replace(
                _progress("jaw_width"),
                posterior=replace(_posterior(), consistency_ppm=0),
            ),
        ),
        total_questions_asked=0,
        limit=1,
    )
    assert consistent.scores[0].score_ppm > 0
    assert contradictory.scores[0].score_ppm > consistent.scores[0].score_ppm


def test_singular_source_ids_drive_coverage_not_pair_side_ids() -> None:
    progress = DimensionProgress(
        "jaw_width",
        _posterior(),
        4,
        (10_000, 20_000),
        ("synthetic-a", "synthetic-a"),
    )
    decision = decide_stop(total_questions_asked=16, progress=(progress,))
    assert decision.reason is RouteStopReason.FAIL_CLOSED_COVERAGE_UNMET_AT_MAXIMUM


def test_stop_rule_and_generation_boundary_remain_frozen() -> None:
    incomplete = (_progress("jaw_width"),)
    complete = (_progress("jaw_width", complete=True),)
    assert (
        decide_stop(total_questions_asked=11, progress=complete).reason
        is RouteStopReason.CONTINUE_MINIMUM_NOT_REACHED
    )
    assert decide_stop(total_questions_asked=12, progress=complete).should_stop
    failed = decide_stop(total_questions_asked=16, progress=incomplete)
    assert failed.reason is RouteStopReason.FAIL_CLOSED_COVERAGE_UNMET_AT_MAXIMUM
    plan = schedule_questions(
        bank=_bank(_pair("jaw", "jaw_width", {"jaw_width": 0}), scales={"jaw_width": 100_000}),
        self_state=_state(SelfStateMeasurement("jaw_width", 0, 900_000)),
        progress=incomplete,
        total_questions_asked=16,
        limit=1,
    )
    assert (
        plan.questionnaire_runtime_generative_calls == QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS == 0
    )
    assert plan.real_bank_integration_status == REAL_BANK_INTEGRATION_STATUS


def test_completed_dimension_still_routes_until_global_minimum_is_reached() -> None:
    pair = _pair("jaw", "jaw_width", {"jaw_width": 0})
    plan = schedule_questions(
        bank=_bank(pair, scales={"jaw_width": 100_000}),
        self_state=_state(SelfStateMeasurement("jaw_width", 0, 900_000)),
        progress=(_progress("jaw_width", complete=True),),
        total_questions_asked=8,
        limit=1,
    )
    assert plan.selected_pair_ids == ("jaw",)
    assert plan.scores[0].coverage_need_ppm > 0


def test_desired_delta_input_is_relative_to_supported_self_state() -> None:
    posterior = _posterior()
    result = desired_delta_input(
        _state(SelfStateMeasurement("jaw_width", 25_000, 900_000)),
        (DimensionProgress("jaw_width", posterior, 4, (10_000, 20_000), ("a", "b")),),
    )
    assert result.dimensions[0].self_state_value_ppm == 25_000
    assert result.dimensions[0].desired_delta_ppm == posterior.posterior_mean_ppm
    assert result.dimensions[0].posterior_digest == posterior.digest
