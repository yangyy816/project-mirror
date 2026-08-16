"""First-party synthetic dataset domain contracts.

This package is intentionally independent from HTTP, task runners, storage, and provider SDKs.
"""

from .domain import (
    AuthorityApprovalState,
    CanonicalPolicy,
    DomainValidationError,
    GenerationBatchState,
    GenerationItemState,
    GeometryDimension,
    GeometryDimensionClassification,
    GeometryOntology,
    PolicyKind,
    ReasonCode,
    ReleaseState,
    VariantState,
    canonicalize_policy_content,
    require_ready_dimension,
    transition,
)

__all__ = [
    "AuthorityApprovalState",
    "CanonicalPolicy",
    "DomainValidationError",
    "GenerationBatchState",
    "GenerationItemState",
    "GeometryDimension",
    "GeometryDimensionClassification",
    "GeometryOntology",
    "PolicyKind",
    "ReasonCode",
    "ReleaseState",
    "VariantState",
    "canonicalize_policy_content",
    "require_ready_dimension",
    "transition",
]
