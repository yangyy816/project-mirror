from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from mirror_api.providers.base import PrivateUploadGrant

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


UploadIntentStatus = Literal[
    "awaiting_upload",
    "uploaded_unverified",
    "processing",
    "promoted",
    "rejected",
    "cancelled",
    "expired",
]


@dataclass(frozen=True)
class UploadDeclaration:
    content_type: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class UploadIntentView:
    intent_id: str
    status: UploadIntentStatus
    declaration: UploadDeclaration
    grant_expires_at: datetime
    uploaded_at: datetime | None
    cancelled_at: datetime | None
    expired_at: datetime | None


@dataclass(frozen=True)
class UploadIntentCreationResult:
    intent: UploadIntentView
    grant: PrivateUploadGrant | None
    created: bool


@dataclass(frozen=True)
class UploadCompletionResult:
    intent: UploadIntentView
    completed: bool


@dataclass(frozen=True)
class UploadCancellationResult:
    intent_id: str
    cancelled: bool
    cleanup_result: Literal["deleted", "not_found"]


class UploadIntentFailure(Exception):
    def __init__(self, code: str = "upload_intent_operation_rejected") -> None:
        super().__init__("upload intent operation was rejected")
        self.code = code
