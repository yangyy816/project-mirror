from __future__ import annotations

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_synthetic_asset_qa_invariants import _approved_qa_policy, _normalized_record

from mirror_api.config import get_settings
from mirror_api.models import (
    Asset,
    GeometryOntologyVersion,
    SyntheticIdentity,
    SyntheticQAMeasurement,
    SyntheticQAPolicy,
    SyntheticQAReviewDecision,
    SyntheticQARun,
    TransformRun,
    VariantSpecification,
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
                "TRUNCATE TABLE transform_runs, variant_specifications, synthetic_identities, "
                "synthetic_qa_review_decisions, synthetic_qa_measurements, synthetic_qa_runs, "
                "synthetic_asset_records, synthetic_source_object_deletion_evidence, "
                "provider_cost_events, synthetic_generation_evidence, synthetic_source_objects, "
                "generation_items, generation_batches, job_attempts, jobs, synthetic_qa_policies, "
                "geometry_ontology_versions, synthetic_generation_policies, "
                "synthetic_prompt_templates, assets, offline_synthetic_source_admissions CASCADE"
            )
        )
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _append_passing_evidence(session: Session, qa_run: SyntheticQARun) -> None:
    now = utcnow()
    session.add(
        SyntheticQAMeasurement(
            id=new_id(),
            qa_run_id=qa_run.id,
            measurement_kind="geometry_measurement",
            measurement_code="geometry_subject_valid",
            payload={"valid": True},
            payload_digest="4" * 64,
            algorithm_reference="mirror.fixture/geometry-measurement",
            algorithm_version="v1",
            confidence=None,
            hard_gate=True,
            threshold_outcome="PASSED",
            reason_code="geometry_subject_valid",
        )
    )
    for review_kind in ("adult_presentation", "likeness_risk", "license_rights"):
        session.add(
            SyntheticQAReviewDecision(
                id=new_id(),
                qa_run_id=qa_run.id,
                review_kind=review_kind,
                decision="PASSED",
                reason_code=f"{review_kind}_passed",
                actor_reference="operator:m4-reviewer",
                reviewed_at=now,
                created_at=utcnow(),
            )
        )
    session.commit()


def _canonical_source(
    session: Session,
) -> tuple[Asset, SyntheticIdentity, SyntheticQARun, SyntheticQAPolicy]:
    record, source_asset = _normalized_record(session)
    policy = _approved_qa_policy(session)
    qa_run = SyntheticQARun(
        id=new_id(),
        synthetic_asset_record_id=record.id,
        normalized_asset_id=source_asset.id,
        qa_policy_id=policy.id,
        vision_provider_reference="deterministic-mock",
        vision_algorithm_reference="fixture-observation-v1",
    )
    session.add(qa_run)
    session.commit()
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="RUNNING", started_at=utcnow())
    )
    session.commit()
    _append_passing_evidence(session, qa_run)
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="PASSED", finalized_at=utcnow())
    )
    session.commit()
    identity = SyntheticIdentity(
        id=new_id(),
        canonical_asset_id=source_asset.id,
        accepted_qa_run_id=qa_run.id,
        adult_synthetic_attested=True,
    )
    session.add(identity)
    session.commit()
    session.refresh(qa_run)
    return source_asset, identity, qa_run, policy


def _approved_ontology(session: Session) -> GeometryOntologyVersion:
    ontology = GeometryOntologyVersion(
        id=new_id(),
        version="geometry-m4-fixture-v1",
        content={
            "dimensions": {
                "jaw_width": {"classification": "EXPERIMENTAL"},
                "nose_width": {"classification": "READY"},
            }
        },
        content_digest="5" * 64,
    )
    session.add(ontology)
    session.commit()
    session.execute(
        update(GeometryOntologyVersion)
        .where(GeometryOntologyVersion.id == ontology.id)
        .values(approval_status="APPROVED", approved_at=text("now()"))
    )
    session.commit()
    return ontology


def _specification(
    session: Session,
    source_asset: Asset,
    identity: SyntheticIdentity,
    source_qa_run: SyntheticQARun,
    tolerance_policy: SyntheticQAPolicy,
    ontology: GeometryOntologyVersion,
    *,
    digest: str = "6" * 64,
) -> VariantSpecification:
    specification = VariantSpecification(
        id=new_id(),
        source_asset_id=source_asset.id,
        source_identity_id=identity.id,
        source_qa_run_id=source_qa_run.id,
        geometry_ontology_version_id=ontology.id,
        target_dimension="jaw_width",
        direction="INCREASE",
        relative_magnitude_ppm=100_000,
        control_dimensions=["nose_width"],
        algorithm_version="fixture-transform-v1",
        runtime_manifest_digest="7" * 64,
        tolerance_policy_id=tolerance_policy.id,
        output_width=source_asset.width,
        output_height=source_asset.height,
        output_policy_version="variant-output-v1",
        determinism_level="BIT_EXACT_SAME_PLATFORM",
        content_digest=digest,
    )
    session.add(specification)
    session.commit()
    return specification


def _result_asset(session: Session, source_asset: Asset, *, sha: str = "8" * 64) -> Asset:
    result = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=f"variant-m4-{new_id()}",
        mime_type=source_asset.mime_type,
        byte_size=source_asset.byte_size,
        width=source_asset.width,
        height=source_asset.height,
        sha256=sha,
        synthetic=True,
        is_ai_generated=source_asset.is_ai_generated,
        is_ai_modified=True,
    )
    session.add(result)
    session.commit()
    return result


def _output_stored_run(
    session: Session, specification: VariantSpecification, result_asset: Asset, *, attempt: int = 1
) -> TransformRun:
    run = TransformRun(id=new_id(), variant_specification_id=specification.id, attempt=attempt)
    session.add(run)
    session.commit()
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == run.id)
        .values(status="RUNNING", started_at=utcnow())
    )
    session.commit()
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == run.id)
        .values(status="OUTPUT_STORED", result_asset_id=result_asset.id, output_stored_at=utcnow())
    )
    session.commit()
    session.refresh(run)
    return run


def _passed_variant_run(
    session: Session,
    specification: VariantSpecification,
    policy: SyntheticQAPolicy,
    source_asset: Asset,
    *,
    attempt: int,
    sha: str,
) -> TransformRun:
    result_asset = _result_asset(session, source_asset, sha=sha)
    run = _output_stored_run(session, specification, result_asset, attempt=attempt)
    qa_run = SyntheticQARun(
        id=new_id(),
        schema_version="mirror.synthetic-dataset/SyntheticQARun/v2",
        subject_kind="GEOMETRY_VARIANT",
        synthetic_asset_record_id=None,
        transform_run_id=run.id,
        normalized_asset_id=result_asset.id,
        qa_policy_id=policy.id,
        vision_provider_reference="deterministic-mock",
        vision_algorithm_reference="fixture-observation-v1",
    )
    session.add(qa_run)
    session.commit()
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="RUNNING", started_at=utcnow())
    )
    session.commit()
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == run.id)
        .values(status="MEASURING", measurement_started_at=utcnow())
    )
    session.commit()
    _append_passing_evidence(session, qa_run)
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="PASSED", finalized_at=utcnow())
    )
    session.commit()
    return run


def test_variant_result_uses_single_qa_authority_and_completes_monotonically(
    session: Session,
) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    specification = _specification(
        session, source_asset, identity, source_qa, policy, _approved_ontology(session)
    )
    result_asset = _result_asset(session, source_asset)
    run = _output_stored_run(session, specification, result_asset)

    qa_run = SyntheticQARun(
        id=new_id(),
        schema_version="mirror.synthetic-dataset/SyntheticQARun/v2",
        subject_kind="GEOMETRY_VARIANT",
        synthetic_asset_record_id=None,
        transform_run_id=run.id,
        normalized_asset_id=result_asset.id,
        qa_policy_id=policy.id,
        vision_provider_reference="deterministic-mock",
        vision_algorithm_reference="fixture-observation-v1",
    )
    session.add(qa_run)
    session.commit()
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="RUNNING", started_at=utcnow())
    )
    session.commit()
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == run.id)
        .values(status="MEASURING", measurement_started_at=utcnow())
    )
    session.commit()
    _append_passing_evidence(session, qa_run)
    session.execute(
        update(SyntheticQARun)
        .where(SyntheticQARun.id == qa_run.id)
        .values(status="PASSED", finalized_at=utcnow())
    )
    session.commit()
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == run.id)
        .values(status="COMPLETED", finalized_at=utcnow())
    )
    session.commit()
    session.refresh(run)
    assert run.status == "COMPLETED"
    assert qa_run.synthetic_asset_record_id is None
    assert qa_run.transform_run_id == run.id
    assert session.scalar(select(Asset).where(Asset.id == source_asset.id)) is not None


def test_variant_authority_rejects_forged_mixed_and_mutated_lineage(session: Session) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    ontology = _approved_ontology(session)
    specification = _specification(session, source_asset, identity, source_qa, policy, ontology)
    with pytest.raises(DBAPIError, match="variant specification is immutable"):
        session.execute(
            update(VariantSpecification)
            .where(VariantSpecification.id == specification.id)
            .values(relative_magnitude_ppm=200_000)
        )
        session.commit()
    session.rollback()

    unrelated_asset = _result_asset(session, source_asset, sha="9" * 64)
    with pytest.raises(DBAPIError, match="canonical synthetic authority"):
        forged = VariantSpecification(
            id=new_id(),
            source_asset_id=unrelated_asset.id,
            source_identity_id=identity.id,
            source_qa_run_id=source_qa.id,
            geometry_ontology_version_id=ontology.id,
            target_dimension="jaw_width",
            direction="DECREASE",
            relative_magnitude_ppm=100_000,
            control_dimensions=["nose_width"],
            algorithm_version="fixture-transform-v1",
            runtime_manifest_digest="a" * 64,
            tolerance_policy_id=policy.id,
            output_width=unrelated_asset.width,
            output_height=unrelated_asset.height,
            output_policy_version="variant-output-v1",
            determinism_level="BIT_EXACT_SAME_PLATFORM",
            content_digest="b" * 64,
        )
        session.add(forged)
        session.commit()
    session.rollback()

    result_asset = _result_asset(session, source_asset, sha="c" * 64)
    run = _output_stored_run(session, specification, result_asset)
    with pytest.raises((DBAPIError, IntegrityError)):
        session.add(
            SyntheticQARun(
                id=new_id(),
                schema_version="mirror.synthetic-dataset/SyntheticQARun/v2",
                subject_kind="GEOMETRY_VARIANT",
                synthetic_asset_record_id="forged-record-reference",
                transform_run_id=run.id,
                normalized_asset_id=result_asset.id,
                qa_policy_id=policy.id,
            )
        )
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="invalid transform run state transition"):
        session.execute(
            update(TransformRun)
            .where(TransformRun.id == run.id)
            .values(status="COMPLETED", finalized_at=utcnow())
        )
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable"):
        session.execute(delete(TransformRun).where(TransformRun.id == run.id))
        session.commit()
    session.rollback()

    failed_attempt = TransformRun(id=new_id(), variant_specification_id=specification.id, attempt=2)
    session.add(failed_attempt)
    session.commit()
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == failed_attempt.id)
        .values(status="RUNNING", started_at=utcnow())
    )
    session.commit()
    now = utcnow()
    with pytest.raises(DBAPIError, match="evidence does not match state transition"):
        session.execute(
            update(TransformRun)
            .where(TransformRun.id == failed_attempt.id)
            .values(
                status="FAILED",
                result_asset_id=unrelated_asset.id,
                output_stored_at=now,
                finalized_at=now,
                result_code="transform_failed",
            )
        )
        session.commit()
    session.rollback()


def test_duplicate_successful_lineage_is_rejected(session: Session) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    specification = _specification(
        session, source_asset, identity, source_qa, policy, _approved_ontology(session)
    )
    first = _passed_variant_run(
        session, specification, policy, source_asset, attempt=1, sha="d" * 64
    )
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == first.id)
        .values(status="COMPLETED", finalized_at=utcnow())
    )
    session.commit()
    second = _passed_variant_run(
        session, specification, policy, source_asset, attempt=2, sha="e" * 64
    )
    with pytest.raises(IntegrityError):
        session.execute(
            update(TransformRun)
            .where(TransformRun.id == second.id)
            .values(status="COMPLETED", finalized_at=utcnow())
        )
        session.commit()
    session.rollback()
    session.refresh(second)
    assert second.status == "MEASURING"


def test_concurrent_duplicate_attempt_has_one_authority(session: Session) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    specification = _specification(
        session, source_asset, identity, source_qa, policy, _approved_ontology(session)
    )
    specification_id = specification.id
    database_url = os.environ["TEST_DATABASE_URL"]
    barrier = Barrier(2)

    def insert_attempt(run_id: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                worker_session.add(
                    TransformRun(id=run_id, variant_specification_id=specification_id, attempt=1)
                )
                barrier.wait(timeout=10)
                try:
                    worker_session.commit()
                except IntegrityError:
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(insert_attempt, (new_id(), new_id())))
    assert results == ["conflict", "created"]
    session.expire_all()
    assert (
        len(
            session.scalars(
                select(TransformRun).where(
                    TransformRun.variant_specification_id == specification_id,
                    TransformRun.attempt == 1,
                )
            ).all()
        )
        == 1
    )


def test_existing_base_qa_row_survives_0012_downgrade_and_reupgrade(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    record, asset = _normalized_record(session)
    policy = _approved_qa_policy(session)
    qa_run = SyntheticQARun(
        id=new_id(),
        synthetic_asset_record_id=record.id,
        normalized_asset_id=asset.id,
        qa_policy_id=policy.id,
    )
    session.add(qa_run)
    session.commit()
    qa_run_id = qa_run.id
    record_id = record.id
    session.close()

    database_url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.downgrade(config, "0011_offline_synth_source")
    command.upgrade(config, "head")
    with create_engine(database_url).connect() as connection:
        row = connection.execute(
            text(
                "SELECT subject_kind, synthetic_asset_record_id, transform_run_id "
                "FROM synthetic_qa_runs WHERE id = :qa_run_id"
            ),
            {"qa_run_id": qa_run_id},
        ).one()
        assert row == ("CANONICAL_BASE", record_id, None)
    get_settings.cache_clear()


def test_0012_downgrade_fails_closed_when_m4_authority_exists(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    _specification(session, source_asset, identity, source_qa, policy, _approved_ontology(session))
    session.close()

    database_url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    with pytest.raises(DBAPIError, match="0012 downgrade would discard M4"):
        command.downgrade(config, "0011_offline_synth_source")
    with create_engine(database_url).connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0012_geometry_variant_authority"
        )
    get_settings.cache_clear()
