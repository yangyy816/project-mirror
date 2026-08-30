"""PostgreSQL adapter for the frozen D07 editing authority graph.

The adapter deliberately commits reservation and materialization in separate
transactions.  Private storage writes happen between those transactions in
``DemoEditingService`` so a retry can recover a durable object without ever
publishing an unverified Asset or ImageVersion.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, NoReturn, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_editing_service import (
    ArtifactState,
    EditArtifact,
    EditingSessionCommand,
    EditPlanCommand,
    ExecutionCommand,
    MaterializationEvidence,
    MaterializedObject,
    Promotion,
)
from mirror_api.demo_effect_verifier import (
    VERIFIER_VERSION,
    EffectVerificationResult,
    VerificationStatus,
)
from mirror_api.demo_idempotency import canonical_json_bytes, semantic_request_digest
from mirror_api.demo_models import (
    DemoActor,
    DemoDesiredDeltaProfile,
    DemoEditArtifact,
    DemoEditArtifactEvent,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoSession,
    DemoStyleProfile,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.demo_operation_graph import (
    ImageVersionReference,
    OperationLineageError,
    OperationType,
    TransitionIntent,
    plan_restore_transition,
    plan_rollback_transition,
    validate_result_asset_id,
)
from mirror_api.models import Asset, AssetVariant, Job, JobAttempt, new_id, utcnow

DEMO_JOB_BINDING_SCHEMA = "mirror.demo/DemoJobBinding/v1"
_TERMINAL_EVENTS = frozenset({"PROMOTED", "REJECTED", "CANCELLED", "CLEANED"})
_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PUBLISHED_KEY = re.compile(r"^demo-published/v1/[0-9a-f]{32}/[0-9a-f]{64}$")
_NON_AUTHORITY_COLUMNS = frozenset(
    {
        "id",
        "schema_version",
        "canonical_payload",
        "content_digest",
        "created_at",
        "closed_at",
        "tombstoned_at",
    }
)


class DemoEditingRepositoryError(RuntimeError):
    """A stable fail-closed persistence error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SqlAlchemyDemoEditingRepository:
    """Transaction-scoped implementation of ``DemoEditingRepository``."""

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def create_editing_session(self, command: EditingSessionCommand) -> str:
        async with self._sessions() as session:
            async with session.begin():
                await self._require_owner_context(
                    session, actor_id=command.actor_id, session_id=command.session_id
                )
                source = await session.get(Asset, command.source_asset_id)
                if (
                    source is None
                    or source.deleted_at is not None
                    or source.sha256 != command.source_asset_sha256
                ):
                    raise DemoEditingRepositoryError(
                        "SOURCE_ASSET_UNAVAILABLE", "editing source authority is unavailable"
                    )
                await self._require_profile_digest(
                    session,
                    DemoDesiredDeltaProfile,
                    command.desired_delta_profile_digest,
                    command.actor_id,
                )
                await self._require_profile_digest(
                    session,
                    DemoStyleProfile,
                    command.style_profile_digest,
                    command.actor_id,
                )
                await self._require_profile_digest(
                    session,
                    DemoIdentityConstraints,
                    command.identity_constraints_digest,
                    command.actor_id,
                )
                fields: dict[str, Any] = {
                    "demo_actor_id": command.actor_id,
                    "demo_session_id": command.session_id,
                    "source_asset_id": source.id,
                    "source_asset_sha256": source.sha256,
                    "desired_delta_profile_digest": command.desired_delta_profile_digest,
                    "style_profile_digest": command.style_profile_digest,
                    "identity_constraints_digest": command.identity_constraints_digest,
                    "context_digest": command.context_digest,
                    "instruction_digest": command.instruction_digest,
                    "tool_registry_version": command.tool_registry_version,
                    "closed_at": None,
                    "tombstoned_at": None,
                }
                candidate = _authority_row(DemoEditingSession, **fields)
                existing = await session.scalar(
                    select(DemoEditingSession).where(
                        DemoEditingSession.content_digest == candidate.content_digest
                    )
                )
                if existing is not None:
                    self._validate_editing_session(existing, fields)
                    return existing.id
                session.add(candidate)
                try:
                    await session.flush()
                except IntegrityError as exc:
                    raise DemoEditingRepositoryError(
                        "EDITING_SESSION_CONFLICT", "editing Session authority conflicts"
                    ) from exc
                return candidate.id

    async def persist_plan(self, command: EditPlanCommand) -> str:
        async with self._sessions() as session:
            async with session.begin():
                editing = await self._lock_editing_session(
                    session,
                    actor_id=command.actor_id,
                    session_id=command.session_id,
                    editing_session_id=command.editing_session_id,
                )
                image = await session.scalar(
                    select(DemoImageVersion)
                    .where(
                        DemoImageVersion.id == command.input_image_version_id,
                        DemoImageVersion.demo_actor_id == command.actor_id,
                        DemoImageVersion.demo_session_id == command.session_id,
                        DemoImageVersion.editing_session_id == editing.id,
                    )
                    .with_for_update()
                )
                if image is None:
                    raise DemoEditingRepositoryError(
                        "INPUT_IMAGE_VERSION_UNAVAILABLE", "plan input ImageVersion is unavailable"
                    )
                maximum = await session.scalar(
                    select(func.max(DemoEditPlan.plan_version)).where(
                        DemoEditPlan.input_image_version_id == image.id
                    )
                )
                plan_version = int(maximum or 0) + 1
                common: dict[str, Any] = {
                    "demo_actor_id": command.actor_id,
                    "demo_session_id": command.session_id,
                    "editing_session_id": editing.id,
                    "input_image_version_id": image.id,
                    "plan_version": plan_version,
                    "desired_delta_profile_digest": editing.desired_delta_profile_digest,
                    "style_profile_digest": editing.style_profile_digest,
                    "identity_constraints_digest": editing.identity_constraints_digest,
                    "instruction_digest": editing.instruction_digest,
                    "planner_version": command.planner_version,
                    "tool_registry_version": command.tool_registry_version,
                }
                request_plan = _authority_row(
                    DemoEditPlan,
                    **common,
                    record_kind="REQUEST",
                    request_plan_id=None,
                    operation_specs=[],
                )
                specs = [item.canonical_payload() for item in command.operation_specs]
                result_plan = _authority_row(
                    DemoEditPlan,
                    **common,
                    record_kind="RESULT",
                    request_plan_id=request_plan.id,
                    operation_specs=specs,
                )
                operations = [
                    _authority_row(
                        DemoEditOperation,
                        demo_actor_id=command.actor_id,
                        demo_session_id=command.session_id,
                        edit_plan_id=result_plan.id,
                        operation_index=index,
                        engine=spec.engine.value,
                        operation_type=spec.operation_type.value,
                        parameters=dict(spec.parameters),
                        preserve=[item.value for item in spec.preserve],
                        expected_effect=dict(spec.expected_effect),
                    )
                    for index, spec in enumerate(command.operation_specs)
                ]
                # PostgreSQL validates the composite plan/owner foreign key on
                # DemoEditOperation immediately.  Persist both immutable plan
                # authority rows first so operation insertion never depends on
                # SQLAlchemy's ordering of otherwise unrelated mapped rows.
                session.add_all((request_plan, result_plan))
                try:
                    await session.flush()
                    session.add_all(operations)
                    await session.flush()
                except IntegrityError as exc:
                    raise DemoEditingRepositoryError(
                        "EDIT_PLAN_CONFLICT", "edit plan authority conflicts"
                    ) from exc
                return result_plan.id

    async def reserve_execution(self, command: ExecutionCommand, object_key: str) -> EditArtifact:
        async with self._sessions() as session:
            async with session.begin():
                existing = await session.scalar(
                    select(DemoEditArtifact)
                    .where(
                        DemoEditArtifact.execution_job_binding_id
                        == command.execution_job_binding_id,
                        DemoEditArtifact.formal_job_attempt_id == command.formal_job_attempt_id,
                        DemoEditArtifact.edit_operation_id == command.operation_id,
                    )
                    .with_for_update()
                )
                if existing is not None:
                    self._validate_artifact_row(existing, command, object_key)
                    return await self._artifact_dto(session, existing)
                await self._validate_execution_context(session, command)
                row = _authority_row(
                    DemoEditArtifact,
                    demo_actor_id=command.actor_id,
                    demo_session_id=command.session_id,
                    edit_operation_id=command.operation_id,
                    execution_job_binding_id=command.execution_job_binding_id,
                    formal_job_attempt_id=command.formal_job_attempt_id,
                    private_object_key=object_key,
                    engine=command.operation.engine.value,
                    engine_version=command.engine_version,
                    expected_engine_digest=command.engine_digest,
                    expected_config_digest=command.config_digest,
                )
                session.add(row)
                try:
                    await session.flush()
                except IntegrityError as exc:
                    raise DemoEditingRepositoryError(
                        "EDIT_ARTIFACT_CONFLICT", "edit artifact reservation conflicts"
                    ) from exc
                return await self._artifact_dto(session, row)

    async def append_materialized(
        self, artifact: EditArtifact, materialized: MaterializedObject
    ) -> EditArtifact:
        async with self._sessions() as session:
            async with session.begin():
                row = await self._lock_artifact(session, artifact)
                current = await self._artifact_dto(session, row)
                if current.state is not ArtifactState.RESERVED:
                    if current.state is ArtifactState.MATERIALIZED:
                        _validate_materialized_replay(current, materialized)
                    return current
                event = _authority_row(
                    DemoEditArtifactEvent,
                    demo_actor_id=row.demo_actor_id,
                    demo_session_id=row.demo_session_id,
                    demo_edit_artifact_id=row.id,
                    sequence=1,
                    event_type="MATERIALIZED",
                    object_sha256=materialized.sha256,
                    byte_size=len(materialized.content),
                    width=materialized.width,
                    height=materialized.height,
                    mime_type=materialized.mime_type,
                    engine_digest=materialized.engine_digest,
                    config_digest=materialized.config_digest,
                    promoted_asset_id=None,
                    promoted_asset_variant_id=None,
                    verification_result_id=None,
                    image_version_id=None,
                    reason_code=None,
                )
                session.add(event)
                try:
                    await session.flush()
                except IntegrityError as exc:
                    raise DemoEditingRepositoryError(
                        "MATERIALIZATION_CONFLICT", "materialization authority conflicts"
                    ) from exc
                return await self._artifact_dto(session, row)

    async def append_rejected(
        self,
        artifact: EditArtifact,
        verification: EffectVerificationResult,
        materialized: MaterializedObject,
        *,
        parent_job_id: str | None = None,
        parent_job_attempt_id: str | None = None,
    ) -> EditArtifact:
        if verification.status is VerificationStatus.PASS:
            raise DemoEditingRepositoryError(
                "INVALID_REJECTION", "PASS verification cannot reject an artifact"
            )
        async with self._sessions() as session:
            async with session.begin():
                (
                    execution_job,
                    execution_attempt,
                    parent_job,
                    parent_attempt,
                ) = await self._lock_execution_terminal_context(
                    session,
                    artifact,
                    parent_job_id=parent_job_id,
                    parent_job_attempt_id=parent_job_attempt_id,
                )
                row = await self._lock_artifact(session, artifact)
                current = await self._artifact_dto(session, row)
                if current.state in {
                    ArtifactState.REJECTED,
                    ArtifactState.CANCELLED,
                    ArtifactState.CLEANED,
                }:
                    _validate_terminal_execution(current.state, execution_job, execution_attempt)
                    if parent_job is not None and parent_attempt is not None:
                        _validate_terminal_execution(current.state, parent_job, parent_attempt)
                    return current
                if current.state is ArtifactState.PROMOTED:
                    raise DemoEditingRepositoryError(
                        "TERMINAL_ARTIFACT_CONFLICT", "published artifact cannot be rejected"
                    )
                _require_running_execution(execution_job, execution_attempt)
                if parent_job is not None and parent_attempt is not None:
                    _require_running_execution(parent_job, parent_attempt)
                _validate_materialized_replay(current, materialized)
                tool = await self._ensure_tool_run(session, row)
                verification_row, verifier_job, verifier_attempt = await self._ensure_verification(
                    session,
                    artifact=row,
                    tool=tool,
                    verification=verification,
                    image_version_id=None,
                    output_asset=None,
                )
                event = _authority_row(
                    DemoEditArtifactEvent,
                    demo_actor_id=row.demo_actor_id,
                    demo_session_id=row.demo_session_id,
                    demo_edit_artifact_id=row.id,
                    sequence=2,
                    event_type="REJECTED",
                    object_sha256=None,
                    byte_size=None,
                    width=None,
                    height=None,
                    mime_type=None,
                    engine_digest=None,
                    config_digest=None,
                    promoted_asset_id=None,
                    promoted_asset_variant_id=None,
                    verification_result_id=verification_row.id,
                    image_version_id=None,
                    reason_code=f"VERIFIER_{verification.status.value}",
                )
                session.add(event)
                _finish_job(
                    verifier_job,
                    verifier_attempt,
                    status="REJECTED",
                    result_code=f"VERIFICATION_{verification.status.value}",
                )
                _finish_job(
                    execution_job,
                    execution_attempt,
                    status="REJECTED",
                    result_code=f"VERIFICATION_{verification.status.value}",
                )
                if parent_job is not None and parent_attempt is not None:
                    _finish_job(
                        parent_job,
                        parent_attempt,
                        status="REJECTED",
                        result_code=f"RESTORE_VERIFICATION_{verification.status.value}",
                    )
                await session.flush()
                return await self._artifact_dto(session, row)

    async def promote_pass(
        self,
        artifact: EditArtifact,
        verification: EffectVerificationResult,
        materialized: MaterializedObject,
        published_storage_key: str,
        *,
        parent_job_id: str | None = None,
        parent_job_attempt_id: str | None = None,
    ) -> Promotion:
        if verification.status is not VerificationStatus.PASS or not verification.publishable:
            raise DemoEditingRepositoryError(
                "INVALID_PROMOTION", "only publishable PASS verification may promote"
            )
        if _PUBLISHED_KEY.fullmatch(published_storage_key) is None:
            raise DemoEditingRepositoryError(
                "INVALID_PUBLISHED_KEY", "published storage key is invalid"
            )
        async with self._sessions() as session:
            async with session.begin():
                (
                    execution_job,
                    execution_attempt,
                    parent_job,
                    parent_attempt,
                ) = await self._lock_execution_terminal_context(
                    session,
                    artifact,
                    parent_job_id=parent_job_id,
                    parent_job_attempt_id=parent_job_attempt_id,
                )
                row = await self._lock_artifact(session, artifact)
                current = await self._artifact_dto(session, row)
                if current.state is ArtifactState.PROMOTED:
                    _validate_terminal_execution(current.state, execution_job, execution_attempt)
                    if parent_job is not None and parent_attempt is not None:
                        _validate_terminal_execution(current.state, parent_job, parent_attempt)
                    return await self._promotion_for_artifact(session, row.id)
                if current.state is not ArtifactState.MATERIALIZED:
                    raise DemoEditingRepositoryError(
                        "ARTIFACT_NOT_MATERIALIZED", "artifact is not publishable"
                    )
                _require_running_execution(execution_job, execution_attempt)
                if parent_job is not None and parent_attempt is not None:
                    _require_running_execution(parent_job, parent_attempt)
                _validate_materialized_replay(current, materialized)
                tool = await self._ensure_tool_run(session, row)
                parent, plan, operation = await self._publication_context(session, row, tool)
                result_asset_id = _deterministic_id("D07ResultAsset", row.id, materialized.sha256)
                transition_intent = await self._transition_intent(
                    session,
                    parent=parent,
                    plan=plan,
                    operation=operation,
                )
                if transition_intent is not None:
                    if materialized.sha256 != transition_intent.expected_result_asset_sha256:
                        raise DemoEditingRepositoryError(
                            "TRANSITION_RESULT_DIGEST_MISMATCH",
                            "transition bytes do not match the bound historical target",
                        )
                    try:
                        validate_result_asset_id(transition_intent, result_asset_id)
                    except OperationLineageError as exc:
                        raise DemoEditingRepositoryError(exc.code, str(exc)) from exc
                result_asset = await session.get(Asset, result_asset_id)
                if result_asset is None:
                    source_asset = await session.get(Asset, tool.input_asset_id)
                    if source_asset is None:
                        raise DemoEditingRepositoryError(
                            "SOURCE_ASSET_UNAVAILABLE", "ToolRun source Asset is unavailable"
                        )
                    result_asset = Asset(
                        id=result_asset_id,
                        owner_user_id=None,
                        asset_role="derived",
                        storage_key=published_storage_key,
                        mime_type=materialized.mime_type,
                        byte_size=len(materialized.content),
                        width=materialized.width,
                        height=materialized.height,
                        sha256=materialized.sha256,
                        synthetic=source_asset.synthetic,
                        is_ai_generated=source_asset.is_ai_generated,
                        is_ai_modified=True,
                        internal_purpose=None,
                        deleted_at=None,
                    )
                    session.add(result_asset)
                else:
                    _validate_published_asset(result_asset, published_storage_key, materialized)
                variant_id = _deterministic_id("D07AssetVariant", row.id, materialized.sha256)
                variant = await session.get(AssetVariant, variant_id)
                if variant is None:
                    variant = AssetVariant(
                        id=variant_id,
                        source_asset_id=tool.input_asset_id,
                        result_asset_id=result_asset.id,
                        variant_type=_variant_type(operation.operation_type),
                    )
                    session.add(variant)
                image_id = _deterministic_id("D07ImageVersion", row.id, materialized.sha256)
                verification_row, verifier_job, verifier_attempt = await self._ensure_verification(
                    session,
                    artifact=row,
                    tool=tool,
                    verification=verification,
                    image_version_id=image_id,
                    output_asset=result_asset,
                )
                image = await session.get(DemoImageVersion, image_id)
                if image is None:
                    image = _authority_row(
                        DemoImageVersion,
                        row_id=image_id,
                        demo_actor_id=row.demo_actor_id,
                        demo_session_id=row.demo_session_id,
                        editing_session_id=plan.editing_session_id,
                        sequence=parent.sequence + 1,
                        parent_version_id=parent.id,
                        source_asset_id=tool.input_asset_id,
                        source_asset_sha256=tool.input_asset_sha256,
                        result_asset_id=result_asset.id,
                        result_asset_sha256=result_asset.sha256,
                        result_asset_variant_id=variant.id,
                        version_kind=_version_kind(operation.operation_type),
                        plan_digest=plan.content_digest,
                        tool_run_digest=tool.content_digest,
                        verifier_digest=verification_row.content_digest,
                    )
                    session.add(image)
                    await session.flush()
                event = _authority_row(
                    DemoEditArtifactEvent,
                    demo_actor_id=row.demo_actor_id,
                    demo_session_id=row.demo_session_id,
                    demo_edit_artifact_id=row.id,
                    sequence=2,
                    event_type="PROMOTED",
                    object_sha256=None,
                    byte_size=None,
                    width=None,
                    height=None,
                    mime_type=None,
                    engine_digest=None,
                    config_digest=None,
                    promoted_asset_id=result_asset.id,
                    promoted_asset_variant_id=variant.id,
                    verification_result_id=verification_row.id,
                    image_version_id=image.id,
                    reason_code=None,
                )
                session.add(event)
                _finish_job(
                    verifier_job,
                    verifier_attempt,
                    status="COMPLETED",
                    result_code="VERIFICATION_PASS",
                )
                _finish_job(
                    execution_job,
                    execution_attempt,
                    status="COMPLETED",
                    result_code="EDIT_EXECUTION_COMPLETED",
                )
                if parent_job is not None and parent_attempt is not None:
                    _finish_job(
                        parent_job,
                        parent_attempt,
                        status="COMPLETED",
                        result_code="IMAGE_VERSION_RESTORED",
                    )
                await session.flush()
                return Promotion(result_asset.id, variant.id, image.id, verification_row.id)

    async def create_transition(
        self,
        *,
        actor_id: str,
        session_id: str,
        source_image_version_id: str,
        target_image_version_id: str,
        transition: str,
    ) -> str:
        del actor_id, session_id, source_image_version_id, target_image_version_id, transition
        raise DemoEditingRepositoryError(
            "TRANSITION_EXECUTION_REQUIRED",
            "restore and rollback require a typed persisted plan and execution Job",
        )

    async def _validate_execution_context(
        self, session: AsyncSession, command: ExecutionCommand
    ) -> None:
        operation = await session.scalar(
            select(DemoEditOperation)
            .where(DemoEditOperation.id == command.operation_id)
            .with_for_update()
        )
        binding = await session.scalar(
            select(DemoJobBinding)
            .where(DemoJobBinding.id == command.execution_job_binding_id)
            .with_for_update()
        )
        attempt = await session.scalar(
            select(JobAttempt)
            .where(JobAttempt.id == command.formal_job_attempt_id)
            .with_for_update()
        )
        job = None
        if binding is not None:
            job = await session.scalar(
                select(Job).where(Job.id == binding.job_id).with_for_update()
            )
        if operation is None or binding is None or job is None or attempt is None:
            raise DemoEditingRepositoryError(
                "EXECUTION_AUTHORITY_UNAVAILABLE", "execution authority is unavailable"
            )
        plan = await session.get(DemoEditPlan, operation.edit_plan_id)
        if (
            plan is None
            or plan.record_kind != "RESULT"
            or operation.demo_actor_id != command.actor_id
            or operation.demo_session_id != command.session_id
            or operation.content_digest != command.operation_digest
            or operation.engine != command.operation.engine.value
            or operation.operation_type != command.operation.operation_type.value
            or operation.parameters != dict(command.operation.parameters)
            or operation.preserve != [item.value for item in command.operation.preserve]
            or operation.expected_effect != dict(command.operation.expected_effect)
            or binding.demo_actor_id != command.actor_id
            or binding.demo_session_id != command.session_id
            or binding.endpoint_operation != "edit_plan.execute"
            or binding.target_type != "EDIT_PLAN"
            or binding.target_id != plan.id
            or attempt.job_id != binding.job_id
            or attempt.attempt != job.attempt_count
            or job.status != "RUNNING"
            or attempt.status != "RUNNING"
        ):
            raise DemoEditingRepositoryError(
                "EXECUTION_AUTHORITY_MISMATCH", "execution authority does not match command"
            )
        if (command.parent_job_id is None) != (command.parent_job_attempt_id is None):
            raise DemoEditingRepositoryError(
                "PARENT_EXECUTION_AUTHORITY_MISMATCH",
                "parent restore Job authority must be a complete pair",
            )
        if command.parent_job_id is not None:
            assert command.parent_job_attempt_id is not None
            target_id = operation.parameters.get("target_image_version_id")
            parent_binding = await session.scalar(
                select(DemoJobBinding)
                .where(DemoJobBinding.job_id == command.parent_job_id)
                .with_for_update()
            )
            parent_job = await session.scalar(
                select(Job).where(Job.id == command.parent_job_id).with_for_update()
            )
            parent_attempt = await session.scalar(
                select(JobAttempt)
                .where(JobAttempt.id == command.parent_job_attempt_id)
                .with_for_update()
            )
            if (
                operation.operation_type
                not in {OperationType.RESTORE.value, OperationType.ROLLBACK.value}
                or not isinstance(target_id, str)
                or parent_binding is None
                or parent_job is None
                or parent_attempt is None
                or parent_binding.demo_actor_id != command.actor_id
                or parent_binding.demo_session_id != command.session_id
                or parent_binding.endpoint_operation != "image_version.restore"
                or parent_binding.target_type != "IMAGE_VERSION"
                or parent_binding.target_id != target_id
                or parent_attempt.job_id != parent_job.id
                or parent_attempt.attempt != parent_job.attempt_count
                or parent_job.status != "RUNNING"
                or parent_attempt.status != "RUNNING"
            ):
                raise DemoEditingRepositoryError(
                    "PARENT_EXECUTION_AUTHORITY_MISMATCH",
                    "parent restore Job authority does not match execution",
                )

    async def _lock_execution_terminal_context(
        self,
        session: AsyncSession,
        artifact: EditArtifact,
        *,
        parent_job_id: str | None,
        parent_job_attempt_id: str | None,
    ) -> tuple[Job, JobAttempt, Job | None, JobAttempt | None]:
        """Lock child/parent Jobs, attempts, then the caller locks the artifact."""
        if (parent_job_id is None) != (parent_job_attempt_id is None):
            raise DemoEditingRepositoryError(
                "PARENT_EXECUTION_AUTHORITY_MISMATCH",
                "parent restore Job authority must be a complete pair",
            )
        binding = await session.get(DemoJobBinding, artifact.execution_job_binding_id)
        if (
            binding is None
            or binding.demo_actor_id != artifact.actor_id
            or binding.demo_session_id != artifact.session_id
            or binding.endpoint_operation != "edit_plan.execute"
            or binding.target_type != "EDIT_PLAN"
        ):
            raise DemoEditingRepositoryError(
                "EXECUTION_AUTHORITY_UNAVAILABLE", "execution Job binding is unavailable"
            )
        job_ids = [binding.job_id]
        attempt_ids = [artifact.formal_job_attempt_id]
        parent_binding = None
        if parent_job_id is not None:
            parent_binding = await session.scalar(
                select(DemoJobBinding).where(DemoJobBinding.job_id == parent_job_id)
            )
            assert parent_job_attempt_id is not None
            job_ids.append(parent_job_id)
            attempt_ids.append(parent_job_attempt_id)
        jobs = {
            row.id: row
            for row in (
                await session.scalars(
                    select(Job).where(Job.id.in_(job_ids)).order_by(Job.id).with_for_update()
                )
            ).all()
        }
        attempts = {
            row.id: row
            for row in (
                await session.scalars(
                    select(JobAttempt)
                    .where(JobAttempt.id.in_(attempt_ids))
                    .order_by(JobAttempt.id)
                    .with_for_update()
                )
            ).all()
        }
        job = jobs.get(binding.job_id)
        attempt = attempts.get(artifact.formal_job_attempt_id)
        if (
            job is None
            or attempt is None
            or attempt.job_id != binding.job_id
            or attempt.attempt != job.attempt_count
        ):
            raise DemoEditingRepositoryError(
                "EXECUTION_AUTHORITY_MISMATCH",
                "execution Job and current attempt do not match artifact authority",
            )
        if parent_job_id is None:
            return job, attempt, None, None
        assert parent_job_attempt_id is not None
        parent_job = jobs.get(parent_job_id)
        parent_attempt = attempts.get(parent_job_attempt_id)
        if (
            parent_binding is None
            or parent_job is None
            or parent_attempt is None
            or parent_binding.demo_actor_id != artifact.actor_id
            or parent_binding.demo_session_id != artifact.session_id
            or parent_binding.endpoint_operation != "image_version.restore"
            or parent_binding.target_type != "IMAGE_VERSION"
            or parent_attempt.job_id != parent_job.id
            or parent_attempt.attempt != parent_job.attempt_count
        ):
            raise DemoEditingRepositoryError(
                "PARENT_EXECUTION_AUTHORITY_MISMATCH",
                "parent restore Job authority does not match execution",
            )
        return job, attempt, parent_job, parent_attempt

    async def _ensure_tool_run(
        self, session: AsyncSession, artifact: DemoEditArtifact
    ) -> DemoToolRun:
        existing = await session.scalar(
            select(DemoToolRun)
            .where(DemoToolRun.demo_edit_artifact_id == artifact.id)
            .with_for_update()
        )
        if existing is not None:
            return existing
        operation = await session.get(DemoEditOperation, artifact.edit_operation_id)
        binding = await session.get(DemoJobBinding, artifact.execution_job_binding_id)
        if operation is None or binding is None:
            raise DemoEditingRepositoryError(
                "TOOL_AUTHORITY_UNAVAILABLE", "ToolRun authority is unavailable"
            )
        plan = await session.get(DemoEditPlan, operation.edit_plan_id)
        if plan is None:
            raise DemoEditingRepositoryError(
                "PLAN_AUTHORITY_UNAVAILABLE", "ToolRun plan authority is unavailable"
            )
        parent = await self._execution_parent(session, plan, operation)
        tool = _authority_row(
            DemoToolRun,
            demo_actor_id=artifact.demo_actor_id,
            demo_session_id=artifact.demo_session_id,
            edit_operation_id=operation.id,
            edit_operation_digest=operation.content_digest,
            demo_job_binding_id=binding.id,
            formal_job_attempt_id=artifact.formal_job_attempt_id,
            demo_edit_artifact_id=artifact.id,
            tool_name=f"demo-{operation.engine.lower()}-{operation.operation_type.lower()}",
            tool_version=artifact.engine_version,
            input_asset_id=parent.result_asset_id,
            input_asset_sha256=parent.result_asset_sha256,
            output_asset_id=None,
            output_asset_sha256=None,
            effect_contract=operation.expected_effect,
            outcome="COMPLETED",
        )
        session.add(tool)
        await session.flush()
        return tool

    async def _ensure_verification(
        self,
        session: AsyncSession,
        *,
        artifact: DemoEditArtifact,
        tool: DemoToolRun,
        verification: EffectVerificationResult,
        image_version_id: str | None,
        output_asset: Asset | None,
    ) -> tuple[DemoVerificationResult, Job, JobAttempt]:
        existing = await session.scalar(
            select(DemoVerificationResult).where(
                DemoVerificationResult.demo_edit_artifact_id == artifact.id
            )
        )
        if existing is not None:
            raise DemoEditingRepositoryError(
                "VERIFICATION_ALREADY_EXISTS", "verification authority already exists"
            )
        verifier_job, verifier_binding, verifier_attempt = await self._create_verifier_job(
            session, artifact=artifact, tool=tool, verification=verification
        )
        reason_codes = sorted(
            {
                code
                for category in verification.categories
                for code in category.reason_codes
                if code != "VERIFIED"
            }
        )
        metrics: dict[str, Any] = {
            "categories": [item.canonical_payload() for item in verification.categories],
            "identity_claim_scope": verification.identity_claim_scope,
            "publishable": verification.publishable,
            "request_digest": verification.request_digest,
            "result_digest": verification.result_digest,
        }
        row = _authority_row(
            DemoVerificationResult,
            demo_actor_id=artifact.demo_actor_id,
            demo_session_id=artifact.demo_session_id,
            tool_run_id=tool.id,
            image_version_id=image_version_id,
            demo_job_binding_id=verifier_binding.id,
            demo_edit_artifact_id=artifact.id,
            formal_job_attempt_id=verifier_attempt.id,
            output_asset_id=None if output_asset is None else output_asset.id,
            output_asset_sha256=None if output_asset is None else output_asset.sha256,
            verifier_version=VERIFIER_VERSION,
            config_digest=verification.policy_digest,
            metrics=metrics,
            thresholds={"policy_digest": verification.policy_digest},
            outcome=verification.status.value,
            reason_codes=reason_codes,
        )
        session.add(row)
        await session.flush()
        return row, verifier_job, verifier_attempt

    async def _create_verifier_job(
        self,
        session: AsyncSession,
        *,
        artifact: DemoEditArtifact,
        tool: DemoToolRun,
        verification: EffectVerificationResult,
    ) -> tuple[Job, DemoJobBinding, JobAttempt]:
        key_hash = hashlib.sha256(f"tool.verify/{tool.id}".encode()).hexdigest()
        request_digest = semantic_request_digest(
            {
                "tool_run_digest": tool.content_digest,
                "verification_request_digest": verification.request_digest,
            }
        )
        job_id = new_id()
        now = utcnow()
        job = Job(
            id=job_id,
            job_type="demo_p3_p7.tool.verify",
            status="PENDING",
            idempotency_key_hash=_formal_job_key_hash(
                artifact.demo_actor_id, "tool.verify", key_hash
            ),
            request_id=f"d07-verify-{tool.id}",
            payload={},
            owner_user_id=None,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )
        payload: dict[str, Any] = {
            "demo_actor_id": artifact.demo_actor_id,
            "demo_session_id": artifact.demo_session_id,
            "endpoint_operation": "tool.verify",
            "idempotency_key_hash": key_hash,
            "job_id": job.id,
            "request_digest": request_digest,
            "target_id": tool.id,
            "target_type": "TOOL_RUN",
        }
        binding = _authority_row(
            DemoJobBinding,
            schema_version=DEMO_JOB_BINDING_SCHEMA,
            **payload,
        )
        # The frozen DemoJobBinding trigger accepts only an untouched PENDING
        # formal Job envelope.  Establish that authority first, then claim the
        # verifier work through the same legal PENDING -> RUNNING transition
        # used by the other Demo workers.
        session.add(job)
        await session.flush()
        session.add(binding)
        await session.flush()
        attempt = JobAttempt(
            id=new_id(),
            job_id=job.id,
            attempt=1,
            status="RUNNING",
            started_at=now,
        )
        session.add(attempt)
        job.status = "RUNNING"
        job.attempt_count = 1
        job.updated_at = now
        await session.flush()
        return job, binding, attempt

    async def _publication_context(
        self, session: AsyncSession, artifact: DemoEditArtifact, tool: DemoToolRun
    ) -> tuple[DemoImageVersion, DemoEditPlan, DemoEditOperation]:
        operation = await session.get(DemoEditOperation, artifact.edit_operation_id)
        if operation is None:
            raise DemoEditingRepositoryError(
                "OPERATION_AUTHORITY_UNAVAILABLE", "edit operation authority is unavailable"
            )
        plan = await session.get(DemoEditPlan, operation.edit_plan_id)
        if plan is None:
            raise DemoEditingRepositoryError(
                "PLAN_AUTHORITY_UNAVAILABLE", "edit plan authority is unavailable"
            )
        parent = await self._execution_parent(session, plan, operation)
        if (
            parent.result_asset_id != tool.input_asset_id
            or parent.result_asset_sha256 != tool.input_asset_sha256
        ):
            raise DemoEditingRepositoryError(
                "TOOL_INPUT_MISMATCH", "ToolRun input differs from ImageVersion authority"
            )
        return parent, plan, operation

    async def _execution_parent(
        self, session: AsyncSession, plan: DemoEditPlan, operation: DemoEditOperation
    ) -> DemoImageVersion:
        if operation.operation_index == 0:
            parent = await session.scalar(
                select(DemoImageVersion)
                .where(DemoImageVersion.id == plan.input_image_version_id)
                .with_for_update()
            )
        else:
            previous_operation = await session.scalar(
                select(DemoEditOperation).where(
                    DemoEditOperation.edit_plan_id == plan.id,
                    DemoEditOperation.operation_index == operation.operation_index - 1,
                )
            )
            parent = None
            if previous_operation is not None:
                parent = await session.scalar(
                    select(DemoImageVersion)
                    .join(
                        DemoToolRun,
                        DemoToolRun.content_digest == DemoImageVersion.tool_run_digest,
                    )
                    .where(
                        DemoImageVersion.plan_digest == plan.content_digest,
                        DemoToolRun.edit_operation_id == previous_operation.id,
                    )
                    .with_for_update(of=DemoImageVersion)
                )
        if parent is None:
            raise DemoEditingRepositoryError(
                "EXECUTION_PARENT_UNAVAILABLE", "operation input ImageVersion is unavailable"
            )
        return parent

    async def _transition_intent(
        self,
        session: AsyncSession,
        *,
        parent: DemoImageVersion,
        plan: DemoEditPlan,
        operation: DemoEditOperation,
    ) -> TransitionIntent | None:
        if operation.operation_type not in {
            OperationType.RESTORE.value,
            OperationType.ROLLBACK.value,
        }:
            return None
        target_id = operation.parameters.get("target_image_version_id")
        target_digest = operation.parameters.get("target_image_version_digest")
        if not isinstance(target_id, str) or not isinstance(target_digest, str):
            raise DemoEditingRepositoryError(
                "TRANSITION_TARGET_INVALID", "transition target binding is invalid"
            )
        rows = tuple(
            (
                await session.scalars(
                    select(DemoImageVersion)
                    .where(DemoImageVersion.editing_session_id == plan.editing_session_id)
                    .order_by(DemoImageVersion.sequence, DemoImageVersion.id)
                    .with_for_update()
                )
            ).all()
        )
        history = tuple(_image_version_reference(row) for row in rows)
        current = _image_version_reference(parent)
        try:
            if operation.operation_type == OperationType.RESTORE.value:
                return plan_restore_transition(current, history, target_id, target_digest)
            return plan_rollback_transition(current, history, target_id, target_digest)
        except OperationLineageError as exc:
            raise DemoEditingRepositoryError(exc.code, str(exc)) from exc

    async def _artifact_dto(self, session: AsyncSession, row: DemoEditArtifact) -> EditArtifact:
        events = tuple(
            (
                await session.scalars(
                    select(DemoEditArtifactEvent)
                    .where(DemoEditArtifactEvent.demo_edit_artifact_id == row.id)
                    .order_by(DemoEditArtifactEvent.sequence)
                )
            ).all()
        )
        latest = events[-1] if events else None
        state = ArtifactState.RESERVED if latest is None else ArtifactState(latest.event_type)
        materialized = next((item for item in events if item.event_type == "MATERIALIZED"), None)
        evidence = None
        if materialized is not None:
            if any(
                value is None
                for value in (
                    materialized.object_sha256,
                    materialized.byte_size,
                    materialized.width,
                    materialized.height,
                    materialized.mime_type,
                    materialized.engine_digest,
                    materialized.config_digest,
                )
            ):
                raise DemoEditingRepositoryError(
                    "MATERIALIZATION_AUTHORITY_CORRUPT", "materialization authority is incomplete"
                )
            evidence = MaterializationEvidence(
                sha256=cast(str, materialized.object_sha256),
                byte_size=cast(int, materialized.byte_size),
                width=cast(int, materialized.width),
                height=cast(int, materialized.height),
                mime_type=cast(str, materialized.mime_type),
                engine_digest=cast(str, materialized.engine_digest),
                config_digest=cast(str, materialized.config_digest),
            )
        return EditArtifact(
            artifact_id=row.id,
            actor_id=row.demo_actor_id,
            session_id=row.demo_session_id,
            operation_id=row.edit_operation_id,
            execution_job_binding_id=row.execution_job_binding_id,
            formal_job_attempt_id=row.formal_job_attempt_id,
            private_object_key=row.private_object_key,
            state=state,
            materialized=evidence,
        )

    async def _lock_artifact(
        self, session: AsyncSession, artifact: EditArtifact
    ) -> DemoEditArtifact:
        row = await session.scalar(
            select(DemoEditArtifact)
            .where(DemoEditArtifact.id == artifact.artifact_id)
            .with_for_update()
        )
        if row is None:
            raise DemoEditingRepositoryError(
                "EDIT_ARTIFACT_UNAVAILABLE", "edit artifact authority is unavailable"
            )
        if (
            row.demo_actor_id != artifact.actor_id
            or row.demo_session_id != artifact.session_id
            or row.edit_operation_id != artifact.operation_id
            or row.execution_job_binding_id != artifact.execution_job_binding_id
            or row.formal_job_attempt_id != artifact.formal_job_attempt_id
            or row.private_object_key != artifact.private_object_key
        ):
            raise DemoEditingRepositoryError(
                "EDIT_ARTIFACT_MISMATCH", "edit artifact authority does not match"
            )
        return row

    async def _promotion_for_artifact(self, session: AsyncSession, artifact_id: str) -> Promotion:
        event = await session.scalar(
            select(DemoEditArtifactEvent).where(
                DemoEditArtifactEvent.demo_edit_artifact_id == artifact_id,
                DemoEditArtifactEvent.event_type == "PROMOTED",
            )
        )
        if (
            event is None
            or event.promoted_asset_id is None
            or event.promoted_asset_variant_id is None
            or event.image_version_id is None
            or event.verification_result_id is None
        ):
            raise DemoEditingRepositoryError(
                "PROMOTION_AUTHORITY_CORRUPT", "promotion authority is incomplete"
            )
        return Promotion(
            event.promoted_asset_id,
            event.promoted_asset_variant_id,
            event.image_version_id,
            event.verification_result_id,
        )

    async def _lock_editing_session(
        self,
        session: AsyncSession,
        *,
        actor_id: str,
        session_id: str,
        editing_session_id: str,
    ) -> DemoEditingSession:
        row = await session.scalar(
            select(DemoEditingSession)
            .where(
                DemoEditingSession.id == editing_session_id,
                DemoEditingSession.demo_actor_id == actor_id,
                DemoEditingSession.demo_session_id == session_id,
                DemoEditingSession.closed_at.is_(None),
                DemoEditingSession.tombstoned_at.is_(None),
            )
            .with_for_update()
        )
        if row is None:
            raise DemoEditingRepositoryError(
                "EDITING_SESSION_UNAVAILABLE", "editing Session authority is unavailable"
            )
        return row

    async def _require_owner_context(
        self, session: AsyncSession, *, actor_id: str, session_id: str
    ) -> None:
        actor = await session.get(DemoActor, actor_id)
        demo_session = await session.get(DemoSession, session_id)
        if (
            actor is None
            or actor.tombstoned_at is not None
            or demo_session is None
            or demo_session.demo_actor_id != actor_id
        ):
            raise DemoEditingRepositoryError(
                "OWNER_CONTEXT_UNAVAILABLE", "Demo owner context is unavailable"
            )

    @staticmethod
    async def _require_profile_digest(
        session: AsyncSession,
        model: type[DemoDesiredDeltaProfile]
        | type[DemoStyleProfile]
        | type[DemoIdentityConstraints],
        digest: str,
        actor_id: str,
    ) -> None:
        row = await session.scalar(
            select(model).where(model.content_digest == digest, model.demo_actor_id == actor_id)
        )
        if row is None:
            raise DemoEditingRepositoryError(
                "PROFILE_AUTHORITY_UNAVAILABLE", "editing profile authority is unavailable"
            )

    @staticmethod
    def _validate_editing_session(row: DemoEditingSession, fields: Mapping[str, Any]) -> None:
        if any(getattr(row, key) != value for key, value in fields.items()):
            raise DemoEditingRepositoryError(
                "EDITING_SESSION_REPLAY_MISMATCH", "editing Session replay is inconsistent"
            )

    @staticmethod
    def _validate_artifact_row(
        row: DemoEditArtifact, command: ExecutionCommand, object_key: str
    ) -> None:
        if (
            row.demo_actor_id != command.actor_id
            or row.demo_session_id != command.session_id
            or row.edit_operation_id != command.operation_id
            or row.execution_job_binding_id != command.execution_job_binding_id
            or row.formal_job_attempt_id != command.formal_job_attempt_id
            or row.private_object_key != object_key
            or row.engine != command.operation.engine.value
            or row.engine_version != command.engine_version
            or row.expected_engine_digest != command.engine_digest
            or row.expected_config_digest != command.config_digest
        ):
            raise DemoEditingRepositoryError(
                "EDIT_ARTIFACT_REPLAY_MISMATCH", "edit artifact replay is inconsistent"
            )


def _authority_row[AuthorityT](
    model: type[AuthorityT],
    /,
    *,
    row_id: str | None = None,
    schema_version: str | None = None,
    created_at: datetime | None = None,
    **fields: Any,
) -> AuthorityT:
    authority_schema = schema_version or f"mirror.demo/{model.__name__}/v1"
    authority_time = created_at or utcnow()
    row = cast(Any, model)(
        id=row_id or new_id(),
        schema_version=authority_schema,
        canonical_payload={},
        content_digest="0" * 64,
        created_at=authority_time,
        **fields,
    )
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:
        if column.name in _NON_AUTHORITY_COLUMNS:
            continue
        value = getattr(row, column.name)
        payload[column.name] = _canonical_value(value)
    row.canonical_payload = payload
    row.content_digest = hashlib.sha256(
        authority_schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()
    return cast(AuthorityT, row)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    return value


def _validate_materialized_replay(artifact: EditArtifact, materialized: MaterializedObject) -> None:
    evidence = artifact.materialized
    if (
        artifact.state is not ArtifactState.MATERIALIZED
        or evidence is None
        or evidence.sha256 != materialized.sha256
        or evidence.byte_size != len(materialized.content)
        or evidence.width != materialized.width
        or evidence.height != materialized.height
        or evidence.mime_type != materialized.mime_type
        or evidence.engine_digest != materialized.engine_digest
        or evidence.config_digest != materialized.config_digest
    ):
        raise DemoEditingRepositoryError(
            "MATERIALIZATION_REPLAY_MISMATCH", "materialization replay is inconsistent"
        )


def _validate_published_asset(
    asset: Asset, storage_key: str, materialized: MaterializedObject
) -> None:
    if (
        asset.storage_key != storage_key
        or asset.sha256 != materialized.sha256
        or asset.byte_size != len(materialized.content)
        or asset.width != materialized.width
        or asset.height != materialized.height
        or asset.mime_type != materialized.mime_type
        or asset.asset_role != "derived"
    ):
        raise DemoEditingRepositoryError(
            "PUBLISHED_ASSET_CONFLICT", "published Asset authority conflicts"
        )


def _image_version_reference(row: DemoImageVersion) -> ImageVersionReference:
    return ImageVersionReference(
        image_version_id=row.id,
        image_version_digest=row.content_digest,
        actor_id=row.demo_actor_id,
        demo_session_id=row.demo_session_id,
        editing_session_id=row.editing_session_id,
        result_asset_id=row.result_asset_id,
        result_asset_sha256=row.result_asset_sha256,
        sequence=row.sequence,
        parent_image_version_id=row.parent_version_id,
        quarantined=row.version_kind == "QUARANTINED",
    )


def _finish_job(job: Job, attempt: JobAttempt, *, status: str, result_code: str) -> None:
    now = utcnow()
    attempt.status = status
    attempt.result_code = result_code
    attempt.error_code = None
    attempt.finished_at = now
    job.status = status
    job.finalized_at = now
    job.result_code = result_code
    job.updated_at = now


def _require_running_execution(job: Job, attempt: JobAttempt) -> None:
    if job.status != "RUNNING" or attempt.status != "RUNNING":
        raise DemoEditingRepositoryError(
            "EXECUTION_NOT_RUNNING",
            "execution Job is no longer eligible for publication",
        )
    if job.finalized_at is not None or attempt.finished_at is not None:
        raise DemoEditingRepositoryError(
            "EXECUTION_AUTHORITY_MISMATCH",
            "RUNNING execution authority already has terminal timestamps",
        )


def _validate_terminal_execution(
    artifact_state: ArtifactState, job: Job, attempt: JobAttempt
) -> None:
    expected = {
        ArtifactState.PROMOTED: "COMPLETED",
        ArtifactState.REJECTED: "REJECTED",
        ArtifactState.CANCELLED: "CANCELLED",
    }.get(artifact_state)
    if expected is None:
        if job.status not in {"COMPLETED", "REJECTED", "FAILED", "CANCELLED"}:
            raise DemoEditingRepositoryError(
                "TERMINAL_EXECUTION_MISMATCH",
                "terminal artifact has a non-terminal execution Job",
            )
        return
    if (
        job.status != expected
        or attempt.status != expected
        or job.finalized_at is None
        or attempt.finished_at is None
    ):
        raise DemoEditingRepositoryError(
            "TERMINAL_EXECUTION_MISMATCH",
            "terminal artifact and execution Job authority disagree",
        )


def _formal_job_key_hash(actor_id: str, operation: str, key_hash: str) -> str:
    preimage = f"mirror.demo/JobIdempotency/v1\n{actor_id}\n{operation}\n{key_hash}"
    return hashlib.sha256(preimage.encode()).hexdigest()


def _deterministic_id(kind: str, artifact_id: str, digest: str) -> str:
    return hashlib.sha256(f"mirror.demo/{kind}/v1\n{artifact_id}\n{digest}".encode()).hexdigest()[
        :32
    ]


def _variant_type(operation_type: str) -> str:
    value = f"demo_p3_p7_{operation_type.lower()}_v1"
    if len(value) > 32:
        raise DemoEditingRepositoryError(
            "VARIANT_TYPE_INVALID", "published AssetVariant type is invalid"
        )
    return value


def _version_kind(operation_type: str) -> str:
    if operation_type == OperationType.RESTORE.value:
        return "RESTORED"
    if operation_type == OperationType.ROLLBACK.value:
        return "ROLLED_BACK"
    return "EDITED"


def _raise_unreachable(message: str) -> NoReturn:
    raise DemoEditingRepositoryError("UNREACHABLE", message)


__all__ = ["DemoEditingRepositoryError", "SqlAlchemyDemoEditingRepository"]
