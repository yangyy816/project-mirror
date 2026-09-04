from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_d08_geometry_runtime_postgres import (
    _artifact,
    _authority,
    _context,
    _materialized,
    _plan,
    _verification,
)
from test_demo_schema_authority_invariants import (
    _insert_demo_row,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)

from mirror_api.demo_editing_commands import DemoEditingCommandService, ExecuteDemoEditPlan
from mirror_api.demo_editing_repository import SqlAlchemyDemoEditingRepository
from mirror_api.demo_image_feedback_service import DemoImageFeedbackService
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_models import (
    DemoAcceptedVisualEpisode,
    DemoD02R2Epoch2Admission,
    DemoDesiredDeltaProfile,
    DemoEditPlan,
    DemoIdentityConstraints,
    DemoSelfTransferDimensionEvidence,
    DemoSelfTransferRun,
    DemoVerificationResult,
)
from mirror_api.demo_profile_geometry_selector import (
    DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
    DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
    DemoProfileGeometrySelection,
)
from mirror_api.demo_reference_profile_coordinator import DemoReferenceProfileCoordinator
from mirror_api.demo_reference_profile_service import DemoReferenceProfileService
from mirror_api.demo_self_transfer_acceptance import (
    AcceptDemoSteppedSelfTransfer,
    DemoSteppedSelfTransferAcceptanceCoordinator,
)
from mirror_api.demo_self_transfer_service import (
    CreateDemoSteppedSelfTransferRequest,
    DemoSelfTransferAuthorityCorruption,
    DemoSelfTransferConflict,
    DemoSelfTransferInputError,
    DemoSelfTransferService,
    DemoSelfTransferUnavailable,
    FinalizeDemoSelfTransferResult,
)
from mirror_api.models import Job

pytestmark = pytest.mark.integration


class _RecordingDispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[object] = []

    def dispatch_demo_reference_profile(self, message: object) -> None:
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("fixture dispatch loss")


@pytest.fixture
def postgres_session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
        yield session
        session.rollback()
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
    engine.dispose()


def _service() -> tuple[DemoSelfTransferService, AsyncEngine, async_sessionmaker[Any]]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return DemoSelfTransferService(session_factory=sessions), engine, sessions


def _step_selection(authority: Any) -> DemoProfileGeometrySelection:
    return DemoProfileGeometrySelection(
        dimension_key="jaw_width",
        profile_desired_delta_ppm=15_000,
        execution_delta_ppm=15_000,
        selection_policy_version=DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
        selection_policy_digest=DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
        selected_case_digest=authority.fixed_case.case_record_digest,
    )


async def _stepped_execution(
    postgres_session: Session,
    tmp_path: Any,
    *,
    desired_dimensions: dict[str, Any] | None = None,
) -> tuple[async_sessionmaker[Any], AsyncEngine, dict[str, Any], Any, Any, Any]:
    sessions, engine, graph = await _context(
        postgres_session,
        tmp_path,
        desired_dimensions=desired_dimensions
        or {
            "jaw_width": {
                "dimension_key": "jaw_width",
                "desired_delta_ppm": 15_000,
                "confidence_ppm": 400_000,
                "evidence_kind": "QUESTIONNAIRE",
                "restraint": "NONE",
                "evidence_digest": "a" * 64,
                "self_state_anchor_ppm": 0,
            }
        },
    )
    async with sessions() as session:
        desired = await session.scalar(
            select(DemoDesiredDeltaProfile).where(
                DemoDesiredDeltaProfile.demo_actor_id == graph["actor"].id,
                DemoDesiredDeltaProfile.demo_session_id == graph["session"].id,
            )
        )
    assert desired is not None
    graph["desired"] = desired
    commands = DemoEditingCommandService(session_factory=sessions)
    repository = SqlAlchemyDemoEditingRepository(session_factory=sessions)
    plan = await _plan(commands, graph, "d06-profile-guided-step")
    async with sessions() as session:
        stored = await session.get(DemoEditPlan, plan.target_id)
        assert stored is not None
        execution = await commands.execute_edit_plan(
            ExecuteDemoEditPlan(
                graph["actor"].id,
                stored.id,
                "GEOMETRY",
                stored.content_digest,
                "d06-profile-guided-step-execution",
                "d06-profile-guided-step-request",
            )
        )
    authority, attempt, operation = await _authority(
        sessions, graph, plan.target_id, execution.job_id
    )
    materialized = _materialized(authority, attempt, b"d06-profile-guided-output")
    row, artifact = _artifact(
        graph,
        binding_id=attempt.execution_job_binding_id,
        operation=operation,
        attempt_id=attempt.attempt_id,
        materialized=materialized,
    )
    async with sessions() as session:
        session.add(row)
        await session.commit()
    published = await repository.promote_pass(
        await repository.append_materialized(artifact, materialized),
        _verification(authority, materialized),
        materialized,
        f"demo-published/v1/{artifact.artifact_id}/{materialized.sha256}",
    )
    return sessions, engine, graph, authority, execution, published


def _desired_dimension(
    delta: int,
    confidence: int = 400_000,
    restraint: str = "NONE",
) -> dict[str, Any]:
    return {
        "dimension_key": "jaw_width",
        "desired_delta_ppm": delta,
        "confidence_ppm": confidence,
        "evidence_kind": "QUESTIONNAIRE",
        "restraint": restraint,
        "evidence_digest": "a" * 64,
        "self_state_anchor_ppm": 0,
    }


def _append_persistent_constraints(
    postgres_session: Session,
    graph: dict[str, Any],
    *,
    locks: dict[str, Any],
    prohibited_operations: list[str],
) -> None:
    current = postgres_session.scalar(
        select(DemoIdentityConstraints)
        .where(
            DemoIdentityConstraints.demo_actor_id == graph["actor"].id,
            DemoIdentityConstraints.constraint_scope == "PERSISTENT",
        )
        .order_by(DemoIdentityConstraints.version.desc())
        .limit(1)
    )
    assert current is not None
    _insert_demo_row(
        postgres_session,
        DemoIdentityConstraints,
        demo_actor_id=current.demo_actor_id,
        demo_session_id=None,
        self_state_id=current.self_state_id,
        version=current.version + 1,
        constraint_scope="PERSISTENT",
        source_event_digests=list(current.source_event_digests),
        locks=locks,
        bounds=dict(current.bounds),
        prohibited_operations=prohibited_operations,
    )


def _command(
    graph: dict[str, Any], authority: Any, execution: Any, published: Any, *, key: str
) -> CreateDemoSteppedSelfTransferRequest:
    return CreateDemoSteppedSelfTransferRequest(
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=graph["desired"].id,
        source_asset_id=graph["source"].id,
        execution_job_id=execution.job_id,
        result_image_version_id=published.image_version_id,
        selection=_step_selection(authority),
        idempotency_key=key,
        request_id=f"request-{key}",
    )


@pytest.mark.asyncio
async def test_v2_create_replay_collision_and_exact_finalize(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        command = _command(graph, authority, execution, published, key="d06-v2-create-race")
        with pytest.raises(DemoSelfTransferConflict, match="authoritative selector"):
            await service.create_stepped_request(
                replace(
                    command,
                    idempotency_key="d06-v2-override-step",
                    selection=replace(
                        command.selection,
                        profile_desired_delta_ppm=30_000,
                        execution_delta_ppm=30_000,
                    ),
                )
            )
        first, second = await asyncio.gather(
            service.create_stepped_request(command), service.create_stepped_request(command)
        )
        assert first.request_run_id == second.request_run_id
        assert sorted((first.replayed, second.replayed)) == [False, True]
        with pytest.raises(DemoSelfTransferConflict, match="idempotency key"):
            await service.create_stepped_request(
                replace(command, result_image_version_id=graph["image"].id)
            )
        await service.reserve(demo_actor_id=graph["actor"].id, request_run_id=first.request_run_id)
        result = await service.finalize(
            FinalizeDemoSelfTransferResult(
                demo_actor_id=graph["actor"].id,
                request_run_id=first.request_run_id,
                result_image_version_id=published.image_version_id,
                user_outcome="REJECTED",
            )
        )
        replay = await service.finalize(
            FinalizeDemoSelfTransferResult(
                demo_actor_id=graph["actor"].id,
                request_run_id=first.request_run_id,
                result_image_version_id=published.image_version_id,
                user_outcome="REJECTED",
            )
        )
        assert result.measured_delta_ppm == 15_000
        assert replay.replayed is True
        postgres_session.expire_all()
        stored = postgres_session.get(DemoSelfTransferRun, result.result_run_id)
        assert stored is not None and stored.schema_version.endswith("/v2")
        assert stored.requested_delta["execution_delta_ppm"] == 15_000
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_v2_rejects_non_nearest_step_from_persisted_profile(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session,
        tmp_path,
        desired_dimensions={"jaw_width": _desired_dimension(30_000)},
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        with pytest.raises(DemoSelfTransferConflict, match="authoritative selector"):
            await service.create_stepped_request(
                _command(graph, authority, execution, published, key="d06-v2-nonnearest")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_v2_rejects_lower_ranked_dimension_from_persisted_profile(
    postgres_session: Session, tmp_path: Any
) -> None:
    dimensions = {
        "jaw_width": _desired_dimension(15_000),
        "chin_height": {
            **_desired_dimension(30_000),
            "dimension_key": "chin_height",
        },
    }
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path, desired_dimensions=dimensions
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        with pytest.raises(DemoSelfTransferConflict, match="authoritative selector"):
            await service.create_stepped_request(
                _command(graph, authority, execution, published, key="test-d06-key-00000000")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_v2_rejects_confidence_zero_selected_dimension(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session,
        tmp_path,
        desired_dimensions={"jaw_width": _desired_dimension(15_000, confidence=0)},
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        with pytest.raises(DemoSelfTransferAuthorityCorruption, match="no eligible"):
            await service.create_stepped_request(
                _command(graph, authority, execution, published, key="d06-v2-zero-confidence")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_v2_rejects_restrained_selected_dimension(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session,
        tmp_path,
        desired_dimensions={
            "jaw_width": _desired_dimension(15_000, restraint="INSUFFICIENT_CONFIDENCE")
        },
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        with pytest.raises(DemoSelfTransferAuthorityCorruption, match="no eligible"):
            await service.create_stepped_request(
                _command(graph, authority, execution, published, key="d06-v2-restrained")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_v2_rejects_persistent_preserve_without_session_override(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    _append_persistent_constraints(
        postgres_session,
        graph,
        locks={"jaw_width": {"mode": "PRESERVE"}},
        prohibited_operations=[],
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        with pytest.raises(DemoSelfTransferAuthorityCorruption, match="no eligible"):
            await service.create_stepped_request(
                _command(graph, authority, execution, published, key="d06-v2-preserve")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_v2_rejects_geometry_prohibited_by_latest_constraints(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    _append_persistent_constraints(
        postgres_session,
        graph,
        locks={},
        prohibited_operations=["GEOMETRY"],
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        with pytest.raises(DemoSelfTransferAuthorityCorruption, match="no eligible"):
            await service.create_stepped_request(
                _command(graph, authority, execution, published, key="d06-v2-geometry-prohibited")
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stable_core_case_substitution_is_blocked_by_immutable_verifier_authority(
    postgres_session: Session, tmp_path: Any
) -> None:
    _, engine, _, _, _, published = await _stepped_execution(postgres_session, tmp_path)
    try:
        with pytest.raises(DBAPIError, match="immutable"):
            postgres_session.execute(
                text(
                    "UPDATE demo_verification_results "
                    "SET metrics = jsonb_set("
                    "metrics, '{geometry_execution,stable_core,case_record_digest}', "
                    "to_jsonb(CAST(:digest AS text))"
                    ") WHERE id = :id"
                ),
                {"digest": "f" * 64, "id": published.verification_result_id},
            )
            postgres_session.commit()
        postgres_session.rollback()
        verifier = postgres_session.get(DemoVerificationResult, published.verification_result_id)
        assert verifier is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_d02_admission_report_substitution_is_blocked_by_immutable_authority(
    postgres_session: Session, tmp_path: Any
) -> None:
    _, engine, _, _, _, _ = await _stepped_execution(postgres_session, tmp_path)
    try:
        admission = postgres_session.scalar(select(DemoD02R2Epoch2Admission).limit(1))
        assert admission is not None
        with pytest.raises(DBAPIError, match="append-only"):
            postgres_session.execute(
                text(
                    "UPDATE demo_d02_r2_epoch2_admissions "
                    "SET screening_report_digest = :digest WHERE id = :id"
                ),
                {"digest": "f" * 64, "id": admission.id},
            )
            postgres_session.commit()
        postgres_session.rollback()
        reloaded = postgres_session.get(DemoD02R2Epoch2Admission, admission.id)
        assert reloaded is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_no_autoflush_replay_rejects_corrupted_stable_core_projection(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        created = await service.create_stepped_request(
            _command(graph, authority, execution, published, key="d06-v2-core-projection")
        )
        async with sessions() as session:
            request = await session.get(DemoSelfTransferRun, created.request_run_id)
            profile = await session.get(DemoDesiredDeltaProfile, graph["desired"].id)
            verifier = await session.get(DemoVerificationResult, published.verification_result_id)
            assert request is not None and profile is not None and verifier is not None
            metrics = dict(verifier.metrics)
            execution_metrics = dict(metrics["geometry_execution"])
            core = dict(execution_metrics["stable_core"])
            core["case_record_digest"] = "f" * 64
            execution_metrics["stable_core"] = core
            metrics["geometry_execution"] = execution_metrics
            verifier.metrics = metrics
            with session.no_autoflush:
                with pytest.raises(DemoSelfTransferAuthorityCorruption, match="stable core"):
                    await service._require_stepped_execution(
                        session, request=request, profile=profile
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_no_autoflush_replay_rejects_corrupted_geometry_authority_projection(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        created = await service.create_stepped_request(
            _command(graph, authority, execution, published, key="d06-v2-authority-projection")
        )
        async with sessions() as session:
            request = await session.get(DemoSelfTransferRun, created.request_run_id)
            profile = await session.get(DemoDesiredDeltaProfile, graph["desired"].id)
            verifier = await session.get(DemoVerificationResult, published.verification_result_id)
            assert request is not None and profile is not None and verifier is not None
            metrics = dict(verifier.metrics)
            geometry = dict(metrics["geometry_verification"])
            geometry["authority_digest"] = "f" * 64
            metrics["geometry_verification"] = geometry
            verifier.metrics = metrics
            with session.no_autoflush:
                with pytest.raises(DemoSelfTransferAuthorityCorruption, match="stable core"):
                    await service._require_stepped_execution(
                        session, request=request, profile=profile
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_no_autoflush_replay_rejects_corrupted_admission_report_projection(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    service = DemoSelfTransferService(session_factory=sessions)
    try:
        created = await service.create_stepped_request(
            _command(graph, authority, execution, published, key="d06-v2-admission-projection")
        )
        async with sessions() as session:
            request = await session.get(DemoSelfTransferRun, created.request_run_id)
            admission = await session.scalar(select(DemoD02R2Epoch2Admission).limit(1))
            assert request is not None and admission is not None
            admission.screening_report_digest = "f" * 64
            with session.no_autoflush:
                with pytest.raises(
                    (DemoSelfTransferAuthorityCorruption, DemoSelfTransferUnavailable)
                ):
                    await service._stepped_d02_report(session, request=request)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_final_save_and_accepted_v2_are_atomic_then_queue_is_durable(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    transfer = DemoSelfTransferService(session_factory=sessions)
    dispatcher = _RecordingDispatcher(fail=True)
    reference = DemoReferenceProfileService(session_factory=sessions)
    reference_coordinator = DemoReferenceProfileCoordinator(
        service=reference,
        jobs=DemoJobService(session_factory=sessions),
        dispatcher=dispatcher,  # type: ignore[arg-type]
    )
    coordinator = DemoSteppedSelfTransferAcceptanceCoordinator(
        session_factory=sessions,
        feedback=DemoImageFeedbackService(session_factory=sessions),
        transfer=transfer,
        reference_service=reference,
        reference_coordinator=reference_coordinator,
    )
    try:
        created = await transfer.create_stepped_request(
            _command(graph, authority, execution, published, key="d06-v2-atomic")
        )
        await transfer.reserve(
            demo_actor_id=graph["actor"].id, request_run_id=created.request_run_id
        )
        acceptance_command = AcceptDemoSteppedSelfTransfer(
            demo_actor_id=graph["actor"].id,
            request_run_id=created.request_run_id,
            result_image_version_id=published.image_version_id,
            final_save_idempotency_key="test-d06-final-00000000",
            outcome="FINAL_SAVE_AND_USE_AS_REFERENCE",
        )
        accepted, replay = await asyncio.gather(
            coordinator.accept(acceptance_command), coordinator.accept(acceptance_command)
        )
        assert sorted((accepted.feedback.replayed, replay.feedback.replayed)) == [False, True]
        assert sorted((accepted.transfer.replayed, replay.transfer.replayed)) == [False, True]
        assert accepted.feedback.final_save is True
        assert accepted.transfer.evidence_id is not None
        assert accepted.transfer.confidence_ppm == 400_000
        assert accepted.reference_profile_job_id is not None
        assert replay.reference_profile_job_id == accepted.reference_profile_job_id
        with pytest.raises(DemoSelfTransferInputError, match="Final Save"):
            await transfer.finalize(
                FinalizeDemoSelfTransferResult(
                    demo_actor_id=graph["actor"].id,
                    request_run_id=created.request_run_id,
                    result_image_version_id=published.image_version_id,
                    user_outcome="ACCEPTED",
                )
            )
        assert len(dispatcher.messages) >= 1
        dispatcher.fail = False
        assert await reference_coordinator.reconcile() == (accepted.reference_profile_job_id,)
        postgres_session.expire_all()
        assert (
            postgres_session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
            == 1
        )
        assert (
            postgres_session.scalar(
                select(func.count()).select_from(DemoSelfTransferDimensionEvidence)
            )
            == 1
        )
        job = postgres_session.get(Job, accepted.reference_profile_job_id)
        assert job is not None and job.status == "PENDING"
        result_run = postgres_session.get(DemoSelfTransferRun, accepted.transfer.result_run_id)
        assert result_run is not None
        assert job.request_id.startswith("d06-reference-")
        assert result_run.content_digest not in job.request_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_atomic_acceptance_rolls_back_final_save_when_d06_cannot_finalize(
    postgres_session: Session, tmp_path: Any
) -> None:
    sessions, engine, graph, authority, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    transfer = DemoSelfTransferService(session_factory=sessions)
    reference = DemoReferenceProfileService(session_factory=sessions)
    reference_coordinator = DemoReferenceProfileCoordinator(
        service=reference,
        jobs=DemoJobService(session_factory=sessions),
        dispatcher=_RecordingDispatcher(),  # type: ignore[arg-type]
    )
    coordinator = DemoSteppedSelfTransferAcceptanceCoordinator(
        session_factory=sessions,
        feedback=DemoImageFeedbackService(session_factory=sessions),
        transfer=transfer,
        reference_service=reference,
        reference_coordinator=reference_coordinator,
    )
    try:
        created = await transfer.create_stepped_request(
            _command(graph, authority, execution, published, key="d06-v2-rollback")
        )
        postgres_session.expire_all()
        before_events = postgres_session.scalar(
            select(func.count()).select_from(DemoAcceptedVisualEpisode)
        )
        before_evidence = postgres_session.scalar(
            select(func.count()).select_from(DemoSelfTransferDimensionEvidence)
        )
        with pytest.raises(DemoSelfTransferConflict, match="must be RUNNING"):
            await coordinator.accept(
                AcceptDemoSteppedSelfTransfer(
                    demo_actor_id=graph["actor"].id,
                    request_run_id=created.request_run_id,
                    result_image_version_id=published.image_version_id,
                    final_save_idempotency_key="d06-v2-rollback-final-save",
                    outcome="FINAL_SAVE_AND_USE_AS_REFERENCE",
                )
            )
        postgres_session.expire_all()
        assert (
            postgres_session.scalar(select(func.count()).select_from(DemoAcceptedVisualEpisode))
            == before_events
        )
        assert (
            postgres_session.scalar(
                select(func.count()).select_from(DemoSelfTransferDimensionEvidence)
            )
            == before_evidence
        )
        job = postgres_session.get(Job, created.job_id)
        assert job is not None and job.status == "PENDING"
    finally:
        await engine.dispose()
