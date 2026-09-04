"""Real PostgreSQL regression coverage for the public D08 geometry boundary."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_d02_generic_admission import _generic_admission_bundle
from test_demo_schema_authority_invariants import (
    GENESIS_DIGEST,
    _insert_actor,
    _insert_demo_row,
    _insert_job_binding,
    _insert_p3_authority_graph,
    _insert_preference_event,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)

from mirror_api.demo_d02_generic_admission_coordinator import D02GenericAdmissionCoordinator
from mirror_api.demo_d08_geometry_adapter import (
    D08_VERIFIER_POLICY_VERSION,
    GeometryAttemptExecutionEvidence,
    GeometryStableMaterializationCore,
    stable_config_digest,
    stable_engine_digest,
)
from mirror_api.demo_d08_geometry_authority import (
    GeometryAuthorityResolutionError,
    require_geometry_plan_admission,
    resolve_geometry_execution_authority,
)
from mirror_api.demo_editing_commands import (
    CreateDemoEditPlan,
    DemoEditingCommandService,
    DemoEditingCommandUnavailable,
    ExecuteDemoEditPlan,
)
from mirror_api.demo_editing_repository import (
    DemoEditingRepositoryError,
    SqlAlchemyDemoEditingRepository,
    _authority_row,
)
from mirror_api.demo_editing_runtime import DemoEditingRuntime, DemoEditingRuntimeError
from mirror_api.demo_editing_service import (
    ArtifactState,
    DemoEditingService,
    EditArtifact,
    ExecutionCommand,
    MaterializationEvidence,
    MaterializedObject,
)
from mirror_api.demo_editing_storage import DemoLocalPrivateObjectStorage
from mirror_api.demo_editing_task_contract import DemoEditingTaskMessage
from mirror_api.demo_effect_verifier import (
    EffectVerificationInput,
    EffectVerificationResult,
    EffectVerifierPolicy,
    verify_effect,
)
from mirror_api.demo_models import (
    DemoDesiredDeltaProfile,
    DemoEditArtifact,
    DemoEditArtifactEvent,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoPairScreeningReport,
    DemoStyleProfile,
    DemoSyntheticIdentity,
    DemoVerificationResult,
)
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
    parse_operation_spec,
)
from mirror_api.demo_tool_registry import GEOMETRY_ENGINE_VERSION, TOOL_REGISTRY_VERSION
from mirror_api.models import Asset, AssetVariant, Job, JobAttempt, new_id, utcnow
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION

pytestmark = pytest.mark.integration

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def postgres_session() -> Generator[Session]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
        yield session
        session.rollback()
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
    engine.dispose()


def _bundle(session: Session, tmp_path: Path) -> Any:
    """Admit public D02 metadata with root keys required by the D08 contract."""

    return _generic_admission_bundle(
        session,
        tmp_path,
        source_storage_key_factory=lambda asset_id, _position: (
            f"internal-synthetic/v1/d02/source/{asset_id}"
        ),
        geometry_algorithm_version=ALGORITHM_VERSION,
    )


async def _count(sessions: async_sessionmaker[AsyncSession], model: type[Any]) -> int:
    async with sessions() as session:
        value = await session.scalar(select(func.count()).select_from(model))
    assert isinstance(value, int)
    return value


async def _context(
    db: Session,
    tmp_path: Path,
    *,
    desired_dimensions: dict[str, Any] | None = None,
) -> tuple[async_sessionmaker[AsyncSession], Any, dict[str, Any]]:
    bundle = _bundle(db, tmp_path)
    db.commit()
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    await D02GenericAdmissionCoordinator(session_factory=sessions).admit(
        idempotency_key="d08-authority-only-admission", bundle=bundle
    )
    source = db.get(Asset, cast(str, bundle.source_rows[0]["source_asset_id"]))
    identity = db.get(DemoSyntheticIdentity, bundle.identity_rows[0]["id"])
    assert source is not None and identity is not None
    actor = _insert_actor(db)
    graph = _insert_p3_authority_graph(
        db, actor=actor, source_asset=source, synthetic_identity=identity
    )
    session = graph["session"]
    event = _insert_preference_event(
        db,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"geometry": 1},
        demo_session=session,
        event_type="FEATURE_LOCKED",
    )
    _, profile_binding = _insert_job_binding(
        db,
        actor,
        endpoint_operation="profile.compile",
        target_type="DEMO_ACTOR",
        target_id=actor.id,
        demo_session=session,
    )
    desired = _insert_demo_row(
        db,
        DemoDesiredDeltaProfile,
        demo_actor_id=actor.id,
        demo_session_id=session.id,
        self_state_id=graph["self_state"].id,
        demo_job_binding_id=profile_binding.id,
        version=1,
        as_of_event_sequence=1,
        compilation_watermark=event.content_digest,
        compiler_version="d08-pg-profile-v1",
        dimensions=desired_dimensions or {"jaw_width": {"delta_ppm": 15_000}},
        evidence_digests=[event.content_digest],
        restraint={"max_ppm": 30_000},
    )
    style = _insert_demo_row(
        db,
        DemoStyleProfile,
        demo_actor_id=actor.id,
        demo_session_id=session.id,
        desired_delta_profile_id=desired.id,
        demo_job_binding_id=profile_binding.id,
        version=1,
        as_of_event_sequence=1,
        compilation_watermark=event.content_digest,
        compiler_version="d08-pg-style-v1",
        preferences={"finish": "natural"},
        negative_evidence=[],
        evidence_digests=[event.content_digest],
    )
    constraints = _insert_demo_row(
        db,
        DemoIdentityConstraints,
        demo_actor_id=actor.id,
        demo_session_id=None,
        self_state_id=graph["self_state"].id,
        version=1,
        constraint_scope="PERSISTENT",
        source_event_digests=[event.content_digest],
        locks={},
        bounds={"max_ppm": 100_000},
        prohibited_operations=[],
    )
    editing = _insert_demo_row(
        db,
        DemoEditingSession,
        demo_actor_id=actor.id,
        demo_session_id=session.id,
        source_asset_id=source.id,
        source_asset_sha256=source.sha256,
        desired_delta_profile_digest=desired.content_digest,
        style_profile_digest=style.content_digest,
        identity_constraints_digest=constraints.content_digest,
        context_digest=hashlib.sha256(b"d08-context").hexdigest(),
        instruction_digest=hashlib.sha256(b"d08-instruction").hexdigest(),
        tool_registry_version=TOOL_REGISTRY_VERSION,
        closed_at=None,
        tombstoned_at=None,
    )
    snapshot = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="derived",
        storage_key=f"demo-original/v1/{editing.id}/{source.sha256}",
        mime_type=source.mime_type,
        byte_size=source.byte_size,
        width=source.width,
        height=source.height,
        sha256=source.sha256,
        synthetic=True,
        is_ai_generated=False,
        is_ai_modified=False,
        internal_purpose=None,
    )
    variant = AssetVariant(
        id=new_id(),
        source_asset_id=source.id,
        result_asset_id=snapshot.id,
        variant_type="demo_p3_p7_original_snapshot",
    )
    db.add_all((snapshot, variant))
    db.commit()
    image = _insert_demo_row(
        db,
        DemoImageVersion,
        demo_actor_id=actor.id,
        demo_session_id=session.id,
        editing_session_id=editing.id,
        sequence=0,
        parent_version_id=None,
        source_asset_id=source.id,
        source_asset_sha256=source.sha256,
        result_asset_id=snapshot.id,
        result_asset_sha256=snapshot.sha256,
        result_asset_variant_id=variant.id,
        version_kind="ORIGINAL",
        plan_digest=None,
        tool_run_digest=None,
        verifier_digest=None,
    )
    return (
        sessions,
        engine,
        {
            "actor": actor,
            "session": session,
            "editing": editing,
            "source": source,
            "snapshot": snapshot,
            "image": image,
        },
    )


async def _plan(commands: DemoEditingCommandService, graph: dict[str, Any], key: str) -> Any:
    return await commands.create_edit_plan(
        CreateDemoEditPlan(
            graph["actor"].id,
            graph["editing"].id,
            OperationType.GEOMETRY,
            15_000,
            key,
            f"{key}-request",
        )
    )


async def _authority(
    sessions: async_sessionmaker[AsyncSession], graph: dict[str, Any], plan_id: str, job_id: str
) -> tuple[Any, Any, DemoEditOperation]:
    async with sessions() as session:
        job_binding = await session.scalar(
            select(DemoJobBinding).where(DemoJobBinding.job_id == job_id)
        )
        job = await session.get(Job, job_id)
        assert job_binding is not None and job is not None
        if job.status == "PENDING":
            now, token = utcnow(), new_id()
            job.status, job.attempt_count, job.lease_token = "RUNNING", 1, token
            job.lease_acquired_at, job.lease_expires_at = now, now + timedelta(minutes=5)
            attempt = JobAttempt(
                id=new_id(),
                job_id=job.id,
                attempt=1,
                status="RUNNING",
                lease_token=token,
                started_at=now,
            )
            session.add(attempt)
        else:
            assert job.status == "RUNNING"
            attempt = await session.scalar(
                select(JobAttempt).where(
                    JobAttempt.job_id == job.id,
                    JobAttempt.attempt == job.attempt_count,
                )
            )
            assert attempt is not None and attempt.status == "RUNNING"
        await session.commit()
    async with sessions() as session:
        operation = await session.scalar(
            select(DemoEditOperation).where(DemoEditOperation.edit_plan_id == plan_id)
        )
        assert operation is not None
        spec = parse_operation_spec(
            {
                "engine": operation.engine,
                "operation_type": operation.operation_type,
                "parameters": operation.parameters,
                "preserve": operation.preserve,
                "expected_effect": operation.expected_effect,
            }
        )
        authority, attempt_binding = await resolve_geometry_execution_authority(
            session,
            actor_id=graph["actor"].id,
            session_id=graph["session"].id,
            editing_session_id=graph["editing"].id,
            plan_id=plan_id,
            operation_id=operation.id,
            operation=spec,
            execution_job_binding_id=job_binding.id,
            formal_job_attempt_id=attempt.id,
        )
    return authority, attempt_binding, operation


@pytest.mark.asyncio
async def test_geometry_plan_and_resolver_use_distinct_sequence_zero_snapshot(
    postgres_session: Session, tmp_path: Path
) -> None:
    sessions, engine, graph = await _context(postgres_session, tmp_path)
    commands = DemoEditingCommandService(session_factory=sessions)
    try:
        async with sessions() as session:
            report = await session.scalar(
                select(DemoPairScreeningReport).where(DemoPairScreeningReport.status == "PASSED")
            )
        assert report is not None
        unselected_dimension = next(
            item
            for item in ("jaw_width", "chin_height", "eye_spacing")
            if item not in report.selected_dimension_keys
        )
        unselected = OperationSpec(
            engine=OperationEngine.GEOMETRY,
            operation_type=OperationType.GEOMETRY,
            parameters={"dimension_key": unselected_dimension, "delta_ppm": -15_000},
            preserve=(
                PreserveKey.IDENTITY_REFERENCE_FRAME,
                PreserveKey.NON_TARGET_GEOMETRY,
            ),
            expected_effect={
                "effect_type": "GEOMETRY",
                "target_region": "FACE_REGION",
                "dimension_key": unselected_dimension,
                "delta_ppm": -15_000,
            },
        )
        async with sessions() as session:
            with pytest.raises(
                GeometryAuthorityResolutionError,
                match="not a selected QuestionBank side",
            ):
                await require_geometry_plan_admission(
                    session,
                    editing_session_id=graph["editing"].id,
                    image_version_id=graph["image"].id,
                    operation=unselected,
                )
        before = await _count(sessions, DemoEditPlan), await _count(sessions, DemoEditOperation)
        plan = await _plan(commands, graph, "d08-geometry-positive")
        assert (
            await _count(sessions, DemoEditPlan),
            await _count(sessions, DemoEditOperation),
        ) == (before[0] + 2, before[1] + 1)
        async with sessions() as session:
            stored = await session.get(DemoEditPlan, plan.target_id)
            assert stored is not None
            execution = await commands.execute_edit_plan(
                ExecuteDemoEditPlan(
                    graph["actor"].id,
                    stored.id,
                    "GEOMETRY",
                    stored.content_digest,
                    "d08-geometry-execution",
                    "d08-geometry-execution-request",
                )
            )
        authority, _, _ = await _authority(sessions, graph, plan.target_id, execution.job_id)
        assert authority.input_asset_id == graph["snapshot"].id
        assert authority.root_source_asset_id == graph["source"].id
        assert authority.input_asset_id != authority.root_source_asset_id
        assert authority.input_asset_sha256 == authority.root_source_asset_sha256
        assert authority.fixed_case.source_asset_id == graph["source"].id

        baseline = await _count(sessions, DemoEditPlan), await _count(sessions, DemoEditOperation)
        async with sessions() as session:
            snapshot = await session.get(Asset, graph["snapshot"].id)
            assert snapshot is not None
            snapshot.deleted_at = utcnow()
            await session.commit()
        with pytest.raises(DemoEditingCommandUnavailable, match="geometry plan authority"):
            await _plan(commands, graph, "d08-geometry-deleted-snapshot")
        assert (
            await _count(sessions, DemoEditPlan),
            await _count(sessions, DemoEditOperation),
        ) == baseline
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_missing_geometry_capability_fails_before_job_claim_or_source_load(
    postgres_session: Session, tmp_path: Path
) -> None:
    sessions, engine, graph = await _context(postgres_session, tmp_path)
    commands = DemoEditingCommandService(session_factory=sessions)

    class _NoSourceLoad:
        calls = 0

        async def load(self, _reference: object) -> bytes:
            self.calls += 1
            raise AssertionError("source bytes must not load before geometry capability")

    loader = _NoSourceLoad()
    try:
        plan = await _plan(commands, graph, "d08-geometry-preclaim")
        async with sessions() as session:
            stored = await session.get(DemoEditPlan, plan.target_id)
            assert stored is not None
            execution = await commands.execute_edit_plan(
                ExecuteDemoEditPlan(
                    graph["actor"].id,
                    stored.id,
                    "GEOMETRY",
                    stored.content_digest,
                    "d08-geometry-preclaim-execution",
                    "d08-geometry-preclaim-request",
                )
            )
        runtime = DemoEditingRuntime(
            session_factory=sessions,
            asset_loader=cast(Any, loader),
            storage=DemoLocalPrivateObjectStorage(root=tmp_path / "preclaim-private"),
        )
        with pytest.raises(DemoEditingRuntimeError) as raised:
            await runtime.run(
                DemoEditingTaskMessage(
                    graph["actor"].id,
                    execution.job_id,
                    "edit_plan.execute",
                    execution.request_id,
                )
            )
        assert raised.value.code == "GEOMETRY_CAPABILITY_UNAVAILABLE"
        assert loader.calls == 0
        async with sessions() as session:
            job = await session.get(Job, execution.job_id)
            assert job is not None
            assert (job.status, job.attempt_count) == ("PENDING", 0)
            assert (
                await session.scalar(
                    select(func.count()).select_from(JobAttempt).where(JobAttempt.job_id == job.id)
                )
                == 0
            )
    finally:
        await engine.dispose()


def _materialized(authority: Any, job_attempt: Any, content: bytes) -> MaterializedObject:
    engine_digest = stable_engine_digest(authority, GEOMETRY_ENGINE_VERSION)
    config_digest = stable_config_digest(authority, D08_VERIFIER_POLICY_VERSION)
    core = GeometryStableMaterializationCore(
        operation_id=authority.operation_id,
        operation_authority_digest=authority.operation_authority_digest,
        operation_spec_digest=authority.operation_spec_digest,
        authority_digest=authority.authority_digest,
        case_id=authority.fixed_case.case_id,
        case_record_digest=authority.fixed_case.case_record_digest,
        case_specification_digest=authority.fixed_case.case_specification_digest,
        case_binding_digest=authority.fixed_case.case_binding_digest,
        backend_candidate_id=authority.fixed_case.backend_candidate_id,
        backend_algorithm_version=authority.fixed_case.backend_algorithm_version,
        backend_runtime_manifest_digest=authority.fixed_case.backend_runtime_manifest_digest,
        backend_configuration_digest=authority.fixed_case.backend_configuration_digest,
        warp_plan_digest=authority.fixed_case.warp_plan_digest,
        input_image_version_id=authority.input_image_version_id,
        input_image_version_digest=authority.input_image_version_digest,
        input_asset_id=authority.input_asset_id,
        input_asset_sha256=authority.input_asset_sha256,
        root_source_asset_id=authority.root_source_asset_id,
        root_source_asset_sha256=authority.root_source_asset_sha256,
        result_sha256=hashlib.sha256(content).hexdigest(),
        result_byte_size=len(content),
        result_media_type="image/jpeg",
        result_width=16,
        result_height=12,
        changed_pixel_count=1,
        engine_digest=engine_digest,
        config_digest=config_digest,
        stable_core_digest="0" * 64,
    )
    attempt_evidence = GeometryAttemptExecutionEvidence(
        job_attempt=job_attempt,
        operation_id=authority.operation_id,
        operation_authority_digest=authority.operation_authority_digest,
        operation_spec_digest=authority.operation_spec_digest,
        authority_digest=authority.authority_digest,
        stable_core_digest=core.stable_core_digest,
        backend_execution_receipt="d" * 64,
        attempt_receipt_digest="0" * 64,
    )
    return MaterializedObject(
        content,
        core.result_sha256,
        core.result_width,
        core.result_height,
        core.result_media_type,
        core.engine_digest,
        core.config_digest,
        geometry_stable_core=core,
        geometry_attempt_evidence=attempt_evidence,
    )


def _verification(authority: Any, materialized: MaterializedObject) -> EffectVerificationResult:
    requested_delta = authority.magnitude_ppm * (
        1 if authority.direction.value == "INCREASE" else -1
    )
    result = verify_effect(
        EffectVerifierPolicy(
            target_tolerance_ppm=60_000,
            structural_drift_thresholds_ppm={
                "chin_height": 20_000,
                "eye_spacing": 20_000,
                "jaw_width": 20_000,
            },
            locked_drift_thresholds_ppm={},
            non_target_drift_threshold_ppm=20_000,
            allowed_media_types=("image/jpeg",),
        ),
        EffectVerificationInput(
            source_asset_id=authority.input_asset_id,
            result_asset_id="f" * 32,
            target_dimension_key=authority.dimension_key,
            operation_digest=authority.operation_authority_digest,
            requested_delta_ppm=requested_delta,
            measured_delta_ppm=requested_delta,
            structural_drifts_ppm={
                "chin_height": 0,
                "eye_spacing": 0,
                "jaw_width": 0,
            },
            locked_drifts_ppm={},
            non_target_drift_ppm=0,
            artifact_status="PASS",
            artifact_codes=(),
            original_before_sha256=authority.root_source_asset_sha256,
            original_after_sha256=authority.root_source_asset_sha256,
            result_bytes=materialized.content,
            declared_result_sha256=materialized.sha256,
            decode_valid=True,
            width=materialized.width,
            height=materialized.height,
            media_type=materialized.mime_type,
        ),
    )
    assert materialized.geometry_stable_core is not None
    assert materialized.geometry_attempt_evidence is not None
    dimension_order = (
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    )
    target_index = dimension_order.index(authority.dimension_key)
    source_measurements = ["0.200000000000000000"] * 6
    result_measurements = list(source_measurements)
    result_measurements[target_index] = (
        "0.215000000000000000"
        if authority.direction.value == "INCREASE"
        else "0.185000000000000000"
    )
    control_dimensions = [key for key in dimension_order if key != authority.dimension_key]
    repeats = [
        {
            "repeat_index": repeat_index,
            "source_output_digest": hashlib.sha256(
                f"source-output-{repeat_index}".encode()
            ).hexdigest(),
            "source_receipt_digest": hashlib.sha256(
                f"source-receipt-{repeat_index}".encode()
            ).hexdigest(),
            "source_landmark_digest": "1" * 64,
            "source_observation_digest": "2" * 64,
            "result_output_digest": hashlib.sha256(
                f"result-output-{repeat_index}".encode()
            ).hexdigest(),
            "result_receipt_digest": hashlib.sha256(
                f"result-receipt-{repeat_index}".encode()
            ).hexdigest(),
            "result_landmark_digest": "3" * 64,
            "result_observation_digest": "4" * 64,
            "source_measurements_fixed18": source_measurements,
            "result_measurements_fixed18": result_measurements,
            "signed_target_delta_ppm": 15_000
            if authority.direction.value == "INCREASE"
            else -15_000,
            "control_dimensions": control_dimensions,
            "control_drifts_ppm": [0, 0, 0, 0, 0],
            "max_control_dimension_key": control_dimensions[0],
            "max_control_drift_ppm": 0,
            "direction_passed": True,
            "target_minimum_passed": True,
            "target_maximum_passed": True,
            "control_drift_passed": True,
            "observation_passed": True,
        }
        for repeat_index in (1, 2, 3)
    ]
    return replace(
        result,
        authority_metrics={
            "schema_version": "mirror.demo/D08GeometryVerificationMetrics/v1",
            "authority_digest": authority.authority_digest,
            "stable_core_digest": materialized.geometry_stable_core.stable_core_digest,
            "attempt_receipt_digest": (
                materialized.geometry_attempt_evidence.attempt_receipt_digest
            ),
            "operation_id": authority.operation_id,
            "operation_authority_digest": authority.operation_authority_digest,
            "operation_spec_digest": authority.operation_spec_digest,
            "case_id": authority.fixed_case.case_id,
            "case_ordinal": authority.fixed_case.case_ordinal,
            "source_ordinal": authority.fixed_case.source_ordinal,
            "source_asset_id": authority.root_source_asset_id,
            "result_sha256": materialized.sha256,
            "source_sha256": authority.root_source_asset_sha256,
            "dimension_key": authority.dimension_key,
            "direction": authority.direction.value,
            "magnitude_ppm": authority.magnitude_ppm,
            "source_result_digest_distinct": True,
            "source_digest_after_verification": authority.root_source_asset_sha256,
            "original_immutability_passed": True,
            "decode_passed": True,
            "artifact_passed": True,
            "runtime_identity": {
                "recipe_digest": "5" * 64,
                "runtime_manifest_digest": authority.fixed_case.backend_runtime_manifest_digest,
                "m3_algorithm_version": "accepted-m3-v1",
                "m4_algorithm_version": authority.fixed_case.backend_algorithm_version,
                "model_identity_digest": "6" * 64,
                "model_config_digest": "7" * 64,
                "weights_digest_or_no_weights": "8" * 64,
                "topology_digest": "9" * 64,
                "measurement_config_digest": "a" * 64,
                "network_policy": "PUBLIC_INTERNET_EGRESS_DISABLED",
            },
            "d08_verifier_policy_version": D08_VERIFIER_POLICY_VERSION,
            "measurement_dimension_order": list(dimension_order),
            "repeats": repeats,
            "repeat_gate_passed": True,
            "repeat_group_validation": {
                "repeat_indexes_complete": True,
                "source_receipts_fresh": True,
                "result_receipts_fresh": True,
                "source_outputs_fresh": True,
                "result_outputs_fresh": True,
                "source_landmarks_stable": True,
                "result_landmarks_stable": True,
            },
            "max_non_target_drift_ppm": 0,
            "max_non_target_dimension_key": control_dimensions[0],
            "max_non_target_repeat_index": 1,
        },
        authority_thresholds={
            "schema_version": "mirror.demo/D08GeometryVerificationThresholds/v1",
            "policy_digest": result.policy_digest,
            "repeat_count": 3,
            "target_min_abs_ppm": 10,
            "target_max_abs_ppm": 60_000,
            "max_control_drift_ppm": 20_000,
            "d08_verifier_policy_version": D08_VERIFIER_POLICY_VERSION,
        },
    )


def _artifact(
    graph: dict[str, Any],
    *,
    binding_id: str,
    operation: DemoEditOperation,
    attempt_id: str,
    materialized: MaterializedObject,
) -> tuple[DemoEditArtifact, EditArtifact]:
    artifact_id = new_id()
    private_object_key = (
        f"demo-quarantine/{graph['actor'].id}/{binding_id}/{operation.id}/{attempt_id}"
    )
    row = _authority_row(
        DemoEditArtifact,
        row_id=artifact_id,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        edit_operation_id=operation.id,
        execution_job_binding_id=binding_id,
        formal_job_attempt_id=attempt_id,
        private_object_key=private_object_key,
        engine="GEOMETRY",
        engine_version=GEOMETRY_ENGINE_VERSION,
        expected_engine_digest=materialized.engine_digest,
        expected_config_digest=materialized.config_digest,
    )
    return row, EditArtifact(
        artifact_id,
        graph["actor"].id,
        graph["session"].id,
        operation.id,
        binding_id,
        attempt_id,
        private_object_key,
        ArtifactState.RESERVED,
    )


async def _prepared_geometry_artifact(
    sessions: async_sessionmaker[AsyncSession],
    graph: dict[str, Any],
    commands: DemoEditingCommandService,
    repository: SqlAlchemyDemoEditingRepository,
    *,
    key: str,
    content: bytes,
) -> tuple[Any, MaterializedObject, EditArtifact]:
    plan = await _plan(commands, graph, key)
    async with sessions() as session:
        stored = await session.get(DemoEditPlan, plan.target_id)
        assert stored is not None
        execution = await commands.execute_edit_plan(
            ExecuteDemoEditPlan(
                graph["actor"].id,
                stored.id,
                "GEOMETRY",
                stored.content_digest,
                f"{key}-execution",
                f"{key}-execution-request",
            )
        )
    authority, job_attempt, operation = await _authority(
        sessions, graph, plan.target_id, execution.job_id
    )
    materialized = _materialized(authority, job_attempt, content)
    row, artifact = _artifact(
        graph,
        binding_id=job_attempt.execution_job_binding_id,
        operation=operation,
        attempt_id=job_attempt.attempt_id,
        materialized=materialized,
    )
    async with sessions() as session:
        session.add(row)
        await session.commit()
    return authority, materialized, await repository.append_materialized(artifact, materialized)


@pytest.mark.asyncio
async def test_geometry_materialization_replay_rejects_cross_attempt_stable_mismatch(
    postgres_session: Session, tmp_path: Path
) -> None:
    sessions, engine, graph = await _context(postgres_session, tmp_path)
    commands = DemoEditingCommandService(session_factory=sessions)
    repository = SqlAlchemyDemoEditingRepository(session_factory=sessions)
    try:
        plan = await _plan(commands, graph, "d08-geometry-replay")
        async with sessions() as session:
            stored = await session.get(DemoEditPlan, plan.target_id)
            assert stored is not None
            execution = await commands.execute_edit_plan(
                ExecuteDemoEditPlan(
                    graph["actor"].id,
                    stored.id,
                    "GEOMETRY",
                    stored.content_digest,
                    "d08-geometry-replay-execution",
                    "d08-geometry-replay-request",
                )
            )
        authority, job_attempt, operation = await _authority(
            sessions, graph, plan.target_id, execution.job_id
        )
        binding_id = job_attempt.execution_job_binding_id
        attempt_id = job_attempt.attempt_id
        materialized = _materialized(authority, job_attempt, b"d08-synthetic-output")
        publication_baseline = (
            await _count(sessions, DemoImageVersion),
            await _count(sessions, AssetVariant),
        )
        async with sessions() as session:
            first_row, first = _artifact(
                graph,
                binding_id=binding_id,
                operation=operation,
                attempt_id=attempt_id,
                materialized=materialized,
            )
            session.add(first_row)
            await session.commit()
        assert (
            await repository.append_materialized(first, materialized)
        ).state is ArtifactState.MATERIALIZED
        second_attempt = new_id()
        now = utcnow()
        async with sessions() as session:
            job = await session.get(Job, execution.job_id, with_for_update=True)
            prior = await session.get(JobAttempt, attempt_id, with_for_update=True)
            assert job is not None and prior is not None
            prior.status, prior.error_code, prior.finished_at = "FAILED", "LEASE_EXPIRED", now
            token = new_id()
            session.add(
                JobAttempt(
                    id=second_attempt,
                    job_id=job.id,
                    attempt=2,
                    status="RUNNING",
                    lease_token=token,
                    started_at=now,
                )
            )
            job.attempt_count, job.lease_token = 2, token
            job.lease_acquired_at, job.lease_expires_at = now, now + timedelta(minutes=5)
            await session.flush()
            second_row, second = _artifact(
                graph,
                binding_id=binding_id,
                operation=operation,
                attempt_id=second_attempt,
                materialized=materialized,
            )
            session.add(second_row)
            await session.commit()
        second_authority, second_job_attempt, _ = await _authority(
            sessions, graph, plan.target_id, execution.job_id
        )
        second_materialized = _materialized(
            second_authority, second_job_attempt, b"d08-synthetic-output"
        )
        assert (
            await repository.append_materialized(second, second_materialized)
        ).state is ArtifactState.MATERIALIZED
        third_attempt = new_id()
        now = utcnow()
        async with sessions() as session:
            job = await session.get(Job, execution.job_id, with_for_update=True)
            prior = await session.get(JobAttempt, second_attempt, with_for_update=True)
            assert job is not None and prior is not None
            prior.status, prior.error_code, prior.finished_at = "FAILED", "LEASE_EXPIRED", now
            token = new_id()
            session.add(
                JobAttempt(
                    id=third_attempt,
                    job_id=job.id,
                    attempt=3,
                    status="RUNNING",
                    lease_token=token,
                    started_at=now,
                )
            )
            job.attempt_count, job.lease_token = 3, token
            job.lease_acquired_at, job.lease_expires_at = now, now + timedelta(minutes=5)
            await session.flush()
            third_row, third = _artifact(
                graph,
                binding_id=binding_id,
                operation=operation,
                attempt_id=third_attempt,
                materialized=materialized,
            )
            session.add(third_row)
            await session.commit()
        third_authority, third_job_attempt, _ = await _authority(
            sessions, graph, plan.target_id, execution.job_id
        )
        third_materialized = _materialized(
            third_authority, third_job_attempt, b"d08-synthetic-output"
        )
        assert third_materialized.geometry_stable_core is not None
        assert third_materialized.geometry_attempt_evidence is not None
        incompatible_core = replace(
            third_materialized.geometry_stable_core,
            engine_digest="c" * 64,
            stable_core_digest="0" * 64,
        )
        incompatible_attempt = replace(
            third_materialized.geometry_attempt_evidence,
            stable_core_digest=incompatible_core.stable_core_digest,
            attempt_receipt_digest="0" * 64,
        )
        incompatible = replace(
            third_materialized,
            engine_digest="c" * 64,
            geometry_stable_core=incompatible_core,
            geometry_attempt_evidence=incompatible_attempt,
        )
        with pytest.raises(DemoEditingRepositoryError, match="stable surface"):
            await repository.append_materialized(third, incompatible)
        assert await _count(sessions, DemoEditArtifactEvent) == 2
        assert (
            await _count(sessions, DemoImageVersion),
            await _count(sessions, AssetVariant),
        ) == publication_baseline
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_geometry_terminal_persists_execution_and_verifier_authority(
    postgres_session: Session, tmp_path: Path
) -> None:
    sessions, engine, graph = await _context(postgres_session, tmp_path)
    commands = DemoEditingCommandService(session_factory=sessions)
    repository = SqlAlchemyDemoEditingRepository(session_factory=sessions)
    try:
        plan = await _plan(commands, graph, "d08-geometry-persistence")
        async with sessions() as session:
            stored = await session.get(DemoEditPlan, plan.target_id)
            assert stored is not None
            execution = await commands.execute_edit_plan(
                ExecuteDemoEditPlan(
                    graph["actor"].id,
                    stored.id,
                    "GEOMETRY",
                    stored.content_digest,
                    "d08-geometry-persistence-execution",
                    "d08-geometry-persistence-request",
                )
            )
        authority, job_attempt, operation = await _authority(
            sessions, graph, plan.target_id, execution.job_id
        )
        materialized = _materialized(authority, job_attempt, b"d08-synthetic-persisted-output")
        row, artifact = _artifact(
            graph,
            binding_id=job_attempt.execution_job_binding_id,
            operation=operation,
            attempt_id=job_attempt.attempt_id,
            materialized=materialized,
        )
        async with sessions() as session:
            session.add(row)
            await session.commit()
        materialized_artifact = await repository.append_materialized(artifact, materialized)
        verification = _verification(authority, materialized)
        promotion = await repository.promote_pass(
            materialized_artifact,
            verification,
            materialized,
            f"demo-published/v1/{artifact.artifact_id}/{materialized.sha256}",
        )
        async with sessions() as session:
            persisted = await session.get(DemoVerificationResult, promotion.verification_result_id)
            image = await session.get(DemoImageVersion, promotion.image_version_id)
            assert persisted is not None and image is not None
            assert image.verifier_digest == persisted.content_digest
            execution_evidence = cast(dict[str, Any], persisted.metrics["geometry_execution"])
            stable_core = cast(dict[str, Any], execution_evidence["stable_core"])
            attempt_evidence = cast(dict[str, Any], execution_evidence["attempt_evidence"])
            assert stable_core["stable_core_digest"] == (
                materialized.geometry_stable_core.stable_core_digest
            )
            assert attempt_evidence["attempt_receipt_digest"] == (
                materialized.geometry_attempt_evidence.attempt_receipt_digest
            )
            assert persisted.metrics["geometry_verification"] == dict(
                cast(dict[str, object], verification.authority_metrics)
            )
            assert persisted.thresholds["geometry_verification"] == dict(
                cast(dict[str, object], verification.authority_thresholds)
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_geometry_terminal_rejects_expired_lease_with_zero_publication(
    postgres_session: Session, tmp_path: Path
) -> None:
    sessions, engine, graph = await _context(postgres_session, tmp_path)
    commands = DemoEditingCommandService(session_factory=sessions)
    repository = SqlAlchemyDemoEditingRepository(session_factory=sessions)
    try:
        authority, materialized, artifact = await _prepared_geometry_artifact(
            sessions,
            graph,
            commands,
            repository,
            key="d08-geometry-expired",
            content=b"d08-expired-output",
        )
        async with sessions() as session:
            binding = await session.get(DemoJobBinding, artifact.execution_job_binding_id)
            assert binding is not None
            job = await session.get(Job, binding.job_id, with_for_update=True)
            assert job is not None
            job.lease_expires_at = utcnow() - timedelta(seconds=1)
            await session.commit()
        baseline = (
            await _count(sessions, Asset),
            await _count(sessions, AssetVariant),
            await _count(sessions, DemoImageVersion),
            await _count(sessions, DemoVerificationResult),
        )
        with pytest.raises(DemoEditingRepositoryError) as raised:
            await repository.promote_pass(
                artifact,
                _verification(authority, materialized),
                materialized,
                f"demo-published/v1/{artifact.artifact_id}/{materialized.sha256}",
            )
        assert raised.value.code == "EXECUTION_LEASE_EXPIRED"
        assert raised.value.published_cleanup_safe
        assert (
            await _count(sessions, Asset),
            await _count(sessions, AssetVariant),
            await _count(sessions, DemoImageVersion),
            await _count(sessions, DemoVerificationResult),
        ) == baseline
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_geometry_terminal_rejects_stale_sequence_zero_with_one_winner(
    postgres_session: Session, tmp_path: Path
) -> None:
    sessions, engine, graph = await _context(postgres_session, tmp_path)
    commands = DemoEditingCommandService(session_factory=sessions)
    repository = SqlAlchemyDemoEditingRepository(session_factory=sessions)
    try:
        first_authority, first_materialized, first_artifact = await _prepared_geometry_artifact(
            sessions,
            graph,
            commands,
            repository,
            key="d08-geometry-first-winner",
            content=b"d08-first-output",
        )
        second_authority, second_materialized, second_artifact = await _prepared_geometry_artifact(
            sessions,
            graph,
            commands,
            repository,
            key="d08-geometry-stale-loser",
            content=b"d08-second-output",
        )
        await repository.promote_pass(
            first_artifact,
            _verification(first_authority, first_materialized),
            first_materialized,
            f"demo-published/v1/{first_artifact.artifact_id}/{first_materialized.sha256}",
        )
        winner_counts = (
            await _count(sessions, Asset),
            await _count(sessions, AssetVariant),
            await _count(sessions, DemoImageVersion),
            await _count(sessions, DemoVerificationResult),
        )
        with pytest.raises(DemoEditingRepositoryError) as raised:
            await repository.promote_pass(
                second_artifact,
                _verification(second_authority, second_materialized),
                second_materialized,
                f"demo-published/v1/{second_artifact.artifact_id}/{second_materialized.sha256}",
            )
        assert raised.value.code == "REJECTED_STALE_INPUT_VERSION"
        assert raised.value.published_cleanup_safe
        assert (
            await _count(sessions, Asset),
            await _count(sessions, AssetVariant),
            await _count(sessions, DemoImageVersion),
            await _count(sessions, DemoVerificationResult),
        ) == winner_counts
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_geometry_terminal_failure_discards_pre_published_object(
    postgres_session: Session, tmp_path: Path
) -> None:
    sessions, engine, graph = await _context(postgres_session, tmp_path)
    commands = DemoEditingCommandService(session_factory=sessions)

    class _FailingTerminalRepository:
        artifact: EditArtifact | None = None

        async def reserve_execution(
            self, command: ExecutionCommand, object_key: str
        ) -> EditArtifact:
            self.artifact = EditArtifact(
                "9" * 32,
                command.actor_id,
                command.session_id,
                command.operation_id,
                command.execution_job_binding_id,
                command.formal_job_attempt_id,
                object_key,
                ArtifactState.RESERVED,
            )
            return self.artifact

        async def append_materialized(
            self, artifact: EditArtifact, value: MaterializedObject
        ) -> EditArtifact:
            self.artifact = replace(
                artifact,
                state=ArtifactState.MATERIALIZED,
                materialized=MaterializationEvidence(
                    value.sha256,
                    len(value.content),
                    value.width,
                    value.height,
                    value.mime_type,
                    value.engine_digest,
                    value.config_digest,
                ),
            )
            return self.artifact

        async def promote_pass(self, *_args: Any, **_kwargs: Any) -> Any:
            raise DemoEditingRepositoryError(
                "REJECTED_STALE_INPUT_VERSION",
                "simulated terminal revalidation failure",
                published_cleanup_safe=True,
            )

    repository = _FailingTerminalRepository()
    storage = DemoLocalPrivateObjectStorage(root=tmp_path / "d08-private")
    try:
        plan = await _plan(commands, graph, "d08-geometry-cleanup")
        async with sessions() as session:
            stored = await session.get(DemoEditPlan, plan.target_id)
            assert stored is not None
            execution = await commands.execute_edit_plan(
                ExecuteDemoEditPlan(
                    graph["actor"].id,
                    stored.id,
                    "GEOMETRY",
                    stored.content_digest,
                    "d08-geometry-cleanup-execution",
                    "d08-geometry-cleanup-request",
                )
            )
        authority, job_attempt, operation = await _authority(
            sessions, graph, plan.target_id, execution.job_id
        )
        spec = parse_operation_spec(
            {
                "engine": operation.engine,
                "operation_type": operation.operation_type,
                "parameters": operation.parameters,
                "preserve": operation.preserve,
                "expected_effect": operation.expected_effect,
            }
        )
        source_bytes = b"private-source-placeholder"
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        fixed_case = replace(
            authority.fixed_case,
            source_asset_sha256=source_sha256,
            case_binding_digest="0" * 64,
        )
        authority = replace(
            authority,
            input_asset_sha256=source_sha256,
            root_source_asset_sha256=source_sha256,
            fixed_case=fixed_case,
            authority_digest="0" * 64,
        )
        materialized = _materialized(authority, job_attempt, b"d08-cleanup-output")
        command = ExecutionCommand(
            actor_id=graph["actor"].id,
            session_id=graph["session"].id,
            operation_id=operation.id,
            operation_digest=operation.content_digest,
            execution_job_binding_id=job_attempt.execution_job_binding_id,
            formal_job_attempt_id=job_attempt.attempt_id,
            source_asset_id=authority.input_asset_id,
            source_asset_sha256=source_sha256,
            source_bytes=source_bytes,
            operation=spec,
            engine_version=GEOMETRY_ENGINE_VERSION,
            engine_digest=materialized.engine_digest,
            config_digest=materialized.config_digest,
            editing_session_id=authority.editing_session_id,
            plan_id=authority.plan_id,
            input_image_version_id=authority.input_image_version_id,
            root_source_asset_id=authority.root_source_asset_id,
            geometry_authority=authority,
            geometry_job_attempt=job_attempt,
        )

        async def dispatch(_command: ExecutionCommand) -> MaterializedObject:
            return materialized

        async def verify(
            _command: ExecutionCommand, _materialized: MaterializedObject
        ) -> EffectVerificationResult:
            return _verification(authority, materialized)

        service = DemoEditingService(
            repository=repository,
            storage=storage,
            verifier=verify,
            geometry_dispatcher=dispatch,
        )
        with pytest.raises(DemoEditingRepositoryError) as raised:
            await service.execute(command)
        assert raised.value.code == "REJECTED_STALE_INPUT_VERSION"
        assert repository.artifact is not None
        published_key = f"demo-published/v1/{repository.artifact.artifact_id}/{materialized.sha256}"
        assert await storage.read(key=published_key) is None
        assert (
            await storage.read(key=repository.artifact.private_object_key) == materialized.content
        )
    finally:
        await engine.dispose()
