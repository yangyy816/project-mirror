from __future__ import annotations

import hashlib

from mirror_api.providers.base import AgentPlan, GeneratedImage, SignedObjectURL, VisionResult
from mirror_api.security import validate_storage_key


def _stable_id(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}:{value}".encode()).hexdigest()[:24]


class MockSmsProvider:
    """Development provider that records no phone number or verification code."""

    async def send_verification_code(self, *, phone_hash: str, code: str) -> str:
        del code
        return f"local-sms-{_stable_id('sms', phone_hash)}"


class LocalObjectStorageProvider:
    def __init__(self, *, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds

    async def create_private_upload_url(self, *, object_key: str) -> SignedObjectURL:
        safe_key = validate_storage_key(object_key)
        token = _stable_id("object", safe_key)
        return SignedObjectURL(
            url=f"http://127.0.0.1:8000/_local/private-upload/{token}",
            expires_in_seconds=self.ttl_seconds,
        )


class MockVisionProvider:
    async def inspect_synthetic_fixture(self, *, fixture_id: str) -> VisionResult:
        return VisionResult(
            face_count=1,
            quality_score=0.9,
            provider_run_id=f"mock-vision-{_stable_id('vision', fixture_id)}",
        )


class MockImageGenerationProvider:
    async def generate_synthetic_fixture(self, *, prompt_version: str) -> GeneratedImage:
        run_id = f"mock-image-{_stable_id('image', prompt_version)}"
        return GeneratedImage(asset_reference=f"fixture://{run_id}", provider_run_id=run_id)


class MockAgentProvider:
    async def create_plan(self, *, intent: str) -> AgentPlan:
        return AgentPlan(
            intent=intent,
            operations=("inspect_only",),
            provider_run_id=f"mock-agent-{_stable_id('agent', intent)}",
        )
