from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ConsentStatus = Literal["granted", "withdrawn", "missing"]
ConsentMissingReason = Literal["absent", "expired", "version_mismatch"]


@dataclass(frozen=True)
class ConsentRequirement:
    consent_type: str
    purpose_code: str
    purpose_version: str
    policy_code: str
    policy_version: str
    policy_digest: str
    operations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.operations or len(self.operations) != len(set(self.operations)):
            raise ValueError("consent operations must be non-empty and unique")
        if len(self.policy_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.policy_digest
        ):
            raise ValueError("consent policy digest must be lowercase SHA-256")

    @property
    def scope(self) -> dict[str, object]:
        return {"operations": list(self.operations)}


@dataclass(frozen=True)
class ConsentState:
    status: ConsentStatus
    requirement: ConsentRequirement
    grant_id: str | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    missing_reason: ConsentMissingReason | None = None


@dataclass(frozen=True)
class ConsentGrantResult:
    grant_id: str
    granted_at: datetime
    expires_at: datetime | None
    created: bool


@dataclass(frozen=True)
class ConsentWithdrawalResult:
    withdrawal_id: str
    grant_id: str
    withdrawn_at: datetime
    created: bool


class ConsentFailure(Exception):
    def __init__(self, code: str = "consent_operation_rejected") -> None:
        super().__init__("consent operation was rejected")
        self.code = code
