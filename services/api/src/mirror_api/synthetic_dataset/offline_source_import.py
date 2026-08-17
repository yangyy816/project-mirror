from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from typing import cast

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import OfflineSyntheticSourceAdmission, SyntheticSourceObject, new_id
from mirror_api.providers.base import (
    MAX_SYNTHETIC_GENERATED_IMAGE_BYTES,
    SyntheticObjectStorageProvider,
    SyntheticStorageOperationError,
)
from mirror_api.synthetic_dataset.codex_native_source import (
    CodexNativeAdmissionEvidence,
    CodexNativeAdmissionEvidenceV2,
)

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_REFERENCE = re.compile(r"[a-z][a-z0-9_-]{2,63}\Z")
_MEDIA_FORMATS: dict[str, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
_Receipt = CodexNativeAdmissionEvidence | CodexNativeAdmissionEvidenceV2


class OfflineSyntheticSourceImportRejected(ValueError):
    """Fail closed without exposing a prompt, path, object key, or image bytes."""

    def __init__(self, code: str) -> None:
        self.code = (
            code if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code) else "offline_import_rejected"
        )
        super().__init__("offline synthetic source import was rejected")


@dataclass(frozen=True)
class OfflineSyntheticSourceImportResult:
    admission_id: str
    source_object_id: str
    admission_evidence_digest: str


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


class OfflineSyntheticSourceImportService:
    """Bind an already-admitted offline receipt to the existing raw-source authority.

    This is intentionally an application-only bridge: it cannot call Codex, create
    M2 execution-envelope rows, or accept a loose JSON document.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: SyntheticObjectStorageProvider,
    ) -> None:
        self._sessions = session_factory
        self._storage = storage

    async def import_receipt(
        self,
        *,
        receipt: _Receipt,
        retention_expires_at: datetime,
    ) -> OfflineSyntheticSourceImportResult:
        document = self._closed_document(receipt)
        self._validate_receipt(receipt, retention_expires_at=retention_expires_at)
        evidence_digest = self._canonical_digest(document)
        await self._verify_storage(receipt)

        async with _transaction(self._sessions) as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:reference, 0))"),
                {"reference": receipt.storage_reference},
            )
            existing_source = await self._source_by_storage(session, receipt.storage_reference)
            if existing_source is not None:
                return await self._verify_existing_source(
                    session, existing_source, receipt, retention_expires_at, evidence_digest
                )
            existing_admission = await self._admission_by_digest(session, evidence_digest)
            if existing_admission is not None:
                return await self._verify_existing_admission(
                    session, existing_admission, receipt, retention_expires_at, evidence_digest
                )

            admission = OfflineSyntheticSourceAdmission(
                id=new_id(),
                schema_version="mirror.synthetic-dataset/OfflineSyntheticSourceAdmission/v1",
                admission_evidence_schema_version=receipt.schema_version,
                specification_reference=receipt.specification_reference,
                specification_version=receipt.specification_version,
                generation_policy_reference=receipt.generation_policy_reference,
                prompt_template_reference=receipt.prompt_template_reference,
                prompt_digest=receipt.prompt_digest,
                item_reference=receipt.item_reference,
                attempt=receipt.attempt,
                source_kind=receipt.source_kind,
                provenance_level=receipt.provenance_level,
                cost_accounting_mode=receipt.cost_accounting_mode,
                synthetic_only=receipt.synthetic_only,
                real_person_reference_used=receipt.real_person_reference_used,
                generated_at=receipt.generated_at,
                admitted_at=receipt.admitted_at,
                sha256=receipt.sha256,
                media_type=receipt.media_type,
                byte_size=receipt.byte_size,
                width=receipt.width,
                height=receipt.height,
                requested_width=receipt.requested_width,
                requested_height=receipt.requested_height,
                dimensions_match_requested=receipt.dimensions_match_requested,
                storage_reference=receipt.storage_reference,
                retention_expires_at=retention_expires_at,
                admission_evidence_digest=evidence_digest,
                model_reference=None,
                model_version_reference=None,
                provider_request_reference=None,
                provider_actual_seed=None,
                provider_usage=None,
                provider_cost=None,
                created_at=receipt.admitted_at,
            )
            source = SyntheticSourceObject(
                id=new_id(),
                schema_version="mirror.synthetic-dataset/SyntheticSourceObject/v2",
                generation_item_id=None,
                job_attempt_id=None,
                offline_admission_id=admission.id,
                storage_reference=receipt.storage_reference,
                sha256=receipt.sha256,
                media_type=receipt.media_type,
                byte_size=receipt.byte_size,
                width=receipt.width,
                height=receipt.height,
                retention_expires_at=retention_expires_at,
                created_at=receipt.admitted_at,
            )
            session.add_all((admission, source))
            await session.flush()
            return OfflineSyntheticSourceImportResult(admission.id, source.id, evidence_digest)

    async def _verify_storage(self, receipt: _Receipt) -> None:
        try:
            metadata = await self._storage.inspect_generated_image(
                storage_reference=receipt.storage_reference
            )
            if metadata is None or (
                metadata.storage_reference != receipt.storage_reference
                or metadata.sha256 != receipt.sha256
                or metadata.media_type != receipt.media_type
                or metadata.byte_size != receipt.byte_size
            ):
                raise OfflineSyntheticSourceImportRejected("source_metadata_mismatch")
            content = bytearray()
            digest = sha256()
            async for chunk in self._storage.stream_generated_image(
                storage_reference=receipt.storage_reference
            ):
                if type(chunk) is not bytes:
                    raise OfflineSyntheticSourceImportRejected("source_stream_invalid")
                content.extend(chunk)
                if len(content) > receipt.byte_size:
                    raise OfflineSyntheticSourceImportRejected("source_integrity_mismatch")
                digest.update(chunk)
        except SyntheticStorageOperationError as error:
            raise OfflineSyntheticSourceImportRejected("source_storage_invalid") from error
        if len(content) != receipt.byte_size or digest.hexdigest() != receipt.sha256:
            raise OfflineSyntheticSourceImportRejected("source_integrity_mismatch")
        self._verify_dimensions(bytes(content), receipt)

    @staticmethod
    def _verify_dimensions(content: bytes, receipt: _Receipt) -> None:
        try:
            with Image.open(BytesIO(content)) as image:
                if image.format != _MEDIA_FORMATS[receipt.media_type]:
                    raise ValueError("unexpected image format")
                image.verify()
            with Image.open(BytesIO(content)) as image:
                dimensions = image.size
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise OfflineSyntheticSourceImportRejected("source_decode_invalid") from error
        if dimensions != (receipt.width, receipt.height):
            raise OfflineSyntheticSourceImportRejected("source_dimensions_mismatch")

    @staticmethod
    def _closed_document(receipt: _Receipt) -> dict[str, object]:
        if type(receipt) not in (CodexNativeAdmissionEvidence, CodexNativeAdmissionEvidenceV2):
            raise OfflineSyntheticSourceImportRejected("receipt_type_not_supported")
        document = cast(dict[str, object], asdict(receipt))
        expected = {
            "schema_version",
            "specification_reference",
            "specification_version",
            "item_reference",
            "attempt",
            "source_kind",
            "provenance_level",
            "generation_policy_reference",
            "prompt_template_reference",
            "prompt_digest",
            "coverage_pack_reference",
            "coverage_cell_reference",
            "generated_at",
            "admitted_at",
            "sha256",
            "media_type",
            "byte_size",
            "width",
            "height",
            "requested_width",
            "requested_height",
            "dimensions_match_requested",
            "storage_reference",
            "synthetic_only",
            "real_person_reference_used",
            "cost_accounting_mode",
            "credit_source",
            "model_reference",
            "model_version_reference",
            "provider_request_reference",
            "provider_actual_seed",
            "provider_usage",
            "provider_cost",
        }
        if set(document) != expected:
            raise OfflineSyntheticSourceImportRejected("receipt_fields_invalid")
        for field in ("generated_at", "admitted_at"):
            value = document[field]
            if not isinstance(value, datetime):
                raise OfflineSyntheticSourceImportRejected("receipt_timestamp_invalid")
            document[field] = value.isoformat()
        return document

    @staticmethod
    def _canonical_digest(document: dict[str, object]) -> str:
        try:
            encoded = json.dumps(
                document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise OfflineSyntheticSourceImportRejected("receipt_canonicalization_failed") from error
        return sha256(encoded).hexdigest()

    @staticmethod
    def _validate_receipt(receipt: _Receipt, *, retention_expires_at: datetime) -> None:
        if receipt.schema_version not in {
            "mirror.synthetic-dataset/CodexNativeAdmissionEvidence/v1",
            "mirror.synthetic-dataset/CodexNativeAdmissionEvidence/v2",
        }:
            raise OfflineSyntheticSourceImportRejected("receipt_schema_not_supported")
        if (
            receipt.source_kind != "CODEX_NATIVE_IMAGEGEN"
            or receipt.provenance_level != "PROVENANCE_ONLY"
            or receipt.cost_accounting_mode != "REQUEST_COUNT_ONLY"
            or receipt.credit_source != "CODEX_NATIVE_ENTITLEMENT"
            or receipt.synthetic_only is not True
            or receipt.real_person_reference_used is not False
        ):
            raise OfflineSyntheticSourceImportRejected("receipt_provenance_invalid")
        if any(
            value is not None
            for value in (
                receipt.model_reference,
                receipt.model_version_reference,
                receipt.provider_request_reference,
                receipt.provider_actual_seed,
                receipt.provider_usage,
                receipt.provider_cost,
            )
        ):
            raise OfflineSyntheticSourceImportRejected("receipt_provider_facts_invalid")
        if (
            receipt.attempt < 1
            or any(
                _REFERENCE.fullmatch(reference) is None
                for reference in (
                    receipt.specification_reference,
                    receipt.specification_version,
                    receipt.generation_policy_reference,
                    receipt.prompt_template_reference,
                    receipt.item_reference,
                    receipt.storage_reference,
                )
            )
            or _DIGEST.fullmatch(receipt.prompt_digest) is None
            or _DIGEST.fullmatch(receipt.sha256) is None
            or receipt.media_type not in _MEDIA_FORMATS
            or receipt.byte_size < 1
            or receipt.byte_size > MAX_SYNTHETIC_GENERATED_IMAGE_BYTES
            or receipt.width < 1
            or receipt.height < 1
            or receipt.width > 8192
            or receipt.height > 8192
            or receipt.width * receipt.height > 40_000_000
        ):
            raise OfflineSyntheticSourceImportRejected("receipt_metadata_invalid")
        if (receipt.requested_width is None) != (receipt.requested_height is None):
            raise OfflineSyntheticSourceImportRejected("receipt_requested_dimensions_invalid")
        if receipt.requested_width is None:
            if receipt.dimensions_match_requested is not None:
                raise OfflineSyntheticSourceImportRejected("receipt_requested_dimensions_invalid")
        elif (
            receipt.requested_width < 1
            or receipt.requested_height is None
            or receipt.requested_height < 1
            or receipt.dimensions_match_requested
            != (
                receipt.width == receipt.requested_width
                and receipt.height == receipt.requested_height
            )
        ):
            raise OfflineSyntheticSourceImportRejected("receipt_requested_dimensions_invalid")
        timestamps = (receipt.generated_at, receipt.admitted_at, retention_expires_at)
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise OfflineSyntheticSourceImportRejected("receipt_timestamp_invalid")
        if not receipt.generated_at <= receipt.admitted_at < retention_expires_at:
            raise OfflineSyntheticSourceImportRejected("receipt_timestamp_invalid")

    @staticmethod
    async def _source_by_storage(
        session: AsyncSession, storage_reference: str
    ) -> SyntheticSourceObject | None:
        return cast(
            SyntheticSourceObject | None,
            await session.scalar(
                select(SyntheticSourceObject)
                .where(SyntheticSourceObject.storage_reference == storage_reference)
                .with_for_update()
            ),
        )

    @staticmethod
    async def _admission_by_digest(
        session: AsyncSession, digest: str
    ) -> OfflineSyntheticSourceAdmission | None:
        return cast(
            OfflineSyntheticSourceAdmission | None,
            await session.scalar(
                select(OfflineSyntheticSourceAdmission)
                .where(OfflineSyntheticSourceAdmission.admission_evidence_digest == digest)
                .with_for_update()
            ),
        )

    async def _verify_existing_source(
        self,
        session: AsyncSession,
        source: SyntheticSourceObject,
        receipt: _Receipt,
        retention_expires_at: datetime,
        digest: str,
    ) -> OfflineSyntheticSourceImportResult:
        if source.offline_admission_id is None:
            raise OfflineSyntheticSourceImportRejected("storage_reference_conflict")
        admission = await session.get(OfflineSyntheticSourceAdmission, source.offline_admission_id)
        if admission is None:
            raise OfflineSyntheticSourceImportRejected("offline_admission_not_found")
        return self._matching_result(source, admission, receipt, retention_expires_at, digest)

    async def _verify_existing_admission(
        self,
        session: AsyncSession,
        admission: OfflineSyntheticSourceAdmission,
        receipt: _Receipt,
        retention_expires_at: datetime,
        digest: str,
    ) -> OfflineSyntheticSourceImportResult:
        source = cast(
            SyntheticSourceObject | None,
            await session.scalar(
                select(SyntheticSourceObject)
                .where(SyntheticSourceObject.offline_admission_id == admission.id)
                .with_for_update()
            ),
        )
        if source is None:
            raise OfflineSyntheticSourceImportRejected("offline_source_missing")
        return self._matching_result(source, admission, receipt, retention_expires_at, digest)

    @staticmethod
    def _matching_result(
        source: SyntheticSourceObject,
        admission: OfflineSyntheticSourceAdmission,
        receipt: _Receipt,
        retention_expires_at: datetime,
        digest: str,
    ) -> OfflineSyntheticSourceImportResult:
        expected = (
            admission.admission_evidence_digest == digest
            and admission.storage_reference == receipt.storage_reference
            and admission.sha256 == receipt.sha256
            and admission.media_type == receipt.media_type
            and admission.byte_size == receipt.byte_size
            and admission.width == receipt.width
            and admission.height == receipt.height
            and admission.retention_expires_at == retention_expires_at
            and source.schema_version == "mirror.synthetic-dataset/SyntheticSourceObject/v2"
            and source.generation_item_id is None
            and source.job_attempt_id is None
            and source.offline_admission_id == admission.id
            and source.storage_reference == receipt.storage_reference
            and source.sha256 == receipt.sha256
            and source.media_type == receipt.media_type
            and source.byte_size == receipt.byte_size
            and source.width == receipt.width
            and source.height == receipt.height
            and source.retention_expires_at == retention_expires_at
        )
        if not expected:
            raise OfflineSyntheticSourceImportRejected("offline_import_conflict")
        return OfflineSyntheticSourceImportResult(admission.id, source.id, digest)
