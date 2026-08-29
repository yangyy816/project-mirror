from __future__ import annotations

import os
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mirror_api.config import get_settings
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
    SyntheticIdentity,
    SyntheticPromptTemplate,
    SyntheticQAMeasurement,
    SyntheticQAPolicy,
    SyntheticQAReviewDecision,
    SyntheticQARun,
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
                "TRUNCATE TABLE synthetic_identities, synthetic_qa_review_decisions, "
                "synthetic_qa_measurements, synthetic_qa_runs, synthetic_asset_records, "
                "synthetic_source_object_deletion_evidence, provider_cost_events, "
                "synthetic_generation_evidence, synthetic_source_objects, generation_items, "
                "generation_batches, job_attempts, jobs, synthetic_qa_policies, "
                "synthetic_generation_policies, synthetic_prompt_templates, assets, "
                "offline_synthetic_source_admissions CASCADE"
            )
        )
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _approved_generation_authorities(session: Session) -> tuple[str, str]:
    policy = SyntheticGenerationPolicy(
        id=new_id(),
        version="m3-generation-fixture-v1",
        content={"subject": "synthetic"},
        content_digest="a" * 64,
    )
    prompt = SyntheticPromptTemplate(
        id=new_id(),
        version="m3-prompt-fixture-v1",
        content={"template": "redacted-reference"},
        content_digest="b" * 64,
    )
    session.add_all((policy, prompt))
    session.commit()
    for model, record_id in (
        (SyntheticGenerationPolicy, policy.id),
        (SyntheticPromptTemplate, prompt.id),
    ):
        session.execute(
            update(model)
            .where(model.id == record_id)
            .values(approval_status="APPROVED", approved_at=text("now()"))
        )
    session.commit()
    return policy.id, prompt.id


def _raw_source(session: Session) -> SyntheticSourceObject:
    generation_policy_id, prompt_template_id = _approved_generation_authorities(session)
    batch = GenerationBatch(
        id=new_id(),
        idempotency_key_hash="c" * 64,
        generation_policy_id=generation_policy_id,
        prompt_template_id=prompt_template_id,
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
    job = Job(
        id=new_id(),
        job_type="synthetic_generation",
        status="pending",
        idempotency_key_hash="d" * 64,
        request_id="request-m3-fixture",
        payload={},
        owner_user_id=None,
    )
    session.add_all((batch, job))
    session.commit()
    item = GenerationItem(
        id=new_id(),
        batch_id=batch.id,
        ordinal=0,
        job_id=job.id,
        request_reference="generation-item-m3-fixture",
        requested_seed=0,
        reserved_budget_micros=100,
    )
    attempt = JobAttempt(
        id=new_id(), job_id=job.id, attempt=1, status="running", lease_token="e" * 64
    )
    session.add_all((item, attempt))
    session.commit()
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
        storage_reference=f"raw-m3-{item.id}",
        sha256="f" * 64,
        media_type="image/png",
        byte_size=68,
        width=1,
        height=1,
        retention_expires_at=now + timedelta(days=1),
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
                provider_run_reference="provider-run-m3-fixture",
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
    session.execute(
        update(JobAttempt)
        .where(JobAttempt.id == attempt.id)
        .values(
            status="raw_stored",
            result_code="raw_stored",
            error_code=None,
            finished_at=now,
        )
    )
    session.commit()
    session.execute(
        update(GenerationItem)
        .where(GenerationItem.id == item.id)
        .values(status="RAW_STORED", finalized_at=now, result_code="raw_stored")
    )
    session.commit()
    return source


def _normalized_record(session: Session) -> tuple[SyntheticAssetRecord, Asset]:
    source = _raw_source(session)
    record = SyntheticAssetRecord(
        id=new_id(),
        source_object_id=source.id,
        normalizer_version="image-sanitizer-v1",
        normalizer_config_digest="1" * 64,
    )
    session.add(record)
    session.commit()
    now = utcnow()
    with pytest.raises(DBAPIError, match="protected by active normalization"):
        session.add(
            SyntheticSourceObjectDeletionEvidence(
                id=new_id(),
                source_object_id=source.id,
                reason_code="manual_cleanup",
                deletion_result="deleted",
                actor_kind="system",
                actor_reference=None,
                deleted_at=now,
            )
        )
        session.commit()
    session.rollback()
    session.execute(
        update(SyntheticAssetRecord)
        .where(SyntheticAssetRecord.id == record.id)
        .values(status="NORMALIZING", normalization_started_at=now)
    )
    session.commit()
    asset = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=f"normalized-m3-{record.id}",
        mime_type="image/jpeg",
        byte_size=631,
        width=1,
        height=1,
        sha256="2" * 64,
        synthetic=True,
        is_ai_generated=True,
    )
    session.add(asset)
    session.commit()
    session.execute(
        update(SyntheticAssetRecord)
        .where(SyntheticAssetRecord.id == record.id)
        .values(status="NORMALIZED", normalized_asset_id=asset.id, normalized_at=now)
    )
    session.commit()
    session.refresh(record)
    return record, asset


def _approved_qa_policy(session: Session) -> SyntheticQAPolicy:
    policy = SyntheticQAPolicy(
        id=new_id(),
        version="m3-qa-fixture-v1",
        content={"required_reviews": ["adult_presentation", "likeness_risk", "license_rights"]},
        content_digest="3" * 64,
    )
    session.add(policy)
    session.commit()
    session.execute(
        update(SyntheticQAPolicy)
        .where(SyntheticQAPolicy.id == policy.id)
        .values(approval_status="APPROVED", approved_at=text("now()"))
    )
    session.commit()
    return policy


def test_normalization_qa_and_identity_authority_is_monotonic_and_non_bypassable(
    session: Session,
) -> None:
    record, asset = _normalized_record(session)
    qa_policy = _approved_qa_policy(session)
    qa_run = SyntheticQARun(
        id=new_id(),
        synthetic_asset_record_id=record.id,
        normalized_asset_id=asset.id,
        qa_policy_id=qa_policy.id,
        vision_provider_reference="deterministic-mock",
        vision_algorithm_reference="fixture-observation-v1",
    )
    session.add(qa_run)
    session.commit()
    session.refresh(record)
    assert record.status == "QA_PENDING"

    now = utcnow()
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="RUNNING", started_at=now)
    )
    session.commit()
    session.refresh(record)
    assert record.status == "QA_RUNNING"

    measurement = SyntheticQAMeasurement(
        id=new_id(),
        qa_run_id=qa_run.id,
        measurement_kind="face_count",
        measurement_code="exactly_one_face",
        payload={"count": 1},
        payload_digest="4" * 64,
        algorithm_reference="mirror.fixture/face-count",
        algorithm_version="v1",
        confidence=None,
        hard_gate=True,
        threshold_outcome="PASSED",
        reason_code="exactly_one_face",
    )
    session.add(measurement)
    session.commit()
    with pytest.raises(DBAPIError, match="mandatory human reviews"):
        session.execute(
            update(SyntheticQARun)
            .where(SyntheticQARun.id == qa_run.id)
            .values(status="PASSED", finalized_at=utcnow())
        )
        session.commit()
    session.rollback()

    for review_kind in ("adult_presentation", "likeness_risk", "license_rights"):
        session.add(
            SyntheticQAReviewDecision(
                id=new_id(),
                qa_run_id=qa_run.id,
                review_kind=review_kind,
                decision="PASSED",
                reason_code=f"{review_kind}_passed",
                actor_reference="operator:m3-reviewer",
                reviewed_at=now,
                created_at=utcnow(),
            )
        )
    session.commit()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            update(SyntheticQAMeasurement)
            .where(SyntheticQAMeasurement.id == measurement.id)
            .values(threshold_outcome="FAILED")
        )
        session.commit()
    session.rollback()

    finalized_at = utcnow()
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="PASSED", finalized_at=finalized_at)
    )
    session.commit()
    session.refresh(record)
    assert record.status == "QA_PASSED"

    identity = SyntheticIdentity(
        id=new_id(),
        canonical_asset_id=asset.id,
        accepted_qa_run_id=qa_run.id,
        generator_provider=None,
        generator_model=None,
        prompt_version=None,
        provenance=None,
        adult_synthetic_attested=True,
    )
    session.add(identity)
    session.commit()
    session.refresh(record)
    assert identity.bank_version_id is None
    assert record.status == "IDENTITY_REGISTERED"
    with pytest.raises(ValueError, match="immutable record"):
        identity.generator_provider = "invented-provider"
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic identity authority is immutable"):
        session.execute(delete(SyntheticIdentity).where(SyntheticIdentity.id == identity.id))
        session.commit()
    session.rollback()


def test_qa_policy_and_canonical_identity_links_fail_closed(session: Session) -> None:
    record, asset = _normalized_record(session)
    unapproved_policy = SyntheticQAPolicy(
        id=new_id(),
        version="m3-unapproved-qa-v1",
        content={"kind": "fixture"},
        content_digest="5" * 64,
    )
    session.add(unapproved_policy)
    session.commit()
    with pytest.raises(DBAPIError, match="approved QA policy"):
        session.add(
            SyntheticQARun(
                id=new_id(),
                synthetic_asset_record_id=record.id,
                normalized_asset_id=asset.id,
                qa_policy_id=unapproved_policy.id,
            )
        )
        session.commit()
    session.rollback()
    assert (
        session.scalar(
            select(SyntheticIdentity).where(SyntheticIdentity.canonical_asset_id == asset.id)
        )
        is None
    )
    with pytest.raises(ValueError, match="canonical synthetic identity links are required"):
        session.add(SyntheticIdentity(id=new_id(), adult_synthetic_attested=True))
        session.commit()
    session.rollback()


def test_m3_evidence_and_lineage_are_append_only(session: Session) -> None:
    record, asset = _normalized_record(session)
    with pytest.raises(DBAPIError, match="lineage is immutable"):
        session.execute(
            update(SyntheticAssetRecord)
            .where(SyntheticAssetRecord.id == record.id)
            .values(normalizer_config_digest="6" * 64)
        )
        session.commit()
    session.rollback()
    with pytest.raises(IntegrityError):
        session.add(
            SyntheticAssetRecord(
                id=new_id(),
                source_object_id=record.source_object_id,
                normalizer_version="image-sanitizer-v1",
                normalizer_config_digest="7" * 64,
            )
        )
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(delete(SyntheticAssetRecord).where(SyntheticAssetRecord.id == record.id))
        session.commit()
    session.rollback()
    assert asset.owner_user_id is None


def test_0010_downgrade_fails_closed_when_m3_authority_exists(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    record, _ = _normalized_record(session)
    assert record.status == "NORMALIZED"
    session.close()

    database_url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    with pytest.raises(DBAPIError, match="0010 downgrade would discard M3"):
        command.downgrade(config, "0009_generation_batch_pipeline")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "demo_0011_d03_job_recovery"
        )
    engine.dispose()
    get_settings.cache_clear()
