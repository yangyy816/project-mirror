from __future__ import annotations

import hashlib
from collections.abc import Mapping

from mirror_api.providers.base import (
    AgeAssuranceResult,
    AgeAssuranceStatus,
    AgentPlan,
    GeneratedImage,
    SignedObjectURL,
    VisionResult,
)
from mirror_api.security import validate_storage_key


def _stable_id(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}:{value}".encode()).hexdigest()[:24]


class MockSmsProvider:
    """Development provider that records no phone number or verification code."""

    async def send_verification_code(
        self,
        *,
        destination_phone: str,
        verification_code: str,
        request_reference: str,
    ) -> str:
        del destination_phone, verification_code
        return f"local-sms-{_stable_id('sms', request_reference)}"


class MockAgeAssuranceProvider:
    """Deterministic test-only age provider that retains no credential plaintext."""

    def __init__(self, *, fixture_statuses: Mapping[str, AgeAssuranceStatus] | None = None) -> None:
        self._fixture_statuses = dict(fixture_statuses or {})

    @staticmethod
    def fixture_credential_key(credential: str) -> str:
        """Create a non-plaintext key for an explicit test fixture mapping."""

        return _stable_id("age-credential", credential)

    async def verify_credential(
        self, *, credential: str, request_reference: str
    ) -> AgeAssuranceResult:
        status = self._fixture_statuses.get(
            self.fixture_credential_key(credential), "indeterminate"
        )
        return AgeAssuranceResult(
            status=status,
            provider_reference=f"mock-age-{_stable_id('age-reference', request_reference)}",
            provider_version="mock-age-v1",
            policy_version="mock-policy-v1",
        )


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
