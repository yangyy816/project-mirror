from __future__ import annotations

from dataclasses import replace

import pytest

from mirror_api.synthetic_dataset import (
    LANDMARK_WARP_PLAN_BUILDER_VERSION,
    DomainValidationError,
    LandmarkWarpPlanAdmissionService,
    LandmarkWarpPlanAuthority,
    LandmarkWarpPlanOrigin,
    ReasonCode,
    WarpControlPoint,
    WarpTriangle,
)
from mirror_api.synthetic_dataset.geometry_transform import LandmarkWarpPlan


def _plan() -> LandmarkWarpPlan:
    return LandmarkWarpPlan.create(
        specification_digest="a" * 64,
        control_points=(
            WarpControlPoint("a", 0.0, 0.0, 0.05, 0.0, 900_000),
            WarpControlPoint("b", 1.0, 0.0, 1.0, 0.0, 900_000),
            WarpControlPoint("c", 0.0, 1.0, 0.05, 1.0, 900_000),
        ),
        triangles=(WarpTriangle(("a", "b", "c")),),
    )


def _authority() -> LandmarkWarpPlanAuthority:
    return LandmarkWarpPlanAdmissionService.prepare(
        specification_digest="a" * 64,
        plan=_plan(),
        origin_reference="m4-research-plan-01",
        origin_digest="b" * 64,
        builder_version=LANDMARK_WARP_PLAN_BUILDER_VERSION,
        builder_manifest_digest="c" * 64,
    )


def test_plan_payload_round_trips_exactly_and_authority_binds_all_facts() -> None:
    authority = _authority()

    assert LandmarkWarpPlan.from_canonical_payload(authority.canonical_payload) == authority.plan
    persisted = LandmarkWarpPlanAuthority.from_persisted(
        specification_digest=authority.specification_digest,
        canonical_payload=authority.canonical_payload,
        origin_kind=LandmarkWarpPlanOrigin.PREREGISTERED_M4_RESEARCH_PLAN,
        origin_reference=authority.origin_reference,
        origin_digest=authority.origin_digest,
        builder_version=authority.builder_version,
        builder_manifest_digest=authority.builder_manifest_digest,
        warp_plan_digest=authority.warp_plan_digest,
        authority_digest=authority.authority_digest,
    )
    assert persisted == authority


@pytest.mark.parametrize(
    "payload",
    (
        lambda value: value.replace('"control_points"', '"unknown"', 1),
        lambda value: value.replace('"control_points":[', '"control_points": [', 1),
        lambda value: value.replace(
            '"landmark_code":"a"', '"landmark_code":"a","landmark_code":"x"', 1
        ),
        lambda value: value.replace('"source_x":0.0', '"source_x":0', 1),
        lambda value: value.replace('"destination_x":0.05', '"destination_x":NaN', 1),
        lambda value: value.replace('"a","b","c"', '"b","c","a"', 1),
        lambda value: value.replace(
            '],"specification_digest"',
            ',{"confidence_ppm":900000,"destination_x":0.5,"destination_y":0.5,'
            '"landmark_code":"extra","source_x":0.5,"source_y":0.5,"unknown":true}]'
            ',"specification_digest"',
            1,
        ),
    ),
)
def test_plan_parser_rejects_noncanonical_or_closed_grammar_payloads(payload: object) -> None:
    canonical = _plan().to_canonical_payload()
    assert callable(payload)
    with pytest.raises(DomainValidationError) as rejected:
        LandmarkWarpPlan.from_canonical_payload(payload(canonical))
    assert rejected.value.reason_code is ReasonCode.INVALID_WARP_PLAN


def test_authority_rejects_plan_specification_mismatch_and_tampered_binding() -> None:
    authority = _authority()
    with pytest.raises(DomainValidationError):
        LandmarkWarpPlanAdmissionService.prepare(
            specification_digest="d" * 64,
            plan=authority.plan,
            origin_reference=authority.origin_reference,
            origin_digest=authority.origin_digest,
            builder_version=authority.builder_version,
            builder_manifest_digest=authority.builder_manifest_digest,
        )
    with pytest.raises(DomainValidationError):
        replace(authority, origin_digest="d" * 64)
    for unsafe_reference in ("https://example.invalid/plan", "private/path/plan"):
        with pytest.raises(DomainValidationError):
            LandmarkWarpPlanAdmissionService.prepare(
                specification_digest=authority.specification_digest,
                plan=authority.plan,
                origin_reference=unsafe_reference,
                origin_digest=authority.origin_digest,
                builder_version=LANDMARK_WARP_PLAN_BUILDER_VERSION,
                builder_manifest_digest=authority.builder_manifest_digest,
            )
    with pytest.raises(DomainValidationError):
        LandmarkWarpPlanAdmissionService.prepare(
            specification_digest=authority.specification_digest,
            plan=authority.plan,
            origin_reference=authority.origin_reference,
            origin_digest=authority.origin_digest,
            builder_version="unapproved-builder-v2",
            builder_manifest_digest=authority.builder_manifest_digest,
        )
