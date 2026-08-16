from __future__ import annotations

import os
from asyncio import gather
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.models import (
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    SyntheticSourceObject,
    SyntheticSourceObjectDeletionEvidence,
    new_id,
)
from mirror_api.providers import synthetic_local
from mirror_api.providers.base import (
    GeneratedImagePayload,
    GenerationBudgetContext,
    SyntheticGenerationRequest,
    SyntheticOutputSpecification,
    SyntheticStorageConflictError,
    SyntheticStorageOperationError,
    SyntheticStorageWriteRequest,
)
from mirror_api.providers.mock import (
    MOCK_SYNTHETIC_PROVENANCE,
    MockImageGenerationProvider,
)
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.storage_keys import (
    internal_synthetic_raw_object_key,
    synthetic_raw_storage_reference,
)
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.generation_types import (
    GenerationBatchCreate,
    GenerationOperationRejected,
)
from mirror_api.synthetic_dataset.prompt_material import EphemeralPrompt
from mirror_api.synthetic_dataset.raw_storage import SyntheticRawStorageService

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)


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
                    "TRUNCATE TABLE synthetic_source_object_deletion_evidence, "
                    "provider_cost_events, synthetic_generation_evidence, "
                    "synthetic_source_objects, generation_items, generation_batches, "
                    "job_attempts, jobs, synthetic_generation_policies, "
                    "synthetic_prompt_templates CASCADE"
                )
            )
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE synthetic_source_object_deletion_evidence, "
                    "provider_cost_events, synthetic_generation_evidence, "
                    "synthetic_source_objects, generation_items, generation_batches, "
                    "job_attempts, jobs, synthetic_generation_policies, "
                    "synthetic_prompt_templates CASCADE"
                )
            )
        await engine.dispose()


async def _authorities(sessions: async_sessionmaker[AsyncSession]) -> tuple[str, str]:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="raw-storage-policy-v1",
        content={"subject": "synthetic"},
        content_digest="a" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="raw-storage-prompt-v1",
        content={"template": "clearly adult synthetic non-human fixture"},
        content_digest="b" * 64,
    )
    async with sessions() as session:
        session.add_all((policy, prompt))
        await session.commit()
        await session.execute(
            update(SyntheticGenerationPolicy)
            .where(SyntheticGenerationPolicy.id == policy.id)
            .values(approval_status="APPROVED", approved_at=NOW)
        )
        await session.execute(
            update(SyntheticPromptTemplate)
            .where(SyntheticPromptTemplate.id == prompt.id)
            .values(approval_status="APPROVED", approved_at=NOW)
        )
        await session.commit()
    return policy.id, prompt.id


def _command(policy_id: str, prompt_id: str, *, key: str) -> GenerationBatchCreate:
    return GenerationBatchCreate(
        idempotency_key_hash=key * 64,
        request_id=f"raw-storage-{key * 8}",
        generation_policy_id=policy_id,
        prompt_template_id=prompt_id,
        provider_reference="mock-provider-v1",
        model_reference="mock-model-v1",
        model_version_reference="mock-model-version-v1",
        pricing_snapshot_reference="pricing-fixture-v1",
        output_media_type="image/png",
        output_width=1,
        output_height=1,
        output_max_bytes=1024,
        item_count=1,
        requested_seeds=(None,),
        currency="CNY",
        hard_budget_micros=100,
        per_item_ceiling_micros=100,
        retry_ceiling=1,
        concurrency_ceiling=1,
    )


def _generation_request(request_reference: str) -> SyntheticGenerationRequest:
    return SyntheticGenerationRequest(
        request_reference=request_reference,
        generation_policy_reference="generation-policy-v1",
        prompt_template_reference="prompt-template-v1",
        output_specification=SyntheticOutputSpecification(
            media_type="image/png", width=1, height=1, max_byte_size=1024
        ),
        generation_parameters=(),
        seed=None,
        budget=GenerationBudgetContext(
            currency="CNY",
            max_amount_micros=100,
            pricing_snapshot_reference="pricing-fixture-v1",
        ),
    )


@pytest.mark.asyncio
async def test_local_raw_storage_is_exact_immutable_and_private(tmp_path: Path) -> None:
    provider = LocalSyntheticRawStorageProvider(root=tmp_path)
    item_id = "1" * 32
    attempt_id = "2" * 32
    reference = synthetic_raw_storage_reference(item_id, attempt_id)
    assert reference == synthetic_raw_storage_reference(item_id, attempt_id)
    assert item_id not in reference and attempt_id not in reference
    object_key = internal_synthetic_raw_object_key(reference)
    assert object_key.startswith("internal-synthetic/v1/raw/")
    assert reference not in object_key

    first_payload = GeneratedImagePayload(content=b"synthetic-raw-one", media_type="image/png")
    first_request = SyntheticStorageWriteRequest(
        storage_reference=reference,
        payload=first_payload,
        provenance=MOCK_SYNTHETIC_PROVENANCE,
    )
    first, replay = await gather(
        provider.store_generated_image_if_absent(request=first_request),
        provider.store_generated_image_if_absent(request=first_request),
    )
    assert replay == first
    assert first.sha256 == sha256(first_payload.content).hexdigest()
    assert await provider.store_generated_image_if_absent(request=first_request) == first
    assert await provider.inspect_generated_image(storage_reference=reference) == first
    assert (
        b"".join(
            [chunk async for chunk in provider.stream_generated_image(storage_reference=reference)]
        )
        == first_payload.content
    )
    assert all(reference not in path.name for path in tmp_path.rglob("*"))

    conflicting = SyntheticStorageWriteRequest(
        storage_reference=reference,
        payload=GeneratedImagePayload(content=b"synthetic-raw-two", media_type="image/png"),
        provenance=MOCK_SYNTHETIC_PROVENANCE,
    )
    with pytest.raises(SyntheticStorageConflictError) as conflict:
        await provider.store_generated_image_if_absent(request=conflicting)
    assert str(conflict.value) == "synthetic storage conflict"
    assert reference not in str(conflict.value)
    assert first.sha256 not in str(conflict.value)

    assert await provider.delete_generated_image(storage_reference=reference) == "deleted"
    assert await provider.delete_generated_image(storage_reference=reference) == "not_found"
    assert await provider.inspect_generated_image(storage_reference=reference) is None
    assert list(tmp_path.rglob(".part-*")) == []


@pytest.mark.asyncio
async def test_local_raw_storage_detects_tampering_and_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = LocalSyntheticRawStorageProvider(root=tmp_path)
    reference = synthetic_raw_storage_reference("3" * 32, "4" * 32)
    request = SyntheticStorageWriteRequest(
        storage_reference=reference,
        payload=GeneratedImagePayload(content=b"synthetic-integrity", media_type="image/webp"),
        provenance=MOCK_SYNTHETIC_PROVENANCE,
    )
    await provider.store_generated_image_if_absent(request=request)
    digest = internal_synthetic_raw_object_key(reference).rsplit("/", 1)[-1]
    payload_path = tmp_path / "internal-synthetic" / "v1" / "raw" / digest / "payload"
    payload_path.write_bytes(b"tampered")
    with pytest.raises(SyntheticStorageOperationError) as integrity:
        await provider.inspect_generated_image(storage_reference=reference)
    assert integrity.value.reason == "synthetic_integrity_mismatch"
    assert reference not in str(integrity.value)

    second_reference = synthetic_raw_storage_reference("5" * 32, "6" * 32)
    second_digest = internal_synthetic_raw_object_key(second_reference).rsplit("/", 1)[-1]
    target = tmp_path / "internal-synthetic" / "v1" / "raw" / second_digest
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        target.symlink_to(outside, target_is_directory=True)
    except OSError:
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda path: path == target or original_is_symlink(path),
        )
    with pytest.raises(SyntheticStorageOperationError) as symlink:
        await provider.inspect_generated_image(storage_reference=second_reference)
    assert symlink.value.reason == "synthetic_object_invalid"

    failure_reference = synthetic_raw_storage_reference("a" * 32, "b" * 32)
    failure_request = SyntheticStorageWriteRequest(
        storage_reference=failure_reference,
        payload=GeneratedImagePayload(content=b"synthetic-failure", media_type="image/png"),
        provenance=MOCK_SYNTHETIC_PROVENANCE,
    )
    original_rename = synthetic_local.os.rename

    def fail_rename(source: object, target: object) -> None:
        del source, target
        raise OSError

    monkeypatch.setattr(synthetic_local.os, "rename", fail_rename)
    with pytest.raises(SyntheticStorageOperationError) as write_failure:
        await provider.store_generated_image_if_absent(request=failure_request)
    assert write_failure.value.reason == "synthetic_store_failed"
    assert list(tmp_path.rglob(".part-*")) == []
    monkeypatch.setattr(synthetic_local.os, "rename", original_rename)


@pytest.mark.asyncio
async def test_retention_and_failed_attempt_orphan_reconciliation(tmp_path: Path) -> None:
    async with _database() as sessions:
        policy_id, prompt_id = await _authorities(sessions)
        generation = GenerationBatchService(session_factory=sessions, now=lambda: NOW)
        storage = LocalSyntheticRawStorageProvider(root=tmp_path)

        created = await generation.create_batch(_command(policy_id, prompt_id, key="7"))
        await generation.queue_batch(created.batch.batch_id)
        reservation = await generation.reserve_next_item(created.batch.batch_id)
        assert reservation is not None
        provider_result = await MockImageGenerationProvider().generate_synthetic(
            request=_generation_request(reservation.request_reference),
            prompt=EphemeralPrompt("clearly adult synthetic non-human fixture"),
        )
        reference = synthetic_raw_storage_reference(reservation.item_id, reservation.attempt_id)
        stored = await storage.store_generated_image_if_absent(
            request=SyntheticStorageWriteRequest(
                storage_reference=reference,
                payload=provider_result.payload,
                provenance=provider_result.provenance,
            )
        )
        assert await generation.record_raw_stored(
            item_id=reservation.item_id,
            attempt_id=reservation.attempt_id,
            result=provider_result,
            stored=stored,
            retention_expires_at=NOW + timedelta(minutes=1),
        )

        cleanup = SyntheticRawStorageService(
            session_factory=sessions,
            storage=storage,
            now=lambda: NOW + timedelta(minutes=2),
        )
        referenced = await cleanup.delete_failed_attempt_orphan(
            item_id=reservation.item_id,
            attempt_id=reservation.attempt_id,
            storage_reference=reference,
        )
        assert referenced.outcome == "referenced"
        cleaned = await cleanup.cleanup_expired()
        assert len(cleaned) == 1
        assert cleaned[0].deletion_result == "deleted"
        assert cleaned[0].evidence_created
        assert await storage.inspect_generated_image(storage_reference=reference) is None
        assert await cleanup.cleanup_expired() == ()
        async with sessions() as session:
            source = await session.scalar(
                select(SyntheticSourceObject).where(
                    SyntheticSourceObject.storage_reference == reference
                )
            )
            assert source is not None
            evidence = await session.scalar(
                select(SyntheticSourceObjectDeletionEvidence).where(
                    SyntheticSourceObjectDeletionEvidence.source_object_id == source.id
                )
            )
            assert evidence is not None
            assert evidence.reason_code == "retention_expired"
            assert evidence.deletion_result == "deleted"

        failed = await generation.create_batch(_command(policy_id, prompt_id, key="8"))
        await generation.queue_batch(failed.batch.batch_id)
        failed_reservation = await generation.reserve_next_item(failed.batch.batch_id)
        assert failed_reservation is not None
        failed_result = await MockImageGenerationProvider().generate_synthetic(
            request=_generation_request(failed_reservation.request_reference),
            prompt=EphemeralPrompt("clearly adult synthetic non-human fixture"),
        )
        failed_reference = synthetic_raw_storage_reference(
            failed_reservation.item_id, failed_reservation.attempt_id
        )
        await storage.store_generated_image_if_absent(
            request=SyntheticStorageWriteRequest(
                storage_reference=failed_reference,
                payload=failed_result.payload,
                provenance=failed_result.provenance,
            )
        )
        with pytest.raises(GenerationOperationRejected) as active_orphan:
            await cleanup.delete_failed_attempt_orphan(
                item_id=failed_reservation.item_id,
                attempt_id=failed_reservation.attempt_id,
                storage_reference=failed_reference,
            )
        assert active_orphan.value.code == "orphan_attempt_not_quiescent"
        assert await generation.record_attempt_failure(
            item_id=failed_reservation.item_id,
            attempt_id=failed_reservation.attempt_id,
            result_code="database_write_failed",
            retryable=False,
        )
        orphan = await cleanup.delete_failed_attempt_orphan(
            item_id=failed_reservation.item_id,
            attempt_id=failed_reservation.attempt_id,
            storage_reference=failed_reference,
        )
        assert orphan.outcome == "deleted"
        repeated = await cleanup.delete_failed_attempt_orphan(
            item_id=failed_reservation.item_id,
            attempt_id=failed_reservation.attempt_id,
            storage_reference=failed_reference,
        )
        assert repeated.outcome == "not_found"
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(SyntheticSourceObject).where(
                        SyntheticSourceObject.storage_reference == failed_reference
                    )
                )
                is None
            )

        crash = await generation.create_batch(_command(policy_id, prompt_id, key="9"))
        await generation.queue_batch(crash.batch.batch_id)
        crash_reservation = await generation.reserve_next_item(crash.batch.batch_id)
        assert crash_reservation is not None
        crash_result = await MockImageGenerationProvider().generate_synthetic(
            request=_generation_request(crash_reservation.request_reference),
            prompt=EphemeralPrompt("clearly adult synthetic non-human fixture"),
        )
        crash_reference = synthetic_raw_storage_reference(
            crash_reservation.item_id, crash_reservation.attempt_id
        )
        crash_stored = await storage.store_generated_image_if_absent(
            request=SyntheticStorageWriteRequest(
                storage_reference=crash_reference,
                payload=crash_result.payload,
                provenance=crash_result.provenance,
            )
        )
        assert await generation.record_raw_stored(
            item_id=crash_reservation.item_id,
            attempt_id=crash_reservation.attempt_id,
            result=crash_result,
            stored=crash_stored,
            retention_expires_at=NOW + timedelta(minutes=1),
        )
        assert await storage.delete_generated_image(storage_reference=crash_reference) == "deleted"
        recovered = await cleanup.cleanup_expired()
        assert len(recovered) == 1
        assert recovered[0].deletion_result == "not_found"
        assert recovered[0].evidence_created
