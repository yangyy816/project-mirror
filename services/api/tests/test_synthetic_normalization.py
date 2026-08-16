from __future__ import annotations

import os
from asyncio import gather
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.image_sanitizer import sanitize_image
from mirror_api.models import (
    Asset,
    GenerationBatch,
    GenerationItem,
    Job,
    JobAttempt,
    ProviderCostEvent,
    SyntheticAssetRecord,
    SyntheticGenerationEvidence,
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    SyntheticSourceObject,
    new_id,
)
from mirror_api.providers.base import (
    GeneratedImagePayload,
    SyntheticNormalizedImage,
    SyntheticNormalizedStorageWriteRequest,
    SyntheticNormalizedStoredImage,
    SyntheticStorageOperationError,
    SyntheticStorageWriteRequest,
)
from mirror_api.providers.mock import MOCK_SYNTHETIC_PROVENANCE
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.providers.synthetic_normalized_local import (
    LocalSyntheticNormalizedStorageProvider,
)
from mirror_api.storage_keys import (
    internal_synthetic_normalized_object_key,
    internal_synthetic_raw_object_key,
    synthetic_normalized_storage_reference,
    synthetic_raw_storage_reference,
)
from mirror_api.synthetic_dataset.normalization_service import SyntheticNormalizationService
from mirror_api.synthetic_dataset.normalization_types import NormalizationRetryableError

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    truncate = text(
        "TRUNCATE TABLE synthetic_identities, synthetic_qa_review_decisions, "
        "synthetic_qa_measurements, synthetic_qa_runs, synthetic_asset_records, "
        "synthetic_source_object_deletion_evidence, provider_cost_events, "
        "synthetic_generation_evidence, synthetic_source_objects, generation_items, "
        "generation_batches, job_attempts, jobs, synthetic_qa_policies, "
        "synthetic_generation_policies, synthetic_prompt_templates, assets CASCADE"
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(truncate)
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(truncate)
        await engine.dispose()


def _png_bytes(
    *,
    metadata: bool = False,
    trailer: bool = False,
    color: tuple[int, int, int] = (30, 80, 120),
) -> bytes:
    image = Image.new("RGB", (64, 64), color)
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("comment", "synthetic-normalization-fixture")
    output = BytesIO()
    try:
        image.save(output, format="PNG", pnginfo=info)
    finally:
        image.close()
    value = output.getvalue()
    return value + b"polyglot-sentinel" if trailer else value


async def _raw_source(
    sessions: async_sessionmaker[AsyncSession],
    *,
    storage: LocalSyntheticRawStorageProvider,
    raw_bytes: bytes,
    media_type: str = "image/png",
    width: int = 64,
    height: int = 64,
) -> SyntheticSourceObject:
    policy_version = f"n-policy-{new_id()[:8]}-v1"
    prompt_version = f"n-prompt-{new_id()[:8]}-v1"
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version=policy_version,
        content={"subject": "synthetic"},
        content_digest=sha256(policy_version.encode()).hexdigest(),
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version=prompt_version,
        content={"template": "redacted-reference"},
        content_digest=sha256(prompt_version.encode()).hexdigest(),
    )
    async with sessions() as session:
        session.add_all((policy, prompt))
        await session.commit()
        for model, record_id in (
            (SyntheticGenerationPolicy, policy.id),
            (SyntheticPromptTemplate, prompt.id),
        ):
            await session.execute(
                update(model)
                .where(model.id == record_id)
                .values(approval_status="APPROVED", approved_at=NOW)
            )
        await session.commit()
        batch = GenerationBatch(
            id=new_id(),
            idempotency_key_hash=sha256(new_id().encode()).hexdigest(),
            generation_policy_id=policy.id,
            prompt_template_id=prompt.id,
            provider_reference="deterministic-fixture",
            model_reference="non-human-fixture",
            model_version_reference="fixture-v1",
            pricing_snapshot_reference="pricing-fixture-v1",
            output_media_type=media_type,
            output_width=width,
            output_height=height,
            output_max_bytes=max(len(raw_bytes), 1024),
            item_count=1,
            currency="CNY",
            hard_budget_micros=100,
            per_item_ceiling_micros=100,
            retry_ceiling=1,
            concurrency_ceiling=1,
        )
        job = Job(
            id=new_id(),
            job_type="synthetic_generation",
            status="pending",
            idempotency_key_hash=sha256(f"job-{new_id()}".encode()).hexdigest(),
            request_id=f"normalization-{new_id()}",
            payload={},
            owner_user_id=None,
        )
        session.add_all((batch, job))
        await session.commit()
        item = GenerationItem(
            id=new_id(),
            batch_id=batch.id,
            ordinal=0,
            job_id=job.id,
            request_reference=f"normalization-item-{new_id()}",
            requested_seed=0,
            reserved_budget_micros=100,
        )
        attempt = JobAttempt(
            id=new_id(), job_id=job.id, attempt=1, status="running", lease_token="e" * 64
        )
        session.add_all((item, attempt))
        await session.commit()
        await session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(status="GENERATING", started_at=NOW)
        )
        await session.commit()
        reference = synthetic_raw_storage_reference(item.id, attempt.id)
        stored = await storage.store_generated_image_if_absent(
            request=SyntheticStorageWriteRequest(
                storage_reference=reference,
                payload=GeneratedImagePayload(content=raw_bytes, media_type=media_type),
                provenance=MOCK_SYNTHETIC_PROVENANCE,
            )
        )
        source = SyntheticSourceObject(
            id=new_id(),
            generation_item_id=item.id,
            job_attempt_id=attempt.id,
            storage_reference=reference,
            sha256=stored.sha256,
            media_type=media_type,
            byte_size=stored.byte_size,
            width=width,
            height=height,
            retention_expires_at=NOW + timedelta(days=1),
            created_at=NOW,
        )
        session.add_all(
            (
                source,
                SyntheticGenerationEvidence(
                    id=new_id(),
                    generation_item_id=item.id,
                    job_attempt_id=attempt.id,
                    provider_reference=batch.provider_reference,
                    model_reference=batch.model_reference,
                    model_version_reference=batch.model_version_reference,
                    provider_run_reference=f"fixture-run-{new_id()}",
                    safety_policy_reference="safety-fixture-v1",
                    safety_outcome="passed",
                    safety_reason_code="fixture_passed",
                    retention_status="not_retained",
                    output_rights="internal_evaluation_only",
                    provider_actual_seed=None,
                    provider_actual_parameters={},
                    reproducibility_level="BIT_EXACT",
                    generated_at=NOW,
                    created_at=NOW,
                ),
                ProviderCostEvent(
                    id=new_id(),
                    generation_item_id=item.id,
                    job_attempt_id=attempt.id,
                    event_kind="final",
                    currency="CNY",
                    amount_micros=100,
                    pricing_snapshot_reference=batch.pricing_snapshot_reference,
                    occurred_at=NOW,
                    created_at=NOW,
                ),
            )
        )
        await session.commit()
        await session.execute(
            update(JobAttempt)
            .where(JobAttempt.id == attempt.id)
            .values(status="raw_stored", result_code="raw_stored", finished_at=NOW)
        )
        await session.commit()
        await session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(status="RAW_STORED", finalized_at=NOW, result_code="raw_stored")
        )
        await session.commit()
        return source


class _CrashAfterStore:
    def __init__(self, delegate: LocalSyntheticNormalizedStorageProvider) -> None:
        self.delegate = delegate
        self.failed = False

    async def store_normalized_image_if_absent(
        self, *, request: SyntheticNormalizedStorageWriteRequest
    ) -> SyntheticNormalizedStoredImage:
        stored = await self.delegate.store_normalized_image_if_absent(request=request)
        if not self.failed:
            self.failed = True
            raise SyntheticStorageOperationError("synthetic_store_failed")
        return stored

    async def inspect_normalized_image(
        self, *, storage_reference: str
    ) -> SyntheticNormalizedStoredImage | None:
        return await self.delegate.inspect_normalized_image(storage_reference=storage_reference)

    def stream_normalized_image(self, *, storage_reference: str) -> AsyncIterator[bytes]:
        return self.delegate.stream_normalized_image(storage_reference=storage_reference)


@pytest.mark.asyncio
async def test_normalization_is_deterministic_private_and_concurrency_idempotent(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        raw_storage = LocalSyntheticRawStorageProvider(root=tmp_path)
        normalized_storage = LocalSyntheticNormalizedStorageProvider(root=tmp_path)
        raw = _png_bytes(metadata=True, trailer=True)
        source = await _raw_source(sessions, storage=raw_storage, raw_bytes=raw)
        service = SyntheticNormalizationService(
            session_factory=sessions,
            raw_storage=raw_storage,
            normalized_storage=normalized_storage,
            spool_root=tmp_path / "spool",
            now=lambda: NOW + timedelta(minutes=1),
        )
        first, second = await gather(
            service.normalize_source(source_object_id=source.id),
            service.normalize_source(source_object_id=source.id),
        )
        assert first == second
        assert first.status == "NORMALIZED"
        assert first.normalized_asset_id is not None
        async with sessions() as session:
            asset = await session.get(Asset, first.normalized_asset_id)
            assert asset is not None
            assert asset.owner_user_id is None
            assert asset.asset_role == "synthetic"
            assert asset.internal_purpose == "synthetic_dataset"
            assert asset.synthetic and asset.is_ai_generated and not asset.is_ai_modified
            assert asset.storage_key.startswith("internal-synthetic/v1/normalized/")
            assert await session.scalar(select(func.count()).select_from(SyntheticAssetRecord)) == 1
            assert await session.scalar(select(func.count()).select_from(Asset)) == 1
        record_id = first.record_id
        reference = synthetic_normalized_storage_reference(
            record_id, service.authority.normalizer_config_digest
        )
        metadata = await normalized_storage.inspect_normalized_image(storage_reference=reference)
        assert metadata is not None
        normalized = b"".join(
            [
                chunk
                async for chunk in normalized_storage.stream_normalized_image(
                    storage_reference=reference
                )
            ]
        )
        assert sha256(normalized).hexdigest() == first.sha256 == metadata.sha256
        assert b"synthetic-normalization-fixture" not in normalized
        assert b"polyglot-sentinel" not in normalized
        async with sessions() as session:
            await session.execute(
                update(SyntheticAssetRecord)
                .where(SyntheticAssetRecord.id == record_id)
                .values(status="QA_PENDING")
            )
            await session.commit()
        assert await service.normalize_record(record_id=record_id) == first


@pytest.mark.asyncio
async def test_normalization_detects_raw_tamper_and_malformed_input(tmp_path: Path) -> None:
    async with _database() as sessions:
        raw_storage = LocalSyntheticRawStorageProvider(root=tmp_path)
        normalized_storage = LocalSyntheticNormalizedStorageProvider(root=tmp_path)
        source = await _raw_source(sessions, storage=raw_storage, raw_bytes=_png_bytes())
        raw_digest = internal_synthetic_raw_object_key(source.storage_reference).rsplit("/", 1)[-1]
        (tmp_path / "internal-synthetic" / "v1" / "raw" / raw_digest / "payload").write_bytes(
            b"tampered"
        )
        service = SyntheticNormalizationService(
            session_factory=sessions,
            raw_storage=raw_storage,
            normalized_storage=normalized_storage,
            spool_root=tmp_path / "spool",
            now=lambda: NOW + timedelta(minutes=1),
        )
        tampered = await service.normalize_source(source_object_id=source.id)
        assert tampered.status == "NORMALIZATION_FAILED"
        assert tampered.result_code == "source_storage_invalid"

        malformed = await _raw_source(
            sessions,
            storage=raw_storage,
            raw_bytes=b"synthetic-but-not-an-image",
        )
        rejected = await service.normalize_source(source_object_id=malformed.id)
        assert rejected.status == "NORMALIZATION_FAILED"
        assert rejected.result_code == "image_magic_mismatch"


@pytest.mark.asyncio
async def test_normalized_storage_tamper_fails_closed(tmp_path: Path) -> None:
    async with _database() as sessions:
        raw_storage = LocalSyntheticRawStorageProvider(root=tmp_path)
        normalized_storage = LocalSyntheticNormalizedStorageProvider(root=tmp_path)
        raw = _png_bytes()
        source = await _raw_source(sessions, storage=raw_storage, raw_bytes=raw)
        service = SyntheticNormalizationService(
            session_factory=sessions,
            raw_storage=raw_storage,
            normalized_storage=normalized_storage,
            spool_root=tmp_path / "spool",
            now=lambda: NOW + timedelta(minutes=1),
        )
        record_id = await service.ensure_record(source_object_id=source.id)
        reference = synthetic_normalized_storage_reference(
            record_id, service.authority.normalizer_config_digest
        )
        conflicting = sanitize_image(
            _png_bytes(), declared_mime_type="image/png", spool_root=tmp_path / "conflict-spool"
        )
        await normalized_storage.store_normalized_image_if_absent(
            request=service._normalized_write(reference, conflicting)
        )
        target = tmp_path / Path(internal_synthetic_normalized_object_key(reference))
        payload = target / "payload"
        payload.write_bytes(payload.read_bytes() + b"different")
        result = await service.normalize_record(record_id=record_id)
        assert result.status == "NORMALIZATION_FAILED"
        assert result.result_code == "normalized_storage_invalid"


@pytest.mark.asyncio
async def test_normalized_storage_conflict_fails_closed(tmp_path: Path) -> None:
    async with _database() as sessions:
        raw_storage = LocalSyntheticRawStorageProvider(root=tmp_path)
        normalized_storage = LocalSyntheticNormalizedStorageProvider(root=tmp_path)
        source = await _raw_source(sessions, storage=raw_storage, raw_bytes=_png_bytes())
        service = SyntheticNormalizationService(
            session_factory=sessions,
            raw_storage=raw_storage,
            normalized_storage=normalized_storage,
            spool_root=tmp_path / "spool",
            now=lambda: NOW + timedelta(minutes=1),
        )
        record_id = await service.ensure_record(source_object_id=source.id)
        reference = synthetic_normalized_storage_reference(
            record_id, service.authority.normalizer_config_digest
        )
        conflicting = sanitize_image(
            _png_bytes(color=(120, 30, 80)),
            declared_mime_type="image/png",
            spool_root=tmp_path / "conflict-spool",
        )
        await normalized_storage.store_normalized_image_if_absent(
            request=SyntheticNormalizedStorageWriteRequest(
                storage_reference=reference,
                image=SyntheticNormalizedImage(
                    content=conflicting.bytes_value,
                    sha256=conflicting.sha256,
                    byte_size=conflicting.byte_size,
                    width=conflicting.width,
                    height=conflicting.height,
                ),
                normalizer_version=service.authority.normalizer_version,
                normalizer_config_digest=service.authority.normalizer_config_digest,
            )
        )
        result = await service.normalize_record(record_id=record_id)
        assert result.status == "NORMALIZATION_FAILED"
        assert result.result_code == "normalized_storage_conflict"


@pytest.mark.asyncio
async def test_blob_before_database_crash_is_recovered_without_overwrite(tmp_path: Path) -> None:
    async with _database() as sessions:
        raw_storage = LocalSyntheticRawStorageProvider(root=tmp_path)
        normalized = LocalSyntheticNormalizedStorageProvider(root=tmp_path)
        crash_once = _CrashAfterStore(normalized)
        source = await _raw_source(sessions, storage=raw_storage, raw_bytes=_png_bytes())
        service = SyntheticNormalizationService(
            session_factory=sessions,
            raw_storage=raw_storage,
            normalized_storage=crash_once,
            spool_root=tmp_path / "spool",
            now=lambda: NOW + timedelta(minutes=1),
        )
        record_id = await service.ensure_record(source_object_id=source.id)
        with pytest.raises(NormalizationRetryableError):
            await service.normalize_record(record_id=record_id)
        async with sessions() as session:
            record = await session.get(SyntheticAssetRecord, record_id)
            assert record is not None and record.status == "NORMALIZING"
            assert record.normalized_asset_id is None
        recovered = await service.normalize_record(record_id=record_id)
        assert recovered.status == "NORMALIZED"
        assert recovered.normalized_asset_id is not None
