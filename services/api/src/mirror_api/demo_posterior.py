"""Deterministic Decimal posterior for synthetic pairwise demo evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    FloatOperation,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum
from typing import Final

ALGORITHM_VERSION: Final = "demo-bayesian-pairwise-logistic-v1"
RESULT_SCHEMA_VERSION: Final = "demo-posterior-result-v1"
PPM: Final = 1_000_000
DECIMAL_PRECISION: Final = 50
DECIMAL_EMIN: Final = -999_999
DECIMAL_EMAX: Final = 999_999
DECIMAL_CAPITALS: Final = 1
DECIMAL_CLAMP: Final = 0
EXP_TAIL_CUTOFF_ABS: Final = 128
MAX_ITERATIONS: Final = 32
MAX_AUTHORITY_PPM: Final = 1_000_000

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_NUMERIC_STRING = re.compile(r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?")


def _new_v1_decimal_context() -> Context:
    context = Context(
        prec=DECIMAL_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=DECIMAL_EMIN,
        Emax=DECIMAL_EMAX,
        capitals=DECIMAL_CAPITALS,
        clamp=DECIMAL_CLAMP,
    )
    for signal in context.traps:
        context.traps[signal] = False
    for signal in (DivisionByZero, FloatOperation, InvalidOperation, Overflow):
        context.traps[signal] = True
    context.clear_flags()
    return context


class PosteriorError(ValueError):
    """A fail-closed posterior domain error."""


class PosteriorConvergenceError(PosteriorError):
    """The bounded MAP solver did not establish a valid optimum."""

    def __init__(self, code: ConvergenceCode) -> None:
        self.code = code.value
        super().__init__(self.code)


class ConvergenceCode(StrEnum):
    MAP_GRADIENT_NOT_BRACKETED = "MAP_GRADIENT_NOT_BRACKETED"
    MAP_BRACKET_COLLAPSED = "MAP_BRACKET_COLLAPSED"
    MAP_ITERATION_LIMIT_EXCEEDED = "MAP_ITERATION_LIMIT_EXCEEDED"


class PairwiseChoice(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    INDISTINGUISHABLE = "INDISTINGUISHABLE"
    SKIP = "SKIP"


class MapLocation(StrEnum):
    LOWER_BOUND = "LOWER_BOUND"
    INTERIOR = "INTERIOR"
    UPPER_BOUND = "UPPER_BOUND"


@dataclass(frozen=True, order=True)
class DesignCellKey:
    dimension_key: str
    low_delta_ppm: int
    high_delta_ppm: int
    magnitude_ppm: int
    stimulus_config_version: str
    posterior_config_digest: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "posterior_config_digest": self.posterior_config_digest,
            "dimension_key": self.dimension_key,
            "high_delta_ppm": self.high_delta_ppm,
            "low_delta_ppm": self.low_delta_ppm,
            "magnitude_ppm": self.magnitude_ppm,
            "stimulus_config_version": self.stimulus_config_version,
        }


@dataclass(frozen=True)
class PairwiseObservation:
    dimension_key: str
    left_delta_ppm: int
    right_delta_ppm: int
    magnitude_ppm: int
    stimulus_config_version: str
    posterior_config_digest: str
    choice: PairwiseChoice

    def __post_init__(self) -> None:
        if not isinstance(self.dimension_key, str) or not 1 <= len(self.dimension_key) <= 48:
            raise PosteriorError("dimension_key must contain between 1 and 48 characters")
        if (
            not isinstance(self.stimulus_config_version, str)
            or not 1 <= len(self.stimulus_config_version) <= 64
        ):
            raise PosteriorError("stimulus_config_version must contain between 1 and 64 characters")
        integer_fields = (
            self.left_delta_ppm,
            self.right_delta_ppm,
            self.magnitude_ppm,
        )
        if any(type(value) is not int for value in integer_fields):
            raise PosteriorError("stimulus deltas and magnitude must be true integers")
        if not 1 <= self.magnitude_ppm <= MAX_AUTHORITY_PPM:
            raise PosteriorError("magnitude_ppm is outside the supported authority range")
        if min(self.left_delta_ppm, self.right_delta_ppm) != -self.magnitude_ppm:
            raise PosteriorError("the low stimulus delta must equal negative magnitude_ppm")
        if max(self.left_delta_ppm, self.right_delta_ppm) != self.magnitude_ppm:
            raise PosteriorError("the high stimulus delta must equal magnitude_ppm")
        if (
            not isinstance(self.posterior_config_digest, str)
            or _DIGEST_PATTERN.fullmatch(self.posterior_config_digest) is None
        ):
            raise PosteriorError("posterior_config_digest must be a lowercase SHA-256 digest")
        if not isinstance(self.choice, PairwiseChoice):
            raise PosteriorError("choice must be a PairwiseChoice")

    @property
    def design_cell_key(self) -> DesignCellKey:
        return DesignCellKey(
            dimension_key=self.dimension_key,
            low_delta_ppm=min(self.left_delta_ppm, self.right_delta_ppm),
            high_delta_ppm=max(self.left_delta_ppm, self.right_delta_ppm),
            magnitude_ppm=self.magnitude_ppm,
            stimulus_config_version=self.stimulus_config_version,
            posterior_config_digest=self.posterior_config_digest,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "posterior_config_digest": self.posterior_config_digest,
            "choice": self.choice.value,
            "dimension_key": self.dimension_key,
            "left_delta_ppm": self.left_delta_ppm,
            "magnitude_ppm": self.magnitude_ppm,
            "right_delta_ppm": self.right_delta_ppm,
            "stimulus_config_version": self.stimulus_config_version,
        }


@dataclass(frozen=True)
class PosteriorConfig:
    tau_ppm: int = 15_000
    prior_sd_ppm: int = 30_000
    lower_bound_ppm: int = -30_000
    upper_bound_ppm: int = 30_000
    iteration_limit: int = 32
    gradient_tolerance_ppm: int = 1
    step_tolerance_ppm: int = 1
    algorithm_version: str = ALGORITHM_VERSION

    def __post_init__(self) -> None:
        integer_fields = (
            self.tau_ppm,
            self.prior_sd_ppm,
            self.lower_bound_ppm,
            self.upper_bound_ppm,
            self.iteration_limit,
            self.gradient_tolerance_ppm,
            self.step_tolerance_ppm,
        )
        if any(type(value) is not int for value in integer_fields):
            raise PosteriorError("posterior configuration must use true integers")
        if not 1 <= self.tau_ppm <= MAX_AUTHORITY_PPM:
            raise PosteriorError("tau_ppm is outside the supported authority range")
        if not 1 <= self.prior_sd_ppm <= MAX_AUTHORITY_PPM:
            raise PosteriorError("prior_sd_ppm is outside the supported authority range")
        if not (
            -MAX_AUTHORITY_PPM <= self.lower_bound_ppm < self.upper_bound_ppm <= MAX_AUTHORITY_PPM
            and self.lower_bound_ppm <= 0 <= self.upper_bound_ppm
        ):
            raise PosteriorError("posterior bounds must be ordered and contain zero")
        if not 1 <= self.iteration_limit <= MAX_ITERATIONS:
            raise PosteriorError("iteration_limit is outside the frozen range")
        if not 1 <= self.gradient_tolerance_ppm <= MAX_AUTHORITY_PPM:
            raise PosteriorError("gradient_tolerance_ppm is outside the frozen range")
        max_step_tolerance = min(MAX_AUTHORITY_PPM, self.upper_bound_ppm - self.lower_bound_ppm)
        if not 0 <= self.step_tolerance_ppm <= max_step_tolerance:
            raise PosteriorError("step_tolerance_ppm is outside the frozen range")
        if self.algorithm_version != ALGORITHM_VERSION:
            raise PosteriorError("algorithm_version is not supported")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "boundary_policy": "censored-boundary-prior-uncertainty-v1",
            "bounds_ppm": [self.lower_bound_ppm, self.upper_bound_ppm],
            "confidence_policy": "integer-posterior-sd-complement-v1",
            "contradiction_policy": "count-weighted-unordered-design-cell-reversal-v1",
            "decimal_capitals": DECIMAL_CAPITALS,
            "decimal_clamp": DECIMAL_CLAMP,
            "decimal_context_policy": "fresh-explicit-context-per-authority-call-v1",
            "decimal_emax": DECIMAL_EMAX,
            "decimal_emin": DECIMAL_EMIN,
            "decimal_flags_policy": "clear-on-entry-ignore-nonfatal-do-not-leak-v1",
            "decimal_nonfatal_signals": [
                "Clamped",
                "Inexact",
                "Rounded",
                "Subnormal",
                "Underflow",
            ],
            "decimal_precision": DECIMAL_PRECISION,
            "decimal_rounding": "ROUND_HALF_EVEN",
            "decimal_traps": [
                "DivisionByZero",
                "FloatOperation",
                "InvalidOperation",
                "Overflow",
            ],
            "exp_tail_cutoff_abs": EXP_TAIL_CUTOFF_ABS,
            "exp_tail_policy": "sigmoid-softplus-saturate-inclusive-v1",
            "gradient_tolerance_ppm": self.gradient_tolerance_ppm,
            "iteration_limit": self.iteration_limit,
            "likelihood_policy": "pairwise-logistic-unit-likelihood-utility-difference-v1",
            "prior_policy": "zero-mean-gaussian-v1",
            "prior_sd_ppm": self.prior_sd_ppm,
            "quantization_policy": "clamp-decimal-half-even-normalized-zero-v1",
            "solver_policy": "bounded-safeguarded-newton-kkt-v1",
            "step_tolerance_ppm": self.step_tolerance_ppm,
            "tau_ppm": self.tau_ppm,
            "tie_only_precision_policy": "prior-uncertainty-zero-confidence-v1",
            "uncertainty_policy": "laplace-with-contradiction-floor-v1",
        }

    @property
    def posterior_config_digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True)
class PosteriorResult:
    result_schema_version: str
    algorithm_version: str
    posterior_config_digest: str
    evidence_digest: str
    posterior_mean_ppm: int
    map_location: MapLocation
    laplace_sd_ppm: int
    posterior_sd_ppm: int
    confidence_ppm: int
    consistency_ppm: int

    def __post_init__(self) -> None:
        integer_fields = (
            self.posterior_mean_ppm,
            self.laplace_sd_ppm,
            self.posterior_sd_ppm,
            self.confidence_ppm,
            self.consistency_ppm,
        )
        if any(type(value) is not int for value in integer_fields):
            raise PosteriorError("persistent posterior fields must be true integers")
        if self.result_schema_version != RESULT_SCHEMA_VERSION:
            raise PosteriorError("posterior result schema version is invalid")
        if self.algorithm_version != ALGORITHM_VERSION:
            raise PosteriorError("posterior result algorithm_version is invalid")
        if _DIGEST_PATTERN.fullmatch(self.posterior_config_digest) is None:
            raise PosteriorError("posterior result posterior_config_digest is invalid")
        if _DIGEST_PATTERN.fullmatch(self.evidence_digest) is None:
            raise PosteriorError("posterior result evidence_digest is invalid")
        if not isinstance(self.map_location, MapLocation):
            raise PosteriorError("posterior result map_location is invalid")
        if not 0 <= self.confidence_ppm <= PPM:
            raise PosteriorError("confidence_ppm must be a ppm fraction")
        if not 0 <= self.consistency_ppm <= PPM:
            raise PosteriorError("consistency_ppm must be a ppm fraction")
        if not 0 <= self.posterior_sd_ppm <= MAX_AUTHORITY_PPM:
            raise PosteriorError("posterior_sd_ppm is outside the authority range")
        if not 0 <= self.laplace_sd_ppm <= MAX_AUTHORITY_PPM:
            raise PosteriorError("laplace_sd_ppm is outside the authority range")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "confidence_ppm": self.confidence_ppm,
            "posterior_config_digest": self.posterior_config_digest,
            "consistency_ppm": self.consistency_ppm,
            "evidence_digest": self.evidence_digest,
            "laplace_sd_ppm": self.laplace_sd_ppm,
            "map_location": self.map_location.value,
            "posterior_mean_ppm": self.posterior_mean_ppm,
            "posterior_sd_ppm": self.posterior_sd_ppm,
            "result_schema_version": self.result_schema_version,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.canonical_payload())).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    """Encode only deterministic authority primitives; reject numeric surrogates."""

    _validate_canonical_value(value)
    try:
        encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return encoded.encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise PosteriorError("canonical authority encoding failed") from exc


def _validate_canonical_value(value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        raise PosteriorError("bool is forbidden in canonical posterior authority")
    if type(value) is int:
        return
    if isinstance(value, (float, Decimal)):
        raise PosteriorError("raw numeric values are forbidden in canonical authority")
    if isinstance(value, str):
        if _NUMERIC_STRING.fullmatch(value):
            raise PosteriorError("numeric strings are forbidden in canonical authority")
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


def stable_sigmoid(value: Decimal) -> Decimal:
    decimal_value = _require_decimal(value, "sigmoid input")
    try:
        with localcontext(_new_v1_decimal_context()):
            cutoff = Decimal(EXP_TAIL_CUTOFF_ABS)
            if decimal_value >= cutoff:
                return Decimal(1)
            if decimal_value <= -cutoff:
                return Decimal(0)
            if decimal_value >= 0:
                exponent = (-decimal_value).exp()
                result = Decimal(1) / (Decimal(1) + exponent)
            else:
                exponent = decimal_value.exp()
                result = exponent / (Decimal(1) + exponent)
            return _require_finite(result, "sigmoid result")
    except DecimalException as exc:
        raise PosteriorError("sigmoid calculation failed") from exc


def stable_softplus(value: Decimal) -> Decimal:
    decimal_value = _require_decimal(value, "softplus input")
    try:
        with localcontext(_new_v1_decimal_context()):
            cutoff = Decimal(EXP_TAIL_CUTOFF_ABS)
            if decimal_value >= cutoff:
                return decimal_value
            if decimal_value <= -cutoff:
                return Decimal(0)
            if decimal_value > 0:
                result = decimal_value + (Decimal(1) + (-decimal_value).exp()).ln()
            else:
                result = (Decimal(1) + decimal_value.exp()).ln()
            return _require_finite(result, "softplus result")
    except DecimalException as exc:
        raise PosteriorError("softplus calculation failed") from exc


def log_posterior(
    delta_ppm: Decimal | int,
    observations: Sequence[PairwiseObservation],
    config: PosteriorConfig,
) -> Decimal:
    try:
        with localcontext(_new_v1_decimal_context()):
            value, _, _ = _posterior_terms(delta_ppm, observations, config)
            return value
    except DecimalException as exc:
        raise PosteriorError("log posterior calculation failed") from exc


def log_posterior_gradient(
    delta_ppm: Decimal | int,
    observations: Sequence[PairwiseObservation],
    config: PosteriorConfig,
) -> Decimal:
    try:
        with localcontext(_new_v1_decimal_context()):
            _, gradient, _ = _posterior_terms(delta_ppm, observations, config)
            return gradient
    except DecimalException as exc:
        raise PosteriorError("log posterior gradient calculation failed") from exc


def log_posterior_hessian(
    delta_ppm: Decimal | int,
    observations: Sequence[PairwiseObservation],
    config: PosteriorConfig,
) -> Decimal:
    try:
        with localcontext(_new_v1_decimal_context()):
            _, _, hessian = _posterior_terms(delta_ppm, observations, config)
            return hessian
    except DecimalException as exc:
        raise PosteriorError("log posterior Hessian calculation failed") from exc


def _posterior_terms(
    delta_ppm: Decimal | int,
    observations: Sequence[PairwiseObservation],
    config: PosteriorConfig,
) -> tuple[Decimal, Decimal, Decimal]:
    delta = _require_decimal(delta_ppm, "delta_ppm")
    _validate_observations(observations, config)
    with localcontext(_new_v1_decimal_context()):
        prior_variance = Decimal(config.prior_sd_ppm * config.prior_sd_ppm)
        tau_variance = Decimal(config.tau_ppm * config.tau_ppm)
        log_value = -(delta * delta) / (Decimal(2) * prior_variance)
        gradient = -delta / prior_variance
        hessian = -Decimal(1) / prior_variance
        for observation in observations:
            if observation.choice is PairwiseChoice.SKIP:
                continue
            left = Decimal(observation.left_delta_ppm)
            right = Decimal(observation.right_delta_ppm)
            span = right - left
            utility_delta = span * (Decimal(2) * delta - left - right) / (Decimal(2) * tau_variance)
            utility_delta = Decimal(0) if utility_delta.is_zero() else utility_delta
            slope = span / tau_variance
            probability = stable_sigmoid(utility_delta)
            response = _choice_probability(observation.choice)
            weight = Decimal(_choice_weight_ppm(observation.choice)) / Decimal(PPM)
            log_value += weight * (response * utility_delta - stable_softplus(utility_delta))
            gradient += weight * slope * (response - probability)
            hessian -= weight * slope * slope * probability * (Decimal(1) - probability)
        log_value = _require_finite(log_value, "log posterior")
        gradient = _require_finite(gradient, "log posterior gradient")
        hessian = _require_finite(hessian, "log posterior hessian")
        if hessian >= 0:
            raise PosteriorError("posterior Hessian is not strictly negative")
        return log_value, gradient, hessian


def _choice_probability(choice: PairwiseChoice) -> Decimal:
    if choice is PairwiseChoice.LEFT:
        return Decimal(0)
    if choice is PairwiseChoice.RIGHT:
        return Decimal(1)
    if choice is PairwiseChoice.INDISTINGUISHABLE:
        return Decimal(1) / Decimal(2)
    raise PosteriorError("SKIP has no likelihood probability")


def _choice_weight_ppm(choice: PairwiseChoice) -> int:
    if choice in (
        PairwiseChoice.LEFT,
        PairwiseChoice.RIGHT,
        PairwiseChoice.INDISTINGUISHABLE,
    ):
        return PPM
    if choice is PairwiseChoice.SKIP:
        return 0
    raise PosteriorError("unsupported pairwise choice")


def infer_pairwise_posterior(
    observations: Sequence[PairwiseObservation], config: PosteriorConfig = PosteriorConfig()
) -> PosteriorResult:
    """Find the bounded logistic MAP and deterministic posterior authority."""

    try:
        with localcontext(_new_v1_decimal_context()):
            return _infer_pairwise_posterior(observations, config)
    except DecimalException as exc:
        raise PosteriorError("posterior authority calculation failed") from exc


def _infer_pairwise_posterior(
    observations: Sequence[PairwiseObservation], config: PosteriorConfig
) -> PosteriorResult:

    observation_tuple = tuple(observations)
    _validate_observations(observation_tuple, config)
    evidence_digest = _evidence_digest(observation_tuple)
    directional_count = sum(
        item.choice in (PairwiseChoice.LEFT, PairwiseChoice.RIGHT) for item in observation_tuple
    )
    effective_count = sum(item.choice is not PairwiseChoice.SKIP for item in observation_tuple)
    if effective_count == 0:
        return _no_response_result(config, evidence_digest=evidence_digest)

    effective = tuple(item for item in observation_tuple if item.choice is not PairwiseChoice.SKIP)
    map_delta, map_location = _bounded_map(effective, config)
    _, _, hessian = _posterior_terms(map_delta, effective, config)
    with localcontext(_new_v1_decimal_context()):
        try:
            laplace_sd = (-Decimal(1) / hessian).sqrt()
        except (InvalidOperation, ValueError) as exc:
            raise PosteriorError("Laplace standard deviation is invalid") from exc
        laplace_sd = _require_finite(laplace_sd, "Laplace standard deviation")
        if laplace_sd < 0:
            raise PosteriorError("Laplace standard deviation is negative")
        contradiction_rate = _contradiction_rate(effective)
        contradiction_ppm = quantize_ppm(contradiction_rate * Decimal(PPM), 0, PPM)
        if map_location is not MapLocation.INTERIOR or directional_count == 0:
            posterior_sd = Decimal(config.prior_sd_ppm)
        else:
            contradiction_floor = Decimal(config.prior_sd_ppm) * contradiction_rate
            posterior_sd = max(laplace_sd, contradiction_floor)
            posterior_sd = min(posterior_sd, Decimal(config.prior_sd_ppm))

        mean_ppm = quantize_ppm(map_delta, config.lower_bound_ppm, config.upper_bound_ppm)
        laplace_sd_ppm = quantize_ppm(laplace_sd, 0, config.prior_sd_ppm)
        posterior_sd_ppm = quantize_ppm(posterior_sd, 0, config.prior_sd_ppm)
        if map_location is not MapLocation.INTERIOR or directional_count == 0:
            confidence_ppm = 0
        else:
            confidence_ppm = quantize_ppm(
                Decimal(PPM)
                * Decimal(config.prior_sd_ppm - posterior_sd_ppm)
                / Decimal(config.prior_sd_ppm),
                0,
                PPM,
            )
        consistency_ppm = PPM - contradiction_ppm

    return PosteriorResult(
        result_schema_version=RESULT_SCHEMA_VERSION,
        algorithm_version=config.algorithm_version,
        posterior_config_digest=config.posterior_config_digest,
        evidence_digest=evidence_digest,
        posterior_mean_ppm=mean_ppm,
        map_location=map_location,
        laplace_sd_ppm=laplace_sd_ppm,
        posterior_sd_ppm=posterior_sd_ppm,
        confidence_ppm=confidence_ppm,
        consistency_ppm=consistency_ppm,
    )


def _no_response_result(
    config: PosteriorConfig,
    *,
    evidence_digest: str,
) -> PosteriorResult:
    return PosteriorResult(
        result_schema_version=RESULT_SCHEMA_VERSION,
        algorithm_version=config.algorithm_version,
        posterior_config_digest=config.posterior_config_digest,
        evidence_digest=evidence_digest,
        posterior_mean_ppm=0,
        map_location=_map_location(Decimal(0), config),
        laplace_sd_ppm=config.prior_sd_ppm,
        posterior_sd_ppm=config.prior_sd_ppm,
        confidence_ppm=0,
        consistency_ppm=PPM,
    )


def _bounded_map(
    observations: Sequence[PairwiseObservation], config: PosteriorConfig
) -> tuple[Decimal, MapLocation]:
    lower = Decimal(config.lower_bound_ppm)
    upper = Decimal(config.upper_bound_ppm)

    _, lower_gradient, _ = _posterior_terms(lower, observations, config)
    if _kkt_satisfied(lower, lower_gradient, config, MapLocation.LOWER_BOUND):
        return lower, MapLocation.LOWER_BOUND
    _, upper_gradient, _ = _posterior_terms(upper, observations, config)
    if _kkt_satisfied(upper, upper_gradient, config, MapLocation.UPPER_BOUND):
        return upper, MapLocation.UPPER_BOUND
    if lower_gradient <= 0 or upper_gradient >= 0:
        raise PosteriorConvergenceError(ConvergenceCode.MAP_GRADIENT_NOT_BRACKETED)

    bracket_lower = lower
    bracket_upper = upper
    current = Decimal(0)
    for _ in range(config.iteration_limit):
        _, gradient, hessian = _posterior_terms(current, observations, config)
        if _kkt_satisfied(current, gradient, config, MapLocation.INTERIOR):
            return current, MapLocation.INTERIOR

        if gradient > 0:
            bracket_lower = current
        else:
            bracket_upper = current
        if bracket_lower >= bracket_upper:
            raise PosteriorConvergenceError(ConvergenceCode.MAP_BRACKET_COLLAPSED)

        midpoint = (bracket_lower + bracket_upper) / Decimal(2)
        newton_candidate = current - gradient / hessian
        bracket_width = bracket_upper - bracket_lower
        guard = bracket_width / Decimal(20)
        newton_has_sufficient_progress = (
            newton_candidate.is_finite()
            and bracket_lower + guard <= newton_candidate <= bracket_upper - guard
            and abs(newton_candidate - current) > Decimal(config.step_tolerance_ppm)
        )
        candidate = newton_candidate if newton_has_sufficient_progress else midpoint
        if not candidate.is_finite():
            raise PosteriorError("safeguarded Newton candidate is invalid")
        current = Decimal(0) if candidate.is_zero() else candidate

    _, gradient, _ = _posterior_terms(current, observations, config)
    if _kkt_satisfied(current, gradient, config, MapLocation.INTERIOR):
        return current, MapLocation.INTERIOR
    raise PosteriorConvergenceError(ConvergenceCode.MAP_ITERATION_LIMIT_EXCEEDED)


def _kkt_satisfied(
    delta_ppm: Decimal,
    gradient: Decimal,
    config: PosteriorConfig,
    location: MapLocation,
) -> bool:
    tolerance = Decimal(config.gradient_tolerance_ppm) / Decimal(
        config.prior_sd_ppm * config.prior_sd_ppm
    )
    if location is MapLocation.LOWER_BOUND:
        return delta_ppm == Decimal(config.lower_bound_ppm) and gradient <= tolerance
    if location is MapLocation.UPPER_BOUND:
        return delta_ppm == Decimal(config.upper_bound_ppm) and gradient >= -tolerance
    return (
        Decimal(config.lower_bound_ppm) < delta_ppm < Decimal(config.upper_bound_ppm)
        and abs(gradient) <= tolerance
    )


def _contradiction_rate(observations: Sequence[PairwiseObservation]) -> Decimal:
    counts: dict[DesignCellKey, list[int]] = {}
    directional_total = 0
    for observation in observations:
        if observation.choice not in (PairwiseChoice.LEFT, PairwiseChoice.RIGHT):
            continue
        chosen_delta = (
            observation.left_delta_ppm
            if observation.choice is PairwiseChoice.LEFT
            else observation.right_delta_ppm
        )
        cell_counts = counts.setdefault(observation.design_cell_key, [0, 0])
        if chosen_delta == observation.design_cell_key.low_delta_ppm:
            cell_counts[0] += 1
        else:
            cell_counts[1] += 1
        directional_total += 1
    if directional_total == 0:
        return Decimal(0)
    minority_total = sum(min(low_count, high_count) for low_count, high_count in counts.values())
    with localcontext(_new_v1_decimal_context()):
        return Decimal(2 * minority_total) / Decimal(directional_total)


def _evidence_digest(observations: Sequence[PairwiseObservation]) -> str:
    payload = {
        "observations": [
            observation.canonical_payload() | {"ordinal": ordinal}
            for ordinal, observation in enumerate(observations, start=1)
        ]
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _map_location(delta_ppm: Decimal, config: PosteriorConfig) -> MapLocation:
    if delta_ppm == Decimal(config.lower_bound_ppm):
        return MapLocation.LOWER_BOUND
    if delta_ppm == Decimal(config.upper_bound_ppm):
        return MapLocation.UPPER_BOUND
    return MapLocation.INTERIOR


def _validate_observations(
    observations: Sequence[PairwiseObservation], config: PosteriorConfig
) -> None:
    if isinstance(observations, (str, bytes, bytearray)) or not isinstance(observations, Sequence):
        raise PosteriorError("observations must be a sequence")
    posterior_config_digest = config.posterior_config_digest
    dimension_key: str | None = None
    for observation in observations:
        if not isinstance(observation, PairwiseObservation):
            raise PosteriorError("each observation must be a PairwiseObservation")
        if observation.posterior_config_digest != posterior_config_digest:
            raise PosteriorError("observation posterior_config_digest does not match config")
        if dimension_key is None:
            dimension_key = observation.dimension_key
        elif observation.dimension_key != dimension_key:
            raise PosteriorError("posterior observations must contain exactly one dimension_key")


def quantize_ppm(value: Decimal | int, lower: int, upper: int) -> int:
    """Clamp a finite Decimal then round half even to an integer authority."""

    if type(lower) is not int or type(upper) is not int:
        raise PosteriorError("quantization bounds must be true integers")
    if lower > upper:
        raise PosteriorError("quantization bounds must be ordered")
    decimal_value = _require_decimal(value, "quantization value")
    try:
        with localcontext(_new_v1_decimal_context()):
            clamped = min(max(decimal_value, Decimal(lower)), Decimal(upper))
            result = int(clamped.to_integral_value(rounding=ROUND_HALF_EVEN))
            return 0 if result == 0 else result
    except DecimalException as exc:
        raise PosteriorError("quantization calculation failed") from exc


def _require_decimal(value: Decimal | int, description: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or isinstance(value, str):
        raise PosteriorError(f"{description} must be an integer or Decimal")
    if type(value) is int:
        decimal_value = Decimal(value)
    elif isinstance(value, Decimal):
        decimal_value = value
    else:
        raise PosteriorError(f"{description} must be an integer or Decimal")
    if not decimal_value.is_finite():
        raise PosteriorError(f"{description} must be finite")
    if decimal_value.is_zero() and decimal_value.is_signed():
        raise PosteriorError(f"{description} cannot be negative zero")
    return decimal_value


def _require_finite(value: Decimal, description: str) -> Decimal:
    if not value.is_finite():
        raise PosteriorError(f"{description} is non-finite")
    return Decimal(0) if value.is_zero() else value
