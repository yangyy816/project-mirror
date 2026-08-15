from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mirror_api.models import (
    AccountDeletionEvent,
    AccountDeletionRequest,
    AestheticProfile,
    AestheticProfileVersion,
    Asset,
    AssetAccessAudit,
    AssetDeletionEvent,
    AssetDeletionRequest,
    AssetIngestionRecord,
    AssetVariant,
    BaselineFaceModel,
    ConsentRecord,
    CreditAccount,
    CreditLedger,
    DataExportEvent,
    DataExportRequest,
    DesiredDeltaProfileVersion,
    EditingSession,
    IdentityConstraintVersion,
    ImageVersion,
    Job,
    JobAttempt,
    ObjectDeletionEvidence,
    QuestionBankVersion,
    QuestionnaireRun,
    SelfState,
    StyleProfileVersion,
    UploadIntent,
    UploadIntentEvent,
    User,
    new_id,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Session:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE question_bank_versions, users CASCADE"))
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def make_asset(user_id: str, role: str, suffix: str) -> Asset:
    return Asset(
        id=new_id(),
        owner_user_id=user_id,
        asset_role=role,
        storage_key=f"users/fixture/assets/{suffix}",
        mime_type="image/png",
        byte_size=100,
        width=10,
        height=10,
        sha256=(suffix[0] if suffix else "f") * 64,
        synthetic=True,
    )


def create_profile_fixture(
    session: Session, phone_seed: str = "a"
) -> tuple[User, AestheticProfile, AestheticProfileVersion]:
    user = User(id=new_id(), phone_hash=phone_seed * 64)
    baseline_asset = make_asset(user.id, "original", f"baseline-{phone_seed}")
    session.add(user)
    session.commit()
    session.add(baseline_asset)
    session.commit()
    baseline = BaselineFaceModel(
        id=new_id(),
        user_id=user.id,
        source_asset_id=baseline_asset.id,
        version=1,
        analyzer_provider="deterministic_fixture",
        analyzer_version="fixture-v1",
        analysis_schema_version="analysis-v1",
        measurement_normalization_version="normalization-v1",
    )
    session.add(baseline)
    session.commit()
    self_state = SelfState(
        id=new_id(),
        user_id=user.id,
        version=1,
        baseline_face_model_id=baseline.id,
        reliable_dimensions=["fixture_dimension"],
        identity_anchor_reference={"kind": "synthetic_numeric_fixture"},
        state_schema_version="self-state-v1",
        derivation_algorithm_version="derivation-v1",
    )
    session.add(self_state)
    session.commit()
    desired_delta = DesiredDeltaProfileVersion(
        id=new_id(),
        user_id=user.id,
        version=1,
        self_state_version_id=self_state.id,
        inference_algorithm_version="inference-v1",
        evidence_fusion_version="fusion-v1",
        source="synthetic_fixture",
    )
    style = StyleProfileVersion(
        id=new_id(),
        user_id=user.id,
        version=1,
        inference_algorithm_version="style-v1",
    )
    constraints = IdentityConstraintVersion(
        id=new_id(),
        user_id=user.id,
        version=1,
        self_state_version_id=self_state.id,
        source="explicit_fixture",
    )
    profile = AestheticProfile(id=new_id(), user_id=user.id)
    version = AestheticProfileVersion(
        id=new_id(),
        profile_id=profile.id,
        version=1,
        self_state_version_id=self_state.id,
        desired_delta_profile_version_id=desired_delta.id,
        style_profile_version_id=style.id,
        identity_constraint_version_id=constraints.id,
        source="questionnaire",
        reason="initial profile fixture",
        profile_generation_version="profile-v1",
    )
    session.add_all([desired_delta, style, constraints, profile])
    session.commit()
    session.add(version)
    session.commit()
    return user, profile, version


def test_profile_versions_cannot_be_updated_or_deleted(session: Session) -> None:
    _, _, version = create_profile_fixture(session)
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            text("UPDATE aesthetic_profile_versions SET reason='overwrite' WHERE id=:id"),
            {"id": version.id},
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            text("DELETE FROM aesthetic_profile_versions WHERE id=:id"), {"id": version.id}
        )


def test_consent_history_is_append_only_and_supports_withdrawal(session: Session) -> None:
    user = User(id=new_id(), phone_hash="b" * 64)
    grant = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type="facial_data_processing",
        purpose="create_private_aesthetic_profile",
        purpose_version="purpose-v1",
        scope={"operations": ["landmark_detection"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="a" * 64,
        action="grant",
        granted_at=datetime.now(UTC),
        source="web_beta",
        request_id="consent-grant-fixture",
    )
    session.add(user)
    session.commit()
    session.add(grant)
    session.commit()

    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            text("UPDATE consent_records SET purpose='changed' WHERE id=:id"), {"id": grant.id}
        )
    session.rollback()

    withdrawal = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type=grant.consent_type,
        purpose=grant.purpose,
        purpose_version=grant.purpose_version,
        scope=grant.scope,
        policy_code=grant.policy_code,
        policy_version=grant.policy_version,
        policy_digest=grant.policy_digest,
        action="withdraw",
        supersedes_id=grant.id,
        withdrawn_at=datetime.now(UTC),
        source="web_beta",
        request_id="consent-withdraw-fixture",
    )
    session.add(withdrawal)
    session.commit()
    assert session.scalar(select(func.count()).select_from(ConsentRecord)) == 2

    duplicate_withdrawal = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type=grant.consent_type,
        purpose=grant.purpose,
        purpose_version=grant.purpose_version,
        scope=grant.scope,
        policy_code=grant.policy_code,
        policy_version=grant.policy_version,
        policy_digest=grant.policy_digest,
        action="withdraw",
        supersedes_id=grant.id,
        withdrawn_at=datetime.now(UTC),
        source="web_beta",
        request_id="duplicate-withdrawal-fixture",
    )
    session.add(duplicate_withdrawal)
    with pytest.raises(IntegrityError):
        session.commit()


def test_consent_withdrawal_must_match_the_referenced_grant(session: Session) -> None:
    now = datetime.now(UTC)
    owner = User(id=new_id(), phone_hash="1" * 64)
    other = User(id=new_id(), phone_hash="2" * 64)
    grant = ConsentRecord(
        id=new_id(),
        user_id=owner.id,
        consent_type="facial_data_processing",
        purpose="personal_aesthetic_baseline",
        purpose_version="purpose-v1",
        scope={"operations": ["private_upload"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="a" * 64,
        action="grant",
        granted_at=now,
        source="integration_fixture",
        request_id="matching-grant-fixture",
    )
    session.add_all((owner, other))
    session.commit()
    session.add(grant)
    session.commit()

    mismatched = ConsentRecord(
        id=new_id(),
        user_id=other.id,
        consent_type=grant.consent_type,
        purpose=grant.purpose,
        purpose_version=grant.purpose_version,
        scope=grant.scope,
        policy_code=grant.policy_code,
        policy_version=grant.policy_version,
        policy_digest=grant.policy_digest,
        action="withdraw",
        supersedes_id=grant.id,
        withdrawn_at=now,
        source="integration_fixture",
        request_id="mismatched-withdrawal-fixture",
    )
    session.add(mismatched)
    with pytest.raises(DBAPIError, match="exactly supersede"):
        session.commit()


def test_upload_intent_is_quarantine_control_and_events_are_append_only(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    user = User(id=new_id(), phone_hash="9" * 64, status="active")
    consent = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type="facial_data_processing",
        purpose="personal_aesthetic_baseline",
        purpose_version="purpose-v1",
        scope={"operations": ["private_upload", "security_validation"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="b" * 64,
        action="grant",
        granted_at=now,
        source="integration_fixture",
        request_id="upload-consent-fixture",
    )
    intent = UploadIntent(
        id=new_id(),
        owner_user_id=user.id,
        consent_record_id=consent.id,
        object_key=f"quarantine/v1/{new_id()}",
        declared_mime_type="image/png",
        declared_byte_size=128,
        declared_sha256="c" * 64,
        status="awaiting_upload",
        grant_expires_at=now + timedelta(minutes=5),
    )
    event = UploadIntentEvent(
        id=new_id(),
        upload_intent_id=intent.id,
        event_type="created",
        request_id="upload-intent-fixture",
        metadata_json={"schema_version": "upload-intent-v1"},
    )
    session.add(user)
    session.commit()
    session.add(consent)
    session.commit()
    session.add(intent)
    session.commit()
    session.add(event)
    session.commit()

    assert session.scalar(select(func.count()).select_from(Asset)) == 0
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            text("UPDATE upload_intent_events SET event_type='cancelled' WHERE id=:id"),
            {"id": event.id},
        )


@pytest.mark.parametrize(
    ("declared_byte_size", "declared_sha256"),
    ((0, "d" * 64), (20 * 1024 * 1024 + 1, "d" * 64), (128, "not-a-sha256")),
)
def test_upload_intent_declared_metadata_is_bounded(
    session: Session,
    declared_byte_size: int,
    declared_sha256: str,
) -> None:
    now = datetime.now(UTC)
    user = User(id=new_id(), phone_hash="3" * 64, status="active")
    consent = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type="facial_data_processing",
        purpose="personal_aesthetic_baseline",
        purpose_version="purpose-v1",
        scope={"operations": ["private_upload"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="e" * 64,
        action="grant",
        granted_at=now,
        source="integration_fixture",
        request_id="metadata-consent-fixture",
    )
    session.add(user)
    session.commit()
    session.add(consent)
    session.commit()
    session.add(
        UploadIntent(
            id=new_id(),
            owner_user_id=user.id,
            consent_record_id=consent.id,
            object_key=f"quarantine/v1/{new_id()}",
            declared_mime_type="image/png",
            declared_byte_size=declared_byte_size,
            declared_sha256=declared_sha256,
            status="awaiting_upload",
            grant_expires_at=now + timedelta(minutes=5),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_upload_intent_owner_must_own_the_bound_consent(session: Session) -> None:
    now = datetime.now(UTC)
    consent_owner = User(id=new_id(), phone_hash="4" * 64, status="active")
    other = User(id=new_id(), phone_hash="5" * 64, status="active")
    consent = ConsentRecord(
        id=new_id(),
        user_id=consent_owner.id,
        consent_type="facial_data_processing",
        purpose="personal_aesthetic_baseline",
        purpose_version="purpose-v1",
        scope={"operations": ["private_upload"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="f" * 64,
        action="grant",
        granted_at=now,
        source="integration_fixture",
        request_id="owner-consent-fixture",
    )
    session.add_all((consent_owner, other))
    session.commit()
    session.add(consent)
    session.commit()
    session.add(
        UploadIntent(
            id=new_id(),
            owner_user_id=other.id,
            consent_record_id=consent.id,
            object_key=f"quarantine/v1/{new_id()}",
            declared_mime_type="image/png",
            declared_byte_size=128,
            declared_sha256="6" * 64,
            status="awaiting_upload",
            grant_expires_at=now + timedelta(minutes=5),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_upload_intent_object_key_is_unique_under_concurrency(session: Session) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    now = datetime.now(UTC)
    user = User(id=new_id(), phone_hash="7" * 64, status="active")
    consent = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type="facial_data_processing",
        purpose="personal_aesthetic_baseline",
        purpose_version="purpose-v1",
        scope={"operations": ["private_upload"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="8" * 64,
        action="grant",
        granted_at=now,
        source="integration_fixture",
        request_id="concurrent-key-consent-fixture",
    )
    session.add(user)
    session.commit()
    session.add(consent)
    session.commit()
    object_key = f"quarantine/v1/{new_id()}"
    barrier = Barrier(2)
    engine = create_engine(database_url)

    def insert_intent() -> str:
        with Session(engine) as concurrent_session:
            concurrent_session.add(
                UploadIntent(
                    id=new_id(),
                    owner_user_id=user.id,
                    consent_record_id=consent.id,
                    object_key=object_key,
                    declared_mime_type="image/png",
                    declared_byte_size=128,
                    declared_sha256="9" * 64,
                    status="awaiting_upload",
                    grant_expires_at=now + timedelta(minutes=5),
                )
            )
            barrier.wait(timeout=5)
            try:
                concurrent_session.commit()
            except IntegrityError:
                concurrent_session.rollback()
                return "duplicate"
            return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _: insert_intent(), range(2)))
    engine.dispose()
    assert outcomes == ["created", "duplicate"]


def create_uploaded_ingestion_fixture(
    session: Session, phone_seed: str = "j"
) -> tuple[User, UploadIntent]:
    now = datetime.now(UTC)
    user = User(id=new_id(), phone_hash=phone_seed * 64, status="active")
    consent = ConsentRecord(
        id=new_id(),
        user_id=user.id,
        consent_type="facial_data_processing",
        purpose="personal_aesthetic_baseline",
        purpose_version="purpose-v1",
        scope={"operations": ["private_upload", "security_validation"]},
        policy_code="facial-data-policy",
        policy_version="privacy-v1",
        policy_digest="a" * 64,
        action="grant",
        granted_at=now,
        source="integration_fixture",
        request_id="ingestion-consent-fixture",
    )
    intent = UploadIntent(
        id=new_id(),
        owner_user_id=user.id,
        consent_record_id=consent.id,
        object_key=f"quarantine/v1/{new_id()}",
        declared_mime_type="image/png",
        declared_byte_size=128,
        declared_sha256="b" * 64,
        status="uploaded_unverified",
        grant_expires_at=now + timedelta(minutes=5),
        uploaded_at=now,
        quarantine_retention_deadline=now + timedelta(hours=1),
    )
    session.add(user)
    session.commit()
    session.add(consent)
    session.commit()
    session.add(intent)
    session.commit()
    return user, intent


def make_ingestion_job(user_id: str, intent_id: str, suffix: str) -> Job:
    return Job(
        id=new_id(),
        job_type="asset_ingestion",
        status="pending",
        idempotency_key_hash=suffix * 64,
        request_id=f"ingestion-job-{suffix}",
        payload={"schema_version": "ingestion-job-v1"},
        owner_user_id=user_id,
        ingestion_upload_intent_id=intent_id,
    )


def test_preclaim_cancelled_ingestion_job_has_no_attempt_or_evidence_and_is_immutable(
    session: Session,
) -> None:
    user, intent = create_uploaded_ingestion_fixture(session, "z")
    job = make_ingestion_job(user.id, intent.id, "y")
    session.add(job)
    session.commit()

    now = datetime.now(UTC)
    intent.status = "cancelled"
    intent.cancelled_at = now
    job.status = "cancelled"
    job.finalized_at = now
    job.result_code = "ingestion_cancelled_before_claim"
    session.commit()

    assert job.attempt_count == 0
    assert session.scalar(select(func.count()).select_from(JobAttempt)) == 0
    assert session.scalar(select(func.count()).select_from(AssetIngestionRecord)) == 0
    with pytest.raises(DBAPIError, match="cancelled ingestion job is immutable"):
        session.execute(
            text("UPDATE jobs SET result_code='rewritten' WHERE id=:id"), {"id": job.id}
        )


def test_ingestion_final_evidence_is_owner_bound_append_only_and_promoted_shape_is_strict(
    session: Session,
) -> None:
    user, intent = create_uploaded_ingestion_fixture(session)
    job = make_ingestion_job(user.id, intent.id, "c")
    session.add(job)
    session.commit()

    started_at = datetime.now(UTC)
    lease_token = new_id()
    job.status = "leased"
    job.attempt_count = 1
    job.lease_token = lease_token
    job.lease_acquired_at = started_at
    job.lease_expires_at = started_at + timedelta(minutes=5)
    intent.status = "processing"
    intent.processing_started_at = started_at
    session.flush()
    attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=1,
        status="leased",
        lease_token=lease_token,
    )
    session.add(attempt)
    session.commit()

    original = make_asset(user.id, "original", "ingestion-original")
    original.synthetic = False
    finished_at = datetime.now(UTC)
    session.add(original)
    session.flush()
    job.status = "promoted"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = finished_at
    job.result_asset_id = original.id
    job.result_code = "ingestion_promoted"
    intent.status = "promoted"
    intent.finalized_at = finished_at
    session.flush()
    session.add(
        AssetIngestionRecord(
            id=new_id(),
            owner_user_id=user.id,
            upload_intent_id=intent.id,
            job_id=job.id,
            outcome="promoted",
            result_asset_id=original.id,
            result_code="ingestion_promoted",
            sanitizer_version="image-sanitizer-v1",
            finalized_at=finished_at,
        )
    )
    attempt.status = "promoted"
    attempt.result_code = "ingestion_promoted"
    attempt.finished_at = finished_at
    session.commit()

    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            text(
                "UPDATE asset_ingestion_records SET result_code='overwritten' WHERE job_id=:job_id"
            ),
            {"job_id": job.id},
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="promoted ingestion asset identity"):
        session.execute(
            text("UPDATE assets SET synthetic=true WHERE id=:id"),
            {"id": original.id},
        )
    session.rollback()

    session.execute(
        text("UPDATE assets SET deleted_at=now() WHERE id=:id"),
        {"id": original.id},
    )
    session.commit()

    other = User(id=new_id(), phone_hash="d" * 64, status="active")
    other_asset = make_asset(other.id, "original", "other-original")
    other_asset.synthetic = False
    session.add(other)
    session.commit()
    session.add(other_asset)
    session.commit()
    with pytest.raises(DBAPIError):
        session.execute(
            text(
                "INSERT INTO asset_ingestion_records "
                "(id, owner_user_id, upload_intent_id, job_id, outcome, result_asset_id, "
                "result_code, sanitizer_version, finalized_at) "
                "VALUES (:id, :owner, :intent, :job, 'promoted', :asset, "
                "'ingestion_promoted', 'image-sanitizer-v1', now())"
            ),
            {
                "id": new_id(),
                "owner": user.id,
                "intent": intent.id,
                "job": job.id,
                "asset": other_asset.id,
            },
        )


def test_ingestion_rejected_record_cannot_reference_asset(session: Session) -> None:
    user, intent = create_uploaded_ingestion_fixture(session, "e")
    job = make_ingestion_job(user.id, intent.id, "f")
    session.add(job)
    session.commit()
    now = datetime.now(UTC)
    job.status = "leased"
    job.attempt_count = 1
    lease_token = new_id()
    job.lease_token = lease_token
    job.lease_acquired_at = now
    job.lease_expires_at = now + timedelta(minutes=5)
    intent.status = "processing"
    intent.processing_started_at = now
    session.flush()
    attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=1,
        status="leased",
        lease_token=lease_token,
    )
    session.add(attempt)
    session.commit()

    final_at = datetime.now(UTC)
    job.status = "rejected"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = final_at
    job.result_code = "invalid_image"
    intent.status = "rejected"
    intent.finalized_at = final_at
    attempt.status = "rejected"
    attempt.result_code = "invalid_image"
    attempt.finished_at = final_at
    session.flush()
    session.add(
        AssetIngestionRecord(
            id=new_id(),
            owner_user_id=user.id,
            upload_intent_id=intent.id,
            job_id=job.id,
            outcome="rejected",
            result_code="invalid_image",
            finalized_at=final_at,
        )
    )
    session.commit()

    with pytest.raises(DBAPIError):
        session.execute(
            text(
                "INSERT INTO asset_ingestion_records "
                "(id, owner_user_id, upload_intent_id, job_id, outcome, result_asset_id, "
                "result_code, sanitizer_version, finalized_at) "
                "VALUES (:id, :owner, :intent, :job, 'rejected', :asset, "
                "'invalid_image', NULL, now())"
            ),
            {
                "id": new_id(),
                "owner": user.id,
                "intent": intent.id,
                "job": job.id,
                "asset": new_id(),
            },
        )


def test_ingestion_job_and_attempt_states_must_commit_consistently(session: Session) -> None:
    user, intent = create_uploaded_ingestion_fixture(session, "r")
    job = make_ingestion_job(user.id, intent.id, "s")
    session.add(job)
    session.commit()

    first_started_at = datetime.now(UTC)
    first_lease_token = new_id()
    job.status = "leased"
    job.attempt_count = 1
    job.lease_token = first_lease_token
    job.lease_acquired_at = first_started_at
    job.lease_expires_at = first_started_at + timedelta(minutes=5)
    intent.status = "processing"
    intent.processing_started_at = first_started_at
    with pytest.raises(DBAPIError, match="current leased attempt"):
        session.commit()
    session.rollback()

    job = session.get(Job, job.id)
    intent = session.get(UploadIntent, intent.id)
    assert job is not None
    assert intent is not None
    job.status = "leased"
    job.attempt_count = 1
    job.lease_token = first_lease_token
    job.lease_acquired_at = first_started_at
    job.lease_expires_at = first_started_at + timedelta(minutes=5)
    intent.status = "processing"
    intent.processing_started_at = first_started_at
    first_attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=1,
        status="leased",
        lease_token=first_lease_token,
    )
    session.add(first_attempt)
    session.commit()

    job.status = "pending"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    with pytest.raises(DBAPIError, match="cannot retain a leased attempt"):
        session.commit()
    session.rollback()

    job = session.get(Job, job.id)
    first_attempt = session.get(JobAttempt, first_attempt.id)
    assert job is not None
    assert first_attempt is not None
    retry_finished_at = datetime.now(UTC)
    job.status = "pending"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    first_attempt.status = "retryable_failure"
    first_attempt.result_code = "storage_retryable"
    first_attempt.finished_at = retry_finished_at
    session.commit()

    second_started_at = retry_finished_at + timedelta(seconds=1)
    second_lease_token = new_id()
    job.status = "leased"
    job.attempt_count = 2
    job.lease_token = second_lease_token
    job.lease_acquired_at = second_started_at
    job.lease_expires_at = second_started_at + timedelta(minutes=5)
    second_attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=2,
        status="leased",
        lease_token=second_lease_token,
    )
    session.add(second_attempt)
    session.commit()

    finalized_at = second_started_at + timedelta(seconds=1)
    job.status = "rejected"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = finalized_at
    job.result_code = "invalid_image"
    intent.status = "rejected"
    intent.finalized_at = finalized_at
    second_attempt.status = "rejected"
    second_attempt.result_code = "different_result"
    second_attempt.finished_at = finalized_at
    session.add(
        AssetIngestionRecord(
            id=new_id(),
            owner_user_id=user.id,
            upload_intent_id=intent.id,
            job_id=job.id,
            outcome="rejected",
            result_code="invalid_image",
            finalized_at=finalized_at,
        )
    )
    with pytest.raises(DBAPIError, match="matching completed current attempt"):
        session.commit()
    session.rollback()

    job = session.get(Job, job.id)
    intent = session.get(UploadIntent, intent.id)
    second_attempt = session.get(JobAttempt, second_attempt.id)
    assert job is not None
    assert intent is not None
    assert second_attempt is not None
    job.status = "rejected"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = finalized_at
    job.result_code = "invalid_image"
    intent.status = "rejected"
    intent.finalized_at = finalized_at
    second_attempt.status = "rejected"
    second_attempt.result_code = "invalid_image"
    second_attempt.finished_at = finalized_at
    session.add(
        AssetIngestionRecord(
            id=new_id(),
            owner_user_id=user.id,
            upload_intent_id=intent.id,
            job_id=job.id,
            outcome="rejected",
            result_code="invalid_image",
            finalized_at=finalized_at,
        )
    )
    session.commit()


def test_ingestion_job_is_unique_per_intent_under_concurrency(session: Session) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    user, intent = create_uploaded_ingestion_fixture(session, "g")
    barrier = Barrier(2)
    engine = create_engine(database_url)

    def insert_job(suffix: str) -> str:
        with Session(engine) as concurrent_session:
            concurrent_session.add(make_ingestion_job(user.id, intent.id, suffix))
            barrier.wait(timeout=5)
            try:
                concurrent_session.commit()
            except IntegrityError:
                concurrent_session.rollback()
                return "duplicate"
            return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(insert_job, ("h", "i")))
    engine.dispose()
    assert outcomes == ["created", "duplicate"]


def test_credit_ledger_is_append_only_and_balance_is_aggregated(session: Session) -> None:
    user = User(id=new_id(), phone_hash="c" * 64)
    account = CreditAccount(id=new_id(), user_id=user.id)
    grant = CreditLedger(
        id=new_id(),
        account_id=account.id,
        amount=100,
        reason="beta_grant",
        reference_type="admin",
        reference_id="initial",
        idempotency_key_hash="d" * 64,
    )
    spend = CreditLedger(
        id=new_id(),
        account_id=account.id,
        amount=-15,
        reason="fixture_usage",
        reference_type="job",
        reference_id="job-fixture",
        idempotency_key_hash="e" * 64,
    )
    session.add(user)
    session.commit()
    session.add(account)
    session.commit()
    session.add_all([grant, spend])
    session.commit()
    assert (
        session.scalar(
            select(func.sum(CreditLedger.amount)).where(CreditLedger.account_id == account.id)
        )
        == 85
    )

    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(text("UPDATE credit_ledger SET amount=200 WHERE id=:id"), {"id": grant.id})
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(text("DELETE FROM credit_ledger WHERE id=:id"), {"id": grant.id})


def test_original_asset_and_image_lineage_are_enforced(session: Session) -> None:
    user, _, profile_version = create_profile_fixture(session, "f")
    original = make_asset(user.id, "original", "original")
    derived_zero = make_asset(user.id, "derived", "derived-zero")
    derived_one = make_asset(user.id, "derived", "derived-one")
    editing = EditingSession(
        id=new_id(),
        user_id=user.id,
        source_asset_id=original.id,
        profile_version_id=profile_version.id,
    )
    root_version = ImageVersion(
        id=new_id(),
        editing_session_id=editing.id,
        result_asset_id=derived_zero.id,
        sequence=0,
    )
    child_version = ImageVersion(
        id=new_id(),
        editing_session_id=editing.id,
        parent_version_id=root_version.id,
        result_asset_id=derived_one.id,
        sequence=1,
    )
    session.add_all([original, derived_zero, derived_one])
    session.commit()
    session.add(editing)
    session.commit()
    session.add(root_version)
    session.commit()
    session.add(child_version)
    session.commit()

    with pytest.raises(DBAPIError, match="original asset blob metadata"):
        session.execute(
            text("UPDATE assets SET storage_key='users/fixture/assets/replaced' WHERE id=:id"),
            {"id": original.id},
        )
    session.rollback()

    with pytest.raises(IntegrityError):
        session.execute(
            text("UPDATE image_versions SET parent_version_id=NULL WHERE id=:id"),
            {"id": child_version.id},
        )
    session.rollback()

    original.deleted_at = datetime.now(UTC)
    session.commit()
    session.refresh(child_version)
    assert child_version.parent_version_id == root_version.id


def test_desired_delta_history_is_append_only(session: Session) -> None:
    _, _, profile_version = create_profile_fixture(session, "g")
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(
            text("UPDATE desired_delta_profile_versions SET source='overwrite' WHERE id=:id"),
            {"id": profile_version.desired_delta_profile_version_id},
        )


def test_baseline_state_allows_supersession_but_not_evidence_overwrite(
    session: Session,
) -> None:
    _, _, profile_version = create_profile_fixture(session, "i")
    self_state = session.get(SelfState, profile_version.self_state_version_id)
    assert self_state is not None
    baseline = session.get(BaselineFaceModel, self_state.baseline_face_model_id)
    assert baseline is not None
    baseline.superseded_at = datetime.now(UTC)
    session.commit()
    with pytest.raises(DBAPIError, match="versioned state evidence is immutable"):
        session.execute(
            text("UPDATE baseline_face_models SET analyzer_version='overwrite' WHERE id=:id"),
            {"id": baseline.id},
        )


def test_questionnaire_run_binds_baseline_and_self_state_versions(session: Session) -> None:
    _, _, profile_version = create_profile_fixture(session, "h")
    bank = QuestionBankVersion(id=new_id(), version="fixture-bank-v1", qa_version="fixture-qa-v1")
    run = QuestionnaireRun(
        id=new_id(),
        user_id=session.get(SelfState, profile_version.self_state_version_id).user_id,
        bank_version_id=bank.id,
        baseline_face_model_id=session.get(
            SelfState, profile_version.self_state_version_id
        ).baseline_face_model_id,
        self_state_version_id=profile_version.self_state_version_id,
        routing_algorithm_version="route-v1",
        route_seed="reproducible-fixture-seed",
        measurement_normalization_version="normalization-v1",
        morphology_descriptor_version="descriptor-v1",
        neighborhood_metric_version="metric-v1",
        stimulus_generator_version="stimulus-v1",
    )
    session.add(bank)
    session.commit()
    session.add(run)
    session.commit()
    assert run.baseline_face_model_id
    assert run.self_state_version_id == profile_version.self_state_version_id


def make_rights_job(user_id: str, job_type: str, suffix: str) -> Job:
    return Job(
        id=new_id(),
        owner_user_id=user_id,
        job_type=job_type,
        status="pending",
        idempotency_key_hash=(suffix * 64)[:64],
        request_id=f"rights-{suffix}",
        payload={"schema_version": "data-rights-task-v1"},
    )


def test_asset_deletion_requires_owner_job_tombstone_and_append_only_evidence(
    session: Session,
) -> None:
    user = User(id=new_id(), phone_hash="j" * 64, status="active")
    asset = make_asset(user.id, "original", "rights-asset")
    derived = make_asset(user.id, "derived", "rights-derived")
    variant = AssetVariant(
        id=new_id(),
        source_asset_id=asset.id,
        result_asset_id=derived.id,
        variant_type="sanitized_preview",
    )
    job = make_rights_job(user.id, "asset_deletion", "k")
    session.add(user)
    session.commit()
    session.add_all([asset, derived, job])
    session.commit()
    session.add(variant)
    session.commit()

    request = AssetDeletionRequest(
        id=new_id(),
        owner_user_id=user.id,
        asset_id=asset.id,
        job_id=job.id,
        idempotency_key_hash="l" * 64,
        status="requested",
    )
    session.add(request)
    with pytest.raises(DBAPIError, match="immediate asset tombstone"):
        session.commit()
    session.rollback()

    asset = session.get(Asset, asset.id)
    derived = session.get(Asset, derived.id)
    job = session.get(Job, job.id)
    assert asset is not None and derived is not None and job is not None
    asset.deleted_at = datetime.now(UTC)
    derived.deleted_at = asset.deleted_at
    request = AssetDeletionRequest(
        id=new_id(),
        owner_user_id=user.id,
        asset_id=asset.id,
        job_id=job.id,
        idempotency_key_hash="l" * 64,
        status="requested",
    )
    session.add(request)
    session.commit()
    event = AssetDeletionEvent(id=new_id(), request_id=request.id, event_type="requested")
    session.add(event)
    session.commit()

    with pytest.raises(DBAPIError, match="immutable record"):
        event.event_type = "failed"
        session.commit()
    session.rollback()

    evidence = ObjectDeletionEvidence(
        id=new_id(),
        owner_user_id=user.id,
        asset_deletion_request_id=request.id,
        target_asset_id=asset.id,
        object_kind="asset",
        outcome="deleted",
        result_code="deleted",
    )
    session.add(evidence)
    session.commit()
    derived_evidence = ObjectDeletionEvidence(
        id=new_id(),
        owner_user_id=user.id,
        asset_deletion_request_id=request.id,
        target_asset_id=derived.id,
        object_kind="asset",
        outcome="not_found",
        result_code="already_absent",
    )
    session.add(derived_evidence)
    session.commit()
    unreachable = make_asset(user.id, "derived", "rights-unreachable")
    unreachable.deleted_at = datetime.now(UTC)
    session.add(unreachable)
    session.commit()
    session.add(
        ObjectDeletionEvidence(
            id=new_id(),
            owner_user_id=user.id,
            asset_deletion_request_id=request.id,
            target_asset_id=unreachable.id,
            object_kind="asset",
            outcome="deleted",
            result_code="deleted",
        )
    )
    with pytest.raises(DBAPIError, match="outside dependency graph"):
        session.commit()
    session.rollback()
    evidence = session.get(ObjectDeletionEvidence, evidence.id)
    assert evidence is not None
    with pytest.raises(DBAPIError, match="immutable record"):
        session.delete(evidence)
        session.commit()


def test_account_deletion_requires_immediate_freeze_and_owner_bound_job(
    session: Session,
) -> None:
    user = User(id=new_id(), phone_hash="m" * 64, status="active")
    job = make_rights_job(user.id, "account_deletion", "n")
    session.add(user)
    session.commit()
    session.add(job)
    session.commit()
    request = AccountDeletionRequest(
        id=new_id(),
        owner_user_id=user.id,
        job_id=job.id,
        idempotency_key_hash="o" * 64,
        status="requested",
    )
    session.add(request)
    with pytest.raises(DBAPIError, match="immediate user freeze"):
        session.commit()
    session.rollback()

    user = session.get(User, user.id)
    job = session.get(Job, job.id)
    assert user is not None and job is not None
    user.status = "deletion_requested"
    request = AccountDeletionRequest(
        id=new_id(),
        owner_user_id=user.id,
        job_id=job.id,
        idempotency_key_hash="o" * 64,
        status="requested",
    )
    session.add(request)
    session.commit()
    event = AccountDeletionEvent(id=new_id(), request_id=request.id, event_type="requested")
    session.add(event)
    session.commit()

    wrong_asset = make_asset(user.id, "original", "wrong-authority")
    wrong_asset.deleted_at = datetime.now(UTC)
    wrong_job = make_rights_job(user.id, "data_export", "p")
    session.add_all([wrong_asset, wrong_job])
    session.commit()
    session.add(
        AssetDeletionRequest(
            id=new_id(),
            owner_user_id=user.id,
            asset_id=wrong_asset.id,
            job_id=wrong_job.id,
            idempotency_key_hash="q" * 64,
            status="requested",
        )
    )
    with pytest.raises(DBAPIError, match="matching owner-bound job"):
        session.commit()


def test_account_quarantine_evidence_is_terminal_owner_bound_and_append_only(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    user = User(id=new_id(), phone_hash="q" * 64, status="active")
    outsider = User(id=new_id(), phone_hash="z" * 64, status="active")
    account_job = make_rights_job(user.id, "account_deletion", "r")
    session.add_all([user, outsider])
    session.commit()
    session.add(account_job)
    session.commit()
    user.status = "deletion_requested"
    account_request = AccountDeletionRequest(
        id=new_id(),
        owner_user_id=user.id,
        job_id=account_job.id,
        idempotency_key_hash="s" * 64,
        status="requested",
    )
    session.add(account_request)
    session.commit()

    def add_intent(owner: User, seed: str, status: str) -> UploadIntent:
        consent = ConsentRecord(
            id=new_id(),
            user_id=owner.id,
            consent_type="facial_data_processing",
            purpose="personal_aesthetic_baseline",
            purpose_version="purpose-v1",
            scope={"operations": ["private_upload"]},
            policy_code="facial-data-policy",
            policy_version="privacy-v1",
            policy_digest=seed * 64,
            action="grant",
            granted_at=now,
            source="integration_fixture",
            request_id=f"quarantine-consent-{seed}",
        )
        session.add(consent)
        session.commit()
        intent = UploadIntent(
            id=new_id(),
            owner_user_id=owner.id,
            consent_record_id=consent.id,
            object_key=f"quarantine/v1/{new_id()}",
            declared_mime_type="image/png",
            declared_byte_size=128,
            declared_sha256=seed * 64,
            status=status,
            grant_expires_at=now + timedelta(minutes=5),
            cancelled_at=now if status == "cancelled" else None,
        )
        session.add(intent)
        session.commit()
        return intent

    owned = add_intent(user, "a", "cancelled")
    evidence = ObjectDeletionEvidence(
        id=new_id(),
        owner_user_id=user.id,
        account_deletion_request_id=account_request.id,
        target_upload_intent_id=owned.id,
        object_kind="quarantine",
        outcome="deleted",
        result_code="deleted",
    )
    session.add(evidence)
    session.commit()

    outsider_intent = add_intent(outsider, "b", "cancelled")
    session.add(
        ObjectDeletionEvidence(
            id=new_id(),
            owner_user_id=user.id,
            account_deletion_request_id=account_request.id,
            target_upload_intent_id=outsider_intent.id,
            object_kind="quarantine",
            outcome="not_found",
            result_code="already_absent",
        )
    )
    with pytest.raises(DBAPIError, match="owner must match authority and target"):
        session.commit()
    session.rollback()

    active = add_intent(user, "c", "awaiting_upload")
    session.add(
        ObjectDeletionEvidence(
            id=new_id(),
            owner_user_id=user.id,
            account_deletion_request_id=account_request.id,
            target_upload_intent_id=active.id,
            object_kind="quarantine",
            outcome="deleted",
            result_code="deleted",
        )
    )
    with pytest.raises(DBAPIError, match="requires terminal upload intent"):
        session.commit()
    session.rollback()

    evidence = session.get(ObjectDeletionEvidence, evidence.id)
    assert evidence is not None
    with pytest.raises(DBAPIError, match="immutable record"):
        session.delete(evidence)
        session.commit()


def test_export_shape_and_access_audit_are_enforced(session: Session) -> None:
    user = User(id=new_id(), phone_hash="r" * 64, status="active")
    job = make_rights_job(user.id, "data_export", "s")
    asset = make_asset(user.id, "original", "audit-asset")
    session.add(user)
    session.commit()
    session.add_all([job, asset])
    session.commit()
    export = DataExportRequest(
        id=new_id(),
        owner_user_id=user.id,
        job_id=job.id,
        idempotency_key_hash="t" * 64,
        status="requested",
        schema_version="data-export-v1",
    )
    session.add(export)
    session.commit()
    export.status = "processing"
    session.commit()
    export.status = "ready"
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    audit = AssetAccessAudit(
        id=new_id(),
        asset_id=asset.id,
        actor_user_id=user.id,
        action="download_grant_created",
        request_id="audit-request",
    )
    session.add(audit)
    session.commit()
    with pytest.raises(DBAPIError, match="immutable record"):
        audit.action = "changed"
        session.commit()

    session.rollback()
    export = session.get(DataExportRequest, export.id)
    assert export is not None
    now = datetime.now(UTC)
    export.status = "ready"
    export.storage_key = "users/fixture/exports/export.zip"
    export.sha256 = "u" * 64
    export.byte_size = 100
    export.ready_at = now
    export.expires_at = now + timedelta(minutes=15)
    session.commit()
    event = DataExportEvent(id=new_id(), request_id=export.id, event_type="ready")
    session.add(event)
    session.commit()


def test_data_rights_request_authority_and_state_are_monotonic(session: Session) -> None:
    user = User(id=new_id(), phone_hash="v" * 64, status="active")
    asset = make_asset(user.id, "original", "rights-state")
    asset.deleted_at = datetime.now(UTC)
    job = make_rights_job(user.id, "asset_deletion", "w")
    session.add(user)
    session.commit()
    session.add_all([asset, job])
    session.commit()
    request = AssetDeletionRequest(
        id=new_id(),
        owner_user_id=user.id,
        asset_id=asset.id,
        job_id=job.id,
        idempotency_key_hash="x" * 64,
        status="requested",
    )
    session.add(request)
    session.commit()

    request.idempotency_key_hash = "y" * 64
    with pytest.raises(DBAPIError, match="authority is immutable"):
        session.commit()
    session.rollback()

    request = session.get(AssetDeletionRequest, request.id)
    assert request is not None
    request.status = "completed"
    request.started_at = datetime.now(UTC)
    request.completed_at = datetime.now(UTC)
    request.result_code = "deleted"
    with pytest.raises(DBAPIError, match="invalid data-rights request status transition"):
        session.commit()
    session.rollback()

    request = session.get(AssetDeletionRequest, request.id)
    assert request is not None
    session.delete(request)
    with pytest.raises(DBAPIError, match="authority is append-only"):
        session.commit()
