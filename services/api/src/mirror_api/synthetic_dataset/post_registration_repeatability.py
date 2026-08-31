"""Bounded, authority-homogeneous repeatability aggregation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


class RepeatabilityAggregationError(RuntimeError):
    """Fail-closed repeatability aggregation error."""


@dataclass(frozen=True, slots=True)
class RepeatabilityRecord:
    request_reference_sha256: str
    legacy_bridge_sha256: str
    runtime_sha256: str
    model_sha256: str
    policy_sha256: str
    outcome: str
    measurements: tuple[float, ...]


def aggregate_repeatability(records: Sequence[RepeatabilityRecord]) -> tuple[float, ...]:
    """Return per-measurement span only for complete, authority-equal success records."""
    if not records or any(record.outcome != "passed" for record in records):
        raise RepeatabilityAggregationError("REPEATABILITY_INCOMPLETE_OR_FAILED")
    first = records[0]
    authority = (
        first.request_reference_sha256,
        first.legacy_bridge_sha256,
        first.runtime_sha256,
        first.model_sha256,
        first.policy_sha256,
    )
    if any(
        (
            record.request_reference_sha256,
            record.legacy_bridge_sha256,
            record.runtime_sha256,
            record.model_sha256,
            record.policy_sha256,
        )
        != authority
        for record in records
    ):
        raise RepeatabilityAggregationError("REPEATABILITY_AUTHORITY_MISMATCH")
    width = len(first.measurements)
    if width == 0 or any(len(record.measurements) != width for record in records):
        raise RepeatabilityAggregationError("REPEATABILITY_MEASUREMENT_SHAPE_INVALID")
    return tuple(
        max(column) - min(column) for column in zip(*(r.measurements for r in records), strict=True)
    )
