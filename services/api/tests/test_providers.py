from __future__ import annotations

import pytest

from mirror_api.providers.mock import (
    LocalObjectStorageProvider,
    MockAgentProvider,
    MockImageGenerationProvider,
    MockSmsProvider,
    MockVisionProvider,
)


@pytest.mark.asyncio
async def test_provider_fakes_are_deterministic_and_private() -> None:
    sms = MockSmsProvider()
    storage = LocalObjectStorageProvider()
    vision = MockVisionProvider()
    image = MockImageGenerationProvider()
    agent = MockAgentProvider()

    assert await sms.send_verification_code(phone_hash="hash", code="123456") == (
        await sms.send_verification_code(phone_hash="hash", code="different")
    )
    signed = await storage.create_private_upload_url(object_key="users/demo/assets/abc")
    assert "users/demo" not in signed.url
    assert signed.expires_in_seconds == 300
    assert (await vision.inspect_synthetic_fixture(fixture_id="fixture-1")).face_count == 1
    assert (await image.generate_synthetic_fixture(prompt_version="v1")).asset_reference.startswith(
        "fixture://"
    )
    assert (await agent.create_plan(intent="inspect")).operations == ("inspect_only",)
