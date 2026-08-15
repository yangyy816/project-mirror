from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import secrets
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

from mirror_api.providers.base import (
    DeleteResult,
    PrivateUploadGrant,
    QuarantineObjectMetadata,
    SanitizedObjectConflictError,
    SanitizedObjectMetadata,
)
from mirror_api.security import ALLOWED_MIME_TYPES, MAX_UPLOAD_BYTES, validate_storage_key

QUARANTINE_KEY = re.compile(r"^quarantine/v1/[0-9a-f]{64}$")
SANITIZED_KEY = re.compile(r"^sanitized/v1/[0-9a-f]{32}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
UPLOAD_AUTHORIZATION_HEADER = "X-Mirror-Upload-Authorization"
UPLOAD_CHECKSUM_HEADER = "X-Content-SHA256"
STORAGE_CHUNK_BYTES = 64 * 1024


def sanitized_object_key_for_job(job_id: str) -> str:
    """Derive the only canonical sanitized storage key from an opaque job id."""
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("job id must use the opaque 32-character syntax")
    return f"sanitized/v1/{job_id}"


class LocalStorageOperationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__("local private upload was rejected")
        self.reason = reason


@dataclass
class _PendingGrant:
    object_key: str
    content_type: str
    content_length: int
    checksum_sha256: str
    proof_digest: bytes
    expires_at: datetime
    consumed: bool = False


class LocalObjectStorageProvider:
    """Non-production, write-only quarantine storage for synthetic fixtures."""

    def __init__(
        self,
        *,
        root: Path,
        base_url: str = "http://127.0.0.1:8000",
        ttl_seconds: int = 300,
        clock: Callable[[], datetime] | None = None,
        proof_key: bytes | None = None,
    ) -> None:
        raw_root = root.absolute()
        if raw_root.is_symlink():
            raise ValueError("local storage root cannot be a symlink")
        raw_root.mkdir(parents=True, exist_ok=True)
        self._root = raw_root.resolve(strict=True)
        if ttl_seconds < 1 or ttl_seconds > 900:
            raise ValueError("local upload grant TTL must be between 1 and 900 seconds")
        self._base_url = base_url.rstrip("/")
        self._ttl_seconds = ttl_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._proof_key = proof_key or secrets.token_bytes(32)
        self._grants: dict[str, _PendingGrant] = {}
        self._metadata: dict[str, QuarantineObjectMetadata] = {}
        self._lock = asyncio.Lock()

    async def create_private_upload_grant(
        self,
        *,
        object_key: str,
        content_type: str,
        content_length: int,
        checksum_sha256: str,
    ) -> PrivateUploadGrant:
        self._validate_declaration(
            object_key=object_key,
            content_type=content_type,
            content_length=content_length,
            checksum_sha256=checksum_sha256,
        )
        self._resolve_object_path(object_key)
        grant_id = secrets.token_urlsafe(18)
        proof = secrets.token_urlsafe(32)
        expires_at = self._clock() + timedelta(seconds=self._ttl_seconds)
        state = _PendingGrant(
            object_key=object_key,
            content_type=content_type,
            content_length=content_length,
            checksum_sha256=checksum_sha256,
            proof_digest=self._proof_digest(grant_id, proof),
            expires_at=expires_at,
        )
        async with self._lock:
            self._grants[grant_id] = state
        headers = MappingProxyType(
            {
                "Content-Type": content_type,
                "Content-Length": str(content_length),
                UPLOAD_CHECKSUM_HEADER: checksum_sha256,
                UPLOAD_AUTHORIZATION_HEADER: proof,
            }
        )
        return PrivateUploadGrant(
            method="PUT",
            url=f"{self._base_url}/_local/private-upload/{grant_id}",
            required_headers=headers,
            expires_at=expires_at,
        )

    async def receive_private_upload(
        self,
        *,
        grant_id: str,
        authorization: str,
        content_type: str,
        content_length: int,
        checksum_sha256: str,
        body: AsyncIterable[bytes],
    ) -> None:
        state = await self._consume_grant(grant_id=grant_id, authorization=authorization)
        if content_type != state.content_type:
            raise LocalStorageOperationError("content_type_mismatch")
        if content_length != state.content_length:
            raise LocalStorageOperationError("content_length_mismatch")
        if not hmac.compare_digest(checksum_sha256, state.checksum_sha256):
            raise LocalStorageOperationError("checksum_header_mismatch")

        target = self._resolve_object_path(state.object_key)
        temporary = self._resolve_temporary_path(grant_id)
        await asyncio.to_thread(self._create_empty_file, temporary)
        digest = hashlib.sha256()
        received = 0
        published = False
        try:
            async for chunk in body:
                if not isinstance(chunk, bytes):
                    raise LocalStorageOperationError("invalid_body_chunk")
                received += len(chunk)
                if received > state.content_length or received > MAX_UPLOAD_BYTES:
                    raise LocalStorageOperationError("body_too_large")
                digest.update(chunk)
                if chunk:
                    await asyncio.to_thread(self._append_chunk, temporary, chunk)
            if received != state.content_length:
                raise LocalStorageOperationError("body_too_short")
            actual_sha256 = digest.hexdigest()
            if not hmac.compare_digest(actual_sha256, state.checksum_sha256):
                raise LocalStorageOperationError("checksum_mismatch")
            await asyncio.to_thread(self._publish_without_overwrite, temporary, target)
            published = True
            uploaded_at = self._clock()
            self._metadata[state.object_key] = QuarantineObjectMetadata(
                byte_size=received,
                content_type=state.content_type,
                sha256=actual_sha256,
                etag=actual_sha256,
                uploaded_at=uploaded_at,
            )
        finally:
            if not published:
                await asyncio.to_thread(temporary.unlink, missing_ok=True)

    async def inspect_quarantine_object(
        self, *, object_key: str
    ) -> QuarantineObjectMetadata | None:
        target = self._resolve_object_path(object_key)
        metadata = self._metadata.get(object_key)
        if metadata is None or not await asyncio.to_thread(target.is_file):
            return None
        return metadata

    async def delete_quarantine_object(self, *, object_key: str) -> DeleteResult:
        target = self._resolve_object_path(object_key)
        existed = await asyncio.to_thread(target.is_file)
        await asyncio.to_thread(target.unlink, missing_ok=True)
        self._metadata.pop(object_key, None)
        return "deleted" if existed else "not_found"

    async def stream_quarantine_object(self, *, object_key: str) -> AsyncIterator[bytes]:
        """Read only a server-issued quarantine key in bounded chunks."""
        target = self._resolve_object_path(object_key)
        if not await asyncio.to_thread(target.is_file):
            raise LocalStorageOperationError("quarantine_not_found")
        handle = await asyncio.to_thread(target.open, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(handle.read, STORAGE_CHUNK_BYTES)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

    async def create_sanitized_object_if_absent(
        self,
        *,
        object_key: str,
        content_type: str,
        content_length: int,
        checksum_sha256: str,
        body: AsyncIterable[bytes],
    ) -> SanitizedObjectMetadata:
        self._validate_sanitized_declaration(
            object_key=object_key,
            content_type=content_type,
            content_length=content_length,
            checksum_sha256=checksum_sha256,
        )
        target = self._resolve_sanitized_path(object_key)
        temporary = self._resolve_temporary_path("sanitized")
        await asyncio.to_thread(self._create_empty_file, temporary)
        digest = hashlib.sha256()
        received = 0
        published = False
        try:
            async for chunk in body:
                if not isinstance(chunk, bytes):
                    raise LocalStorageOperationError("invalid_sanitized_body")
                received += len(chunk)
                if received > content_length or received > MAX_UPLOAD_BYTES:
                    raise LocalStorageOperationError("sanitized_body_too_large")
                digest.update(chunk)
                if chunk:
                    await asyncio.to_thread(self._append_chunk, temporary, chunk)
            if received != content_length:
                raise LocalStorageOperationError("sanitized_body_length_mismatch")
            if not hmac.compare_digest(digest.hexdigest(), checksum_sha256):
                raise LocalStorageOperationError("sanitized_checksum_mismatch")
            try:
                await asyncio.to_thread(self._publish_without_overwrite, temporary, target)
                published = True
            except LocalStorageOperationError as exc:
                if exc.reason != "object_already_exists":
                    raise
                existing = await self.inspect_sanitized_object(object_key=object_key)
                if existing is None or not (
                    existing.byte_size == content_length
                    and hmac.compare_digest(existing.sha256, checksum_sha256)
                    and existing.content_type == content_type
                ):
                    raise SanitizedObjectConflictError() from exc
                return existing
            return SanitizedObjectMetadata(
                byte_size=content_length,
                content_type="image/jpeg",
                sha256=checksum_sha256,
            )
        finally:
            if not published:
                await asyncio.to_thread(temporary.unlink, missing_ok=True)

    async def inspect_sanitized_object(self, *, object_key: str) -> SanitizedObjectMetadata | None:
        target = self._resolve_sanitized_path(object_key)
        if not await asyncio.to_thread(target.is_file):
            return None
        byte_size, checksum = await asyncio.to_thread(self._file_size_and_sha256, target)
        if byte_size <= 0 or byte_size > MAX_UPLOAD_BYTES:
            raise LocalStorageOperationError("invalid_sanitized_object")
        return SanitizedObjectMetadata(
            byte_size=byte_size,
            content_type="image/jpeg",
            sha256=checksum,
        )

    async def delete_sanitized_object(self, *, object_key: str) -> DeleteResult:
        target = self._resolve_sanitized_path(object_key)
        existed = await asyncio.to_thread(target.is_file)
        await asyncio.to_thread(target.unlink, missing_ok=True)
        return "deleted" if existed else "not_found"

    async def _consume_grant(self, *, grant_id: str, authorization: str) -> _PendingGrant:
        async with self._lock:
            state = self._grants.get(grant_id)
            if state is None:
                raise LocalStorageOperationError("unknown_grant")
            if state.consumed:
                raise LocalStorageOperationError("grant_replayed")
            if self._clock() >= state.expires_at:
                state.consumed = True
                raise LocalStorageOperationError("grant_expired")
            if not hmac.compare_digest(
                self._proof_digest(grant_id, authorization), state.proof_digest
            ):
                state.consumed = True
                raise LocalStorageOperationError("invalid_authorization")
            state.consumed = True
            return state

    def _validate_declaration(
        self,
        *,
        object_key: str,
        content_type: str,
        content_length: int,
        checksum_sha256: str,
    ) -> None:
        self._validate_quarantine_key(object_key)
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError("unsupported declared content type")
        if content_length <= 0 or content_length > MAX_UPLOAD_BYTES:
            raise ValueError("declared content length is outside the allowed boundary")
        if not SHA256_HEX.fullmatch(checksum_sha256):
            raise ValueError("declared checksum must be lowercase SHA-256")

    def _validate_sanitized_declaration(
        self,
        *,
        object_key: str,
        content_type: str,
        content_length: int,
        checksum_sha256: str,
    ) -> None:
        self._validate_sanitized_key(object_key)
        if content_type != "image/jpeg":
            raise ValueError("sanitized objects must use canonical JPEG")
        if content_length <= 0 or content_length > MAX_UPLOAD_BYTES:
            raise ValueError("sanitized content length is outside the allowed boundary")
        if not SHA256_HEX.fullmatch(checksum_sha256):
            raise ValueError("sanitized checksum must be lowercase SHA-256")

    @staticmethod
    def _validate_quarantine_key(object_key: str) -> None:
        validate_storage_key(object_key)
        if not QUARANTINE_KEY.fullmatch(object_key):
            raise ValueError("object key must use the opaque quarantine syntax")

    @staticmethod
    def _validate_sanitized_key(object_key: str) -> None:
        validate_storage_key(object_key)
        if not SANITIZED_KEY.fullmatch(object_key):
            raise ValueError("object key must use the opaque sanitized syntax")

    def _resolve_object_path(self, object_key: str) -> Path:
        self._validate_quarantine_key(object_key)
        candidate = self._root.joinpath(*object_key.split("/"))
        self._reject_symlink_components(candidate.parent)
        if candidate.is_symlink():
            raise ValueError("symlinks are forbidden in local quarantine storage")
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self._root):
            raise ValueError("object path escapes the local quarantine root")
        return resolved

    def _resolve_sanitized_path(self, object_key: str) -> Path:
        self._validate_sanitized_key(object_key)
        candidate = self._root.joinpath(*object_key.split("/"))
        self._reject_symlink_components(candidate.parent)
        if candidate.is_symlink():
            raise ValueError("symlinks are forbidden in local sanitized storage")
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self._root):
            raise ValueError("object path escapes the local sanitized root")
        return resolved

    def _resolve_temporary_path(self, grant_id: str) -> Path:
        temporary_root = self._root / ".tmp"
        self._reject_symlink_components(temporary_root)
        temporary_root.mkdir(parents=True, exist_ok=True)
        self._reject_symlink_components(temporary_root)
        return temporary_root / f"{grant_id}.{secrets.token_hex(8)}.part"

    def _reject_symlink_components(self, path: Path) -> None:
        current = self._root
        if current.is_symlink() or current.resolve(strict=True) != self._root:
            raise ValueError("local storage root changed unexpectedly")
        relative = path.relative_to(self._root)
        for part in relative.parts:
            current /= part
            if current.exists() and current.is_symlink():
                raise ValueError("symlinks are forbidden in local quarantine storage")

    def _proof_digest(self, grant_id: str, proof: str) -> bytes:
        return hmac.digest(self._proof_key, f"{grant_id}:{proof}".encode(), "sha256")

    @staticmethod
    def _create_empty_file(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb"):
            pass

    @staticmethod
    def _append_chunk(path: Path, chunk: bytes) -> None:
        with path.open("ab") as handle:
            handle.write(chunk)

    @staticmethod
    def _file_size_and_sha256(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        byte_size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(STORAGE_CHUNK_BYTES):
                byte_size += len(chunk)
                digest.update(chunk)
        return byte_size, digest.hexdigest()

    def _publish_without_overwrite(self, temporary: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        self._reject_symlink_components(target.parent)
        if target.resolve(strict=False) != target:
            raise LocalStorageOperationError("unsafe_storage_path")
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise LocalStorageOperationError("object_already_exists") from exc
        temporary.unlink()
