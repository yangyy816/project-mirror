from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _commit_execution_pair,
    _insert_demo_row,
    _insert_full_demo_graph,
    _insert_job_binding,
    _prepare_followup_execution,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)

from mirror_api.demo_models import (
    DemoDesiredDeltaProfile,
    DemoReferenceProfile,
    DemoSelfTransferDimensionEvidence,
    DemoSelfTransferRun,
)
from mirror_api.demo_profile_service import (
    DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST,
    DEMO_SELF_TRANSFER_PROJECTION_VERSION,
)
from mirror_api.demo_self_transfer_service import (
    CompileDemoReferenceProfile,
    CreateDemoSelfTransferRequest,
    DemoReferenceSource,
    DemoSelfTransferAuthorityCorruption,
    DemoSelfTransferConflict,
    DemoSelfTransferService,
    FinalizeDemoSelfTransferResult,
)
from mirror_api.models import Job, JobAttempt

pytestmark = pytest.mark.integration


@pytest.fixture
def postgres_session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as db_session:
        _truncate_demo_authority(db_session)
        _truncate_formal_synthetic_fixture_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_authority(db_session)
        _truncate_formal_synthetic_fixture_authority(db_session)
    engine.dispose()


def _service() -> tuple[DemoSelfTransferService, AsyncEngine]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return DemoSelfTransferService(session_factory=sessions), engine


def _create_command(
    graph: dict[str, Any], *, key: str = "d06-create-key-0001"
) -> CreateDemoSelfTransferRequest:
    return CreateDemoSelfTransferRequest(
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=graph["desired_delta"].id,
        source_asset_id=graph["source_asset"].id,
        dimension_key="jaw_width",
        idempotency_key=key,
        request_id=f"d06-{key}",
    )


def _verifier_metrics(
    *, dimension: str = "jaw_width", requested: int = 10_000, measured: int = 9_500
) -> dict[str, Any]:
    categories = [
        {
            "category": "STRUCTURAL_IDENTITY_CONSTRAINTS",
            "evidence": {"drifts_ppm": {"jaw_width": 0}, "thresholds_ppm": {"jaw_width": 1}},
            "reason_codes": ["VERIFIED"],
            "status": "PASS",
        },
        {
            "category": "LOCK_PRESERVATION",
            "evidence": {"drifts_ppm": {}, "thresholds_ppm": {}},
            "reason_codes": ["VERIFIED"],
            "status": "PASS",
        },
        {
            "category": "TARGET_DELTA",
            "evidence": {
                "measured_delta_ppm": measured,
                "operation_digest": "a" * 64,
                "requested_delta_ppm": requested,
                "target_dimension_key": dimension,
                "tolerance_ppm": 1_000,
            },
            "reason_codes": ["VERIFIED"],
            "status": "PASS",
        },
        {
            "category": "NON_TARGET_DRIFT",
            "evidence": {"drift_ppm": 100, "threshold_ppm": 1_000},
            "reason_codes": ["VERIFIED"],
            "status": "PASS",
        },
        {
            "category": "ARTIFACT",
            "evidence": {"artifact_codes": [], "artifact_status": "PASS"},
            "reason_codes": ["VERIFIED"],
            "status": "PASS",
        },
        {
            "category": "ORIGINAL_IMMUTABILITY",
            "evidence": {"immutable": True},
            "reason_codes": ["VERIFIED"],
            "status": "PASS",
        },
        {
            "category": "DECODE_VALIDITY",
            "evidence": {"decode_valid": True},
            "reason_codes": ["VERIFIED"],
            "status": "PASS",
        },
    ]
    return {
        "categories": categories,
        "identity_claim_scope": "STRUCTURAL_ONLY_NOT_BIOMETRIC_IDENTITY_VERIFICATION",
        "publishable": True,
        "request_digest": "b" * 64,
        "result_digest": "c" * 64,
    }


def _published_result(
    postgres_session: Session,
    graph: dict[str, Any],
    *,
    dimension: str = "jaw_width",
    requested: int = 10_000,
    measured: int = 9_500,
) -> dict[str, Any]:
    execution = _prepare_followup_execution(
        postgres_session,
        graph,
        verification_overrides={
            "metrics": _verifier_metrics(
                dimension=dimension, requested=requested, measured=measured
            )
        },
    )
    _commit_execution_pair(postgres_session, execution)
    return execution


@pytest.mark.asyncio
async def test_create_reserve_finalize_and_reference_profile_replay(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    published = _published_result(postgres_session, graph)
    service, engine = _service()
    try:
        created = await service.create_request(_create_command(graph))
        replay = await service.create_request(_create_command(graph))
        assert replay.request_run_id == created.request_run_id
        assert replay.job_id == created.job_id
        assert replay.replayed is True

        reservation = await service.reserve(
            demo_actor_id=graph["actor"].id, request_run_id=created.request_run_id
        )
        reservation_replay = await service.reserve(
            demo_actor_id=graph["actor"].id, request_run_id=created.request_run_id
        )
        assert reservation.attempt == 1
        assert reservation_replay.formal_job_attempt_id == reservation.formal_job_attempt_id
        assert reservation_replay.replayed is True

        final_command = FinalizeDemoSelfTransferResult(
            demo_actor_id=graph["actor"].id,
            request_run_id=created.request_run_id,
            result_image_version_id=published["image"].id,
            user_outcome="ACCEPTED",
        )
        result = await service.finalize(final_command)
        result_replay = await service.finalize(final_command)
        assert result.measured_delta_ppm == 9_500
        assert result.confidence_ppm == 999_500
        assert result.evidence_id is not None
        assert result_replay.result_run_id == result.result_run_id
        assert result_replay.replayed is True

        reference_command = CompileDemoReferenceProfile(
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            desired_delta_profile_id=graph["desired_delta"].id,
            style_profile_id=graph["style"].id,
            identity_constraints_id=graph["constraints"].id,
            sources=(DemoReferenceSource(published["output_asset"].id, "FRONT"),),
        )
        reference = await service.compile_reference_profile(reference_command)
        reference_replay = await service.compile_reference_profile(reference_command)
        assert reference.version == 2  # the full-graph fixture already owns version 1
        assert reference_replay.reference_profile_id == reference.reference_profile_id
        assert reference_replay.content_digest == reference.content_digest
        assert reference_replay.replayed is True

        postgres_session.expire_all()
        job = postgres_session.get(Job, created.job_id)
        attempt = postgres_session.get(JobAttempt, reservation.formal_job_attempt_id)
        evidence = postgres_session.get(DemoSelfTransferDimensionEvidence, result.evidence_id)
        profile = postgres_session.get(DemoReferenceProfile, reference.reference_profile_id)
        assert job is not None and job.status == "COMPLETED"
        assert attempt is not None and attempt.status == "COMPLETED"
        assert evidence is not None
        assert evidence.projection_version == DEMO_SELF_TRANSFER_PROJECTION_VERSION
        assert evidence.projection_config_digest == DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST
        assert profile is not None
        assert profile.structured_profile["identity_reference_frame"] == "SELF_STATE_ANCHORED"
        assert profile.structured_profile["dimensions"]["jaw_width"]["desired_delta_ppm"] == 9_500
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_is_concurrent_and_payload_collision_safe(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    service, engine = _service()
    command = _create_command(graph, key="d06-concurrent-create")
    try:
        first, second = await asyncio.gather(
            service.create_request(command), service.create_request(command)
        )
        assert first.request_run_id == second.request_run_id
        assert first.job_id == second.job_id
        assert sorted((first.replayed, second.replayed)) == [False, True]

        collision = CreateDemoSelfTransferRequest(
            demo_actor_id=command.demo_actor_id,
            demo_session_id=command.demo_session_id,
            desired_delta_profile_id=command.desired_delta_profile_id,
            source_asset_id=command.source_asset_id,
            dimension_key="chin_height",
            idempotency_key=command.idempotency_key,
            request_id=command.request_id,
        )
        with pytest.raises(
            DemoSelfTransferConflict,
            match="idempotency key is bound to another request",
        ):
            await service.create_request(collision)

        duplicate = _create_command(graph, key="d06-duplicate-authority")
        with pytest.raises(
            DemoSelfTransferConflict,
            match="identical immutable self-transfer request already exists",
        ):
            await service.create_request(duplicate)

        postgres_session.expire_all()
        count = postgres_session.scalar(
            select(func.count())
            .select_from(DemoSelfTransferRun)
            .where(
                DemoSelfTransferRun.demo_actor_id == graph["actor"].id,
                DemoSelfTransferRun.record_kind == "REQUEST",
                DemoSelfTransferRun.id.in_((first.request_run_id, second.request_run_id)),
            )
        )
        assert count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_verifier_projection_rolls_back_without_partial_result(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    published = _published_result(postgres_session, graph, dimension="chin_height")
    service, engine = _service()
    try:
        created = await service.create_request(_create_command(graph, key="d06-invalid-metrics"))
        reservation = await service.reserve(
            demo_actor_id=graph["actor"].id, request_run_id=created.request_run_id
        )
        with pytest.raises(
            DemoSelfTransferAuthorityCorruption,
            match="verifier integer projection differs from the requested profile",
        ):
            await service.finalize(
                FinalizeDemoSelfTransferResult(
                    demo_actor_id=graph["actor"].id,
                    request_run_id=created.request_run_id,
                    result_image_version_id=published["image"].id,
                    user_outcome="ACCEPTED",
                )
            )

        postgres_session.expire_all()
        job = postgres_session.get(Job, created.job_id)
        attempt = postgres_session.get(JobAttempt, reservation.formal_job_attempt_id)
        results = postgres_session.scalar(
            select(func.count())
            .select_from(DemoSelfTransferRun)
            .where(
                DemoSelfTransferRun.request_run_id == created.request_run_id,
                DemoSelfTransferRun.record_kind == "RESULT",
            )
        )
        assert results == 0
        assert job is not None and job.status == "RUNNING"
        assert attempt is not None and attempt.status == "RUNNING"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rejected_self_transfer_cannot_become_reference_profile(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    published = _published_result(postgres_session, graph)
    service, engine = _service()
    try:
        created = await service.create_request(_create_command(graph, key="d06-rejected-result"))
        await service.reserve(
            demo_actor_id=graph["actor"].id, request_run_id=created.request_run_id
        )
        await service.finalize(
            FinalizeDemoSelfTransferResult(
                demo_actor_id=graph["actor"].id,
                request_run_id=created.request_run_id,
                result_image_version_id=published["image"].id,
                user_outcome="REJECTED",
            )
        )
        postgres_session.expire_all()
        rejected_evidence_count = postgres_session.scalar(
            select(func.count())
            .select_from(DemoSelfTransferDimensionEvidence)
            .join(
                DemoSelfTransferRun,
                DemoSelfTransferRun.id == DemoSelfTransferDimensionEvidence.self_transfer_run_id,
            )
            .where(DemoSelfTransferRun.request_run_id == created.request_run_id)
        )
        assert rejected_evidence_count == 0
        with pytest.raises(
            DemoSelfTransferConflict,
            match="exactly one accepted self-transfer authority",
        ):
            await service.compile_reference_profile(
                CompileDemoReferenceProfile(
                    demo_actor_id=graph["actor"].id,
                    demo_session_id=graph["session"].id,
                    desired_delta_profile_id=graph["desired_delta"].id,
                    style_profile_id=graph["style"].id,
                    identity_constraints_id=graph["constraints"].id,
                    sources=(DemoReferenceSource(published["output_asset"].id, "FRONT"),),
                )
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_accepted_dimension_is_rejected_without_partial_authority(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    published = _published_result(postgres_session, graph)
    service, engine = _service()
    try:
        first = await service.create_request(_create_command(graph, key="d06-first-accepted"))
        await service.reserve(demo_actor_id=graph["actor"].id, request_run_id=first.request_run_id)
        await service.finalize(
            FinalizeDemoSelfTransferResult(
                demo_actor_id=graph["actor"].id,
                request_run_id=first.request_run_id,
                result_image_version_id=published["image"].id,
                user_outcome="ACCEPTED",
            )
        )

        _, profile_binding = _insert_job_binding(
            postgres_session,
            graph["actor"],
            endpoint_operation="profile.compile",
            target_type="DEMO_ACTOR",
            target_id=graph["actor"].id,
            demo_session=graph["session"],
        )
        second_profile = _insert_demo_row(
            postgres_session,
            DemoDesiredDeltaProfile,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            self_state_id=graph["self_state"].id,
            demo_job_binding_id=profile_binding.id,
            version=2,
            as_of_event_sequence=graph["desired_delta"].as_of_event_sequence,
            compilation_watermark=graph["desired_delta"].compilation_watermark,
            compiler_version="d06-second-profile-v1",
            dimensions={"jaw_width_ppm": 10_000},
            evidence_digests=list(graph["desired_delta"].evidence_digests),
            restraint=dict(graph["desired_delta"].restraint),
        )
        second = await service.create_request(
            CreateDemoSelfTransferRequest(
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                desired_delta_profile_id=second_profile.id,
                source_asset_id=graph["source_asset"].id,
                dimension_key="jaw_width",
                idempotency_key="d06-second-accepted",
                request_id="d06-second-accepted",
            )
        )
        reservation = await service.reserve(
            demo_actor_id=graph["actor"].id, request_run_id=second.request_run_id
        )
        with pytest.raises(
            DemoSelfTransferConflict,
            match="already owns this SelfState dimension",
        ):
            await service.finalize(
                FinalizeDemoSelfTransferResult(
                    demo_actor_id=graph["actor"].id,
                    request_run_id=second.request_run_id,
                    result_image_version_id=published["image"].id,
                    user_outcome="ACCEPTED",
                )
            )

        postgres_session.expire_all()
        job = postgres_session.get(Job, second.job_id)
        attempt = postgres_session.get(JobAttempt, reservation.formal_job_attempt_id)
        second_result_count = postgres_session.scalar(
            select(func.count())
            .select_from(DemoSelfTransferRun)
            .where(
                DemoSelfTransferRun.request_run_id == second.request_run_id,
                DemoSelfTransferRun.record_kind == "RESULT",
            )
        )
        assert second_result_count == 0
        assert job is not None and job.status == "RUNNING"
        assert attempt is not None and attempt.status == "RUNNING"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_finalization_replay_rejects_changed_user_outcome(
    postgres_session: Session,
) -> None:
    graph = _insert_full_demo_graph(postgres_session)
    published = _published_result(postgres_session, graph)
    service, engine = _service()
    try:
        created = await service.create_request(_create_command(graph, key="d06-result-collision"))
        await service.reserve(
            demo_actor_id=graph["actor"].id, request_run_id=created.request_run_id
        )
        await service.finalize(
            FinalizeDemoSelfTransferResult(
                demo_actor_id=graph["actor"].id,
                request_run_id=created.request_run_id,
                result_image_version_id=published["image"].id,
                user_outcome="ACCEPTED",
            )
        )
        with pytest.raises(DemoSelfTransferConflict, match="immutable winner"):
            await service.finalize(
                FinalizeDemoSelfTransferResult(
                    demo_actor_id=graph["actor"].id,
                    request_run_id=created.request_run_id,
                    result_image_version_id=published["image"].id,
                    user_outcome="ADJUSTED",
                )
            )
    finally:
        await engine.dispose()
