"""PostgreSQL-backed, reference-only D07 Worker runtime.

This module deliberately contains no Celery, HTTP, Provider, or private-path
knowledge.  A worker adapter gives it an opaque :class:`DemoEditingTaskMessage`
and injected byte/runtime ports.  The database remains the authority for every
claim and terminal transition; storage is used only before a later authority
commit so redelivery can safely replay an interrupted publication.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_d08_geometry_adapter import (
    D08_VERIFIER_POLICY_VERSION,
    stable_config_digest,
    stable_engine_digest,
)
from mirror_api.demo_d08_geometry_authority import (
    GeometryAuthorityResolutionError,
    resolve_geometry_execution_authority,
)
from mirror_api.demo_editing_asset_loader import (
    DemoAssetByteLoader,
    DemoAssetByteReference,
    DemoAssetLoadError,
)
from mirror_api.demo_editing_repository import (
    DEMO_JOB_BINDING_SCHEMA,
    SqlAlchemyDemoEditingRepository,
    _authority_row,
)
from mirror_api.demo_editing_service import (
    DemoEditingService,
    DemoEditingServiceError,
    EditVerifier,
    ExecutionCommand,
    GeometryDispatcher,
    MaterializedObject,
)
from mirror_api.demo_editing_storage import (
    DemoEditingStorageError,
    DemoLocalPrivateObjectStorage,
)
from mirror_api.demo_editing_task_contract import DemoEditingTaskMessage
from mirror_api.demo_editing_verifier_adapter import DemoEditingVerifierAdapterError
from mirror_api.demo_geometry_editor import (
    GeometryExecutionBackend,
    GeometryExecutionRequest,
    GeometryExecutionState,
    execute_geometry_operation,
)
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import (
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoImageVersion,
    DemoJobBinding,
)
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    parse_operation_spec,
)
from mirror_api.demo_tool_registry import (
    GEOMETRY_ENGINE_VERSION,
    TOOL_REGISTRY_VERSION,
    DemoToolRegistryError,
    resolve_tool,
)
from mirror_api.models import Asset, AssetVariant, Job, JobAttempt, new_id, utcnow

_TERMINAL: Final = frozenset({"COMPLETED", "REJECTED", "FAILED", "CANCELLED"})
_REJECTED_CODES: Final = frozenset(
    {
        "CAPABILITY_UNAVAILABLE",
        "GEOMETRY_CAPABILITY_UNAVAILABLE",
        "REJECTED_STALE_INPUT_VERSION",
        "MAKEUP_DEFERRED_NO_APPROVED_ENGINE",
        "GENERATIVE_PROVIDER_UNAVAILABLE",
        "TRANSITION_RUNTIME_UNAVAILABLE",
        "VERIFIER_CAPABILITY_UNAVAILABLE",
    }
)
_RETRYABLE_STORAGE_CODES: Final = frozenset(
    {
        "ASSET_BYTES_UNAVAILABLE",
        "ASSET_READ_FAILED",
        "STORAGE_OBJECT_MISSING",
        "STORAGE_PATH_UNAVAILABLE",
        "STORAGE_PROMOTION_FAILED",
        "STORAGE_READ_FAILED",
        "STORAGE_WRITE_FAILED",
    }
)
_INTERNAL_RESTORE_REQUEST: Final = re.compile(r"^d07-restore-([0-9a-f]{32})$")


class DemoEditingRuntimeError(RuntimeError):
    """Fail-closed Worker error which never carries image bytes or locators."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DemoEditingRuntimeResult:
    job_id: str
    status: str
    result_code: str | None
    executed: bool
    replayed: bool


@dataclass(frozen=True, slots=True)
class _Claim:
    actor_id: str
    binding_id: str
    job_id: str
    attempt_id: str
    operation: str
    target_id: str
    session_id: str
    restore_parent_job_id: str | None = None


class DemoEditingRuntime:
    """Execute the four immutable D07 command projections.

    An active lease is deliberately a no-op for duplicate delivery.  A stale
    lease produces one new attempt up to ``max_attempts``; both paths use the
    same durable source/original/quarantine object keys.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        asset_loader: DemoAssetByteLoader,
        storage: DemoLocalPrivateObjectStorage,
        verifier: EditVerifier | None = None,
        geometry_dispatcher: GeometryDispatcher | None = None,
        geometry_backend: GeometryExecutionBackend | None = None,
        now: Callable[[], datetime] = utcnow,
        lease_seconds: int = 120,
        max_attempts: int = 3,
    ) -> None:
        if not 1 <= lease_seconds <= 3600 or not 1 <= max_attempts <= 10:
            raise ValueError("runtime lease and retry limits are invalid")
        self._sessions = session_factory
        self._asset_loader = asset_loader
        self._storage = storage
        self._verifier = verifier
        self._injected_geometry_dispatcher = geometry_dispatcher
        self._geometry_backend = geometry_backend
        self._now = now
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._repository = SqlAlchemyDemoEditingRepository(session_factory=session_factory)

    async def run(self, message: DemoEditingTaskMessage) -> DemoEditingRuntimeResult:
        message.validate()
        claim = await self._claim(message)
        if claim is None:
            return await self._snapshot(message.job_id, executed=False, replayed=True)
        try:
            if claim.restore_parent_job_id is not None:
                await self._terminalize(claim, "FAILED", "RESTORE_PARENT_TERMINAL")
            elif claim.operation == "editing_session.create":
                await self._publish_original(claim)
            elif claim.operation == "edit_plan.create":
                await self._complete_plan(claim)
            elif claim.operation == "edit_plan.execute":
                await self._execute_plan(claim)
            elif claim.operation == "image_version.restore":
                await self._restore(claim)
            else:  # Defensive: binding validation is intentionally repeated here.
                raise DemoEditingRuntimeError("TASK_OPERATION_INVALID", "operation is unsupported")
        except DemoEditingRuntimeError as exc:
            await self._terminalize(claim, self._terminal_for(exc.code), exc.code)
        except DemoEditingServiceError as exc:
            if exc.code == "EXECUTION_LEASE_EXPIRED":
                await self._defer_retry(claim)
            else:
                await self._terminalize(claim, self._terminal_for(exc.code), exc.code)
        except (DemoAssetLoadError, DemoEditingStorageError) as exc:
            if exc.code in _RETRYABLE_STORAGE_CODES:
                await self._defer_retry(claim)
            else:
                await self._terminalize(claim, "FAILED", exc.code)
        except OperationalError:
            await self._defer_retry(claim)
        except DemoEditingVerifierAdapterError as exc:
            await self._terminalize(claim, "FAILED", exc.code)
        except Exception:
            await self._terminalize(claim, "FAILED", "RUNTIME_EXECUTION_FAILED")
        return await self._snapshot(message.job_id, executed=True, replayed=False)

    async def _claim(self, message: DemoEditingTaskMessage) -> _Claim | None:
        now = self._normalized_now()
        async with self._sessions() as session:
            async with session.begin():
                row = await session.execute(
                    select(Job, DemoJobBinding)
                    .join(DemoJobBinding, DemoJobBinding.job_id == Job.id)
                    .where(Job.id == message.job_id)
                    .with_for_update(of=Job)
                )
                pair = row.one_or_none()
                if pair is None:
                    raise DemoEditingRuntimeError("JOB_UNAVAILABLE", "Demo Job is unavailable")
                job, binding = pair
                self._validate_message_binding(job, binding, message)
                restore_parent_job_id = await self._internal_restore_parent_id(
                    session, job, binding
                )
                if restore_parent_job_id is not None:
                    restore_parent = await session.get(Job, restore_parent_job_id)
                    if restore_parent is None:
                        raise DemoEditingRuntimeError(
                            "RESTORE_PARENT_UNAVAILABLE",
                            "internal restore parent Job is unavailable",
                        )
                    if restore_parent.status not in _TERMINAL:
                        return None
                if job.status in _TERMINAL:
                    return None
                if job.status == "RUNNING":
                    active = await session.scalar(
                        select(JobAttempt)
                        .where(
                            JobAttempt.job_id == job.id,
                            JobAttempt.attempt == job.attempt_count,
                        )
                        .with_for_update()
                    )
                    if active is None or active.status != "RUNNING":
                        raise DemoEditingRuntimeError(
                            "JOB_ATTEMPT_AUTHORITY_INVALID",
                            "running Job lacks current attempt",
                        )
                    if job.lease_expires_at is None or job.lease_expires_at > now:
                        return None
                    if job.attempt_count >= self._max_attempts:
                        self._finish(job, active, "FAILED", "RETRY_LIMIT_EXHAUSTED", now)
                        return None
                    active.status = "FAILED"
                    active.error_code = "LEASE_EXPIRED"
                    active.result_code = None
                    active.finished_at = now
                elif job.status != "PENDING":
                    raise DemoEditingRuntimeError("JOB_STATE_INVALID", "Job state is invalid")
                elif job.attempt_count != 0:
                    raise DemoEditingRuntimeError(
                        "JOB_ATTEMPT_AUTHORITY_INVALID", "pending Job has attempts"
                    )
                attempt_number = job.attempt_count + 1
                token = hashlib.sha256(
                    (
                        f"mirror.demo/D07Lease/v1\n{job.id}\n{attempt_number}\n{now.isoformat()}"
                    ).encode()
                ).hexdigest()
                attempt = JobAttempt(
                    id=new_id(),
                    job_id=job.id,
                    attempt=attempt_number,
                    status="RUNNING",
                    lease_token=token,
                    started_at=now,
                )
                session.add(attempt)
                job.status = "RUNNING"
                job.attempt_count = attempt_number
                job.lease_token = token
                job.lease_acquired_at = now
                job.lease_expires_at = now + timedelta(seconds=self._lease_seconds)
                job.updated_at = now
                await session.flush()
                if binding.demo_session_id is None:
                    raise DemoEditingRuntimeError(
                        "BINDING_SESSION_MISSING", "Demo Session is required"
                    )
                return _Claim(
                    binding.demo_actor_id,
                    binding.id,
                    job.id,
                    attempt.id,
                    binding.endpoint_operation,
                    binding.target_id,
                    binding.demo_session_id,
                    restore_parent_job_id,
                )

    async def _publish_original(self, claim: _Claim) -> None:
        """Write original bytes first, then atomically append sequence zero authority."""

        async with self._sessions() as session:
            editing = await session.get(DemoEditingSession, claim.target_id)
            if editing is None or editing.demo_actor_id != claim.actor_id:
                raise DemoEditingRuntimeError(
                    "EDITING_SESSION_UNAVAILABLE", "editing Session is unavailable"
                )
            source = await session.get(Asset, editing.source_asset_id)
            if source is None:
                raise DemoEditingRuntimeError(
                    "SOURCE_ASSET_UNAVAILABLE", "source Asset is unavailable"
                )
            reference = self._reference(source)
        content = await self._asset_loader.load(reference)
        if hashlib.sha256(content).hexdigest() != reference.sha256:
            raise DemoEditingRuntimeError("SOURCE_DIGEST_MISMATCH", "source bytes changed")
        original_key = await self._storage.store_original_snapshot(
            editing_session_id=claim.target_id, content=content, sha256=reference.sha256
        )
        async with self._sessions() as session:
            async with session.begin():
                job, attempt, binding = await self._lock_running(session, claim)
                editing = await session.scalar(
                    select(DemoEditingSession)
                    .where(DemoEditingSession.id == claim.target_id)
                    .with_for_update()
                )
                if editing is None or binding.target_id != editing.id:
                    raise DemoEditingRuntimeError(
                        "EDITING_SESSION_UNAVAILABLE", "editing Session is unavailable"
                    )
                source = await session.get(Asset, editing.source_asset_id, with_for_update=True)
                if source is None or source.deleted_at is not None or not source.synthetic:
                    raise DemoEditingRuntimeError(
                        "SOURCE_ASSET_UNAVAILABLE", "source Asset is unavailable"
                    )
                if source.sha256 != reference.sha256 or source.byte_size != len(content):
                    raise DemoEditingRuntimeError(
                        "SOURCE_AUTHORITY_MISMATCH", "source Asset changed"
                    )
                existing = await session.scalar(
                    select(DemoImageVersion)
                    .where(
                        DemoImageVersion.editing_session_id == editing.id,
                        DemoImageVersion.sequence == 0,
                    )
                    .with_for_update()
                )
                if existing is None:
                    result_id = self._id("D07OriginalAsset", editing.id, source.sha256)
                    variant_id = self._id("D07OriginalAssetVariant", editing.id, source.sha256)
                    image_id = self._id("D07OriginalImageVersion", editing.id, source.sha256)
                    result = await session.get(Asset, result_id)
                    if result is None:
                        result = Asset(
                            id=result_id,
                            owner_user_id=None,
                            asset_role="derived",
                            storage_key=original_key,
                            mime_type=source.mime_type,
                            byte_size=source.byte_size,
                            width=source.width,
                            height=source.height,
                            sha256=source.sha256,
                            synthetic=True,
                            is_ai_generated=source.is_ai_generated,
                            is_ai_modified=False,
                            internal_purpose=None,
                            deleted_at=None,
                        )
                        session.add(result)
                    elif result.storage_key != original_key or result.sha256 != source.sha256:
                        raise DemoEditingRuntimeError(
                            "ORIGINAL_SNAPSHOT_CONFLICT", "original snapshot conflicts"
                        )
                    variant = await session.get(AssetVariant, variant_id)
                    if variant is None:
                        variant = AssetVariant(
                            id=variant_id,
                            source_asset_id=source.id,
                            result_asset_id=result_id,
                            variant_type="demo_p3_p7_original_snapshot",
                        )
                        session.add(variant)
                    # The PostgreSQL ImageVersion guard validates live AssetVariant
                    # lineage immediately, so the immutable Asset/variant pair must
                    # be visible before the ImageVersion insert is attempted.
                    await session.flush()
                    image = _authority_row(
                        DemoImageVersion,
                        row_id=image_id,
                        demo_actor_id=claim.actor_id,
                        demo_session_id=claim.session_id,
                        editing_session_id=editing.id,
                        sequence=0,
                        parent_version_id=None,
                        source_asset_id=source.id,
                        source_asset_sha256=source.sha256,
                        result_asset_id=result_id,
                        result_asset_sha256=source.sha256,
                        result_asset_variant_id=variant_id,
                        version_kind="ORIGINAL",
                        plan_digest=None,
                        tool_run_digest=None,
                        verifier_digest=None,
                    )
                    session.add(image)
                self._finish(
                    job,
                    attempt,
                    "COMPLETED",
                    "EDITING_SESSION_INITIALIZED",
                    self._normalized_now(),
                )
                await session.flush()

    async def _complete_plan(self, claim: _Claim) -> None:
        async with self._sessions() as session:
            async with session.begin():
                job, attempt, _binding = await self._lock_running(session, claim)
                plan = await session.scalar(
                    select(DemoEditPlan).where(DemoEditPlan.id == claim.target_id).with_for_update()
                )
                if (
                    plan is None
                    or plan.record_kind != "RESULT"
                    or plan.demo_actor_id != claim.actor_id
                    or plan.demo_session_id != claim.session_id
                ):
                    raise DemoEditingRuntimeError(
                        "PLAN_AUTHORITY_INVALID", "result plan is unavailable"
                    )
                operations = (
                    await session.scalars(
                        select(DemoEditOperation)
                        .where(DemoEditOperation.edit_plan_id == plan.id)
                        .order_by(DemoEditOperation.operation_index)
                        .with_for_update()
                    )
                ).all()
                if not operations or [item.operation_index for item in operations] != list(
                    range(len(operations))
                ):
                    raise DemoEditingRuntimeError(
                        "PLAN_OPERATION_INVALID", "plan operations are invalid"
                    )
                for operation in operations:
                    self._operation_spec(operation)
                self._finish(job, attempt, "COMPLETED", "EDIT_PLAN_READY", self._normalized_now())

    async def _execute_plan(self, claim: _Claim, *, parent: _Claim | None = None) -> None:
        command = await self._execution_command(claim, parent=parent)
        if (
            command.operation.engine is OperationEngine.GEOMETRY
            and self._geometry_backend is None
            and self._injected_geometry_dispatcher is None
        ):
            raise DemoEditingRuntimeError(
                "GEOMETRY_CAPABILITY_UNAVAILABLE", "geometry runtime is not materialized"
            )
        if self._verifier is None:
            raise DemoEditingRuntimeError(
                "VERIFIER_CAPABILITY_UNAVAILABLE", "verifier is not configured"
            )
        service = DemoEditingService(
            repository=self._repository,
            storage=self._storage,
            verifier=self._verifier,
            geometry_dispatcher=(
                self._dispatch_geometry
                if self._geometry_backend is not None
                else self._injected_geometry_dispatcher
            ),
            transition_dispatcher=self._transition_dispatcher,
        )
        await service.execute(command)

    async def _restore(self, parent: _Claim) -> None:
        child = await self._claim_restore_child(parent)
        if child is None:
            return
        try:
            await self._execute_plan(child, parent=parent)
        except (DemoEditingRuntimeError, DemoEditingServiceError) as exc:
            status = self._terminal_for(exc.code)
            await self._terminalize(child, status, exc.code, parent=parent)
            raise

    async def _claim_restore_child(self, parent: _Claim) -> _Claim | None:
        """Create/reuse the deterministic internal execution Job for a restore parent."""

        from mirror_api.demo_editing_commands import restore_result_plan_id

        async with self._sessions() as session:
            async with session.begin():
                parent_job, parent_attempt, parent_binding = await self._lock_running(
                    session, parent
                )
                if parent_job.lease_expires_at is None:
                    raise DemoEditingRuntimeError(
                        "RESTORE_PARENT_LEASE_INVALID", "restore parent lease is unavailable"
                    )
                plan_id = restore_result_plan_id(parent.job_id)
                plan = await session.get(DemoEditPlan, plan_id, with_for_update=True)
                if plan is None or plan.record_kind != "RESULT":
                    raise DemoEditingRuntimeError(
                        "RESTORE_PLAN_UNAVAILABLE", "restore plan is unavailable"
                    )
                child_id = self._id(
                    "D07RestoreChildJob", parent.job_id, parent_binding.content_digest
                )
                binding = await session.scalar(
                    select(DemoJobBinding)
                    .where(DemoJobBinding.job_id == child_id)
                    .with_for_update()
                )
                now = self._normalized_now()
                attempt_number = 1
                if binding is None:
                    key_hash = hashlib.sha256(
                        f"mirror.demo/D07RestoreChild/v1\n{parent.job_id}".encode()
                    ).hexdigest()
                    request_digest = hashlib.sha256(
                        canonical_json_bytes(
                            {
                                "parent_binding_digest": parent_binding.content_digest,
                                "parent_job_id": parent.job_id,
                                "result_plan_id": plan_id,
                            }
                        )
                    ).hexdigest()
                    job = Job(
                        id=child_id,
                        job_type="demo_p3_p7.edit_plan.execute",
                        status="PENDING",
                        idempotency_key_hash=hashlib.sha256(
                            (
                                "mirror.demo/JobIdempotency/v1\n"
                                f"{parent.actor_id}\nedit_plan.execute\n{key_hash}"
                            ).encode()
                        ).hexdigest(),
                        request_id=f"d07-restore-{parent.job_id}",
                        payload={},
                        owner_user_id=None,
                        attempt_count=0,
                        created_at=now,
                        updated_at=now,
                    )
                    binding = _authority_row(
                        DemoJobBinding,
                        schema_version=DEMO_JOB_BINDING_SCHEMA,
                        demo_actor_id=parent.actor_id,
                        demo_session_id=parent.session_id,
                        endpoint_operation="edit_plan.execute",
                        idempotency_key_hash=key_hash,
                        job_id=child_id,
                        request_digest=request_digest,
                        target_id=plan_id,
                        target_type="EDIT_PLAN",
                    )
                    session.add(job)
                    await session.flush()
                    session.add(binding)
                    await session.flush()
                else:
                    existing_job = await session.get(Job, child_id, with_for_update=True)
                    if existing_job is None:
                        raise DemoEditingRuntimeError(
                            "RESTORE_CHILD_INVALID", "restore child Job is invalid"
                        )
                    job = existing_job
                    if (
                        binding.endpoint_operation != "edit_plan.execute"
                        or binding.target_id != plan_id
                        or binding.demo_actor_id != parent.actor_id
                        or binding.demo_session_id != parent.session_id
                        or binding.target_type != "EDIT_PLAN"
                    ):
                        raise DemoEditingRuntimeError(
                            "RESTORE_CHILD_INVALID", "restore child binding mismatches"
                        )
                    if job.status in _TERMINAL:
                        raise DemoEditingRuntimeError(
                            "RESTORE_CHILD_TERMINAL_MISMATCH",
                            "restore child is terminal while its parent remains running",
                        )
                    if job.status == "RUNNING":
                        active = await session.scalar(
                            select(JobAttempt)
                            .where(
                                JobAttempt.job_id == job.id,
                                JobAttempt.attempt == job.attempt_count,
                            )
                            .with_for_update()
                        )
                        if active is None or active.status != "RUNNING":
                            raise DemoEditingRuntimeError(
                                "RESTORE_CHILD_INVALID",
                                "running restore child lacks its current attempt",
                            )
                        if job.lease_expires_at is None or job.lease_expires_at > now:
                            return None
                        if job.attempt_count >= self._max_attempts:
                            self._finish(
                                job,
                                active,
                                "FAILED",
                                "RETRY_LIMIT_EXHAUSTED",
                                now,
                            )
                            self._finish(
                                parent_job,
                                parent_attempt,
                                "FAILED",
                                "RETRY_LIMIT_EXHAUSTED",
                                now,
                            )
                            return None
                        active.status = "FAILED"
                        active.error_code = "LEASE_EXPIRED"
                        active.result_code = None
                        active.finished_at = now
                        attempt_number = job.attempt_count + 1
                    elif job.status == "PENDING" and job.attempt_count == 0:
                        attempt_number = 1
                    else:
                        raise DemoEditingRuntimeError(
                            "RESTORE_CHILD_INVALID", "restore child state is invalid"
                        )
                token = hashlib.sha256(
                    (
                        f"mirror.demo/D07Lease/v1\n{child_id}\n{attempt_number}\n{now.isoformat()}"
                    ).encode()
                ).hexdigest()
                attempt = JobAttempt(
                    id=new_id(),
                    job_id=child_id,
                    attempt=attempt_number,
                    status="RUNNING",
                    lease_token=token,
                    started_at=now,
                )
                session.add(attempt)
                job.status, job.attempt_count = "RUNNING", attempt_number
                job.lease_token, job.lease_acquired_at = token, now
                job.lease_expires_at = parent_job.lease_expires_at
                job.updated_at = now
                await session.flush()
                return _Claim(
                    parent.actor_id,
                    binding.id,
                    child_id,
                    attempt.id,
                    "edit_plan.execute",
                    plan_id,
                    parent.session_id,
                    parent.job_id,
                )

    async def _execution_command(self, claim: _Claim, *, parent: _Claim | None) -> ExecutionCommand:
        async with self._sessions() as session:
            plan = await session.get(DemoEditPlan, claim.target_id)
            if plan is None or plan.record_kind != "RESULT":
                raise DemoEditingRuntimeError(
                    "PLAN_AUTHORITY_INVALID", "result plan is unavailable"
                )
            if plan.tool_registry_version != TOOL_REGISTRY_VERSION:
                raise DemoEditingRuntimeError(
                    "TOOL_REGISTRY_MISMATCH", "result plan registry version is invalid"
                )
            operations = (
                await session.scalars(
                    select(DemoEditOperation)
                    .where(DemoEditOperation.edit_plan_id == plan.id)
                    .order_by(DemoEditOperation.operation_index)
                )
            ).all()
            if len(operations) != 1 or operations[0].operation_index != 0:
                raise DemoEditingRuntimeError(
                    "MULTI_OPERATION_EXECUTION_UNAVAILABLE",
                    "runtime accepts exactly one operation",
                )
            operation = operations[0]
            spec = self._operation_spec(operation)
            try:
                descriptor = resolve_tool(spec.engine, spec.operation_type)
            except DemoToolRegistryError as exc:
                raise DemoEditingRuntimeError(
                    "TOOL_REGISTRY_MISMATCH", "operation is not registered"
                ) from exc
            if descriptor.unavailable_reason_code is not None:
                raise DemoEditingRuntimeError(
                    descriptor.unavailable_reason_code,
                    "operation capability is deliberately unavailable",
                )
            image = await session.get(DemoImageVersion, plan.input_image_version_id)
            if image is None or image.editing_session_id != plan.editing_session_id:
                raise DemoEditingRuntimeError(
                    "INPUT_IMAGE_VERSION_UNAVAILABLE", "input ImageVersion is unavailable"
                )
            source = await session.get(Asset, image.result_asset_id)
            if source is None or source.deleted_at is not None or not source.synthetic:
                raise DemoEditingRuntimeError(
                    "SOURCE_ASSET_UNAVAILABLE", "input Asset is unavailable"
                )
            if source.sha256 != image.result_asset_sha256:
                raise DemoEditingRuntimeError(
                    "SOURCE_AUTHORITY_MISMATCH", "input Asset digest mismatches"
                )
            geometry_authority = None
            geometry_job_attempt = None
            if spec.engine is OperationEngine.GEOMETRY:
                try:
                    (
                        geometry_authority,
                        geometry_job_attempt,
                    ) = await resolve_geometry_execution_authority(
                        session,
                        actor_id=claim.actor_id,
                        session_id=claim.session_id,
                        editing_session_id=plan.editing_session_id,
                        plan_id=plan.id,
                        operation_id=operation.id,
                        operation=spec,
                        execution_job_binding_id=claim.binding_id,
                        formal_job_attempt_id=claim.attempt_id,
                    )
                except GeometryAuthorityResolutionError as exc:
                    raise DemoEditingRuntimeError(exc.code, str(exc)) from exc
                root = await session.get(Asset, geometry_authority.root_source_asset_id)
                if (
                    root is None
                    or root.sha256 != geometry_authority.root_source_asset_sha256
                    or root.deleted_at is not None
                    or not root.synthetic
                    or source.id != geometry_authority.input_asset_id
                    or source.sha256 != geometry_authority.input_asset_sha256
                    or source.sha256 != root.sha256
                ):
                    raise DemoEditingRuntimeError(
                        "GEOMETRY_SOURCE_LINEAGE_INVALID", "geometry root source changed"
                    )
            reference = self._reference(source)
        content = await self._asset_loader.load(reference)
        if descriptor.engine_version is None:
            raise DemoEditingRuntimeError(
                "CAPABILITY_UNAVAILABLE", "execution engine is unavailable"
            )
        engine_digest = self._digest("D07Engine", descriptor.engine_version)
        config_digest = self._digest("D07Config", plan.content_digest, operation.content_digest)
        if geometry_authority is not None:
            engine_digest = stable_engine_digest(geometry_authority, GEOMETRY_ENGINE_VERSION)
            config_digest = stable_config_digest(geometry_authority, D08_VERIFIER_POLICY_VERSION)
        return ExecutionCommand(
            actor_id=claim.actor_id,
            session_id=claim.session_id,
            operation_id=operation.id,
            operation_digest=operation.content_digest,
            execution_job_binding_id=claim.binding_id,
            formal_job_attempt_id=claim.attempt_id,
            source_asset_id=source.id,
            source_asset_sha256=source.sha256,
            source_bytes=content,
            operation=spec,
            engine_version=descriptor.engine_version,
            engine_digest=engine_digest,
            config_digest=config_digest,
            editing_session_id=None if geometry_authority is None else plan.editing_session_id,
            plan_id=None if geometry_authority is None else plan.id,
            input_image_version_id=None if geometry_authority is None else image.id,
            root_source_asset_id=(
                None if geometry_authority is None else geometry_authority.root_source_asset_id
            ),
            geometry_authority=geometry_authority,
            geometry_job_attempt=geometry_job_attempt,
            parent_job_id=None if parent is None else parent.job_id,
            parent_job_attempt_id=None if parent is None else parent.attempt_id,
        )

    async def _dispatch_geometry(self, command: ExecutionCommand) -> MaterializedObject:
        if command.geometry_authority is None or command.geometry_job_attempt is None:
            raise DemoEditingRuntimeError(
                "GEOMETRY_AUTHORITY_MISSING", "geometry command lacks authority"
            )
        outcome = execute_geometry_operation(
            GeometryExecutionRequest(
                operation=command.operation,
                authority=command.geometry_authority,
                job_attempt=command.geometry_job_attempt,
                source_bytes=command.source_bytes,
            ),
            self._geometry_backend,
        )
        if outcome.state is not GeometryExecutionState.MATERIALIZED or outcome.success is None:
            raise DemoEditingRuntimeError(outcome.reason_code, "geometry materialization failed")
        success = outcome.success
        return MaterializedObject(
            content=success.output_bytes,
            sha256=success.result_sha256,
            width=success.stable_core.result_width,
            height=success.stable_core.result_height,
            mime_type=success.stable_core.result_media_type,
            engine_digest=success.stable_core.engine_digest,
            config_digest=success.stable_core.config_digest,
            geometry_stable_core=success.stable_core,
            geometry_attempt_evidence=success.attempt_evidence,
        )

    async def _transition_dispatcher(self, command: ExecutionCommand) -> MaterializedObject:
        target_id = command.operation.parameters.get("target_image_version_id")
        target_digest = command.operation.parameters.get("target_image_version_digest")
        if not isinstance(target_id, str) or not isinstance(target_digest, str):
            raise DemoEditingRuntimeError(
                "TRANSITION_TARGET_INVALID", "transition target is invalid"
            )
        async with self._sessions() as session:
            target = await session.get(DemoImageVersion, target_id)
            if target is None or target.content_digest != target_digest:
                raise DemoEditingRuntimeError(
                    "TRANSITION_TARGET_INVALID", "transition target changed"
                )
            asset = await session.get(Asset, target.result_asset_id)
            if asset is None or asset.sha256 != target.result_asset_sha256 or not asset.synthetic:
                raise DemoEditingRuntimeError(
                    "TRANSITION_TARGET_INVALID", "transition target Asset is invalid"
                )
            reference = self._reference(asset)
        content = await self._asset_loader.load(reference)
        return MaterializedObject(
            content=content,
            sha256=reference.sha256,
            width=asset.width,
            height=asset.height,
            mime_type=asset.mime_type,
            engine_digest=command.engine_digest,
            config_digest=command.config_digest,
        )

    async def _terminalize(
        self,
        claim: _Claim,
        status: Literal["REJECTED", "FAILED"],
        code: str,
        *,
        parent: _Claim | None = None,
    ) -> None:
        async with self._sessions() as session:
            async with session.begin():
                job, attempt, _binding = await self._lock_running(session, claim, terminal_ok=True)
                if job.status == "RUNNING":
                    self._finish(job, attempt, status, code, self._normalized_now())
                if parent is not None:
                    parent_job, parent_attempt, _ = await self._lock_running(
                        session, parent, terminal_ok=True
                    )
                    if parent_job.status == "RUNNING":
                        self._finish(
                            parent_job, parent_attempt, status, code, self._normalized_now()
                        )

    async def _defer_retry(self, claim: _Claim) -> None:
        """Expire, but do not terminalize, a recoverable in-flight attempt."""

        async with self._sessions() as session:
            async with session.begin():
                job, _attempt, _binding = await self._lock_running(session, claim, terminal_ok=True)
                if job.status != "RUNNING":
                    return
                if job.attempt_count >= self._max_attempts:
                    attempt = await session.get(JobAttempt, claim.attempt_id, with_for_update=True)
                    if attempt is None:
                        raise DemoEditingRuntimeError(
                            "JOB_ATTEMPT_AUTHORITY_INVALID",
                            "Job attempt is unavailable",
                        )
                    self._finish(
                        job,
                        attempt,
                        "FAILED",
                        "RETRY_LIMIT_EXHAUSTED",
                        self._normalized_now(),
                    )
                    return
                job.lease_expires_at = self._normalized_now() - timedelta(microseconds=1)
                job.updated_at = self._normalized_now()

    async def _lock_running(
        self, session: AsyncSession, claim: _Claim, *, terminal_ok: bool = False
    ) -> tuple[Job, JobAttempt, DemoJobBinding]:
        row = await session.execute(
            select(Job, DemoJobBinding)
            .join(DemoJobBinding, DemoJobBinding.job_id == Job.id)
            .where(Job.id == claim.job_id, DemoJobBinding.id == claim.binding_id)
            .with_for_update(of=Job)
        )
        pair = row.one_or_none()
        if pair is None:
            raise DemoEditingRuntimeError("JOB_UNAVAILABLE", "Demo Job is unavailable")
        job, binding = pair
        attempt = await session.scalar(
            select(JobAttempt).where(JobAttempt.id == claim.attempt_id).with_for_update()
        )
        if attempt is None or attempt.job_id != job.id:
            raise DemoEditingRuntimeError(
                "JOB_ATTEMPT_AUTHORITY_INVALID", "Job attempt is unavailable"
            )
        if job.status in _TERMINAL and terminal_ok:
            return job, attempt, binding
        if (
            job.status != "RUNNING"
            or attempt.status != "RUNNING"
            or attempt.attempt != job.attempt_count
        ):
            raise DemoEditingRuntimeError("JOB_NOT_RUNNING", "Job is not running")
        return job, attempt, binding

    async def _snapshot(
        self, job_id: str, *, executed: bool, replayed: bool
    ) -> DemoEditingRuntimeResult:
        async with self._sessions() as session:
            job = await session.get(Job, job_id)
            if job is None:
                raise DemoEditingRuntimeError("JOB_UNAVAILABLE", "Demo Job is unavailable")
            return DemoEditingRuntimeResult(job.id, job.status, job.result_code, executed, replayed)

    @staticmethod
    def _finish(job: Job, attempt: JobAttempt, status: str, code: str, now: datetime) -> None:
        if status not in {"COMPLETED", "REJECTED", "FAILED"}:
            raise DemoEditingRuntimeError("JOB_TERMINAL_INVALID", "terminal status is invalid")
        attempt.status, attempt.result_code, attempt.error_code, attempt.finished_at = (
            status,
            code if status != "FAILED" else None,
            code if status == "FAILED" else None,
            now,
        )
        job.status, job.result_code, job.finalized_at = status, code, now
        job.lease_token = job.lease_acquired_at = job.lease_expires_at = None
        job.updated_at = now

    @staticmethod
    def _terminal_for(code: str) -> Literal["REJECTED", "FAILED"]:
        return "REJECTED" if code in _REJECTED_CODES else "FAILED"

    @staticmethod
    def _reference(asset: Asset) -> DemoAssetByteReference:
        if asset.deleted_at is not None or not asset.synthetic:
            raise DemoEditingRuntimeError("SOURCE_ASSET_UNAVAILABLE", "Asset is unavailable")
        return DemoAssetByteReference(
            asset.id, asset.storage_key, asset.sha256, asset.byte_size, True
        )

    @staticmethod
    def _operation_spec(operation: DemoEditOperation) -> OperationSpec:
        spec = parse_operation_spec(
            {
                "engine": operation.engine,
                "operation_type": operation.operation_type,
                "parameters": operation.parameters,
                "preserve": operation.preserve,
                "expected_effect": operation.expected_effect,
            }
        )
        try:
            resolve_tool(spec.engine, spec.operation_type)
        except DemoToolRegistryError as exc:
            raise DemoEditingRuntimeError(
                "TOOL_REGISTRY_MISMATCH", "operation spec is not registered"
            ) from exc
        return spec

    @staticmethod
    def _id(kind: str, *values: str) -> str:
        return hashlib.sha256("\n".join((f"mirror.demo/{kind}/v1", *values)).encode()).hexdigest()[
            :32
        ]

    @staticmethod
    def _digest(kind: str, *values: str) -> str:
        return hashlib.sha256("\n".join((f"mirror.demo/{kind}/v1", *values)).encode()).hexdigest()

    @staticmethod
    def _validate_message_binding(
        job: Job, binding: DemoJobBinding, message: DemoEditingTaskMessage
    ) -> None:
        if (
            binding.demo_actor_id != message.demo_actor_id
            or binding.job_id != job.id
            or binding.endpoint_operation != message.operation
            or job.request_id != message.request_id
            or job.job_type != f"demo_p3_p7.{message.operation}"
        ):
            raise DemoEditingRuntimeError(
                "TASK_BINDING_MISMATCH", "task message mismatches authority"
            )

    async def _internal_restore_parent_id(
        self,
        session: AsyncSession,
        job: Job,
        binding: DemoJobBinding,
    ) -> str | None:
        if binding.endpoint_operation != "edit_plan.execute":
            return None
        match = _INTERNAL_RESTORE_REQUEST.fullmatch(job.request_id)
        if match is None:
            return None
        parent_job_id = match.group(1)
        parent_binding = await session.scalar(
            select(DemoJobBinding).where(DemoJobBinding.job_id == parent_job_id)
        )
        if parent_binding is None or parent_binding.endpoint_operation != "image_version.restore":
            return None

        from mirror_api.demo_editing_commands import restore_result_plan_id

        expected_child_id = self._id(
            "D07RestoreChildJob", parent_job_id, parent_binding.content_digest
        )
        if (
            job.id != expected_child_id
            or binding.target_id != restore_result_plan_id(parent_job_id)
            or binding.target_type != "EDIT_PLAN"
            or binding.demo_actor_id != parent_binding.demo_actor_id
            or binding.demo_session_id != parent_binding.demo_session_id
        ):
            raise DemoEditingRuntimeError(
                "RESTORE_CHILD_INVALID", "internal restore child authority mismatches"
            )
        return parent_job_id

    def _normalized_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise DemoEditingRuntimeError("CLOCK_INVALID", "runtime clock must be timezone-aware")
        return value.astimezone(UTC)


__all__ = ["DemoEditingRuntime", "DemoEditingRuntimeError", "DemoEditingRuntimeResult"]
