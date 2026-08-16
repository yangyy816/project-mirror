"""Reference-only M3 worker orchestration and canonical identity registration.

`Job` and `JobAttempt` are execution envelopes only.  The M3 authority remains the
immutable source/Asset/QA chain; jobs intentionally have an empty payload and a deterministic
opaque ID derived from that authority.
"""

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
    Asset,
    Job,
    JobAttempt,
    SyntheticAssetRecord,
    SyntheticIdentity,
    SyntheticQAMeasurement,
    SyntheticQAPolicy,
    SyntheticQAReviewDecision,
    SyntheticQARun,
    new_id,
)
from mirror_api.synthetic_dataset.domain import CanonicalPolicy
from mirror_api.synthetic_dataset.normalization_service import SyntheticNormalizationService
from mirror_api.synthetic_dataset.normalization_types import (
    NormalizationRejected,
    NormalizationRetryableError,
)
from mirror_api.synthetic_dataset.qa_repository import SyntheticQARepository
from mirror_api.synthetic_dataset.qa_service import SyntheticQAService
from mirror_api.synthetic_dataset.qa_types import (
    QAEvaluation,
    QAMeasurementEvidence,
    QAOutcome,
    QAPolicyDefinition,
    QAReviewEvidence,
    ReviewDecision,
    ThresholdOutcome,
    evaluate_qa,
)
from mirror_api.synthetic_dataset.task_contract import (
    SyntheticNormalizationTaskMessage,
    SyntheticQATaskMessage,
)

_ID = re.compile(r"[0-9a-f]{32}\Z")
_CODE = re.compile(r"[a-z][a-z0-9_]{2,63}\Z")
_TASK_KIND = Literal["normalization", "qa"]
_RETRY_OUTCOME = Literal["scheduled", "exhausted", "stale"]
_JOB_TYPE: dict[_TASK_KIND, str] = {
    "normalization": "synthetic_normalization",
    "qa": "synthetic_qa",
}
_MAX_ATTEMPTS = 4


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


class M3OperationRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code if _CODE.fullmatch(code) else "m3_operation_rejected"
        super().__init__("synthetic M3 operation was rejected")


class M3LeaseExpired(Exception):
    """A stale at-least-once delivery reached a database completion boundary."""


class M3RetryableError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code if _CODE.fullmatch(code) else "m3_execution_unavailable"
        super().__init__("synthetic M3 execution remains retryable")


@dataclass(frozen=True)
class M3TaskReservation:
    kind: _TASK_KIND
    target_id: str
    job_id: str
    attempt_id: str
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class M3TaskResult:
    target_id: str
    job_id: str
    status: Literal[
        "normalized", "normalization_failed", "qa_passed", "qa_rejected", "qa_failed", "no_op"
    ]
    identity_id: str | None = None


class CanonicalIdentityRegistrationService:
    """Rechecks immutable QA authority then creates exactly one canonical identity.

    Lock order is always SyntheticAssetRecord -> Asset -> SyntheticQARun.  The policy/evidence
    rows are append-only and are read only after the run lock.  PostgreSQL guards remain the
    final authority, while this service makes idempotency and stale-delivery behaviour explicit.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._sessions = session_factory
        self._now = now

    async def register(
        self,
        *,
        record_id: str,
        qa_run_id: str,
        completion_guard: Callable[[AsyncSession], Awaitable[None]] | None = None,
    ) -> tuple[str, bool]:
        self._require_id(record_id)
        self._require_id(qa_run_id)
        async with _transaction(self._sessions) as session:
            record = await self._locked_record(session, record_id)
            if record is None:
                raise M3OperationRejected("synthetic_record_not_found")
            if record.normalized_asset_id is None:
                raise M3OperationRejected("normalized_asset_not_found")
            asset = await self._locked_asset(session, record.normalized_asset_id)
            run = await self._locked_run(session, qa_run_id)
            if asset is None or run is None:
                raise M3OperationRejected("canonical_qa_authority_missing")
            if record.status == "IDENTITY_REGISTERED":
                identity = await self._identity_for_asset(session, asset.id)
                if identity is None or identity.accepted_qa_run_id != run.id:
                    raise M3OperationRejected("canonical_identity_authority_missing")
                return identity.id, False
            if (
                record.status != "QA_PASSED"
                or run.status != "PASSED"
                or run.synthetic_asset_record_id != record.id
                or run.normalized_asset_id != asset.id
            ):
                raise M3OperationRejected("canonical_qa_not_passed")
            self._validate_asset(asset)
            await self._validate_qa_authority(session, run)
            if completion_guard is not None:
                await completion_guard(session)
            existing = await self._identity_for_asset(session, asset.id)
            if existing is not None:
                if existing.accepted_qa_run_id != run.id:
                    raise M3OperationRejected("canonical_identity_conflict")
                return existing.id, False
            identity = SyntheticIdentity(
                id=new_id(),
                authority_kind="CANONICAL_QA",
                canonical_asset_id=asset.id,
                accepted_qa_run_id=run.id,
                generator_provider=None,
                generator_model=None,
                prompt_version=None,
                provenance=None,
                adult_synthetic_attested=True,
                created_at=self._now(),
            )
            session.add(identity)
            await session.flush()
            return identity.id, True

    async def _validate_qa_authority(self, session: AsyncSession, run: SyntheticQARun) -> None:
        policy = cast(
            SyntheticQAPolicy | None,
            await session.scalar(
                select(SyntheticQAPolicy)
                .where(SyntheticQAPolicy.id == run.qa_policy_id)
                .execution_options(populate_existing=True)
            ),
        )
        if policy is None or policy.approval_status != "APPROVED":
            raise M3OperationRejected("qa_policy_not_approved")
        try:
            CanonicalPolicy.validate_external(
                schema_version=policy.schema_version,
                version=policy.version,
                content=policy.content,
                content_digest=policy.content_digest,
            )
            definition = QAPolicyDefinition.parse(policy.content)
        except (TypeError, ValueError):
            raise M3OperationRejected("qa_policy_authority_invalid") from None
        measurements = list(
            (
                await session.scalars(
                    select(SyntheticQAMeasurement)
                    .where(SyntheticQAMeasurement.qa_run_id == run.id)
                    .order_by(SyntheticQAMeasurement.id)
                )
            ).all()
        )
        reviews = list(
            (
                await session.scalars(
                    select(SyntheticQAReviewDecision)
                    .where(SyntheticQAReviewDecision.qa_run_id == run.id)
                    .order_by(SyntheticQAReviewDecision.id)
                )
            ).all()
        )
        try:
            evaluation = evaluate_qa(
                requirements=definition.requirements,
                measurements=tuple(
                    QAMeasurementEvidence(
                        measurement_kind=value.measurement_kind,
                        measurement_code=value.measurement_code,
                        payload=value.payload,
                        algorithm_reference=value.algorithm_reference,
                        algorithm_version=value.algorithm_version,
                        confidence=float(value.confidence)
                        if value.confidence is not None
                        else None,
                        hard_gate=value.hard_gate,
                        threshold_outcome=ThresholdOutcome(value.threshold_outcome),
                        reason_code=value.reason_code,
                    )
                    for value in measurements
                ),
                reviews=tuple(
                    QAReviewEvidence(
                        review_kind=value.review_kind,
                        decision=ReviewDecision(value.decision),
                        reason_code=value.reason_code,
                        actor_reference=value.actor_reference,
                    )
                    for value in reviews
                ),
            )
        except (TypeError, ValueError):
            raise M3OperationRejected("qa_evidence_authority_invalid") from None
        if evaluation.outcome is not QAOutcome.PASSED:
            raise M3OperationRejected("qa_required_evidence_unresolved")

    @staticmethod
    async def _locked_record(session: AsyncSession, record_id: str) -> SyntheticAssetRecord | None:
        return cast(
            SyntheticAssetRecord | None,
            await session.scalar(
                select(SyntheticAssetRecord)
                .where(SyntheticAssetRecord.id == record_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    async def _locked_asset(session: AsyncSession, asset_id: str) -> Asset | None:
        return cast(
            Asset | None,
            await session.scalar(
                select(Asset)
                .where(Asset.id == asset_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    async def _locked_run(session: AsyncSession, run_id: str) -> SyntheticQARun | None:
        return cast(
            SyntheticQARun | None,
            await session.scalar(
                select(SyntheticQARun)
                .where(SyntheticQARun.id == run_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    async def _identity_for_asset(session: AsyncSession, asset_id: str) -> SyntheticIdentity | None:
        return cast(
            SyntheticIdentity | None,
            await session.scalar(
                select(SyntheticIdentity)
                .where(SyntheticIdentity.canonical_asset_id == asset_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    def _validate_asset(asset: Asset) -> None:
        if (
            asset.owner_user_id is not None
            or asset.asset_role != "synthetic"
            or not asset.synthetic
            or asset.internal_purpose != "synthetic_dataset"
            or asset.deleted_at is not None
        ):
            raise M3OperationRejected("canonical_asset_invalid")

    @staticmethod
    def _require_id(value: str) -> None:
        if _ID.fullmatch(value) is None:
            raise ValueError("M3 identifiers must be opaque")


class SyntheticM3OrchestrationService:
    """Owns M3 envelope leases, retries and reconciliation, never M3 domain authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        normalizer: SyntheticNormalizationService,
        now: Callable[[], datetime] = _utcnow,
        lease_seconds: int = 300,
    ) -> None:
        if not 60 <= lease_seconds <= 900:
            raise ValueError("M3 lease duration is outside the bounded range")
        self._sessions = session_factory
        self._normalizer = normalizer
        self._now = now
        self._lease_seconds = lease_seconds
        self._identity = CanonicalIdentityRegistrationService(
            session_factory=session_factory, now=now
        )

    async def schedule_normalization(
        self, *, record_id: str, request_id: str
    ) -> SyntheticNormalizationTaskMessage:
        job = await self._ensure_job("normalization", record_id, request_id)
        return SyntheticNormalizationTaskMessage(
            record_id=record_id, job_id=job.id, request_id=job.request_id
        )

    async def schedule_qa(self, *, qa_run_id: str, request_id: str) -> SyntheticQATaskMessage:
        job = await self._ensure_job("qa", qa_run_id, request_id)
        return SyntheticQATaskMessage(qa_run_id=qa_run_id, job_id=job.id, request_id=job.request_id)

    async def execute_normalization(
        self, message: SyntheticNormalizationTaskMessage
    ) -> M3TaskResult:
        message.validate()
        reservation = await self._reserve("normalization", message.record_id, message.job_id)
        if reservation is None:
            return M3TaskResult(message.record_id, message.job_id, "no_op")
        guard = self._lease_guard(reservation)
        try:
            result = await self._normalizer.normalize_record(
                record_id=reservation.target_id, completion_guard=guard
            )
        except M3LeaseExpired:
            return M3TaskResult(message.record_id, message.job_id, "no_op")
        except NormalizationRetryableError as error:
            retry = await self._retry(reservation, error.code)
            if retry == "scheduled":
                raise M3RetryableError(error.code) from None
            return M3TaskResult(
                message.record_id,
                message.job_id,
                "normalization_failed" if retry == "exhausted" else "no_op",
            )
        except NormalizationRejected as error:
            completed = await self._complete(reservation, "failed", error.code)
            return M3TaskResult(
                message.record_id,
                message.job_id,
                "normalization_failed" if completed else "no_op",
            )
        if result.status == "NORMALIZED":
            completed = await self._complete(reservation, "succeeded", "normalized")
            return M3TaskResult(
                message.record_id, message.job_id, "normalized" if completed else "no_op"
            )
        completed = await self._complete(
            reservation, "failed", result.result_code or "normalization_failed"
        )
        return M3TaskResult(
            message.record_id,
            message.job_id,
            "normalization_failed" if completed else "no_op",
        )

    async def execute_qa(self, message: SyntheticQATaskMessage) -> M3TaskResult:
        message.validate()
        reservation = await self._reserve("qa", message.qa_run_id, message.job_id)
        if reservation is None:
            return M3TaskResult(message.qa_run_id, message.job_id, "no_op")
        try:
            evaluation = await self._finalize_qa(reservation)
        except M3LeaseExpired:
            return M3TaskResult(message.qa_run_id, message.job_id, "no_op")
        except M3RetryableError as error:
            retry = await self._retry(reservation, error.code)
            if retry == "scheduled":
                raise
            return M3TaskResult(
                message.qa_run_id,
                message.job_id,
                "qa_failed" if retry == "exhausted" else "no_op",
            )
        except M3OperationRejected as error:
            completed = await self._complete(reservation, "failed", error.code)
            return M3TaskResult(
                message.qa_run_id, message.job_id, "qa_failed" if completed else "no_op"
            )
        if evaluation.outcome is QAOutcome.REJECTED:
            completed = await self._complete(
                reservation, "rejected", evaluation.reason_code or "qa_rejected"
            )
            return M3TaskResult(
                message.qa_run_id, message.job_id, "qa_rejected" if completed else "no_op"
            )
        try:
            identity_id, _ = await self._identity.register(
                record_id=await self._record_for_run(reservation.target_id),
                qa_run_id=reservation.target_id,
                completion_guard=self._lease_guard(reservation),
            )
        except M3LeaseExpired:
            return M3TaskResult(message.qa_run_id, message.job_id, "no_op")
        except M3OperationRejected as error:
            completed = await self._complete(reservation, "failed", error.code)
            return M3TaskResult(
                message.qa_run_id, message.job_id, "qa_failed" if completed else "no_op"
            )
        completed = await self._complete(reservation, "succeeded", "identity_registered")
        return M3TaskResult(
            message.qa_run_id,
            message.job_id,
            "qa_passed" if completed else "no_op",
            identity_id if completed else None,
        )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[SyntheticNormalizationTaskMessage | SyntheticQATaskMessage, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("M3 reconciliation limit is outside the boundary")
        async with self._sessions() as session:
            records = list(
                (
                    await session.scalars(
                        select(SyntheticAssetRecord.id)
                        .where(
                            SyntheticAssetRecord.status.in_(
                                ("NORMALIZATION_PENDING", "NORMALIZING")
                            )
                        )
                        .order_by(SyntheticAssetRecord.created_at, SyntheticAssetRecord.id)
                        .limit(limit)
                    )
                ).all()
            )
            remaining = limit - len(records)
            runs: list[str] = []
            if remaining:
                runs = list(
                    (
                        await session.scalars(
                            select(SyntheticQARun.id)
                            .join(
                                SyntheticAssetRecord,
                                SyntheticAssetRecord.id == SyntheticQARun.synthetic_asset_record_id,
                            )
                            .where(
                                SyntheticQARun.status.in_(("PENDING", "RUNNING"))
                                | (
                                    (SyntheticQARun.status == "PASSED")
                                    & (SyntheticAssetRecord.status == "QA_PASSED")
                                )
                            )
                            .order_by(SyntheticQARun.created_at, SyntheticQARun.id)
                            .limit(remaining)
                        )
                    ).all()
                )
        messages: list[SyntheticNormalizationTaskMessage | SyntheticQATaskMessage] = []
        for record_id in records:
            messages.append(
                await self.schedule_normalization(record_id=record_id, request_id="m3-reconcile")
            )
        for run_id in runs:
            messages.append(await self.schedule_qa(qa_run_id=run_id, request_id="m3-reconcile"))
        return tuple(messages)

    async def _ensure_job(self, kind: _TASK_KIND, target_id: str, request_id: str) -> Job:
        self._require_id(target_id)
        self._require_request_id(request_id)
        job_id = self._job_id(kind, target_id)
        async with _transaction(self._sessions) as session:
            job = await self._locked_job(session, job_id)
            if job is not None:
                if (
                    job.job_type != _JOB_TYPE[kind]
                    or job.owner_user_id is not None
                    or job.payload != {}
                ):
                    raise M3OperationRejected("m3_job_authority_conflict")
                return job
            job = Job(
                id=job_id,
                job_type=_JOB_TYPE[kind],
                status="pending",
                idempotency_key_hash=hashlib.sha256(
                    f"m3-envelope-v1:{kind}:{target_id}".encode()
                ).hexdigest(),
                request_id=request_id,
                payload={},
                owner_user_id=None,
            )
            session.add(job)
            await session.flush()
            return job

    async def _reserve(
        self, kind: _TASK_KIND, target_id: str, job_id: str
    ) -> M3TaskReservation | None:
        self._require_id(target_id)
        self._require_id(job_id)
        if job_id != self._job_id(kind, target_id):
            raise M3OperationRejected("m3_task_job_mismatch")
        now = self._now()
        async with _transaction(self._sessions) as session:
            # Domain authority is always locked before its generic execution envelope.  The
            # completion paths use the same order, preventing reserve/complete deadlocks.
            if kind == "normalization":
                record = await self._locked_record(session, target_id)
                if record is None or record.status not in {"NORMALIZATION_PENDING", "NORMALIZING"}:
                    return None
            else:
                run = await self._locked_run(session, target_id)
                if run is None or run.status not in {"PENDING", "RUNNING", "PASSED"}:
                    return None
            job = await self._locked_job(session, job_id)
            if (
                job is None
                or job.job_type != _JOB_TYPE[kind]
                or job.owner_user_id is not None
                or job.payload != {}
            ):
                raise M3OperationRejected("m3_job_not_found")
            if job.status in {"succeeded", "rejected", "failed"}:
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
            return M3TaskReservation(kind, target_id, job.id, attempt.id, token, expires)

    async def _finalize_qa(self, reservation: M3TaskReservation) -> QAEvaluation:
        try:
            async with _transaction(self._sessions) as session:
                service = SyntheticQAService(SyntheticQARepository(session))
                started = await service.start(run_id=reservation.target_id)
                if not started:
                    run = await SyntheticQARepository(session).locked_run(reservation.target_id)
                    if run is None:
                        raise M3OperationRejected("qa_run_not_found")
                    if run.status == "PASSED":
                        return QAEvaluation(QAOutcome.PASSED, None, ())
                    if run.status == "REJECTED":
                        return QAEvaluation(QAOutcome.REJECTED, run.result_code, ())
                    raise M3OperationRejected("qa_run_state_invalid")
                evaluation = await service.finalize(run_id=reservation.target_id)
                await self._lease_guard(reservation)(session)
                return evaluation
        except M3LeaseExpired:
            raise
        except M3OperationRejected:
            raise
        except Exception as error:
            raise M3RetryableError("qa_execution_unavailable") from error

    async def _record_for_run(self, qa_run_id: str) -> str:
        async with self._sessions() as session:
            run = cast(
                SyntheticQARun | None,
                await session.scalar(select(SyntheticQARun).where(SyntheticQARun.id == qa_run_id)),
            )
            if run is None:
                raise M3OperationRejected("qa_run_not_found")
            return run.synthetic_asset_record_id

    def _lease_guard(
        self, reservation: M3TaskReservation
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
            if (
                job is None
                or attempt is None
                or job.status != "leased"
                or job.lease_token != reservation.lease_token
                or job.lease_expires_at is None
                or job.lease_expires_at <= self._now()
                or attempt.job_id != job.id
                or attempt.status != "leased"
                or attempt.lease_token != reservation.lease_token
            ):
                raise M3LeaseExpired

        return guard

    async def _complete(self, reservation: M3TaskReservation, status: str, code: str) -> bool:
        async with _transaction(self._sessions) as session:
            try:
                await self._lease_guard(reservation)(session)
            except M3LeaseExpired:
                return False
            job = await self._locked_job(session, reservation.job_id)
            attempt = cast(JobAttempt | None, await session.get(JobAttempt, reservation.attempt_id))
            if job is None or attempt is None:
                return False
            now = self._now()
            attempt.status = status
            attempt.result_code = code
            attempt.error_code = None if status != "failed" else code
            attempt.finished_at = now
            job.status = status
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.result_code = code
            job.finalized_at = now
            job.updated_at = now
            await session.flush()
            return True

    async def _retry(self, reservation: M3TaskReservation, code: str) -> _RETRY_OUTCOME:
        async with _transaction(self._sessions) as session:
            record: SyntheticAssetRecord | None = None
            run: SyntheticQARun | None = None
            if reservation.kind == "normalization":
                record = await self._locked_record(session, reservation.target_id)
            else:
                run = await self._locked_run(session, reservation.target_id)
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
            attempt.status = "failed"
            attempt.result_code = code
            if reservation.kind == "normalization":
                if record is None or record.status != "NORMALIZING":
                    raise M3OperationRejected("normalization_retry_authority_missing")
                record.status = "NORMALIZATION_FAILED"
                record.result_code = code
            else:
                if run is None or run.status not in {"PENDING", "RUNNING"}:
                    raise M3OperationRejected("qa_retry_authority_missing")
                qa_service = SyntheticQAService(SyntheticQARepository(session))
                if run.status == "PENDING":
                    await qa_service.start(run_id=run.id)
                await qa_service.fail_execution(run_id=run.id, reason_code=code)
            job.status = "failed"
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.result_code = code
            job.finalized_at = now
            job.updated_at = now
            await session.flush()
            return "exhausted"

    @staticmethod
    def _reservation_is_current(
        job: Job | None,
        attempt: JobAttempt | None,
        reservation: M3TaskReservation,
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
    async def _locked_record(session: AsyncSession, record_id: str) -> SyntheticAssetRecord | None:
        return cast(
            SyntheticAssetRecord | None,
            await session.scalar(
                select(SyntheticAssetRecord)
                .where(SyntheticAssetRecord.id == record_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    async def _locked_run(session: AsyncSession, run_id: str) -> SyntheticQARun | None:
        return cast(
            SyntheticQARun | None,
            await session.scalar(
                select(SyntheticQARun)
                .where(SyntheticQARun.id == run_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    def _job_id(kind: _TASK_KIND, target_id: str) -> str:
        return hashlib.sha256(
            f"mirror.synthetic-m3-envelope/v1:{kind}:{target_id}".encode()
        ).hexdigest()[:32]

    @staticmethod
    def _require_id(value: str) -> None:
        if _ID.fullmatch(value) is None:
            raise ValueError("M3 identifiers must be opaque")

    @staticmethod
    def _require_request_id(value: str) -> None:
        if not 8 <= len(value) <= 128 or any(character in value for character in "\r\n\0"):
            raise ValueError("M3 request ID is outside the safe boundary")
