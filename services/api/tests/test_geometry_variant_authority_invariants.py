from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Generator
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
    LandmarkWarpPlanAuthority,
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
from mirror_api.synthetic_dataset import (
    LANDMARK_WARP_PLAN_BUILDER_VERSION,
    LandmarkWarpPlanAdmissionService,
    WarpControlPoint,
    WarpTriangle,
)
from mirror_api.synthetic_dataset import (
    LandmarkWarpPlanAuthority as LandmarkWarpPlanDocument,
)
from mirror_api.synthetic_dataset.geometry_transform import LandmarkWarpPlan

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
                "TRUNCATE TABLE transform_runs, landmark_warp_plans, variant_specifications, "
                "synthetic_identities, "
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


def _admit_plan(session: Session, specification: VariantSpecification) -> LandmarkWarpPlanAuthority:
    existing = session.scalar(
        select(LandmarkWarpPlanAuthority).where(
            LandmarkWarpPlanAuthority.variant_specification_id == specification.id
        )
    )
    if existing is not None:
        return existing
    plan = LandmarkWarpPlan.create(
        specification_digest=specification.content_digest,
        control_points=(
            WarpControlPoint("a", 0.0, 0.0, 0.05, 0.0, 900_000),
            WarpControlPoint("b", 1.0, 0.0, 1.0, 0.0, 900_000),
            WarpControlPoint("c", 0.0, 1.0, 0.05, 1.0, 900_000),
        ),
        triangles=(WarpTriangle(("a", "b", "c")),),
    )
    authority = LandmarkWarpPlanAdmissionService.prepare(
        specification_digest=specification.content_digest,
        plan=plan,
        origin_reference="m4-plan-fixture-01",
        origin_digest="a" * 64,
        builder_version=LANDMARK_WARP_PLAN_BUILDER_VERSION,
        builder_manifest_digest="b" * 64,
    )
    row = LandmarkWarpPlanAuthority(
        id=new_id(),
        variant_specification_id=specification.id,
        schema_version=authority.schema_version,
        plan_schema_version=authority.plan_schema_version,
        canonical_payload=authority.canonical_payload,
        warp_plan_digest=authority.warp_plan_digest,
        authority_digest=authority.authority_digest,
        origin_kind=authority.origin_kind.value,
        origin_reference=authority.origin_reference,
        origin_digest=authority.origin_digest,
        builder_version=authority.builder_version,
        builder_manifest_digest=authority.builder_manifest_digest,
    )
    session.add(row)
    session.commit()
    return row


def _output_stored_run(
    session: Session, specification: VariantSpecification, result_asset: Asset, *, attempt: int = 1
) -> TransformRun:
    _admit_plan(session, specification)
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
    _admit_plan(session, specification)
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
    _admit_plan(session, specification)
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
    _admit_plan(session, specification)
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


def test_landmark_warp_plan_is_required_and_immutable(session: Session) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    specification = _specification(
        session, source_asset, identity, source_qa, policy, _approved_ontology(session)
    )
    with pytest.raises(DBAPIError, match="requires immutable landmark warp plan"):
        session.add(TransformRun(id=new_id(), variant_specification_id=specification.id, attempt=1))
        session.commit()
    session.rollback()

    authority = _admit_plan(session, specification)
    with pytest.raises(DBAPIError, match="landmark warp plan authority is immutable"):
        session.execute(
            update(LandmarkWarpPlanAuthority)
            .where(LandmarkWarpPlanAuthority.id == authority.id)
            .values(origin_reference="m4-plan-fixture-02")
        )
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="landmark warp plan authority is immutable"):
        session.execute(
            delete(LandmarkWarpPlanAuthority).where(LandmarkWarpPlanAuthority.id == authority.id)
        )
        session.commit()
    session.rollback()

    run = TransformRun(id=new_id(), variant_specification_id=specification.id, attempt=1)
    session.add(run)
    session.commit()


def _rebind_payload_digests(
    authority: LandmarkWarpPlanDocument, canonical_payload: str
) -> tuple[str, str]:
    warp_plan_digest = hashlib.sha256(
        f"{authority.plan_schema_version}\n{canonical_payload}".encode()
    ).hexdigest()
    facts = {
        "builder_manifest_digest": authority.builder_manifest_digest,
        "builder_version": authority.builder_version,
        "origin_digest": authority.origin_digest,
        "origin_kind": authority.origin_kind.value,
        "origin_reference": authority.origin_reference,
        "specification_digest": authority.specification_digest,
        "warp_plan_digest": warp_plan_digest,
    }
    canonical_authority = json.dumps(
        facts, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    authority_digest = hashlib.sha256(
        f"{authority.schema_version}\n{canonical_authority}".encode()
    ).hexdigest()
    return warp_plan_digest, authority_digest


@pytest.mark.parametrize(
    ("payload_mutator", "origin_reference", "rebind_digests"),
    (
        (
            lambda value: value.replace('"control_points":[', '"control_points": [', 1),
            None,
            False,
        ),
        (
            lambda value: value.replace(
                '"landmark_code":"a"', '"landmark_code":"a","landmark_code":"a"', 1
            ),
            None,
            True,
        ),
        (lambda value: value.replace('"source_x":0.0', '"source_x":0', 1), None, True),
        (lambda value: value, "https://example.invalid/private-plan", False),
    ),
)
def test_landmark_warp_plan_direct_sql_rejects_noncanonical_or_unsafe_authority(
    session: Session,
    payload_mutator: Callable[[str], str],
    origin_reference: str | None,
    rebind_digests: bool,
) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    specification = _specification(
        session, source_asset, identity, source_qa, policy, _approved_ontology(session)
    )
    plan = LandmarkWarpPlan.create(
        specification_digest=specification.content_digest,
        control_points=(
            WarpControlPoint("a", 0.0, 0.0, 0.05, 0.0, 900_000),
            WarpControlPoint("b", 1.0, 0.0, 1.0, 0.0, 900_000),
            WarpControlPoint("c", 0.0, 1.0, 0.05, 1.0, 900_000),
        ),
        triangles=(WarpTriangle(("a", "b", "c")),),
    )
    authority = LandmarkWarpPlanAdmissionService.prepare(
        specification_digest=specification.content_digest,
        plan=plan,
        origin_reference="m4-plan-fixture-01",
        origin_digest="a" * 64,
        builder_version=LANDMARK_WARP_PLAN_BUILDER_VERSION,
        builder_manifest_digest="b" * 64,
    )
    canonical_payload = payload_mutator(authority.canonical_payload)
    warp_plan_digest = authority.warp_plan_digest
    authority_digest = authority.authority_digest
    if rebind_digests:
        warp_plan_digest, authority_digest = _rebind_payload_digests(authority, canonical_payload)
    with pytest.raises(DBAPIError):
        session.execute(
            text(
                """
                INSERT INTO landmark_warp_plans (
                    id, schema_version, plan_schema_version, variant_specification_id,
                    canonical_payload, warp_plan_digest, authority_digest, origin_kind,
                    origin_reference, origin_digest, builder_version,
                    builder_manifest_digest, created_at
                ) VALUES (
                    :id, :schema_version, :plan_schema_version, :variant_specification_id,
                    :canonical_payload, :warp_plan_digest, :authority_digest, :origin_kind,
                    :origin_reference, :origin_digest, :builder_version,
                    :builder_manifest_digest, :created_at
                )
                """
            ),
            {
                "id": new_id(),
                "schema_version": authority.schema_version,
                "plan_schema_version": authority.plan_schema_version,
                "variant_specification_id": specification.id,
                "canonical_payload": canonical_payload,
                "warp_plan_digest": warp_plan_digest,
                "authority_digest": authority_digest,
                "origin_kind": authority.origin_kind.value,
                "origin_reference": origin_reference or authority.origin_reference,
                "origin_digest": authority.origin_digest,
                "builder_version": authority.builder_version,
                "builder_manifest_digest": authority.builder_manifest_digest,
                "created_at": utcnow(),
            },
        )
        session.commit()
    session.rollback()


def test_0013_empty_lifecycle_downgrades_and_reupgrades(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.close()
    database_url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.downgrade(config, "0012_geometry_variant_authority")
    command.upgrade(config, "head")
    with create_engine(database_url).connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "demo_0011_d03_job_recovery"
        )
    get_settings.cache_clear()


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
            "demo_0011_d03_job_recovery"
        )
    get_settings.cache_clear()


def test_0013_upgrade_rejects_legacy_transform_run(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_asset, identity, source_qa, policy = _canonical_source(session)
    specification = _specification(
        session, source_asset, identity, source_qa, policy, _approved_ontology(session)
    )
    specification_id = specification.id
    session.close()

    database_url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.downgrade(config, "0012_geometry_variant_authority")
    engine = create_engine(database_url)
    with Session(engine) as legacy_session:
        legacy_session.add(
            TransformRun(id=new_id(), variant_specification_id=specification_id, attempt=1)
        )
        legacy_session.commit()
    with pytest.raises(DBAPIError, match="cannot infer landmark warp plan authority"):
        command.upgrade(config, "head")
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0012_geometry_variant_authority"
        )
        connection.execute(text("TRUNCATE TABLE transform_runs CASCADE"))
    command.upgrade(config, "head")
    engine.dispose()
    get_settings.cache_clear()
