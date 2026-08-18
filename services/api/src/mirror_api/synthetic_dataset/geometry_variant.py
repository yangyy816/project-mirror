"""Pure domain contracts for source-relative deterministic geometry research.

The module deliberately has no ORM, image library, storage, task-runner, or provider imports.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from .domain import (
    DomainValidationError,
    GeometryDimension,
    GeometryDimensionClassification,
    GeometryOntology,
    ReasonCode,
)

VARIANT_SPECIFICATION_SCHEMA_VERSION = "mirror.synthetic-dataset/VariantSpecification/v1"
MAX_RELATIVE_MAGNITUDE_PPM = 1_000_000
MAX_VARIANT_EDGE_PIXELS = 16_384
MAX_VARIANT_TOTAL_PIXELS = 64_000_000

_REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_VERSION_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*\Z")
_DIMENSION_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class TransformDirection(StrEnum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"


class DeterminismLevel(StrEnum):
    BIT_EXACT_CROSS_PLATFORM = "BIT_EXACT_CROSS_PLATFORM"
    BIT_EXACT_SAME_PLATFORM = "BIT_EXACT_SAME_PLATFORM"
    MEASUREMENT_EQUIVALENT = "MEASUREMENT_EQUIVALENT"


class TransformRunState(StrEnum):
    SPECIFIED = "SPECIFIED"
    RUNNING = "RUNNING"
    OUTPUT_STORED = "OUTPUT_STORED"
    MEASURING = "MEASURING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_TRANSFORM_RUN_TRANSITIONS: Mapping[TransformRunState, frozenset[TransformRunState]] = {
    TransformRunState.SPECIFIED: frozenset(
        {TransformRunState.RUNNING, TransformRunState.CANCELLED}
    ),
    TransformRunState.RUNNING: frozenset(
        {
            TransformRunState.OUTPUT_STORED,
            TransformRunState.REJECTED,
            TransformRunState.FAILED,
            TransformRunState.CANCELLED,
        }
    ),
    TransformRunState.OUTPUT_STORED: frozenset(
        {
            TransformRunState.MEASURING,
            TransformRunState.REJECTED,
            TransformRunState.FAILED,
        }
    ),
    TransformRunState.MEASURING: frozenset(
        {
            TransformRunState.COMPLETED,
            TransformRunState.REJECTED,
            TransformRunState.FAILED,
        }
    ),
    TransformRunState.COMPLETED: frozenset(),
    TransformRunState.REJECTED: frozenset(),
    TransformRunState.FAILED: frozenset(),
    TransformRunState.CANCELLED: frozenset(),
}


def transition_transform_run(
    current: TransformRunState, target: TransformRunState
) -> TransformRunState:
    """Apply only the monotonic run transitions accepted by ADR-036."""
    if not isinstance(current, TransformRunState) or not isinstance(target, TransformRunState):
        raise DomainValidationError(ReasonCode.INVALID_STATE_TRANSITION)
    if target not in _TRANSFORM_RUN_TRANSITIONS[current]:
        raise DomainValidationError(ReasonCode.INVALID_STATE_TRANSITION)
    return target


def require_researchable_dimension(
    ontology: GeometryOntology, dimension_key: str
) -> GeometryDimension:
    """Allow M4 research only for READY or EXPERIMENTAL ontology entries."""
    dimension = ontology.dimension_for(dimension_key)
    if dimension.classification in {
        GeometryDimensionClassification.READY,
        GeometryDimensionClassification.EXPERIMENTAL,
    }:
        return dimension
    if dimension.classification is GeometryDimensionClassification.UNSUPPORTED:
        raise DomainValidationError(ReasonCode.UNSUPPORTED_DIMENSION)
    if dimension.classification is GeometryDimensionClassification.REQUIRES_3D:
        raise DomainValidationError(ReasonCode.REQUIRES_3D_RESEARCH)
    if dimension.classification is GeometryDimensionClassification.STYLE_ONLY:
        raise DomainValidationError(ReasonCode.STYLE_ONLY_DIMENSION)
    raise DomainValidationError(ReasonCode.UNKNOWN_GEOMETRY_DIMENSION)


@dataclass(frozen=True)
class VariantSpecification:
    """Canonical, source-relative requested intent; never an absolute target face."""

    source_asset_reference: str
    source_identity_reference: str
    source_qa_run_reference: str
    ontology_version: str
    ontology_digest: str
    target_dimension: str
    direction: TransformDirection
    relative_magnitude_ppm: int
    control_dimensions: tuple[str, ...]
    algorithm_version: str
    runtime_manifest_digest: str
    tolerance_policy_reference: str
    output_width: int
    output_height: int
    output_policy_version: str
    determinism_level: DeterminismLevel
    content_digest: str

    def __post_init__(self) -> None:
        for reference in (
            self.source_asset_reference,
            self.source_identity_reference,
            self.source_qa_run_reference,
            self.tolerance_policy_reference,
        ):
            _require_reference(reference)
        for version in (
            self.ontology_version,
            self.algorithm_version,
            self.output_policy_version,
        ):
            _require_version(version)
        _require_sha256(self.ontology_digest)
        _require_sha256(self.runtime_manifest_digest)
        _require_dimension_key(self.target_dimension)
        if not isinstance(self.direction, TransformDirection):
            raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)
        if not isinstance(self.determinism_level, DeterminismLevel):
            raise DomainValidationError(ReasonCode.INVALID_DETERMINISM_CLAIM)
        if (
            isinstance(self.relative_magnitude_ppm, bool)
            or not isinstance(self.relative_magnitude_ppm, int)
            or not 1 <= self.relative_magnitude_ppm <= MAX_RELATIVE_MAGNITUDE_PPM
        ):
            raise DomainValidationError(ReasonCode.INVALID_RELATIVE_MAGNITUDE)
        _validate_control_dimensions(self.target_dimension, self.control_dimensions)
        _validate_output_bounds(self.output_width, self.output_height)
        _require_sha256(self.content_digest)
        if self.content_digest != _specification_digest(self._canonical_facts()):
            raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)

    @classmethod
    def create(
        cls,
        *,
        ontology: GeometryOntology,
        source_asset_reference: str,
        source_identity_reference: str,
        source_qa_run_reference: str,
        target_dimension: str,
        direction: TransformDirection,
        relative_magnitude_ppm: int,
        control_dimensions: tuple[str, ...],
        algorithm_version: str,
        runtime_manifest_digest: str,
        tolerance_policy_reference: str,
        output_width: int,
        output_height: int,
        output_policy_version: str,
        determinism_level: DeterminismLevel,
    ) -> VariantSpecification:
        require_researchable_dimension(ontology, target_dimension)
        if not isinstance(direction, TransformDirection):
            raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)
        if not isinstance(determinism_level, DeterminismLevel):
            raise DomainValidationError(ReasonCode.INVALID_DETERMINISM_CLAIM)
        canonical_controls = tuple(sorted(control_dimensions))
        _validate_control_dimensions(target_dimension, canonical_controls)
        for control_dimension in canonical_controls:
            require_researchable_dimension(ontology, control_dimension)
        facts: dict[str, object] = {
            "algorithm_version": algorithm_version,
            "control_dimensions": list(canonical_controls),
            "determinism_level": determinism_level.value,
            "direction": direction.value,
            "ontology_digest": ontology.authority.content_digest,
            "ontology_version": ontology.authority.version,
            "output_height": output_height,
            "output_policy_version": output_policy_version,
            "output_width": output_width,
            "relative_magnitude_ppm": relative_magnitude_ppm,
            "runtime_manifest_digest": runtime_manifest_digest,
            "source_asset_reference": source_asset_reference,
            "source_identity_reference": source_identity_reference,
            "source_qa_run_reference": source_qa_run_reference,
            "target_dimension": target_dimension,
            "tolerance_policy_reference": tolerance_policy_reference,
        }
        return cls(
            source_asset_reference=source_asset_reference,
            source_identity_reference=source_identity_reference,
            source_qa_run_reference=source_qa_run_reference,
            ontology_version=ontology.authority.version,
            ontology_digest=ontology.authority.content_digest,
            target_dimension=target_dimension,
            direction=direction,
            relative_magnitude_ppm=relative_magnitude_ppm,
            control_dimensions=canonical_controls,
            algorithm_version=algorithm_version,
            runtime_manifest_digest=runtime_manifest_digest,
            tolerance_policy_reference=tolerance_policy_reference,
            output_width=output_width,
            output_height=output_height,
            output_policy_version=output_policy_version,
            determinism_level=determinism_level,
            content_digest=_specification_digest(facts),
        )

    def _canonical_facts(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "control_dimensions": list(self.control_dimensions),
            "determinism_level": self.determinism_level.value,
            "direction": self.direction.value,
            "ontology_digest": self.ontology_digest,
            "ontology_version": self.ontology_version,
            "output_height": self.output_height,
            "output_policy_version": self.output_policy_version,
            "output_width": self.output_width,
            "relative_magnitude_ppm": self.relative_magnitude_ppm,
            "runtime_manifest_digest": self.runtime_manifest_digest,
            "source_asset_reference": self.source_asset_reference,
            "source_identity_reference": self.source_identity_reference,
            "source_qa_run_reference": self.source_qa_run_reference,
            "target_dimension": self.target_dimension,
            "tolerance_policy_reference": self.tolerance_policy_reference,
        }


def _validate_control_dimensions(target_dimension: str, controls: tuple[str, ...]) -> None:
    if not controls:
        raise DomainValidationError(ReasonCode.CONTROL_DIMENSION_REQUIRED)
    if controls != tuple(sorted(set(controls))):
        raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)
    for control in controls:
        _require_dimension_key(control)
    if target_dimension in controls:
        raise DomainValidationError(ReasonCode.TARGET_CONTROL_CONFLICT)


def _validate_output_bounds(width: int, height: int) -> None:
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
        or width > MAX_VARIANT_EDGE_PIXELS
        or height > MAX_VARIANT_EDGE_PIXELS
        or width * height > MAX_VARIANT_TOTAL_PIXELS
    ):
        raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)


def _require_reference(value: str) -> None:
    if not isinstance(value, str) or _REFERENCE_PATTERN.fullmatch(value) is None:
        raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)


def _require_version(value: str) -> None:
    if not isinstance(value, str) or _VERSION_PATTERN.fullmatch(value) is None:
        raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)


def _require_dimension_key(value: str) -> None:
    if not isinstance(value, str) or _DIMENSION_KEY_PATTERN.fullmatch(value) is None:
        raise DomainValidationError(ReasonCode.UNKNOWN_GEOMETRY_DIMENSION)


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)


def _specification_digest(facts: Mapping[str, object]) -> str:
    canonical = json.dumps(
        facts,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    envelope = f"{VARIANT_SPECIFICATION_SCHEMA_VERSION}\n{canonical}".encode()
    return hashlib.sha256(envelope).hexdigest()
