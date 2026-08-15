from __future__ import annotations

import socket
from typing import cast

import pytest

from mirror_api.providers.base import (
    AgeAssuranceProvider,
    AgeAssuranceResult,
    AgeAssuranceStatus,
    SmsProvider,
)
from mirror_api.providers.mock import (
    LocalObjectStorageProvider,
    MockAgeAssuranceProvider,
    MockAgentProvider,
    MockImageGenerationProvider,
    MockSmsProvider,
    MockVisionProvider,
)
from mirror_api.providers.tencent import TencentAgeAssuranceCandidateProvider, TencentSmsProvider


@pytest.mark.asyncio
async def test_provider_fakes_are_deterministic_and_private() -> None:
    sms: SmsProvider = MockSmsProvider()
    storage = LocalObjectStorageProvider()
    vision = MockVisionProvider()
    image = MockImageGenerationProvider()
    agent = MockAgentProvider()

    assert await sms.send_verification_code(
        destination_phone="+8610000000000",
        verification_code="123456",
        request_reference="request-1",
    ) == (
        await sms.send_verification_code(
            destination_phone="+8610000000001",
            verification_code="different",
            request_reference="request-1",
        )
    )
    signed = await storage.create_private_upload_url(object_key="users/demo/assets/abc")
    assert "users/demo" not in signed.url
    assert signed.expires_in_seconds == 300
    assert (await vision.inspect_synthetic_fixture(fixture_id="fixture-1")).face_count == 1
    assert (await image.generate_synthetic_fixture(prompt_version="v1")).asset_reference.startswith(
        "fixture://"
    )
    assert (await agent.create_plan(intent="inspect")).operations == ("inspect_only",)


@pytest.mark.asyncio
async def test_mock_age_assurance_is_deterministic_and_minimal() -> None:
    credential = "test-credential-verified"
    rejected_credential = "test-credential-rejected"
    age: AgeAssuranceProvider = MockAgeAssuranceProvider(
        fixture_statuses={
            MockAgeAssuranceProvider.fixture_credential_key(credential): "verified",
            MockAgeAssuranceProvider.fixture_credential_key(rejected_credential): "not_verified",
        }
    )

    result = await age.verify_credential(credential=credential, request_reference="request-1")
    same_request_result = await age.verify_credential(
        credential="a-different-credential", request_reference="request-1"
    )

    assert result.status == "verified"
    assert (
        await age.verify_credential(credential=rejected_credential, request_reference="request-2")
    ).status == "not_verified"
    assert (
        await age.verify_credential(
            credential="unmapped-test-credential", request_reference="request-3"
        )
    ).status == "indeterminate"
    assert result.provider_reference == same_request_result.provider_reference
    assert result.provider_version == "mock-age-v1"
    assert result.policy_version == "mock-policy-v1"
    assert result.expires_at is None
    assert set(AgeAssuranceResult.__dataclass_fields__) == {
        "status",
        "provider_reference",
        "provider_version",
        "policy_version",
        "expires_at",
    }
    assert credential not in repr(vars(age))
    with pytest.raises(ValueError, match="age assurance status"):
        AgeAssuranceResult(
            status=cast(AgeAssuranceStatus, "unknown"),
            provider_reference="reference",
            provider_version="version",
            policy_version="policy",
        )


@pytest.mark.asyncio
async def test_unverified_tencent_candidates_fail_closed_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("provider attempted external network access")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentSmsProvider().send_verification_code(
            destination_phone="+8610000000000",
            verification_code="123456",
            request_reference="request-1",
        )

    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentAgeAssuranceCandidateProvider().verify_credential(
            credential="test-credential", request_reference="request-1"
        )
