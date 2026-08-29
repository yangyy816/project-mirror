"""Pure D03 face-runtime domain compiler for typed observation evidence.

This module is deliberately not the live M3 adapter.  Frozen M3 capability and
contracts are sufficient for this implementation; fresh runtime replay remains
deferred until a runtime-dependent integration or acceptance Gate needs it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Final, Literal

PPM_SCALE: Final = 1_000_000
RUNTIME_READINESS: Final = "IMPLEMENTATION_READY"
INTEGRATION_STATUS: Final = "RUNTIME_INTEGRATION_DEFERRED_PENDING_EVIDENCE"
FACE_RUNTIME_SCHEMA: Final = "mirror.demo/D03FaceRuntime/v1"
MEASUREMENT_CONFIDENCE_KIND: Final = "DEMO_P3_M3_OBSERVATION_CONFIDENCE_V1"
REPEAT_RELIABILITY_KIND: Final = "DEMO_P3_THREE_REPEAT_RANGE_RELIABILITY_V1"

_DIMENSION = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_REFERENCE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_REASON = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,63}$")

SupportState = Literal["SUPPORTED", "UNSUPPORTED"]
RoutingEligibility = Literal[
    "ROUTING_ELIGIBLE",
    "UNSUPPORTED",
    "INSUFFICIENT_RELIABILITY",
]


class FaceRuntimeError(ValueError):
    """Raised when a D03 fixture violates the immutable domain contract."""


def _require_ppm(value: object, field_name: str) -> int:
    if type(value) is not int or not 0 <= value <= PPM_SCALE:
        raise FaceRuntimeError(f"{field_name} must be an integer in [0, {PPM_SCALE}]")
    return value


def _mean_ppm(values: Sequence[int]) -> int:
    with localcontext() as context:
        context.prec = 30
        context.rounding = ROUND_HALF_EVEN
        return int((sum(values) / Decimal(len(values))).to_integral_value())


def _product_ppm(left: int, right: int) -> int:
    with localcontext() as context:
        context.prec = 30
        context.rounding = ROUND_HALF_EVEN
        return int((Decimal(left) * Decimal(right) / PPM_SCALE).to_integral_value())


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(FACE_RUNTIME_SCHEMA.encode("utf-8") + b"\n" + encoded).hexdigest()


@dataclass(frozen=True)
class DimensionObservation:
    """One quantized continuous measurement from a synthetic deterministic fixture."""

    dimension: str
    support_state: SupportState
    value_ppm: int | None
    measurement_confidence_ppm: int
    unsupported_reason: str | None = None

    def __post_init__(self) -> None:
        if _DIMENSION.fullmatch(self.dimension) is None:
            raise FaceRuntimeError("dimension must use the allowlisted opaque syntax")
        _require_ppm(self.measurement_confidence_ppm, "measurement_confidence_ppm")
        if self.support_state == "SUPPORTED":
            if self.value_ppm is None:
                raise FaceRuntimeError("supported dimension must have a quantized value")
            _require_ppm(self.value_ppm, "value_ppm")
            if self.unsupported_reason is not None:
                raise FaceRuntimeError("supported dimension must not have an unsupported reason")
        elif self.support_state == "UNSUPPORTED":
            if self.value_ppm is not None:
                raise FaceRuntimeError("unsupported dimension must not carry a value")
            if _REASON.fullmatch(self.unsupported_reason or "") is None:
                raise FaceRuntimeError("unsupported dimension requires an opaque reason")
        else:
            raise FaceRuntimeError("unknown support state")


@dataclass(frozen=True)
class FaceObservation:
    """One independently recorded repeat projected from runtime evidence."""

    evidence_reference: str
    repeat_index: int
    dimensions: tuple[DimensionObservation, ...]

    def __post_init__(self) -> None:
        if _REFERENCE.fullmatch(self.evidence_reference) is None:
            raise FaceRuntimeError("evidence reference must use the opaque first-party syntax")
        if type(self.repeat_index) is not int or self.repeat_index not in {1, 2, 3}:
            raise FaceRuntimeError("repeat index must be 1, 2, or 3")
        if not self.dimensions:
            raise FaceRuntimeError("observation must contain at least one dimension")
        dimensions = [entry.dimension for entry in self.dimensions]
        if len(dimensions) != len(set(dimensions)):
            raise FaceRuntimeError("observation dimensions must be unique")

    @property
    def canonical_digest(self) -> str:
        return _canonical_digest(
            {
                "evidence_reference": self.evidence_reference,
                "repeat_index": self.repeat_index,
                "dimensions": [
                    {
                        "dimension": entry.dimension,
                        "support_state": entry.support_state,
                        "value_ppm": entry.value_ppm,
                        "measurement_confidence_ppm": entry.measurement_confidence_ppm,
                        "unsupported_reason": entry.unsupported_reason,
                    }
                    for entry in sorted(self.dimensions, key=lambda entry: entry.dimension)
                ],
            }
        )


@dataclass(frozen=True)
class BaselineDimension:
    dimension: str
    support_state: SupportState
    value_ppm: int | None
    reliability_ppm: int
    uncertainty_ppm: int
    unsupported_reason: str | None
    measurement_confidence_ppm: int
    repeat_reliability_ppm: int
    measurement_confidence_kind: str = MEASUREMENT_CONFIDENCE_KIND
    repeat_reliability_kind: str = REPEAT_RELIABILITY_KIND

    def __post_init__(self) -> None:
        if _DIMENSION.fullmatch(self.dimension) is None:
            raise FaceRuntimeError("baseline dimension is invalid")
        _require_ppm(self.reliability_ppm, "reliability_ppm")
        _require_ppm(self.uncertainty_ppm, "uncertainty_ppm")
        _require_ppm(self.measurement_confidence_ppm, "measurement_confidence_ppm")
        _require_ppm(self.repeat_reliability_ppm, "repeat_reliability_ppm")
        if self.measurement_confidence_kind != MEASUREMENT_CONFIDENCE_KIND:
            raise FaceRuntimeError("measurement confidence kind is not accepted")
        if self.repeat_reliability_kind != REPEAT_RELIABILITY_KIND:
            raise FaceRuntimeError("repeat reliability kind is not accepted")
        if self.reliability_ppm + self.uncertainty_ppm != PPM_SCALE:
            raise FaceRuntimeError("reliability and uncertainty must complement exactly")
        if self.reliability_ppm != _product_ppm(
            self.measurement_confidence_ppm, self.repeat_reliability_ppm
        ):
            raise FaceRuntimeError("self-state reliability must replay the accepted composite")
        if self.support_state == "SUPPORTED":
            _require_ppm(self.value_ppm, "value_ppm")
            if self.unsupported_reason is not None:
                raise FaceRuntimeError(
                    "supported baseline dimension must not have an unsupported reason"
                )
        elif self.support_state == "UNSUPPORTED":
            if (
                self.value_ppm is not None
                or self.reliability_ppm != 0
                or self.measurement_confidence_ppm != 0
                or self.repeat_reliability_ppm != 0
            ):
                raise FaceRuntimeError("unsupported baseline dimension must fail closed")
            if _REASON.fullmatch(self.unsupported_reason or "") is None:
                raise FaceRuntimeError("unsupported baseline dimension requires an opaque reason")
        else:
            raise FaceRuntimeError("unknown baseline support state")


@dataclass(frozen=True)
class BaselineFaceModel:
    """Versioned measurement evidence, separate from the derived SelfState."""

    aggregation_version: str
    ordered_repeat_digests: tuple[str, str, str]
    dimensions: tuple[BaselineDimension, ...]
    runtime_readiness: Literal["IMPLEMENTATION_READY"] = RUNTIME_READINESS
    integration_status: Literal["RUNTIME_INTEGRATION_DEFERRED_PENDING_EVIDENCE"] = (
        INTEGRATION_STATUS
    )

    def __post_init__(self) -> None:
        if _REFERENCE.fullmatch(self.aggregation_version) is None:
            raise FaceRuntimeError("aggregation version must use the opaque first-party syntax")
        if len(set(self.ordered_repeat_digests)) != 3 or any(
            re.fullmatch(r"[0-9a-f]{64}", digest) is None for digest in self.ordered_repeat_digests
        ):
            raise FaceRuntimeError("baseline requires three distinct canonical repeat digests")
        dimensions = [entry.dimension for entry in self.dimensions]
        if not dimensions or len(dimensions) != len(set(dimensions)):
            raise FaceRuntimeError("baseline dimensions must be non-empty and unique")

    @property
    def canonical_digest(self) -> str:
        return _canonical_digest(
            {
                "aggregation_version": self.aggregation_version,
                "ordered_repeat_digests": list(self.ordered_repeat_digests),
                "dimensions": [
                    {
                        "dimension": entry.dimension,
                        "support_state": entry.support_state,
                        "value_ppm": entry.value_ppm,
                        "reliability_ppm": entry.reliability_ppm,
                        "uncertainty_ppm": entry.uncertainty_ppm,
                        "unsupported_reason": entry.unsupported_reason,
                        "measurement_confidence_ppm": entry.measurement_confidence_ppm,
                        "repeat_reliability_ppm": entry.repeat_reliability_ppm,
                        "measurement_confidence_kind": entry.measurement_confidence_kind,
                        "repeat_reliability_kind": entry.repeat_reliability_kind,
                    }
                    for entry in sorted(self.dimensions, key=lambda entry: entry.dimension)
                ],
            }
        )


@dataclass(frozen=True)
class SelfStateDimension:
    dimension: str
    value_ppm: int | None
    reliability_ppm: int
    uncertainty_ppm: int
    routing_eligibility: RoutingEligibility


@dataclass(frozen=True)
class SelfState:
    """Derived current state suitable only for explicitly eligible routing dimensions."""

    baseline_digest: str
    derivation_version: str
    dimensions: tuple[SelfStateDimension, ...]
    runtime_readiness: Literal["IMPLEMENTATION_READY"] = RUNTIME_READINESS
    integration_status: Literal["RUNTIME_INTEGRATION_DEFERRED_PENDING_EVIDENCE"] = (
        INTEGRATION_STATUS
    )

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", self.baseline_digest) is None:
            raise FaceRuntimeError("self state must bind a baseline digest")
        if _REFERENCE.fullmatch(self.derivation_version) is None:
            raise FaceRuntimeError("derivation version must use the opaque first-party syntax")
        if not self.dimensions:
            raise FaceRuntimeError("self state must contain at least one dimension")
        names = [entry.dimension for entry in self.dimensions]
        if len(names) != len(set(names)):
            raise FaceRuntimeError("self state dimensions must be unique")
        for entry in self.dimensions:
            _require_ppm(entry.reliability_ppm, "reliability_ppm")
            _require_ppm(entry.uncertainty_ppm, "uncertainty_ppm")
            if entry.reliability_ppm + entry.uncertainty_ppm != PPM_SCALE:
                raise FaceRuntimeError(
                    "self state reliability and uncertainty must complement exactly"
                )
            if entry.routing_eligibility == "ROUTING_ELIGIBLE":
                _require_ppm(entry.value_ppm, "value_ppm")
                if entry.reliability_ppm == 0:
                    raise FaceRuntimeError("zero reliability must not be routing eligible")
            elif entry.routing_eligibility == "UNSUPPORTED":
                if entry.value_ppm is not None or entry.reliability_ppm != 0:
                    raise FaceRuntimeError("unsupported self state must fail closed")
            elif entry.routing_eligibility == "INSUFFICIENT_RELIABILITY":
                _require_ppm(entry.value_ppm, "value_ppm")
                if entry.reliability_ppm != 0:
                    raise FaceRuntimeError(
                        "insufficient-reliability state must have zero reliability"
                    )
            else:
                raise FaceRuntimeError("unknown routing eligibility")

    @property
    def canonical_digest(self) -> str:
        return _canonical_digest(
            {
                "baseline_digest": self.baseline_digest,
                "derivation_version": self.derivation_version,
                "dimensions": [
                    {
                        "dimension": entry.dimension,
                        "value_ppm": entry.value_ppm,
                        "reliability_ppm": entry.reliability_ppm,
                        "uncertainty_ppm": entry.uncertainty_ppm,
                        "routing_eligibility": entry.routing_eligibility,
                    }
                    for entry in sorted(self.dimensions, key=lambda entry: entry.dimension)
                ],
            }
        )


@dataclass(frozen=True)
class FaceRuntimeCompilation:
    baseline: BaselineFaceModel
    self_state: SelfState


def compile_baseline_face_model(
    repeats: Sequence[FaceObservation], *, aggregation_version: str = "d03-face-runtime-v1"
) -> BaselineFaceModel:
    """Compile exactly three independently recorded repeats into baseline evidence."""

    if len(repeats) != 3:
        raise FaceRuntimeError("exactly three independent observations are required")
    ordered = tuple(sorted(repeats, key=lambda observation: observation.repeat_index))
    if tuple(observation.repeat_index for observation in ordered) != (1, 2, 3):
        raise FaceRuntimeError("repeat indices must contain each of 1, 2, and 3 exactly once")
    if len({observation.evidence_reference for observation in ordered}) != 3:
        raise FaceRuntimeError("repeat observations must use distinct evidence references")

    by_dimension = {
        name: tuple(
            next((entry for entry in observation.dimensions if entry.dimension == name), None)
            for observation in ordered
        )
        for name in sorted(
            {entry.dimension for observation in ordered for entry in observation.dimensions}
        )
    }
    dimensions = tuple(
        _compile_dimension(dimension, entries) for dimension, entries in by_dimension.items()
    )
    return BaselineFaceModel(
        aggregation_version=aggregation_version,
        ordered_repeat_digests=(
            ordered[0].canonical_digest,
            ordered[1].canonical_digest,
            ordered[2].canonical_digest,
        ),
        dimensions=dimensions,
    )


def derive_self_state(
    baseline: BaselineFaceModel, *, derivation_version: str = "d03-self-state-v1"
) -> SelfState:
    """Project baseline evidence without inventing values for unsupported observations."""

    dimensions: list[SelfStateDimension] = []
    for entry in baseline.dimensions:
        if entry.support_state == "UNSUPPORTED":
            eligibility: RoutingEligibility = "UNSUPPORTED"
        elif entry.reliability_ppm == 0:
            eligibility = "INSUFFICIENT_RELIABILITY"
        else:
            eligibility = "ROUTING_ELIGIBLE"
        dimensions.append(
            SelfStateDimension(
                dimension=entry.dimension,
                value_ppm=entry.value_ppm,
                reliability_ppm=entry.reliability_ppm,
                uncertainty_ppm=entry.uncertainty_ppm,
                routing_eligibility=eligibility,
            )
        )
    return SelfState(
        baseline_digest=baseline.canonical_digest,
        derivation_version=derivation_version,
        dimensions=tuple(dimensions),
    )


def compile_face_runtime(repeats: Sequence[FaceObservation]) -> FaceRuntimeCompilation:
    """Compile the D03 pure-domain result without requiring a live M3 handle."""

    baseline = compile_baseline_face_model(repeats)
    return FaceRuntimeCompilation(baseline=baseline, self_state=derive_self_state(baseline))


def _compile_dimension(
    dimension: str, entries: tuple[DimensionObservation | None, ...]
) -> BaselineDimension:
    if len(entries) != 3 or any(entry is None for entry in entries):
        return _unsupported_baseline_dimension(dimension, "MISSING_MEASUREMENT")
    present = tuple(entry for entry in entries if entry is not None)
    unsupported = next((entry for entry in present if entry.support_state == "UNSUPPORTED"), None)
    if unsupported is not None:
        assert unsupported.unsupported_reason is not None
        return _unsupported_baseline_dimension(dimension, unsupported.unsupported_reason)
    values = tuple(entry.value_ppm for entry in present)
    assert all(value is not None for value in values)
    supported_values = tuple(value for value in values if value is not None)
    mean_value = _mean_ppm(supported_values)
    agreement_ppm = PPM_SCALE - (max(supported_values) - min(supported_values))
    measurement_confidence_ppm = min(entry.measurement_confidence_ppm for entry in present)
    repeat_reliability_ppm = agreement_ppm
    reliability_ppm = _product_ppm(measurement_confidence_ppm, repeat_reliability_ppm)
    return BaselineDimension(
        dimension=dimension,
        support_state="SUPPORTED",
        value_ppm=mean_value,
        reliability_ppm=reliability_ppm,
        uncertainty_ppm=PPM_SCALE - reliability_ppm,
        unsupported_reason=None,
        measurement_confidence_ppm=measurement_confidence_ppm,
        repeat_reliability_ppm=repeat_reliability_ppm,
    )


def _unsupported_baseline_dimension(dimension: str, reason: str) -> BaselineDimension:
    return BaselineDimension(
        dimension=dimension,
        support_state="UNSUPPORTED",
        value_ppm=None,
        reliability_ppm=0,
        uncertainty_ppm=PPM_SCALE,
        unsupported_reason=reason,
        measurement_confidence_ppm=0,
        repeat_reliability_ppm=0,
    )
