"""Deterministic, stdlib-only posterior for synthetic pairwise demo evidence."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Final

ALGORITHM_VERSION: Final = "demo-bayesian-pairwise-logistic-v1"
_PPM: Final = 1_000_000
_DECIMAL_STRING = re.compile(r"[+-]?(?:(?:\d+\.\d*)|(?:\d*\.\d+)|(?:\d+[eE][+-]?\d+))")


class PosteriorError(ValueError):
    """A fail-closed posterior domain error."""


class PosteriorConvergenceError(PosteriorError):
    """The bounded MAP solver did not establish a valid optimum."""


class PairwiseChoice(Enum):
    LEFT = 0
    RIGHT = 1
    INDISTINGUISHABLE = Fraction(1, 2)
    SKIP = "SKIP"


@dataclass(frozen=True)
class PairwiseObservation:
    left_ppm: int
    right_ppm: int
    choice: PairwiseChoice

    def __post_init__(self) -> None:
        if isinstance(self.left_ppm, bool) or not isinstance(self.left_ppm, int):
            raise PosteriorError("left_ppm must be an integer")
        if isinstance(self.right_ppm, bool) or not isinstance(self.right_ppm, int):
            raise PosteriorError("right_ppm must be an integer")
        if not isinstance(self.choice, PairwiseChoice):
            raise PosteriorError("choice must be a PairwiseChoice")


@dataclass(frozen=True)
class PosteriorConfig:
    tau_ppm: int = 15_000
    prior_sd_ppm: int = 30_000
    lower_bound_ppm: int = -30_000
    upper_bound_ppm: int = 30_000
    iteration_limit: int = 32
    gradient_tolerance: int = 1
    step_tolerance_ppm: int = 1
    algorithm_version: str = ALGORITHM_VERSION

    def __post_init__(self) -> None:
        integer_fields = (
            self.tau_ppm,
            self.prior_sd_ppm,
            self.lower_bound_ppm,
            self.upper_bound_ppm,
            self.iteration_limit,
            self.gradient_tolerance,
            self.step_tolerance_ppm,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in integer_fields):
            raise PosteriorError("posterior configuration must use integers")
        if self.tau_ppm <= 0 or self.prior_sd_ppm <= 0:
            raise PosteriorError("tau_ppm and prior_sd_ppm must be positive")
        if self.lower_bound_ppm >= self.upper_bound_ppm:
            raise PosteriorError("posterior bounds must be ordered")
        if self.iteration_limit <= 0:
            raise PosteriorError("iteration_limit must be positive")
        if self.gradient_tolerance < 0 or self.step_tolerance_ppm < 0:
            raise PosteriorError("solver tolerances must be non-negative")
        if not self.algorithm_version or _DECIMAL_STRING.fullmatch(self.algorithm_version):
            raise PosteriorError("algorithm_version must be a non-numeric authority string")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "bounds_ppm": [self.lower_bound_ppm, self.upper_bound_ppm],
            "confidence_formula": "clamped posterior uncertainty complement",
            "contradiction_formula": "maximum normalized unordered design-cell reversal rate",
            "gradient_tolerance": self.gradient_tolerance,
            "gradient_tolerance_formula": "prior curvature scaled gradient threshold",
            "iteration_limit": self.iteration_limit,
            "laplace_formula": "negative inverse local curvature square root",
            "likelihood": "pairwise logistic utility difference",
            "prior": "zero mean Gaussian",
            "prior_sd_ppm": self.prior_sd_ppm,
            "quantization": "clamp then integer round half even with normalized zero",
            "step_tolerance_ppm": self.step_tolerance_ppm,
            "tau_ppm": self.tau_ppm,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True)
class PosteriorResult:
    posterior_mean_ppm: int
    laplace_sd_ppm: int
    posterior_sd_ppm: int
    confidence_ppm: int
    consistency_ppm: int
    config_digest: str
    algorithm_version: str

    def __post_init__(self) -> None:
        integer_fields = (
            self.posterior_mean_ppm,
            self.laplace_sd_ppm,
            self.posterior_sd_ppm,
            self.confidence_ppm,
            self.consistency_ppm,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in integer_fields):
            raise PosteriorError("persistent posterior fields must be integers")
        if not 0 <= self.confidence_ppm <= _PPM or not 0 <= self.consistency_ppm <= _PPM:
            raise PosteriorError("confidence and consistency must be ppm fractions")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "confidence_ppm": self.confidence_ppm,
            "config_digest": self.config_digest,
            "consistency_ppm": self.consistency_ppm,
            "laplace_sd_ppm": self.laplace_sd_ppm,
            "posterior_mean_ppm": self.posterior_mean_ppm,
            "posterior_sd_ppm": self.posterior_sd_ppm,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.canonical_payload())).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    """Encode only deterministic authority primitives; reject float-like values."""
    _validate_canonical_value(value)
    try:
        encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return encoded.encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PosteriorError("canonical authority encoding failed") from exc


def _validate_canonical_value(value: object) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise PosteriorError("raw float is forbidden in canonical authority")
    if isinstance(value, str):
        if _DECIMAL_STRING.fullmatch(value):
            raise PosteriorError("decimal string is forbidden in canonical authority")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise PosteriorError("canonical authority mapping keys must be strings")
            _validate_canonical_value(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_canonical_value(item)
        return
    raise PosteriorError("canonical authority does not support this value type")


def stable_sigmoid(value: float) -> float:
    if not math.isfinite(value):
        raise PosteriorError("non-finite likelihood input")
    if value >= 0:
        exponent = math.exp(-value)
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def stable_softplus(value: float) -> float:
    if not math.isfinite(value):
        raise PosteriorError("non-finite likelihood input")
    if value > 0:
        return value + math.log1p(math.exp(-value))
    return math.log1p(math.exp(value))


def log_posterior(
    delta_ppm: float, observations: Sequence[PairwiseObservation], config: PosteriorConfig
) -> float:
    value, _, _ = _posterior_terms(delta_ppm, observations, config)
    return value


def log_posterior_gradient(
    delta_ppm: float, observations: Sequence[PairwiseObservation], config: PosteriorConfig
) -> float:
    _, gradient, _ = _posterior_terms(delta_ppm, observations, config)
    return gradient


def log_posterior_hessian(
    delta_ppm: float, observations: Sequence[PairwiseObservation], config: PosteriorConfig
) -> float:
    _, _, hessian = _posterior_terms(delta_ppm, observations, config)
    return hessian


def _posterior_terms(
    delta_ppm: float, observations: Sequence[PairwiseObservation], config: PosteriorConfig
) -> tuple[float, float, float]:
    if not math.isfinite(delta_ppm):
        raise PosteriorError("delta_ppm must be finite")
    try:
        prior_variance = float(config.prior_sd_ppm * config.prior_sd_ppm)
        tau_variance = float(config.tau_ppm * config.tau_ppm)
        log_value = -(delta_ppm * delta_ppm) / (2.0 * prior_variance)
        gradient = -delta_ppm / prior_variance
        hessian = -1.0 / prior_variance
        for observation in observations:
            if observation.choice is PairwiseChoice.SKIP:
                continue
            difference = observation.right_ppm - observation.left_ppm
            slope = difference / tau_variance
            utility_delta = -(
                (observation.right_ppm - delta_ppm) ** 2 - (observation.left_ppm - delta_ppm) ** 2
            ) / (2.0 * tau_variance)
            probability = stable_sigmoid(utility_delta)
            response = _choice_probability(observation.choice)
            log_value += response * utility_delta - stable_softplus(utility_delta)
            gradient += slope * (response - probability)
            hessian -= slope * slope * probability * (1.0 - probability)
    except (OverflowError, ValueError) as exc:
        raise PosteriorError("posterior arithmetic overflowed") from exc
    if not all(math.isfinite(item) for item in (log_value, gradient, hessian)) or hessian >= 0:
        raise PosteriorError("posterior derivatives are invalid")
    return log_value, gradient, hessian


def _choice_probability(choice: PairwiseChoice) -> float:
    if choice is PairwiseChoice.LEFT:
        return 0.0
    if choice is PairwiseChoice.RIGHT:
        return 1.0
    if choice is PairwiseChoice.INDISTINGUISHABLE:
        return 0.5
    raise PosteriorError("SKIP has no likelihood probability")


def infer_pairwise_posterior(
    observations: Sequence[PairwiseObservation], config: PosteriorConfig = PosteriorConfig()
) -> PosteriorResult:
    """Find the bounded logistic MAP and deterministic Laplace-style uncertainty."""
    effective = tuple(item for item in observations if item.choice is not PairwiseChoice.SKIP)
    if not effective:
        return _no_response_result(config)
    map_delta = _bounded_map(effective, config)
    _, _, hessian = _posterior_terms(map_delta, effective, config)
    laplace_sd = math.sqrt(-1.0 / hessian)
    if not math.isfinite(laplace_sd) or laplace_sd < 0:
        raise PosteriorError("Laplace standard deviation is invalid")
    reversal_rate = _contradiction_rate(effective)
    floor_sd = config.prior_sd_ppm * reversal_rate
    posterior_sd = max(laplace_sd, floor_sd)
    mean_ppm = quantize_ppm(map_delta, config.lower_bound_ppm, config.upper_bound_ppm)
    laplace_sd_ppm = quantize_ppm(laplace_sd, 0, config.prior_sd_ppm)
    posterior_sd_ppm = quantize_ppm(posterior_sd, 0, config.prior_sd_ppm)
    consistency_ppm = _quantize_unit_interval(1.0 - reversal_rate)
    confidence_ppm = _quantize_unit_interval(1.0 - (posterior_sd / config.prior_sd_ppm))
    return PosteriorResult(
        posterior_mean_ppm=mean_ppm,
        laplace_sd_ppm=laplace_sd_ppm,
        posterior_sd_ppm=posterior_sd_ppm,
        confidence_ppm=confidence_ppm,
        consistency_ppm=consistency_ppm,
        config_digest=config.digest,
        algorithm_version=config.algorithm_version,
    )


def _no_response_result(config: PosteriorConfig) -> PosteriorResult:
    return PosteriorResult(
        posterior_mean_ppm=0,
        laplace_sd_ppm=config.prior_sd_ppm,
        posterior_sd_ppm=config.prior_sd_ppm,
        confidence_ppm=0,
        consistency_ppm=_PPM,
        config_digest=config.digest,
        algorithm_version=config.algorithm_version,
    )


def _bounded_map(observations: Sequence[PairwiseObservation], config: PosteriorConfig) -> float:
    lower = float(config.lower_bound_ppm)
    upper = float(config.upper_bound_ppm)

    _, lower_gradient, _ = _posterior_terms(lower, observations, config)
    if _kkt_satisfied(lower, lower_gradient, config):
        return lower
    _, upper_gradient, _ = _posterior_terms(upper, observations, config)
    if _kkt_satisfied(upper, upper_gradient, config):
        return upper
    if lower_gradient <= 0 or upper_gradient >= 0:
        raise PosteriorConvergenceError("posterior gradient does not bracket an interior MAP")

    bracket_lower = lower
    bracket_upper = upper
    current = min(max(0.0, lower), upper)
    for _ in range(config.iteration_limit):
        _, gradient, hessian = _posterior_terms(current, observations, config)
        if _kkt_satisfied(current, gradient, config):
            return current

        if gradient > 0:
            bracket_lower = current
        else:
            bracket_upper = current
        if bracket_lower >= bracket_upper:
            raise PosteriorConvergenceError("posterior MAP bracket collapsed")

        midpoint = (bracket_lower + bracket_upper) / 2.0
        newton_candidate = current - (gradient / hessian)
        bracket_width = bracket_upper - bracket_lower
        guard = bracket_width / 20.0
        newton_has_sufficient_progress = (
            math.isfinite(newton_candidate)
            and bracket_lower + guard <= newton_candidate <= bracket_upper - guard
            and abs(newton_candidate - current) > config.step_tolerance_ppm
        )
        candidate = newton_candidate if newton_has_sufficient_progress else midpoint
        if not math.isfinite(candidate):
            raise PosteriorError("safeguarded Newton candidate is invalid")
        current = candidate
    _, gradient, _ = _posterior_terms(current, observations, config)
    if _kkt_satisfied(current, gradient, config):
        return current
    raise PosteriorConvergenceError("bounded Newton did not converge to KKT conditions")


def _kkt_satisfied(delta_ppm: float, gradient: float, config: PosteriorConfig) -> bool:
    tolerance = float(config.gradient_tolerance) / (config.prior_sd_ppm * config.prior_sd_ppm)
    lower = float(config.lower_bound_ppm)
    upper = float(config.upper_bound_ppm)
    if delta_ppm <= lower:
        return gradient <= tolerance
    if delta_ppm >= upper:
        return gradient >= -tolerance
    return abs(gradient) <= tolerance


def _contradiction_rate(observations: Sequence[PairwiseObservation]) -> float:
    counts: dict[tuple[int, int], Counter[PairwiseChoice]] = {}
    for observation in observations:
        if observation.choice not in (PairwiseChoice.LEFT, PairwiseChoice.RIGHT):
            continue
        left_ppm = observation.left_ppm
        right_ppm = observation.right_ppm
        choice = observation.choice
        if left_ppm > right_ppm:
            left_ppm, right_ppm = right_ppm, left_ppm
            choice = PairwiseChoice.RIGHT if choice is PairwiseChoice.LEFT else PairwiseChoice.LEFT
        cell = (left_ppm, right_ppm)
        counts.setdefault(cell, Counter())[choice] += 1
    if not counts:
        return 0.0
    return max(
        (2.0 * min(cell[PairwiseChoice.LEFT], cell[PairwiseChoice.RIGHT]))
        / (cell[PairwiseChoice.LEFT] + cell[PairwiseChoice.RIGHT])
        for cell in counts.values()
    )


def quantize_ppm(value: float, lower: int, upper: int) -> int:
    """Clamp then use Python's specified round-half-even integer quantizer."""
    if not math.isfinite(value):
        raise PosteriorError("cannot quantize a non-finite value")
    if lower > upper:
        raise PosteriorError("quantization bounds must be ordered")
    result = round(min(max(value, float(lower)), float(upper)))
    return 0 if result == 0 else result


def _quantize_unit_interval(value: float) -> int:
    return quantize_ppm(value * _PPM, 0, _PPM)
