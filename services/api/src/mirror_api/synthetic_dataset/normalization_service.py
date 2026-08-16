from __future__ import annotations

import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.image_sanitizer import (
    DEFAULT_IMAGE_SANITIZER_CONFIG,
    SANITIZER_VERSION,
    ImageSanitizationError,
    ImageSanitizerConfig,
    SanitizedImage,
    sanitize_async_image_stream,
)
from mirror_api.models import Asset, SyntheticAssetRecord, SyntheticSourceObject, new_id
from mirror_api.providers.base import (
    SyntheticNormalizedImage,
    SyntheticNormalizedStorageProvider,
    SyntheticNormalizedStorageWriteRequest,
    SyntheticObjectStorageProvider,
    SyntheticStorageConflictError,
    SyntheticStorageOperationError,
)
from mirror_api.storage_keys import synthetic_normalized_storage_reference
from mirror_api.synthetic_dataset.normalization_repository import (
    SyntheticNormalizationRepository,
)
from mirror_api.synthetic_dataset.normalization_types import (
    NormalizationAuthority,
    NormalizationRejected,
    NormalizationResult,
    NormalizationRetryableError,
    normalizer_config_digest,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def _transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


@dataclass(frozen=True)
class _NormalizationClaim:
    record_id: str
    source_object_id: str
    source_storage_reference: str
    source_sha256: str
    source_media_type: str
    source_byte_size: int
    source_width: int
    source_height: int


class SyntheticNormalizationService:
    """Canonicalizes one immutable M2 source without taking ownership of raw bytes."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        raw_storage: SyntheticObjectStorageProvider,
        normalized_storage: SyntheticNormalizedStorageProvider,
        sanitizer_config: ImageSanitizerConfig = DEFAULT_IMAGE_SANITIZER_CONFIG,
        spool_root: Path | None = None,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._sessions = session_factory
        self._raw_storage = raw_storage
        self._normalized_storage = normalized_storage
        self._sanitizer_config = sanitizer_config
        self._spool_root = spool_root
        self._now = now
        self.authority = NormalizationAuthority(
            normalizer_version=SANITIZER_VERSION,
            normalizer_config_digest=normalizer_config_digest(sanitizer_config),
        )

    async def ensure_record(self, *, source_object_id: str) -> str:
        self._require_id(source_object_id, field_name="source object id")
        async with _transaction(self._sessions) as session:
            repository = SyntheticNormalizationRepository(session)
            source = await repository.locked_source(source_object_id)
            if source is None:
                raise NormalizationRejected("source_object_not_found")
            if await repository.source_was_deleted(source.id):
                raise NormalizationRejected("source_object_deleted")
            existing = await repository.locked_record_by_source(source.id)
            if existing is not None:
                self._verify_authority(existing)
                return existing.id
            record = SyntheticAssetRecord(
                id=new_id(),
                source_object_id=source.id,
                normalizer_version=self.authority.normalizer_version,
                normalizer_config_digest=self.authority.normalizer_config_digest,
            )
            repository.add(record)
            await repository.flush()
            return record.id

    async def normalize_source(self, *, source_object_id: str) -> NormalizationResult:
        record_id = await self.ensure_record(source_object_id=source_object_id)
        return await self.normalize_record(record_id=record_id)

    async def normalize_record(
        self,
        *,
        record_id: str,
        completion_guard: Callable[[AsyncSession], Awaitable[None]] | None = None,
    ) -> NormalizationResult:
        """Normalize one record, optionally proving an enclosing worker lease at commit.

        The guard is deliberately invoked only in the record/Asset transaction, after the
        source->record locks have been acquired and before any immutable database evidence is
        written.  It lets an at-least-once adapter reject an expired delivery without turning
        a transient lease race into a content failure.
        """
        self._require_id(record_id, field_name="synthetic asset record id")
        claimed = await self._claim(record_id)
        if isinstance(claimed, NormalizationResult):
            return claimed
        try:
            raw_metadata = await self._raw_storage.inspect_generated_image(
                storage_reference=claimed.source_storage_reference
            )
        except SyntheticStorageOperationError as error:
            return await self._handle_raw_storage_error(record_id, error)
        if raw_metadata is None:
            return await self._fail(record_id, "source_object_missing")
        if (
            raw_metadata.storage_reference != claimed.source_storage_reference
            or raw_metadata.sha256 != claimed.source_sha256
            or raw_metadata.media_type != claimed.source_media_type
            or raw_metadata.byte_size != claimed.source_byte_size
        ):
            return await self._fail(record_id, "source_metadata_mismatch")
        try:
            sanitized = await sanitize_async_image_stream(
                self._verified_raw_stream(claimed),
                declared_mime_type=claimed.source_media_type,
                config=self._sanitizer_config,
                spool_root=self._spool_root,
            )
        except ImageSanitizationError as error:
            return await self._fail(record_id, error.code)
        except SyntheticStorageOperationError as error:
            return await self._handle_raw_storage_error(record_id, error)
        if (sanitized.width, sanitized.height) != (
            claimed.source_width,
            claimed.source_height,
        ):
            return await self._fail(record_id, "source_dimensions_mismatch")
        storage_reference = synthetic_normalized_storage_reference(
            claimed.record_id, self.authority.normalizer_config_digest
        )
        request = self._normalized_write(storage_reference, sanitized)
        try:
            stored = await self._normalized_storage.store_normalized_image_if_absent(
                request=request
            )
        except SyntheticStorageConflictError:
            return await self._fail(record_id, "normalized_storage_conflict")
        except SyntheticStorageOperationError as error:
            if error.reason == "synthetic_store_failed":
                raise NormalizationRetryableError from None
            return await self._fail(record_id, "normalized_storage_invalid")
        if (
            stored.storage_reference != storage_reference
            or stored.sha256 != sanitized.sha256
            or stored.byte_size != sanitized.byte_size
            or stored.width != sanitized.width
            or stored.height != sanitized.height
            or stored.media_type != sanitized.content_type
            or stored.normalizer_version != self.authority.normalizer_version
            or stored.normalizer_config_digest != self.authority.normalizer_config_digest
        ):
            return await self._fail(record_id, "normalized_metadata_mismatch")
        return await self._complete(
            record_id, stored.storage_key, sanitized, completion_guard=completion_guard
        )

    async def _claim(self, record_id: str) -> _NormalizationClaim | NormalizationResult:
        async with _transaction(self._sessions) as session:
            repository = SyntheticNormalizationRepository(session)
            observed = await repository.record(record_id)
            if observed is None:
                raise NormalizationRejected("normalization_record_not_found")
            source = await repository.locked_source(observed.source_object_id)
            record = await repository.locked_record(record_id)
            if record is None or record.source_object_id != observed.source_object_id:
                raise NormalizationRejected("normalization_record_not_found")
            self._verify_authority(record)
            if record.status == "NORMALIZATION_FAILED":
                return self._result(record, asset=None)
            if record.status not in {"NORMALIZATION_PENDING", "NORMALIZING"}:
                asset = (
                    await repository.asset(record.normalized_asset_id)
                    if record.normalized_asset_id is not None
                    else None
                )
                return self._result(record, asset=asset)
            if source is None or await repository.source_was_deleted(record.source_object_id):
                if record.status == "NORMALIZATION_PENDING":
                    record.normalization_started_at = self._now()
                    record.status = "NORMALIZING"
                    await repository.flush()
                record.status = "NORMALIZATION_FAILED"
                record.result_code = "source_object_deleted"
                await repository.flush()
                return self._result(record, asset=None)
            if record.status == "NORMALIZATION_PENDING":
                record.status = "NORMALIZING"
                record.normalization_started_at = self._now()
                await repository.flush()
            return self._claim_value(record, source)

    async def _complete(
        self,
        record_id: str,
        storage_key: str,
        sanitized: SanitizedImage,
        *,
        completion_guard: Callable[[AsyncSession], Awaitable[None]] | None,
    ) -> NormalizationResult:
        async with _transaction(self._sessions) as session:
            repository = SyntheticNormalizationRepository(session)
            observed = await repository.record(record_id)
            if observed is None:
                raise NormalizationRejected("normalization_record_not_found")
            source = await repository.locked_source(observed.source_object_id)
            record = await repository.locked_record(record_id)
            if record is None or record.source_object_id != observed.source_object_id:
                raise NormalizationRejected("normalization_record_not_found")
            self._verify_authority(record)
            if record.status != "NORMALIZING":
                asset = (
                    await repository.asset(record.normalized_asset_id)
                    if record.normalized_asset_id is not None
                    else None
                )
                return self._result(record, asset=asset)
            if source is None or await repository.source_was_deleted(record.source_object_id):
                record.status = "NORMALIZATION_FAILED"
                record.result_code = "source_object_deleted"
                await repository.flush()
                return self._result(record, asset=None)
            if completion_guard is not None:
                await completion_guard(session)
            asset = Asset(
                id=new_id(),
                owner_user_id=None,
                asset_role="synthetic",
                storage_key=storage_key,
                mime_type=sanitized.content_type,
                byte_size=sanitized.byte_size,
                width=sanitized.width,
                height=sanitized.height,
                sha256=sanitized.sha256,
                synthetic=True,
                is_ai_generated=True,
                is_ai_modified=False,
                internal_purpose="synthetic_dataset",
            )
            repository.add(asset)
            await repository.flush()
            record.normalized_asset_id = asset.id
            record.status = "NORMALIZED"
            record.normalized_at = self._now()
            await repository.flush()
            return self._result(record, asset=asset)

    async def _fail(self, record_id: str, result_code: str) -> NormalizationResult:
        async with _transaction(self._sessions) as session:
            repository = SyntheticNormalizationRepository(session)
            record = await repository.locked_record(record_id)
            if record is None:
                raise NormalizationRejected("normalization_record_not_found")
            if record.status == "NORMALIZATION_FAILED":
                return self._result(record, asset=None)
            if record.status != "NORMALIZING":
                asset = (
                    await repository.asset(record.normalized_asset_id)
                    if record.normalized_asset_id is not None
                    else None
                )
                return self._result(record, asset=asset)
            record.status = "NORMALIZATION_FAILED"
            record.result_code = result_code
            await repository.flush()
            return self._result(record, asset=None)

    async def _handle_raw_storage_error(
        self, record_id: str, error: SyntheticStorageOperationError
    ) -> NormalizationResult:
        if error.reason in {
            "synthetic_integrity_mismatch",
            "synthetic_metadata_invalid",
            "synthetic_object_invalid",
            "invalid_storage_reference",
        }:
            return await self._fail(record_id, "source_storage_invalid")
        raise NormalizationRetryableError from None

    async def _verified_raw_stream(self, claimed: _NormalizationClaim) -> AsyncIterator[bytes]:
        digest = sha256()
        byte_size = 0
        async for chunk in self._raw_storage.stream_generated_image(
            storage_reference=claimed.source_storage_reference
        ):
            byte_size += len(chunk)
            digest.update(chunk)
            yield chunk
        if byte_size != claimed.source_byte_size or digest.hexdigest() != claimed.source_sha256:
            raise SyntheticStorageOperationError("synthetic_integrity_mismatch")

    def _normalized_write(
        self, storage_reference: str, sanitized: SanitizedImage
    ) -> SyntheticNormalizedStorageWriteRequest:
        return SyntheticNormalizedStorageWriteRequest(
            storage_reference=storage_reference,
            image=SyntheticNormalizedImage(
                content=sanitized.bytes_value,
                sha256=sanitized.sha256,
                byte_size=sanitized.byte_size,
                width=sanitized.width,
                height=sanitized.height,
            ),
            normalizer_version=self.authority.normalizer_version,
            normalizer_config_digest=self.authority.normalizer_config_digest,
        )

    def _verify_authority(self, record: SyntheticAssetRecord) -> None:
        if (
            record.normalizer_version != self.authority.normalizer_version
            or record.normalizer_config_digest != self.authority.normalizer_config_digest
        ):
            raise NormalizationRejected("normalizer_authority_mismatch")

    @staticmethod
    def _claim_value(
        record: SyntheticAssetRecord, source: SyntheticSourceObject
    ) -> _NormalizationClaim:
        return _NormalizationClaim(
            record_id=record.id,
            source_object_id=source.id,
            source_storage_reference=source.storage_reference,
            source_sha256=source.sha256,
            source_media_type=source.media_type,
            source_byte_size=source.byte_size,
            source_width=source.width,
            source_height=source.height,
        )

    @staticmethod
    def _result(record: SyntheticAssetRecord, *, asset: Asset | None) -> NormalizationResult:
        if record.status == "NORMALIZATION_FAILED":
            return NormalizationResult(
                record_id=record.id,
                status="NORMALIZATION_FAILED",
                normalized_asset_id=None,
                result_code=record.result_code,
                sha256=None,
            )
        if record.normalized_asset_id is None or asset is None:
            raise NormalizationRejected("normalization_record_not_terminal")
        return NormalizationResult(
            record_id=record.id,
            status="NORMALIZED",
            normalized_asset_id=record.normalized_asset_id,
            result_code=None,
            sha256=asset.sha256,
        )

    @staticmethod
    def _require_id(value: str, *, field_name: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", value):
            raise ValueError(f"{field_name} must use the opaque identifier syntax")
