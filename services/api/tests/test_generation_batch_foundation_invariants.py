from __future__ import annotations

import os
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, delete, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mirror_api.models import (
    GenerationBatch,
    GenerationItem,
    Job,
    JobAttempt,
    ProviderCostEvent,
    SyntheticGenerationEvidence,
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    SyntheticSourceObject,
    SyntheticSourceObjectDeletionEvidence,
    new_id,
    utcnow,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE synthetic_source_object_deletion_evidence, "
                "provider_cost_events, synthetic_generation_evidence, synthetic_source_objects, "
                "generation_items, generation_batches, job_attempts, jobs, "
                "synthetic_generation_policies, synthetic_prompt_templates CASCADE"
            )
        )
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _approved_authorities(session: Session) -> tuple[str, str]:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="generation-fixture-v1",
        content={"subject": "synthetic"},
        content_digest="a" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="prompt-fixture-v1",
        content={"template": "redacted-fixture-reference"},
        content_digest="b" * 64,
    )
    session.add_all((policy, prompt))
    session.commit()
    session.execute(
        update(SyntheticGenerationPolicy)
        .where(SyntheticGenerationPolicy.id == policy.id)
        .values(approval_status="APPROVED", approved_at=text("now()"))
    )
    session.execute(
        update(SyntheticPromptTemplate)
        .where(SyntheticPromptTemplate.id == prompt.id)
        .values(approval_status="APPROVED", approved_at=text("now()"))
    )
    session.commit()
    return policy.id, prompt.id


def _batch(
    session: Session,
    *,
    item_count: int = 1,
    hard_budget_micros: int = 200,
    per_item_ceiling_micros: int = 100,
) -> GenerationBatch:
    policy_id, prompt_id = _approved_authorities(session)
    batch = GenerationBatch(
        id=new_id(),
        idempotency_key_hash="c" * 64,
        generation_policy_id=policy_id,
        prompt_template_id=prompt_id,
        provider_reference="deterministic-mock",
        model_reference="non-human-fixture",
        model_version_reference="fixture-v1",
        pricing_snapshot_reference="pricing-fixture-v1",
        output_media_type="image/png",
        output_width=1,
        output_height=1,
        output_max_bytes=1024,
        item_count=item_count,
        currency="CNY",
        hard_budget_micros=hard_budget_micros,
        per_item_ceiling_micros=per_item_ceiling_micros,
        retry_ceiling=2,
        concurrency_ceiling=min(item_count, 2),
    )
    session.add(batch)
    session.commit()
    return batch


def _job(session: Session, *, suffix: str) -> Job:
    job = Job(
        id=new_id(),
        job_type="synthetic_generation",
        status="pending",
        idempotency_key_hash=(suffix * 64)[:64],
        request_id=f"request-{suffix * 8}",
        payload={},
        owner_user_id=None,
    )
    session.add(job)
    session.commit()
    return job


def _item(
    session: Session, batch: GenerationBatch, job: Job, *, ordinal: int = 0
) -> GenerationItem:
    item = GenerationItem(
        id=new_id(),
        batch_id=batch.id,
        ordinal=ordinal,
        job_id=job.id,
        request_reference=f"generation-item-{ordinal}-{job.id}",
        requested_seed=ordinal,
        reserved_budget_micros=batch.per_item_ceiling_micros,
    )
    session.add(item)
    session.commit()
    return item


def _attempt(session: Session, job: Job, *, attempt: int) -> JobAttempt:
    job_attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=attempt,
        status="running",
        lease_token="d" * 64,
    )
    session.add(job_attempt)
    session.commit()
    return job_attempt


def _finish_successful_attempt(
    session: Session, attempt: JobAttempt, *, result_code: str, finished_at: datetime
) -> None:
    session.execute(
        update(JobAttempt)
        .where(JobAttempt.id == attempt.id)
        .values(
            status="raw_stored",
            result_code=result_code,
            error_code=None,
            finished_at=finished_at,
        )
    )
    session.commit()


def test_batch_requires_approved_authorities_and_has_immutable_configuration(
    session: Session,
) -> None:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="unapproved-policy-v1",
        content={"subject": "synthetic"},
        content_digest="1" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="unapproved-prompt-v1",
        content={"template": "fixture"},
        content_digest="2" * 64,
    )
    session.add_all((policy, prompt))
    session.commit()
    session.add(
        GenerationBatch(
            id=new_id(),
            idempotency_key_hash="3" * 64,
            generation_policy_id=policy.id,
            prompt_template_id=prompt.id,
            provider_reference="deterministic-mock",
            model_reference="non-human-fixture",
            model_version_reference="fixture-v1",
            pricing_snapshot_reference="pricing-fixture-v1",
            output_media_type="image/png",
            output_width=1,
            output_height=1,
            output_max_bytes=1024,
            item_count=1,
            currency="CNY",
            hard_budget_micros=100,
            per_item_ceiling_micros=100,
            retry_ceiling=1,
            concurrency_ceiling=1,
        )
    )
    with pytest.raises(DBAPIError, match="requires approved policy and prompt"):
        session.commit()
    session.rollback()

    batch = _batch(session)
    with pytest.raises(DBAPIError, match="configuration is immutable"):
        session.execute(
            update(GenerationBatch)
            .where(GenerationBatch.id == batch.id)
            .values(model_version_reference="fixture-v2")
        )
    session.rollback()
    batch.model_reference = "changed-model"
    with pytest.raises(ValueError, match="generation batch configuration is immutable"):
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(delete(GenerationBatch).where(GenerationBatch.id == batch.id))
    session.rollback()


def test_reference_only_job_and_item_bounds_are_database_authoritative(session: Session) -> None:
    batch = _batch(session)
    invalid_job = Job(
        id=new_id(),
        job_type="synthetic_generation",
        status="pending",
        idempotency_key_hash="4" * 64,
        request_id="invalid-payload-request",
        payload={"generation_item_id": new_id()},
    )
    session.add(invalid_job)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    job = _job(session, suffix="e")
    invalid_item = GenerationItem(
        id=new_id(),
        batch_id=batch.id,
        ordinal=batch.item_count,
        job_id=job.id,
        request_reference=f"out-of-range-{job.id}",
        reserved_budget_micros=batch.per_item_ceiling_micros,
    )
    session.add(invalid_item)
    with pytest.raises(DBAPIError, match="exceeds batch bounds"):
        session.commit()
    session.rollback()

    item = _item(session, batch, job)
    with pytest.raises(DBAPIError, match="generation item authority is immutable"):
        session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(reserved_budget_micros=1)
        )
    session.rollback()


def test_timestamp_opaque_reference_and_operator_actor_shapes_are_enforced(
    session: Session,
) -> None:
    batch = _batch(session)
    with pytest.raises(IntegrityError):
        session.execute(
            update(GenerationBatch)
            .where(GenerationBatch.id == batch.id)
            .values(cancel_requested_at=batch.created_at - timedelta(seconds=1))
        )
    session.rollback()

    job = _job(session, suffix="t")
    item = _item(session, batch, job)
    attempt = _attempt(session, job, attempt=1)
    with pytest.raises(IntegrityError):
        session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(
                status="GENERATING",
                started_at=item.created_at - timedelta(seconds=1),
            )
        )
    session.rollback()
    now = utcnow()
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="GENERATING", started_at=now)
    )
    session.commit()
    session.add(
        SyntheticGenerationEvidence(
            id=new_id(),
            generation_item_id=item.id,
            job_attempt_id=attempt.id,
            provider_reference=batch.provider_reference,
            model_reference=batch.model_reference,
            model_version_reference=batch.model_version_reference,
            provider_run_reference="invalid-safety-reason-run",
            safety_policy_reference="safety-fixture-v1",
            safety_outcome="passed",
            safety_reason_code="INVALID REASON",
            retention_status="not_retained",
            output_rights="internal_evaluation_only",
            provider_actual_seed=None,
            provider_actual_parameters={},
            reproducibility_level="BIT_EXACT",
            generated_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    source = SyntheticSourceObject(
        id=new_id(),
        generation_item_id=item.id,
        job_attempt_id=attempt.id,
        storage_reference=f"raw/source/{item.id}",
        sha256="d" * 64,
        media_type="image/png",
        byte_size=68,
        width=1,
        height=1,
        retention_expires_at=now + timedelta(days=1),
    )
    session.add(source)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    source.storage_reference = f"raw-source-{item.id}"
    session.add(source)
    session.commit()
    session.add(
        SyntheticSourceObjectDeletionEvidence(
            id=new_id(),
            source_object_id=source.id,
            reason_code="operator_cleanup",
            deletion_result="deleted",
            actor_kind="operator",
            actor_reference=None,
            deleted_at=source.created_at + timedelta(seconds=1),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_queue_and_terminal_batch_aggregates_are_database_authoritative(
    session: Session,
) -> None:
    batch = _batch(session, item_count=2)
    first_job = _job(session, suffix="q")
    first_item = _item(session, batch, first_job, ordinal=0)
    now = utcnow()
    with pytest.raises(DBAPIError, match="complete item set"):
        session.execute(
            update(GenerationBatch)
            .where(GenerationBatch.id == batch.id)
            .values(status="QUEUED", queued_at=now)
        )
    session.rollback()

    second_job = _job(session, suffix="r")
    second_item = _item(session, batch, second_job, ordinal=1)
    now = utcnow()
    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="QUEUED", queued_at=now)
    )
    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="RUNNING", started_at=now)
    )
    for item in (first_item, second_item):
        session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(status="GENERATING", started_at=now)
        )
        session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(
                status="GENERATION_FAILED",
                finalized_at=now,
                result_code="provider_failed",
            )
        )
    session.commit()

    with pytest.raises(DBAPIError, match="requires all items raw stored"):
        session.execute(
            update(GenerationBatch)
            .where(GenerationBatch.id == batch.id)
            .values(status="COMPLETED", finalized_at=now)
        )
    session.rollback()
    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="FAILED", finalized_at=now)
    )
    session.commit()


def test_raw_stored_requires_complete_chain_and_matching_successful_attempt(
    session: Session,
) -> None:
    batch = _batch(session)
    job = _job(session, suffix="s")
    item = _item(session, batch, job)
    attempt = _attempt(session, job, attempt=1)
    now = utcnow()
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="GENERATING", started_at=now)
    )
    session.commit()

    with pytest.raises(DBAPIError, match="complete source evidence and cost chain"):
        session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(status="RAW_STORED", finalized_at=now, result_code="raw_stored")
        )
    session.rollback()

    session.add_all(
        (
            SyntheticSourceObject(
                id=new_id(),
                generation_item_id=item.id,
                job_attempt_id=attempt.id,
                storage_reference=f"raw-chain-{item.id}",
                sha256="e" * 64,
                media_type="image/png",
                byte_size=68,
                width=1,
                height=1,
                retention_expires_at=now + timedelta(days=1),
            ),
            SyntheticGenerationEvidence(
                id=new_id(),
                generation_item_id=item.id,
                job_attempt_id=attempt.id,
                provider_reference=batch.provider_reference,
                model_reference=batch.model_reference,
                model_version_reference=batch.model_version_reference,
                provider_run_reference="provider-run-chain",
                safety_policy_reference="safety-fixture-v1",
                safety_outcome="passed",
                safety_reason_code="fixture_passed",
                retention_status="not_retained",
                output_rights="internal_evaluation_only",
                provider_actual_seed=None,
                provider_actual_parameters={},
                reproducibility_level="BIT_EXACT",
                generated_at=now,
            ),
            ProviderCostEvent(
                id=new_id(),
                generation_item_id=item.id,
                job_attempt_id=attempt.id,
                event_kind="final",
                currency="CNY",
                amount_micros=100,
                pricing_snapshot_reference=batch.pricing_snapshot_reference,
                occurred_at=now,
            ),
        )
    )
    session.commit()
    with pytest.raises(DBAPIError, match="matching successful attempt"):
        session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(status="RAW_STORED", finalized_at=now, result_code="raw_stored")
        )
    session.rollback()

    _finish_successful_attempt(session, attempt, result_code="raw_stored", finished_at=now)
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="RAW_STORED", finalized_at=now, result_code="raw_stored")
    )
    session.commit()


def test_batch_and_item_states_are_monotonic_and_distinguish_generation_failure(
    session: Session,
) -> None:
    batch = _batch(session)
    job = _job(session, suffix="f")
    item = _item(session, batch, job)
    now = utcnow()

    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="QUEUED", queued_at=now)
    )
    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="RUNNING", started_at=now)
    )
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="GENERATING", started_at=now)
    )
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="GENERATION_FAILED", finalized_at=now, result_code="provider_failed")
    )
    session.commit()

    with pytest.raises(DBAPIError, match="invalid generation item transition"):
        session.execute(
            update(GenerationItem)
            .where(GenerationItem.id == item.id)
            .values(status="GENERATING", finalized_at=None, result_code=None)
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="invalid generation item transition"):
        session.execute(
            update(GenerationItem).where(GenerationItem.id == item.id).values(status="REJECTED")
        )
    session.rollback()

    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="FAILED", finalized_at=now)
    )
    session.commit()
    with pytest.raises(DBAPIError, match="invalid generation batch transition"):
        session.execute(
            update(GenerationBatch)
            .where(GenerationBatch.id == batch.id)
            .values(status="RUNNING", finalized_at=None)
        )
    session.rollback()


def test_generation_evidence_source_bounds_and_budget_are_append_only(session: Session) -> None:
    batch = _batch(session)
    job = _job(session, suffix="6")
    item = _item(session, batch, job)
    attempt = _attempt(session, job, attempt=1)
    now = utcnow()
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="GENERATING", started_at=now)
    )
    session.commit()

    wrong_evidence = SyntheticGenerationEvidence(
        id=new_id(),
        generation_item_id=item.id,
        job_attempt_id=attempt.id,
        provider_reference="different-provider",
        model_reference=batch.model_reference,
        model_version_reference=batch.model_version_reference,
        provider_run_reference="provider-run-1",
        safety_policy_reference="safety-fixture-v1",
        safety_outcome="passed",
        safety_reason_code="fixture_passed",
        retention_status="not_retained",
        output_rights="internal_evaluation_only",
        provider_actual_seed=None,
        provider_actual_parameters={},
        reproducibility_level="BIT_EXACT",
        generated_at=now,
    )
    session.add(wrong_evidence)
    with pytest.raises(DBAPIError, match="differs from pinned batch provider"):
        session.commit()
    session.rollback()

    evidence = SyntheticGenerationEvidence(
        id=new_id(),
        generation_item_id=item.id,
        job_attempt_id=attempt.id,
        provider_reference=batch.provider_reference,
        model_reference=batch.model_reference,
        model_version_reference=batch.model_version_reference,
        provider_run_reference="provider-run-1",
        safety_policy_reference="safety-fixture-v1",
        safety_outcome="passed",
        safety_reason_code="fixture_passed",
        retention_status="not_retained",
        output_rights="internal_evaluation_only",
        provider_actual_seed=None,
        provider_actual_parameters={},
        reproducibility_level="BIT_EXACT",
        generated_at=now,
    )
    source = SyntheticSourceObject(
        id=new_id(),
        generation_item_id=item.id,
        job_attempt_id=attempt.id,
        storage_reference=f"raw-source-{item.id}",
        sha256="7" * 64,
        media_type="image/png",
        byte_size=68,
        width=1,
        height=1,
        retention_expires_at=now + timedelta(days=1),
    )
    cost = ProviderCostEvent(
        id=new_id(),
        generation_item_id=item.id,
        job_attempt_id=attempt.id,
        event_kind="final",
        currency="CNY",
        amount_micros=100,
        pricing_snapshot_reference=batch.pricing_snapshot_reference,
        occurred_at=now,
    )
    session.add_all((evidence, source, cost))
    session.commit()

    second_attempt = _attempt(session, job, attempt=2)
    session.add(
        ProviderCostEvent(
            id=new_id(),
            generation_item_id=item.id,
            job_attempt_id=second_attempt.id,
            event_kind="estimated",
            currency="CNY",
            amount_micros=1,
            pricing_snapshot_reference=batch.pricing_snapshot_reference,
            occurred_at=now,
        )
    )
    with pytest.raises(DBAPIError, match="exceeds reserved budget"):
        session.commit()
    session.rollback()

    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            update(SyntheticGenerationEvidence)
            .where(SyntheticGenerationEvidence.id == evidence.id)
            .values(provider_run_reference="changed-run")
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            update(SyntheticSourceObject)
            .where(SyntheticSourceObject.id == source.id)
            .values(sha256="8" * 64)
        )
    session.rollback()


def test_source_cleanup_appends_evidence_without_deleting_metadata(session: Session) -> None:
    batch = _batch(session)
    job = _job(session, suffix="9")
    item = _item(session, batch, job)
    attempt = _attempt(session, job, attempt=1)
    now = utcnow()
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="GENERATING", started_at=now)
    )
    session.commit()
    source = SyntheticSourceObject(
        id=new_id(),
        generation_item_id=item.id,
        job_attempt_id=attempt.id,
        storage_reference=f"raw-cleanup-{item.id}",
        sha256="a" * 64,
        media_type="image/png",
        byte_size=68,
        width=1,
        height=1,
        retention_expires_at=now + timedelta(days=1),
    )
    session.add(source)
    session.commit()

    session.add(
        SyntheticSourceObjectDeletionEvidence(
            id=new_id(),
            source_object_id=source.id,
            reason_code="retention_expired",
            deletion_result="deleted",
            actor_kind="system",
            deleted_at=now,
        )
    )
    with pytest.raises(DBAPIError, match="retention has not expired"):
        session.commit()
    session.rollback()

    deletion_evidence = SyntheticSourceObjectDeletionEvidence(
        id=new_id(),
        source_object_id=source.id,
        reason_code="orphan_cleanup",
        deletion_result="not_found",
        actor_kind="system",
        deleted_at=source.created_at + timedelta(seconds=1),
    )
    session.add(deletion_evidence)
    session.commit()
    assert session.get(SyntheticSourceObject, source.id) is not None

    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            update(SyntheticSourceObjectDeletionEvidence)
            .where(SyntheticSourceObjectDeletionEvidence.id == deletion_evidence.id)
            .values(reason_code="changed_reason")
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(delete(SyntheticSourceObject).where(SyntheticSourceObject.id == source.id))
    session.rollback()


def test_concurrent_cost_events_cannot_exceed_item_reservation(session: Session) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    batch = _batch(session)
    job = _job(session, suffix="0")
    item = _item(session, batch, job)
    first_attempt = _attempt(session, job, attempt=1)
    second_attempt = _attempt(session, job, attempt=2)
    barrier = Barrier(2)

    def post_cost(attempt_id: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                barrier.wait(timeout=5)
                worker_session.add(
                    ProviderCostEvent(
                        id=new_id(),
                        generation_item_id=item.id,
                        job_attempt_id=attempt_id,
                        event_kind="final",
                        currency="CNY",
                        amount_micros=60,
                        pricing_snapshot_reference=batch.pricing_snapshot_reference,
                        occurred_at=utcnow(),
                    )
                )
                try:
                    worker_session.commit()
                except DBAPIError:
                    worker_session.rollback()
                    return "budget_rejected"
                return "committed"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(post_cost, (first_attempt.id, second_attempt.id)))

    assert sorted(results) == ["budget_rejected", "committed"]
    total = session.execute(
        text(
            "SELECT COALESCE(SUM(amount_micros), 0) FROM provider_cost_events "
            "WHERE generation_item_id = :item_id"
        ),
        {"item_id": item.id},
    ).scalar_one()
    assert total == 60


def test_cost_trigger_uses_batch_before_item_lock_order(session: Session) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    batch = _batch(session)
    job = _job(session, suffix="l")
    item = _item(session, batch, job)
    attempt = _attempt(session, job, attempt=1)
    now = utcnow()
    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="QUEUED", queued_at=now, updated_at=now)
    )
    session.execute(
        update(GenerationBatch)
        .where(GenerationBatch.id == batch.id)
        .values(status="RUNNING", started_at=now, updated_at=now)
    )
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="GENERATING", started_at=now, updated_at=now)
    )
    session.commit()

    writer_engine = create_engine(
        database_url,
        connect_args={"application_name": "p2_m2_cost_lock_order_writer"},
    )
    blocker_engine = create_engine(database_url)
    observer_engine = create_engine(database_url)

    def post_cost() -> None:
        with writer_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '3s'"))
            connection.execute(
                text(
                    "INSERT INTO provider_cost_events "
                    "(id, schema_version, generation_item_id, job_attempt_id, event_kind, "
                    "currency, amount_micros, pricing_snapshot_reference, occurred_at, created_at) "
                    "VALUES (:id, 'mirror.synthetic-dataset/ProviderCostEvent/v1', :item_id, "
                    ":attempt_id, 'final', 'CNY', 10, :pricing, :now, :now)"
                ),
                {
                    "id": new_id(),
                    "item_id": item.id,
                    "attempt_id": attempt.id,
                    "pricing": batch.pricing_snapshot_reference,
                    "now": now,
                },
            )

    try:
        with blocker_engine.connect() as blocker:
            transaction = blocker.begin()
            blocker.execute(text("SET LOCAL lock_timeout = '3s'"))
            blocker.execute(
                text("SELECT id FROM generation_batches WHERE id = :id FOR UPDATE"),
                {"id": batch.id},
            )
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(post_cost)
                deadline = time.monotonic() + 3
                waiting = False
                while time.monotonic() < deadline:
                    with observer_engine.connect() as observer:
                        waiting = bool(
                            observer.execute(
                                text(
                                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                    "WHERE application_name = 'p2_m2_cost_lock_order_writer' "
                                    "AND wait_event_type = 'Lock')"
                                )
                            ).scalar_one()
                        )
                    if waiting:
                        break
                    time.sleep(0.02)
                assert waiting, "cost writer did not block on the batch authority lock"

                blocker.execute(
                    text(
                        "UPDATE generation_items SET status = 'GENERATION_FAILED', "
                        "result_code = 'provider_failed', finalized_at = :now, updated_at = :now "
                        "WHERE id = :id"
                    ),
                    {"id": item.id, "now": now},
                )
                blocker.execute(
                    text(
                        "UPDATE generation_batches SET status = 'FAILED', finalized_at = :now, "
                        "updated_at = :now WHERE id = :id"
                    ),
                    {"id": batch.id, "now": now},
                )
                transaction.commit()
                future.result(timeout=5)
    finally:
        writer_engine.dispose()
        blocker_engine.dispose()
        observer_engine.dispose()

    assert (
        session.scalar(
            select(func.count())
            .select_from(ProviderCostEvent)
            .where(ProviderCostEvent.generation_item_id == item.id)
        )
        == 1
    )
