from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, create_engine, delete, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_geometry_variant_authority_invariants import _canonical_source, _result_asset

from mirror_api.demo_models import (
    DEMO_TABLE_NAMES,
    DemoAcceptedVisualEpisode,
    DemoActor,
    DemoAestheticProfile,
    DemoBaselineFaceModel,
    DemoContextCompilation,
    DemoDesiredDeltaProfile,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoFaceObservation,
    DemoFaceObservationRepeat,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoQuestionBank,
    DemoQuestionnaireRun,
    DemoQuestionnaireStep,
    DemoQuestionPair,
    DemoReferenceProfile,
    DemoSelfState,
    DemoSelfTransferRun,
    DemoSession,
    DemoStyleProfile,
    DemoSyntheticIdentity,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.models import (
    Asset,
    AssetVariant,
    Job,
    JobAttempt,
    SyntheticIdentity,
    SyntheticQARun,
    new_id,
    utcnow,
)

DEMO_REVISION = "demo_0001_p3_p7_core"
FORMAL_DOWN_REVISION = "0014_m5_eval_authority"
GENESIS_DIGEST = "0" * 64
_NON_AUTHORITY_COLUMNS = {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
    "closed_at",
    "tombstoned_at",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(schema_version: str, payload: dict[str, Any]) -> str:
    authority = f"{schema_version}\n{_canonical_json(payload)}".encode()
    return hashlib.sha256(authority).hexdigest()


def _authority_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _insert_demo_row(
    session: Session,
    model: type[Any],
    /,
    *,
    created_at: datetime | None = None,
    **authority_fields: Any,
) -> Any:
    authority_created_at = created_at or datetime(2026, 8, 23, 3, 0, tzinfo=UTC)
    schema_version = f"mirror.demo/{model.__name__}/v1"
    row = model(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload={},
        content_digest="0" * 64,
        created_at=authority_created_at,
        **authority_fields,
    )
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:
        if column.name in _NON_AUTHORITY_COLUMNS:
            continue
        value = getattr(row, column.name)
        if value is JSON.NULL:
            payload[column.name] = None
        else:
            payload[column.name] = _authority_time(value) if isinstance(value, datetime) else value
    row.canonical_payload = payload
    row.content_digest = _digest(schema_version, payload)
    session.add(row)
    session.commit()
    return row


def _insert_job_binding(
    session: Session,
    actor: DemoActor,
    *,
    endpoint_operation: str,
    target_type: str,
    target_id: str,
    demo_session: DemoSession | None,
    request_digest: str | None = None,
) -> tuple[Job, DemoJobBinding]:
    client_key_hash = hashlib.sha256(new_id().encode()).hexdigest()
    formal_hash = hashlib.sha256(
        (
            f"mirror.demo/JobIdempotency/v1\n{actor.id}\n{endpoint_operation}\n{client_key_hash}"
        ).encode()
    ).hexdigest()
    job = Job(
        id=new_id(),
        job_type=f"demo_p3_p7.{endpoint_operation}",
        status="PENDING",
        idempotency_key_hash=formal_hash,
        request_id=f"demo-d01b-{new_id()}",
        payload={},
        owner_user_id=None,
    )
    session.add(job)
    session.commit()
    binding = _insert_demo_row(
        session,
        DemoJobBinding,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id if demo_session is not None else None,
        job_id=job.id,
        endpoint_operation=endpoint_operation,
        idempotency_key_hash=client_key_hash,
        request_digest=request_digest or hashlib.sha256(new_id().encode()).hexdigest(),
        target_type=target_type,
        target_id=target_id,
    )
    return job, binding


def _truncate_demo_authority(session: Session) -> None:
    table_list = ", ".join(sorted(DEMO_TABLE_NAMES))
    session.execute(text(f"TRUNCATE TABLE {table_list} CASCADE"))
    session.execute(
        text("DELETE FROM asset_variants WHERE variant_type LIKE 'demo_p3_p7\\_%' ESCAPE '\\'")
    )
    session.execute(
        text(
            "DELETE FROM job_attempts WHERE job_id IN "
            "(SELECT id FROM jobs WHERE job_type LIKE 'demo_p3_p7.%')"
        )
    )
    session.execute(text("DELETE FROM jobs WHERE job_type LIKE 'demo_p3_p7.%'"))
    session.commit()


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with Session(engine) as db_session:
        _truncate_demo_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_authority(db_session)
    engine.dispose()


def _insert_actor(
    session: Session,
    *,
    actor_id: str | None = None,
    credential_key_id: str | None = None,
) -> DemoActor:
    authority_at = datetime(2026, 8, 23, 0, 0, tzinfo=UTC)
    schema_version = "mirror.demo/DemoActor/v1"
    payload = {
        "actor_kind": "AUTOMATED_TEST",
        "authority_at": _authority_time(authority_at),
        "credential_key_id": credential_key_id or new_id() + new_id(),
    }
    actor = DemoActor(
        id=actor_id or new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=authority_at,
        actor_kind="AUTOMATED_TEST",
        credential_key_id=payload["credential_key_id"],
        authority_at=authority_at,
    )
    session.add(actor)
    session.commit()
    return actor


def _insert_session(session: Session, actor: DemoActor, *, config: dict[str, Any]) -> DemoSession:
    expires_at = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    schema_version = "mirror.demo/DemoSession/v1"
    payload = {
        "config": config,
        "context_seed": "1" * 64,
        "demo_actor_id": actor.id,
        "expires_at": _authority_time(expires_at),
    }
    demo_session = DemoSession(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=actor.created_at,
        demo_actor_id=actor.id,
        config=config,
        context_seed="1" * 64,
        expires_at=expires_at,
    )
    session.add(demo_session)
    session.commit()
    return demo_session


def _insert_preference_event(
    session: Session,
    actor: DemoActor,
    *,
    sequence: int,
    previous_digest: str,
    signal: dict[str, Any],
    demo_session: DemoSession | None = None,
    event_type: str = "EXPLICIT_STYLE_SELECTION",
    source_type: str = "EXPLICIT_USER_ACTION",
    target_type: str | None = None,
    target_id: str | None = None,
    occurred_at: datetime | None = None,
    commit: bool = True,
) -> DemoPreferenceEvent:
    event_time = occurred_at or datetime(2026, 8, 23, 1, sequence, tzinfo=UTC)
    schema_version = "mirror.demo/DemoPreferenceEvent/v1"
    payload = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id if demo_session is not None else None,
        "event_sequence": sequence,
        "event_type": event_type,
        "occurred_at": _authority_time(event_time),
        "previous_event_digest": previous_digest,
        "signal": signal,
        "source_type": source_type,
        "target_id": target_id,
        "target_type": target_type,
    }
    event = DemoPreferenceEvent(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=event_time,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id if demo_session is not None else None,
        event_sequence=sequence,
        event_type=event_type,
        source_type=source_type,
        target_type=target_type,
        target_id=target_id,
        signal=signal,
        occurred_at=event_time,
        previous_event_digest=previous_digest,
    )
    session.add(event)
    if commit:
        session.commit()
    else:
        session.flush()
    return event


def _accepted_synthetic_source(session: Session) -> tuple[Asset, SyntheticIdentity]:
    """Reuse a qualified formal fixture when present; create it only on a fresh database."""
    identity = session.scalar(
        select(SyntheticIdentity)
        .join(Asset, Asset.id == SyntheticIdentity.canonical_asset_id)
        .join(SyntheticQARun, SyntheticQARun.id == SyntheticIdentity.accepted_qa_run_id)
        .where(
            SyntheticIdentity.bank_version_id.is_(None),
            SyntheticIdentity.authority_kind == "CANONICAL_QA",
            SyntheticIdentity.adult_synthetic_attested.is_(True),
            SyntheticQARun.status == "PASSED",
            SyntheticQARun.normalized_asset_id == SyntheticIdentity.canonical_asset_id,
            Asset.owner_user_id.is_(None),
            Asset.synthetic.is_(True),
            Asset.deleted_at.is_(None),
        )
    )
    if identity is not None:
        source_asset = session.get(Asset, identity.canonical_asset_id)
        assert source_asset is not None
        return source_asset, identity
    source_asset, identity, _, _ = _canonical_source(session)
    return source_asset, identity


def _result_variant(
    session: Session, source_asset: Asset, *, sha: str, variant_type: str
) -> tuple[Asset, AssetVariant]:
    result_asset = _result_asset(session, source_asset, sha=sha)
    variant = AssetVariant(
        id=new_id(),
        source_asset_id=source_asset.id,
        result_asset_id=result_asset.id,
        variant_type=variant_type,
    )
    session.add(variant)
    session.commit()
    return result_asset, variant


def _insert_episode(
    session: Session, graph: dict[str, Any], trajectory_digests: list[str]
) -> DemoAcceptedVisualEpisode:
    actor = graph["actor"]
    demo_session = graph["session"]
    editing_session = graph["editing_session"]
    image0 = graph["image0"]
    image1 = graph["image1"]
    verification = graph["verification"]
    accepted_event = graph["accepted_event"]
    desired_delta = graph["desired_delta"]
    return _insert_demo_row(
        session,
        DemoAcceptedVisualEpisode,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        editing_session_id=editing_session.id,
        accepted_image_version_id=image1.id,
        verification_result_id=verification.id,
        acceptance_event_id=accepted_event.id,
        source_asset_id=image0.source_asset_id,
        source_asset_sha256=graph["source_asset"].sha256,
        final_asset_id=image1.result_asset_id,
        final_asset_sha256=graph["image1_asset"].sha256,
        trajectory_digests=trajectory_digests,
        profile_digest=desired_delta.content_digest,
        context_digest=editing_session.context_digest,
        instruction_digest=editing_session.instruction_digest,
    )


def _insert_full_demo_graph(session: Session, *, include_episode: bool = True) -> dict[str, Any]:
    """Insert one valid authority lineage spanning every Demo table."""

    def digest(character: str) -> str:
        return character * 64

    actor = _insert_actor(session)
    demo_session = _insert_session(session, actor, config={"graph": 1})
    source_asset, formal_identity = _accepted_synthetic_source(session)
    synthetic_identity = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        formal_synthetic_identity_id=formal_identity.id,
        admission_sequence=1,
        admission_action="ADMIT",
        admission_config_digest=digest("1"),
        supersedes_id=None,
    )
    observation = _insert_demo_row(
        session,
        DemoFaceObservation,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        demo_synthetic_identity_id=synthetic_identity.id,
        source_asset_id=source_asset.id,
        source_asset_sha256=source_asset.sha256,
        analyzer_version="fixture-analyzer-v1",
        runtime_manifest_digest=digest("2"),
        config_digest=digest("3"),
        repeat_count=3,
        observation_state="SUPPORTED",
        unsupported_reason=None,
    )
    repeats = [
        _insert_demo_row(
            session,
            DemoFaceObservationRepeat,
            demo_actor_id=actor.id,
            demo_session_id=demo_session.id,
            observation_id=observation.id,
            repeat_index=index,
            runtime_manifest_digest=digest("2"),
            model_manifest_digest=digest("4"),
            landmarks=[0] * 478,
            pose={"yaw_ppm": 0},
            quality={"score_ppm": 1_000_000},
            measurements={"jaw_width_ppm": 0},
        )
        for index in range(1, 4)
    ]
    baseline = _insert_demo_row(
        session,
        DemoBaselineFaceModel,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        observation_id=observation.id,
        version=1,
        aggregation_version="fixture-aggregate-v1",
        measurement_version="fixture-measure-v1",
        ordered_repeat_digests=[repeat.content_digest for repeat in repeats],
        measurements={"jaw_width_ppm": 0},
        reliability={"jaw_width_ppm": 1_000_000},
        uncertainty={"jaw_width_ppm": 0},
        unsupported_state={},
    )
    self_state = _insert_demo_row(
        session,
        DemoSelfState,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        baseline_face_model_id=baseline.id,
        version=1,
        ontology_version="fixture-ontology-v1",
        derivation_version="fixture-derive-v1",
        measurements={"jaw_width_ppm": 0},
        reliability={"jaw_width_ppm": 1_000_000},
        uncertainty={"jaw_width_ppm": 0},
        routing_eligibility={"eligible": 1},
    )
    bank = _insert_demo_row(
        session,
        DemoQuestionBank,
        version=f"fixture-bank-{new_id()}",
        algorithm_config_digest=digest("5"),
        routing_version="fixture-route-v1",
        stopping_version="fixture-stop-v1",
        neighborhood_version="fixture-neighborhood-v1",
        pair_manifest_digest=digest("6"),
        dimension_manifest=[{"key": "jaw_width"}],
    )
    left_asset, left_variant = _result_variant(
        session, source_asset, sha=digest("7"), variant_type="demo_p3_p7_question_left"
    )
    right_asset, right_variant = _result_variant(
        session, source_asset, sha=digest("8"), variant_type="demo_p3_p7_question_right"
    )
    question_pair = _insert_demo_row(
        session,
        DemoQuestionPair,
        question_bank_id=bank.id,
        demo_synthetic_identity_id=synthetic_identity.id,
        source_asset_id=source_asset.id,
        source_asset_sha256=source_asset.sha256,
        left_asset_id=left_asset.id,
        left_asset_sha256=left_asset.sha256,
        right_asset_id=right_asset.id,
        right_asset_sha256=right_asset.sha256,
        left_asset_variant_id=left_variant.id,
        right_asset_variant_id=right_variant.id,
        dimension_key="jaw_width",
        magnitude_ppm=10_000,
        left_delta_ppm=-10_000,
        right_delta_ppm=10_000,
        pair_quality_ppm=1_000_000,
        qa_payload={"passed": 1},
    )
    questionnaire_run = _insert_demo_row(
        session,
        DemoQuestionnaireRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        question_bank_id=bank.id,
        self_state_id=self_state.id,
        algorithm_config_digest=bank.algorithm_config_digest,
        seed=1,
        max_questions=12,
        initial_posterior={"jaw_width_ppm": 0},
    )
    questionnaire_step = _insert_demo_row(
        session,
        DemoQuestionnaireStep,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        questionnaire_run_id=questionnaire_run.id,
        event_sequence=1,
        step_number=1,
        event_type="PRESENTED",
        question_pair_id=question_pair.id,
        routing_snapshot={"selected": 1},
        response_snapshot=None,
        posterior_before={"jaw_width_ppm": 0},
        posterior_after={"jaw_width_ppm": 0},
        scheduler_version="fixture-scheduler-v1",
    )
    source_event = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"locked": 1},
        demo_session=demo_session,
        event_type="FEATURE_LOCKED",
    )
    _, compiler_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="profile.compile",
        target_type="DEMO_ACTOR",
        target_id=actor.id,
        demo_session=demo_session,
    )
    desired_delta = _insert_demo_row(
        session,
        DemoDesiredDeltaProfile,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        self_state_id=self_state.id,
        demo_job_binding_id=compiler_binding.id,
        version=1,
        as_of_event_sequence=1,
        compilation_watermark=source_event.content_digest,
        compiler_version="fixture-profile-v1",
        dimensions={"jaw_width_ppm": 10_000},
        evidence_digests=[source_event.content_digest],
        restraint={"max_ppm": 10_000},
    )
    style = _insert_demo_row(
        session,
        DemoStyleProfile,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        demo_job_binding_id=compiler_binding.id,
        version=1,
        as_of_event_sequence=1,
        compilation_watermark=source_event.content_digest,
        compiler_version="fixture-style-v1",
        preferences={"finish": "natural"},
        negative_evidence=[],
        evidence_digests=[source_event.content_digest],
    )
    constraints = _insert_demo_row(
        session,
        DemoIdentityConstraints,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        self_state_id=self_state.id,
        version=1,
        constraint_scope="SESSION_OVERRIDE",
        source_event_digests=[source_event.content_digest],
        locks={"identity": 1},
        bounds={"max_ppm": 10_000},
        prohibited_operations=[],
    )
    transfer_request = _insert_demo_row(
        session,
        DemoSelfTransferRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        record_kind="REQUEST",
        request_run_id=None,
        demo_job_binding_id=None,
        source_asset_id=source_asset.id,
        result_asset_id=None,
        requested_delta={"jaw_width_ppm": 10_000},
        measured_delta=None,
        non_target_drift=None,
        verifier_digest=None,
        user_outcome=None,
    )
    _, transfer_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="self_transfer.execute",
        target_type="SELF_TRANSFER_RUN",
        target_id=transfer_request.id,
        demo_session=demo_session,
    )
    transfer_asset = _result_asset(session, source_asset, sha=digest("9"))
    transfer_result = _insert_demo_row(
        session,
        DemoSelfTransferRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        record_kind="RESULT",
        request_run_id=transfer_request.id,
        demo_job_binding_id=transfer_binding.id,
        source_asset_id=source_asset.id,
        result_asset_id=transfer_asset.id,
        requested_delta={"jaw_width_ppm": 10_000},
        measured_delta={"jaw_width_ppm": 10_000},
        non_target_drift={"max_ppm": 0},
        verifier_digest=digest("a"),
        user_outcome="ACCEPTED",
    )
    reference_profile = _insert_demo_row(
        session,
        DemoReferenceProfile,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        style_profile_id=style.id,
        identity_constraints_id=constraints.id,
        version=1,
        source_assets=[
            {"asset_id": source_asset.id, "sha256": source_asset.sha256, "view": "FRONT"}
        ],
        analysis_version="fixture-reference-v1",
        compiler_version="fixture-reference-compiler-v1",
        structured_profile={"reference": 1},
        evidence_digests=[source_event.content_digest],
    )
    editing_session = _insert_demo_row(
        session,
        DemoEditingSession,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        source_asset_id=source_asset.id,
        source_asset_sha256=source_asset.sha256,
        desired_delta_profile_digest=desired_delta.content_digest,
        style_profile_digest=style.content_digest,
        identity_constraints_digest=constraints.content_digest,
        context_digest=digest("b"),
        instruction_digest=digest("c"),
        tool_registry_version="fixture-tools-v1",
        closed_at=None,
        tombstoned_at=None,
    )
    image0_asset = _result_asset(session, source_asset, sha=digest("d"))
    image0 = _insert_demo_row(
        session,
        DemoImageVersion,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        editing_session_id=editing_session.id,
        sequence=0,
        parent_version_id=None,
        source_asset_id=source_asset.id,
        result_asset_id=image0_asset.id,
        result_asset_variant_id=None,
        version_kind="ORIGINAL",
        plan_digest=None,
        tool_run_digest=None,
        verifier_digest=None,
    )
    plan_fields = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id,
        "editing_session_id": editing_session.id,
        "input_image_version_id": image0.id,
        "plan_version": 1,
        "desired_delta_profile_digest": desired_delta.content_digest,
        "style_profile_digest": style.content_digest,
        "identity_constraints_digest": constraints.content_digest,
        "instruction_digest": editing_session.instruction_digest,
        "planner_version": "fixture-planner-v1",
        "tool_registry_version": editing_session.tool_registry_version,
    }
    request_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="REQUEST",
        request_plan_id=None,
        operation_specs=[],
    )
    result_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="RESULT",
        request_plan_id=request_plan.id,
        operation_specs=[{"operation": "fixture"}],
    )
    operation = _insert_demo_row(
        session,
        DemoEditOperation,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        edit_plan_id=result_plan.id,
        operation_index=0,
        engine="GEOMETRY",
        operation_type="fixture_warp",
        parameters={"delta_ppm": 10_000},
        preserve=["identity"],
        expected_effect={"jaw_width_ppm": 10_000},
    )
    execution_job, execution_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="edit_plan.execute",
        target_type="EDIT_PLAN",
        target_id=result_plan.id,
        demo_session=demo_session,
    )
    attempt = JobAttempt(
        id=new_id(),
        job_id=execution_job.id,
        attempt=1,
        status="PENDING",
        started_at=utcnow(),
    )
    session.add(attempt)
    session.commit()
    image1_asset, image1_variant = _result_variant(
        session, image0_asset, sha=digest("e"), variant_type="demo_p3_p7_edit_result"
    )
    tool_run = _insert_demo_row(
        session,
        DemoToolRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        edit_operation_id=operation.id,
        demo_job_binding_id=execution_binding.id,
        formal_job_attempt_id=attempt.id,
        tool_name="fixture-tool",
        tool_version="fixture-tool-v1",
        input_asset_id=image0_asset.id,
        input_asset_sha256=image0_asset.sha256,
        output_asset_id=image1_asset.id,
        output_asset_sha256=image1_asset.sha256,
        effect_contract={"identity_preserved": 1},
        outcome="COMPLETED",
    )
    image1 = _insert_demo_row(
        session,
        DemoImageVersion,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        editing_session_id=editing_session.id,
        sequence=1,
        parent_version_id=image0.id,
        source_asset_id=image0_asset.id,
        result_asset_id=image1_asset.id,
        result_asset_variant_id=image1_variant.id,
        version_kind="EDITED",
        plan_digest=result_plan.content_digest,
        tool_run_digest=tool_run.content_digest,
        verifier_digest=digest("f"),
    )
    _, verification_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="tool.verify",
        target_type="TOOL_RUN",
        target_id=tool_run.id,
        demo_session=demo_session,
    )
    verification = _insert_demo_row(
        session,
        DemoVerificationResult,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        tool_run_id=tool_run.id,
        image_version_id=image1.id,
        demo_job_binding_id=verification_binding.id,
        output_asset_id=image1_asset.id,
        output_asset_sha256=image1_asset.sha256,
        verifier_version="fixture-verify-v1",
        config_digest=digest("f"),
        metrics={"identity_ppm": 1_000_000},
        thresholds={"identity_min_ppm": 900_000},
        outcome="PASS",
        reason_codes=[],
    )
    accepted_event = _insert_preference_event(
        session,
        actor,
        sequence=2,
        previous_digest=source_event.content_digest,
        signal={"accepted": 1},
        demo_session=demo_session,
        event_type="IMAGE_ACCEPTED",
        source_type="EXPLICIT_USER_ACTION",
        target_type="IMAGE_VERSION",
        target_id=image1.id,
    )
    aesthetic_profile = _insert_demo_row(
        session,
        DemoAestheticProfile,
        demo_actor_id=actor.id,
        demo_job_binding_id=compiler_binding.id,
        generation=1,
        as_of_event_sequence=2,
        compilation_watermark=accepted_event.content_digest,
        reset_epoch=0,
        compiler_version="fixture-aesthetic-v1",
        evidence_digests=[accepted_event.content_digest],
        profile_payload={"accepted_episode": 1},
    )
    _, context_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="context.compile",
        target_type="DEMO_SESSION",
        target_id=demo_session.id,
        demo_session=demo_session,
    )
    context = _insert_demo_row(
        session,
        DemoContextCompilation,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        aesthetic_profile_id=aesthetic_profile.id,
        demo_job_binding_id=context_binding.id,
        context_as_of_time=datetime(2026, 8, 23, 4, 0, tzinfo=UTC),
        compilation_watermark=accepted_event.content_digest,
        compiler_version="fixture-context-v1",
        current_instruction_digest=editing_session.instruction_digest,
        selected_evidence=[{"digest": accepted_event.content_digest}],
        rejected_evidence=[],
        budgets={"tokens": 1},
        trace_payload={"selected": 1},
        expires_at=datetime(2026, 8, 24, 4, 0, tzinfo=UTC),
    )
    graph = {
        "actor": actor,
        "session": demo_session,
        "source_asset": source_asset,
        "synthetic_identity": synthetic_identity,
        "observation": observation,
        "repeats": repeats,
        "baseline": baseline,
        "self_state": self_state,
        "bank": bank,
        "question_pair": question_pair,
        "questionnaire_run": questionnaire_run,
        "questionnaire_step": questionnaire_step,
        "source_event": source_event,
        "compiler_binding": compiler_binding,
        "desired_delta": desired_delta,
        "style": style,
        "constraints": constraints,
        "transfer_request": transfer_request,
        "transfer_result": transfer_result,
        "reference_profile": reference_profile,
        "editing_session": editing_session,
        "image0": image0,
        "request_plan": request_plan,
        "result_plan": result_plan,
        "operation": operation,
        "execution_binding": execution_binding,
        "tool_run": tool_run,
        "image1": image1,
        "image1_asset": image1_asset,
        "verification": verification,
        "accepted_event": accepted_event,
        "aesthetic_profile": aesthetic_profile,
        "context": context,
        "context_binding": context_binding,
    }
    if include_episode:
        graph["episode"] = _insert_episode(
            session, graph, [image0.content_digest, image1.content_digest]
        )
    return graph


def test_full_demo_authority_graph_covers_every_table(session: Session) -> None:
    graph = _insert_full_demo_graph(session)
    authority_rows = [
        row
        for value in graph.values()
        for row in (value if isinstance(value, list) else [value])
        if getattr(row, "__table__", None) is not None and row.__table__.name in DEMO_TABLE_NAMES
    ]
    assert {row.__table__.name for row in authority_rows} == set(DEMO_TABLE_NAMES)
    for table_name in DEMO_TABLE_NAMES:
        assert session.scalar(text(f"SELECT count(*) FROM {table_name}")) >= 1  # noqa: S608


def test_every_demo_authority_row_rejects_direct_update_and_delete(session: Session) -> None:
    _insert_full_demo_graph(session)
    for table_name in sorted(DEMO_TABLE_NAMES):
        row_id = session.scalar(text(f"SELECT id FROM {table_name} LIMIT 1"))  # noqa: S608
        assert row_id is not None
        with pytest.raises(DBAPIError):
            session.execute(
                text(f"UPDATE {table_name} SET content_digest=content_digest WHERE id=:row_id"),  # noqa: S608
                {"row_id": row_id},
            )
        session.rollback()
        with pytest.raises(DBAPIError):
            session.execute(
                text(f"DELETE FROM {table_name} WHERE id=:row_id"),  # noqa: S608
                {"row_id": row_id},
            )
        session.rollback()


def test_cross_owner_and_session_references_fail_closed(session: Session) -> None:
    graph = _insert_full_demo_graph(session)
    other_actor = _insert_actor(session)
    other_session = _insert_session(session, other_actor, config={"other": 1})
    source_asset = graph["source_asset"]

    with pytest.raises(DBAPIError, match="ReferenceProfile input ownership mismatch"):
        _insert_demo_row(
            session,
            DemoReferenceProfile,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            desired_delta_profile_id=graph["desired_delta"].id,
            style_profile_id=None,
            identity_constraints_id=None,
            version=1,
            source_assets=[
                {"asset_id": source_asset.id, "sha256": source_asset.sha256, "view": "FRONT"}
            ],
            analysis_version="fixture-reference-v1",
            compiler_version="fixture-reference-compiler-v1",
            structured_profile={"reference": 1},
            evidence_digests=[graph["source_event"].content_digest],
        )
    session.rollback()

    foreign_result = _result_asset(session, source_asset, sha="b" * 64)
    with pytest.raises(DBAPIError):
        _insert_demo_row(
            session,
            DemoImageVersion,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            editing_session_id=graph["editing_session"].id,
            sequence=0,
            parent_version_id=None,
            source_asset_id=source_asset.id,
            result_asset_id=foreign_result.id,
            result_asset_variant_id=None,
            version_kind="ORIGINAL",
            plan_digest=None,
            tool_run_digest=None,
            verifier_digest=None,
        )
    session.rollback()

    _, context_binding = _insert_job_binding(
        session,
        other_actor,
        endpoint_operation="context.compile",
        target_type="DEMO_SESSION",
        target_id=other_session.id,
        demo_session=other_session,
    )
    with pytest.raises(DBAPIError, match="ContextCompilation ownership mismatch"):
        _insert_demo_row(
            session,
            DemoContextCompilation,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            aesthetic_profile_id=graph["aesthetic_profile"].id,
            demo_job_binding_id=context_binding.id,
            context_as_of_time=datetime(2026, 8, 23, 5, 0, tzinfo=UTC),
            compilation_watermark="c" * 64,
            compiler_version="fixture-context-v1",
            current_instruction_digest="d" * 64,
            selected_evidence=[],
            rejected_evidence=[],
            budgets={"tokens": 1},
            trace_payload={"selected": 1},
            expires_at=datetime(2026, 8, 24, 5, 0, tzinfo=UTC),
        )
    session.rollback()

    with pytest.raises(DBAPIError):
        _insert_demo_row(
            session,
            DemoFaceObservationRepeat,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            observation_id=graph["observation"].id,
            repeat_index=1,
            runtime_manifest_digest="2" * 64,
            model_manifest_digest="4" * 64,
            landmarks=[0] * 478,
            pose={"yaw_ppm": 0},
            quality={"score_ppm": 1_000_000},
            measurements={"jaw_width_ppm": 0},
        )
    session.rollback()


def test_profile_and_context_evidence_requires_existing_actor_authority(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session)
    foreign_actor = _insert_actor(session)
    foreign_session = _insert_session(session, foreign_actor, config={"foreign": 1})
    foreign_event = _insert_preference_event(
        session,
        foreign_actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"style_context": "foreign"},
        demo_session=foreign_session,
    )
    foreign_digest = foreign_event.content_digest

    with pytest.raises(DBAPIError, match="DesiredDelta evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoDesiredDeltaProfile,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            self_state_id=graph["self_state"].id,
            demo_job_binding_id=graph["compiler_binding"].id,
            version=2,
            as_of_event_sequence=2,
            compilation_watermark=foreign_digest,
            compiler_version="fixture-profile-v1",
            dimensions={"jaw_width_ppm": 9_000},
            evidence_digests=[foreign_digest],
            restraint={"max_ppm": 9_000},
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="StyleProfile evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoStyleProfile,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            desired_delta_profile_id=graph["desired_delta"].id,
            demo_job_binding_id=graph["compiler_binding"].id,
            version=2,
            as_of_event_sequence=2,
            compilation_watermark=foreign_digest,
            compiler_version="fixture-style-v1",
            preferences={"finish": "editorial"},
            negative_evidence=[],
            evidence_digests=[foreign_digest],
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="ReferenceProfile evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoReferenceProfile,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            desired_delta_profile_id=graph["desired_delta"].id,
            style_profile_id=graph["style"].id,
            identity_constraints_id=graph["constraints"].id,
            version=2,
            source_assets=[
                {
                    "asset_id": graph["source_asset"].id,
                    "sha256": graph["source_asset"].sha256,
                    "view": "FRONT",
                }
            ],
            analysis_version="fixture-reference-v1",
            compiler_version="fixture-reference-compiler-v1",
            structured_profile={"reference": 2},
            evidence_digests=[foreign_digest],
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="AestheticProfile evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoAestheticProfile,
            demo_actor_id=graph["actor"].id,
            demo_job_binding_id=graph["compiler_binding"].id,
            generation=2,
            as_of_event_sequence=2,
            compilation_watermark=foreign_digest,
            reset_epoch=0,
            compiler_version="fixture-aesthetic-v1",
            evidence_digests=[foreign_digest],
            profile_payload={"accepted_episode": 2},
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="ContextCompilation evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoContextCompilation,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            aesthetic_profile_id=graph["aesthetic_profile"].id,
            demo_job_binding_id=graph["context_binding"].id,
            context_as_of_time=datetime(2026, 8, 23, 5, 0, tzinfo=UTC),
            compilation_watermark=graph["accepted_event"].content_digest,
            compiler_version="fixture-context-v1",
            current_instruction_digest=graph["editing_session"].instruction_digest,
            selected_evidence=[{"digest": foreign_digest}],
            rejected_evidence=[],
            budgets={"tokens": 1},
            trace_payload={"selected": 1},
            expires_at=datetime(2026, 8, 24, 5, 0, tzinfo=UTC),
        )
    session.rollback()

    unknown_digest = hashlib.sha256(b"missing-demo-evidence").hexdigest()
    with pytest.raises(DBAPIError, match="ContextCompilation evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoContextCompilation,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            aesthetic_profile_id=graph["aesthetic_profile"].id,
            demo_job_binding_id=graph["context_binding"].id,
            context_as_of_time=datetime(2026, 8, 23, 6, 0, tzinfo=UTC),
            compilation_watermark=graph["accepted_event"].content_digest,
            compiler_version="fixture-context-v1",
            current_instruction_digest=graph["editing_session"].instruction_digest,
            selected_evidence=[{"digest": unknown_digest}],
            rejected_evidence=[],
            budgets={"tokens": 1},
            trace_payload={"selected": 1},
            expires_at=datetime(2026, 8, 24, 6, 0, tzinfo=UTC),
        )
    session.rollback()


def test_context_evidence_allows_same_actor_next_session_recall(session: Session) -> None:
    graph = _insert_full_demo_graph(session)
    next_session = _insert_session(session, graph["actor"], config={"next_session": 1})
    _, next_binding = _insert_job_binding(
        session,
        graph["actor"],
        endpoint_operation="context.compile",
        target_type="DEMO_SESSION",
        target_id=next_session.id,
        demo_session=next_session,
    )
    context = _insert_demo_row(
        session,
        DemoContextCompilation,
        demo_actor_id=graph["actor"].id,
        demo_session_id=next_session.id,
        aesthetic_profile_id=graph["aesthetic_profile"].id,
        demo_job_binding_id=next_binding.id,
        context_as_of_time=datetime(2026, 8, 23, 7, 0, tzinfo=UTC),
        compilation_watermark=graph["accepted_event"].content_digest,
        compiler_version="fixture-context-v1",
        current_instruction_digest=hashlib.sha256(b"next-session-instruction").hexdigest(),
        selected_evidence=[{"digest": graph["accepted_event"].content_digest}],
        rejected_evidence=[],
        budgets={"tokens": 1},
        trace_payload={"recalled_previous_session": 1},
        expires_at=datetime(2026, 8, 24, 7, 0, tzinfo=UTC),
    )
    assert context.demo_session_id == next_session.id


@pytest.mark.parametrize(
    "trajectory_factory",
    (
        lambda graph: [graph["image1"].content_digest],
        lambda graph: [graph["image1"].content_digest, graph["image0"].content_digest],
        lambda graph: [graph["image0"].content_digest, "0" * 64],
    ),
    ids=("omitted-root", "wrong-order", "foreign-digest"),
)
def test_accepted_episode_requires_exact_root_to_leaf_trajectory(
    session: Session, trajectory_factory: Any
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    with pytest.raises(DBAPIError, match="accepted episode trajectory lineage mismatch"):
        _insert_episode(session, graph, trajectory_factory(graph))
    session.rollback()
    episode = _insert_episode(
        session, graph, [graph["image0"].content_digest, graph["image1"].content_digest]
    )
    assert episode.trajectory_digests == [
        graph["image0"].content_digest,
        graph["image1"].content_digest,
    ]


def test_demo_metadata_and_database_objects_match(session: Session) -> None:
    assert len(DEMO_TABLE_NAMES) == 27
    database_tables = set(
        session.scalars(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename LIKE 'demo_%'"
            )
        )
    )
    assert database_tables == set(DEMO_TABLE_NAMES)
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_authority_%'"
            )
        )
        == 27
    )
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_terminal_binding_%'"
            )
        )
        == 4
    )
    assert session.scalar(
        text("SELECT to_regprocedure('mirror_demo_evidence_owned_by(text,text)') IS NOT NULL")
    )
    assert session.scalar(
        text("SELECT to_regprocedure('mirror_demo_validate_terminal_binding()') IS NOT NULL")
    )
    assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION


def test_canonical_json_digest_and_integer_numeric_authority(session: Session) -> None:
    assert (
        session.scalar(
            text("SELECT mirror_demo_canonical_json(jsonb_build_object('b', 2, 'a', 1))")
        )
        == '{"a":1,"b":2}'
    )
    negative_zero, zero, same_value = session.execute(
        text(
            "SELECT mirror_demo_canonical_json('-0'::jsonb), "
            "mirror_demo_canonical_json('0'::jsonb), '-0'::jsonb = '0'::jsonb"
        )
    ).one()
    assert (negative_zero, zero, same_value) == ("0", "0", True)

    with pytest.raises(DBAPIError, match="requires integer numeric leaves"):
        session.scalar(text("SELECT mirror_demo_canonical_json('1.5'::jsonb)"))
    session.rollback()

    actor = _insert_actor(session)
    with pytest.raises(DBAPIError, match="canonical digest mismatch"):
        session.execute(
            text(
                "INSERT INTO demo_actors "
                "(id,schema_version,canonical_payload,content_digest,created_at,"
                "actor_kind,credential_key_id,authority_at,tombstoned_at) "
                "SELECT :id,schema_version,canonical_payload,:wrong_digest,created_at,"
                "actor_kind,credential_key_id,authority_at,NULL "
                "FROM demo_actors WHERE id=:source_id"
            ),
            {
                "id": new_id(),
                "wrong_digest": "f" * 64,
                "source_id": actor.id,
            },
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="disagrees with structured authority"):
        session.execute(
            text(
                "INSERT INTO demo_actors "
                "(id,schema_version,canonical_payload,content_digest,created_at,"
                "actor_kind,credential_key_id,authority_at,tombstoned_at) "
                "SELECT :id,schema_version,canonical_payload,content_digest,created_at,"
                "'LOCAL_SINGLE_USER',credential_key_id,authority_at,NULL "
                "FROM demo_actors WHERE id=:source_id"
            ),
            {"id": new_id(), "source_id": actor.id},
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="requires integer numeric leaves"):
        _insert_session(session, actor, config={"fractional": 0.5})


def test_nullable_jsonb_uses_sql_null_and_rejects_explicit_json_null(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session)
    nullable_state = session.execute(
        text(
            "SELECT response_snapshot IS NULL, jsonb_typeof(response_snapshot) "
            "FROM demo_questionnaire_steps WHERE id=:step_id"
        ),
        {"step_id": graph["questionnaire_step"].id},
    ).one()
    transfer_state = session.execute(
        text(
            "SELECT measured_delta IS NULL, jsonb_typeof(measured_delta), "
            "non_target_drift IS NULL, jsonb_typeof(non_target_drift) "
            "FROM demo_self_transfer_runs WHERE id=:run_id"
        ),
        {"run_id": graph["transfer_request"].id},
    ).one()
    assert nullable_state == (True, None)
    assert transfer_state == (True, None, True, None)

    with pytest.raises(DBAPIError, match="response_snapshot_object"):
        _insert_demo_row(
            session,
            DemoQuestionnaireStep,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            questionnaire_run_id=graph["questionnaire_run"].id,
            event_sequence=2,
            step_number=2,
            event_type="PRESENTED",
            question_pair_id=graph["question_pair"].id,
            routing_snapshot={"selected": 1},
            response_snapshot=JSON.NULL,
            posterior_before={"jaw_width_ppm": 0},
            posterior_after={"jaw_width_ppm": 0},
            scheduler_version="fixture-scheduler-v1",
        )
    session.rollback()

    for field_name, requested_ppm in (("measured_delta", 9_999), ("non_target_drift", 9_998)):
        nullable_fields = {"measured_delta": None, "non_target_drift": None}
        nullable_fields[field_name] = JSON.NULL
        with pytest.raises(DBAPIError, match=r"record_shape|_object"):
            _insert_demo_row(
                session,
                DemoSelfTransferRun,
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                desired_delta_profile_id=graph["desired_delta"].id,
                record_kind="REQUEST",
                request_run_id=None,
                demo_job_binding_id=None,
                source_asset_id=graph["source_asset"].id,
                result_asset_id=None,
                requested_delta={"jaw_width_ppm": requested_ppm},
                verifier_digest=None,
                user_outcome=None,
                **nullable_fields,
            )
        session.rollback()


def test_direct_sql_immutability_and_terminal_transition(session: Session) -> None:
    actor = _insert_actor(session)
    with pytest.raises(DBAPIError, match="Invalid Demo actor tombstone transition"):
        session.execute(
            text("UPDATE demo_actors SET credential_key_id=:value WHERE id=:actor_id"),
            {"value": new_id() + new_id(), "actor_id": actor.id},
        )
    session.rollback()
    tombstoned_at = datetime(2026, 8, 23, 2, 0, tzinfo=UTC)
    session.execute(
        text("UPDATE demo_actors SET tombstoned_at=:value WHERE id=:actor_id"),
        {"value": tombstoned_at, "actor_id": actor.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={},
        event_type="ACTOR_TOMBSTONED",
        source_type="SYSTEM_LIFECYCLE",
        target_type="DEMO_ACTOR",
        target_id=actor.id,
        occurred_at=tombstoned_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_actors SET tombstoned_at=:value WHERE id=:actor_id"),
        {"value": tombstoned_at, "actor_id": actor.id},
    )
    session.commit()
    with pytest.raises(DBAPIError, match="Invalid Demo actor tombstone transition"):
        session.execute(
            text("UPDATE demo_actors SET tombstoned_at=:value WHERE id=:actor_id"),
            {"value": tombstoned_at, "actor_id": actor.id},
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(delete(DemoActor).where(DemoActor.id == actor.id))
    session.rollback()


def test_orphan_lifecycle_event_fails_closed_at_commit(session: Session) -> None:
    actor = _insert_actor(session)
    tombstoned_at = datetime(2026, 8, 23, 2, 30, tzinfo=UTC)
    _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={},
        event_type="ACTOR_TOMBSTONED",
        source_type="SYSTEM_LIFECYCLE",
        target_type="DEMO_ACTOR",
        target_id=actor.id,
        occurred_at=tombstoned_at,
        commit=False,
    )
    with pytest.raises(DBAPIError, match="header lacks matching lifecycle event"):
        session.commit()
    session.rollback()


def test_demo_session_terminal_transitions_are_monotonic(session: Session) -> None:
    actor = _insert_actor(session)
    demo_session = _insert_session(session, actor, config={"purpose": "terminal-test"})
    closed_at = datetime(2026, 8, 23, 2, 0, tzinfo=UTC)
    tombstoned_at = datetime(2026, 8, 23, 3, 0, tzinfo=UTC)

    with pytest.raises(DBAPIError, match="Invalid Demo terminal header transition"):
        session.execute(
            text("UPDATE demo_sessions SET tombstoned_at=:value WHERE id=:session_id"),
            {"value": tombstoned_at, "session_id": demo_session.id},
        )
    session.rollback()

    session.execute(
        text("UPDATE demo_sessions SET closed_at=:value WHERE id=:session_id"),
        {"value": closed_at, "session_id": demo_session.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    close_event = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={},
        demo_session=demo_session,
        event_type="SESSION_CLOSED",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=closed_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_sessions SET closed_at=:value WHERE id=:session_id"),
        {"value": closed_at, "session_id": demo_session.id},
    )
    session.commit()

    session.execute(
        text("UPDATE demo_sessions SET tombstoned_at=:value WHERE id=:session_id"),
        {"value": tombstoned_at, "session_id": demo_session.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    _insert_preference_event(
        session,
        actor,
        sequence=2,
        previous_digest=close_event.content_digest,
        signal={"authority_id": demo_session.id, "authority_type": "DEMO_SESSION"},
        demo_session=demo_session,
        event_type="TOMBSTONE",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=tombstoned_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_sessions SET tombstoned_at=:value WHERE id=:session_id"),
        {"value": tombstoned_at, "session_id": demo_session.id},
    )
    session.commit()

    with pytest.raises(DBAPIError, match="Invalid Demo terminal header transition"):
        session.execute(
            text("UPDATE demo_sessions SET closed_at=:value WHERE id=:session_id"),
            {"value": datetime(2026, 8, 23, 4, 0, tzinfo=UTC), "session_id": demo_session.id},
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(delete(DemoSession).where(DemoSession.id == demo_session.id))
    session.rollback()


def test_editing_session_terminal_binding_rejects_wrong_target_owner_and_time(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session)
    editing_session = graph["editing_session"]
    closed_at = datetime(2026, 8, 23, 8, 0, tzinfo=UTC)
    tombstoned_at = datetime(2026, 8, 23, 9, 0, tzinfo=UTC)

    session.execute(
        text("UPDATE demo_editing_sessions SET closed_at=:value WHERE id=:editing_id"),
        {"value": closed_at, "editing_id": editing_session.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    other_actor = _insert_actor(session)
    other_session = _insert_session(session, other_actor, config={"other": 1})
    other_editing = _insert_demo_row(
        session,
        DemoEditingSession,
        demo_actor_id=other_actor.id,
        demo_session_id=other_session.id,
        source_asset_id=graph["source_asset"].id,
        source_asset_sha256=graph["source_asset"].sha256,
        desired_delta_profile_digest=hashlib.sha256(b"other-desired").hexdigest(),
        style_profile_digest=hashlib.sha256(b"other-style").hexdigest(),
        identity_constraints_digest=hashlib.sha256(b"other-constraints").hexdigest(),
        context_digest=hashlib.sha256(b"other-context").hexdigest(),
        instruction_digest=hashlib.sha256(b"other-instruction").hexdigest(),
        tool_registry_version="fixture-tools-v1",
        closed_at=None,
        tombstoned_at=None,
    )
    with pytest.raises(DBAPIError, match="editing session close lifecycle authority is invalid"):
        _insert_preference_event(
            session,
            graph["actor"],
            sequence=3,
            previous_digest=graph["accepted_event"].content_digest,
            signal={"editing_session_id": other_editing.id},
            demo_session=graph["session"],
            event_type="EDITING_SESSION_CLOSED",
            source_type="SYSTEM_LIFECYCLE",
            occurred_at=closed_at,
            commit=False,
        )
    session.rollback()

    _insert_preference_event(
        session,
        graph["actor"],
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"editing_session_id": editing_session.id},
        demo_session=graph["session"],
        event_type="EDITING_SESSION_CLOSED",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=closed_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_editing_sessions SET closed_at=:value WHERE id=:editing_id"),
        {
            "value": datetime(2026, 8, 23, 8, 1, tzinfo=UTC),
            "editing_id": editing_session.id,
        },
    )
    with pytest.raises(DBAPIError, match=r"lacks matching lifecycle event|requires matching"):
        session.commit()
    session.rollback()

    close_event = _insert_preference_event(
        session,
        graph["actor"],
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"editing_session_id": editing_session.id},
        demo_session=graph["session"],
        event_type="EDITING_SESSION_CLOSED",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=closed_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_editing_sessions SET closed_at=:value WHERE id=:editing_id"),
        {"value": closed_at, "editing_id": editing_session.id},
    )
    session.commit()

    _insert_preference_event(
        session,
        graph["actor"],
        sequence=4,
        previous_digest=close_event.content_digest,
        signal={"authority_id": editing_session.id, "authority_type": "EDITING_SESSION"},
        demo_session=graph["session"],
        event_type="TOMBSTONE",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=tombstoned_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_editing_sessions SET tombstoned_at=:value WHERE id=:editing_id"),
        {"value": tombstoned_at, "editing_id": editing_session.id},
    )
    session.commit()


def test_preference_event_sequence_and_digest_chain(session: Session) -> None:
    actor = _insert_actor(session)
    first = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"style_context": "editorial"},
    )
    with pytest.raises(DBAPIError, match="sequence or digest chain is invalid"):
        _insert_preference_event(
            session,
            actor,
            sequence=3,
            previous_digest=first.content_digest,
            signal={"style_context": "minimal"},
        )
    session.rollback()
    second = _insert_preference_event(
        session,
        actor,
        sequence=2,
        previous_digest=first.content_digest,
        signal={"style_context": "minimal"},
    )
    assert second.event_sequence == 2
    assert (
        session.scalar(
            select(DemoPreferenceEvent.content_digest).where(DemoPreferenceEvent.id == second.id)
        )
        == second.content_digest
    )


def test_concurrent_preference_event_append_has_one_canonical_winner(session: Session) -> None:
    actor = _insert_actor(session)
    first = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"style_context": "first"},
    )
    database_url = os.environ["TEST_DATABASE_URL"]
    actor_id = actor.id
    first_digest = first.content_digest
    barrier = Barrier(2)

    def append(sequence_signal: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                worker_actor = worker_session.get(DemoActor, actor_id)
                assert worker_actor is not None
                barrier.wait(timeout=10)
                try:
                    _insert_preference_event(
                        worker_session,
                        worker_actor,
                        sequence=2,
                        previous_digest=first_digest,
                        signal={"style_context": sequence_signal},
                    )
                except (DBAPIError, IntegrityError):
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(append, ("left", "right")))
    assert results == ["conflict", "created"]
    session.expire_all()
    events = session.scalars(
        select(DemoPreferenceEvent)
        .where(DemoPreferenceEvent.demo_actor_id == actor.id)
        .order_by(DemoPreferenceEvent.event_sequence)
    ).all()
    assert [event.event_sequence for event in events] == [1, 2]
    assert events[1].previous_event_digest == first.content_digest


def test_job_binding_uses_namespaced_formal_job_and_typed_owner(session: Session) -> None:
    actor = _insert_actor(session)
    endpoint_operation = "profile.compile"
    client_key_hash = "2" * 64
    formal_hash = hashlib.sha256(
        (
            f"mirror.demo/JobIdempotency/v1\n{actor.id}\n{endpoint_operation}\n{client_key_hash}"
        ).encode()
    ).hexdigest()
    job = Job(
        id=new_id(),
        job_type=f"demo_p3_p7.{endpoint_operation}",
        status="PENDING",
        idempotency_key_hash=formal_hash,
        request_id="demo-d01b-job-binding",
        payload={},
        owner_user_id=None,
        ingestion_upload_intent_id=None,
        attempt_count=0,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(job)
    session.commit()

    schema_version = "mirror.demo/DemoJobBinding/v1"
    request_digest = "3" * 64
    payload = {
        "demo_actor_id": actor.id,
        "demo_session_id": None,
        "endpoint_operation": endpoint_operation,
        "idempotency_key_hash": client_key_hash,
        "job_id": job.id,
        "request_digest": request_digest,
        "target_id": actor.id,
        "target_type": "DEMO_ACTOR",
    }
    binding = DemoJobBinding(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=utcnow(),
        demo_actor_id=actor.id,
        demo_session_id=None,
        job_id=job.id,
        endpoint_operation=endpoint_operation,
        idempotency_key_hash=client_key_hash,
        request_digest=request_digest,
        target_type="DEMO_ACTOR",
        target_id=actor.id,
    )
    session.add(binding)
    session.commit()
    assert binding.job_id == job.id

    with pytest.raises((IntegrityError, DBAPIError)):
        session.execute(
            update(DemoJobBinding)
            .where(DemoJobBinding.id == binding.id)
            .values(request_digest="4" * 64)
        )
    session.rollback()


def test_concurrent_job_binding_idempotency_has_one_canonical_winner(session: Session) -> None:
    actor = _insert_actor(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    actor_id = actor.id
    endpoint_operation = "profile.compile"
    client_key_hash = "b" * 64
    formal_hash = hashlib.sha256(
        (
            f"mirror.demo/JobIdempotency/v1\n{actor_id}\n{endpoint_operation}\n{client_key_hash}"
        ).encode()
    ).hexdigest()
    barrier = Barrier(2)

    def create_binding(request_suffix: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                job = Job(
                    id=new_id(),
                    job_type=f"demo_p3_p7.{endpoint_operation}",
                    status="PENDING",
                    idempotency_key_hash=formal_hash,
                    request_id=f"demo-d01b-concurrent-{request_suffix}",
                    payload={},
                    owner_user_id=None,
                )
                worker_session.add(job)
                barrier.wait(timeout=10)
                try:
                    worker_session.flush()
                    worker_actor = worker_session.get(DemoActor, actor_id)
                    assert worker_actor is not None
                    _insert_demo_row(
                        worker_session,
                        DemoJobBinding,
                        demo_actor_id=actor_id,
                        demo_session_id=None,
                        job_id=job.id,
                        endpoint_operation=endpoint_operation,
                        idempotency_key_hash=client_key_hash,
                        request_digest=hashlib.sha256(request_suffix.encode()).hexdigest(),
                        target_type="DEMO_ACTOR",
                        target_id=actor_id,
                    )
                except (DBAPIError, IntegrityError):
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(create_binding, ("left", "right")))
    assert results == ["conflict", "created"]
    session.expire_all()
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM demo_job_bindings "
                "WHERE demo_actor_id=:actor_id AND endpoint_operation=:operation "
                "AND idempotency_key_hash=:key_hash"
            ),
            {"actor_id": actor.id, "operation": endpoint_operation, "key_hash": client_key_hash},
        )
        == 1
    )


def test_empty_downgrade_and_reupgrade_lifecycle(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.downgrade(config, FORMAL_DOWN_REVISION)
    try:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            FORMAL_DOWN_REVISION
        )
        assert (
            session.scalar(text("SELECT count(*) FROM pg_tables WHERE tablename LIKE 'demo_%'"))
            == 0
        )
    finally:
        command.upgrade(config, DEMO_REVISION)
    assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION


def test_populated_downgrade_fails_closed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = _insert_actor(session)
    actor_id = actor.id
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    session.close()

    with pytest.raises(DBAPIError, match="downgrade blocked by populated table"):
        command.downgrade(config, FORMAL_DOWN_REVISION)

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION
        assert (
            connection.scalar(
                text("SELECT count(*) FROM demo_actors WHERE id=:actor_id"),
                {"actor_id": actor_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_authority_%'"
                )
            )
            == 27
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_terminal_binding_%'"
                )
            )
            == 4
        )
    engine.dispose()


@pytest.mark.parametrize(
    "populated_authority",
    ("job", "job_attempt", "asset_variant"),
)
def test_populated_formal_demo_authority_blocks_downgrade(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    populated_authority: str,
) -> None:
    """Each formal authority class independently prevents destructive rollback."""
    job = Job(
        id=new_id(),
        job_type="demo_p3_p7.profile.compile",
        status="PENDING",
        idempotency_key_hash=hashlib.sha256(new_id().encode()).hexdigest(),
        request_id=f"demo-d01b-downgrade-{populated_authority}",
        payload={},
        owner_user_id=None,
    )
    if populated_authority in {"job", "job_attempt"}:
        session.add(job)
        session.commit()
    if populated_authority == "job_attempt":
        session.add(
            JobAttempt(
                id=new_id(),
                job_id=job.id,
                attempt=1,
                status="PENDING",
                started_at=utcnow(),
            )
        )
        session.commit()
    if populated_authority == "asset_variant":
        source_asset = Asset(
            id=new_id(),
            owner_user_id=None,
            asset_role="synthetic",
            storage_key=f"internal-synthetic/v1/demo-d01b/{new_id()}",
            mime_type="image/png",
            byte_size=1,
            width=1,
            height=1,
            sha256=hashlib.sha256(new_id().encode()).hexdigest(),
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=False,
            internal_purpose="synthetic_dataset",
        )
        result_asset = Asset(
            id=new_id(),
            owner_user_id=None,
            asset_role="synthetic",
            storage_key=f"internal-synthetic/v1/demo-d01b/{new_id()}",
            mime_type="image/png",
            byte_size=1,
            width=1,
            height=1,
            sha256=hashlib.sha256(new_id().encode()).hexdigest(),
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=True,
            internal_purpose="synthetic_dataset",
        )
        session.add_all((source_asset, result_asset))
        session.commit()
        session.add(
            AssetVariant(
                id=new_id(),
                source_asset_id=source_asset.id,
                result_asset_id=result_asset.id,
                variant_type="demo_p3_p7_fixture",
            )
        )
        session.commit()

    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    session.close()

    expected_message = {
        "job": "Demo Job authority",
        "job_attempt": "Demo JobAttempt authority",
        "asset_variant": "Demo AssetVariant authority",
    }[populated_authority]
    with pytest.raises(DBAPIError, match=expected_message):
        command.downgrade(config, FORMAL_DOWN_REVISION)

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_authority_%'"
                )
            )
            == 27
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_terminal_binding_%'"
                )
            )
            == 4
        )
    engine.dispose()
