from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final, Literal, TypedDict, cast

from mirror_api.providers.base import (
    SyntheticStorageConflictError,
    SyntheticStorageOperationError,
)
from mirror_api.storage_keys import internal_synthetic_variant_object_key
from mirror_api.synthetic_dataset.variant_storage import (
    VariantStorageWriteRequest,
    VariantStoredImage,
)

_CHUNK_BYTES: Final = 64 * 1024
_METADATA_NAME: Final = "metadata.json"
_PAYLOAD_NAME: Final = "payload"
_REFERENCE = re.compile(r"variant-[0-9a-f]{56}\Z")


class _VariantMetadata(TypedDict):
    schema_version: str
    storage_reference: str
    storage_key: str
    transform_run_reference: str
    specification_digest: str
    sha256: str
    byte_size: int
    width: int
    height: int
    changed_pixel_count: int
    runtime_version: str
    runtime_manifest_digest: str
    warp_plan_digest: str
    output_policy_version: str
    receipt_digest: str
    media_type: str


class LocalSyntheticVariantStorageProvider:
    """Create-if-absent private variant objects, isolated from raw/normalized/user data."""

    def __init__(self, *, root: Path) -> None:
        storage_root = root.absolute()
        if storage_root.is_symlink():
            raise ValueError("synthetic storage root cannot be a symlink")
        storage_root.mkdir(parents=True, exist_ok=True)
        self._root = storage_root.resolve(strict=True)
        self._variant_root = self._root / "internal-synthetic" / "v1" / "variants"
        self._prepare_directory(self._variant_root)
        self._lock = asyncio.Lock()

    async def store_variant_if_absent(
        self, *, request: VariantStorageWriteRequest
    ) -> VariantStoredImage:
        expected = self._receipt_for(request)
        target = self._target(request.storage_reference)
        async with self._lock:
            existing = await asyncio.to_thread(self._inspect_sync, request.storage_reference)
            if existing is not None:
                if existing != expected:
                    raise SyntheticStorageConflictError
                return existing
            temporary = self._variant_root / f".part-{target.name}-{secrets.token_hex(8)}"
            try:
                await asyncio.to_thread(
                    self._write_temporary, temporary, expected, request.result.content
                )
                try:
                    await asyncio.to_thread(os.rename, temporary, target)
                except OSError:
                    existing = await asyncio.to_thread(
                        self._inspect_sync, request.storage_reference
                    )
                    if existing is None:
                        raise SyntheticStorageOperationError("variant_store_failed") from None
                    if existing != expected:
                        raise SyntheticStorageConflictError from None
                return expected
            finally:
                await asyncio.to_thread(self._remove_temporary, temporary)

    async def inspect_variant(self, *, storage_reference: str) -> VariantStoredImage | None:
        self._validate_reference(storage_reference)
        return await asyncio.to_thread(self._inspect_sync, storage_reference)

    async def stream_variant(self, *, storage_reference: str) -> AsyncIterator[bytes]:
        metadata = await self.inspect_variant(storage_reference=storage_reference)
        if metadata is None:
            raise SyntheticStorageOperationError("variant_object_not_found")
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

    async def delete_variant(self, *, storage_reference: str) -> Literal["deleted", "not_found"]:
        self._validate_reference(storage_reference)
        target = self._target(storage_reference)
        async with self._lock:
            if not target.exists():
                return "not_found"
            await asyncio.to_thread(self._remove_target, target)
            return "deleted"

    @staticmethod
    def _validate_reference(storage_reference: str) -> None:
        if _REFERENCE.fullmatch(storage_reference) is None:
            raise SyntheticStorageOperationError("invalid_variant_reference")

    def _target(self, storage_reference: str) -> Path:
        self._validate_reference(storage_reference)
        object_key = internal_synthetic_variant_object_key(storage_reference)
        target = self._variant_root / object_key.rsplit("/", 1)[-1]
        if target.parent != self._variant_root:
            raise SyntheticStorageOperationError("invalid_variant_reference")
        return target

    @staticmethod
    def _receipt_for(request: VariantStorageWriteRequest) -> VariantStoredImage:
        return VariantStoredImage.create(
            storage_reference=request.storage_reference,
            storage_key=internal_synthetic_variant_object_key(request.storage_reference),
            transform_run_reference=request.transform_run_reference,
            specification_digest=request.specification_digest,
            result=request.result,
            output_policy_version=request.output_policy_version,
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

    def _inspect_sync(self, storage_reference: str) -> VariantStoredImage | None:
        target = self._target(storage_reference)
        if target.is_symlink():
            raise SyntheticStorageOperationError("variant_object_invalid")
        if not target.exists():
            return None
        if not target.is_dir() or {entry.name for entry in target.iterdir()} != {
            _METADATA_NAME,
            _PAYLOAD_NAME,
        }:
            raise SyntheticStorageOperationError("variant_object_invalid")
        metadata_path = target / _METADATA_NAME
        payload_path = target / _PAYLOAD_NAME
        if any(path.is_symlink() or not path.is_file() for path in (metadata_path, payload_path)):
            raise SyntheticStorageOperationError("variant_object_invalid")
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise SyntheticStorageOperationError("variant_metadata_invalid") from None
        if not isinstance(raw, dict) or set(raw) != set(_VariantMetadata.__annotations__):
            raise SyntheticStorageOperationError("variant_metadata_invalid")
        try:
            receipt = VariantStoredImage(
                storage_reference=cast(str, raw["storage_reference"]),
                storage_key=cast(str, raw["storage_key"]),
                transform_run_reference=cast(str, raw["transform_run_reference"]),
                specification_digest=cast(str, raw["specification_digest"]),
                sha256=cast(str, raw["sha256"]),
                byte_size=cast(int, raw["byte_size"]),
                width=cast(int, raw["width"]),
                height=cast(int, raw["height"]),
                changed_pixel_count=cast(int, raw["changed_pixel_count"]),
                runtime_version=cast(str, raw["runtime_version"]),
                runtime_manifest_digest=cast(str, raw["runtime_manifest_digest"]),
                warp_plan_digest=cast(str, raw["warp_plan_digest"]),
                output_policy_version=cast(str, raw["output_policy_version"]),
                receipt_digest=cast(str, raw["receipt_digest"]),
                media_type="image/jpeg",
                schema_version=cast(str, raw["schema_version"]),
            )
        except (TypeError, ValueError):
            raise SyntheticStorageOperationError("variant_metadata_invalid") from None
        if (
            raw["media_type"] != "image/jpeg"
            or receipt.storage_reference != storage_reference
            or receipt.storage_key != internal_synthetic_variant_object_key(storage_reference)
        ):
            raise SyntheticStorageOperationError("variant_metadata_invalid")
        digest = hashlib.sha256()
        size = 0
        try:
            with payload_path.open("rb") as handle:
                while chunk := handle.read(_CHUNK_BYTES):
                    size += len(chunk)
                    digest.update(chunk)
        except OSError:
            raise SyntheticStorageOperationError("variant_object_invalid") from None
        if size != receipt.byte_size or digest.hexdigest() != receipt.sha256:
            raise SyntheticStorageOperationError("variant_integrity_mismatch")
        return receipt

    @staticmethod
    def _write_temporary(temporary: Path, receipt: VariantStoredImage, payload: bytes) -> None:
        temporary.mkdir()
        with (temporary / _PAYLOAD_NAME).open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        document: _VariantMetadata = {
            "schema_version": receipt.schema_version,
            "storage_reference": receipt.storage_reference,
            "storage_key": receipt.storage_key,
            "transform_run_reference": receipt.transform_run_reference,
            "specification_digest": receipt.specification_digest,
            "sha256": receipt.sha256,
            "byte_size": receipt.byte_size,
            "width": receipt.width,
            "height": receipt.height,
            "changed_pixel_count": receipt.changed_pixel_count,
            "runtime_version": receipt.runtime_version,
            "runtime_manifest_digest": receipt.runtime_manifest_digest,
            "warp_plan_digest": receipt.warp_plan_digest,
            "output_policy_version": receipt.output_policy_version,
            "receipt_digest": receipt.receipt_digest,
            "media_type": receipt.media_type,
        }
        with (temporary / _METADATA_NAME).open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _remove_temporary(self, temporary: Path) -> None:
        if temporary.parent != self._variant_root or not temporary.name.startswith(".part-"):
            raise SyntheticStorageOperationError("variant_temporary_invalid")
        if not temporary.exists():
            return
        self._remove_target(temporary)

    def _remove_target(self, target: Path) -> None:
        if target.parent != self._variant_root or target.is_symlink() or not target.is_dir():
            raise SyntheticStorageOperationError("variant_object_invalid")
        names = {entry.name for entry in target.iterdir()}
        if not names.issubset({_PAYLOAD_NAME, _METADATA_NAME}):
            raise SyntheticStorageOperationError("variant_object_invalid")
        for name in (_PAYLOAD_NAME, _METADATA_NAME):
            path = target / name
            if path.exists():
                if path.is_symlink() or not path.is_file():
                    raise SyntheticStorageOperationError("variant_object_invalid")
                path.unlink()
        target.rmdir()
