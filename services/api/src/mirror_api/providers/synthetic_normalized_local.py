from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final, TypedDict, cast

from mirror_api.providers.base import (
    SyntheticNormalizedStorageWriteRequest,
    SyntheticNormalizedStoredImage,
    SyntheticStorageConflictError,
    SyntheticStorageOperationError,
)
from mirror_api.storage_keys import internal_synthetic_normalized_object_key

_CHUNK_BYTES: Final = 64 * 1024
_METADATA_NAME: Final = "metadata.json"
_PAYLOAD_NAME: Final = "payload"
_REFERENCE = re.compile(r"normalized-[0-9a-f]{53}\Z")


class _NormalizedMetadata(TypedDict):
    schema_version: str
    storage_reference: str
    storage_key: str
    sha256: str
    byte_size: int
    width: int
    height: int
    media_type: str
    normalizer_version: str
    normalizer_config_digest: str


class LocalSyntheticNormalizedStorageProvider:
    """Development/test canonical storage isolated from raw and user namespaces."""

    def __init__(self, *, root: Path) -> None:
        storage_root = root.absolute()
        if storage_root.is_symlink():
            raise ValueError("synthetic storage root cannot be a symlink")
        storage_root.mkdir(parents=True, exist_ok=True)
        self._root = storage_root.resolve(strict=True)
        self._normalized_root = self._root / "internal-synthetic" / "v1" / "normalized"
        self._prepare_directory(self._normalized_root)
        self._lock = asyncio.Lock()

    async def store_normalized_image_if_absent(
        self, *, request: SyntheticNormalizedStorageWriteRequest
    ) -> SyntheticNormalizedStoredImage:
        expected = self._metadata_for(request)
        target = self._target(request.storage_reference)
        async with self._lock:
            existing = await asyncio.to_thread(self._inspect_sync, request.storage_reference)
            if existing is not None:
                if existing != expected:
                    raise SyntheticStorageConflictError
                return existing
            temporary = self._normalized_root / f".part-{target.name}-{secrets.token_hex(8)}"
            try:
                await asyncio.to_thread(
                    self._write_temporary, temporary, expected, request.image.content
                )
                try:
                    await asyncio.to_thread(os.rename, temporary, target)
                except OSError:
                    existing = await asyncio.to_thread(
                        self._inspect_sync, request.storage_reference
                    )
                    if existing is None:
                        raise SyntheticStorageOperationError("synthetic_store_failed") from None
                    if existing != expected:
                        raise SyntheticStorageConflictError from None
                return expected
            finally:
                await asyncio.to_thread(self._remove_temporary, temporary)

    async def inspect_normalized_image(
        self, *, storage_reference: str
    ) -> SyntheticNormalizedStoredImage | None:
        self._validate_reference(storage_reference)
        return await asyncio.to_thread(self._inspect_sync, storage_reference)

    async def stream_normalized_image(self, *, storage_reference: str) -> AsyncIterator[bytes]:
        metadata = await self.inspect_normalized_image(storage_reference=storage_reference)
        if metadata is None:
            raise SyntheticStorageOperationError("synthetic_object_not_found")
        handle = await asyncio.to_thread(
            (self._target(storage_reference) / _PAYLOAD_NAME).open, "rb"
        )
        try:
            while True:
                chunk = await asyncio.to_thread(handle.read, _CHUNK_BYTES)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

    @staticmethod
    def _validate_reference(storage_reference: str) -> None:
        if _REFERENCE.fullmatch(storage_reference) is None:
            raise SyntheticStorageOperationError("invalid_storage_reference")

    def _target(self, storage_reference: str) -> Path:
        self._validate_reference(storage_reference)
        object_key = internal_synthetic_normalized_object_key(storage_reference)
        target = self._normalized_root / object_key.rsplit("/", 1)[-1]
        if target.parent != self._normalized_root:
            raise SyntheticStorageOperationError("invalid_storage_reference")
        return target

    @staticmethod
    def _metadata_for(
        request: SyntheticNormalizedStorageWriteRequest,
    ) -> SyntheticNormalizedStoredImage:
        image = request.image
        return SyntheticNormalizedStoredImage(
            storage_reference=request.storage_reference,
            storage_key=internal_synthetic_normalized_object_key(request.storage_reference),
            sha256=image.sha256,
            byte_size=image.byte_size,
            width=image.width,
            height=image.height,
            media_type=image.media_type,
            normalizer_version=request.normalizer_version,
            normalizer_config_digest=request.normalizer_config_digest,
        )

    @staticmethod
    def _prepare_directory(path: Path) -> None:
        pending: list[Path] = []
        current = path
        while not current.exists():
            pending.append(current)
            current = current.parent
        if current.is_symlink():
            raise ValueError("synthetic storage namespace cannot contain a symlink")
        for directory in reversed(pending):
            directory.mkdir()
            if directory.is_symlink():
                raise ValueError("synthetic storage namespace cannot contain a symlink")

    def _inspect_sync(self, storage_reference: str) -> SyntheticNormalizedStoredImage | None:
        target = self._target(storage_reference)
        if target.is_symlink():
            raise SyntheticStorageOperationError("synthetic_object_invalid")
        if not target.exists():
            return None
        if not target.is_dir():
            raise SyntheticStorageOperationError("synthetic_object_invalid")
        names = {entry.name for entry in target.iterdir()}
        if names != {_METADATA_NAME, _PAYLOAD_NAME}:
            raise SyntheticStorageOperationError("synthetic_object_invalid")
        metadata_path = target / _METADATA_NAME
        payload_path = target / _PAYLOAD_NAME
        if (
            metadata_path.is_symlink()
            or not metadata_path.is_file()
            or payload_path.is_symlink()
            or not payload_path.is_file()
        ):
            raise SyntheticStorageOperationError("synthetic_object_invalid")
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise SyntheticStorageOperationError("synthetic_metadata_invalid") from None
        expected_fields = set(_NormalizedMetadata.__annotations__)
        if not isinstance(raw, dict) or set(raw) != expected_fields:
            raise SyntheticStorageOperationError("synthetic_metadata_invalid")
        try:
            metadata = SyntheticNormalizedStoredImage(
                storage_reference=cast(str, raw["storage_reference"]),
                storage_key=cast(str, raw["storage_key"]),
                sha256=cast(str, raw["sha256"]),
                byte_size=cast(int, raw["byte_size"]),
                width=cast(int, raw["width"]),
                height=cast(int, raw["height"]),
                media_type="image/jpeg",
                normalizer_version=cast(str, raw["normalizer_version"]),
                normalizer_config_digest=cast(str, raw["normalizer_config_digest"]),
            )
        except (TypeError, ValueError):
            raise SyntheticStorageOperationError("synthetic_metadata_invalid") from None
        if (
            raw["schema_version"] != "mirror.synthetic-storage/normalized-object/v1"
            or raw["media_type"] != "image/jpeg"
            or metadata.storage_reference != storage_reference
            or metadata.storage_key != internal_synthetic_normalized_object_key(storage_reference)
        ):
            raise SyntheticStorageOperationError("synthetic_metadata_invalid")
        digest = hashlib.sha256()
        size = 0
        try:
            with payload_path.open("rb") as handle:
                while chunk := handle.read(_CHUNK_BYTES):
                    size += len(chunk)
                    digest.update(chunk)
        except OSError:
            raise SyntheticStorageOperationError("synthetic_object_invalid") from None
        if size != metadata.byte_size or digest.hexdigest() != metadata.sha256:
            raise SyntheticStorageOperationError("synthetic_integrity_mismatch")
        return metadata

    @staticmethod
    def _write_temporary(
        temporary: Path, metadata: SyntheticNormalizedStoredImage, payload: bytes
    ) -> None:
        temporary.mkdir()
        payload_path = temporary / _PAYLOAD_NAME
        metadata_path = temporary / _METADATA_NAME
        with payload_path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        document: _NormalizedMetadata = {
            "schema_version": "mirror.synthetic-storage/normalized-object/v1",
            "storage_reference": metadata.storage_reference,
            "storage_key": metadata.storage_key,
            "sha256": metadata.sha256,
            "byte_size": metadata.byte_size,
            "width": metadata.width,
            "height": metadata.height,
            "media_type": metadata.media_type,
            "normalizer_version": metadata.normalizer_version,
            "normalizer_config_digest": metadata.normalizer_config_digest,
        }
        with metadata_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _remove_temporary(self, temporary: Path) -> None:
        if temporary.parent != self._normalized_root or not temporary.name.startswith(".part-"):
            raise SyntheticStorageOperationError("synthetic_temporary_invalid")
        if temporary.is_symlink():
            raise SyntheticStorageOperationError("synthetic_temporary_invalid")
        if not temporary.exists():
            return
        if not temporary.is_dir():
            raise SyntheticStorageOperationError("synthetic_temporary_invalid")
        for name in (_PAYLOAD_NAME, _METADATA_NAME):
            path = temporary / name
            if path.exists():
                if path.is_symlink() or not path.is_file():
                    raise SyntheticStorageOperationError("synthetic_temporary_invalid")
                path.unlink()
        if any(temporary.iterdir()):
            raise SyntheticStorageOperationError("synthetic_temporary_invalid")
        temporary.rmdir()
