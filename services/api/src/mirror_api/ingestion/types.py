from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

IngestionJobStatus = Literal["pending", "leased", "promoted", "rejected", "cancelled"]


class IngestionFailure(Exception):
    def __init__(self, code: str = "ingestion_operation_rejected") -> None:
        super().__init__("ingestion operation was rejected")
        self.code = code


@dataclass(frozen=True)
class IngestionJobView:
    job_id: str
    status: IngestionJobStatus
    result_code: str | None
    asset_id: str | None
    finalized_at: datetime | None


@dataclass(frozen=True)
class IngestionJobResult:
    job: IngestionJobView
    created: bool = False


@dataclass(frozen=True)
class IngestionJobClaim:
    job_id: str
    request_id: str
    lease_token: str
    attempt: int
    lease_expires_at: datetime
