from __future__ import annotations

from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    Clamped,
    Decimal,
    Inexact,
    Rounded,
    Subnormal,
    Underflow,
    localcontext,
)

import pytest

from mirror_api.demo_posterior import (
    ALGORITHM_VERSION,
    RESULT_SCHEMA_VERSION,
    DesignCellKey,
    MapLocation,
    PairwiseChoice,
    PairwiseObservation,
    PosteriorConfig,
    PosteriorConvergenceError,
    PosteriorError,
    _new_v1_decimal_context,
    canonical_json_bytes,
    infer_pairwise_posterior,
    log_posterior,
    log_posterior_gradient,
    log_posterior_hessian,
    quantize_ppm,
    stable_sigmoid,
    stable_softplus,
)

DEFAULT_CONFIG = PosteriorConfig()
DEFAULT_POSTERIOR_CONFIG_DIGEST = "a3ce13813e901b935900d7d5251802ff7873cf0d76526088e541362fa365b8de"


def _observation(
    magnitude_ppm: int,
    choice: PairwiseChoice,
    *,
    config: PosteriorConfig = DEFAULT_CONFIG,
    dimension_key: str = "jaw_width",
    reverse_presentation: bool = False,
    stimulus_config_version: str = "stimulus-v1",
) -> PairwiseObservation:
    left_ppm, right_ppm = (
        (magnitude_ppm, -magnitude_ppm) if reverse_presentation else (-magnitude_ppm, magnitude_ppm)
    )
    return PairwiseObservation(
        dimension_key=dimension_key,
        left_delta_ppm=left_ppm,
        right_delta_ppm=right_ppm,
        magnitude_ppm=magnitude_ppm,
        stimulus_config_version=stimulus_config_version,
        posterior_config_digest=config.posterior_config_digest,
        choice=choice,
    )


def test_default_config_is_exact_versioned_authority() -> None:
    config = PosteriorConfig()
    assert config.algorithm_version == ALGORITHM_VERSION
    assert config.iteration_limit == 32
    assert config.gradient_tolerance_ppm == 1
    assert not hasattr(config, "indistinguishable_weight_ppm")
    assert config.posterior_config_digest == DEFAULT_POSTERIOR_CONFIG_DIGEST
    assert config.canonical_payload() == {
        "algorithm_version": "demo-bayesian-pairwise-logistic-v1",
        "boundary_policy": "censored-boundary-prior-uncertainty-v1",
        "bounds_ppm": [-30_000, 30_000],
        "confidence_policy": "integer-posterior-sd-complement-v1",
        "contradiction_policy": "count-weighted-unordered-design-cell-reversal-v1",
        "decimal_capitals": 1,
        "decimal_clamp": 0,
        "decimal_context_policy": "fresh-explicit-context-per-authority-call-v1",
        "decimal_emax": 999_999,
        "decimal_emin": -999_999,
        "decimal_flags_policy": "clear-on-entry-ignore-nonfatal-do-not-leak-v1",
        "decimal_nonfatal_signals": [
            "Clamped",
            "Inexact",
            "Rounded",
            "Subnormal",
            "Underflow",
        ],
        "decimal_precision": 50,
        "decimal_rounding": "ROUND_HALF_EVEN",
        "decimal_traps": [
            "DivisionByZero",
            "FloatOperation",
            "InvalidOperation",
            "Overflow",
        ],
        "exp_tail_cutoff_abs": 128,
        "exp_tail_policy": "sigmoid-softplus-saturate-inclusive-v1",
        "gradient_tolerance_ppm": 1,
        "iteration_limit": 32,
        "likelihood_policy": "pairwise-logistic-unit-likelihood-utility-difference-v1",
        "prior_policy": "zero-mean-gaussian-v1",
        "prior_sd_ppm": 30_000,
        "quantization_policy": "clamp-decimal-half-even-normalized-zero-v1",
        "solver_policy": "bounded-safeguarded-newton-kkt-v1",
        "step_tolerance_ppm": 1,
        "tau_ppm": 15_000,
        "tie_only_precision_policy": "prior-uncertainty-zero-confidence-v1",
        "uncertainty_policy": "laplace-with-contradiction-floor-v1",
    }


def test_decimal_context_factory_is_fresh_and_exactly_frozen() -> None:
    first = _new_v1_decimal_context()
    second = _new_v1_decimal_context()
    assert first is not second
    assert (
        first.prec,
        first.rounding,
        first.Emin,
        first.Emax,
        first.capitals,
        first.clamp,
    ) == (50, ROUND_HALF_EVEN, -999_999, 999_999, 1, 0)
    assert {signal.__name__ for signal, trapped in first.traps.items() if trapped} == {
        "DivisionByZero",
        "FloatOperation",
        "InvalidOperation",
        "Overflow",
    }
    assert all(not raised for raised in first.flags.values())
    first.prec = 6
    assert second.prec == 50


@pytest.mark.parametrize(
    "kwargs",
    [
        {"algorithm_version": "caller-invented-v1"},
        {"tau_ppm": 0},
        {"tau_ppm": 1_000_001},
        {"prior_sd_ppm": 0},
        {"lower_bound_ppm": 1},
        {"upper_bound_ppm": -1},
        {"lower_bound_ppm": 0, "upper_bound_ppm": 0},
        {"lower_bound_ppm": -1_000_001},
        {"upper_bound_ppm": 1_000_001},
        {"iteration_limit": 0},
        {"iteration_limit": 33},
        {"gradient_tolerance_ppm": 0},
        {"gradient_tolerance_ppm": 1_000_001},
        {"step_tolerance_ppm": -1},
        {"step_tolerance_ppm": 60_001},
        {"tau_ppm": True},
        {"prior_sd_ppm": 30_000.0},
        {"iteration_limit": "32"},
    ],
)
def test_config_rejects_invalid_or_noncanonical_authority(kwargs: dict[str, object]) -> None:
    with pytest.raises(PosteriorError):
        PosteriorConfig(**kwargs)  # type: ignore[arg-type]


def test_observation_requires_complete_design_cell_authority() -> None:
    observation = _observation(15_000, PairwiseChoice.RIGHT)
    assert observation.design_cell_key == DesignCellKey(
        dimension_key="jaw_width",
        low_delta_ppm=-15_000,
        high_delta_ppm=15_000,
        magnitude_ppm=15_000,
        stimulus_config_version="stimulus-v1",
        posterior_config_digest=DEFAULT_POSTERIOR_CONFIG_DIGEST,
    )
    assert observation.design_cell_key.canonical_payload() == {
        "posterior_config_digest": DEFAULT_POSTERIOR_CONFIG_DIGEST,
        "dimension_key": "jaw_width",
        "high_delta_ppm": 15_000,
        "low_delta_ppm": -15_000,
        "magnitude_ppm": 15_000,
        "stimulus_config_version": "stimulus-v1",
    }

    invalid_payloads: tuple[dict[str, object], ...] = (
        {"dimension_key": ""},
        {"dimension_key": "x" * 49},
        {"left_delta_ppm": True},
        {"right_delta_ppm": 14_999},
        {"magnitude_ppm": 0},
        {"stimulus_config_version": ""},
        {"posterior_config_digest": "A" * 64},
        {"choice": "RIGHT"},
    )
    base: dict[str, object] = {
        "dimension_key": "jaw_width",
        "left_delta_ppm": -15_000,
        "right_delta_ppm": 15_000,
        "magnitude_ppm": 15_000,
        "stimulus_config_version": "stimulus-v1",
        "posterior_config_digest": DEFAULT_POSTERIOR_CONFIG_DIGEST,
        "choice": PairwiseChoice.RIGHT,
    }
    for override in invalid_payloads:
        with pytest.raises(PosteriorError):
            PairwiseObservation(**(base | override))  # type: ignore[arg-type]


def test_observation_posterior_config_digest_must_match_active_config() -> None:
    observation = _observation(15_000, PairwiseChoice.RIGHT)
    other_config = PosteriorConfig(prior_sd_ppm=40_000)
    with pytest.raises(PosteriorError, match="does not match config"):
        infer_pairwise_posterior((observation,), other_config)


def test_zero_may_be_an_inclusive_bound_with_boundary_uncertainty() -> None:
    lower_config = PosteriorConfig(lower_bound_ppm=0, upper_bound_ppm=30_000)
    upper_config = PosteriorConfig(lower_bound_ppm=-30_000, upper_bound_ppm=0)
    lower = infer_pairwise_posterior((), lower_config)
    upper = infer_pairwise_posterior((), upper_config)
    assert lower.map_location is MapLocation.LOWER_BOUND
    assert upper.map_location is MapLocation.UPPER_BOUND
    for result in (lower, upper):
        assert result.posterior_mean_ppm == 0
        assert result.posterior_sd_ppm == 30_000
        assert result.confidence_ppm == 0


def test_zero_centered_gaussian_prior_terms_are_exact() -> None:
    config = PosteriorConfig()
    assert log_posterior(0, (), config) == 0
    assert log_posterior_gradient(0, (), config) == 0
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        expected_hessian = -Decimal(1) / Decimal(config.prior_sd_ppm * config.prior_sd_ppm)
    assert log_posterior_hessian(0, (), config) == expected_hessian


def test_grid_posterior_reference_matches_bounded_newton() -> None:
    config = PosteriorConfig()
    observations = (
        _observation(15_000, PairwiseChoice.RIGHT, config=config),
        _observation(10_000, PairwiseChoice.RIGHT, config=config),
        _observation(20_000, PairwiseChoice.LEFT, config=config),
    )
    result = infer_pairwise_posterior(observations, config)
    grid_map = max(
        range(config.lower_bound_ppm, config.upper_bound_ppm + 1),
        key=lambda delta: log_posterior(delta, observations, config),
    )
    assert result.map_location is MapLocation.INTERIOR
    assert abs(result.posterior_mean_ppm - grid_map) <= 2


def test_unit_likelihood_finite_difference_gradient_and_hessian() -> None:
    config = PosteriorConfig()
    observations = (
        _observation(15_000, PairwiseChoice.RIGHT, config=config),
        _observation(10_000, PairwiseChoice.INDISTINGUISHABLE, config=config),
    )
    delta = Decimal(1234)
    epsilon = Decimal("0.01")
    numerical_gradient = (
        log_posterior(delta + epsilon, observations, config)
        - log_posterior(delta - epsilon, observations, config)
    ) / (Decimal(2) * epsilon)
    numerical_hessian = (
        log_posterior_gradient(delta + epsilon, observations, config)
        - log_posterior_gradient(delta - epsilon, observations, config)
    ) / (Decimal(2) * epsilon)
    assert abs(log_posterior_gradient(delta, observations, config) - numerical_gradient) < Decimal(
        "1e-18"
    )
    assert abs(log_posterior_hessian(delta, observations, config) - numerical_hessian) < Decimal(
        "1e-21"
    )


def test_indistinguishable_uses_unit_likelihood_against_independent_decimal_reference() -> None:
    config = PosteriorConfig()
    one_tie = (_observation(15_000, PairwiseChoice.INDISTINGUISHABLE, config=config),)
    one_directional = (_observation(15_000, PairwiseChoice.RIGHT, config=config),)
    with localcontext(_new_v1_decimal_context()):
        slope = Decimal(30_000) / Decimal(config.tau_ppm * config.tau_ppm)
        expected_log_posterior = -Decimal(2).ln()
        expected_hessian = -Decimal(1) / Decimal(
            config.prior_sd_ppm * config.prior_sd_ppm
        ) - slope * slope / Decimal(4)
    assert abs(log_posterior(0, one_tie, config) - expected_log_posterior) < Decimal("1e-48")
    assert abs(log_posterior_hessian(0, one_tie, config) - expected_hessian) < Decimal("1e-56")
    assert log_posterior(0, one_tie, config) == log_posterior(0, one_directional, config)
    assert log_posterior_hessian(0, one_tie, config) == log_posterior_hessian(
        0, one_directional, config
    )


def test_symmetry_choice_reversal_and_presentation_swap() -> None:
    positive = infer_pairwise_posterior(
        (_observation(10_000, PairwiseChoice.RIGHT),), DEFAULT_CONFIG
    )
    negative = infer_pairwise_posterior(
        (_observation(10_000, PairwiseChoice.LEFT),), DEFAULT_CONFIG
    )
    side_swapped = infer_pairwise_posterior(
        (
            _observation(
                10_000,
                PairwiseChoice.LEFT,
                reverse_presentation=True,
            ),
        ),
        DEFAULT_CONFIG,
    )
    assert positive.posterior_mean_ppm == -negative.posterior_mean_ppm
    assert positive.posterior_sd_ppm == negative.posterior_sd_ppm
    assert positive.posterior_mean_ppm == side_swapped.posterior_mean_ppm
    assert positive.posterior_sd_ppm == side_swapped.posterior_sd_ppm
    assert positive.consistency_ppm == side_swapped.consistency_ppm
    assert positive.evidence_digest != side_swapped.evidence_digest


def test_monotonic_directional_evidence_reduces_laplace_uncertainty() -> None:
    one = infer_pairwise_posterior((_observation(15_000, PairwiseChoice.RIGHT),), DEFAULT_CONFIG)
    many = infer_pairwise_posterior(
        tuple(_observation(15_000, PairwiseChoice.RIGHT) for _ in range(8)),
        DEFAULT_CONFIG,
    )
    assert one.map_location is MapLocation.INTERIOR
    assert many.map_location is MapLocation.INTERIOR
    assert many.posterior_mean_ppm > one.posterior_mean_ppm
    assert many.laplace_sd_ppm < one.laplace_sd_ppm
    assert many.posterior_sd_ppm < one.posterior_sd_ppm


def test_skip_and_empty_evidence_preserve_prior_uncertainty() -> None:
    empty = infer_pairwise_posterior((), DEFAULT_CONFIG)
    skipped = infer_pairwise_posterior((_observation(15_000, PairwiseChoice.SKIP),), DEFAULT_CONFIG)
    all_skipped = infer_pairwise_posterior(
        tuple(_observation(15_000, PairwiseChoice.SKIP) for _ in range(4)),
        DEFAULT_CONFIG,
    )
    for result in (empty, skipped, all_skipped):
        assert result.posterior_mean_ppm == 0
        assert result.map_location is MapLocation.INTERIOR
        assert result.laplace_sd_ppm == DEFAULT_CONFIG.prior_sd_ppm
        assert result.posterior_sd_ppm == DEFAULT_CONFIG.prior_sd_ppm
        assert result.confidence_ppm == 0
        assert result.consistency_ppm == 1_000_000
    assert empty.evidence_digest != skipped.evidence_digest
    assert skipped.evidence_digest != all_skipped.evidence_digest


def test_mixed_dimensions_fail_closed_including_skip_and_indistinguishable() -> None:
    mixed_directional = (
        _observation(15_000, PairwiseChoice.RIGHT, dimension_key="jaw_width"),
        _observation(15_000, PairwiseChoice.LEFT, dimension_key="chin_height"),
    )
    mixed_nondirectional = (
        _observation(15_000, PairwiseChoice.SKIP, dimension_key="jaw_width"),
        _observation(
            15_000,
            PairwiseChoice.INDISTINGUISHABLE,
            dimension_key="chin_height",
        ),
    )
    for observations in (mixed_directional, mixed_nondirectional):
        with pytest.raises(PosteriorError, match="exactly one dimension_key"):
            infer_pairwise_posterior(observations, DEFAULT_CONFIG)


def test_tie_only_evidence_is_diagnostic_but_never_precision_authority() -> None:
    for count in (1, 2, 8, 16):
        result = infer_pairwise_posterior(
            tuple(_observation(15_000, PairwiseChoice.INDISTINGUISHABLE) for _ in range(count)),
            DEFAULT_CONFIG,
        )
        assert result.posterior_mean_ppm == 0
        assert result.map_location is MapLocation.INTERIOR
        assert result.posterior_sd_ppm == DEFAULT_CONFIG.prior_sd_ppm
        assert result.confidence_ppm == 0
    sixteen = infer_pairwise_posterior(
        tuple(_observation(15_000, PairwiseChoice.INDISTINGUISHABLE) for _ in range(16)),
        DEFAULT_CONFIG,
    )
    assert sixteen.laplace_sd_ppm == 3_721


def test_one_left_one_right_is_full_count_aware_contradiction() -> None:
    result = infer_pairwise_posterior(
        (
            _observation(15_000, PairwiseChoice.RIGHT),
            _observation(15_000, PairwiseChoice.LEFT),
        ),
        DEFAULT_CONFIG,
    )
    assert result.posterior_mean_ppm == 0
    assert result.posterior_sd_ppm == DEFAULT_CONFIG.prior_sd_ppm
    assert result.confidence_ppm == 0
    assert result.consistency_ppm == 0


def test_sparse_conflict_cell_cannot_dominate_large_consistent_evidence() -> None:
    observations = (
        *(_observation(15_000, PairwiseChoice.RIGHT) for _ in range(100)),
        _observation(10_000, PairwiseChoice.RIGHT),
        _observation(10_000, PairwiseChoice.LEFT),
    )
    result = infer_pairwise_posterior(observations, DEFAULT_CONFIG)
    assert result.consistency_ppm == 980_392


def test_multiple_medium_conflict_cells_are_count_weighted() -> None:
    observations = (
        *(_observation(15_000, PairwiseChoice.RIGHT) for _ in range(3)),
        _observation(15_000, PairwiseChoice.LEFT),
        *(_observation(10_000, PairwiseChoice.RIGHT) for _ in range(4)),
        *(_observation(10_000, PairwiseChoice.LEFT) for _ in range(2)),
    )
    result = infer_pairwise_posterior(observations, DEFAULT_CONFIG)
    assert result.consistency_ppm == 400_000
    assert result.posterior_sd_ppm == 18_000


def test_contradiction_is_invariant_to_left_right_presentation_swap() -> None:
    canonical = tuple(_observation(15_000, PairwiseChoice.RIGHT) for _ in range(4)) + tuple(
        _observation(15_000, PairwiseChoice.LEFT) for _ in range(4)
    )
    swapped = tuple(
        _observation(
            15_000,
            PairwiseChoice.LEFT,
            reverse_presentation=True,
        )
        for _ in range(4)
    ) + tuple(
        _observation(
            15_000,
            PairwiseChoice.RIGHT,
            reverse_presentation=True,
        )
        for _ in range(4)
    )
    canonical_result = infer_pairwise_posterior(canonical, DEFAULT_CONFIG)
    swapped_result = infer_pairwise_posterior(swapped, DEFAULT_CONFIG)
    assert canonical_result.consistency_ppm == swapped_result.consistency_ppm == 0
    assert canonical_result.posterior_mean_ppm == swapped_result.posterior_mean_ppm
    assert canonical_result.posterior_sd_ppm == swapped_result.posterior_sd_ppm
    assert canonical_result.evidence_digest != swapped_result.evidence_digest


def test_boundary_map_is_typed_and_censored_in_both_directions() -> None:
    config = PosteriorConfig(lower_bound_ppm=-500, upper_bound_ppm=500)
    upper_observations = tuple(
        _observation(30_000, PairwiseChoice.RIGHT, config=config) for _ in range(10)
    )
    lower_observations = tuple(
        _observation(30_000, PairwiseChoice.LEFT, config=config) for _ in range(10)
    )
    upper = infer_pairwise_posterior(upper_observations, config)
    lower = infer_pairwise_posterior(lower_observations, config)
    assert upper.map_location is MapLocation.UPPER_BOUND
    assert lower.map_location is MapLocation.LOWER_BOUND
    assert upper.posterior_mean_ppm == config.upper_bound_ppm
    assert lower.posterior_mean_ppm == config.lower_bound_ppm
    upper_grid_map = max(
        range(config.lower_bound_ppm, config.upper_bound_ppm + 1),
        key=lambda delta: log_posterior(delta, upper_observations, config),
    )
    lower_grid_map = max(
        range(config.lower_bound_ppm, config.upper_bound_ppm + 1),
        key=lambda delta: log_posterior(delta, lower_observations, config),
    )
    assert upper_grid_map == config.upper_bound_ppm
    assert lower_grid_map == config.lower_bound_ppm
    assert upper.laplace_sd_ppm == lower.laplace_sd_ppm == 2_370
    for result in (upper, lower):
        assert result.posterior_sd_ppm == config.prior_sd_ppm
        assert result.confidence_ppm == 0
        assert result.consistency_ppm == 1_000_000


def test_boundary_censoring_dominates_contradiction_uncertainty_floor() -> None:
    config = PosteriorConfig(lower_bound_ppm=-500, upper_bound_ppm=500)
    observations = (
        *(_observation(30_000, PairwiseChoice.RIGHT, config=config) for _ in range(10)),
        _observation(30_000, PairwiseChoice.LEFT, config=config),
    )
    result = infer_pairwise_posterior(observations, config)
    assert result.map_location is MapLocation.UPPER_BOUND
    assert result.posterior_mean_ppm == config.upper_bound_ppm
    assert result.posterior_sd_ppm == config.prior_sd_ppm
    assert result.confidence_ppm == 0
    assert result.consistency_ppm == 818_182


def test_non_convergence_has_stable_terminal_machine_code() -> None:
    config = PosteriorConfig(
        iteration_limit=1,
        gradient_tolerance_ppm=1,
        step_tolerance_ppm=0,
    )
    observation = _observation(15_000, PairwiseChoice.RIGHT, config=config)
    with pytest.raises(PosteriorConvergenceError) as captured:
        infer_pairwise_posterior((observation,), config)
    assert captured.value.code == "MAP_ITERATION_LIMIT_EXCEEDED"


def test_legal_extreme_authority_is_overflow_safe() -> None:
    config = PosteriorConfig(
        tau_ppm=1,
        prior_sd_ppm=1_000_000,
        lower_bound_ppm=-1_000_000,
        upper_bound_ppm=1_000_000,
    )
    observation = _observation(1_000_000, PairwiseChoice.RIGHT, config=config)
    result = infer_pairwise_posterior((observation,), config)
    assert -1_000_000 <= result.posterior_mean_ppm <= 1_000_000
    assert 0 <= result.laplace_sd_ppm <= config.prior_sd_ppm
    assert 0 <= result.posterior_sd_ppm <= config.prior_sd_ppm


def test_decimal_tail_cutoff_has_frozen_inclusive_vectors() -> None:
    inputs = (-129, -128, -127, 0, 127, 128, 129)
    sigmoid_outputs = tuple(str(stable_sigmoid(Decimal(value))) for value in inputs)
    softplus_outputs = tuple(str(stable_softplus(Decimal(value))) for value in inputs)
    assert sigmoid_outputs == (
        "0",
        "0",
        "6.9919899966459170226962577404006557276976516403543E-56",
        "0.5",
        "1",
        "1",
        "1",
    )
    assert softplus_outputs == (
        "0",
        "0",
        "0",
        "0.69314718055994530941723212145817656807550013436026",
        "127",
        "128",
        "129",
    )


def test_authority_is_independent_of_adversarial_ambient_decimal_context() -> None:
    baseline = infer_pairwise_posterior(
        (_observation(15_000, PairwiseChoice.RIGHT),), DEFAULT_CONFIG
    )
    extreme_config = PosteriorConfig(
        tau_ppm=1,
        prior_sd_ppm=1_000_000,
        lower_bound_ppm=-1_000_000,
        upper_bound_ppm=1_000_000,
    )
    extreme_observations = tuple(
        _observation(1_000_000, choice, config=extreme_config)
        for choice in (
            PairwiseChoice.LEFT,
            PairwiseChoice.RIGHT,
            PairwiseChoice.INDISTINGUISHABLE,
        )
    )
    baseline_extremes = tuple(
        infer_pairwise_posterior((observation,), extreme_config)
        for observation in extreme_observations
    )

    with localcontext() as ambient:
        ambient.prec = 6
        ambient.rounding = ROUND_DOWN
        ambient.Emin = -9
        ambient.Emax = 9
        ambient.capitals = 0
        ambient.clamp = 1
        for nonfatal_signal in (Clamped, Inexact, Rounded, Subnormal, Underflow):
            ambient.traps[nonfatal_signal] = True
        for context_signal in ambient.flags:
            ambient.flags[context_signal] = True
        before = (
            ambient.prec,
            ambient.rounding,
            ambient.Emin,
            ambient.Emax,
            ambient.capitals,
            ambient.clamp,
            tuple(ambient.traps.items()),
            tuple(ambient.flags.items()),
        )
        replay = infer_pairwise_posterior(
            (_observation(15_000, PairwiseChoice.RIGHT),), DEFAULT_CONFIG
        )
        replay_extremes = tuple(
            infer_pairwise_posterior((observation,), extreme_config)
            for observation in extreme_observations
        )
        after = (
            ambient.prec,
            ambient.rounding,
            ambient.Emin,
            ambient.Emax,
            ambient.capitals,
            ambient.clamp,
            tuple(ambient.traps.items()),
            tuple(ambient.flags.items()),
        )

    assert replay == baseline
    assert replay_extremes == baseline_extremes
    assert before == after


def test_true_decimal_overflow_fails_closed_as_domain_error() -> None:
    with pytest.raises(PosteriorError, match="calculation failed"):
        log_posterior(Decimal("1e999999"), (), DEFAULT_CONFIG)


def test_evidence_order_and_skip_are_digest_authority() -> None:
    first = _observation(10_000, PairwiseChoice.RIGHT)
    second = _observation(15_000, PairwiseChoice.LEFT)
    skipped = _observation(20_000, PairwiseChoice.SKIP)
    ordered = infer_pairwise_posterior((first, second), DEFAULT_CONFIG)
    reversed_order = infer_pairwise_posterior((second, first), DEFAULT_CONFIG)
    with_skip = infer_pairwise_posterior((first, second, skipped), DEFAULT_CONFIG)
    assert ordered.posterior_mean_ppm == reversed_order.posterior_mean_ppm
    assert ordered.posterior_sd_ppm == reversed_order.posterior_sd_ppm
    assert ordered.evidence_digest != reversed_order.evidence_digest
    assert ordered.digest != reversed_order.digest
    assert with_skip.posterior_mean_ppm == ordered.posterior_mean_ppm
    assert with_skip.posterior_sd_ppm == ordered.posterior_sd_ppm
    assert with_skip.evidence_digest != ordered.evidence_digest


def test_evidence_digest_binds_the_complete_design_cell_authority() -> None:
    baseline = _observation(15_000, PairwiseChoice.RIGHT)
    other_dimension = _observation(
        15_000,
        PairwiseChoice.RIGHT,
        dimension_key="chin_projection",
    )
    other_stimulus_version = _observation(
        15_000,
        PairwiseChoice.RIGHT,
        stimulus_config_version="stimulus-v2",
    )
    baseline_result = infer_pairwise_posterior((baseline,), DEFAULT_CONFIG)
    dimension_result = infer_pairwise_posterior((other_dimension,), DEFAULT_CONFIG)
    version_result = infer_pairwise_posterior((other_stimulus_version,), DEFAULT_CONFIG)
    assert baseline_result.posterior_mean_ppm == dimension_result.posterior_mean_ppm
    assert baseline_result.posterior_mean_ppm == version_result.posterior_mean_ppm
    assert (
        len(
            {
                baseline_result.evidence_digest,
                dimension_result.evidence_digest,
                version_result.evidence_digest,
            }
        )
        == 3
    )


def test_frozen_cross_platform_vectors_and_canonical_result_fields() -> None:
    directional = infer_pairwise_posterior(
        (_observation(15_000, PairwiseChoice.RIGHT),), DEFAULT_CONFIG
    )
    expected_directional_bytes = (
        b'{"algorithm_version":"demo-bayesian-pairwise-logistic-v1",'
        b'"confidence_ppm":394133,'
        b'"consistency_ppm":1000000,'
        b'"evidence_digest":"70eca6b937bc6e2090b11103cf339af646607ceb548d8423def3370e82b6de5b",'
        b'"laplace_sd_ppm":18176,"map_location":"INTERIOR",'
        b'"posterior_config_digest":"a3ce13813e901b935900d7d5251802ff7873cf0d76526088e541362fa365b8de",'
        b'"posterior_mean_ppm":14742,"posterior_sd_ppm":18176,'
        b'"result_schema_version":"demo-posterior-result-v1"}'
    )
    assert canonical_json_bytes(directional.canonical_payload()) == expected_directional_bytes
    assert directional.digest == "e9e1af7b3a88adf2dc9291293710ba20dcda08ee785d09ef5baa9d14a0ade59b"

    tie_only = infer_pairwise_posterior(
        tuple(_observation(15_000, PairwiseChoice.INDISTINGUISHABLE) for _ in range(16)),
        DEFAULT_CONFIG,
    )
    contradiction = infer_pairwise_posterior(
        (
            _observation(15_000, PairwiseChoice.RIGHT),
            _observation(15_000, PairwiseChoice.LEFT),
        ),
        DEFAULT_CONFIG,
    )
    boundary_config = PosteriorConfig(lower_bound_ppm=-500, upper_bound_ppm=500)
    upper = infer_pairwise_posterior(
        tuple(
            _observation(30_000, PairwiseChoice.RIGHT, config=boundary_config) for _ in range(10)
        ),
        boundary_config,
    )
    lower = infer_pairwise_posterior(
        tuple(_observation(30_000, PairwiseChoice.LEFT, config=boundary_config) for _ in range(10)),
        boundary_config,
    )
    assert tie_only.digest == "0455fe1f13d3c07abc1312c1cd1a3b9a307dda13c39a314e5e12ed0ba80ae188"
    assert (
        contradiction.digest == "4deef0311681f76881f7214d87ef0919263c977f7c8ead109cbf71ecd437cdcc"
    )
    assert upper.digest == "f6f5e2d3b9967a70200394b229aed586b994038c147dff569294987d6a58c313"
    assert lower.digest == "0fa3c8aa7c276df65b4edb9571d6525edf74dacd6eaba688396f1f28defb8275"
    assert set(directional.canonical_payload()) == {
        "algorithm_version",
        "confidence_ppm",
        "posterior_config_digest",
        "consistency_ppm",
        "evidence_digest",
        "laplace_sd_ppm",
        "map_location",
        "posterior_mean_ppm",
        "posterior_sd_ppm",
        "result_schema_version",
    }


def test_quantization_is_decimal_half_even_and_normalizes_zero() -> None:
    assert quantize_ppm(Decimal("2.5"), -10, 10) == 2
    assert quantize_ppm(Decimal("3.5"), -10, 10) == 4
    assert quantize_ppm(Decimal("-0.1"), -10, 10) == 0
    assert quantize_ppm(Decimal("100"), -10, 10) == 10
    with pytest.raises(PosteriorError):
        quantize_ppm(Decimal("-0"), -10, 10)
    with pytest.raises(PosteriorError):
        quantize_ppm(Decimal("NaN"), -10, 10)
    with pytest.raises(PosteriorError):
        quantize_ppm(0.5, -10, 10)  # type: ignore[arg-type]


def test_canonical_authority_rejects_float_numeric_strings_bool_and_unknown_types() -> None:
    for value in (0.5, Decimal("0.5"), "0.5", "1", True, {1, 2}):
        with pytest.raises(PosteriorError):
            canonical_json_bytes({"value": value})


def test_result_schema_version_is_frozen() -> None:
    result = infer_pairwise_posterior((), DEFAULT_CONFIG)
    assert result.result_schema_version == RESULT_SCHEMA_VERSION
    assert result.algorithm_version == ALGORITHM_VERSION
    assert b"created_at" not in canonical_json_bytes(result.canonical_payload())
