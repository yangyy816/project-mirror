"""Deterministic, provider-neutral contracts for the P2 synthetic dataset authority.

The contracts deliberately encode only the policy, lifecycle, QA, and ontology decisions
accepted in ADR-021 through ADR-023.  They do not perform generation, image processing,
provider calls, or persistence.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import cast

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_VERSION_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*\Z")
_DIMENSION_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
_FORBIDDEN_ONTOLOGY_KEY_TOKENS = frozenset(
    {
        "age",
        "adult",
        "attractiveness",
        "beauty",
        "ethnicity",
        "health",
        "ideal",
        "minor",
        "nationality",
        "percentile",
        "political",
        "population",
        "race",
        "rank",
        "ranking",
        "religion",
        "score",
        "sexual",
    }
)


class ReasonCode(StrEnum):
    """Stable, safe reason codes for policy validation and future QA evidence."""

    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    INVALID_VERSION = "INVALID_VERSION"
    INVALID_POLICY_CONTENT = "INVALID_POLICY_CONTENT"
    CONTENT_DIGEST_MISMATCH = "CONTENT_DIGEST_MISMATCH"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    SYNTHETIC_ORIGIN_REQUIRED = "SYNTHETIC_ORIGIN_REQUIRED"
    LICENSE_EVIDENCE_REQUIRED = "LICENSE_EVIDENCE_REQUIRED"
    ADULT_SYNTHETIC_REJECTED = "ADULT_SYNTHETIC_REJECTED"
    DECODE_SAFETY_GATE_FAILED = "DECODE_SAFETY_GATE_FAILED"
    PROVENANCE_EVIDENCE_REQUIRED = "PROVENANCE_EVIDENCE_REQUIRED"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    RELEASE_CONSISTENCY_FAILED = "RELEASE_CONSISTENCY_FAILED"
    UNRESOLVED_VARIABLE_ISOLATION = "UNRESOLVED_VARIABLE_ISOLATION"
    UNKNOWN_GEOMETRY_DIMENSION = "UNKNOWN_GEOMETRY_DIMENSION"
    FURTHER_RESEARCH = "FURTHER_RESEARCH"
    UNSUPPORTED_DIMENSION = "UNSUPPORTED_DIMENSION"
    REQUIRES_3D_RESEARCH = "REQUIRES_3D_RESEARCH"
    STYLE_ONLY_DIMENSION = "STYLE_ONLY_DIMENSION"
    PROHIBITED_ONTOLOGY_CONCEPT = "PROHIBITED_ONTOLOGY_CONCEPT"
    INVALID_VARIANT_SPECIFICATION = "INVALID_VARIANT_SPECIFICATION"
    INVALID_RELATIVE_MAGNITUDE = "INVALID_RELATIVE_MAGNITUDE"
    CONTROL_DIMENSION_REQUIRED = "CONTROL_DIMENSION_REQUIRED"
    TARGET_CONTROL_CONFLICT = "TARGET_CONTROL_CONFLICT"
    INVALID_DETERMINISM_CLAIM = "INVALID_DETERMINISM_CLAIM"
    INVALID_WARP_PLAN = "INVALID_WARP_PLAN"
    INSUFFICIENT_LANDMARK_CONFIDENCE = "INSUFFICIENT_LANDMARK_CONFIDENCE"
    OUT_OF_BOUNDS_DISPLACEMENT = "OUT_OF_BOUNDS_DISPLACEMENT"
    FOLDOVER_REJECTED = "FOLDOVER_REJECTED"
    TRANSFORM_RUNTIME_MISMATCH = "TRANSFORM_RUNTIME_MISMATCH"
    TRANSFORM_OUTPUT_INVALID = "TRANSFORM_OUTPUT_INVALID"
    SOURCE_RESULT_IDENTICAL = "SOURCE_RESULT_IDENTICAL"


class DomainValidationError(ValueError):
    """A safe validation failure which intentionally contains no submitted content."""

    def __init__(self, reason_code: ReasonCode) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code.value)


class PolicyKind(StrEnum):
    """The four P2-M1 authority concepts accepted by ADR-021."""

    SYNTHETIC_GENERATION_POLICY = "SyntheticGenerationPolicy"
    SYNTHETIC_PROMPT_TEMPLATE = "SyntheticPromptTemplate"
    SYNTHETIC_QA_POLICY = "SyntheticQAPolicy"
    GEOMETRY_ONTOLOGY_VERSION = "GeometryOntologyVersion"

    @property
    def schema_version(self) -> str:
        return f"mirror.synthetic-dataset/{self.value}/v1"


@dataclass(frozen=True)
class CanonicalPolicy:
    """Versioned policy/template/ontology content with a canonical SHA-256 digest."""

    kind: PolicyKind
    version: str
    canonical_content: str
    content_digest: str

    def __post_init__(self) -> None:
        """Reject direct construction that bypasses the canonical authority contract."""
        if not isinstance(self.kind, PolicyKind):
            raise DomainValidationError(ReasonCode.UNSUPPORTED_SCHEMA)
        _validate_version(self.version)
        canonical_content = _validate_canonical_content(self.canonical_content)
        if not isinstance(self.content_digest, str) or not _is_lowercase_sha256(
            self.content_digest
        ):
            raise DomainValidationError(ReasonCode.CONTENT_DIGEST_MISMATCH)
        expected_digest = _digest(self.kind.schema_version, self.version, canonical_content)
        if self.content_digest != expected_digest:
            raise DomainValidationError(ReasonCode.CONTENT_DIGEST_MISMATCH)

    @property
    def schema_version(self) -> str:
        return self.kind.schema_version

    @classmethod
    def create(
        cls, *, kind: PolicyKind, version: str, content: Mapping[str, JsonValue]
    ) -> CanonicalPolicy:
        _validate_version(version)
        canonical_content = canonicalize_policy_content(content)
        return cls(
            kind=kind,
            version=version,
            canonical_content=canonical_content,
            content_digest=_digest(kind.schema_version, version, canonical_content),
        )

    @classmethod
    def validate_external(
        cls,
        *,
        schema_version: str,
        version: str,
        content: Mapping[str, JsonValue],
        content_digest: str,
    ) -> CanonicalPolicy:
        """Validate persisted/untrusted policy facts without echoing their content on error."""
        kind = _kind_for_schema(schema_version)
        policy = cls.create(kind=kind, version=version, content=content)
        if not _is_lowercase_sha256(content_digest) or policy.content_digest != content_digest:
            raise DomainValidationError(ReasonCode.CONTENT_DIGEST_MISMATCH)
        return policy


def canonicalize_policy_content(content: Mapping[str, JsonValue]) -> str:
    """Return deterministic JSON for a policy payload or fail closed for non-JSON content."""
    normalized = _normalize_json_object(content)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_version(version: str) -> None:
    if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
        raise DomainValidationError(ReasonCode.INVALID_VERSION)


def _validate_canonical_content(canonical_content: str) -> str:
    """Accept only the exact canonical object JSON emitted by this module."""
    if not isinstance(canonical_content, str):
        raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
    try:
        decoded: object = json.loads(canonical_content)
    except (TypeError, json.JSONDecodeError):
        raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT) from None
    if not isinstance(decoded, Mapping):
        raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
    normalized = canonicalize_policy_content(cast(Mapping[str, JsonValue], decoded))
    if canonical_content != normalized:
        raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
    return normalized


def _kind_for_schema(schema_version: str) -> PolicyKind:
    for kind in PolicyKind:
        if schema_version == kind.schema_version:
            return kind
    raise DomainValidationError(ReasonCode.UNSUPPORTED_SCHEMA)


def _digest(schema_version: str, version: str, canonical_content: str) -> str:
    envelope = f"{schema_version}\n{version}\n{canonical_content}".encode()
    return hashlib.sha256(envelope).hexdigest()


def _is_lowercase_sha256(value: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _normalize_json_object(value: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    normalized = _normalize_json_value(value)
    if not isinstance(normalized, dict):  # Defensive: Mapping always normalizes to a dict.
        raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
    return normalized


def _normalize_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
        return value
    if isinstance(value, Mapping):
        items = tuple(value.items())
        for key, _ in items:
            if not isinstance(key, str):
                raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
        return {key: _normalize_json_value(item) for key, item in sorted(items)}
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]
    raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)


class GenerationBatchState(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GenerationItemState(StrEnum):
    REQUESTED = "REQUESTED"
    GENERATING = "GENERATING"
    RAW_STORED = "RAW_STORED"
    GENERATION_FAILED = "GENERATION_FAILED"
    CANCELLED = "CANCELLED"
    NORMALIZATION_PENDING = "NORMALIZATION_PENDING"
    NORMALIZED = "NORMALIZED"
    QA_PENDING = "QA_PENDING"
    QA_PASSED = "QA_PASSED"
    REJECTED = "REJECTED"
    IDENTITY_REGISTERED = "IDENTITY_REGISTERED"


class VariantState(StrEnum):
    SPECIFIED = "SPECIFIED"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    MEASURED = "MEASURED"
    ISOLATION_PASSED = "ISOLATION_PASSED"
    REJECTED = "REJECTED"


class ReleaseState(StrEnum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    RELEASED = "RELEASED"
    REVOKED = "REVOKED"


class AuthorityApprovalState(StrEnum):
    """Immutable authority revisions are drafted once and then approved once."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


_BATCH_TRANSITIONS: Mapping[GenerationBatchState, frozenset[GenerationBatchState]] = {
    GenerationBatchState.DRAFT: frozenset({GenerationBatchState.QUEUED}),
    GenerationBatchState.QUEUED: frozenset({GenerationBatchState.RUNNING}),
    GenerationBatchState.RUNNING: frozenset(
        {
            GenerationBatchState.COMPLETED,
            GenerationBatchState.PARTIAL,
            GenerationBatchState.FAILED,
            GenerationBatchState.CANCELLED,
        }
    ),
    GenerationBatchState.COMPLETED: frozenset(),
    GenerationBatchState.PARTIAL: frozenset(),
    GenerationBatchState.FAILED: frozenset(),
    GenerationBatchState.CANCELLED: frozenset(),
}

_ITEM_TRANSITIONS: Mapping[GenerationItemState, frozenset[GenerationItemState]] = {
    GenerationItemState.REQUESTED: frozenset(
        {GenerationItemState.GENERATING, GenerationItemState.CANCELLED}
    ),
    GenerationItemState.GENERATING: frozenset(
        {
            GenerationItemState.RAW_STORED,
            GenerationItemState.GENERATION_FAILED,
            GenerationItemState.CANCELLED,
        }
    ),
    GenerationItemState.RAW_STORED: frozenset({GenerationItemState.NORMALIZATION_PENDING}),
    GenerationItemState.GENERATION_FAILED: frozenset(),
    GenerationItemState.CANCELLED: frozenset(),
    GenerationItemState.NORMALIZATION_PENDING: frozenset({GenerationItemState.NORMALIZED}),
    GenerationItemState.NORMALIZED: frozenset({GenerationItemState.QA_PENDING}),
    GenerationItemState.QA_PENDING: frozenset(
        {GenerationItemState.QA_PASSED, GenerationItemState.REJECTED}
    ),
    GenerationItemState.QA_PASSED: frozenset({GenerationItemState.IDENTITY_REGISTERED}),
    GenerationItemState.REJECTED: frozenset(),
    GenerationItemState.IDENTITY_REGISTERED: frozenset(),
}

_VARIANT_TRANSITIONS: Mapping[VariantState, frozenset[VariantState]] = {
    VariantState.SPECIFIED: frozenset({VariantState.GENERATING}),
    VariantState.GENERATING: frozenset({VariantState.GENERATED}),
    VariantState.GENERATED: frozenset({VariantState.MEASURED}),
    VariantState.MEASURED: frozenset({VariantState.ISOLATION_PASSED, VariantState.REJECTED}),
    VariantState.ISOLATION_PASSED: frozenset(),
    VariantState.REJECTED: frozenset(),
}

_RELEASE_TRANSITIONS: Mapping[ReleaseState, frozenset[ReleaseState]] = {
    ReleaseState.DRAFT: frozenset({ReleaseState.UNDER_REVIEW}),
    ReleaseState.UNDER_REVIEW: frozenset({ReleaseState.RELEASED}),
    ReleaseState.RELEASED: frozenset({ReleaseState.REVOKED}),
    ReleaseState.REVOKED: frozenset(),
}

_AUTHORITY_APPROVAL_TRANSITIONS: Mapping[
    AuthorityApprovalState, frozenset[AuthorityApprovalState]
] = {
    AuthorityApprovalState.DRAFT: frozenset({AuthorityApprovalState.APPROVED}),
    AuthorityApprovalState.APPROVED: frozenset(),
}


def transition(current: Enum, target: Enum) -> Enum:
    """Return the target only for an ADR-approved lifecycle transition."""
    if type(current) is not type(target) or target not in _allowed_transitions(current):
        raise DomainValidationError(ReasonCode.INVALID_STATE_TRANSITION)
    return target


def _allowed_transitions(current: Enum) -> frozenset[Enum]:
    if isinstance(current, GenerationBatchState):
        return _BATCH_TRANSITIONS[current]
    if isinstance(current, GenerationItemState):
        return _ITEM_TRANSITIONS[current]
    if isinstance(current, VariantState):
        return _VARIANT_TRANSITIONS[current]
    if isinstance(current, ReleaseState):
        return _RELEASE_TRANSITIONS[current]
    if isinstance(current, AuthorityApprovalState):
        return _AUTHORITY_APPROVAL_TRANSITIONS[current]
    raise DomainValidationError(ReasonCode.INVALID_STATE_TRANSITION)


class GeometryDimensionClassification(StrEnum):
    READY = "READY"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSUPPORTED = "UNSUPPORTED"
    REQUIRES_3D = "REQUIRES_3D"
    STYLE_ONLY = "STYLE_ONLY"


_CLASSIFICATION_REASONS: Mapping[GeometryDimensionClassification, frozenset[ReasonCode]] = {
    GeometryDimensionClassification.READY: frozenset(),
    GeometryDimensionClassification.EXPERIMENTAL: frozenset({ReasonCode.FURTHER_RESEARCH}),
    GeometryDimensionClassification.UNSUPPORTED: frozenset({ReasonCode.UNSUPPORTED_DIMENSION}),
    GeometryDimensionClassification.REQUIRES_3D: frozenset({ReasonCode.REQUIRES_3D_RESEARCH}),
    GeometryDimensionClassification.STYLE_ONLY: frozenset({ReasonCode.STYLE_ONLY_DIMENSION}),
}


@dataclass(frozen=True)
class GeometryDimension:
    """A classified ontology entry; it carries no unvalidated measurement threshold."""

    key: str
    classification: GeometryDimensionClassification
    reason_codes: tuple[ReasonCode, ...] = ()

    def __post_init__(self) -> None:
        if _DIMENSION_KEY_PATTERN.fullmatch(self.key) is None:
            raise DomainValidationError(ReasonCode.UNKNOWN_GEOMETRY_DIMENSION)
        if _FORBIDDEN_ONTOLOGY_KEY_TOKENS & set(self.key.split("_")):
            raise DomainValidationError(ReasonCode.PROHIBITED_ONTOLOGY_CONCEPT)
        expected = _CLASSIFICATION_REASONS[self.classification]
        if self.classification is GeometryDimensionClassification.READY:
            if self.reason_codes:
                raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
            return
        if not self.reason_codes or not set(self.reason_codes).issubset(expected):
            raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)


@dataclass(frozen=True)
class GeometryOntology:
    """A versioned, explicit geometry ontology that rejects undeclared dimensions."""

    authority: CanonicalPolicy
    dimensions: tuple[GeometryDimension, ...]

    def __post_init__(self) -> None:
        if self.authority.kind is not PolicyKind.GEOMETRY_ONTOLOGY_VERSION:
            raise DomainValidationError(ReasonCode.UNSUPPORTED_SCHEMA)
        keys = tuple(dimension.key for dimension in self.dimensions)
        if len(keys) != len(set(keys)):
            raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)

    def classification_for(self, dimension_key: str) -> GeometryDimensionClassification:
        return self.dimension_for(dimension_key).classification

    def dimension_for(self, dimension_key: str) -> GeometryDimension:
        for dimension in self.dimensions:
            if dimension.key == dimension_key:
                return dimension
        raise DomainValidationError(ReasonCode.UNKNOWN_GEOMETRY_DIMENSION)


def require_ready_dimension(ontology: GeometryOntology, dimension_key: str) -> GeometryDimension:
    """Permit geometry work only for an explicitly ontology-declared READY dimension."""
    dimension = ontology.dimension_for(dimension_key)
    if dimension.classification is GeometryDimensionClassification.READY:
        return dimension
    reason_codes = _CLASSIFICATION_REASONS[dimension.classification]
    if reason_codes:
        raise DomainValidationError(next(iter(reason_codes)))
    raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
