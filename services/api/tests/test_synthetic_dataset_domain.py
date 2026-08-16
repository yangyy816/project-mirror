from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from mirror_api.synthetic_dataset.domain import (
    AuthorityApprovalState,
    CanonicalPolicy,
    DomainValidationError,
    GenerationBatchState,
    GenerationItemState,
    GeometryDimension,
    GeometryDimensionClassification,
    GeometryOntology,
    JsonValue,
    PolicyKind,
    ReasonCode,
    ReleaseState,
    VariantState,
    canonicalize_policy_content,
    require_ready_dimension,
    transition,
)

type LifecycleState = (
    AuthorityApprovalState
    | GenerationBatchState
    | GenerationItemState
    | VariantState
    | ReleaseState
)


def test_canonical_policy_content_and_digest_are_deterministic() -> None:
    first = CanonicalPolicy.create(
        kind=PolicyKind.SYNTHETIC_QA_POLICY,
        version="synthetic-qa-policy-v1",
        content={"hard_gates": ["origin", "checksum"], "schema": {"revision": 1}},
    )
    second = CanonicalPolicy.create(
        kind=PolicyKind.SYNTHETIC_QA_POLICY,
        version="synthetic-qa-policy-v1",
        content={"schema": {"revision": 1}, "hard_gates": ["origin", "checksum"]},
    )

    assert first == second
    assert first.canonical_content == canonicalize_policy_content(
        {"schema": {"revision": 1}, "hard_gates": ["origin", "checksum"]}
    )
    assert len(first.content_digest) == 64


def test_external_policy_rejects_unknown_schema_and_digest_without_echoing_content() -> None:
    payload_marker = "provider-payload-must-not-appear"
    with pytest.raises(DomainValidationError) as unknown_schema:
        CanonicalPolicy.validate_external(
            schema_version="mirror.synthetic-dataset/Unknown/v1",
            version="synthetic-qa-policy-v1",
            content={"prompt": payload_marker},
            content_digest="0" * 64,
        )
    assert unknown_schema.value.reason_code is ReasonCode.UNSUPPORTED_SCHEMA
    assert payload_marker not in str(unknown_schema.value)

    policy = CanonicalPolicy.create(
        kind=PolicyKind.SYNTHETIC_PROMPT_TEMPLATE,
        version="synthetic-prompt-template-v1",
        content={"template": payload_marker},
    )
    with pytest.raises(DomainValidationError) as wrong_digest:
        CanonicalPolicy.validate_external(
            schema_version=policy.schema_version,
            version=policy.version,
            content={"template": payload_marker},
            content_digest="f" * 64,
        )
    assert wrong_digest.value.reason_code is ReasonCode.CONTENT_DIGEST_MISMATCH
    assert payload_marker not in str(wrong_digest.value)


@pytest.mark.parametrize(
    "content",
    [
        {7: "provider-payload-must-not-appear"},
        {"nested": {"valid": 1, 7: "provider-payload-must-not-appear"}},
        {"nested": [float("inf")]},
        {"nested": object()},
    ],
    ids=["non-string-key", "mixed-nested-keys", "non-finite-nested", "unsupported-nested"],
)
def test_invalid_policy_content_fails_closed_without_echoing_payload(content: object) -> None:
    payload_marker = "provider-payload-must-not-appear"
    with pytest.raises(DomainValidationError) as error:
        canonicalize_policy_content(cast(Mapping[str, JsonValue], content))
    assert error.value.reason_code is ReasonCode.INVALID_POLICY_CONTENT
    assert payload_marker not in str(error.value)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (GenerationBatchState.DRAFT, GenerationBatchState.QUEUED),
        (GenerationBatchState.RUNNING, GenerationBatchState.PARTIAL),
        (GenerationItemState.QA_PASSED, GenerationItemState.IDENTITY_REGISTERED),
        (VariantState.MEASURED, VariantState.ISOLATION_PASSED),
        (ReleaseState.RELEASED, ReleaseState.REVOKED),
        (AuthorityApprovalState.DRAFT, AuthorityApprovalState.APPROVED),
    ],
)
def test_approved_state_transitions_are_accepted(
    current: LifecycleState, target: LifecycleState
) -> None:
    assert transition(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (GenerationItemState.REQUESTED, GenerationItemState.REJECTED),
        (VariantState.GENERATING, VariantState.REJECTED),
        (ReleaseState.UNDER_REVIEW, ReleaseState.REVOKED),
        (GenerationBatchState.QUEUED, GenerationBatchState.CANCELLED),
        (GenerationBatchState.COMPLETED, GenerationBatchState.RUNNING),
        (GenerationBatchState.QUEUED, GenerationItemState.GENERATING),
        (AuthorityApprovalState.APPROVED, AuthorityApprovalState.DRAFT),
        (AuthorityApprovalState.APPROVED, AuthorityApprovalState.APPROVED),
    ],
)
def test_unapproved_state_transitions_fail_closed(
    current: LifecycleState, target: LifecycleState
) -> None:
    with pytest.raises(DomainValidationError) as error:
        transition(current, target)
    assert error.value.reason_code is ReasonCode.INVALID_STATE_TRANSITION


def test_geometry_ontology_preserves_the_approved_classifications() -> None:
    authority = CanonicalPolicy.create(
        kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
        version="geometry-ontology-v1",
        content={"ontology": "fixture"},
    )
    ontology = GeometryOntology(
        authority=authority,
        dimensions=(
            GeometryDimension("jaw_width", GeometryDimensionClassification.READY),
            GeometryDimension(
                "nose_projection",
                GeometryDimensionClassification.EXPERIMENTAL,
                (ReasonCode.FURTHER_RESEARCH,),
            ),
            GeometryDimension(
                "hair_texture",
                GeometryDimensionClassification.STYLE_ONLY,
                (ReasonCode.STYLE_ONLY_DIMENSION,),
            ),
            GeometryDimension(
                "profile_depth",
                GeometryDimensionClassification.REQUIRES_3D,
                (ReasonCode.REQUIRES_3D_RESEARCH,),
            ),
            GeometryDimension(
                "unknown_measurement",
                GeometryDimensionClassification.UNSUPPORTED,
                (ReasonCode.UNSUPPORTED_DIMENSION,),
            ),
        ),
    )

    assert ontology.classification_for("jaw_width") is GeometryDimensionClassification.READY
    assert ontology.classification_for("hair_texture") is GeometryDimensionClassification.STYLE_ONLY
    assert require_ready_dimension(ontology, "jaw_width").key == "jaw_width"
    with pytest.raises(DomainValidationError) as unsupported:
        require_ready_dimension(ontology, "unknown_measurement")
    assert unsupported.value.reason_code is ReasonCode.UNSUPPORTED_DIMENSION
    with pytest.raises(DomainValidationError) as error:
        ontology.classification_for("undeclared_dimension")
    assert error.value.reason_code is ReasonCode.UNKNOWN_GEOMETRY_DIMENSION


def test_geometry_classification_fails_closed_when_its_reason_is_not_approved() -> None:
    with pytest.raises(DomainValidationError) as error:
        GeometryDimension(
            "profile_depth",
            GeometryDimensionClassification.REQUIRES_3D,
            (ReasonCode.FURTHER_RESEARCH,),
        )
    assert error.value.reason_code is ReasonCode.INVALID_POLICY_CONTENT


@pytest.mark.parametrize("forbidden_key", ["race", "beauty_score", "population_target"])
def test_geometry_ontology_rejects_sensitive_or_global_beauty_concepts(forbidden_key: str) -> None:
    with pytest.raises(DomainValidationError) as error:
        GeometryDimension(forbidden_key, GeometryDimensionClassification.READY)
    assert error.value.reason_code is ReasonCode.PROHIBITED_ONTOLOGY_CONCEPT
