"""Strict localhost-only byte loader for synthetic D07 source Assets."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_DIRECTORY_KEY: Final = re.compile(
    r"^(?:"
    r"internal-synthetic/v1/(?:normalized|variants)/[0-9a-f]{64}|"
    r"demo-original/v1/[0-9a-f]{32}/[0-9a-f]{64}|"
    r"demo-published/v1/[0-9a-f]{32}/[0-9a-f]{64}"
    r")$"
)


class DemoAssetLoadError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DemoAssetByteReference:
    asset_id: str
    storage_key: str
    sha256: str
    byte_size: int
    synthetic: bool


class DemoAssetByteLoader(Protocol):
    async def load(self, reference: DemoAssetByteReference) -> bytes: ...


class LocalDemoAssetByteLoader:
    """Read only the accepted synthetic and D07 private namespaces."""

    def __init__(self, *, root: Path, maximum_bytes: int = 64 * 1024 * 1024) -> None:
        raw_root = root.absolute()
        if raw_root.is_symlink() or not 1 <= maximum_bytes <= 512 * 1024 * 1024:
            raise DemoAssetLoadError("ASSET_STORAGE_ROOT_INVALID", "Asset storage is invalid")
        try:
            raw_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DemoAssetLoadError(
                "ASSET_STORAGE_ROOT_UNAVAILABLE", "Asset storage is unavailable"
            ) from exc
        if raw_root.is_symlink() or not raw_root.is_dir():
            raise DemoAssetLoadError("ASSET_STORAGE_ROOT_INVALID", "Asset storage is invalid")
        self._root = raw_root.resolve(strict=True)
        self._maximum_bytes = maximum_bytes

    async def load(self, reference: DemoAssetByteReference) -> bytes:
        self._validate_reference(reference)
        return await asyncio.to_thread(self._load_sync, reference)

    def _load_sync(self, reference: DemoAssetByteReference) -> bytes:
        target = self._root.joinpath(*reference.storage_key.split("/"), "payload")
        self._reject_symlinks(target)
        try:
            if not target.is_file():
                raise DemoAssetLoadError("ASSET_BYTES_UNAVAILABLE", "Asset bytes are unavailable")
            with target.open("rb") as handle:
                content = handle.read(self._maximum_bytes + 1)
        except DemoAssetLoadError:
            raise
        except OSError as exc:
            raise DemoAssetLoadError("ASSET_READ_FAILED", "Asset bytes could not be read") from exc
        if len(content) > self._maximum_bytes or len(content) != reference.byte_size:
            raise DemoAssetLoadError("ASSET_SIZE_MISMATCH", "Asset byte size mismatches authority")
        actual = hashlib.sha256(content).hexdigest()
        if not hmac.compare_digest(actual, reference.sha256):
            raise DemoAssetLoadError("ASSET_DIGEST_MISMATCH", "Asset digest mismatches authority")
        return content

    def _reject_symlinks(self, target: Path) -> None:
        candidate = self._root
        relative = target.relative_to(self._root)
        for component in relative.parts:
            candidate /= component
            if candidate.is_symlink():
                raise DemoAssetLoadError("ASSET_PATH_INVALID", "Asset path is invalid")
        resolved = target.resolve(strict=False)
        if not resolved.is_relative_to(self._root):
            raise DemoAssetLoadError("ASSET_PATH_INVALID", "Asset path is invalid")

    @staticmethod
    def _validate_reference(reference: DemoAssetByteReference) -> None:
        if not isinstance(reference, DemoAssetByteReference):
            raise DemoAssetLoadError("ASSET_REFERENCE_INVALID", "Asset reference is invalid")
        if (
            re.fullmatch(r"[0-9a-f]{32}", reference.asset_id) is None
            or _ALLOWED_DIRECTORY_KEY.fullmatch(reference.storage_key) is None
            or _DIGEST.fullmatch(reference.sha256) is None
            or type(reference.byte_size) is not int
            or reference.byte_size <= 0
            or reference.synthetic is not True
        ):
            raise DemoAssetLoadError("ASSET_REFERENCE_INVALID", "Asset reference is invalid")


__all__ = [
    "DemoAssetByteLoader",
    "DemoAssetByteReference",
    "DemoAssetLoadError",
    "LocalDemoAssetByteLoader",
]
