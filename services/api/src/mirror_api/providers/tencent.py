from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from typing import Literal, NoReturn

from mirror_api.providers.base import (
    DataExportObjectMetadata,
    DeleteResult,
    SanitizedObjectMetadata,
    SyntheticGenerationRequest,
    SyntheticStorageWriteRequest,
    SyntheticVisionRequest,
)
from mirror_api.synthetic_dataset.prompt_material import EphemeralPrompt


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


class TencentSyntheticObjectStorageCandidateProvider:
    async def store_generated_image_if_absent(
        self, *, request: SyntheticStorageWriteRequest
    ) -> NoReturn:
        del request
        _not_verified("synthetic object storage")

    async def inspect_generated_image(self, *, storage_reference: str) -> NoReturn:
        del storage_reference
        _not_verified("synthetic object storage")

    async def stream_generated_image(self, *, storage_reference: str) -> AsyncIterator[bytes]:
        del storage_reference
        _not_verified("synthetic object storage")
        yield b""  # pragma: no cover

    async def delete_generated_image(self, *, storage_reference: str) -> NoReturn:
        del storage_reference
        _not_verified("synthetic object storage")


class TencentVisionCandidateProvider:
    async def inspect_synthetic(self, *, request: SyntheticVisionRequest) -> NoReturn:
        del request
        _not_verified("vision")


class TencentImageCandidateProvider:
    async def generate_synthetic(
        self, *, request: SyntheticGenerationRequest, prompt: EphemeralPrompt
    ) -> NoReturn:
        del request, prompt
        _not_verified("image generation/editing")


class TencentAgentCandidateProvider:
    async def create_plan(self, *, intent: str) -> NoReturn:
        del intent
        _not_verified("agent")
