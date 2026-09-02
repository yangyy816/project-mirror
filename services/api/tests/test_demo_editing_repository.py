"""Real PostgreSQL checks for D07-B edit artifact persistence authority."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Generator
from dataclasses import replace
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _insert_full_demo_graph,
    _insert_job_binding,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)

from mirror_api.demo_editing_repository import (
    DemoEditingRepositoryError,
    SqlAlchemyDemoEditingRepository,
)
from mirror_api.demo_editing_service import (
    ArtifactState,
    EditPlanCommand,
    ExecutionCommand,
    MaterializedObject,
)
from mirror_api.demo_effect_verifier import (
    EffectVerificationInput,
    EffectVerificationResult,
    EffectVerifierPolicy,
    VerificationStatus,
    verify_effect,
)
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_models import (
    DemoEditArtifact,
    DemoEditArtifactEvent,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoImageVersion,
    DemoJobBinding,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
)
from mirror_api.demo_tool_registry import RASTER_ENGINE_VERSION, TOOL_REGISTRY_VERSION
from mirror_api.models import Asset, AssetVariant, Job, JobAttempt, new_id, utcnow

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


def _spec() -> OperationSpec:
    return OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=OperationType.EXPOSURE,
        parameters={"exposure_ev_milli": 100},
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME,),
        expected_effect={
            "effect_type": "EXPOSURE",
            "target_region": "FULL_IMAGE",
            "exposure_ev_milli": 100,
        },
    )


def _restore_spec(target_id: str, target_digest: str) -> OperationSpec:
    return OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=OperationType.RESTORE,
        parameters={
            "target_image_version_id": target_id,
            "target_image_version_digest": target_digest,
        },
        preserve=(PreserveKey.TARGET_VERSION_BYTES,),
        expected_effect={
            "effect_type": "RESTORE",
            "target_region": "VERSION_CONTENT",
            "target_image_version_digest": target_digest,
        },
    )


def _repository() -> tuple[SqlAlchemyDemoEditingRepository, AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return SqlAlchemyDemoEditingRepository(session_factory=sessions), engine


async def _execution_context(
    postgres_session: Session,
    *,
    restore: bool = False,
    tool_registry_version: str = TOOL_REGISTRY_VERSION,
    engine_version: str = RASTER_ENGINE_VERSION,
) -> tuple[ExecutionCommand, SqlAlchemyDemoEditingRepository, AsyncEngine]:
    graph = _insert_full_demo_graph(postgres_session)
    actor = graph["actor"]
    demo_session = graph["session"]
    editing_session = graph["editing_session"]
    source_image = graph["image1"]
    source_asset = graph["image1_asset"]
    target_image = graph["image0"]
    operation_spec = (
        _restore_spec(target_image.id, target_image.content_digest) if restore else _spec()
    )
    repository, engine = _repository()
    plan_id = await repository.persist_plan(
        EditPlanCommand(
            actor.id,
            demo_session.id,
            editing_session.id,
            source_image.id,
            (operation_spec,),
            "d07-repository-test-planner-v1",
            tool_registry_version,
        )
    )
    operation = postgres_session.scalar(
        select(DemoEditOperation).where(DemoEditOperation.edit_plan_id == plan_id)
    )
    assert operation is not None
    job, binding = _insert_job_binding(
        postgres_session,
        actor,
        endpoint_operation="edit_plan.execute",
        target_type="EDIT_PLAN",
        target_id=plan_id,
        demo_session=demo_session,
    )
    started_at = utcnow()
    job.status = "RUNNING"
    job.attempt_count = 1
    job.updated_at = started_at
    attempt = JobAttempt(
        id=new_id(), job_id=job.id, attempt=1, status="RUNNING", started_at=started_at
    )
    postgres_session.add(attempt)
    parent_job_id = None
    parent_attempt_id = None
    if restore:
        parent_job, _ = _insert_job_binding(
            postgres_session,
            actor,
            endpoint_operation="image_version.restore",
            target_type="IMAGE_VERSION",
            target_id=target_image.id,
            demo_session=demo_session,
        )
        parent_started_at = utcnow()
        parent_job.status = "RUNNING"
        parent_job.attempt_count = 1
        parent_job.updated_at = parent_started_at
        parent_attempt = JobAttempt(
            id=new_id(),
            job_id=parent_job.id,
            attempt=1,
            status="RUNNING",
            started_at=parent_started_at,
        )
        postgres_session.add(parent_attempt)
        parent_job_id = parent_job.id
        parent_attempt_id = parent_attempt.id
    postgres_session.commit()
    return (
        ExecutionCommand(
            actor_id=actor.id,
            session_id=demo_session.id,
            operation_id=operation.id,
            operation_digest=operation.content_digest,
            execution_job_binding_id=binding.id,
            formal_job_attempt_id=attempt.id,
            source_asset_id=source_asset.id,
            source_asset_sha256=source_asset.sha256,
            source_bytes=b"synthetic-only-repository-test-source",
            operation=operation_spec,
            engine_version=engine_version,
            engine_digest=hashlib.sha256(b"d07-test-engine").hexdigest(),
            config_digest=hashlib.sha256(b"d07-test-config").hexdigest(),
            parent_job_id=parent_job_id,
            parent_job_attempt_id=parent_attempt_id,
        ),
        repository,
        engine,
    )


def _materialized(command: ExecutionCommand) -> MaterializedObject:
    content = b"synthetic-only-private-edit-result"
    return MaterializedObject(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        width=16,
        height=12,
        mime_type="image/png",
        engine_digest=command.engine_digest,
        config_digest=command.config_digest,
    )


@pytest.mark.asyncio
async def test_execution_revalidates_root_source_before_reservation(
    postgres_session: Session,
) -> None:
    command, repository, engine = await _execution_context(postgres_session)
    try:
        operation = postgres_session.get(DemoEditOperation, command.operation_id)
        assert operation is not None
        plan = postgres_session.get(DemoEditPlan, operation.edit_plan_id)
        assert plan is not None
        editing = postgres_session.get(DemoEditingSession, plan.editing_session_id)
        assert editing is not None
        root_source = postgres_session.get(Asset, editing.source_asset_id)
        assert root_source is not None
        root_source.deleted_at = utcnow()
        postgres_session.commit()
        before = {
            DemoEditArtifact: postgres_session.scalar(
                select(func.count()).select_from(DemoEditArtifact)
            ),
            DemoEditArtifactEvent: postgres_session.scalar(
                select(func.count()).select_from(DemoEditArtifactEvent)
            ),
            DemoImageVersion: postgres_session.scalar(
                select(func.count()).select_from(DemoImageVersion)
            ),
            AssetVariant: postgres_session.scalar(select(func.count()).select_from(AssetVariant)),
        }
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        with pytest.raises(DemoEditingRepositoryError) as rejected:
            await repository.reserve_execution(
                command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
            )
        assert rejected.value.code == "ROOT_SOURCE_AUTHORITY_MISMATCH"
        postgres_session.expire_all()
        for model, count in before.items():
            assert postgres_session.scalar(select(func.count()).select_from(model)) == count
    finally:
        await engine.dispose()


def _verification(
    command: ExecutionCommand, materialized: MaterializedObject, status: str = "PASS"
) -> EffectVerificationResult:
    return verify_effect(
        EffectVerifierPolicy(
            target_tolerance_ppm=1,
            structural_drift_thresholds_ppm={"jaw_width": 1},
            locked_drift_thresholds_ppm={},
            non_target_drift_threshold_ppm=1,
            allowed_media_types=("image/jpeg", "image/png"),
        ),
        EffectVerificationInput(
            source_asset_id=command.source_asset_id,
            result_asset_id="d" * 32,
            target_dimension_key="jaw_width",
            operation_digest=command.operation_digest,
            requested_delta_ppm=0,
            measured_delta_ppm=0,
            structural_drifts_ppm={"jaw_width": 0},
            locked_drifts_ppm={},
            non_target_drift_ppm=0,
            artifact_status=status,
            artifact_codes=(),
            original_before_sha256=command.source_asset_sha256,
            original_after_sha256=command.source_asset_sha256,
            result_bytes=materialized.content,
            declared_result_sha256=materialized.sha256,
            decode_valid=True,
            width=materialized.width,
            height=materialized.height,
            media_type=materialized.mime_type,
        ),
    )


def _count(postgres_session: Session, model: type[Any]) -> int:
    value = postgres_session.scalar(select(func.count()).select_from(model))
    return cast(int, value)


def _execution_job_and_attempt(
    postgres_session: Session, command: ExecutionCommand
) -> tuple[Job, JobAttempt]:
    postgres_session.expire_all()
    binding = postgres_session.get(DemoJobBinding, command.execution_job_binding_id)
    attempt = postgres_session.get(JobAttempt, command.formal_job_attempt_id)
    assert binding is not None and attempt is not None
    job = postgres_session.get(Job, binding.job_id)
    assert job is not None and attempt.job_id == job.id
    return job, attempt


@pytest.mark.asyncio
async def test_reservation_and_materialization_replay_are_idempotent(
    postgres_session: Session,
) -> None:
    command, repository, engine = await _execution_context(postgres_session)
    try:
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        key += f"{command.operation_id}/{command.formal_job_attempt_id}"
        reserved = await repository.reserve_execution(command, key)
        assert reserved.state is ArtifactState.RESERVED
        assert (
            await repository.reserve_execution(command, key)
        ).artifact_id == reserved.artifact_id

        materialized = _materialized(command)
        first = await repository.append_materialized(reserved, materialized)
        replay = await repository.append_materialized(first, materialized)
        assert first.state is replay.state is ArtifactState.MATERIALIZED
        assert replay.materialized is not None and replay.materialized.sha256 == materialized.sha256
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoEditArtifactEvent)
                .where(DemoEditArtifactEvent.demo_edit_artifact_id == reserved.artifact_id)
            )
            == 1
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ("FAIL", "HUMAN_REVIEW"))
async def test_non_pass_rejection_never_creates_publication_authority(
    postgres_session: Session, status: str
) -> None:
    command, repository, engine = await _execution_context(postgres_session)
    try:
        before = (
            _count(postgres_session, Asset),
            _count(postgres_session, AssetVariant),
            _count(postgres_session, DemoImageVersion),
        )
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        artifact = await repository.reserve_execution(
            command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
        )
        materialized = _materialized(command)
        materialized_artifact = await repository.append_materialized(artifact, materialized)
        rejected = await repository.append_rejected(
            materialized_artifact, _verification(command, materialized, status), materialized
        )
        assert rejected.state is ArtifactState.REJECTED
        execution_job, execution_attempt = _execution_job_and_attempt(postgres_session, command)
        assert execution_job.status == "REJECTED"
        assert execution_attempt.status == "REJECTED"
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoVerificationResult)
                .where(
                    DemoVerificationResult.demo_edit_artifact_id == artifact.artifact_id,
                    DemoVerificationResult.output_asset_id.is_(None),
                )
            )
            == 1
        )
        assert (
            _count(postgres_session, Asset),
            _count(postgres_session, AssetVariant),
            _count(postgres_session, DemoImageVersion),
        ) == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_only_publishable_pass_creates_one_terminal_publication(
    postgres_session: Session,
) -> None:
    command, repository, engine = await _execution_context(postgres_session)
    try:
        before = (
            _count(postgres_session, Asset),
            _count(postgres_session, AssetVariant),
            _count(postgres_session, DemoImageVersion),
        )
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        artifact = await repository.reserve_execution(
            command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
        )
        materialized = _materialized(command)
        materialized_artifact = await repository.append_materialized(artifact, materialized)
        verification = _verification(command, materialized)
        published_key = f"demo-published/v1/{artifact.artifact_id}/{materialized.sha256}"
        first = await repository.promote_pass(
            materialized_artifact, verification, materialized, published_key
        )
        second = await repository.promote_pass(
            materialized_artifact, verification, materialized, published_key
        )
        assert first == second
        execution_job, execution_attempt = _execution_job_and_attempt(postgres_session, command)
        assert execution_job.status == "COMPLETED"
        assert execution_attempt.status == "COMPLETED"
        assert (
            postgres_session.scalar(select(func.count()).select_from(Asset)),
            postgres_session.scalar(select(func.count()).select_from(AssetVariant)),
            postgres_session.scalar(select(func.count()).select_from(DemoImageVersion)),
        ) == tuple(count + 1 for count in before)
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoToolRun)
                .where(DemoToolRun.demo_edit_artifact_id == artifact.artifact_id)
            )
            == 1
        )
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoEditArtifactEvent)
                .where(
                    DemoEditArtifactEvent.demo_edit_artifact_id == artifact.artifact_id,
                    DemoEditArtifactEvent.event_type == "PROMOTED",
                )
            )
            == 1
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_registry_version", "engine_version", "expected_code"),
    (
        ("unknown-tool-registry-v0", RASTER_ENGINE_VERSION, "TOOL_REGISTRY_MISMATCH"),
        (TOOL_REGISTRY_VERSION, "unknown-raster-engine-v0", "TOOL_ENGINE_VERSION_MISMATCH"),
    ),
)
async def test_registry_binding_mismatch_fails_closed_before_publication(
    postgres_session: Session,
    tool_registry_version: str,
    engine_version: str,
    expected_code: str,
) -> None:
    command, repository, engine = await _execution_context(
        postgres_session,
        tool_registry_version=tool_registry_version,
        engine_version=engine_version,
    )
    try:
        before = (
            _count(postgres_session, Asset),
            _count(postgres_session, AssetVariant),
            _count(postgres_session, DemoToolRun),
            _count(postgres_session, DemoVerificationResult),
            _count(postgres_session, DemoImageVersion),
        )
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        artifact = await repository.reserve_execution(
            command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
        )
        materialized = _materialized(command)
        materialized_artifact = await repository.append_materialized(artifact, materialized)
        with pytest.raises(DemoEditingRepositoryError) as error:
            await repository.promote_pass(
                materialized_artifact,
                _verification(command, materialized),
                materialized,
                f"demo-published/v1/{artifact.artifact_id}/{materialized.sha256}",
            )
        assert error.value.code == expected_code
        assert (
            _count(postgres_session, Asset),
            _count(postgres_session, AssetVariant),
            _count(postgres_session, DemoToolRun),
            _count(postgres_session, DemoVerificationResult),
            _count(postgres_session, DemoImageVersion),
        ) == before
        execution_job, execution_attempt = _execution_job_and_attempt(postgres_session, command)
        assert execution_job.status == execution_attempt.status == "RUNNING"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_execution_binding_and_published_key_fail_closed(
    postgres_session: Session,
) -> None:
    command, repository, engine = await _execution_context(postgres_session)
    try:
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        with pytest.raises(DemoEditingRepositoryError, match="execution authority") as error:
            await repository.reserve_execution(
                replace(command, execution_job_binding_id="0" * 32),
                key + f"{command.operation_id}/{command.formal_job_attempt_id}",
            )
        assert error.value.code == "EXECUTION_AUTHORITY_UNAVAILABLE"

        artifact = await repository.reserve_execution(
            command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
        )
        materialized = _materialized(command)
        materialized_artifact = await repository.append_materialized(artifact, materialized)
        asset_count = _count(postgres_session, Asset)
        with pytest.raises(DemoEditingRepositoryError, match="published storage key") as error:
            await repository.promote_pass(
                materialized_artifact,
                _verification(command, materialized),
                materialized,
                "not-a-published-key",
            )
        assert error.value.code == "INVALID_PUBLISHED_KEY"
        assert _count(postgres_session, Asset) == asset_count
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_execution_cannot_publish_an_image_version(
    postgres_session: Session,
) -> None:
    command, repository, engine = await _execution_context(postgres_session)
    try:
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        artifact = await repository.reserve_execution(
            command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
        )
        materialized = _materialized(command)
        materialized_artifact = await repository.append_materialized(artifact, materialized)
        execution_job, _ = _execution_job_and_attempt(postgres_session, command)
        job_service = DemoJobService(
            session_factory=async_sessionmaker(engine, expire_on_commit=False)
        )
        cancelled = await job_service.cancel(
            demo_actor_id=command.actor_id,
            job_id=execution_job.id,
            expected_status="RUNNING",
            reason="USER_REQUEST",
            idempotency_key="d07-cancel-before-publication",
        )
        assert cancelled.status == "CANCELLED"
        image_count = _count(postgres_session, DemoImageVersion)
        with pytest.raises(DemoEditingRepositoryError) as error:
            await repository.promote_pass(
                materialized_artifact,
                _verification(command, materialized),
                materialized,
                f"demo-published/v1/{artifact.artifact_id}/{materialized.sha256}",
            )
        assert error.value.code == "EXECUTION_NOT_RUNNING"
        assert _count(postgres_session, DemoImageVersion) == image_count
        assert (
            postgres_session.scalar(
                select(func.count())
                .select_from(DemoEditArtifactEvent)
                .where(
                    DemoEditArtifactEvent.demo_edit_artifact_id == artifact.artifact_id,
                    DemoEditArtifactEvent.event_type == "PROMOTED",
                )
            )
            == 0
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_restore_wrong_target_digest_rolls_back_without_terminal_jobs(
    postgres_session: Session,
) -> None:
    command, repository, engine = await _execution_context(postgres_session, restore=True)
    try:
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        artifact = await repository.reserve_execution(
            command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
        )
        wrong_materialized = _materialized(command)
        materialized_artifact = await repository.append_materialized(artifact, wrong_materialized)
        image_count = _count(postgres_session, DemoImageVersion)
        with pytest.raises(DemoEditingRepositoryError) as error:
            await repository.promote_pass(
                materialized_artifact,
                _verification(command, wrong_materialized),
                wrong_materialized,
                f"demo-published/v1/{artifact.artifact_id}/{wrong_materialized.sha256}",
                parent_job_id=command.parent_job_id,
                parent_job_attempt_id=command.parent_job_attempt_id,
            )
        assert error.value.code == "TRANSITION_RESULT_DIGEST_MISMATCH"
        child_job, child_attempt = _execution_job_and_attempt(postgres_session, command)
        assert child_job.status == child_attempt.status == "RUNNING"
        assert command.parent_job_id is not None and command.parent_job_attempt_id is not None
        postgres_session.expire_all()
        parent_job = postgres_session.get(Job, command.parent_job_id)
        parent_attempt = postgres_session.get(JobAttempt, command.parent_job_attempt_id)
        assert parent_job is not None and parent_attempt is not None
        assert parent_job.status == parent_attempt.status == "RUNNING"
        assert _count(postgres_session, DemoImageVersion) == image_count
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_restore_target_digest_creates_distinct_version_and_finishes_both_jobs(
    postgres_session: Session,
) -> None:
    command, repository, engine = await _execution_context(postgres_session, restore=True)
    try:
        target_id = command.operation.parameters["target_image_version_id"]
        assert isinstance(target_id, str)
        target = postgres_session.get(DemoImageVersion, target_id)
        assert target is not None
        target_asset = postgres_session.get(Asset, target.result_asset_id)
        assert target_asset is not None
        key = f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        artifact = await repository.reserve_execution(
            command, key + f"{command.operation_id}/{command.formal_job_attempt_id}"
        )
        correct_materialized = replace(_materialized(command), sha256=target.result_asset_sha256)
        materialized_artifact = await repository.append_materialized(artifact, correct_materialized)
        verification = replace(
            _verification(command, correct_materialized),
            result_digest=target.result_asset_sha256,
            status=VerificationStatus.PASS,
            publishable=True,
        )
        promotion = await repository.promote_pass(
            materialized_artifact,
            verification,
            correct_materialized,
            f"demo-published/v1/{artifact.artifact_id}/{correct_materialized.sha256}",
            parent_job_id=command.parent_job_id,
            parent_job_attempt_id=command.parent_job_attempt_id,
        )
        assert promotion.asset_id not in {target.result_asset_id, command.source_asset_id}
        restored = postgres_session.get(DemoImageVersion, promotion.image_version_id)
        assert restored is not None and restored.version_kind == "RESTORED"
        child_job, child_attempt = _execution_job_and_attempt(postgres_session, command)
        assert child_job.status == child_attempt.status == "COMPLETED"
        assert command.parent_job_id is not None and command.parent_job_attempt_id is not None
        postgres_session.expire_all()
        parent_job = postgres_session.get(Job, command.parent_job_id)
        parent_attempt = postgres_session.get(JobAttempt, command.parent_job_attempt_id)
        assert parent_job is not None and parent_attempt is not None
        assert parent_job.status == parent_attempt.status == "COMPLETED"
    finally:
        await engine.dispose()
