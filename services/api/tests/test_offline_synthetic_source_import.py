from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import OfflineSyntheticSourceAdmission, SyntheticSourceObject
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.providers.synthetic_normalized_local import LocalSyntheticNormalizedStorageProvider
from mirror_api.synthetic_dataset.codex_native_source import (
    CodexNativeAdmissionEvidenceV2,
    CodexNativeGenerationSpecificationV2,
    CodexNativeOutputConstraints,
    CodexNativeSourceAdmissionService,
)
from mirror_api.synthetic_dataset.normalization_service import SyntheticNormalizationService
from mirror_api.synthetic_dataset.offline_source_import import (
    OfflineSyntheticSourceImportRejected,
    OfflineSyntheticSourceImportService,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE synthetic_asset_records, "
                    "synthetic_source_object_deletion_evidence, "
                    "synthetic_source_objects, offline_synthetic_source_admissions CASCADE"
                )
            )
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE synthetic_asset_records, "
                    "synthetic_source_object_deletion_evidence, "
                    "synthetic_source_objects, offline_synthetic_source_admissions CASCADE"
                )
            )
        await engine.dispose()


def _png() -> bytes:
    image = Image.new("RGB", (16, 16), (20, 80, 120))
    output = BytesIO()
    try:
        image.save(output, format="PNG")
        return output.getvalue()
    finally:
        image.close()


async def _receipt(
    storage: LocalSyntheticRawStorageProvider,
) -> CodexNativeAdmissionEvidenceV2:
    specification = CodexNativeGenerationSpecificationV2(
        schema_version="mirror.synthetic-dataset/CodexNativeGenerationSpecification/v2",
        specification_reference="offline-import-spec-v2",
        specification_version="offline-import-spec-version-v2",
        generation_policy_reference="offline-import-policy-v2",
        prompt_template_reference="offline-import-prompt-v2",
        prompt_digest="a" * 64,
        requested_pose_reference="offline-import-pose-v2",
        requested_expression_reference="offline-import-expression-v2",
        styling_constraints_reference="offline-import-style-v2",
        output_constraints=CodexNativeOutputConstraints(
            media_type="image/png",
            max_byte_size=1024 * 1024,
            max_width=64,
            max_height=64,
            max_pixels=4096,
            requested_width=None,
            requested_height=None,
        ),
        requested_quantity=1,
        max_attempts=1,
        retry_ceiling=0,
        concurrency_ceiling=1,
        stop_condition_reference="offline-import-stop-v2",
    )
    return await CodexNativeSourceAdmissionService(storage=storage, now=lambda: NOW).admit_v2(
        specification=specification,
        item_reference="offline-import-item-v2",
        attempt=1,
        generated_at=NOW - timedelta(seconds=1),
        content=_png(),
        media_type="image/png",
    )


@pytest.mark.asyncio
async def test_import_is_atomic_idempotent_and_normalization_ready(tmp_path: Path) -> None:
    async with _database() as sessions:
        storage = LocalSyntheticRawStorageProvider(root=tmp_path)
        receipt = await _receipt(storage)
        service = OfflineSyntheticSourceImportService(session_factory=sessions, storage=storage)
        retention = NOW + timedelta(days=1)

        first = await service.import_receipt(receipt=receipt, retention_expires_at=retention)
        second = await service.import_receipt(receipt=receipt, retention_expires_at=retention)

        assert first == second
        normalizer = SyntheticNormalizationService(
            session_factory=sessions,
            raw_storage=storage,
            normalized_storage=LocalSyntheticNormalizedStorageProvider(root=tmp_path),
            spool_root=tmp_path / "spool",
            now=lambda: NOW + timedelta(seconds=1),
        )
        record_id = await normalizer.ensure_record(source_object_id=first.source_object_id)
        assert len(record_id) == 32
        async with sessions() as session:
            assert await session.scalar(select_count(OfflineSyntheticSourceAdmission)) == 1
            assert await session.scalar(select_count(SyntheticSourceObject)) == 1
            source = await session.get(SyntheticSourceObject, first.source_object_id)
            assert source is not None
            assert source.schema_version == "mirror.synthetic-dataset/SyntheticSourceObject/v2"
            assert source.generation_item_id is None and source.job_attempt_id is None
            assert source.offline_admission_id == first.admission_id


@pytest.mark.asyncio
async def test_import_fails_closed_when_retention_or_storage_facts_mismatch(tmp_path: Path) -> None:
    async with _database() as sessions:
        storage = LocalSyntheticRawStorageProvider(root=tmp_path)
        receipt = await _receipt(storage)
        service = OfflineSyntheticSourceImportService(session_factory=sessions, storage=storage)

        with pytest.raises(OfflineSyntheticSourceImportRejected) as expired:
            await service.import_receipt(receipt=receipt, retention_expires_at=NOW)
        assert expired.value.code == "receipt_timestamp_invalid"

        altered = replace(receipt, sha256="b" * 64)
        with pytest.raises(OfflineSyntheticSourceImportRejected) as mismatch:
            await service.import_receipt(
                receipt=altered, retention_expires_at=NOW + timedelta(days=1)
            )
        assert mismatch.value.code == "source_metadata_mismatch"


def select_count(model: type[OfflineSyntheticSourceAdmission] | type[SyntheticSourceObject]):
    return select(func.count()).select_from(model)
