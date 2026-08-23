"""Read-only P2 operational cost and event projections.

The types in this module are deliberately projections over accepted PostgreSQL
authority.  They never create a cost fact, infer money from native/offline
request counts, or accept arbitrary log payloads.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Literal, Protocol, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import GenerationBatch, GenerationItem, ProviderCostEvent

_ID = re.compile(r"[0-9a-f]{32}\Z")
_CODE = re.compile(r"[a-z][a-z0-9_]{2,63}\Z")
_ACTOR = re.compile(r"[a-z][a-z0-9._-]{2,63}\Z")
_CURRENCIES = frozenset({"CNY", "USD"})
_BATCH_STATUSES = frozenset(
    {"DRAFT", "QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED"}
)
_TERMINAL_ITEM_STATUSES = frozenset({"RAW_STORED", "GENERATION_FAILED", "CANCELLED"})
_PENDING_ITEM_STATUSES = frozenset({"REQUESTED", "GENERATING"})


class CostProjectionCode(StrEnum):
    BATCH_NOT_FOUND = "cost_projection_batch_not_found"
    INVALID_ACTOR = "cost_projection_actor_invalid"
    INVALID_AMOUNT = "cost_projection_amount_invalid"
    INVALID_BATCH = "cost_projection_batch_invalid"
    INVALID_BATCH_STATUS = "cost_projection_batch_status_invalid"
    INVALID_COST_KIND = "cost_projection_kind_invalid"
    INVALID_COUNTS = "cost_projection_counts_invalid"
    INVALID_CURRENCY = "cost_projection_currency_invalid"
    INVALID_EVENT = "cost_projection_event_invalid"
    INVALID_EVENT_NAME = "cost_projection_event_name_invalid"
    INVALID_REASON = "cost_projection_reason_invalid"
    INVALID_REQUEST = "cost_projection_request_invalid"
    INVALID_SUMMARY = "cost_projection_summary_invalid"


class CostClassification(StrEnum):
    ACTUAL = "actual"
    ESTIMATED = "estimated"


class CostAvailability(StrEnum):
    ACTUAL = "actual"
    ESTIMATED = "estimated"
    MIXED = "mixed"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class MonetaryCostAggregate:
    """One non-inferred currency aggregate for a single ProviderCostEvent kind."""

    classification: CostClassification
    currency: Literal["CNY", "USD"]
    amount_micros: int
    event_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.classification, CostClassification):
            raise CostProjectionRejected(CostProjectionCode.INVALID_COST_KIND)
        if type(self.currency) is not str or self.currency not in _CURRENCIES:
            raise CostProjectionRejected(CostProjectionCode.INVALID_CURRENCY)
        if type(self.amount_micros) is not int or self.amount_micros < 0:
            raise CostProjectionRejected(CostProjectionCode.INVALID_AMOUNT)
        if type(self.event_count) is not int or self.event_count <= 0:
            raise CostProjectionRejected(CostProjectionCode.INVALID_COUNTS)


@dataclass(frozen=True)
class CostSummary:
    """A reproducible aggregate which keeps money facts distinct from absence."""

    batch_id: str
    generation_policy_id: str
    batch_status: str
    actual: tuple[MonetaryCostAggregate, ...]
    estimated: tuple[MonetaryCostAggregate, ...]
    unavailable_item_count: int
    pending_item_count: int
    total_item_count: int

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.batch_id) is None or _ID.fullmatch(self.generation_policy_id) is None:
            raise CostProjectionRejected(CostProjectionCode.INVALID_BATCH)
        if type(self.batch_status) is not str or self.batch_status not in _BATCH_STATUSES:
            raise CostProjectionRejected(CostProjectionCode.INVALID_BATCH_STATUS)
        if not all(
            isinstance(item, MonetaryCostAggregate)
            and item.classification is CostClassification.ACTUAL
            for item in self.actual
        ) or not all(
            isinstance(item, MonetaryCostAggregate)
            and item.classification is CostClassification.ESTIMATED
            for item in self.estimated
        ):
            raise CostProjectionRejected(CostProjectionCode.INVALID_SUMMARY)
        if (
            any(
                type(value) is not int or value < 0
                for value in (
                    self.unavailable_item_count,
                    self.pending_item_count,
                    self.total_item_count,
                )
            )
            or self.unavailable_item_count + self.pending_item_count > self.total_item_count
        ):
            raise CostProjectionRejected(CostProjectionCode.INVALID_COUNTS)

    @property
    def availability(self) -> CostAvailability:
        has_actual = bool(self.actual)
        has_estimated = bool(self.estimated)
        has_unavailable = self.unavailable_item_count > 0
        has_pending = self.pending_item_count > 0
        category_count = sum((has_actual, has_estimated, has_unavailable, has_pending))
        if category_count > 1:
            return CostAvailability.MIXED
        if has_actual:
            return CostAvailability.ACTUAL
        if has_estimated:
            return CostAvailability.ESTIMATED
        if has_pending:
            return CostAvailability.PENDING
        return CostAvailability.UNAVAILABLE


class CostProjectionRejected(Exception):
    """Stable rejection which never carries a caller or database value."""

    def __init__(self, code: CostProjectionCode) -> None:
        self.code = code
        super().__init__("synthetic dataset cost projection was rejected")


class CostSummaryReadPort(Protocol):
    async def summarize_batch(self, batch_id: str) -> CostSummary: ...


class PostgresCostSummaryReadModel:
    """Read-only PostgreSQL projection over immutable ProviderCostEvent evidence."""

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def summarize_batch(self, batch_id: str) -> CostSummary:
        if _ID.fullmatch(batch_id) is None:
            raise CostProjectionRejected(CostProjectionCode.INVALID_BATCH)
        async with self._sessions() as session:
            batch = await session.scalar(
                select(GenerationBatch).where(GenerationBatch.id == batch_id)
            )
            if batch is None:
                raise CostProjectionRejected(CostProjectionCode.BATCH_NOT_FOUND)
            items = tuple(
                (
                    await session.execute(
                        select(GenerationItem.id, GenerationItem.status).where(
                            GenerationItem.batch_id == batch_id
                        )
                    )
                ).all()
            )
            cost_rows = tuple(
                (
                    await session.execute(
                        select(
                            ProviderCostEvent.generation_item_id,
                            ProviderCostEvent.event_kind,
                            ProviderCostEvent.currency,
                            ProviderCostEvent.amount_micros,
                        )
                        .join(
                            GenerationItem,
                            GenerationItem.id == ProviderCostEvent.generation_item_id,
                        )
                        .where(GenerationItem.batch_id == batch_id)
                    )
                ).all()
            )

        by_kind_currency: dict[tuple[CostClassification, str], list[int]] = {}
        item_cost_ids: set[str] = set()
        for item_id, event_kind, currency, amount_micros in cost_rows:
            classification = _classification_from_event_kind(event_kind)
            key = (classification, currency)
            amounts = by_kind_currency.setdefault(key, [0, 0])
            amounts[0] += amount_micros
            amounts[1] += 1
            item_cost_ids.add(item_id)

        actual = _aggregates_for(CostClassification.ACTUAL, by_kind_currency)
        estimated = _aggregates_for(CostClassification.ESTIMATED, by_kind_currency)
        unavailable = sum(
            status in _TERMINAL_ITEM_STATUSES and item_id not in item_cost_ids
            for item_id, status in items
        )
        pending = sum(status in _PENDING_ITEM_STATUSES for _, status in items)
        return CostSummary(
            batch_id=batch.id,
            generation_policy_id=batch.generation_policy_id,
            batch_status=batch.status,
            actual=actual,
            estimated=estimated,
            unavailable_item_count=unavailable,
            pending_item_count=pending,
            total_item_count=len(items),
        )


@dataclass(frozen=True)
class DatasetOperationalEvent:
    """Fixed, payload-free event projection for P2 operational aggregates."""

    request_id: str
    batch_id: str
    generation_policy_id: str
    actor_reference: str
    reason_code: str
    availability: CostAvailability
    actual_event_count: int
    estimated_event_count: int
    unavailable_item_count: int
    pending_item_count: int
    event_name: Literal["synthetic_dataset.cost_summary.projected"] = (
        "synthetic_dataset.cost_summary.projected"
    )

    def __post_init__(self) -> None:
        if self.event_name != "synthetic_dataset.cost_summary.projected":
            raise CostProjectionRejected(CostProjectionCode.INVALID_EVENT_NAME)
        if _ID.fullmatch(self.request_id) is None:
            raise CostProjectionRejected(CostProjectionCode.INVALID_REQUEST)
        if _ID.fullmatch(self.batch_id) is None or _ID.fullmatch(self.generation_policy_id) is None:
            raise CostProjectionRejected(CostProjectionCode.INVALID_BATCH)
        if _ACTOR.fullmatch(self.actor_reference) is None:
            raise CostProjectionRejected(CostProjectionCode.INVALID_ACTOR)
        if _CODE.fullmatch(self.reason_code) is None:
            raise CostProjectionRejected(CostProjectionCode.INVALID_REASON)
        if not isinstance(self.availability, CostAvailability):
            raise CostProjectionRejected(CostProjectionCode.INVALID_EVENT)
        if any(
            type(value) is not int or value < 0
            for value in (
                self.actual_event_count,
                self.estimated_event_count,
                self.unavailable_item_count,
                self.pending_item_count,
            )
        ):
            raise CostProjectionRejected(CostProjectionCode.INVALID_COUNTS)

    @classmethod
    def from_summary(
        cls,
        summary: CostSummary,
        *,
        request_id: str,
        actor_reference: str,
        reason_code: str,
    ) -> DatasetOperationalEvent:
        return cls(
            request_id=request_id,
            batch_id=summary.batch_id,
            generation_policy_id=summary.generation_policy_id,
            actor_reference=actor_reference,
            reason_code=reason_code,
            availability=summary.availability,
            actual_event_count=sum(item.event_count for item in summary.actual),
            estimated_event_count=sum(item.event_count for item in summary.estimated),
            unavailable_item_count=summary.unavailable_item_count,
            pending_item_count=summary.pending_item_count,
        )


def emit_dataset_operational_event(logger: logging.Logger, event: DatasetOperationalEvent) -> None:
    """Emit only the immutable event allowlist; no arbitrary metadata is accepted."""

    if type(event) is not DatasetOperationalEvent:
        raise CostProjectionRejected(CostProjectionCode.INVALID_EVENT)
    payload = asdict(event)
    payload["availability"] = event.availability.value
    logger.info(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))


def _classification_from_event_kind(event_kind: str) -> CostClassification:
    if event_kind == "final":
        return CostClassification.ACTUAL
    if event_kind == "estimated":
        return CostClassification.ESTIMATED
    raise CostProjectionRejected(CostProjectionCode.INVALID_COST_KIND)


def _aggregates_for(
    classification: CostClassification,
    values: dict[tuple[CostClassification, str], list[int]],
) -> tuple[MonetaryCostAggregate, ...]:
    aggregates: list[MonetaryCostAggregate] = []
    for (aggregate_classification, currency), amount_and_count in sorted(values.items()):
        if aggregate_classification is not classification:
            continue
        aggregates.append(
            MonetaryCostAggregate(
                classification=classification,
                currency=cast(Literal["CNY", "USD"], currency),
                amount_micros=amount_and_count[0],
                event_count=amount_and_count[1],
            )
        )
    return tuple(aggregates)
