from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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


class SmsProvider(Protocol):
    async def send_verification_code(self, *, phone_hash: str, code: str) -> str: ...


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
