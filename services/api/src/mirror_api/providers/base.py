from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


@dataclass(frozen=True)
class SignedObjectURL:
    url: str
    expires_in_seconds: int


@dataclass(frozen=True)
class VisionResult:
    face_count: int
    quality_score: float
    provider_run_id: str


@dataclass(frozen=True)
class GeneratedImage:
    asset_reference: str
    provider_run_id: str


@dataclass(frozen=True)
class AgentPlan:
    intent: str
    operations: tuple[str, ...]
    provider_run_id: str


@dataclass(frozen=True)
class PaymentCommand:
    provider: str
    operation: str
    idempotency_key_hash: str


AgeAssuranceStatus = Literal["verified", "not_verified", "indeterminate"]


@dataclass(frozen=True)
class AgeAssuranceResult:
    """The minimum age-assurance conclusion permitted outside a provider boundary."""

    status: AgeAssuranceStatus
    provider_reference: str
    provider_version: str
    policy_version: str
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status not in ("verified", "not_verified", "indeterminate"):
            raise ValueError(
                "age assurance status must be verified, not_verified, or indeterminate"
            )


class SmsProvider(Protocol):
    async def send_verification_code(
        self,
        *,
        destination_phone: str,
        verification_code: str,
        request_reference: str,
    ) -> str:
        """Send an OTP and return the provider message identifier."""


class AgeAssuranceProvider(Protocol):
    async def verify_credential(
        self, *, credential: str, request_reference: str
    ) -> AgeAssuranceResult:
        """Exchange an external credential for a minimum 18+ assurance result."""


class ObjectStorageProvider(Protocol):
    async def create_private_upload_url(self, *, object_key: str) -> SignedObjectURL: ...


class VisionProvider(Protocol):
    async def inspect_synthetic_fixture(self, *, fixture_id: str) -> VisionResult: ...


class ImageGenerationProvider(Protocol):
    async def generate_synthetic_fixture(self, *, prompt_version: str) -> GeneratedImage: ...


class AgentProvider(Protocol):
    async def create_plan(self, *, intent: str) -> AgentPlan: ...


class PaymentProvider(Protocol):
    async def execute(self, command: PaymentCommand) -> str: ...
