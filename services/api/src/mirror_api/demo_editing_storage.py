"""Local, private quarantine storage for the D07 editing service.

This adapter intentionally stores only opaque private payload bytes below the
injected root.  It is a development/test adapter, not a public file service.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path
from typing import Final

_PAYLOAD_NAME: Final = "payload"
_KEY_COMPONENT: Final = r"[0-9a-f]{32}"
_QUARANTINE_KEY: Final = re.compile(
    rf"demo-quarantine/{_KEY_COMPONENT}/{_KEY_COMPONENT}/{_KEY_COMPONENT}/{_KEY_COMPONENT}\Z"
)
_PUBLISHED_KEY: Final = re.compile(rf"demo-published/v1/{_KEY_COMPONENT}/[0-9a-f]{{64}}\Z")
_ORIGINAL_KEY: Final = re.compile(rf"demo-original/v1/{_KEY_COMPONENT}/[0-9a-f]{{64}}\Z")


class DemoEditingStorageError(RuntimeError):
    """Fail-closed local storage error with a stable, non-sensitive code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DemoLocalPrivateObjectStorage:
    """Atomic immutable storage for one D07 quarantine-object key shape."""

    def __init__(self, *, root: Path) -> None:
        raw_root = root.absolute()
        if raw_root.is_symlink():
            raise DemoEditingStorageError("STORAGE_ROOT_INVALID", "private storage root is invalid")
        try:
            raw_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DemoEditingStorageError(
                "STORAGE_ROOT_UNAVAILABLE", "private storage root is unavailable"
            ) from exc
        if raw_root.is_symlink() or not raw_root.is_dir():
            raise DemoEditingStorageError("STORAGE_ROOT_INVALID", "private storage root is invalid")
        self._root = raw_root.resolve(strict=True)
        self._lock = asyncio.Lock()

    async def put_if_absent(self, *, key: str, content: bytes, sha256: str) -> None:
        self._validate_write(key=key, content=content, sha256=sha256)
        async with self._lock:
            await asyncio.to_thread(self._put_if_absent_sync, key, content, sha256)

    async def read(self, *, key: str) -> bytes | None:
        self._validate_object_key(key)
        async with self._lock:
            return await asyncio.to_thread(self._read_sync, key)

    async def promote_from_quarantine(self, *, key: str, artifact_id: str, sha256: str) -> str:
        """Create one immutable published object without deleting quarantine bytes."""
        self._validate_quarantine_key(key)
        if re.fullmatch(_KEY_COMPONENT, artifact_id) is None:
            raise DemoEditingStorageError(
                "STORAGE_ARTIFACT_ID_INVALID", "private artifact identifier is invalid"
            )
        if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise DemoEditingStorageError(
                "STORAGE_DIGEST_INVALID", "private content digest is invalid"
            )
        published_key = f"demo-published/v1/{artifact_id}/{sha256}"
        async with self._lock:
            await asyncio.to_thread(
                self._promote_sync,
                key,
                published_key,
                sha256,
            )
        return published_key

    async def store_original_snapshot(
        self, *, editing_session_id: str, content: bytes, sha256: str
    ) -> str:
        """Persist one immutable sequence-0 snapshot in its own private namespace."""
        if re.fullmatch(_KEY_COMPONENT, editing_session_id) is None:
            raise DemoEditingStorageError(
                "STORAGE_EDITING_SESSION_ID_INVALID",
                "editing Session identifier is invalid",
            )
        key = f"demo-original/v1/{editing_session_id}/{sha256}"
        self._validate_original_write(key=key, content=content, sha256=sha256)
        async with self._lock:
            await asyncio.to_thread(self._put_if_absent_sync, key, content, sha256)
        return key

    def _put_if_absent_sync(self, key: str, content: bytes, sha256: str) -> None:
        target = self._payload_path(key, create_parent=True)
        existing = self._read_payload(target, missing_ok=True)
        if existing is not None:
            self._ensure_matches(existing, content, sha256)
            return

        temporary = target.parent / f".payload-{secrets.token_hex(16)}.part"
        try:
            self._write_temporary(temporary, content)
            try:
                os.link(temporary, target)
                self._fsync_directory(target.parent)
            except FileExistsError:
                existing = self._read_payload(target, missing_ok=False)
                if existing is None:
                    raise DemoEditingStorageError(
                        "STORAGE_OBJECT_MISSING", "private object is unavailable"
                    ) from None
                self._ensure_matches(existing, content, sha256)
            except OSError as exc:
                raise DemoEditingStorageError(
                    "STORAGE_WRITE_FAILED", "private object could not be written"
                ) from exc
        finally:
            self._remove_temporary(temporary)

    def _read_sync(self, key: str) -> bytes | None:
        return self._read_payload(self._payload_path(key, create_parent=False), missing_ok=True)

    def _promote_sync(self, source_key: str, published_key: str, sha256: str) -> None:
        source = self._payload_path(source_key, create_parent=False)
        content = self._read_payload(source, missing_ok=False)
        if content is None or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), sha256):
            raise DemoEditingStorageError(
                "STORAGE_DIGEST_MISMATCH", "private content digest mismatches"
            )
        target = self._payload_path(published_key, create_parent=True)
        existing = self._read_payload(target, missing_ok=True)
        if existing is not None:
            self._ensure_matches(existing, content, sha256)
            return
        try:
            os.link(source, target)
            self._fsync_directory(target.parent)
        except FileExistsError:
            existing = self._read_payload(target, missing_ok=False)
            if existing is None:
                raise DemoEditingStorageError(
                    "STORAGE_OBJECT_MISSING", "private object is unavailable"
                ) from None
            self._ensure_matches(existing, content, sha256)
        except OSError as exc:
            raise DemoEditingStorageError(
                "STORAGE_PROMOTION_FAILED", "private object could not be promoted"
            ) from exc

    def _payload_path(self, key: str, *, create_parent: bool) -> Path:
        self._validate_object_key(key)
        parent = self._root
        for component in key.split("/"):
            parent = parent / component
            if parent.exists() or parent.is_symlink():
                if parent.is_symlink() or not parent.is_dir():
                    raise DemoEditingStorageError(
                        "STORAGE_PATH_INVALID", "private storage path is invalid"
                    )
                continue
            if not create_parent:
                return parent / _PAYLOAD_NAME
            try:
                parent.mkdir()
            except FileExistsError:
                pass
            except OSError as exc:
                raise DemoEditingStorageError(
                    "STORAGE_PATH_UNAVAILABLE", "private storage path is unavailable"
                ) from exc
            if parent.is_symlink() or not parent.is_dir():
                raise DemoEditingStorageError(
                    "STORAGE_PATH_INVALID", "private storage path is invalid"
                )
        return parent / _PAYLOAD_NAME

    def _read_payload(self, target: Path, *, missing_ok: bool) -> bytes | None:
        if target.is_symlink():
            raise DemoEditingStorageError("STORAGE_OBJECT_INVALID", "private object is invalid")
        try:
            if not target.exists():
                if missing_ok:
                    return None
                raise DemoEditingStorageError(
                    "STORAGE_OBJECT_MISSING", "private object is unavailable"
                )
            if not target.is_file():
                raise DemoEditingStorageError("STORAGE_OBJECT_INVALID", "private object is invalid")
            with target.open("rb") as handle:
                return handle.read()
        except DemoEditingStorageError:
            raise
        except OSError as exc:
            raise DemoEditingStorageError(
                "STORAGE_READ_FAILED", "private object could not be read"
            ) from exc

    @staticmethod
    def _validate_write(*, key: str, content: bytes, sha256: str) -> None:
        DemoLocalPrivateObjectStorage._validate_quarantine_key(key)
        DemoLocalPrivateObjectStorage._validate_content(content=content, sha256=sha256)

    @staticmethod
    def _validate_original_write(*, key: str, content: bytes, sha256: str) -> None:
        if not isinstance(key, str) or _ORIGINAL_KEY.fullmatch(key) is None:
            raise DemoEditingStorageError("STORAGE_KEY_INVALID", "private storage key is invalid")
        DemoLocalPrivateObjectStorage._validate_content(content=content, sha256=sha256)

    @staticmethod
    def _validate_content(*, content: bytes, sha256: str) -> None:
        if type(content) is not bytes:
            raise DemoEditingStorageError("STORAGE_CONTENT_INVALID", "private content is invalid")
        if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise DemoEditingStorageError(
                "STORAGE_DIGEST_INVALID", "private content digest is invalid"
            )
        actual = hashlib.sha256(content).hexdigest()
        if not hmac.compare_digest(actual, sha256):
            raise DemoEditingStorageError(
                "STORAGE_DIGEST_MISMATCH", "private content digest mismatches"
            )

    @staticmethod
    def _validate_quarantine_key(key: str) -> None:
        if not isinstance(key, str) or _QUARANTINE_KEY.fullmatch(key) is None:
            raise DemoEditingStorageError("STORAGE_KEY_INVALID", "private storage key is invalid")
        if "\\" in key or key.startswith("/") or "//" in key or "/../" in key:
            raise DemoEditingStorageError("STORAGE_KEY_INVALID", "private storage key is invalid")

    @staticmethod
    def _validate_object_key(key: str) -> None:
        if not isinstance(key, str) or (
            _QUARANTINE_KEY.fullmatch(key) is None
            and _PUBLISHED_KEY.fullmatch(key) is None
            and _ORIGINAL_KEY.fullmatch(key) is None
        ):
            raise DemoEditingStorageError("STORAGE_KEY_INVALID", "private storage key is invalid")
        if "\\" in key or key.startswith("/") or "//" in key or "/../" in key:
            raise DemoEditingStorageError("STORAGE_KEY_INVALID", "private storage key is invalid")

    @staticmethod
    def _ensure_matches(existing: bytes, content: bytes, sha256: str) -> None:
        if (
            not hmac.compare_digest(hashlib.sha256(existing).hexdigest(), sha256)
            or existing != content
        ):
            raise DemoEditingStorageError(
                "STORAGE_OBJECT_CONFLICT", "private object conflicts with the reserved content"
            )

    @staticmethod
    def _write_temporary(path: Path, content: bytes) -> None:
        try:
            with path.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as exc:
            raise DemoEditingStorageError(
                "STORAGE_WRITE_FAILED", "private object could not be written"
            ) from exc
        except OSError as exc:
            raise DemoEditingStorageError(
                "STORAGE_WRITE_FAILED", "private object could not be written"
            ) from exc

    @staticmethod
    def _remove_temporary(path: Path) -> None:
        if path.parent.is_symlink() or not path.name.startswith(".payload-"):
            raise DemoEditingStorageError("STORAGE_PATH_INVALID", "private storage path is invalid")
        try:
            if path.exists() or path.is_symlink():
                if path.is_symlink() or not path.is_file():
                    raise DemoEditingStorageError(
                        "STORAGE_OBJECT_INVALID", "private object is invalid"
                    )
                path.unlink()
        except DemoEditingStorageError:
            raise
        except OSError as exc:
            raise DemoEditingStorageError(
                "STORAGE_WRITE_FAILED", "private object could not be written"
            ) from exc

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)
