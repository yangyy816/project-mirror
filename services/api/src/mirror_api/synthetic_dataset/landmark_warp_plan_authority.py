"""Immutable, preregistered LandmarkWarpPlan authority for P2-M4.

This module deliberately accepts a typed plan only.  It is not a landmark
planner and does not accept image, QA, storage, URL, or arbitrary JSON input.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from .domain import DomainValidationError, ReasonCode
from .geometry_transform import WARP_PLAN_SCHEMA_VERSION, LandmarkWarpPlan

LANDMARK_WARP_PLAN_AUTHORITY_SCHEMA_VERSION = (
    "mirror.synthetic-dataset/LandmarkWarpPlanAuthority/v1"
)
MAX_CANONICAL_WARP_PLAN_BYTES = 262_144
LANDMARK_WARP_PLAN_BUILDER_VERSION = "canonical-warp-plan-builder-v1"

_REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@-]{2,127}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class LandmarkWarpPlanOrigin(StrEnum):
    PREREGISTERED_M4_RESEARCH_PLAN = "PREREGISTERED_M4_RESEARCH_PLAN"


@dataclass(frozen=True)
class LandmarkWarpPlanAuthority:
    """Closed immutable facts required to bind one plan to one specification."""

    specification_digest: str
    plan: LandmarkWarpPlan
    origin_kind: LandmarkWarpPlanOrigin
    origin_reference: str
    origin_digest: str
    builder_version: str
    builder_manifest_digest: str
    canonical_payload: str
    warp_plan_digest: str
    authority_digest: str
    plan_schema_version: str = WARP_PLAN_SCHEMA_VERSION
    schema_version: str = LANDMARK_WARP_PLAN_AUTHORITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != LANDMARK_WARP_PLAN_AUTHORITY_SCHEMA_VERSION:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if self.plan_schema_version != WARP_PLAN_SCHEMA_VERSION:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if type(self.plan) is not LandmarkWarpPlan:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        _require_digest(self.specification_digest)
        _require_digest(self.origin_digest)
        _require_digest(self.builder_manifest_digest)
        _require_digest(self.warp_plan_digest)
        _require_digest(self.authority_digest)
        _require_reference(self.origin_reference)
        if self.builder_version != LANDMARK_WARP_PLAN_BUILDER_VERSION:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if self.origin_kind is not LandmarkWarpPlanOrigin.PREREGISTERED_M4_RESEARCH_PLAN:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        if self.plan.specification_digest != self.specification_digest:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        payload = self.plan.to_canonical_payload()
        if (
            self.canonical_payload != payload
            or len(payload.encode("utf-8")) > MAX_CANONICAL_WARP_PLAN_BYTES
            or self.warp_plan_digest != _warp_plan_digest(payload)
            or self.authority_digest
            != _authority_digest(
                specification_digest=self.specification_digest,
                origin_kind=self.origin_kind,
                origin_reference=self.origin_reference,
                origin_digest=self.origin_digest,
                builder_version=self.builder_version,
                builder_manifest_digest=self.builder_manifest_digest,
                warp_plan_digest=self.warp_plan_digest,
            )
        ):
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)

    @classmethod
    def create(
        cls,
        *,
        specification_digest: str,
        plan: LandmarkWarpPlan,
        origin_kind: LandmarkWarpPlanOrigin,
        origin_reference: str,
        origin_digest: str,
        builder_version: str,
        builder_manifest_digest: str,
    ) -> LandmarkWarpPlanAuthority:
        if type(plan) is not LandmarkWarpPlan:
            raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
        payload = plan.to_canonical_payload()
        warp_plan_digest = _warp_plan_digest(payload)
        return cls(
            specification_digest=specification_digest,
            plan=plan,
            origin_kind=origin_kind,
            origin_reference=origin_reference,
            origin_digest=origin_digest,
            builder_version=builder_version,
            builder_manifest_digest=builder_manifest_digest,
            canonical_payload=payload,
            warp_plan_digest=warp_plan_digest,
            authority_digest=_authority_digest(
                specification_digest=specification_digest,
                origin_kind=origin_kind,
                origin_reference=origin_reference,
                origin_digest=origin_digest,
                builder_version=builder_version,
                builder_manifest_digest=builder_manifest_digest,
                warp_plan_digest=warp_plan_digest,
            ),
        )

    @classmethod
    def from_persisted(
        cls,
        *,
        specification_digest: str,
        canonical_payload: str,
        origin_kind: LandmarkWarpPlanOrigin,
        origin_reference: str,
        origin_digest: str,
        builder_version: str,
        builder_manifest_digest: str,
        warp_plan_digest: str,
        authority_digest: str,
        plan_schema_version: str = WARP_PLAN_SCHEMA_VERSION,
        schema_version: str = LANDMARK_WARP_PLAN_AUTHORITY_SCHEMA_VERSION,
    ) -> LandmarkWarpPlanAuthority:
        return cls(
            specification_digest=specification_digest,
            plan=LandmarkWarpPlan.from_canonical_payload(canonical_payload),
            origin_kind=origin_kind,
            origin_reference=origin_reference,
            origin_digest=origin_digest,
            builder_version=builder_version,
            builder_manifest_digest=builder_manifest_digest,
            canonical_payload=canonical_payload,
            warp_plan_digest=warp_plan_digest,
            authority_digest=authority_digest,
            plan_schema_version=plan_schema_version,
            schema_version=schema_version,
        )


class LandmarkWarpPlanAdmissionService:
    """Prepare a closed authority document from a typed preregistered plan only."""

    @staticmethod
    def prepare(
        *,
        specification_digest: str,
        plan: LandmarkWarpPlan,
        origin_reference: str,
        origin_digest: str,
        builder_version: str,
        builder_manifest_digest: str,
    ) -> LandmarkWarpPlanAuthority:
        return LandmarkWarpPlanAuthority.create(
            specification_digest=specification_digest,
            plan=plan,
            origin_kind=LandmarkWarpPlanOrigin.PREREGISTERED_M4_RESEARCH_PLAN,
            origin_reference=origin_reference,
            origin_digest=origin_digest,
            builder_version=builder_version,
            builder_manifest_digest=builder_manifest_digest,
        )


def _warp_plan_digest(canonical_payload: str) -> str:
    return hashlib.sha256(f"{WARP_PLAN_SCHEMA_VERSION}\n{canonical_payload}".encode()).hexdigest()


def _authority_digest(
    *,
    specification_digest: str,
    origin_kind: LandmarkWarpPlanOrigin,
    origin_reference: str,
    origin_digest: str,
    builder_version: str,
    builder_manifest_digest: str,
    warp_plan_digest: str,
) -> str:
    facts = {
        "builder_manifest_digest": builder_manifest_digest,
        "builder_version": builder_version,
        "origin_digest": origin_digest,
        "origin_kind": origin_kind.value,
        "origin_reference": origin_reference,
        "specification_digest": specification_digest,
        "warp_plan_digest": warp_plan_digest,
    }
    canonical = json.dumps(
        facts, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(
        f"{LANDMARK_WARP_PLAN_AUTHORITY_SCHEMA_VERSION}\n{canonical}".encode()
    ).hexdigest()


def _require_digest(value: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)


def _require_reference(value: str) -> None:
    if type(value) is not str or _REFERENCE_PATTERN.fullmatch(value) is None:
        raise DomainValidationError(ReasonCode.INVALID_WARP_PLAN)
