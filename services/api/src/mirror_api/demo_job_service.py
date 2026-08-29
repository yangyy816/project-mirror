"""Owner-bound lifecycle reads and cancellation for Demo Jobs.

The formal ``jobs`` row remains mutable execution state.  The immutable
``DemoJobBinding`` supplies the Demo actor, optional Session and typed target
authority needed by the public lifecycle envelope.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_idempotency import (
    DemoIdempotencyPayloadConflict,
    DemoIdempotencyTarget,
    DemoSemanticIdempotencyCoordinator,
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DemoActor,
    DemoAnalysisRun,
    DemoAuthorityMixin,
    DemoCommandBinding,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoFaceObservation,
    DemoImageVersion,
    DemoJobBinding,
    DemoQuestionnaireRun,
    DemoSelfTransferRun,
    DemoSession,
    DemoToolRun,
)
from mirror_api.models import Job, JobAttempt, utcnow

DemoJobStatus = Literal["PENDING", "RUNNING", "COMPLETED", "REJECTED", "FAILED", "CANCELLED"]
DemoJobTargetType = Literal[
    "DEMO_ACTOR",
    "DEMO_SESSION",
    "ANALYSIS_RUN",
    "FACE_OBSERVATION",
    "QUESTIONNAIRE_RUN",
    "SELF_TRANSFER_RUN",
    "EDITING_SESSION",
    "IMAGE_VERSION",
    "EDIT_PLAN",
    "EDIT_OPERATION",
    "TOOL_RUN",
]

DEMO_JOB_BINDING_SCHEMA: Final = "mirror.demo/DemoJobBinding/v1"
DEMO_JOB_CANCEL_OPERATION: Final = "job.cancel"
_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL: Final = frozenset({"COMPLETED", "REJECTED", "FAILED", "CANCELLED"})
_STATUSES: Final = frozenset({"PENDING", "RUNNING", *_TERMINAL})

_TARGET_MODELS: Mapping[str, type[DemoAuthorityMixin]] = {
    "DEMO_ACTOR": DemoActor,
    "DEMO_SESSION": DemoSession,
    "ANALYSIS_RUN": DemoAnalysisRun,
    "FACE_OBSERVATION": DemoFaceObservation,
    "QUESTIONNAIRE_RUN": DemoQuestionnaireRun,
    "SELF_TRANSFER_RUN": DemoSelfTransferRun,
    "EDITING_SESSION": DemoEditingSession,
    "IMAGE_VERSION": DemoImageVersion,
    "EDIT_PLAN": DemoEditPlan,
    "EDIT_OPERATION": DemoEditOperation,
    "TOOL_RUN": DemoToolRun,
}
_EXPECTED_TARGETS: Mapping[str, str] = {
    "analysis.create": "ANALYSIS_RUN",
    "questionnaire.run.create": "QUESTIONNAIRE_RUN",
    "profile.compile": "DEMO_ACTOR",
    "editing_session.create": "EDITING_SESSION",
    "edit_plan.create": "EDIT_PLAN",
    "edit_plan.execute": "EDIT_PLAN",
    "image_version.restore": "IMAGE_VERSION",
    "profile.rebuild": "DEMO_ACTOR",
    "self_transfer.execute": "SELF_TRANSFER_RUN",
    "tool.verify": "TOOL_RUN",
    "context.compile": "DEMO_SESSION",
}
_CAPABILITIES: Mapping[str, str] = {
    "analysis.create": "P3_FACE_ANALYSIS",
    "questionnaire.run.create": "P4_QUESTIONNAIRE",
    "profile.compile": "P5_COMPILER",
    "editing_session.create": "P6_EDITING_SESSION",
    "edit_plan.create": "P6_EDIT_PLAN",
    "edit_plan.execute": "P6_EDIT_EXECUTION",
    "image_version.restore": "P6_RESTORE",
    "profile.rebuild": "P7_PROFILE_REBUILD",
    "self_transfer.execute": "P5_SELF_TRANSFER",
    "tool.verify": "P6_TOOL_VERIFY",
    "context.compile": "P7_CONTEXT_COMPILER",
}


class DemoJobError(RuntimeError):
    """Base public Demo Job lifecycle failure."""


class DemoJobInputError(DemoJobError):
    """A lifecycle command violates the frozen request boundary."""


class DemoJobUnavailable(DemoJobError):
    """The actor cannot read the requested Job authority."""


class DemoJobStateConflict(DemoJobError):
    """The requested transition is not legal from the current state."""


class DemoJobAuthorityCorruption(DemoJobError):
    """Persisted Job/binding/target authority cannot be trusted."""


@dataclass(frozen=True)
class DemoJobTargetSnapshot:
    target_type: DemoJobTargetType
    target_id: str
    authority_digest: str


@dataclass(frozen=True)
class DemoJobSnapshot:
    job_id: str
    demo_actor_id: str
    demo_session_id: str | None
    status: DemoJobStatus
    capability: str
    job_binding_digest: str
    target: DemoJobTargetSnapshot
    result_code: str | None
    finalized_at: datetime | None


class DemoJobService:
    """Read and cancel Demo Jobs through PostgreSQL-owned authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._idempotency = DemoSemanticIdempotencyCoordinator(session_factory=session_factory)
        self._now = now

    async def get(self, *, demo_actor_id: str, job_id: str) -> DemoJobSnapshot:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(job_id, "job_id")
        async with self._sessions() as session:
            return await self._load_owned_snapshot(
                session,
                demo_actor_id=demo_actor_id,
                job_id=job_id,
                lock=False,
            )

    async def cancel(
        self,
        *,
        demo_actor_id: str,
        job_id: str,
        expected_status: Literal["PENDING", "RUNNING"],
        reason: Literal["USER_REQUEST"],
        idempotency_key: str,
    ) -> DemoJobSnapshot:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(job_id, "job_id")
        if expected_status not in {"PENDING", "RUNNING"}:
            raise DemoJobInputError("expected_status must be PENDING or RUNNING")
        if reason != "USER_REQUEST":
            raise DemoJobInputError("unsupported cancellation reason")
        key_hash = idempotency_key_hash(idempotency_key)
        semantic_request = {
            "expected_status": expected_status,
            "job_id": job_id,
            "reason": reason,
        }
        request_digest = semantic_request_digest(semantic_request)

        async def create_target(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoJobSnapshot]:
            snapshot = await self._load_owned_snapshot(
                session,
                demo_actor_id=demo_actor_id,
                job_id=job_id,
                lock=True,
            )
            if snapshot.status in _TERMINAL:
                # A concurrent same-key caller may have observed the pre-transition
                # state before the winner committed.  Only that exact winner may
                # proceed to the coordinator's conflict/reload path.
                winner = await session.scalar(
                    select(DemoCommandBinding).where(
                        DemoCommandBinding.demo_actor_id == demo_actor_id,
                        DemoCommandBinding.endpoint_operation == DEMO_JOB_CANCEL_OPERATION,
                        DemoCommandBinding.idempotency_key_hash == key_hash,
                    )
                )
                if (
                    winner is None
                    or winner.request_digest != request_digest
                    or winner.response_id != job_id
                ):
                    raise DemoJobStateConflict("Demo Job is already terminal")
                return DemoIdempotencyTarget(
                    value=snapshot,
                    response_id=job_id,
                    demo_session_id=snapshot.demo_session_id,
                )
            if snapshot.status != expected_status:
                raise DemoJobStateConflict("Demo Job status differs from expected_status")

            job = await session.get(Job, job_id)
            if job is None:
                raise DemoJobAuthorityCorruption("locked Demo Job disappeared")
            now = self._normalized_now()
            if snapshot.status == "RUNNING":
                attempt = await session.scalar(
                    select(JobAttempt)
                    .where(
                        JobAttempt.job_id == job_id,
                        JobAttempt.attempt == job.attempt_count,
                    )
                    .with_for_update()
                )
                if attempt is None or attempt.status != "RUNNING":
                    raise DemoJobAuthorityCorruption(
                        "RUNNING Demo Job lacks its current RUNNING attempt"
                    )
                attempt.status = "CANCELLED"
                attempt.result_code = reason
                attempt.error_code = None
                attempt.finished_at = now
            elif job.attempt_count != 0:
                raise DemoJobAuthorityCorruption("PENDING Demo Job cannot already contain attempts")

            job.status = "CANCELLED"
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.finalized_at = now
            job.result_code = reason
            job.updated_at = now
            await session.flush()
            cancelled = await self._load_owned_snapshot(
                session,
                demo_actor_id=demo_actor_id,
                job_id=job_id,
                lock=False,
            )
            return DemoIdempotencyTarget(
                value=cancelled,
                response_id=job_id,
                demo_session_id=cancelled.demo_session_id,
            )

        async def load_target(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[DemoJobSnapshot] | None:
            if binding.response_id != job_id:
                raise DemoJobAuthorityCorruption(
                    "cancellation binding references a different Demo Job"
                )
            try:
                snapshot = await self._load_owned_snapshot(
                    session,
                    demo_actor_id=demo_actor_id,
                    job_id=binding.response_id,
                    lock=False,
                )
            except DemoJobUnavailable:
                return None
            if snapshot.status != "CANCELLED":
                raise DemoJobAuthorityCorruption("cancellation binding target is not CANCELLED")
            return DemoIdempotencyTarget(
                value=snapshot,
                response_id=snapshot.job_id,
                demo_session_id=snapshot.demo_session_id,
            )

        result = await self._idempotency.execute(
            demo_actor_id=demo_actor_id,
            endpoint_operation=DEMO_JOB_CANCEL_OPERATION,
            idempotency_key=idempotency_key,
            semantic_request=semantic_request,
            create_target=create_target,
            load_target=load_target,
        )
        return result.value

    async def _load_owned_snapshot(
        self,
        session: AsyncSession,
        *,
        demo_actor_id: str,
        job_id: str,
        lock: bool,
    ) -> DemoJobSnapshot:
        statement = (
            select(Job, DemoJobBinding)
            .join(DemoJobBinding, DemoJobBinding.job_id == Job.id)
            .where(
                Job.id == job_id,
                DemoJobBinding.demo_actor_id == demo_actor_id,
            )
        )
        if lock:
            statement = statement.with_for_update(of=Job)
        row = (await session.execute(statement)).one_or_none()
        if row is None:
            raise DemoJobUnavailable("Demo Job is unavailable")
        job, binding = row
        self._validate_binding(job, binding)
        target = await self._load_target_authority(session, binding)
        self._validate_lifecycle(job)
        return DemoJobSnapshot(
            job_id=job.id,
            demo_actor_id=binding.demo_actor_id,
            demo_session_id=binding.demo_session_id,
            status=cast(DemoJobStatus, job.status),
            capability=_CAPABILITIES[binding.endpoint_operation],
            job_binding_digest=binding.content_digest,
            target=target,
            result_code=job.result_code,
            finalized_at=job.finalized_at,
        )

    @staticmethod
    async def _load_target_authority(
        session: AsyncSession, binding: DemoJobBinding
    ) -> DemoJobTargetSnapshot:
        model = _TARGET_MODELS.get(binding.target_type)
        if model is None:
            raise DemoJobAuthorityCorruption("Demo Job target type is unsupported")
        target = await session.get(model, binding.target_id)
        if target is None:
            raise DemoJobAuthorityCorruption("Demo Job target authority is missing")
        if target.id != binding.target_id or _DIGEST.fullmatch(target.content_digest) is None:
            raise DemoJobAuthorityCorruption("Demo Job target authority is invalid")
        if binding.target_type == "DEMO_ACTOR":
            if target.id != binding.demo_actor_id:
                raise DemoJobAuthorityCorruption("Demo Job actor target ownership mismatch")
        else:
            target_actor_id = getattr(target, "demo_actor_id", None)
            if target_actor_id != binding.demo_actor_id:
                raise DemoJobAuthorityCorruption("Demo Job target actor ownership mismatch")
        if binding.demo_session_id is not None:
            session_authority = await session.get(DemoSession, binding.demo_session_id)
            if (
                session_authority is None
                or session_authority.demo_actor_id != binding.demo_actor_id
            ):
                raise DemoJobAuthorityCorruption("Demo Job Session authority is invalid")
            if binding.target_type != "DEMO_ACTOR":
                target_session_id: str | None
                if binding.target_type == "DEMO_SESSION":
                    target_session_id = target.id
                else:
                    target_session_id = cast(str | None, getattr(target, "demo_session_id", None))
                if target_session_id != binding.demo_session_id:
                    raise DemoJobAuthorityCorruption("Demo Job target Session ownership mismatch")
        return DemoJobTargetSnapshot(
            target_type=cast(DemoJobTargetType, binding.target_type),
            target_id=target.id,
            authority_digest=target.content_digest,
        )

    @staticmethod
    def _validate_binding(job: Job, binding: DemoJobBinding) -> None:
        expected_target = _EXPECTED_TARGETS.get(binding.endpoint_operation)
        capability = _CAPABILITIES.get(binding.endpoint_operation)
        if expected_target is None or capability is None or binding.target_type != expected_target:
            raise DemoJobAuthorityCorruption("Demo Job operation/target mapping is invalid")
        if job.job_type != f"demo_p3_p7.{binding.endpoint_operation}":
            raise DemoJobAuthorityCorruption("formal Job type differs from Demo binding")
        if binding.job_id != job.id:
            raise DemoJobAuthorityCorruption("Demo binding references a different Job")
        payload: dict[str, Any] = {
            "demo_actor_id": binding.demo_actor_id,
            "demo_session_id": binding.demo_session_id,
            "endpoint_operation": binding.endpoint_operation,
            "idempotency_key_hash": binding.idempotency_key_hash,
            "job_id": binding.job_id,
            "request_digest": binding.request_digest,
            "target_id": binding.target_id,
            "target_type": binding.target_type,
        }
        expected_digest = hashlib.sha256(
            DEMO_JOB_BINDING_SCHEMA.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
        ).hexdigest()
        if (
            binding.schema_version != DEMO_JOB_BINDING_SCHEMA
            or binding.canonical_payload != payload
            or binding.content_digest != expected_digest
            or _DIGEST.fullmatch(binding.idempotency_key_hash) is None
            or _DIGEST.fullmatch(binding.request_digest) is None
        ):
            raise DemoJobAuthorityCorruption("Demo Job binding authority is invalid")

    @staticmethod
    def _validate_lifecycle(job: Job) -> None:
        if job.status not in _STATUSES:
            raise DemoJobAuthorityCorruption("Demo Job status is unsupported")
        if job.status in {"PENDING", "RUNNING"}:
            if job.finalized_at is not None or job.result_code is not None:
                raise DemoJobAuthorityCorruption("active Demo Job has terminal fields")
        elif job.finalized_at is None or job.result_code is None:
            raise DemoJobAuthorityCorruption("terminal Demo Job lacks terminal fields")

    def _normalized_now(self) -> datetime:
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise DemoJobAuthorityCorruption("Demo Job clock must be timezone-aware")
        return now.astimezone(UTC)


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoJobInputError(f"{name} must be a lowercase hexadecimal ID")


__all__ = [
    "DemoIdempotencyPayloadConflict",
    "DemoJobAuthorityCorruption",
    "DemoJobInputError",
    "DemoJobService",
    "DemoJobSnapshot",
    "DemoJobStateConflict",
    "DemoJobTargetSnapshot",
    "DemoJobUnavailable",
]
