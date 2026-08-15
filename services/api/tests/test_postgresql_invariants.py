from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mirror_api.models import (
    AestheticProfile,
    AestheticProfileVersion,
    Asset,
    BaselineFaceModel,
    ConsentRecord,
    CreditAccount,
    CreditLedger,
    DesiredDeltaProfileVersion,
    EditingSession,
    IdentityConstraintVersion,
    ImageVersion,
    QuestionBankVersion,
    QuestionnaireRun,
    SelfState,
    StyleProfileVersion,
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
        connection.execute(text("TRUNCATE TABLE users CASCADE"))
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
        scope={"operations": ["landmark_detection"]},
        policy_version="privacy-v1",
        action="grant",
        granted_at=datetime.now(UTC),
        source="web_beta",
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
        scope=grant.scope,
        policy_version=grant.policy_version,
        action="withdraw",
        supersedes_id=grant.id,
        withdrawn_at=datetime.now(UTC),
        source="web_beta",
    )
    session.add(withdrawal)
    session.commit()
    assert session.scalar(select(func.count()).select_from(ConsentRecord)) == 2


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
