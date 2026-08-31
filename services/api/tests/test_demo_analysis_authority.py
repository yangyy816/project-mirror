from __future__ import annotations

import hashlib
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _accepted_synthetic_source,
    _build_demo_row,
    _insert_actor,
    _insert_demo_row,
    _persist_historical_authority_rows,
    _synthetic_admission_fields,
    _truncate_demo_authority,
)

from mirror_api.demo_models import (
    DemoActor,
    DemoAnalysisRun,
    DemoBaselineFaceModel,
    DemoFaceObservation,
    DemoFaceObservationRepeat,
    DemoJobBinding,
    DemoSelfState,
    DemoSession,
    DemoSyntheticIdentity,
)
from mirror_api.models import Job, JobAttempt, new_id

_HEAD = "demo_0016_d06_ref_profile_queue"
_DOWN = "demo_0009_d02_r2_e2_adm"
_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _truncate_demo_analysis_test_authority(session: Session) -> None:
    """Remove the Demo graph before its formal synthetic source fixture."""
    _truncate_demo_authority(session)
    session.execute(
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
    session.commit()


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with Session(engine) as db_session:
        _truncate_demo_analysis_test_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_analysis_test_authority(db_session)
    engine.dispose()


def _analysis_context(
    session: Session,
) -> tuple[DemoActor, DemoSession, DemoSyntheticIdentity]:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    actor = _insert_actor(session)
    identity = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker=f"d03-{new_id()}",
        ),
    )
    demo_session = _insert_demo_row(
        session,
        DemoSession,
        demo_actor_id=actor.id,
        config={
            "schema_version": "mirror.demo/DemoSessionConfig/v1",
            "synthetic_identity_id": identity.id,
        },
        context_seed=_DIGEST_A,
        expires_at=datetime.now(UTC) + timedelta(hours=2),
        closed_at=None,
        tombstoned_at=None,
    )
    return actor, demo_session, identity


def _pending_analysis(
    session: Session,
    actor: DemoActor,
    demo_session: DemoSession,
    identity: DemoSyntheticIdentity,
) -> tuple[Job, DemoAnalysisRun, DemoJobBinding]:
    job_id = new_id()
    run_id = new_id()
    binding_id = new_id()
    client_key_hash = hashlib.sha256(f"d03-key/{new_id()}".encode()).hexdigest()
    formal_key_hash = hashlib.sha256(
        (f"mirror.demo/JobIdempotency/v1\n{actor.id}\nanalysis.create\n{client_key_hash}").encode()
    ).hexdigest()
    job = Job(
        id=job_id,
        job_type="demo_p3_p7.analysis.create",
        status="PENDING",
        idempotency_key_hash=formal_key_hash,
        request_id=f"d03-{new_id()}",
        payload={},
        owner_user_id=None,
    )
    run = _build_demo_row(
        DemoAnalysisRun,
        row_id=run_id,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        demo_synthetic_identity_id=identity.id,
        source_asset_id=identity.formal_canonical_asset_id,
        source_asset_sha256=identity.formal_canonical_asset_sha256,
        demo_job_binding_id=binding_id,
        analyzer_version="demo-face-observation-v1",
        runtime_manifest_digest=_DIGEST_A,
        model_manifest_digest=_DIGEST_B,
        observation_config_digest=_DIGEST_C,
        baseline_aggregation_version="demo-baseline-median-v1",
        measurement_version="demo-face-height-normalized-v1",
        self_state_ontology_version="demo-self-state-ontology-v1",
        self_state_derivation_version="demo-self-state-derivation-v1",
        repeat_count=3,
    )
    binding = _build_demo_row(
        DemoJobBinding,
        row_id=binding_id,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        job_id=job_id,
        endpoint_operation="analysis.create",
        idempotency_key_hash=client_key_hash,
        request_digest=hashlib.sha256(f"d03-request/{new_id()}".encode()).hexdigest(),
        target_type="ANALYSIS_RUN",
        target_id=run_id,
    )
    session.add(job)
    session.flush()
    session.add(run)
    session.flush()
    session.add(binding)
    session.commit()
    return job, run, binding


def _claim_analysis(session: Session, job: Job) -> JobAttempt:
    now = datetime.now(UTC)
    lease_token = hashlib.sha256(f"d03-lease/{new_id()}".encode()).hexdigest()
    attempt = JobAttempt(
        id=new_id(),
        job_id=job.id,
        attempt=1,
        status="RUNNING",
        lease_token=lease_token,
        started_at=now,
    )
    session.add(attempt)
    job.status = "RUNNING"
    job.attempt_count = 1
    job.lease_token = lease_token
    job.lease_acquired_at = now
    job.lease_expires_at = now + timedelta(minutes=5)
    session.commit()
    return attempt


def _observation(run: DemoAnalysisRun, *, marker: str) -> DemoFaceObservation:
    return cast(
        DemoFaceObservation,
        _build_demo_row(
            DemoFaceObservation,
            authority_schema_version="mirror.demo/DemoFaceObservation/v2",
            demo_actor_id=run.demo_actor_id,
            demo_session_id=run.demo_session_id,
            demo_synthetic_identity_id=run.demo_synthetic_identity_id,
            source_asset_id=run.source_asset_id,
            source_asset_sha256=run.source_asset_sha256,
            analysis_run_id=run.id,
            analyzer_version=run.analyzer_version,
            runtime_manifest_digest=run.runtime_manifest_digest,
            config_digest=run.observation_config_digest,
            repeat_count=3,
            observation_state="SUPPORTED",
            unsupported_reason=None,
            created_at=datetime(2026, 8, 29, 8, int(marker), tzinfo=UTC),
        ),
    )


def _complete_graph(
    session: Session,
    run: DemoAnalysisRun,
    job: Job,
    attempt: JobAttempt,
) -> tuple[DemoFaceObservation, DemoBaselineFaceModel, DemoSelfState]:
    observation = _observation(run, marker="1")
    session.add(observation)
    session.flush()
    repeats = [
        _build_demo_row(
            DemoFaceObservationRepeat,
            demo_actor_id=run.demo_actor_id,
            demo_session_id=run.demo_session_id,
            observation_id=observation.id,
            repeat_index=repeat_index,
            runtime_manifest_digest=run.runtime_manifest_digest,
            model_manifest_digest=run.model_manifest_digest,
            landmarks=[{"x_ppm": 0, "y_ppm": 0, "z_ppm": 0} for _ in range(478)],
            pose={"yaw_ppm": 0, "pitch_ppm": 0, "roll_ppm": 0},
            quality={"face_count": 1, "reliability_ppm": 900_000},
            measurements={"jaw_width_ppm": 100_000 + repeat_index},
        )
        for repeat_index in (1, 2, 3)
    ]
    session.add_all(repeats)
    session.flush()
    baseline = _build_demo_row(
        DemoBaselineFaceModel,
        demo_actor_id=run.demo_actor_id,
        demo_session_id=run.demo_session_id,
        observation_id=observation.id,
        version=1,
        aggregation_version=run.baseline_aggregation_version,
        measurement_version=run.measurement_version,
        ordered_repeat_digests=[repeat.content_digest for repeat in repeats],
        measurements={"jaw_width_ppm": 100_002},
        reliability={"jaw_width_ppm": 900_000},
        uncertainty={"jaw_width_ppm": 10_000},
        unsupported_state={},
    )
    session.add(baseline)
    session.flush()
    self_state = _build_demo_row(
        DemoSelfState,
        demo_actor_id=run.demo_actor_id,
        demo_session_id=run.demo_session_id,
        baseline_face_model_id=baseline.id,
        version=1,
        ontology_version=run.self_state_ontology_version,
        derivation_version=run.self_state_derivation_version,
        measurements={"jaw_width_ppm": 100_002},
        reliability={"jaw_width_ppm": 900_000},
        uncertainty={"jaw_width_ppm": 10_000},
        routing_eligibility={"jaw_width": True},
    )
    session.add(self_state)
    session.flush()

    finalized_at = datetime.now(UTC)
    attempt.status = "COMPLETED"
    attempt.result_code = "SUPPORTED"
    attempt.error_code = None
    attempt.finished_at = finalized_at
    job.status = "COMPLETED"
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = finalized_at
    job.result_code = "SUPPORTED"
    session.commit()
    return observation, baseline, self_state


def _next_baseline(baseline: DemoBaselineFaceModel, *, version: int = 2) -> DemoBaselineFaceModel:
    return cast(
        DemoBaselineFaceModel,
        _build_demo_row(
            DemoBaselineFaceModel,
            demo_actor_id=baseline.demo_actor_id,
            demo_session_id=baseline.demo_session_id,
            observation_id=baseline.observation_id,
            version=version,
            aggregation_version=baseline.aggregation_version,
            measurement_version=baseline.measurement_version,
            ordered_repeat_digests=list(baseline.ordered_repeat_digests),
            measurements=dict(baseline.measurements),
            reliability=dict(baseline.reliability),
            uncertainty=dict(baseline.uncertainty),
            unsupported_state=dict(baseline.unsupported_state),
        ),
    )


def _next_self_state(
    self_state: DemoSelfState,
    *,
    baseline_face_model_id: str | None = None,
    version: int = 2,
) -> DemoSelfState:
    return cast(
        DemoSelfState,
        _build_demo_row(
            DemoSelfState,
            demo_actor_id=self_state.demo_actor_id,
            demo_session_id=self_state.demo_session_id,
            baseline_face_model_id=baseline_face_model_id or self_state.baseline_face_model_id,
            version=version,
            ontology_version=self_state.ontology_version,
            derivation_version=self_state.derivation_version,
            measurements=dict(self_state.measurements),
            reliability=dict(self_state.reliability),
            uncertainty=dict(self_state.uncertainty),
            routing_eligibility=dict(self_state.routing_eligibility),
        ),
    )


def _authority_counts(
    session: Session,
    *,
    job_id: str,
    observation_id: str,
) -> tuple[int, int, int, int]:
    attempts = len(session.scalars(select(JobAttempt.id).where(JobAttempt.job_id == job_id)).all())
    repeats = len(
        session.scalars(
            select(DemoFaceObservationRepeat.id).where(
                DemoFaceObservationRepeat.observation_id == observation_id
            )
        ).all()
    )
    baselines = len(
        session.scalars(
            select(DemoBaselineFaceModel.id).where(
                DemoBaselineFaceModel.observation_id == observation_id
            )
        ).all()
    )
    self_states = len(
        session.scalars(
            select(DemoSelfState.id)
            .join(
                DemoBaselineFaceModel,
                DemoBaselineFaceModel.id == DemoSelfState.baseline_face_model_id,
            )
            .where(DemoBaselineFaceModel.observation_id == observation_id)
        ).all()
    )
    return attempts, repeats, baselines, self_states


def test_pending_analysis_run_is_the_immutable_typed_job_target(session: Session) -> None:
    actor, demo_session, identity = _analysis_context(session)
    job, run, binding = _pending_analysis(session, actor, demo_session, identity)

    assert job.status == "PENDING"
    assert binding.target_type == "ANALYSIS_RUN"
    assert binding.target_id == run.id
    assert run.demo_job_binding_id == binding.id
    assert run.repeat_count == 3

    with pytest.raises(DBAPIError, match="immutable"):
        session.execute(
            update(DemoAnalysisRun)
            .where(DemoAnalysisRun.id == run.id)
            .values(analyzer_version="tampered")
        )
        session.commit()
    session.rollback()


def test_result_publication_is_atomic_with_completed_job(session: Session) -> None:
    actor, demo_session, identity = _analysis_context(session)
    job, run, _ = _pending_analysis(session, actor, demo_session, identity)
    _claim_analysis(session, job)

    session.add(_observation(run, marker="2"))
    with pytest.raises(DBAPIError, match="publish atomically"):
        session.commit()
    session.rollback()
    assert (
        session.scalar(
            select(DemoFaceObservation.id).where(DemoFaceObservation.analysis_run_id == run.id)
        )
        is None
    )


def test_complete_graph_and_job_attempt_commit_as_one_authority(session: Session) -> None:
    actor, demo_session, identity = _analysis_context(session)
    job, run, _ = _pending_analysis(session, actor, demo_session, identity)
    attempt = _claim_analysis(session, job)

    observation, baseline, self_state = _complete_graph(session, run, job, attempt)

    assert job.status == "COMPLETED"
    assert attempt.status == "COMPLETED"
    assert observation.analysis_run_id == run.id
    assert baseline.observation_id == observation.id
    assert self_state.baseline_face_model_id == baseline.id


@pytest.mark.parametrize("operation", ["insert", "update", "delete"])
def test_completed_job_attempt_is_exactly_one_and_immutable(
    session: Session, operation: str
) -> None:
    actor, demo_session, identity = _analysis_context(session)
    job, run, _ = _pending_analysis(session, actor, demo_session, identity)
    attempt = _claim_analysis(session, job)
    observation, _, _ = _complete_graph(session, run, job, attempt)

    with pytest.raises(DBAPIError, match="D03"):
        if operation == "insert":
            session.add(
                JobAttempt(
                    id=new_id(),
                    job_id=job.id,
                    attempt=2,
                    status="RUNNING",
                    lease_token=_DIGEST_A,
                    started_at=datetime.now(UTC),
                )
            )
        elif operation == "update":
            session.execute(
                update(JobAttempt).where(JobAttempt.id == attempt.id).values(result_code="TAMPERED")
            )
        else:
            session.delete(attempt)
        session.commit()
    session.rollback()
    assert _authority_counts(session, job_id=job.id, observation_id=observation.id) == (1, 3, 1, 1)


def test_running_job_rejects_a_second_attempt(session: Session) -> None:
    actor, demo_session, identity = _analysis_context(session)
    job, _, _ = _pending_analysis(session, actor, demo_session, identity)
    _claim_analysis(session, job)
    session.add(
        JobAttempt(
            id=new_id(),
            job_id=job.id,
            attempt=2,
            status="RUNNING",
            lease_token=_DIGEST_B,
            started_at=datetime.now(UTC),
        )
    )

    with pytest.raises(DBAPIError, match="declared Attempt cardinality"):
        session.commit()
    session.rollback()
    assert len(session.scalars(select(JobAttempt.id).where(JobAttempt.job_id == job.id)).all()) == 1


@pytest.mark.parametrize("mutation", ["baseline", "self_state", "complete_graph"])
def test_completed_graph_rejects_additional_authority_versions(
    session: Session, mutation: str
) -> None:
    actor, demo_session, identity = _analysis_context(session)
    job, run, _ = _pending_analysis(session, actor, demo_session, identity)
    attempt = _claim_analysis(session, job)
    observation, baseline, self_state = _complete_graph(session, run, job, attempt)

    if mutation == "baseline":
        session.add(_next_baseline(baseline))
    elif mutation == "self_state":
        session.add(_next_self_state(self_state))
    else:
        extra_baseline = _next_baseline(baseline)
        session.add(extra_baseline)
        session.flush()
        session.add(
            _next_self_state(
                self_state,
                baseline_face_model_id=extra_baseline.id,
                version=1,
            )
        )

    with pytest.raises(DBAPIError, match="one complete final authority graph"):
        session.commit()
    session.rollback()
    assert _authority_counts(session, job_id=job.id, observation_id=observation.id) == (1, 3, 1, 1)


def test_populated_analysis_run_blocks_downgrade_before_ddl(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor, demo_session, identity = _analysis_context(session)
    _, run, _ = _pending_analysis(session, actor, demo_session, identity)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _alembic_config(database_url)
    run_id = run.id
    session.close()

    with pytest.raises(Exception, match="downgrade blocked by D03 AnalysisRun"):
        command.downgrade(config, _DOWN)

    engine = create_engine(database_url)
    try:
        with Session(engine) as current:
            assert current.get(DemoAnalysisRun, run_id) is not None
    finally:
        engine.dispose()


def test_upgrade_preserves_legacy_v1_observation_without_resigning(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor, demo_session, identity = _analysis_context(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _alembic_config(database_url)
    actor_id = actor.id
    session_id = demo_session.id
    identity_id = identity.id
    source_asset_id = identity.formal_canonical_asset_id
    source_asset_sha256 = identity.formal_canonical_asset_sha256
    session.close()
    command.downgrade(config, _DOWN)
    engine = create_engine(database_url)
    legacy_id = new_id()
    legacy = _build_demo_row(
        DemoFaceObservation,
        row_id=legacy_id,
        authority_schema_version="mirror.demo/DemoFaceObservation/v1",
        demo_actor_id=actor_id,
        demo_session_id=session_id,
        demo_synthetic_identity_id=identity_id,
        source_asset_id=source_asset_id,
        source_asset_sha256=source_asset_sha256,
        analysis_run_id=None,
        analyzer_version="legacy-demo-analyzer-v1",
        runtime_manifest_digest=_DIGEST_A,
        config_digest=_DIGEST_B,
        repeat_count=3,
        observation_state="SUPPORTED",
        unsupported_reason=None,
    )
    try:
        with Session(engine) as legacy_session:
            _persist_historical_authority_rows(legacy_session, legacy)
        payload_before: dict[str, Any] = dict(legacy.canonical_payload)
        digest_before = legacy.content_digest
        command.upgrade(config, _HEAD)
        with Session(engine) as upgraded:
            preserved = upgraded.get(DemoFaceObservation, legacy_id)
            assert preserved is not None
            assert preserved.analysis_run_id is None
            assert preserved.canonical_payload == payload_before
            assert preserved.content_digest == digest_before

            injected = _build_demo_row(
                DemoFaceObservation,
                authority_schema_version="mirror.demo/DemoFaceObservation/v1",
                demo_actor_id=actor_id,
                demo_session_id=session_id,
                demo_synthetic_identity_id=identity_id,
                source_asset_id=source_asset_id,
                source_asset_sha256=source_asset_sha256,
                analysis_run_id=None,
                analyzer_version="legacy-demo-analyzer-v1",
                runtime_manifest_digest=_DIGEST_A,
                config_digest=_DIGEST_B,
                repeat_count=3,
                observation_state="SUPPORTED",
                unsupported_reason=None,
            )
            upgraded.add(injected)
            with pytest.raises(DBAPIError, match="requires v2 AnalysisRun"):
                upgraded.commit()
            upgraded.rollback()
    finally:
        command.upgrade(config, _HEAD)
        engine.dispose()
