"""PostgreSQL-authoritative D07 public command boundary.

This module deliberately owns command admission only.  It never loads image
bytes, calls a worker adapter, or marks a Job terminal: those actions belong
to the D07 runtime/repository boundary.  Every create path is a single
database transaction containing its immutable authority and a PENDING Job
with an immutable :class:`DemoJobBinding`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_d08_geometry_authority import (
    GeometryAuthorityResolutionError,
    require_geometry_plan_admission,
)
from mirror_api.demo_edit_planner import TypedPlanInput, plan_operation
from mirror_api.demo_editing_repository import (
    DemoEditingRepositoryError,
    require_d02_source_authority_if_applicable,
)
from mirror_api.demo_idempotency import (
    DemoIdempotencyPayloadConflict,
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DemoActor,
    DemoDesiredDeltaProfile,
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
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
    plan_restore_transition,
)
from mirror_api.demo_tool_registry import (
    TOOL_REGISTRY_VERSION,
    DemoToolRegistryError,
    require_execution_mode,
    resolve_persisted_tool,
    resolve_tool,
)
from mirror_api.models import Asset, Job, new_id, utcnow

EDITING_CONTRACT_VERSION = "demo-editing-product-contract-v1"
PLANNER_VERSION = "demo-edit-planner-v1"
DEMO_JOB_BINDING_SCHEMA = "mirror.demo/DemoJobBinding/v1"
_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REQUEST_ID = re.compile(r"^[^\r\n\x00]{8,128}$")


class DemoEditingCommandError(RuntimeError):
    """Base fail-closed error for the D07 public command boundary."""


class DemoEditingCommandInputError(DemoEditingCommandError):
    pass


class DemoEditingCommandUnavailable(DemoEditingCommandError):
    pass


class DemoEditingCommandAuthorityCorruption(DemoEditingCommandError):
    pass


@dataclass(frozen=True)
class CreateDemoEditingSession:
    demo_actor_id: str
    demo_session_id: str
    idempotency_key: str
    request_id: str
    source_asset_id: str | None = None
    source_image_version_id: str | None = None

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.demo_session_id, "demo_session_id")
        if (self.source_asset_id is None) == (self.source_image_version_id is None):
            raise DemoEditingCommandInputError("exactly one source selector is required")
        if self.source_asset_id is not None:
            _require_id(self.source_asset_id, "source_asset_id")
        if self.source_image_version_id is not None:
            _require_id(self.source_image_version_id, "source_image_version_id")
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class CreateDemoEditPlan:
    demo_actor_id: str
    editing_session_id: str
    operation: OperationType
    value_ppm: int
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        for value, name in (
            (self.demo_actor_id, "demo_actor_id"),
            (self.editing_session_id, "editing_session_id"),
        ):
            _require_id(value, name)
        if not isinstance(self.operation, OperationType) or type(self.value_ppm) is not int:
            raise DemoEditingCommandInputError("operation/value_ppm is invalid")
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class ExecuteDemoEditPlan:
    demo_actor_id: str
    edit_plan_id: str
    execution_mode: Literal["DETERMINISTIC_RASTER", "GEOMETRY", "MAKEUP", "GENERATIVE"]
    expected_plan_digest: str
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        for value, name in (
            (self.demo_actor_id, "demo_actor_id"),
            (self.edit_plan_id, "edit_plan_id"),
        ):
            _require_id(value, name)
        _require_digest(self.expected_plan_digest, "expected_plan_digest")
        if self.execution_mode not in {"DETERMINISTIC_RASTER", "GEOMETRY", "MAKEUP", "GENERATIVE"}:
            raise DemoEditingCommandInputError("execution_mode is unsupported")
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class RestoreDemoImageVersion:
    demo_actor_id: str
    target_image_version_id: str
    expected_current_image_version_id: str
    expected_current_image_version_digest: str
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        for value, name in (
            (self.demo_actor_id, "demo_actor_id"),
            (self.target_image_version_id, "target_image_version_id"),
            (self.expected_current_image_version_id, "expected_current_image_version_id"),
        ):
            _require_id(value, name)
        _require_digest(
            self.expected_current_image_version_digest, "expected_current_image_version_digest"
        )
        idempotency_key_hash(self.idempotency_key)
        _require_request_id(self.request_id)


@dataclass(frozen=True)
class DemoEditingCommandAccepted:
    job_id: str
    target_id: str
    request_id: str
    replayed: bool


@dataclass(frozen=True)
class DemoEditingPendingJob:
    demo_actor_id: str
    demo_session_id: str
    job_id: str
    endpoint_operation: str
    target_id: str
    request_id: str


@dataclass(frozen=True)
class DemoOwnedToolRun:
    tool_run_id: str
    tool_name: str
    job_id: str
    job_status: str
    output_digest: str | None


class DemoEditingCommandService:
    """Admit D07 commands through PostgreSQL authority only."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._now = now

    async def create_editing_session(
        self, command: CreateDemoEditingSession
    ) -> DemoEditingCommandAccepted:
        command.validate()
        operation = "editing_session.create"
        request = {
            "session_id": command.demo_session_id,
            "source_asset_id": command.source_asset_id,
            "source_image_version_id": command.source_image_version_id,
        }
        return await self._create_or_replay(
            command.demo_actor_id,
            operation,
            command.idempotency_key,
            request,
            lambda s, h, d: self._create_editing_session(s, command, h, d),
            command.request_id,
        )

    async def create_edit_plan(self, command: CreateDemoEditPlan) -> DemoEditingCommandAccepted:
        command.validate()
        operation = "edit_plan.create"
        request = {
            "editing_session_id": command.editing_session_id,
            "operation": command.operation.value,
            "value_ppm": command.value_ppm,
        }
        return await self._create_or_replay(
            command.demo_actor_id,
            operation,
            command.idempotency_key,
            request,
            lambda s, h, d: self._create_plan(s, command, h, d),
            command.request_id,
        )

    async def execute_edit_plan(self, command: ExecuteDemoEditPlan) -> DemoEditingCommandAccepted:
        command.validate()
        operation = "edit_plan.execute"
        request = {
            "edit_plan_id": command.edit_plan_id,
            "execution_mode": command.execution_mode,
            "expected_plan_digest": command.expected_plan_digest,
        }
        return await self._create_or_replay(
            command.demo_actor_id,
            operation,
            command.idempotency_key,
            request,
            lambda s, h, d: self._execute_plan(s, command, h, d),
            command.request_id,
        )

    async def restore_image_version(
        self, command: RestoreDemoImageVersion
    ) -> DemoEditingCommandAccepted:
        command.validate()
        operation = "image_version.restore"
        request = {
            "target_image_version_id": command.target_image_version_id,
            "expected_current_image_version_id": command.expected_current_image_version_id,
            "expected_current_image_version_digest": command.expected_current_image_version_digest,
        }
        return await self._create_or_replay(
            command.demo_actor_id,
            operation,
            command.idempotency_key,
            request,
            lambda s, h, d: self._restore(s, command, h, d),
            command.request_id,
        )

    async def get_tool_run(self, *, demo_actor_id: str, tool_run_id: str) -> DemoOwnedToolRun:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(tool_run_id, "tool_run_id")
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(DemoToolRun, DemoVerificationResult, DemoJobBinding, Job)
                    .join(
                        DemoVerificationResult,
                        DemoVerificationResult.tool_run_id == DemoToolRun.id,
                    )
                    .join(
                        DemoJobBinding,
                        DemoJobBinding.id == DemoToolRun.demo_job_binding_id,
                    )
                    .join(Job, Job.id == DemoJobBinding.job_id)
                    .where(
                        DemoToolRun.id == tool_run_id,
                        DemoToolRun.demo_actor_id == demo_actor_id,
                        DemoJobBinding.endpoint_operation == "edit_plan.execute",
                    )
                )
            ).one_or_none()
            if row is None:
                raise DemoEditingCommandUnavailable("ToolRun is unavailable")
            tool, verification, binding, job = row
            if binding.demo_session_id != tool.demo_session_id:
                raise DemoEditingCommandAuthorityCorruption(
                    "ToolRun Job binding ownership is invalid"
                )
            return DemoOwnedToolRun(
                tool.id,
                tool.tool_name,
                job.id,
                job.status,
                verification.output_asset_sha256,
            )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[DemoEditingPendingJob, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise DemoEditingCommandInputError("reconciliation limit is invalid")
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(DemoJobBinding, Job)
                    .join(Job, Job.id == DemoJobBinding.job_id)
                    .where(
                        DemoJobBinding.endpoint_operation.in_(
                            (
                                "editing_session.create",
                                "edit_plan.create",
                                "edit_plan.execute",
                                "image_version.restore",
                            )
                        ),
                        or_(
                            and_(Job.status == "PENDING", Job.attempt_count == 0),
                            and_(
                                Job.status == "RUNNING",
                                Job.lease_expires_at.is_not(None),
                                Job.lease_expires_at <= self._normalized_now(),
                            ),
                        ),
                    )
                    .order_by(Job.created_at, Job.id)
                    .limit(limit)
                )
            ).all()
            return tuple(
                DemoEditingPendingJob(
                    binding.demo_actor_id,
                    cast(str, binding.demo_session_id),
                    job.id,
                    binding.endpoint_operation,
                    binding.target_id,
                    job.request_id,
                )
                for binding, job in rows
                if binding.demo_session_id is not None
            )

    async def _create_or_replay(
        self,
        actor_id: str,
        endpoint: str,
        key: str,
        request: Mapping[str, Any],
        creator: Callable[[AsyncSession, str, str], Any],
        request_id: str,
    ) -> DemoEditingCommandAccepted:
        key_hash = idempotency_key_hash(key)
        digest = semantic_request_digest(request)
        async with self._sessions() as session:
            async with session.begin():
                winner = await session.scalar(
                    select(DemoJobBinding).where(
                        DemoJobBinding.demo_actor_id == actor_id,
                        DemoJobBinding.endpoint_operation == endpoint,
                        DemoJobBinding.idempotency_key_hash == key_hash,
                    )
                )
                if winner is not None:
                    if winner.request_digest != digest:
                        raise DemoIdempotencyPayloadConflict()
                    job = await session.get(Job, winner.job_id)
                    if job is None:
                        raise DemoEditingCommandAuthorityCorruption("idempotency winner is invalid")
                    _validate_winner(
                        winner,
                        job,
                        actor_id=actor_id,
                        endpoint=endpoint,
                        key_hash=key_hash,
                        request_digest=digest,
                    )
                    return DemoEditingCommandAccepted(
                        job.id, winner.target_id, job.request_id, True
                    )
                try:
                    async with session.begin_nested():
                        job_id = new_id()
                        response_target_id, binding_target_id = await creator(
                            session, job_id, digest
                        )
                        await self._insert_job_binding(
                            session,
                            job_id,
                            actor_id,
                            endpoint,
                            binding_target_id,
                            key_hash,
                            digest,
                            request_id,
                        )
                except IntegrityError as exc:
                    winner = await session.scalar(
                        select(DemoJobBinding).where(
                            DemoJobBinding.demo_actor_id == actor_id,
                            DemoJobBinding.endpoint_operation == endpoint,
                            DemoJobBinding.idempotency_key_hash == key_hash,
                        )
                    )
                    if winner is None:
                        raise DemoEditingCommandAuthorityCorruption(
                            "idempotency conflict has no winner"
                        ) from exc
                    if winner.request_digest != digest:
                        raise DemoIdempotencyPayloadConflict() from exc
                    job = await session.get(Job, winner.job_id)
                    if job is None:
                        raise DemoEditingCommandAuthorityCorruption(
                            "idempotency winner Job is unavailable"
                        ) from exc
                    _validate_winner(
                        winner,
                        job,
                        actor_id=actor_id,
                        endpoint=endpoint,
                        key_hash=key_hash,
                        request_digest=digest,
                    )
                    return DemoEditingCommandAccepted(
                        winner.job_id, winner.target_id, job.request_id, True
                    )
                return DemoEditingCommandAccepted(job_id, response_target_id, request_id, False)

    async def _create_editing_session(
        self, session: AsyncSession, c: CreateDemoEditingSession, _: str, request_digest: str
    ) -> tuple[str, str]:
        demo_session = await self._lock_context(session, c.demo_actor_id, c.demo_session_id)
        source = await self._source_asset(session, c)
        desired, style, persistent, override = await self._profiles(
            session, c.demo_actor_id, c.demo_session_id
        )
        fields = {
            "demo_actor_id": c.demo_actor_id,
            "demo_session_id": c.demo_session_id,
            "source_asset_id": source.id,
            "source_asset_sha256": source.sha256,
            "desired_delta_profile_digest": desired.content_digest,
            "style_profile_digest": style.content_digest,
            "identity_constraints_digest": persistent.content_digest,
            "context_digest": _digest(
                {
                    "contract_version": EDITING_CONTRACT_VERSION,
                    "context_seed": demo_session.context_seed,
                    "desired": desired.content_digest,
                    "source_asset_sha256": source.sha256,
                    "style": style.content_digest,
                    "constraints": persistent.content_digest,
                    "session_override": None if override is None else override.content_digest,
                }
            ),
            "instruction_digest": request_digest,
            "tool_registry_version": TOOL_REGISTRY_VERSION,
            "closed_at": None,
            "tombstoned_at": None,
        }
        row = _authority(DemoEditingSession, **fields)
        session.add(row)
        await session.flush()
        return row.id, row.id

    async def _create_plan(
        self, session: AsyncSession, c: CreateDemoEditPlan, _: str, request_digest: str
    ) -> tuple[str, str]:
        editing = await self._editing(session, c.demo_actor_id, c.editing_session_id)
        demo_session_id = editing.demo_session_id
        image = await session.scalar(
            select(DemoImageVersion)
            .where(
                DemoImageVersion.editing_session_id == editing.id,
                DemoImageVersion.demo_actor_id == c.demo_actor_id,
                DemoImageVersion.demo_session_id == demo_session_id,
            )
            .order_by(DemoImageVersion.sequence.desc())
            .limit(1)
            .with_for_update()
        )
        if image is None:
            raise DemoEditingCommandUnavailable("editing Session has no published ImageVersion")
        desired, _style, persistent, override = await self._profiles(
            session, c.demo_actor_id, demo_session_id
        )
        spec = plan_operation(
            TypedPlanInput(
                c.operation,
                c.value_ppm,
                _integer_deltas(desired.dimensions),
                _locks(persistent.locks),
                {} if override is None else _locks(override.locks),
                tuple(
                    OperationType(item)
                    for item in sorted(
                        {
                            *persistent.prohibited_operations,
                            *([] if override is None else override.prohibited_operations),
                        }
                    )
                ),
            )
        )
        if spec.engine is OperationEngine.GEOMETRY:
            try:
                await require_geometry_plan_admission(
                    session,
                    editing_session_id=editing.id,
                    image_version_id=image.id,
                    operation=spec,
                )
            except GeometryAuthorityResolutionError as exc:
                raise DemoEditingCommandUnavailable(
                    "geometry plan authority is unavailable"
                ) from exc
        result_id = await self._persist_plan(
            session, c.demo_actor_id, demo_session_id, editing, image, (spec,), request_digest
        )
        return result_id, result_id

    async def _execute_plan(
        self, session: AsyncSession, c: ExecuteDemoEditPlan, _: str, __: str
    ) -> tuple[str, str]:
        plan = await session.scalar(
            select(DemoEditPlan)
            .where(
                DemoEditPlan.id == c.edit_plan_id,
                DemoEditPlan.demo_actor_id == c.demo_actor_id,
                DemoEditPlan.record_kind == "RESULT",
            )
            .with_for_update()
        )
        if plan is None or plan.content_digest != c.expected_plan_digest:
            raise DemoEditingCommandUnavailable("EditPlan is unavailable or stale")
        operations = (
            await session.scalars(
                select(DemoEditOperation)
                .where(DemoEditOperation.edit_plan_id == plan.id)
                .order_by(DemoEditOperation.operation_index)
            )
        ).all()
        if len(operations) != 1 or operations[0].operation_index != 0:
            raise DemoEditingCommandAuthorityCorruption(
                "result plan does not contain one canonical registered operation"
            )
        try:
            descriptor = resolve_persisted_tool(operations[0].engine, operations[0].operation_type)
            require_execution_mode(descriptor, c.execution_mode)
        except DemoToolRegistryError as exc:
            if exc.code == "EXECUTION_MODE_MISMATCH":
                raise DemoEditingCommandInputError(
                    "execution_mode does not match registered tool"
                ) from exc
            raise DemoEditingCommandAuthorityCorruption(
                "persisted plan does not match tool registry"
            ) from exc
        return plan.id, plan.id

    async def _restore(
        self, session: AsyncSession, c: RestoreDemoImageVersion, job_id: str, request_digest: str
    ) -> tuple[str, str]:
        target = await session.scalar(
            select(DemoImageVersion).where(
                DemoImageVersion.id == c.target_image_version_id,
                DemoImageVersion.demo_actor_id == c.demo_actor_id,
            )
        )
        if target is None:
            raise DemoEditingCommandUnavailable("restore history is unavailable or stale")
        current = await session.scalar(
            select(DemoImageVersion)
            .where(
                DemoImageVersion.demo_actor_id == c.demo_actor_id,
                DemoImageVersion.demo_session_id == target.demo_session_id,
                DemoImageVersion.editing_session_id == target.editing_session_id,
            )
            .order_by(DemoImageVersion.sequence.desc())
            .limit(1)
            .with_for_update()
        )
        if (
            current is None
            or current.id != c.expected_current_image_version_id
            or current.content_digest != c.expected_current_image_version_digest
            or target.editing_session_id != current.editing_session_id
        ):
            raise DemoEditingCommandUnavailable("restore history is unavailable or stale")
        history = (
            await session.scalars(
                select(DemoImageVersion)
                .where(DemoImageVersion.editing_session_id == current.editing_session_id)
                .order_by(DemoImageVersion.sequence, DemoImageVersion.id)
            )
        ).all()
        plan_restore_transition(
            _version_ref(current),
            tuple(_version_ref(item) for item in history),
            target.id,
            target.content_digest,
        )
        editing = await self._editing(session, c.demo_actor_id, current.editing_session_id)
        spec = OperationSpec(
            OperationEngine.RASTER,
            OperationType.RESTORE,
            {
                "target_image_version_id": target.id,
                "target_image_version_digest": target.content_digest,
            },
            (PreserveKey.TARGET_VERSION_BYTES,),
            {
                "effect_type": "RESTORE",
                "target_region": "VERSION_CONTENT",
                "target_image_version_digest": target.content_digest,
            },
        )
        # The transition authority is checked above; this typed operation is worker input.
        await self._persist_plan(
            session,
            c.demo_actor_id,
            current.demo_session_id,
            editing,
            current,
            (spec,),
            request_digest,
            deterministic_seed=job_id,
        )
        # Frozen D01-B ownership trigger binds a restore Job to the historical target,
        # while its deterministic request/result plan remains recoverable by the worker.
        return target.id, target.id

    async def _insert_job_binding(
        self,
        session: AsyncSession,
        job_id: str,
        actor_id: str,
        endpoint: str,
        target_id: str,
        key_hash: str,
        request_digest: str,
        request_id: str,
    ) -> str:
        binding_id = new_id()
        now = self._normalized_now()
        target_type = (
            "EDITING_SESSION"
            if endpoint == "editing_session.create"
            else "IMAGE_VERSION"
            if endpoint == "image_version.restore"
            else "EDIT_PLAN"
        )
        demo_session_id = await self._target_session_id(session, target_type, target_id)
        job = Job(
            id=job_id,
            job_type=f"demo_p3_p7.{endpoint}",
            status="PENDING",
            idempotency_key_hash=_formal_key(actor_id, endpoint, key_hash),
            request_id=request_id,
            payload={},
            owner_user_id=None,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )
        payload = {
            "demo_actor_id": actor_id,
            "demo_session_id": demo_session_id,
            "endpoint_operation": endpoint,
            "idempotency_key_hash": key_hash,
            "job_id": job_id,
            "request_digest": request_digest,
            "target_id": target_id,
            "target_type": target_type,
        }
        binding = DemoJobBinding(
            id=binding_id,
            schema_version=DEMO_JOB_BINDING_SCHEMA,
            canonical_payload=payload,
            content_digest=_authority_digest(DEMO_JOB_BINDING_SCHEMA, payload),
            created_at=now,
            **payload,
        )
        session.add(job)
        await session.flush()
        session.add(binding)
        await session.flush()
        return job_id

    async def _persist_plan(
        self,
        session: AsyncSession,
        actor_id: str,
        session_id: str,
        editing: DemoEditingSession,
        image: DemoImageVersion,
        specs: Sequence[OperationSpec],
        instruction_digest: str,
        *,
        deterministic_seed: str | None = None,
    ) -> str:
        try:
            for spec in specs:
                resolve_tool(spec.engine, spec.operation_type)
        except DemoToolRegistryError as exc:
            raise DemoEditingCommandAuthorityCorruption(
                "operation spec does not match tool registry"
            ) from exc
        existing = await session.scalar(
            select(DemoEditPlan.plan_version)
            .where(DemoEditPlan.input_image_version_id == image.id)
            .order_by(DemoEditPlan.plan_version.desc())
            .limit(1)
        )
        version = int(existing or 0) + 1
        common = {
            "demo_actor_id": actor_id,
            "demo_session_id": session_id,
            "editing_session_id": editing.id,
            "input_image_version_id": image.id,
            "plan_version": version,
            "desired_delta_profile_digest": editing.desired_delta_profile_digest,
            "style_profile_digest": editing.style_profile_digest,
            "identity_constraints_digest": editing.identity_constraints_digest,
            "instruction_digest": instruction_digest,
            "planner_version": PLANNER_VERSION,
            "tool_registry_version": TOOL_REGISTRY_VERSION,
        }
        request = _authority(
            DemoEditPlan,
            row_id=None
            if deterministic_seed is None
            else restore_request_plan_id(deterministic_seed),
            **common,
            record_kind="REQUEST",
            request_plan_id=None,
            operation_specs=[],
        )
        result = _authority(
            DemoEditPlan,
            row_id=None
            if deterministic_seed is None
            else restore_result_plan_id(deterministic_seed),
            **common,
            record_kind="RESULT",
            request_plan_id=request.id,
            operation_specs=[s.canonical_payload() for s in specs],
        )
        session.add_all((request, result))
        await session.flush()
        session.add_all(
            _authority(
                DemoEditOperation,
                row_id=None
                if deterministic_seed is None
                else restore_operation_id(deterministic_seed, index),
                demo_actor_id=actor_id,
                demo_session_id=session_id,
                edit_plan_id=result.id,
                operation_index=index,
                engine=spec.engine.value,
                operation_type=spec.operation_type.value,
                parameters=dict(spec.parameters),
                preserve=[item.value for item in spec.preserve],
                expected_effect=dict(spec.expected_effect),
            )
            for index, spec in enumerate(specs)
        )
        await session.flush()
        return cast(str, result.id)

    async def _lock_context(
        self, session: AsyncSession, actor_id: str, session_id: str
    ) -> DemoSession:
        actor = await session.scalar(
            select(DemoActor).where(DemoActor.id == actor_id).with_for_update()
        )
        row = await session.scalar(
            select(DemoSession)
            .where(DemoSession.id == session_id, DemoSession.demo_actor_id == actor_id)
            .with_for_update()
        )
        if (
            actor is None
            or actor.tombstoned_at is not None
            or row is None
            or row.closed_at is not None
            or row.tombstoned_at is not None
            or row.expires_at <= self._normalized_now()
        ):
            raise DemoEditingCommandUnavailable("Demo actor/session is unavailable")
        return row

    async def _editing(
        self, session: AsyncSession, actor_id: str, editing_id: str
    ) -> DemoEditingSession:
        row = await session.scalar(
            select(DemoEditingSession)
            .where(
                DemoEditingSession.id == editing_id,
                DemoEditingSession.demo_actor_id == actor_id,
                DemoEditingSession.closed_at.is_(None),
                DemoEditingSession.tombstoned_at.is_(None),
            )
            .with_for_update()
        )
        if row is None:
            raise DemoEditingCommandUnavailable("editing Session is unavailable")
        return row

    async def _source_asset(self, session: AsyncSession, c: CreateDemoEditingSession) -> Asset:
        if c.source_asset_id is not None:
            asset = await session.get(Asset, c.source_asset_id)
            if asset is None or not asset.synthetic or asset.deleted_at is not None:
                raise DemoEditingCommandUnavailable("source Asset is unavailable")
            await _require_d02_source_authority(session, asset)
            return asset
        image = await session.scalar(
            select(DemoImageVersion).where(
                DemoImageVersion.id == c.source_image_version_id,
                DemoImageVersion.demo_actor_id == c.demo_actor_id,
                DemoImageVersion.demo_session_id == c.demo_session_id,
            )
        )
        if image is None:
            raise DemoEditingCommandUnavailable("source ImageVersion is unavailable")
        asset = await session.get(Asset, image.result_asset_id)
        if (
            asset is None
            or asset.deleted_at is not None
            or not asset.synthetic
            or asset.sha256 != image.result_asset_sha256
        ):
            raise DemoEditingCommandAuthorityCorruption("source ImageVersion Asset is invalid")
        await _require_d02_source_authority(session, asset)
        return asset

    async def _profiles(
        self, session: AsyncSession, actor_id: str, session_id: str
    ) -> tuple[
        DemoDesiredDeltaProfile,
        DemoStyleProfile,
        DemoIdentityConstraints,
        DemoIdentityConstraints | None,
    ]:
        desired = await session.scalar(
            select(DemoDesiredDeltaProfile)
            .where(
                DemoDesiredDeltaProfile.demo_actor_id == actor_id,
                DemoDesiredDeltaProfile.demo_session_id == session_id,
            )
            .order_by(DemoDesiredDeltaProfile.version.desc())
            .limit(1)
        )
        style = await session.scalar(
            select(DemoStyleProfile)
            .where(
                DemoStyleProfile.demo_actor_id == actor_id,
                DemoStyleProfile.demo_session_id == session_id,
            )
            .order_by(DemoStyleProfile.version.desc())
            .limit(1)
        )
        if style is None:
            style = await session.scalar(
                select(DemoStyleProfile)
                .where(
                    DemoStyleProfile.demo_actor_id == actor_id,
                    DemoStyleProfile.demo_session_id.is_(None),
                )
                .order_by(DemoStyleProfile.version.desc())
                .limit(1)
            )
        persistent = await session.scalar(
            select(DemoIdentityConstraints)
            .where(
                DemoIdentityConstraints.demo_actor_id == actor_id,
                DemoIdentityConstraints.constraint_scope == "PERSISTENT",
            )
            .order_by(DemoIdentityConstraints.version.desc())
            .limit(1)
        )
        override = await session.scalar(
            select(DemoIdentityConstraints)
            .where(
                DemoIdentityConstraints.demo_actor_id == actor_id,
                DemoIdentityConstraints.demo_session_id == session_id,
                DemoIdentityConstraints.constraint_scope == "SESSION_OVERRIDE",
            )
            .order_by(DemoIdentityConstraints.version.desc())
            .limit(1)
        )
        if desired is None or style is None or persistent is None:
            raise DemoEditingCommandUnavailable("required profile authority is missing")
        return desired, style, persistent, override

    async def _target_session_id(
        self, session: AsyncSession, target_type: str, target_id: str
    ) -> str:
        model: type[Any] = {
            "EDITING_SESSION": DemoEditingSession,
            "EDIT_PLAN": DemoEditPlan,
            "IMAGE_VERSION": DemoImageVersion,
        }[target_type]
        row = await session.get(model, target_id)
        if row is None or not isinstance(row.demo_session_id, str):
            raise DemoEditingCommandAuthorityCorruption("Job target session is unavailable")
        return row.demo_session_id

    def _normalized_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise DemoEditingCommandAuthorityCorruption("clock must be timezone-aware")
        return value.astimezone(UTC)


def _authority(model: type[Any], /, **fields: Any) -> Any:
    now = fields.pop("created_at", utcnow())
    row_id = fields.pop("row_id", None)
    row = model(
        id=new_id() if row_id is None else row_id,
        schema_version=f"mirror.demo/{model.__name__}/v1",
        canonical_payload={},
        content_digest="0" * 64,
        created_at=now,
        **fields,
    )
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:
        if column.name in {
            "id",
            "schema_version",
            "canonical_payload",
            "content_digest",
            "created_at",
            "closed_at",
            "tombstoned_at",
        }:
            continue
        value = getattr(row, column.name)
        payload[column.name] = (
            value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            if isinstance(value, datetime)
            else value
        )
    row.canonical_payload = payload
    row.content_digest = _authority_digest(row.schema_version, payload)
    return row


def _authority_digest(schema: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(schema.encode() + b"\n" + canonical_json_bytes(payload)).hexdigest()


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _formal_key(actor: str, endpoint: str, key_hash: str) -> str:
    return hashlib.sha256(
        f"mirror.demo/JobIdempotency/v1\n{actor}\n{endpoint}\n{key_hash}".encode()
    ).hexdigest()


def _validate_winner(
    binding: DemoJobBinding,
    job: Job,
    *,
    actor_id: str,
    endpoint: str,
    key_hash: str,
    request_digest: str,
) -> None:
    expected_target_type = (
        "EDITING_SESSION"
        if endpoint == "editing_session.create"
        else "IMAGE_VERSION"
        if endpoint == "image_version.restore"
        else "EDIT_PLAN"
    )
    payload = {
        "demo_actor_id": actor_id,
        "demo_session_id": binding.demo_session_id,
        "endpoint_operation": endpoint,
        "idempotency_key_hash": key_hash,
        "job_id": job.id,
        "request_digest": request_digest,
        "target_id": binding.target_id,
        "target_type": expected_target_type,
    }
    if (
        binding.demo_actor_id != actor_id
        or binding.endpoint_operation != endpoint
        or binding.idempotency_key_hash != key_hash
        or binding.request_digest != request_digest
        or binding.target_type != expected_target_type
        or binding.job_id != job.id
        or binding.schema_version != DEMO_JOB_BINDING_SCHEMA
        or binding.canonical_payload != payload
        or binding.content_digest != _authority_digest(DEMO_JOB_BINDING_SCHEMA, payload)
        or job.job_type != f"demo_p3_p7.{endpoint}"
        or job.idempotency_key_hash != _formal_key(actor_id, endpoint, key_hash)
        or job.payload != {}
        or job.owner_user_id is not None
        or job.ingestion_upload_intent_id is not None
        or job.result_asset_id is not None
        or job.status not in {"PENDING", "RUNNING", "COMPLETED", "REJECTED", "FAILED", "CANCELLED"}
    ):
        raise DemoEditingCommandAuthorityCorruption("idempotency winner envelope is invalid")


def _deterministic_id(kind: str, *parts: str) -> str:
    preimage = "\n".join((f"mirror.demo/{kind}/v1", *parts))
    return hashlib.sha256(preimage.encode()).hexdigest()[:32]


def restore_request_plan_id(parent_job_id: str) -> str:
    _require_id(parent_job_id, "parent_job_id")
    return _deterministic_id("D07RestoreRequestPlan", parent_job_id)


def restore_result_plan_id(parent_job_id: str) -> str:
    _require_id(parent_job_id, "parent_job_id")
    return _deterministic_id("D07RestoreResultPlan", parent_job_id)


def restore_operation_id(parent_job_id: str, index: int = 0) -> str:
    _require_id(parent_job_id, "parent_job_id")
    if type(index) is not int or index < 0:
        raise DemoEditingCommandInputError("restore operation index is invalid")
    return _deterministic_id("D07RestoreOperation", parent_job_id, str(index))


async def _require_d02_source_authority(session: AsyncSession, asset: Asset) -> None:
    try:
        await require_d02_source_authority_if_applicable(session, asset)
    except DemoEditingRepositoryError as exc:
        raise DemoEditingCommandUnavailable("source Asset is unavailable") from exc


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoEditingCommandInputError(f"{name} must be a lowercase hexadecimal ID")


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DemoEditingCommandInputError(f"{name} must be a SHA-256 digest")


def _require_request_id(value: str) -> None:
    if not isinstance(value, str) or _REQUEST_ID.fullmatch(value) is None:
        raise DemoEditingCommandInputError("request_id is outside the safe boundary")


def _locks(value: Mapping[str, Any]) -> dict[str, str]:
    return {
        key: cast(str, item["mode"])
        for key, item in value.items()
        if isinstance(item, Mapping) and isinstance(item.get("mode"), str)
    }


def _integer_deltas(value: Mapping[str, Any]) -> dict[str, int]:
    return {
        key: cast(int, item.get("delta_ppm", 0))
        for key, item in value.items()
        if isinstance(item, Mapping) and type(item.get("delta_ppm", 0)) is int
    }


def _version_ref(row: DemoImageVersion) -> ImageVersionReference:
    return ImageVersionReference(
        row.id,
        row.content_digest,
        row.demo_actor_id,
        row.demo_session_id,
        row.editing_session_id,
        row.result_asset_id,
        row.result_asset_sha256,
        row.sequence,
        row.parent_version_id,
        row.version_kind == "QUARANTINED",
    )


__all__ = [
    "CreateDemoEditPlan",
    "CreateDemoEditingSession",
    "DemoEditingCommandAccepted",
    "DemoEditingCommandAuthorityCorruption",
    "DemoEditingCommandError",
    "DemoEditingCommandInputError",
    "DemoEditingCommandService",
    "DemoEditingCommandUnavailable",
    "DemoEditingPendingJob",
    "DemoOwnedToolRun",
    "ExecuteDemoEditPlan",
    "RestoreDemoImageVersion",
    "restore_operation_id",
    "restore_request_plan_id",
    "restore_result_plan_id",
]
