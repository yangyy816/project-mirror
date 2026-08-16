from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from mirror_api.providers.base import SYNTHETIC_IMAGE_MEDIA_TYPES

_ID = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_REFERENCE = re.compile(r"[a-z0-9][a-z0-9._:-]{2,127}\Z")
_RESULT_CODE = re.compile(r"[a-z][a-z0-9_]{2,63}\Z")


def validate_result_code(value: str) -> str:
    if _RESULT_CODE.fullmatch(value) is None:
        raise GenerationOperationRejected("invalid_generation_result_code")
    return value


class GenerationOperationRejected(Exception):
    """A fail-closed application rejection without policy or Prompt content."""

    def __init__(self, code: str) -> None:
        if _RESULT_CODE.fullmatch(code) is None:
            code = "generation_operation_rejected"
        self.code = code
        super().__init__("synthetic generation operation was rejected")


@dataclass(frozen=True)
class GenerationBatchCreate:
    idempotency_key_hash: str
    request_id: str
    generation_policy_id: str
    prompt_template_id: str
    provider_reference: str
    model_reference: str
    model_version_reference: str
    pricing_snapshot_reference: str
    output_media_type: Literal["image/jpeg", "image/png", "image/webp"]
    output_width: int
    output_height: int
    output_max_bytes: int
    item_count: int
    requested_seeds: tuple[int | None, ...]
    currency: Literal["CNY", "USD"]
    hard_budget_micros: int
    per_item_ceiling_micros: int
    retry_ceiling: int
    concurrency_ceiling: int

    def __post_init__(self) -> None:
        if _DIGEST.fullmatch(self.idempotency_key_hash) is None:
            raise ValueError("idempotency key hash must be lowercase SHA-256")
        if not 8 <= len(self.request_id) <= 96 or any(
            character in self.request_id for character in "\r\n\0"
        ):
            raise ValueError("request id is outside the bounded safe shape")
        for authority_id in (self.generation_policy_id, self.prompt_template_id):
            if _ID.fullmatch(authority_id) is None:
                raise ValueError("authority id must be an opaque identifier")
        for reference in (
            self.provider_reference,
            self.model_reference,
            self.model_version_reference,
            self.pricing_snapshot_reference,
        ):
            if _REFERENCE.fullmatch(reference) is None:
                raise ValueError("generation reference must use the opaque syntax")
        if self.output_media_type not in SYNTHETIC_IMAGE_MEDIA_TYPES:
            raise ValueError("generation output media type is not allowed")
        if not 1 <= self.output_width <= 8192 or not 1 <= self.output_height <= 8192:
            raise ValueError("generation output dimensions are outside the boundary")
        if self.output_width * self.output_height > 40_000_000:
            raise ValueError("generation output pixel count is outside the boundary")
        if not 1 <= self.output_max_bytes <= 20 * 1024 * 1024:
            raise ValueError("generation output byte limit is outside the boundary")
        if not 1 <= self.item_count <= 10_000:
            raise ValueError("generation item count is outside the boundary")
        if len(self.requested_seeds) != self.item_count:
            raise ValueError("requested seeds must match the item count")
        if any(
            seed is not None and not 0 <= seed <= (1 << 63) - 1 for seed in self.requested_seeds
        ):
            raise ValueError("requested seed is outside the boundary")
        if self.currency not in {"CNY", "USD"}:
            raise ValueError("generation currency is not allowed")
        if self.hard_budget_micros < 0 or self.per_item_ceiling_micros < 0:
            raise ValueError("generation budget must be nonnegative")
        if self.per_item_ceiling_micros * self.item_count > self.hard_budget_micros:
            raise ValueError("item reservations exceed the hard budget")
        if not 0 <= self.retry_ceiling <= 20:
            raise ValueError("retry ceiling is outside the boundary")
        if not 1 <= self.concurrency_ceiling <= self.item_count:
            raise ValueError("concurrency ceiling is outside the boundary")


@dataclass(frozen=True)
class GenerationItemView:
    item_id: str
    batch_id: str
    job_id: str
    request_reference: str
    ordinal: int
    requested_seed: int | None
    reserved_budget_micros: int
    status: str
    result_code: str | None
    started_at: datetime | None
    finalized_at: datetime | None


@dataclass(frozen=True)
class GenerationBatchView:
    batch_id: str
    status: str
    item_count: int
    hard_budget_micros: int
    cancel_requested_at: datetime | None
    queued_at: datetime | None
    started_at: datetime | None
    finalized_at: datetime | None


@dataclass(frozen=True)
class GenerationBatchResult:
    batch: GenerationBatchView
    items: tuple[GenerationItemView, ...]
    created: bool


@dataclass(frozen=True)
class GenerationItemReservation:
    batch_id: str
    item_id: str
    job_id: str
    request_id: str
    request_reference: str
    attempt_id: str
    attempt_number: int
    lease_token: str
    lease_expires_at: datetime
    remaining_budget_micros: int


@dataclass(frozen=True)
class ProviderCostInput:
    item_id: str
    job_attempt_id: str
    event_kind: Literal["estimated", "final"]
    currency: Literal["CNY", "USD"]
    amount_micros: int
    pricing_snapshot_reference: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.item_id) is None or _ID.fullmatch(self.job_attempt_id) is None:
            raise ValueError("cost input identifiers must be opaque")
        if self.event_kind not in {"estimated", "final"}:
            raise ValueError("cost event kind is not allowed")
        if self.currency not in {"CNY", "USD"} or self.amount_micros < 0:
            raise ValueError("cost input is outside the allowed boundary")
        if _REFERENCE.fullmatch(self.pricing_snapshot_reference) is None:
            raise ValueError("pricing snapshot reference must be opaque")
