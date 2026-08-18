"""Reference-only M4 Job/Attempt envelope with bounded retry and reconciliation."""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import (
    Job,
    JobAttempt,
    LandmarkWarpPlanAuthority,
    SyntheticQARun,
    TransformRun,
    VariantSpecification,
    new_id,
)

from .task_contract import SyntheticTransformTaskMessage
from .transform_service import (
    SyntheticTransformService,
    TransformApplicationResult,
    TransformExecutionRejected,
    TransformExecutionRetryable,
)

_ID = re.compile(r"[0-9a-f]{32}\Z")
_JOB_TYPE = "synthetic_geometry_transform"
_MAX_ATTEMPTS = 4
_RetryOutcome = Literal["scheduled", "exhausted", "stale"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def _transaction(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


class M4LeaseExpired(Exception):
    """A stale at-least-once delivery reached a guarded completion boundary."""


class M4RetryableError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("synthetic M4 execution remains retryable")


@dataclass(frozen=True)
class M4TaskReservation:
    transform_run_id: str
    job_id: str
    attempt_id: str
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class M4TaskResult:
    transform_run_id: str
    job_id: str
    status: Literal[
        "variant_qa_pending",
        "transform_rejected",
        "transform_failed",
        "cancelled",
        "no_op",
    ]
    result_asset_id: str | None = None
    qa_run_id: str | None = None


class SyntheticM4OrchestrationService:
    """Keeps Celery at-least-once mechanics outside M4 domain authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        transforms: SyntheticTransformService,
        now: Callable[[], datetime] = _utcnow,
        lease_seconds: int = 300,
    ) -> None:
        if not 60 <= lease_seconds <= 900:
            raise ValueError("M4 lease duration is outside the bounded range")
        self._sessions = session_factory
        self._transforms = transforms
        self._now = now
        self._lease_seconds = lease_seconds

    async def schedule_transform(
        self, *, transform_run_id: str, request_id: str
    ) -> SyntheticTransformTaskMessage:
        self._require_id(transform_run_id)
        self._require_request_id(request_id)
        job_id = self._job_id(transform_run_id)
        async with _transaction(self._sessions) as session:
            _, _, run = await self._locked_authority_chain(session, transform_run_id)
            if run.status not in {
                "SPECIFIED",
                "RUNNING",
                "OUTPUT_STORED",
                "MEASURING",
                "COMPLETED",
            }:
                raise TransformExecutionRejected("transform_run_not_schedulable")
            job = await self._locked_job(session, job_id)
            if job is None:
                job = Job(
                    id=job_id,
                    job_type=_JOB_TYPE,
                    status="pending",
                    idempotency_key_hash=hashlib.sha256(
                        f"mirror.synthetic-m4-envelope/v1:{transform_run_id}".encode()
                    ).hexdigest(),
                    request_id=request_id,
                    payload={},
                    owner_user_id=None,
                )
                session.add(job)
                await session.flush()
            elif not self._valid_job(job):
                raise TransformExecutionRejected("m4_job_authority_conflict")
            return SyntheticTransformTaskMessage(
                transform_run_id=run.id,
                job_id=job.id,
                request_id=job.request_id,
            )

    async def execute_transform(self, message: SyntheticTransformTaskMessage) -> M4TaskResult:
        message.validate()
        reservation = await self._reserve(message.transform_run_id, message.job_id)
        if reservation is None:
            recovered = await self._recover_committed_envelope(message)
            return recovered or M4TaskResult(message.transform_run_id, message.job_id, "no_op")
        try:
            result = await self._transforms.execute(
                transform_run_id=reservation.transform_run_id,
                completion_guard=self._lease_guard(reservation),
            )
        except M4LeaseExpired:
            return M4TaskResult(message.transform_run_id, message.job_id, "no_op")
        except TransformExecutionRetryable as error:
            outcome = await self._retry(reservation, error.code)
            if outcome == "scheduled":
                raise M4RetryableError(error.code) from None
            return M4TaskResult(
                message.transform_run_id,
                message.job_id,
                "transform_failed" if outcome == "exhausted" else "no_op",
            )
        except TransformExecutionRejected as error:
            completed = await self._terminalize(
                reservation, job_status="rejected", run_status="REJECTED", code=error.code
            )
            return M4TaskResult(
                message.transform_run_id,
                message.job_id,
                "transform_rejected" if completed else "no_op",
            )
        completed = await self._complete_success(reservation, result)
        return M4TaskResult(
            message.transform_run_id,
            message.job_id,
            "variant_qa_pending" if completed else "no_op",
            result.result_asset_id if completed else None,
            result.qa_run_id if completed else None,
        )

    async def cancel(self, *, transform_run_id: str, reason_code: str) -> bool:
        self._require_id(transform_run_id)
        self._require_code(reason_code)
        job_id = self._job_id(transform_run_id)
        async with _transaction(self._sessions) as session:
            _, _, run = await self._locked_authority_chain(session, transform_run_id)
            if run.status == "CANCELLED":
                return False
            if run.status not in {"SPECIFIED", "RUNNING"} or run.result_asset_id is not None:
                raise TransformExecutionRejected("transform_cancellation_closed")
            job = await self._locked_job(session, job_id)
            attempt = await self._leased_attempt(session, job.id) if job is not None else None
            now = self._now()
            run.status = "CANCELLED"
            run.result_code = reason_code
            run.finalized_at = now
            run.updated_at = now
            if attempt is not None:
                attempt.status = "cancelled"
                attempt.result_code = reason_code
                attempt.finished_at = now
            if job is not None:
                job.status = "cancelled"
                job.lease_token = None
                job.lease_acquired_at = None
                job.lease_expires_at = None
                job.result_code = reason_code
                job.finalized_at = now
                job.updated_at = now
            await session.flush()
        await self._transforms.delete_cancelled_orphan(transform_run_id=transform_run_id)
        return True

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[SyntheticTransformTaskMessage, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("M4 reconciliation limit is outside the boundary")
        async with self._sessions() as session:
            executable = list(
                (
                    await session.scalars(
                        select(TransformRun.id)
                        .where(TransformRun.status.in_(("SPECIFIED", "RUNNING")))
                        .order_by(TransformRun.created_at, TransformRun.id)
                        .limit(limit)
                    )
                ).all()
            )
            repairable = list(
                (
                    await session.scalars(
                        select(TransformRun.id)
                        .where(TransformRun.status == "OUTPUT_STORED")
                        .where(
                            ~select(SyntheticQARun.id)
                            .where(SyntheticQARun.transform_run_id == TransformRun.id)
                            .exists()
                        )
                        .order_by(TransformRun.created_at, TransformRun.id)
                        .limit(max(0, limit - len(executable)))
                    )
                ).all()
            )
            cancelled = list(
                (
                    await session.scalars(
                        select(TransformRun.id)
                        .where(
                            TransformRun.status == "CANCELLED",
                            TransformRun.result_asset_id.is_(None),
                        )
                        .order_by(TransformRun.created_at, TransformRun.id)
                        .limit(limit)
                    )
                ).all()
            )
            committed = list(
                (
                    await session.scalars(
                        select(TransformRun.id)
                        .where(TransformRun.status.in_(("OUTPUT_STORED", "MEASURING", "COMPLETED")))
                        .order_by(TransformRun.created_at, TransformRun.id)
                        .limit(limit)
                    )
                ).all()
            )
        for run_id in repairable:
            await self._transforms.ensure_qa_handoff(transform_run_id=run_id)
        for run_id in cancelled:
            await self._transforms.delete_cancelled_orphan(transform_run_id=run_id)
        messages: list[SyntheticTransformTaskMessage] = []
        for run_id in executable + committed:
            job_id = self._job_id(run_id)
            async with self._sessions() as session:
                job = await session.get(Job, job_id)
                if run_id in committed and job is not None and job.status == "succeeded":
                    continue
            messages.append(
                await self.schedule_transform(transform_run_id=run_id, request_id="m4-reconcile")
            )
        return tuple(messages)

    async def _recover_committed_envelope(
        self, message: SyntheticTransformTaskMessage
    ) -> M4TaskResult | None:
        async with _transaction(self._sessions) as session:
            _, _, run = await self._locked_authority_chain(session, message.transform_run_id)
            if run.status not in {"OUTPUT_STORED", "MEASURING", "COMPLETED"}:
                return None
            if run.result_asset_id is None:
                raise TransformExecutionRejected("transform_result_authority_missing")
            qa_run = cast(
                SyntheticQARun | None,
                await session.scalar(
                    select(SyntheticQARun)
                    .where(SyntheticQARun.transform_run_id == run.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            if qa_run is None:
                return None
            job = await self._locked_job(session, message.job_id)
            if job is None or not self._valid_job(job):
                raise TransformExecutionRejected("m4_job_not_found")
            if job.status == "succeeded":
                return M4TaskResult(
                    run.id,
                    job.id,
                    "no_op",
                    run.result_asset_id,
                    qa_run.id,
                )
            if job.status in {"rejected", "failed", "cancelled"}:
                raise TransformExecutionRejected("m4_job_terminal_conflict")
            attempt = await self._leased_attempt(session, job.id)
            now = self._now()
            if attempt is not None:
                attempt.status = "succeeded"
                attempt.result_code = "variant_qa_pending"
                attempt.finished_at = now
            job.status = "succeeded"
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.result_code = "variant_qa_pending"
            job.finalized_at = now
            job.updated_at = now
            await session.flush()
            return M4TaskResult(
                run.id,
                job.id,
                "variant_qa_pending",
                run.result_asset_id,
                qa_run.id,
            )

    async def _reserve(self, transform_run_id: str, job_id: str) -> M4TaskReservation | None:
        self._require_id(transform_run_id)
        self._require_id(job_id)
        if job_id != self._job_id(transform_run_id):
            raise TransformExecutionRejected("m4_task_job_mismatch")
        now = self._now()
        async with _transaction(self._sessions) as session:
            _, _, run = await self._locked_authority_chain(session, transform_run_id)
            if run.status not in {"SPECIFIED", "RUNNING"}:
                return None
            job = await self._locked_job(session, job_id)
            if job is None or not self._valid_job(job):
                raise TransformExecutionRejected("m4_job_not_found")
            if job.status in {"succeeded", "rejected", "failed", "cancelled"}:
                return None
            if (
                job.status == "leased"
                and job.lease_expires_at is not None
                and job.lease_expires_at > now
            ):
                return None
            job.attempt_count += 1
            token = secrets.token_hex(32)
            expires = now + timedelta(seconds=self._lease_seconds)
            job.status = "leased"
            job.lease_token = token
            job.lease_acquired_at = now
            job.lease_expires_at = expires
            job.finalized_at = None
            job.result_code = None
            job.updated_at = now
            attempt = JobAttempt(
                id=new_id(),
                job_id=job.id,
                attempt=job.attempt_count,
                status="leased",
                lease_token=token,
                started_at=now,
            )
            session.add(attempt)
            await session.flush()
            return M4TaskReservation(run.id, job.id, attempt.id, token, expires)

    def _lease_guard(
        self, reservation: M4TaskReservation
    ) -> Callable[[AsyncSession], Awaitable[None]]:
        async def guard(session: AsyncSession) -> None:
            job = await self._locked_job(session, reservation.job_id)
            attempt = cast(
                JobAttempt | None,
                await session.scalar(
                    select(JobAttempt)
                    .where(JobAttempt.id == reservation.attempt_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            if not self._reservation_is_current(job, attempt, reservation, now=self._now()):
                raise M4LeaseExpired

        return guard

    async def _complete_success(
        self, reservation: M4TaskReservation, result: TransformApplicationResult
    ) -> bool:
        async with _transaction(self._sessions) as session:
            _, _, run = await self._locked_authority_chain(session, reservation.transform_run_id)
            if run.status not in {"OUTPUT_STORED", "MEASURING", "COMPLETED"}:
                return False
            if not await self._guard_is_current(session, reservation):
                return False
            job = await self._locked_job(session, reservation.job_id)
            attempt = await session.get(JobAttempt, reservation.attempt_id)
            if job is None or attempt is None:
                return False
            now = self._now()
            attempt.status = "succeeded"
            attempt.result_code = "variant_qa_pending"
            attempt.finished_at = now
            job.status = "succeeded"
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.result_code = "variant_qa_pending"
            job.finalized_at = now
            job.updated_at = now
            await session.flush()
            return True

    async def _terminalize(
        self,
        reservation: M4TaskReservation,
        *,
        job_status: Literal["rejected", "failed"],
        run_status: Literal["REJECTED", "FAILED"],
        code: str,
    ) -> bool:
        self._require_code(code)
        async with _transaction(self._sessions) as session:
            _, _, run = await self._locked_authority_chain(session, reservation.transform_run_id)
            if not await self._guard_is_current(session, reservation):
                return False
            if run.status == "SPECIFIED":
                run.status = "RUNNING"
                run.started_at = self._now()
                run.updated_at = self._now()
                await session.flush()
            if run.status != "RUNNING":
                return False
            job = await self._locked_job(session, reservation.job_id)
            attempt = await session.get(JobAttempt, reservation.attempt_id)
            if job is None or attempt is None:
                return False
            now = self._now()
            run.status = run_status
            run.result_code = code
            run.finalized_at = now
            run.updated_at = now
            attempt.status = job_status
            attempt.result_code = code
            attempt.error_code = code if job_status == "failed" else None
            attempt.finished_at = now
            job.status = job_status
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.result_code = code
            job.finalized_at = now
            job.updated_at = now
            await session.flush()
            return True

    async def _retry(self, reservation: M4TaskReservation, code: str) -> _RetryOutcome:
        self._require_code(code)
        async with _transaction(self._sessions) as session:
            _, _, run = await self._locked_authority_chain(session, reservation.transform_run_id)
            job = await self._locked_job(session, reservation.job_id)
            attempt = cast(
                JobAttempt | None,
                await session.scalar(
                    select(JobAttempt)
                    .where(JobAttempt.id == reservation.attempt_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            now = self._now()
            if not self._reservation_is_current(job, attempt, reservation, now=now):
                return "stale"
            assert job is not None and attempt is not None
            attempt.status = "retryable_failure"
            attempt.error_code = code
            attempt.finished_at = now
            if job.attempt_count < _MAX_ATTEMPTS:
                job.status = "pending"
                job.lease_token = None
                job.lease_acquired_at = None
                job.lease_expires_at = None
                job.updated_at = now
                await session.flush()
                return "scheduled"
            if run.status == "SPECIFIED":
                run.status = "RUNNING"
                run.started_at = now
                run.updated_at = now
                await session.flush()
            if run.status != "RUNNING":
                raise TransformExecutionRejected("transform_retry_authority_missing")
            run.status = "FAILED"
            run.result_code = code
            run.finalized_at = now
            run.updated_at = now
            attempt.status = "failed"
            attempt.result_code = code
            job.status = "failed"
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.result_code = code
            job.finalized_at = now
            job.updated_at = now
            await session.flush()
            return "exhausted"

    async def _guard_is_current(
        self, session: AsyncSession, reservation: M4TaskReservation
    ) -> bool:
        try:
            await self._lease_guard(reservation)(session)
        except M4LeaseExpired:
            return False
        return True

    @staticmethod
    async def _locked_authority_chain(
        session: AsyncSession, run_id: str
    ) -> tuple[VariantSpecification, LandmarkWarpPlanAuthority, TransformRun]:
        specification_id = cast(
            str | None,
            await session.scalar(
                select(TransformRun.variant_specification_id).where(TransformRun.id == run_id)
            ),
        )
        if specification_id is None:
            raise TransformExecutionRejected("transform_run_not_found")
        specification = cast(
            VariantSpecification | None,
            await session.scalar(
                select(VariantSpecification)
                .where(VariantSpecification.id == specification_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if specification is None:
            raise TransformExecutionRejected("variant_specification_not_found")
        plan = cast(
            LandmarkWarpPlanAuthority | None,
            await session.scalar(
                select(LandmarkWarpPlanAuthority)
                .where(LandmarkWarpPlanAuthority.variant_specification_id == specification.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if plan is None:
            raise TransformExecutionRejected("warp_plan_not_found")
        run = cast(
            TransformRun | None,
            await session.scalar(
                select(TransformRun)
                .where(
                    TransformRun.id == run_id,
                    TransformRun.variant_specification_id == specification.id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if run is None:
            raise TransformExecutionRejected("transform_run_authority_conflict")
        return specification, plan, run

    @staticmethod
    async def _locked_job(session: AsyncSession, job_id: str) -> Job | None:
        return cast(
            Job | None,
            await session.scalar(
                select(Job)
                .where(Job.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    async def _leased_attempt(session: AsyncSession, job_id: str) -> JobAttempt | None:
        return cast(
            JobAttempt | None,
            await session.scalar(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_id, JobAttempt.status == "leased")
                .order_by(JobAttempt.attempt.desc())
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    def _valid_job(job: Job) -> bool:
        return bool(
            job.job_type == _JOB_TYPE
            and job.owner_user_id is None
            and job.ingestion_upload_intent_id is None
            and job.result_asset_id is None
            and job.payload == {}
        )

    @staticmethod
    def _reservation_is_current(
        job: Job | None,
        attempt: JobAttempt | None,
        reservation: M4TaskReservation,
        *,
        now: datetime,
    ) -> bool:
        return bool(
            job is not None
            and attempt is not None
            and job.status == "leased"
            and job.lease_token == reservation.lease_token
            and job.lease_expires_at is not None
            and job.lease_expires_at > now
            and attempt.job_id == job.id
            and attempt.status == "leased"
            and attempt.lease_token == reservation.lease_token
        )

    @staticmethod
    def _job_id(transform_run_id: str) -> str:
        return hashlib.sha256(
            f"mirror.synthetic-m4-envelope/v1:{transform_run_id}".encode()
        ).hexdigest()[:32]

    @staticmethod
    def _require_id(value: str) -> None:
        if _ID.fullmatch(value) is None:
            raise ValueError("M4 identifiers must be opaque")

    @staticmethod
    def _require_request_id(value: str) -> None:
        if not 8 <= len(value) <= 128 or any(character in value for character in "\r\n\0"):
            raise ValueError("M4 request ID is outside the safe boundary")

    @staticmethod
    def _require_code(value: str) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", value) is None:
            raise ValueError("M4 reason code is outside the safe boundary")
