from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from tempfile import SpooledTemporaryFile
from typing import Any
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from mirror_api.models import Asset, ConsentRecord, PolicyAcceptanceRecord, User
from mirror_api.providers.base import ObjectStorageProvider

ARCHIVE_SCHEMA_VERSION = "mirror-data-export-v1"
ARCHIVE_CHUNK_BYTES = 64 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
OPAQUE_ID = re.compile(r"^[0-9a-f]{32}$")


class ExportArchiveFailure(Exception):
    pass


@dataclass
class ExportArchive:
    handle: SpooledTemporaryFile[bytes]
    byte_size: int
    sha256: str

    async def body(self) -> AsyncIterator[bytes]:
        self.handle.seek(0)
        while True:
            chunk = await asyncio.to_thread(self.handle.read, ARCHIVE_CHUNK_BYTES)
            if not chunk:
                break
            yield chunk

    def close(self) -> None:
        self.handle.close()


class ExportArchiveBuilder:
    def __init__(self, *, storage: ObjectStorageProvider) -> None:
        self._storage = storage

    async def build(
        self,
        *,
        user: User,
        policies: tuple[PolicyAcceptanceRecord, ...],
        consents: tuple[ConsentRecord, ...],
        assets: tuple[Asset, ...],
        generated_at: datetime,
    ) -> ExportArchive:
        handle = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
        files: list[dict[str, Any]] = []
        try:
            with ZipFile(
                handle, mode="w", compression=ZIP_STORED, strict_timestamps=True
            ) as archive:
                self._write_json(
                    archive,
                    "account.json",
                    {
                        "id": user.id,
                        "status": user.status,
                        "created_at": self._time(user.created_at),
                    },
                    files,
                )
                self._write_json(
                    archive,
                    "policy_acceptances.json",
                    [
                        {
                            "document_code": item.document_code,
                            "document_version": item.document_version,
                            "document_digest": item.document_digest,
                            "accepted_at": self._time(item.accepted_at),
                            "source": item.source,
                        }
                        for item in policies
                    ],
                    files,
                )
                self._write_json(
                    archive,
                    "consents.json",
                    [
                        {
                            "id": item.id,
                            "consent_type": item.consent_type,
                            "purpose": item.purpose,
                            "purpose_version": item.purpose_version,
                            "scope": item.scope,
                            "policy_code": item.policy_code,
                            "policy_version": item.policy_version,
                            "policy_digest": item.policy_digest,
                            "action": item.action,
                            "supersedes_id": item.supersedes_id,
                            "granted_at": self._time(item.granted_at),
                            "withdrawn_at": self._time(item.withdrawn_at),
                            "expires_at": self._time(item.expires_at),
                            "source": item.source,
                        }
                        for item in consents
                    ],
                    files,
                )
                self._write_json(
                    archive,
                    "assets/index.json",
                    [
                        {
                            "id": asset.id,
                            "asset_role": asset.asset_role,
                            "mime_type": asset.mime_type,
                            "byte_size": asset.byte_size,
                            "width": asset.width,
                            "height": asset.height,
                            "sha256": asset.sha256,
                            "synthetic": asset.synthetic,
                            "is_ai_generated": asset.is_ai_generated,
                            "is_ai_modified": asset.is_ai_modified,
                            "created_at": self._time(asset.created_at),
                        }
                        for asset in assets
                    ],
                    files,
                )
                for asset in assets:
                    await self._write_asset(archive, asset, files)
                self._write_json(
                    archive,
                    "manifest.json",
                    {
                        "schema_version": ARCHIVE_SCHEMA_VERSION,
                        "generated_at": self._time(generated_at),
                        "categories": [
                            "account",
                            "policy_acceptances",
                            "purpose_consents",
                            "sanitized_assets",
                        ],
                        "excluded_categories": [
                            "authentication_secrets",
                            "token_and_hash_material",
                            "raw_quarantine_objects",
                            "internal_risk_and_audit_data",
                            "system_prompts",
                            "other_users",
                        ],
                        "files": files,
                    },
                    None,
                )
            byte_size, checksum = self._size_and_sha256(handle)
            if byte_size <= 0 or byte_size > MAX_ARCHIVE_BYTES:
                raise ExportArchiveFailure("data export archive exceeds the allowed boundary")
            return ExportArchive(handle=handle, byte_size=byte_size, sha256=checksum)
        except Exception:
            handle.close()
            raise

    async def _write_asset(
        self, archive: ZipFile, asset: Asset, files: list[dict[str, Any]]
    ) -> None:
        if not OPAQUE_ID.fullmatch(asset.id) or asset.mime_type != "image/jpeg":
            raise ExportArchiveFailure("asset metadata is outside the export schema")
        path = f"assets/{asset.id}.jpg"
        digest = hashlib.sha256()
        byte_size = 0
        with archive.open(self._zip_info(path), mode="w") as destination:
            async for chunk in self._storage.stream_sanitized_object(object_key=asset.storage_key):
                byte_size += len(chunk)
                if byte_size > asset.byte_size or byte_size > MAX_ARCHIVE_BYTES:
                    raise ExportArchiveFailure("asset bytes exceed authoritative metadata")
                digest.update(chunk)
                destination.write(chunk)
        if byte_size != asset.byte_size or digest.hexdigest() != asset.sha256:
            raise ExportArchiveFailure("asset bytes do not match authoritative metadata")
        files.append({"path": path, "byte_size": byte_size, "sha256": digest.hexdigest()})

    def _write_json(
        self,
        archive: ZipFile,
        path: str,
        value: Any,
        files: list[dict[str, Any]] | None,
    ) -> None:
        body = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        archive.writestr(self._zip_info(path), body)
        if files is not None:
            files.append(
                {"path": path, "byte_size": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            )

    @staticmethod
    def _zip_info(path: str) -> ZipInfo:
        if path.startswith("/") or ".." in path.split("/") or "\\" in path:
            raise ExportArchiveFailure("unsafe archive path")
        info = ZipInfo(filename=path, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_STORED
        info.create_system = 3
        info.external_attr = 0o600 << 16
        return info

    @staticmethod
    def _time(value: datetime | None) -> str | None:
        return None if value is None else value.isoformat()

    @staticmethod
    def _size_and_sha256(handle: SpooledTemporaryFile[bytes]) -> tuple[int, str]:
        handle.seek(0)
        digest = hashlib.sha256()
        size = 0
        while chunk := handle.read(ARCHIVE_CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
        handle.seek(0)
        return size, digest.hexdigest()
