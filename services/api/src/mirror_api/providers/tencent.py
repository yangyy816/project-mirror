from __future__ import annotations

from typing import NoReturn


def _not_verified(capability: str) -> NoReturn:
    message = (
        f"Tencent {capability} adapter is a boundary only; "
        "capability and data terms are not verified"
    )
    raise NotImplementedError(message)


class TencentSmsProvider:
    async def send_verification_code(self, *, phone_hash: str, code: str) -> str:
        del phone_hash, code
        _not_verified("SMS")


class TencentCosProvider:
    async def create_private_upload_url(self, *, object_key: str) -> NoReturn:
        del object_key
        _not_verified("COS")


class TencentVisionCandidateProvider:
    async def inspect_synthetic_fixture(self, *, fixture_id: str) -> NoReturn:
        del fixture_id
        _not_verified("vision")


class TencentImageCandidateProvider:
    async def generate_synthetic_fixture(self, *, prompt_version: str) -> NoReturn:
        del prompt_version
        _not_verified("image generation/editing")


class TencentAgentCandidateProvider:
    async def create_plan(self, *, intent: str) -> NoReturn:
        del intent
        _not_verified("agent")
