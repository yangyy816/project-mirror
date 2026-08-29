"""Pure, deterministic routing for the Demo P4 screened-bank boundary.

This module deliberately has no persistence, runtime generation, provider, or
router dependency. Frozen D02/M3/M4 contracts are sufficient for this domain
implementation; real bank replay remains deferred until runtime evidence is
actually required.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from typing import Final, Protocol

from mirror_api.demo_posterior import PPM, PosteriorResult

ROUTING_ALGORITHM_VERSION: Final = "demo-self-conditioned-routing-v1"
ROUTING_STATUS: Final = "IMPLEMENTATION_READY"
REAL_BANK_INTEGRATION_STATUS: Final = "REAL_BANK_INTEGRATION_DEFERRED_PENDING_EVIDENCE"
QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS: Final = 0
CONTRADICTION_PRIORITY_FLOOR_PPM: Final = 500_000


class RoutingError(ValueError):
    """A fail-closed routing input or eligibility error."""


class RouteStopReason(StrEnum):
    CONTINUE_MINIMUM_NOT_REACHED = "CONTINUE_MINIMUM_NOT_REACHED"
    CONTINUE_COVERAGE_UNMET = "CONTINUE_COVERAGE_UNMET"
    COMPLETE_COVERAGE_MET = "COMPLETE_COVERAGE_MET"
    FAIL_CLOSED_COVERAGE_UNMET_AT_MAXIMUM = "FAIL_CLOSED_COVERAGE_UNMET_AT_MAXIMUM"


@dataclass(frozen=True)
class SelfStateMeasurement:
    """One continuous, reliable SelfState measurement in integer ppm."""

    dimension_id: str
    value_ppm: int
    reliability_ppm: int
    supported: bool = True

    def __post_init__(self) -> None:
        _validate_id(self.dimension_id, "dimension_id")
        _validate_ppm(self.value_ppm, "value_ppm", signed=True)
        _validate_ppm(self.reliability_ppm, "reliability_ppm")
        if type(self.supported) is not bool:
            raise RoutingError("supported must be a bool")


@dataclass(frozen=True)
class SelfStateSnapshot:
    """A structured snapshot, never a sensitive-class label or classifier."""

    self_state_version_id: str
    measurements: tuple[SelfStateMeasurement, ...]

    def __post_init__(self) -> None:
        _validate_id(self.self_state_version_id, "self_state_version_id")
        if not self.measurements:
            raise RoutingError("self state must contain measurements")
        ids = tuple(measurement.dimension_id for measurement in self.measurements)
        if len(set(ids)) != len(ids):
            raise RoutingError("self state dimension_ids must be unique")

    @property
    def by_dimension(self) -> Mapping[str, SelfStateMeasurement]:
        return {measurement.dimension_id: measurement for measurement in self.measurements}


@dataclass(frozen=True)
class QuestionPair:
    """Pre-screened pair metadata required by the pure scheduler.

    ``morphology_anchor_ppm`` contains only continuous measurement values.  Its
    keys are deliberately dimensions rather than any sensitive grouping.
    """

    pair_id: str
    dimension_id: str
    magnitude_ppm: int
    source_identity_id: str
    morphology_anchor_ppm: Mapping[str, int]
    expected_fisher_information_ppm: int
    pair_quality_ppm: int
    eligible: bool = True

    def __post_init__(self) -> None:
        _validate_id(self.pair_id, "pair_id")
        _validate_id(self.dimension_id, "dimension_id")
        if type(self.magnitude_ppm) is not int or not 1 <= self.magnitude_ppm <= PPM:
            raise RoutingError("magnitude_ppm must be an integer in (0, PPM]")
        _validate_id(self.source_identity_id, "source_identity_id")
        if not self.morphology_anchor_ppm:
            raise RoutingError("morphology_anchor_ppm must not be empty")
        for dimension_id, value_ppm in self.morphology_anchor_ppm.items():
            _validate_id(dimension_id, "morphology anchor dimension_id")
            _validate_ppm(value_ppm, "morphology anchor value_ppm", signed=True)
        _validate_ppm(self.expected_fisher_information_ppm, "expected_fisher_information_ppm")
        _validate_ppm(self.pair_quality_ppm, "pair_quality_ppm")
        if type(self.eligible) is not bool:
            raise RoutingError("eligible must be a bool")


class QuestionBank(Protocol):
    """Narrow typed boundary for an already-screened, read-only pair bank."""

    @property
    def pairs(self) -> Sequence[QuestionPair]: ...

    @property
    def morphology_scale_ppm(self) -> Mapping[str, int]: ...

    @property
    def morphology_scale_floor_ppm(self) -> int: ...


@dataclass(frozen=True)
class FixtureQuestionBank:
    """Test-only bank implementation; it must not be mistaken for D02 evidence."""

    pairs: tuple[QuestionPair, ...]
    morphology_scale_ppm: Mapping[str, int]
    morphology_scale_floor_ppm: int
    fixture_only: bool = True

    def __post_init__(self) -> None:
        if not self.fixture_only:
            raise RoutingError("this implementation is fixture-only")
        if not self.pairs:
            raise RoutingError("QuestionBank pairs must not be empty")
        if len({pair.pair_id for pair in self.pairs}) != len(self.pairs):
            raise RoutingError("QuestionBank pair_ids must be unique")
        if type(self.morphology_scale_floor_ppm) is not int or self.morphology_scale_floor_ppm < 1:
            raise RoutingError("morphology_scale_floor_ppm must be a positive true integer")
        if not self.morphology_scale_ppm:
            raise RoutingError("morphology_scale_ppm must be explicitly provided")
        for dimension_id, scale_ppm in self.morphology_scale_ppm.items():
            _validate_id(dimension_id, "morphology scale dimension_id")
            if type(scale_ppm) is not int or scale_ppm < self.morphology_scale_floor_ppm:
                raise RoutingError("morphology scales must satisfy the frozen nonzero floor")
        for pair in self.pairs:
            if pair.dimension_id not in pair.morphology_anchor_ppm:
                raise RoutingError("pair morphology anchor must include its target dimension")
            missing = set(pair.morphology_anchor_ppm) - set(self.morphology_scale_ppm)
            if missing:
                raise RoutingError("every morphology anchor requires an explicit robust scale")


@dataclass(frozen=True)
class DimensionProgress:
    """Append-only run facts consumed by scheduling and stopping logic."""

    dimension_id: str
    posterior: PosteriorResult
    valid_answers: int
    magnitude_ppm_seen: tuple[int, ...]
    source_identity_ids_seen: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_id(self.dimension_id, "dimension_id")
        if type(self.valid_answers) is not int or self.valid_answers < 0:
            raise RoutingError("valid_answers must be a non-negative true integer")
        for magnitude_ppm in self.magnitude_ppm_seen:
            if type(magnitude_ppm) is not int or not 1 <= magnitude_ppm <= PPM:
                raise RoutingError("magnitude_ppm_seen must contain ppm integers")
        for source_id in self.source_identity_ids_seen:
            _validate_id(source_id, "source_identity_id")


@dataclass(frozen=True)
class RoutingPolicy:
    minimum_questions: int = 12
    maximum_questions: int = 16
    minimum_valid_answers_per_dimension: int = 4
    minimum_magnitudes_per_dimension: int = 2
    minimum_source_identities_per_dimension: int = 2

    def __post_init__(self) -> None:
        integer_fields = (
            self.minimum_questions,
            self.maximum_questions,
            self.minimum_valid_answers_per_dimension,
            self.minimum_magnitudes_per_dimension,
            self.minimum_source_identities_per_dimension,
        )
        if any(type(value) is not int for value in integer_fields):
            raise RoutingError("routing policy fields must be true integers")
        if not 12 <= self.minimum_questions <= self.maximum_questions <= 16:
            raise RoutingError("question budget must be within the frozen 12–16 range")
        if self.minimum_valid_answers_per_dimension < 1:
            raise RoutingError("minimum_valid_answers_per_dimension must be positive")
        if self.minimum_magnitudes_per_dimension < 1:
            raise RoutingError("minimum_magnitudes_per_dimension must be positive")
        if self.minimum_source_identities_per_dimension < 1:
            raise RoutingError("minimum_source_identities_per_dimension must be positive")


@dataclass(frozen=True)
class LmnResult:
    eligible: bool
    standardized_rms_ppm: int | None
    shared_reliable_dimensions: tuple[str, ...]
    factor_ppm: int
    reason: str


@dataclass(frozen=True)
class RoutingScore:
    pair_id: str
    dimension_id: str
    score_ppm: int
    posterior_uncertainty_ppm: int
    self_state_reliability_ppm: int
    coverage_need_ppm: int
    expected_fisher_information_ppm: int
    morphology_neighborhood_compatibility_ppm: int
    pair_quality_ppm: int
    contradiction_priority_ppm: int
    standardized_lmn_rms_ppm: int | None
    eligible: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class RoutePlan:
    selected_pair_ids: tuple[str, ...]
    scores: tuple[RoutingScore, ...]
    routing_status: str = ROUTING_STATUS
    real_bank_integration_status: str = REAL_BANK_INTEGRATION_STATUS
    questionnaire_runtime_generative_calls: int = QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS


@dataclass(frozen=True)
class StopDecision:
    should_stop: bool
    reason: RouteStopReason
    coverage_complete: bool
    total_questions_asked: int
    incomplete_dimension_ids: tuple[str, ...]


@dataclass(frozen=True)
class DesiredDeltaDimensionInput:
    """P5 input only: a relative posterior result, never an absolute target."""

    dimension_id: str
    self_state_value_ppm: int
    desired_delta_ppm: int
    uncertainty_ppm: int
    confidence_ppm: int
    consistency_ppm: int
    posterior_digest: str

    def __post_init__(self) -> None:
        _validate_id(self.dimension_id, "dimension_id")
        _validate_ppm(self.self_state_value_ppm, "self_state_value_ppm", signed=True)
        _validate_ppm(self.desired_delta_ppm, "desired_delta_ppm", signed=True)
        _validate_ppm(self.uncertainty_ppm, "uncertainty_ppm")
        _validate_ppm(self.confidence_ppm, "confidence_ppm")
        _validate_ppm(self.consistency_ppm, "consistency_ppm")
        _validate_id(self.posterior_digest, "posterior_digest")


@dataclass(frozen=True)
class DesiredDeltaInput:
    self_state_version_id: str
    dimensions: tuple[DesiredDeltaDimensionInput, ...]

    def __post_init__(self) -> None:
        _validate_id(self.self_state_version_id, "self_state_version_id")
        if not self.dimensions:
            raise RoutingError("DesiredDelta input requires dimensions")
        ids = tuple(dimension.dimension_id for dimension in self.dimensions)
        if len(set(ids)) != len(ids):
            raise RoutingError("DesiredDelta input dimension_ids must be unique")


def local_morphological_neighborhood(
    self_state: SelfStateSnapshot,
    pair: QuestionPair,
    bank: QuestionBank,
    policy: RoutingPolicy,
) -> LmnResult:
    """Compute confidence-weighted standardized RMS and Gaussian compatibility."""

    state_by_dimension = self_state.by_dimension
    target = state_by_dimension.get(pair.dimension_id)
    if target is None or not target.supported:
        return LmnResult(False, None, (), 0, "TARGET_DIMENSION_UNSUPPORTED")
    if target.reliability_ppm == 0:
        return LmnResult(False, None, (), 0, "TARGET_DIMENSION_ZERO_RELIABILITY")
    weighted_squared_distance = Decimal(0)
    weight_total = 0
    shared: list[str] = []
    for dimension_id, anchor_value_ppm in pair.morphology_anchor_ppm.items():
        measurement = state_by_dimension.get(dimension_id)
        if measurement is None or not measurement.supported or measurement.reliability_ppm == 0:
            continue
        scale_ppm = bank.morphology_scale_ppm.get(dimension_id)
        if scale_ppm is None:
            return LmnResult(False, None, (), 0, "MORPHOLOGY_SCALE_MISSING")
        if type(scale_ppm) is not int or scale_ppm < bank.morphology_scale_floor_ppm:
            return LmnResult(False, None, (), 0, "MORPHOLOGY_SCALE_BELOW_FLOOR")
        shared.append(dimension_id)
        with localcontext(_routing_decimal_context()):
            standardized = Decimal(measurement.value_ppm - anchor_value_ppm) / Decimal(scale_ppm)
            weighted_squared_distance += (
                standardized * standardized * Decimal(measurement.reliability_ppm)
            )
        weight_total += measurement.reliability_ppm
    if weight_total == 0:
        return LmnResult(False, None, (), 0, "NO_SHARED_RELIABLE_MEASUREMENT")
    with localcontext(_routing_decimal_context()):
        rms = (weighted_squared_distance / Decimal(weight_total)).sqrt()
        standardized_rms_ppm = _quantize_nonnegative_decimal(rms * Decimal(PPM))
        compatibility_ppm = _quantize_fraction_ppm(
            (-(Decimal("0.5")) * rms * rms).exp() * Decimal(PPM)
        )
    shared_ids = tuple(sorted(shared))
    return LmnResult(True, standardized_rms_ppm, shared_ids, compatibility_ppm, "ELIGIBLE")


def decide_stop(
    *,
    total_questions_asked: int,
    progress: Sequence[DimensionProgress],
    policy: RoutingPolicy | None = None,
) -> StopDecision:
    resolved_policy = RoutingPolicy() if policy is None else policy
    if type(total_questions_asked) is not int or total_questions_asked < 0:
        raise RoutingError("total_questions_asked must be a non-negative true integer")
    if not progress:
        raise RoutingError("stopping requires explicit progress for every routed dimension")
    incomplete = tuple(
        sorted(
            item.dimension_id
            for item in progress
            if not _dimension_coverage_complete(item, resolved_policy)
        )
    )
    complete = not incomplete
    if total_questions_asked < resolved_policy.minimum_questions:
        return StopDecision(
            False,
            RouteStopReason.CONTINUE_MINIMUM_NOT_REACHED,
            complete,
            total_questions_asked,
            incomplete,
        )
    if complete:
        return StopDecision(
            True,
            RouteStopReason.COMPLETE_COVERAGE_MET,
            True,
            total_questions_asked,
            (),
        )
    if total_questions_asked >= resolved_policy.maximum_questions:
        return StopDecision(
            True,
            RouteStopReason.FAIL_CLOSED_COVERAGE_UNMET_AT_MAXIMUM,
            False,
            total_questions_asked,
            incomplete,
        )
    return StopDecision(
        False,
        RouteStopReason.CONTINUE_COVERAGE_UNMET,
        False,
        total_questions_asked,
        incomplete,
    )


def schedule_questions(
    *,
    bank: QuestionBank,
    self_state: SelfStateSnapshot,
    progress: Sequence[DimensionProgress],
    total_questions_asked: int,
    limit: int,
    policy: RoutingPolicy | None = None,
) -> RoutePlan:
    """Rank existing pairs only; this function cannot generate questionnaire media."""

    if type(limit) is not int or limit < 0:
        raise RoutingError("limit must be a non-negative true integer")
    resolved_policy = RoutingPolicy() if policy is None else policy
    stop = decide_stop(
        total_questions_asked=total_questions_asked,
        progress=progress,
        policy=resolved_policy,
    )
    if stop.should_stop or limit == 0:
        return RoutePlan((), ())
    progress_by_dimension = _progress_by_dimension(progress)
    scores = tuple(
        _score_pair(
            pair,
            self_state,
            bank,
            progress_by_dimension.get(pair.dimension_id),
            resolved_policy,
            total_questions_asked,
        )
        for pair in bank.pairs
    )
    eligible = [score for score in scores if score.eligible and score.score_ppm > 0]
    ordered = tuple(
        score.pair_id
        for score in sorted(
            eligible,
            key=lambda item: (-item.score_ppm, item.dimension_id, item.pair_id),
        )[:limit]
    )
    return RoutePlan(ordered, tuple(sorted(scores, key=lambda item: item.pair_id)))


def desired_delta_input(
    self_state: SelfStateSnapshot, progress: Sequence[DimensionProgress]
) -> DesiredDeltaInput:
    """Build only the typed P5 input; compilation and persistence remain out of scope."""

    state_by_dimension = self_state.by_dimension
    dimensions: list[DesiredDeltaDimensionInput] = []
    for item in sorted(progress, key=lambda value: value.dimension_id):
        measurement = state_by_dimension.get(item.dimension_id)
        if measurement is None or not measurement.supported or measurement.reliability_ppm == 0:
            continue
        dimensions.append(
            DesiredDeltaDimensionInput(
                dimension_id=item.dimension_id,
                self_state_value_ppm=measurement.value_ppm,
                desired_delta_ppm=item.posterior.posterior_mean_ppm,
                uncertainty_ppm=PPM - item.posterior.confidence_ppm,
                confidence_ppm=item.posterior.confidence_ppm,
                consistency_ppm=item.posterior.consistency_ppm,
                posterior_digest=item.posterior.digest,
            )
        )
    if not dimensions:
        raise RoutingError("no supported SelfState dimensions have posterior authority")
    return DesiredDeltaInput(self_state.self_state_version_id, tuple(dimensions))


def _score_pair(
    pair: QuestionPair,
    self_state: SelfStateSnapshot,
    bank: QuestionBank,
    progress: DimensionProgress | None,
    policy: RoutingPolicy,
    total_questions_asked: int,
) -> RoutingScore:
    if not pair.eligible:
        return _excluded_score(pair, "PAIR_UNSUPPORTED")
    state_measurement = self_state.by_dimension.get(pair.dimension_id)
    if state_measurement is None or not state_measurement.supported:
        return _excluded_score(pair, "TARGET_DIMENSION_UNSUPPORTED")
    if state_measurement.reliability_ppm == 0:
        return _excluded_score(pair, "TARGET_DIMENSION_ZERO_RELIABILITY")
    lmn = local_morphological_neighborhood(self_state, pair, bank, policy)
    if not lmn.eligible:
        return _excluded_score(pair, lmn.reason, lmn)
    posterior_uncertainty = PPM if progress is None else PPM - progress.posterior.confidence_ppm
    contradiction_priority = (
        PPM
        if progress is None
        else PPM
        - _round_half_even_division(
            progress.posterior.consistency_ppm * (PPM - CONTRADICTION_PRIORITY_FLOOR_PPM),
            PPM,
        )
    )
    coverage_need = (
        PPM if progress is None else _coverage_need_ppm(progress, policy, total_questions_asked)
    )
    score_ppm = _multiply_ppm_factors(
        (
            posterior_uncertainty,
            state_measurement.reliability_ppm,
            coverage_need,
            pair.expected_fisher_information_ppm,
            lmn.factor_ppm,
            pair.pair_quality_ppm,
            contradiction_priority,
        )
    )
    return RoutingScore(
        pair.pair_id,
        pair.dimension_id,
        score_ppm,
        posterior_uncertainty,
        state_measurement.reliability_ppm,
        coverage_need,
        pair.expected_fisher_information_ppm,
        lmn.factor_ppm,
        pair.pair_quality_ppm,
        contradiction_priority,
        lmn.standardized_rms_ppm,
        True,
        None,
    )


def _excluded_score(pair: QuestionPair, reason: str, lmn: LmnResult | None = None) -> RoutingScore:
    return RoutingScore(
        pair.pair_id,
        pair.dimension_id,
        0,
        0,
        0,
        0,
        0,
        0 if lmn is None else lmn.factor_ppm,
        0,
        0,
        None if lmn is None else lmn.standardized_rms_ppm,
        False,
        reason,
    )


def _coverage_need_ppm(
    progress: DimensionProgress, policy: RoutingPolicy, total_questions_asked: int
) -> int:
    missing = 0
    required = (
        policy.minimum_valid_answers_per_dimension
        + policy.minimum_magnitudes_per_dimension
        + policy.minimum_source_identities_per_dimension
    )
    missing += max(0, policy.minimum_valid_answers_per_dimension - progress.valid_answers)
    missing += max(
        0,
        policy.minimum_magnitudes_per_dimension - len(set(progress.magnitude_ppm_seen)),
    )
    missing += max(
        0,
        policy.minimum_source_identities_per_dimension
        - len(set(progress.source_identity_ids_seen)),
    )
    dimension_gap = _round_half_even_division(missing * PPM, required)
    global_minimum_gap = _round_half_even_division(
        max(0, policy.minimum_questions - total_questions_asked) * PPM,
        policy.minimum_questions,
    )
    return max(dimension_gap, global_minimum_gap)


def _dimension_coverage_complete(progress: DimensionProgress, policy: RoutingPolicy) -> bool:
    return (
        progress.valid_answers >= policy.minimum_valid_answers_per_dimension
        and len(set(progress.magnitude_ppm_seen)) >= policy.minimum_magnitudes_per_dimension
        and len(set(progress.source_identity_ids_seen))
        >= policy.minimum_source_identities_per_dimension
    )


def _progress_by_dimension(
    progress: Sequence[DimensionProgress],
) -> Mapping[str, DimensionProgress]:
    by_dimension = {item.dimension_id: item for item in progress}
    if len(by_dimension) != len(progress):
        raise RoutingError("progress dimension_ids must be unique")
    return by_dimension


def _round_half_even_division(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise RoutingError("fixed-point denominator must be positive")
    quotient, remainder = divmod(numerator, denominator)
    doubled_remainder = remainder * 2
    if doubled_remainder > denominator or (doubled_remainder == denominator and quotient % 2 == 1):
        return quotient + 1
    return quotient


def _routing_decimal_context() -> Context:
    return Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=-999_999, Emax=999_999)


def _quantize_nonnegative_decimal(value: Decimal) -> int:
    if not value.is_finite() or value < 0:
        raise RoutingError("fixed-point Decimal result is invalid")
    with localcontext(_routing_decimal_context()):
        return int(value.to_integral_value(rounding=ROUND_HALF_EVEN))


def _quantize_fraction_ppm(value: Decimal) -> int:
    result = _quantize_nonnegative_decimal(value)
    if result > PPM:
        raise RoutingError("fixed-point Decimal fraction exceeds ppm")
    return result


def _multiply_ppm_factors(factors: tuple[int, ...]) -> int:
    if not factors:
        raise RoutingError("routing score requires factors")
    for factor in factors:
        _validate_ppm(factor, "routing score factor")
    product = 1
    for factor in factors:
        product *= factor
    return _round_half_even_division(product, PPM ** (len(factors) - 1))


def _validate_id(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise RoutingError(f"{field_name} must contain between 1 and 128 characters")


def _validate_ppm(value: int, field_name: str, *, signed: bool = False) -> None:
    if type(value) is not int:
        raise RoutingError(f"{field_name} must be a true integer")
    minimum = -PPM if signed else 0
    if not minimum <= value <= PPM:
        raise RoutingError(f"{field_name} is outside the ppm authority range")
