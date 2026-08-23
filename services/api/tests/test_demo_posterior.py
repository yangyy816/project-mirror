from __future__ import annotations

import math

import pytest

from mirror_api.demo_posterior import (
    PairwiseChoice,
    PairwiseObservation,
    PosteriorConfig,
    PosteriorConvergenceError,
    PosteriorError,
    canonical_json_bytes,
    infer_pairwise_posterior,
    log_posterior,
    log_posterior_gradient,
    log_posterior_hessian,
    quantize_ppm,
)


def _observation(left: int, right: int, choice: PairwiseChoice) -> PairwiseObservation:
    return PairwiseObservation(left, right, choice)


def test_grid_posterior_reference_newton_matches_one_ppm_argmax() -> None:
    config = PosteriorConfig()
    observations = (
        _observation(-15_000, 15_000, PairwiseChoice.RIGHT),
        _observation(-10_000, 20_000, PairwiseChoice.RIGHT),
        _observation(-20_000, 10_000, PairwiseChoice.LEFT),
    )
    result = infer_pairwise_posterior(observations, config)
    grid_map = max(
        range(config.lower_bound_ppm, config.upper_bound_ppm + 1),
        key=lambda delta: log_posterior(float(delta), observations, config),
    )
    assert abs(result.posterior_mean_ppm - grid_map) <= 2


def test_finite_difference_gradient_check() -> None:
    config = PosteriorConfig()
    observations = (_observation(-15_000, 15_000, PairwiseChoice.RIGHT),)
    delta = 1234.0
    epsilon = 0.01
    numerical = (
        log_posterior(delta + epsilon, observations, config)
        - log_posterior(delta - epsilon, observations, config)
    ) / (2 * epsilon)
    assert log_posterior_gradient(delta, observations, config) == pytest.approx(numerical, abs=1e-9)


def test_finite_difference_hessian_check() -> None:
    config = PosteriorConfig()
    observations = (_observation(-15_000, 15_000, PairwiseChoice.RIGHT),)
    delta = 1234.0
    epsilon = 0.1
    numerical = (
        log_posterior_gradient(delta + epsilon, observations, config)
        - log_posterior_gradient(delta - epsilon, observations, config)
    ) / (2 * epsilon)
    assert log_posterior_hessian(delta, observations, config) == pytest.approx(numerical, abs=1e-11)


def test_symmetry() -> None:
    positive = infer_pairwise_posterior((_observation(-10_000, 10_000, PairwiseChoice.RIGHT),))
    negative = infer_pairwise_posterior((_observation(10_000, -10_000, PairwiseChoice.RIGHT),))
    side_swapped = infer_pairwise_posterior((_observation(10_000, -10_000, PairwiseChoice.LEFT),))
    assert positive.posterior_mean_ppm == -negative.posterior_mean_ppm
    assert positive.posterior_sd_ppm == negative.posterior_sd_ppm
    assert side_swapped == positive


def test_choice_reversal_changes_map_direction() -> None:
    right = infer_pairwise_posterior((_observation(-15_000, 15_000, PairwiseChoice.RIGHT),))
    left = infer_pairwise_posterior((_observation(-15_000, 15_000, PairwiseChoice.LEFT),))
    assert right.posterior_mean_ppm > 0
    assert left.posterior_mean_ppm < 0


def test_monotonic_evidence_reduces_laplace_uncertainty() -> None:
    one = infer_pairwise_posterior((_observation(-15_000, 15_000, PairwiseChoice.RIGHT),))
    many = infer_pairwise_posterior(
        tuple(_observation(-15_000, 15_000, PairwiseChoice.RIGHT) for _ in range(8))
    )
    assert many.laplace_sd_ppm < one.laplace_sd_ppm


def test_no_response_shrinkage() -> None:
    config = PosteriorConfig()
    for observations in ((), (_observation(-1, 1, PairwiseChoice.SKIP),)):
        result = infer_pairwise_posterior(observations, config)
        assert result.posterior_mean_ppm == 0
        assert result.laplace_sd_ppm == config.prior_sd_ppm
        assert result.posterior_sd_ppm == config.prior_sd_ppm
        assert result.confidence_ppm == 0


def test_contradiction_floor_increases_uncertainty() -> None:
    consistent = infer_pairwise_posterior(
        tuple(_observation(-15_000, 15_000, PairwiseChoice.RIGHT) for _ in range(8))
    )
    contradictory = infer_pairwise_posterior(
        tuple(_observation(-15_000, 15_000, PairwiseChoice.RIGHT) for _ in range(4))
        + tuple(_observation(-15_000, 15_000, PairwiseChoice.LEFT) for _ in range(4))
    )
    assert contradictory.posterior_sd_ppm == 30_000
    assert contradictory.posterior_sd_ppm > consistent.posterior_sd_ppm
    assert abs(contradictory.posterior_mean_ppm) < abs(consistent.posterior_mean_ppm)
    assert contradictory.confidence_ppm < consistent.confidence_ppm
    assert contradictory.consistency_ppm == 0


def test_contradiction_cells_normalize_randomized_left_right_presentation() -> None:
    semantically_consistent = infer_pairwise_posterior(
        tuple(_observation(-15_000, 15_000, PairwiseChoice.RIGHT) for _ in range(4))
        + tuple(_observation(15_000, -15_000, PairwiseChoice.LEFT) for _ in range(4))
    )
    semantically_contradictory = infer_pairwise_posterior(
        tuple(_observation(-15_000, 15_000, PairwiseChoice.RIGHT) for _ in range(4))
        + tuple(_observation(15_000, -15_000, PairwiseChoice.RIGHT) for _ in range(4))
    )
    assert semantically_consistent.consistency_ppm == 1_000_000
    assert semantically_consistent.posterior_mean_ppm > 0
    assert semantically_contradictory.posterior_mean_ppm == 0
    assert semantically_contradictory.consistency_ppm == 0
    assert semantically_contradictory.posterior_sd_ppm == 30_000


def test_non_convergence_fails_closed() -> None:
    config = PosteriorConfig(iteration_limit=1, gradient_tolerance=0, step_tolerance_ppm=0)
    with pytest.raises(PosteriorConvergenceError):
        infer_pairwise_posterior((_observation(-15_000, 15_000, PairwiseChoice.RIGHT),), config)


def test_deterministic_replay_matches_frozen_canonical_authority() -> None:
    observations = (
        _observation(-15_000, 15_000, PairwiseChoice.RIGHT),
        _observation(-15_000, 15_000, PairwiseChoice.INDISTINGUISHABLE),
        _observation(-15_000, 15_000, PairwiseChoice.SKIP),
    )
    first = infer_pairwise_posterior(observations)
    second = infer_pairwise_posterior(observations)
    expected_bytes = (
        b'{"algorithm_version":"demo-bayesian-pairwise-logistic-v1",'
        b'"confidence_ppm":633512,'
        b'"config_digest":"6bd30965af9ed9bb912d60edd9edb4e76583b2a7efaaba6d005e9efa62483631",'
        b'"consistency_ppm":1000000,"laplace_sd_ppm":10995,'
        b'"posterior_mean_ppm":7099,"posterior_sd_ppm":10995}'
    )
    assert first == second
    assert first.config_digest == "6bd30965af9ed9bb912d60edd9edb4e76583b2a7efaaba6d005e9efa62483631"
    assert first.digest == "f29d96a31cc845dc01891b640ed90bda39b87f2e4fc1e158df33d12738e4d7d9"
    assert canonical_json_bytes(first.canonical_payload()) == expected_bytes
    assert canonical_json_bytes(second.canonical_payload()) == expected_bytes
    assert b"created_at" not in expected_bytes


def test_boundary_kkt_is_accepted_in_both_directions() -> None:
    config = PosteriorConfig(lower_bound_ppm=-500, upper_bound_ppm=500)
    upper_observations = tuple(
        _observation(-30_000, 30_000, PairwiseChoice.RIGHT) for _ in range(10)
    )
    lower_observations = tuple(
        _observation(-30_000, 30_000, PairwiseChoice.LEFT) for _ in range(10)
    )
    upper_result = infer_pairwise_posterior(upper_observations, config)
    lower_result = infer_pairwise_posterior(lower_observations, config)
    tolerance = config.gradient_tolerance / (config.prior_sd_ppm * config.prior_sd_ppm)
    assert upper_result.posterior_mean_ppm == config.upper_bound_ppm
    assert lower_result.posterior_mean_ppm == config.lower_bound_ppm
    assert (
        log_posterior_gradient(float(config.upper_bound_ppm), upper_observations, config)
        >= -tolerance
    )
    assert (
        log_posterior_gradient(float(config.lower_bound_ppm), lower_observations, config)
        <= tolerance
    )


def test_safeguarded_newton_breaks_the_clamped_newton_two_cycle() -> None:
    config = PosteriorConfig()
    observations = (
        _observation(-24_809, 8_692, PairwiseChoice.LEFT),
        _observation(-45_599, -4_582, PairwiseChoice.RIGHT),
        _observation(30_835, -46_386, PairwiseChoice.LEFT),
        _observation(57_704, 22_508, PairwiseChoice.RIGHT),
        _observation(-44_861, -47_507, PairwiseChoice.INDISTINGUISHABLE),
        _observation(44_465, 31_340, PairwiseChoice.RIGHT),
        _observation(19_078, -50_344, PairwiseChoice.RIGHT),
        _observation(-14_343, -15_136, PairwiseChoice.INDISTINGUISHABLE),
        _observation(-48_460, -56_651, PairwiseChoice.LEFT),
        _observation(6_861, -49_325, PairwiseChoice.LEFT),
    )
    result = infer_pairwise_posterior(observations, config)
    grid_map = max(
        range(config.lower_bound_ppm, config.upper_bound_ppm + 1),
        key=lambda delta: log_posterior(float(delta), observations, config),
    )
    assert grid_map == -11_082
    assert result.posterior_mean_ppm == -11_082
    assert abs(result.posterior_mean_ppm - grid_map) <= 2


def test_skip_and_indistinguishable_behavior() -> None:
    indistinguishable = infer_pairwise_posterior(
        (_observation(-15_000, 15_000, PairwiseChoice.INDISTINGUISHABLE),)
    )
    skipped = infer_pairwise_posterior((_observation(-15_000, 15_000, PairwiseChoice.SKIP),))
    assert indistinguishable.posterior_mean_ppm == 0
    assert indistinguishable.posterior_sd_ppm < skipped.posterior_sd_ppm
    assert indistinguishable.consistency_ppm == 1_000_000


def test_raw_float_and_decimal_string_canonical_authority_are_rejected() -> None:
    with pytest.raises(PosteriorError):
        canonical_json_bytes({"value": 0.5})
    with pytest.raises(PosteriorError):
        canonical_json_bytes({"value": "0.5"})
    with pytest.raises(PosteriorError):
        canonical_json_bytes({"unordered": {1, 2}})


def test_non_finite_or_overflowing_likelihood_fails_closed() -> None:
    with pytest.raises(PosteriorError):
        infer_pairwise_posterior((_observation(-(10**400), 10**400, PairwiseChoice.RIGHT),))


def test_quantization_is_clamped_half_even_and_normalizes_negative_zero() -> None:
    assert quantize_ppm(2.5, -10, 10) == 2
    assert quantize_ppm(3.5, -10, 10) == 4
    assert quantize_ppm(-0.1, -10, 10) == 0
    with pytest.raises(PosteriorError):
        quantize_ppm(math.inf, -10, 10)
