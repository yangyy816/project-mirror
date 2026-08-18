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
from .geometry_variant import (
    DeterminismLevel,
    TransformDirection,
    TransformRunState,
    VariantSpecification,
    require_researchable_dimension,
    transition_transform_run,
)

__all__ = [
    "AuthorityApprovalState",
    "CanonicalPolicy",
    "DeterminismLevel",
    "DomainValidationError",
    "GenerationBatchState",
    "GenerationItemState",
    "GeometryDimension",
    "GeometryDimensionClassification",
    "GeometryOntology",
    "PolicyKind",
    "ReasonCode",
    "ReleaseState",
    "TransformDirection",
    "TransformRunState",
    "VariantSpecification",
    "VariantState",
    "canonicalize_policy_content",
    "require_ready_dimension",
    "require_researchable_dimension",
    "transition",
    "transition_transform_run",
]
