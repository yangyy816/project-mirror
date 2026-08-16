from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from test_synthetic_asset_qa_invariants import _normalized_record
from test_synthetic_normalization import _png_bytes, _raw_source

from mirror_api.models import (
    Job,
    JobAttempt,
    SyntheticAssetRecord,
    SyntheticIdentity,
    SyntheticQAMeasurement,
    SyntheticQAPolicy,
    SyntheticQAReviewDecision,
    SyntheticQARun,
    new_id,
    utcnow,
)
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.providers.synthetic_normalized_local import (
    LocalSyntheticNormalizedStorageProvider,
)
from mirror_api.synthetic_dataset.domain import CanonicalPolicy, PolicyKind
from mirror_api.synthetic_dataset.normalization_service import SyntheticNormalizationService
from mirror_api.synthetic_dataset.normalization_types import NormalizationResult
from mirror_api.synthetic_dataset.orchestration_service import (
    CanonicalIdentityRegistrationService,
    M3LeaseExpired,
    M3RetryableError,
    SyntheticM3OrchestrationService,
)
from mirror_api.synthetic_dataset.task_contract import SyntheticQATaskMessage

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE synthetic_identities, synthetic_qa_review_decisions, "
                    "synthetic_qa_measurements, synthetic_qa_runs, synthetic_asset_records, "
                    "synthetic_source_object_deletion_evidence, provider_cost_events, "
                    "synthetic_generation_evidence, synthetic_source_objects, generation_items, "
                    "generation_batches, job_attempts, jobs, synthetic_qa_policies, "
                    "synthetic_generation_policies, synthetic_prompt_templates, assets CASCADE"
                )
            )
        await engine.dispose()


def _policy_content() -> dict[str, object]:
    return {
        "schema_version": "mirror.synthetic-dataset/QAPolicyDefinition/v1",
        "requirements": [
            {
                "code": "exactly_one_face",
                "evidence_type": "measurement",
                "hard_gate": True,
                "algorithm_reference": "mirror.fixture/face-count",
                "algorithm_version": "v1",
                "threshold_rule_reference": "face-count-rule-v1",
            },
            {
                "code": "adult_presentation",
                "evidence_type": "review",
                "hard_gate": True,
                "review_rule_reference": "adult-review-v1",
            },
        ],
    }


async def _qa_run(
    sessions: async_sessionmaker[AsyncSession], *, passed: bool = True
) -> tuple[str, str]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sync_engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE synthetic_identities, synthetic_qa_review_decisions, "
                "synthetic_qa_measurements, synthetic_qa_runs, synthetic_asset_records, "
                "synthetic_source_object_deletion_evidence, provider_cost_events, "
                "synthetic_generation_evidence, synthetic_source_objects, generation_items, "
                "generation_batches, job_attempts, jobs, synthetic_qa_policies, "
                "synthetic_generation_policies, synthetic_prompt_templates, assets CASCADE"
            )
        )
    with Session(sync_engine) as session:
        record, asset = _normalized_record(session)
        content = _policy_content()
        canonical = CanonicalPolicy.create(
            kind=PolicyKind.SYNTHETIC_QA_POLICY,
            version="m3-orchestration-policy-v1",
            content=content,
        )
        policy = SyntheticQAPolicy(
            id=new_id(),
            version=canonical.version,
            content=content,
            content_digest=canonical.content_digest,
        )
        session.add(policy)
        session.commit()
        session.execute(
            update(SyntheticQAPolicy)
            .where(SyntheticQAPolicy.id == policy.id)
            .values(approval_status="APPROVED", approved_at=utcnow())
        )
        run = SyntheticQARun(
            id=new_id(),
            synthetic_asset_record_id=record.id,
            normalized_asset_id=asset.id,
            qa_policy_id=policy.id,
        )
        session.add(run)
        session.commit()
        if passed:
            started = utcnow()
            session.execute(
                update(SyntheticQARun)
                .where(SyntheticQARun.id == run.id)
                .values(status="RUNNING", started_at=started)
            )
            session.add_all(
                (
                    SyntheticQAMeasurement(
                        id=new_id(),
                        qa_run_id=run.id,
                        measurement_kind="face_count",
                        measurement_code="exactly_one_face",
                        payload={"count": 1},
                        payload_digest="1" * 64,
                        algorithm_reference="mirror.fixture/face-count",
                        algorithm_version="v1",
                        confidence=1,
                        hard_gate=True,
                        threshold_outcome="PASSED",
                        reason_code="exactly_one_face",
                    ),
                    *(
                        SyntheticQAReviewDecision(
                            id=new_id(),
                            qa_run_id=run.id,
                            review_kind=review_kind,
                            decision="PASSED",
                            reason_code=f"{review_kind}_passed",
                            actor_reference="operator:m3-test",
                            reviewed_at=started,
                            created_at=utcnow(),
                        )
                        for review_kind in (
                            "adult_presentation",
                            "likeness_risk",
                            "license_rights",
                        )
                    ),
                )
            )
            session.commit()
            session.execute(
                update(SyntheticQARun)
                .where(SyntheticQARun.id == run.id)
                .values(status="PASSED", finalized_at=utcnow())
            )
            session.commit()
        result = record.id, run.id
    sync_engine.dispose()
    return result


@pytest.mark.asyncio
async def test_identity_registration_is_concurrent_idempotent_and_lease_guarded() -> None:
    async with _database() as sessions:
        record_id, run_id = await _qa_run(sessions)
        service = CanonicalIdentityRegistrationService(session_factory=sessions, now=lambda: NOW)
        first, second = await asyncio.gather(
            service.register(record_id=record_id, qa_run_id=run_id),
            service.register(record_id=record_id, qa_run_id=run_id),
        )
        assert first[0] == second[0]
        assert {first[1], second[1]} == {True, False}
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(SyntheticIdentity)) == 1
        record_id, run_id = await _qa_run(sessions)

        async def stale(_: AsyncSession) -> None:
            raise M3LeaseExpired

        with pytest.raises(M3LeaseExpired):
            await service.register(
                record_id=record_id,
                qa_run_id=run_id,
                completion_guard=stale,
            )
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(SyntheticIdentity)) == 0


class _NoopNormalizer:
    async def normalize_record(self, **_: object) -> NormalizationResult:
        return NormalizationResult(
            record_id="a" * 32,
            status="NORMALIZED",
            normalized_asset_id="b" * 32,
            result_code=None,
            sha256="c" * 64,
        )


@pytest.mark.asyncio
async def test_normalization_task_is_reference_only_idempotent_and_lease_guarded(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        private_root = tmp_path / "private"
        raw_storage = LocalSyntheticRawStorageProvider(root=private_root)
        source = await _raw_source(
            sessions,
            storage=raw_storage,
            raw_bytes=_png_bytes(metadata=True),
        )
        normalizer = SyntheticNormalizationService(
            session_factory=sessions,
            raw_storage=raw_storage,
            normalized_storage=LocalSyntheticNormalizedStorageProvider(root=private_root),
            spool_root=tmp_path / "spool",
            now=lambda: NOW,
        )
        record_id = await normalizer.ensure_record(source_object_id=source.id)
        service = SyntheticM3OrchestrationService(
            session_factory=sessions,
            normalizer=normalizer,
            now=lambda: NOW + timedelta(minutes=1),
        )
        message = await service.schedule_normalization(
            record_id=record_id, request_id="m3-normalization-idempotent"
        )
        first = await service.execute_normalization(message)
        second = await service.execute_normalization(message)
        assert first.status == "normalized"
        assert second.status == "no_op"
        async with sessions() as session:
            record = await session.get(SyntheticAssetRecord, record_id)
            job = await session.get(Job, message.job_id)
            assert record is not None and record.status == "NORMALIZED"
            assert job is not None and job.payload == {} and job.status == "succeeded"


@pytest.mark.asyncio
async def test_qa_rejection_is_distinct_from_execution_failure_and_message_is_idempotent() -> None:
    async with _database() as sessions:
        _, run_id = await _qa_run(sessions, passed=False)
        # A policy-bound run with absent hard evidence is content rejection, not FAILED.
        service = SyntheticM3OrchestrationService(
            session_factory=sessions,
            normalizer=_NoopNormalizer(),  # type: ignore[arg-type]
            now=lambda: NOW + timedelta(minutes=1),
        )
        message = await service.schedule_qa(qa_run_id=run_id, request_id="m3-qa-idempotent")
        assert isinstance(message, SyntheticQATaskMessage)
        first = await service.execute_qa(message)
        second = await service.execute_qa(message)
        assert first.status == "qa_rejected"
        assert second.status == "no_op"
        async with sessions() as session:
            job = await session.get(Job, message.job_id)
            assert job is not None and job.payload == {} and job.status == "rejected"


@pytest.mark.asyncio
async def test_reconciliation_recovers_passed_qa_before_identity_registration() -> None:
    async with _database() as sessions:
        record_id, run_id = await _qa_run(sessions)
        service = SyntheticM3OrchestrationService(
            session_factory=sessions,
            normalizer=_NoopNormalizer(),  # type: ignore[arg-type]
            now=lambda: NOW + timedelta(minutes=1),
        )
        candidates = await service.reconciliation_candidates()
        assert len(candidates) == 1
        message = candidates[0]
        assert isinstance(message, SyntheticQATaskMessage)
        assert message.qa_run_id == run_id
        result = await service.execute_qa(message)
        assert result.status == "qa_passed"
        assert result.identity_id is not None
        async with sessions() as session:
            record = await session.get(SyntheticAssetRecord, record_id)
            job = await session.get(Job, message.job_id)
            assert record is not None and record.status == "IDENTITY_REGISTERED"
            assert job is not None and job.status == "succeeded"


@pytest.mark.asyncio
async def test_retry_exhaustion_terminalizes_qa_authority_and_stops_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _database() as sessions:
        record_id, run_id = await _qa_run(sessions, passed=False)
        service = SyntheticM3OrchestrationService(
            session_factory=sessions,
            normalizer=_NoopNormalizer(),  # type: ignore[arg-type]
            now=lambda: NOW + timedelta(minutes=1),
        )

        async def unavailable(_: object) -> object:
            raise M3RetryableError("qa_execution_unavailable")

        monkeypatch.setattr(service, "_finalize_qa", unavailable)
        message = await service.schedule_qa(qa_run_id=run_id, request_id="m3-qa-exhaustion")
        for _ in range(3):
            with pytest.raises(M3RetryableError, match="remains retryable"):
                await service.execute_qa(message)
        exhausted = await service.execute_qa(message)
        assert exhausted.status == "qa_failed"
        assert (await service.execute_qa(message)).status == "no_op"
        assert await service.reconciliation_candidates() == ()
        async with sessions() as session:
            run = await session.get(SyntheticQARun, run_id)
            record = await session.get(SyntheticAssetRecord, record_id)
            job = await session.get(Job, message.job_id)
            attempts = list(
                (
                    await session.scalars(
                        select(JobAttempt)
                        .where(JobAttempt.job_id == message.job_id)
                        .order_by(JobAttempt.attempt)
                    )
                ).all()
            )
            assert run is not None and run.status == "FAILED"
            assert record is not None and record.status == "QA_FAILED"
            assert job is not None and job.status == "failed" and job.attempt_count == 4
            assert [attempt.status for attempt in attempts] == [
                "retryable_failure",
                "retryable_failure",
                "retryable_failure",
                "failed",
            ]


@pytest.mark.asyncio
async def test_redis_celery_executes_only_the_reference_only_qa_message() -> None:
    if not os.getenv("RUN_CELERY_INTEGRATION"):
        pytest.skip("NOT VERIFIED LOCALLY: RUN_CELERY_INTEGRATION is not enabled")
    from celery.contrib.testing.worker import start_worker
    from mirror_worker.celery_adapter import celery_app, process_synthetic_qa

    async with _database() as sessions:
        _, run_id = await _qa_run(sessions, passed=False)
        service = SyntheticM3OrchestrationService(
            session_factory=sessions,
            normalizer=_NoopNormalizer(),  # type: ignore[arg-type]
            now=lambda: NOW + timedelta(minutes=1),
        )
        message = await service.schedule_qa(qa_run_id=run_id, request_id="m3-celery-qa")
        with start_worker(
            celery_app,
            perform_ping_check=False,
            loglevel="ERROR",
            queues=["mirror.synthetic"],
        ):
            result = await asyncio.to_thread(
                process_synthetic_qa.apply_async(args=[message.to_message()]).get,
                20,
            )
        assert result == {
            "target_id": run_id,
            "job_id": message.job_id,
            "status": "qa_rejected",
            "identity_id": None,
        }
