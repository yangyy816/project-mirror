from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from typing import Literal, NoReturn

from mirror_api.providers.base import (
    DataExportObjectMetadata,
    DeleteResult,
    SanitizedObjectMetadata,
)


def _not_verified(capability: str) -> NoReturn:
    message = (
        f"Tencent {capability} adapter is a boundary only; "
        "capability and data terms are not verified"
    )
    raise NotImplementedError(message)


class TencentSmsProvider:
    async def send_verification_code(
        self,
        *,
        destination_phone: str,
        verification_code: str,
        request_reference: str,
    ) -> str:
        del destination_phone, verification_code, request_reference
        _not_verified("SMS")


class TencentAgeAssuranceCandidateProvider:
    async def verify_credential(self, *, credential: str, request_reference: str) -> NoReturn:
        del credential, request_reference
        _not_verified("age assurance")


class TencentCosProvider:
    async def create_private_download_grant(
        self, *, object_key: str, request_reference: str
    ) -> NoReturn:
        del object_key, request_reference
        _not_verified("COS private download")

    async def create_private_upload_grant(
        self,
        *,
        object_key: str,
        content_type: str,
        content_length: int,
        checksum_sha256: str,
    ) -> NoReturn:
        del object_key, content_type, content_length, checksum_sha256
        _not_verified("COS")

    async def inspect_quarantine_object(self, *, object_key: str) -> NoReturn:
        del object_key
        _not_verified("COS")

    async def delete_quarantine_object(self, *, object_key: str) -> NoReturn:
        del object_key
        _not_verified("COS")

    async def stream_quarantine_object(self, *, object_key: str) -> AsyncIterator[bytes]:
        del object_key
        _not_verified("COS")
        yield b""  # pragma: no cover

    async def create_sanitized_object_if_absent(
        self,
        *,
        object_key: str,
        content_type: Literal["image/jpeg"],
        content_length: int,
        checksum_sha256: str,
        body: AsyncIterable[bytes],
    ) -> NoReturn:
        del object_key, content_type, content_length, checksum_sha256, body
        _not_verified("COS")

    async def inspect_sanitized_object(self, *, object_key: str) -> SanitizedObjectMetadata | None:
        del object_key
        _not_verified("COS")

    async def stream_sanitized_object(self, *, object_key: str) -> AsyncIterator[bytes]:
        del object_key
        _not_verified("COS")
        yield b""  # pragma: no cover

    async def delete_sanitized_object(self, *, object_key: str) -> DeleteResult:
        del object_key
        _not_verified("COS")

    async def create_data_export_if_absent(
        self,
        *,
        object_key: str,
        content_length: int,
        checksum_sha256: str,
        body: AsyncIterable[bytes],
    ) -> NoReturn:
        del object_key, content_length, checksum_sha256, body
        _not_verified("COS private data export")

    async def inspect_data_export(self, *, object_key: str) -> DataExportObjectMetadata | None:
        del object_key
        _not_verified("COS private data export")

    async def stream_data_export(self, *, object_key: str) -> AsyncIterator[bytes]:
        del object_key
        _not_verified("COS private data export")
        yield b""  # pragma: no cover

    async def delete_data_export(self, *, object_key: str) -> DeleteResult:
        del object_key
        _not_verified("COS private data export")


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
