from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_geometry_variant_authority_invariants import (
    _canonical_source,
    _passed_variant_run,
    _result_asset,
    _specification,
)

from mirror_api.models import (
    DiversityReport,
    DuplicateCluster,
    DuplicateClusterMembership,
    EvaluationCohortAssignment,
    GeometryOntologyVersion,
    IsolationReport,
    SimilarityPairEvidence,
    SimilaritySignatureRecord,
    SyntheticEvaluationDimensionRule,
    SyntheticEvaluationPolicy,
    TransformRun,
    new_id,
    utcnow,
)

pytestmark = pytest.mark.integration


def _signature_digest(*, normalized_sha256: str, phash_hex: str, width: int, height: int) -> str:
    canonical = (
        '{"algorithm_version":"phash-dct-nearest-v1",'
        f'"height":{height},"normalized_sha256":"{normalized_sha256}",'
        f'"phash_hex":"{phash_hex}","width":{width}' + "}"
    )
    envelope = f"mirror.synthetic-dataset/SimilaritySignature/v1\n{canonical}".encode()
    return hashlib.sha256(envelope).hexdigest()


def _policy_digest(canonical_content: dict[str, object]) -> str:
    canonical = json.dumps(
        canonical_content,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    envelope = f"mirror.synthetic-dataset/SyntheticEvaluationPolicy/v1\n{canonical}".encode()
    return hashlib.sha256(envelope).hexdigest()


def _isolation_digest(
    *,
    transform_run_id: str,
    policy_version: str,
    policy_digest: str,
    target_dimension: str,
    target_error_ppm: int,
    non_target_drift_ppm: int,
    conclusion: str,
    reason_codes: list[str],
) -> str:
    canonical = json.dumps(
        {
            "conclusion": conclusion,
            "non_target_drift_ppm": non_target_drift_ppm,
            "policy_digest": policy_digest,
            "policy_version": policy_version,
            "reason_codes": reason_codes,
            "target_dimension": target_dimension,
            "target_error_ppm": target_error_ppm,
            "transform_run_reference": transform_run_id,
        },
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    envelope = f"mirror.synthetic-dataset/IsolationReportResult/v1\n{canonical}".encode()
    return hashlib.sha256(envelope).hexdigest()


def _signature(
    session: Session,
    *,
    asset_id: str,
    normalized_sha256: str,
    width: int,
    height: int,
    identifier: str,
    phash_hex: str = "0" * 16,
) -> SimilaritySignatureRecord:
    signature = SimilaritySignatureRecord(
        id=identifier,
        asset_id=asset_id,
        algorithm_version="phash-dct-nearest-v1",
        normalized_sha256=normalized_sha256,
        phash_hex=phash_hex,
        width=width,
        height=height,
        content_digest=_signature_digest(
            normalized_sha256=normalized_sha256,
            phash_hex=phash_hex,
            width=width,
            height=height,
        ),
    )
    session.add(signature)
    session.commit()
    return signature


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE diversity_reports, isolation_reports, "
                "evaluation_cohort_assignments, duplicate_cluster_decisions, "
                "duplicate_cluster_memberships, duplicate_clusters, "
                "similarity_pair_evidence, similarity_signatures, "
                "synthetic_evaluation_dimension_rules, synthetic_evaluation_policies, "
                "transform_runs, landmark_warp_plans, variant_specifications, "
                "synthetic_identities, synthetic_qa_review_decisions, "
                "synthetic_qa_measurements, synthetic_qa_runs, synthetic_asset_records, "
                "synthetic_source_object_deletion_evidence, provider_cost_events, "
                "synthetic_generation_evidence, synthetic_source_objects, generation_items, "
                "generation_batches, job_attempts, jobs, synthetic_qa_policies, "
                "geometry_ontology_versions, synthetic_generation_policies, "
                "synthetic_prompt_templates, assets, offline_synthetic_source_admissions CASCADE"
            )
        )
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _approved_policy(session: Session) -> SyntheticEvaluationPolicy:
    ontology = GeometryOntologyVersion(
        id=new_id(),
        version="geometry-m5-fixture-v1",
        content={
            "dimensions": {
                "jaw_width": {
                    "classification": "EXPERIMENTAL",
                    "region_group": "lower_face",
                },
                "nose_width": {
                    "classification": "READY",
                    "region_group": "central_face",
                },
            }
        },
        content_digest="5" * 64,
    )
    session.add(ontology)
    session.commit()
    session.execute(
        update(GeometryOntologyVersion)
        .where(GeometryOntologyVersion.id == ontology.id)
        .values(approval_status="APPROVED", approved_at=utcnow())
    )
    session.commit()
    dimension_rule = {
        "control_dimensions": ["nose_width"],
        "control_drift_tolerance_ppm": 1,
        "dimension_key": "jaw_width",
        "platform_variance_tolerance_ppm": 1,
        "region_group": "lower_face",
        "repeat_variance_tolerance_ppm": 1,
        "target_error_tolerance_ppm": 1,
    }
    canonical_content: dict[str, object] = {
        "cohort_stages": [24, 48, 96],
        "dimension_rules": [dimension_rule],
        "duplicate_algorithm_version": "phash-dct-nearest-v1",
        "isolation_algorithm_version": "m5-isolation-v1",
        "measurement_policy_version": "m5-measurement-v1",
        "ontology_digest": ontology.content_digest,
        "ontology_version": ontology.version,
        "split_rule_version": "m5-split-v1",
        "version": "m5-fixture-evaluation-v1",
    }
    policy = SyntheticEvaluationPolicy(
        id=new_id(),
        version="m5-fixture-evaluation-v1",
        geometry_ontology_version_id=ontology.id,
        ontology_digest=ontology.content_digest,
        measurement_policy_version="m5-measurement-v1",
        isolation_algorithm_version="m5-isolation-v1",
        duplicate_algorithm_version="phash-dct-nearest-v1",
        split_rule_version="m5-split-v1",
        canonical_content=canonical_content,
        content_digest=_policy_digest(canonical_content),
    )
    session.add(policy)
    session.commit()
    session.add(
        SyntheticEvaluationDimensionRule(
            id=new_id(),
            policy_id=policy.id,
            dimension_key="jaw_width",
            region_group="lower_face",
            control_dimensions=["nose_width"],
            target_error_tolerance_ppm=1,
            control_drift_tolerance_ppm=1,
            repeat_variance_tolerance_ppm=1,
            platform_variance_tolerance_ppm=1,
        )
    )
    session.commit()
    session.execute(
        update(SyntheticEvaluationPolicy)
        .where(SyntheticEvaluationPolicy.id == policy.id)
        .values(approval_status="APPROVED", approved_at=utcnow())
    )
    session.commit()
    return policy


def _m4_ontology(session: Session) -> GeometryOntologyVersion:
    ontology = GeometryOntologyVersion(
        id=new_id(),
        version="geometry-m4-isolation-v1",
        content={
            "dimensions": {
                "jaw_width": {"classification": "EXPERIMENTAL"},
                "nose_width": {"classification": "READY"},
            }
        },
        content_digest="6" * 64,
    )
    session.add(ontology)
    session.commit()
    session.execute(
        update(GeometryOntologyVersion)
        .where(GeometryOntologyVersion.id == ontology.id)
        .values(approval_status="APPROVED", approved_at=utcnow())
    )
    session.commit()
    return ontology


def test_m5_policy_is_immutable_and_diversity_rejects_prohibited_authority(
    session: Session,
) -> None:
    policy = _approved_policy(session)

    with pytest.raises(
        DBAPIError, match=r"M5 evaluation policy (canonical content|content is immutable)"
    ):
        session.execute(
            update(SyntheticEvaluationPolicy)
            .where(SyntheticEvaluationPolicy.id == policy.id)
            .values(canonical_content={"cohort_stages": [96]})
        )
        session.commit()
    session.rollback()

    session.add(
        DiversityReport(
            id=new_id(),
            policy_id=policy.id,
            cohort_stage=24,
            report_payload={"beauty_score": 0},
            content_digest="b" * 64,
        )
    )
    with pytest.raises(DBAPIError, match="prohibited authority"):
        session.commit()
    session.rollback()


def test_m5_policy_rejects_caller_supplied_content_digest(session: Session) -> None:
    approved = _approved_policy(session)
    canonical_content = dict(approved.canonical_content)
    canonical_content["version"] = "m5-fixture-evaluation-v2"
    session.add(
        SyntheticEvaluationPolicy(
            id=new_id(),
            version="m5-fixture-evaluation-v2",
            geometry_ontology_version_id=approved.geometry_ontology_version_id,
            ontology_digest=approved.ontology_digest,
            measurement_policy_version=approved.measurement_policy_version,
            isolation_algorithm_version=approved.isolation_algorithm_version,
            duplicate_algorithm_version=approved.duplicate_algorithm_version,
            split_rule_version=approved.split_rule_version,
            canonical_content=canonical_content,
            content_digest="9" * 64,
        )
    )
    with pytest.raises(DBAPIError, match="evaluation policy digest mismatch"):
        session.commit()
    session.rollback()


def test_m5_signature_binds_immutable_synthetic_asset_and_rejects_exact_duplicate(
    session: Session,
) -> None:
    source_asset, _, _, _ = _canonical_source(session)
    signature = _signature(
        session,
        asset_id=source_asset.id,
        normalized_sha256=source_asset.sha256,
        width=source_asset.width,
        height=source_asset.height,
        identifier="a" * 32,
    )

    with pytest.raises(DBAPIError, match="similarity signature is immutable"):
        session.execute(
            update(SimilaritySignatureRecord)
            .where(SimilaritySignatureRecord.id == signature.id)
            .values(phash_hex="f" * 16)
        )
        session.commit()
    session.rollback()


def test_m5_concurrent_exact_signature_admission_commits_only_one_authority(
    session: Session,
) -> None:
    source_asset, _, _, _ = _canonical_source(session)
    duplicate_asset = _result_asset(session, source_asset, sha=source_asset.sha256)
    engine = session.get_bind()
    barrier = Barrier(2)

    digest = _signature_digest(
        normalized_sha256=source_asset.sha256,
        phash_hex="0" * 16,
        width=source_asset.width,
        height=source_asset.height,
    )

    def insert_signature(asset_id: str, identifier: str) -> bool:
        try:
            with engine.begin() as connection:
                barrier.wait(timeout=5)
                connection.execute(
                    text(
                        "INSERT INTO similarity_signatures "
                        "(id, schema_version, asset_id, algorithm_version, normalized_sha256, "
                        "phash_hex, width, height, content_digest, created_at) "
                        "VALUES (:id, 'mirror.synthetic-dataset/SimilaritySignature/v1', "
                        ":asset_id, "
                        "'phash-dct-nearest-v1', :sha, '0000000000000000', 1, 1, :digest, now())"
                    ),
                    {
                        "id": identifier,
                        "asset_id": asset_id,
                        "sha": source_asset.sha256,
                        "digest": digest,
                    },
                )
            return True
        except DBAPIError as error:
            assert "M5 exact duplicate is a hard reject" in str(
                error
            ) or "uq_similarity_signatures_normalized_sha256" in str(error)
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: insert_signature(*args),
                (
                    (source_asset.id, "1" * 32),
                    (duplicate_asset.id, "2" * 32),
                ),
            )
        )
    assert results.count(True) == 1
    assert session.scalar(text("SELECT count(*) FROM similarity_signatures")) == 1


def test_m5_similarity_pair_rejects_falsified_hamming_distance(session: Session) -> None:
    source_asset, _, _, _ = _canonical_source(session)
    other_asset = _result_asset(session, source_asset, sha="3" * 64)
    for asset, identifier, sha, phash in (
        (source_asset, "1" * 32, source_asset.sha256, "0" * 16),
        (other_asset, "2" * 32, other_asset.sha256, "f" * 16),
    ):
        _signature(
            session,
            asset_id=asset.id,
            normalized_sha256=sha,
            width=asset.width,
            height=asset.height,
            identifier=identifier,
            phash_hex=phash,
        )
    session.add(
        SimilarityPairEvidence(
            id="3" * 32,
            left_signature_id="1" * 32,
            right_signature_id="2" * 32,
            algorithm_version="phash-dct-nearest-v1",
            hamming_distance=0,
            candidate_kind="NEAR_DUPLICATE_CANDIDATE",
            evidence_digest="c" * 64,
        )
    )
    with pytest.raises(DBAPIError, match="Hamming distance mismatch"):
        session.commit()
    session.rollback()

    duplicate_asset = _result_asset(session, source_asset, sha=source_asset.sha256)
    session.add(
        SimilaritySignatureRecord(
            id="d" * 32,
            asset_id=duplicate_asset.id,
            algorithm_version="phash-dct-nearest-v1",
            normalized_sha256=source_asset.sha256,
            phash_hex="1" * 16,
            width=source_asset.width,
            height=source_asset.height,
            content_digest=_signature_digest(
                normalized_sha256=source_asset.sha256,
                phash_hex="1" * 16,
                width=source_asset.width,
                height=source_asset.height,
            ),
        )
    )
    with pytest.raises(DBAPIError, match="exact duplicate"):
        session.commit()
    session.rollback()


def test_m5_signature_rejects_caller_supplied_content_digest(session: Session) -> None:
    source_asset, _, _, _ = _canonical_source(session)
    session.add(
        SimilaritySignatureRecord(
            id="9" * 32,
            asset_id=source_asset.id,
            algorithm_version="phash-dct-nearest-v1",
            normalized_sha256=source_asset.sha256,
            phash_hex="0" * 16,
            width=source_asset.width,
            height=source_asset.height,
            content_digest="9" * 64,
        )
    )
    with pytest.raises(DBAPIError, match="signature digest mismatch"):
        session.commit()
    session.rollback()


def test_m5_cohort_binds_canonical_identity_qa_asset_and_signature(session: Session) -> None:
    source_asset, identity, _, _ = _canonical_source(session)
    policy = _approved_policy(session)
    _signature(
        session,
        asset_id=source_asset.id,
        normalized_sha256=source_asset.sha256,
        width=source_asset.width,
        height=source_asset.height,
        identifier="1" * 32,
    )
    assignment = EvaluationCohortAssignment(
        id="2" * 32,
        policy_id=policy.id,
        synthetic_identity_id=identity.id,
        source_asset_id=source_asset.id,
        source_asset_sha256=source_asset.sha256,
        split="CALIBRATION",
        dimension_keys=["jaw_width"],
        assignment_digest="2" * 64,
    )
    session.add(assignment)
    session.commit()

    with pytest.raises(DBAPIError, match="cohort assignment is immutable"):
        session.execute(
            update(EvaluationCohortAssignment)
            .where(EvaluationCohortAssignment.id == assignment.id)
            .values(split="HOLDOUT")
        )
        session.commit()
    session.rollback()


def test_m5_cohort_rejects_cluster_without_source_signature_membership(
    session: Session,
) -> None:
    source_asset, identity, _, _ = _canonical_source(session)
    policy = _approved_policy(session)
    _signature(
        session,
        asset_id=source_asset.id,
        normalized_sha256=source_asset.sha256,
        width=source_asset.width,
        height=source_asset.height,
        identifier="1" * 32,
    )
    cluster = DuplicateCluster(
        id="2" * 32,
        algorithm_version="phash-dct-nearest-v1",
        cluster_digest="2" * 64,
    )
    session.add(cluster)
    session.commit()
    session.execute(
        update(DuplicateCluster)
        .where(DuplicateCluster.id == cluster.id)
        .values(status="FINALIZED", finalized_at=utcnow())
    )
    session.commit()
    session.add(
        EvaluationCohortAssignment(
            id="3" * 32,
            policy_id=policy.id,
            synthetic_identity_id=identity.id,
            source_asset_id=source_asset.id,
            source_asset_sha256=source_asset.sha256,
            duplicate_cluster_id=cluster.id,
            split="CALIBRATION",
            dimension_keys=["jaw_width"],
            assignment_digest="3" * 64,
        )
    )
    with pytest.raises(DBAPIError, match="cluster does not contain source signature"):
        session.commit()
    session.rollback()


def test_m5_isolation_report_binds_m4_specification_and_derived_outcome(
    session: Session,
) -> None:
    source_asset, identity, source_qa, qa_policy = _canonical_source(session)
    specification = _specification(
        session,
        source_asset,
        identity,
        source_qa,
        qa_policy,
        _m4_ontology(session),
    )
    transform_run = _passed_variant_run(
        session,
        specification,
        qa_policy,
        source_asset,
        attempt=1,
        sha="8" * 64,
    )
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == transform_run.id)
        .values(status="COMPLETED", finalized_at=utcnow())
    )
    session.commit()
    policy = _approved_policy(session)

    invalid = IsolationReport(
        id="1" * 32,
        transform_run_id=transform_run.id,
        policy_id=policy.id,
        target_dimension="jaw_width",
        requested_delta_ppm=-100_000,
        measured_target_delta_ppm=-100_000,
        target_error_ppm=0,
        control_deltas={"nose_width": 0},
        non_target_drift_ppm=0,
        repeat_variance_ppm=0,
        platform_variance_ppm=0,
        artifact_gate_passed=True,
        reliability_gate_passed=True,
        conclusion="PASSED",
        reason_codes=[],
        content_digest="1" * 64,
    )
    session.add(invalid)
    with pytest.raises(DBAPIError, match="bind the transform target and signed requested delta"):
        session.commit()
    session.rollback()

    content_digest = _isolation_digest(
        transform_run_id=transform_run.id,
        policy_version=policy.version,
        policy_digest=policy.content_digest,
        target_dimension="jaw_width",
        target_error_ppm=0,
        non_target_drift_ppm=0,
        conclusion="PASSED",
        reason_codes=[],
    )
    report = IsolationReport(
        id="2" * 32,
        transform_run_id=transform_run.id,
        policy_id=policy.id,
        target_dimension="jaw_width",
        requested_delta_ppm=100_000,
        measured_target_delta_ppm=100_000,
        target_error_ppm=0,
        control_deltas={"nose_width": 0},
        non_target_drift_ppm=0,
        repeat_variance_ppm=0,
        platform_variance_ppm=0,
        artifact_gate_passed=True,
        reliability_gate_passed=True,
        conclusion="PASSED",
        reason_codes=[],
        content_digest=content_digest,
    )
    session.add(report)
    session.commit()

    with pytest.raises(DBAPIError, match="isolation report is immutable"):
        session.execute(
            update(IsolationReport)
            .where(IsolationReport.id == report.id)
            .values(non_target_drift_ppm=1)
        )
        session.commit()
    session.rollback()


def test_m5_isolation_report_rejects_falsified_outcome_and_digest(session: Session) -> None:
    source_asset, identity, source_qa, qa_policy = _canonical_source(session)
    specification = _specification(
        session,
        source_asset,
        identity,
        source_qa,
        qa_policy,
        _m4_ontology(session),
    )
    transform_run = _passed_variant_run(
        session,
        specification,
        qa_policy,
        source_asset,
        attempt=1,
        sha="8" * 64,
    )
    session.execute(
        update(TransformRun)
        .where(TransformRun.id == transform_run.id)
        .values(status="COMPLETED", finalized_at=utcnow())
    )
    session.commit()
    policy = _approved_policy(session)
    report = IsolationReport(
        id="1" * 32,
        transform_run_id=transform_run.id,
        policy_id=policy.id,
        target_dimension="jaw_width",
        requested_delta_ppm=100_000,
        measured_target_delta_ppm=100_000,
        target_error_ppm=0,
        control_deltas={"nose_width": 10},
        non_target_drift_ppm=10,
        repeat_variance_ppm=0,
        platform_variance_ppm=0,
        artifact_gate_passed=True,
        reliability_gate_passed=True,
        conclusion="PASSED",
        reason_codes=[],
        content_digest="1" * 64,
    )
    session.add(report)
    with pytest.raises(DBAPIError, match="conclusion or reason codes mismatch"):
        session.commit()
    session.rollback()

    report.non_target_drift_ppm = 0
    report.control_deltas = {"nose_width": 0}
    report.content_digest = "1" * 64
    session.add(report)
    with pytest.raises(DBAPIError, match="isolation report digest mismatch"):
        session.commit()
    session.rollback()


def test_m5_finalization_serializes_against_late_cluster_membership(session: Session) -> None:
    source_asset, _, _, _ = _canonical_source(session)
    signature = _signature(
        session,
        asset_id=source_asset.id,
        normalized_sha256=source_asset.sha256,
        width=source_asset.width,
        height=source_asset.height,
        identifier="1" * 32,
    )
    cluster = DuplicateCluster(
        id="2" * 32,
        algorithm_version="phash-dct-nearest-v1",
        cluster_digest="2" * 64,
    )
    session.add(cluster)
    session.commit()
    engine = session.get_bind()
    cluster_id = cluster.id
    signature_id = signature.id
    finalization_locked = Event()
    allow_finalization_commit = Event()
    membership_started = Event()

    def finalize_cluster() -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE duplicate_clusters SET status='FINALIZED', finalized_at=now(), "
                    "updated_at=now() WHERE id=:cluster_id"
                ),
                {"cluster_id": cluster_id},
            )
            finalization_locked.set()
            assert allow_finalization_commit.wait(timeout=5)

    def add_membership() -> bool:
        try:
            with engine.begin() as connection:
                membership_started.set()
                connection.execute(
                    text(
                        "INSERT INTO duplicate_cluster_memberships "
                        "(id, cluster_id, signature_id, evidence_digest, created_at) "
                        "VALUES (:id, :cluster_id, :signature_id, :digest, now())"
                    ),
                    {
                        "id": "3" * 32,
                        "cluster_id": cluster_id,
                        "signature_id": signature_id,
                        "digest": "3" * 64,
                    },
                )
            return True
        except DBAPIError as error:
            assert "invalid M5 cluster membership" in str(error)
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        finalize_future = executor.submit(finalize_cluster)
        assert finalization_locked.wait(timeout=5)
        membership_future = executor.submit(add_membership)
        assert membership_started.wait(timeout=5)
        allow_finalization_commit.set()
        finalize_future.result(timeout=5)
        assert membership_future.result(timeout=5) is False


def test_m5_concurrent_membership_cannot_assign_one_signature_to_two_clusters(
    session: Session,
) -> None:
    source_asset, _, _, _ = _canonical_source(session)
    signature = _signature(
        session,
        asset_id=source_asset.id,
        normalized_sha256=source_asset.sha256,
        width=source_asset.width,
        height=source_asset.height,
        identifier="1" * 32,
    )
    clusters = (
        DuplicateCluster(
            id="2" * 32,
            algorithm_version="phash-dct-nearest-v1",
            cluster_digest="2" * 64,
        ),
        DuplicateCluster(
            id="3" * 32,
            algorithm_version="phash-dct-nearest-v1",
            cluster_digest="3" * 64,
        ),
    )
    session.add_all(clusters)
    session.commit()
    cluster_ids = tuple(cluster.id for cluster in clusters)
    signature_id = signature.id
    engine = session.get_bind()
    barrier = Barrier(2)

    def add_membership(cluster_id: str, identifier: str, digest: str) -> bool:
        try:
            with engine.begin() as connection:
                barrier.wait(timeout=5)
                connection.execute(
                    text(
                        "INSERT INTO duplicate_cluster_memberships "
                        "(id, cluster_id, signature_id, evidence_digest, created_at) "
                        "VALUES (:id, :cluster_id, :signature_id, :digest, now())"
                    ),
                    {
                        "id": identifier,
                        "cluster_id": cluster_id,
                        "signature_id": signature_id,
                        "digest": digest,
                    },
                )
            return True
        except IntegrityError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: add_membership(*args),
                (
                    (cluster_ids[0], "4" * 32, "4" * 64),
                    (cluster_ids[1], "5" * 32, "5" * 64),
                ),
            )
        )
    assert results.count(True) == 1
    assert session.scalar(text("SELECT count(*) FROM duplicate_cluster_memberships")) == 1


def test_m5_concurrent_cluster_split_assignment_commits_only_one_split(
    session: Session,
) -> None:
    source_asset, identity, _, _ = _canonical_source(session)
    policy = _approved_policy(session)
    signature = _signature(
        session,
        asset_id=source_asset.id,
        normalized_sha256=source_asset.sha256,
        width=source_asset.width,
        height=source_asset.height,
        identifier="1" * 32,
    )
    cluster = DuplicateCluster(
        id="2" * 32,
        algorithm_version="phash-dct-nearest-v1",
        cluster_digest="2" * 64,
    )
    session.add(cluster)
    session.commit()
    session.add(
        DuplicateClusterMembership(
            id="3" * 32,
            cluster_id=cluster.id,
            signature_id=signature.id,
            evidence_digest="3" * 64,
        )
    )
    session.commit()
    session.execute(
        update(DuplicateCluster)
        .where(DuplicateCluster.id == cluster.id)
        .values(status="FINALIZED", finalized_at=utcnow())
    )
    session.commit()
    engine = session.get_bind()
    policy_id = policy.id
    identity_id = identity.id
    asset_id = source_asset.id
    source_sha256 = source_asset.sha256
    cluster_id = cluster.id
    barrier = Barrier(2)

    def assign(split: str, identifier: str, digest: str) -> tuple[bool, str]:
        try:
            with engine.begin() as connection:
                barrier.wait(timeout=5)
                connection.execute(
                    text(
                        "INSERT INTO evaluation_cohort_assignments "
                        "(id, policy_id, synthetic_identity_id, source_asset_id, "
                        "source_asset_sha256, duplicate_cluster_id, split, dimension_keys, "
                        "assignment_digest, created_at) VALUES "
                        "(:id, :policy_id, :identity_id, :asset_id, :sha, :cluster_id, "
                        ":split, '[\"jaw_width\"]'::json, :digest, now())"
                    ),
                    {
                        "id": identifier,
                        "policy_id": policy_id,
                        "identity_id": identity_id,
                        "asset_id": asset_id,
                        "sha": source_sha256,
                        "cluster_id": cluster_id,
                        "split": split,
                        "digest": digest,
                    },
                )
            return True, ""
        except DBAPIError as error:
            return False, str(error)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: assign(*args),
                (
                    ("CALIBRATION", "4" * 32, "4" * 64),
                    ("HOLDOUT", "5" * 32, "5" * 64),
                ),
            )
        )
    assert [result[0] for result in results].count(True) == 1
    assert any("M5 duplicate cluster split leakage" in result[1] for result in results)
    assert session.scalar(text("SELECT count(*) FROM evaluation_cohort_assignments")) == 1


def test_m5_downgrade_refuses_to_discard_durable_authority(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = _approved_policy(session)
    policy_id = policy.id
    assert policy_id is not None
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    session.rollback()
    session.close()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    with pytest.raises(DBAPIError, match="0014 downgrade would discard durable M5"):
        command.downgrade(config, "0013_warp_plan_authority")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "demo_0007_d02_recovered_qa"
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM synthetic_evaluation_policies WHERE id=:policy_id"),
                {"policy_id": policy_id},
            )
            == 1
        )
    engine.dispose()
