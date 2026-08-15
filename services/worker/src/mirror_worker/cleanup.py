from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from mirror_api.models import AuditLog, Job, UploadIntent, UploadIntentEvent, new_id
from mirror_api.providers.base import ObjectStorageProvider
from mirror_api.providers.local import sanitized_object_key_for_job
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_worker.ingestion import CleanupResult, RetryableWorkerFailure, SweepResult

_TERMINAL_JOB_STATUSES = ("promoted", "rejected", "cancelled")


class SqlAlchemyIngestionCleanup:
    """Idempotent object cleanup derived from authoritative PostgreSQL state."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: ObjectStorageProvider,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._storage = storage
        self._now = now or (lambda: datetime.now(UTC))

    async def cleanup_job(self, *, job_id: str) -> CleanupResult:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(Job.status, UploadIntent.object_key)
                    .join(
                        UploadIntent,
                        (UploadIntent.id == Job.ingestion_upload_intent_id)
                        & (UploadIntent.owner_user_id == Job.owner_user_id),
                    )
                    .where(Job.id == job_id, Job.job_type == "asset_ingestion")
                )
            ).one_or_none()
        if row is None or row.status not in _TERMINAL_JOB_STATUSES:
            return CleanupResult(status="no_op")
        try:
            quarantine_result = await self._storage.delete_quarantine_object(
                object_key=cast(str, row.object_key)
            )
            sanitized_result = None
            if row.status in ("rejected", "cancelled"):
                sanitized_result = await self._storage.delete_sanitized_object(
                    object_key=sanitized_object_key_for_job(job_id)
                )
        except Exception as exc:
            raise RetryableWorkerFailure("private object cleanup remains retryable") from exc
        return CleanupResult(
            status=cast(str, row.status),
            quarantine_result=quarantine_result,
            sanitized_result=sanitized_result,
        )

    async def sweep(self, *, limit: int = 100) -> SweepResult:
        if limit < 1 or limit > 1_000:
            raise ValueError("cleanup limit must be between 1 and 1000")
        now = self._now()
        terminal_job_ids = await self._terminal_job_ids(limit=limit)
        for job_id in terminal_job_ids:
            await self.cleanup_job(job_id=job_id)
        expired = await self._tombstone_expired_intents(now=now, limit=limit)
        for _, object_key in expired:
            try:
                await self._storage.delete_quarantine_object(object_key=object_key)
            except Exception as exc:
                raise RetryableWorkerFailure(
                    "expired quarantine cleanup remains retryable"
                ) from exc
        return SweepResult(
            terminal_jobs_checked=len(terminal_job_ids),
            expired_intents_tombstoned=sum(1 for was_tombstoned, _ in expired if was_tombstoned),
        )

    async def _terminal_job_ids(self, *, limit: int) -> tuple[str, ...]:
        async with self._sessions() as session:
            return tuple(
                (
                    await session.scalars(
                        select(Job.id)
                        .where(
                            Job.job_type == "asset_ingestion",
                            Job.status.in_(_TERMINAL_JOB_STATUSES),
                        )
                        .order_by(Job.finalized_at, Job.id)
                        .limit(limit)
                    )
                ).all()
            )

    async def _tombstone_expired_intents(
        self, *, now: datetime, limit: int
    ) -> tuple[tuple[bool, str], ...]:
        async with self._sessions() as session:
            intents = list(
                (
                    await session.scalars(
                        select(UploadIntent)
                        .outerjoin(Job, Job.ingestion_upload_intent_id == UploadIntent.id)
                        .where(
                            Job.id.is_(None),
                            UploadIntent.quarantine_retention_deadline.is_not(None),
                            UploadIntent.quarantine_retention_deadline <= now,
                            or_(
                                UploadIntent.status == "uploaded_unverified",
                                UploadIntent.status == "expired",
                            ),
                        )
                        .order_by(UploadIntent.quarantine_retention_deadline, UploadIntent.id)
                        .limit(limit)
                        .with_for_update(skip_locked=True, of=UploadIntent)
                    )
                ).all()
            )
            results: list[tuple[bool, str]] = []
            for intent in intents:
                tombstoned = intent.status == "uploaded_unverified"
                if tombstoned:
                    intent.status = "expired"
                    intent.expired_at = now
                    intent.updated_at = now
                    session.add(
                        UploadIntentEvent(
                            id=new_id(),
                            upload_intent_id=intent.id,
                            event_type="expired",
                            request_id=f"retention-{intent.id}",
                            metadata_json={"event": "expired"},
                            occurred_at=now,
                        )
                    )
                    session.add(
                        AuditLog(
                            id=new_id(),
                            actor_type="system",
                            actor_id=None,
                            action="upload_quarantine_retention_expired",
                            target_type="upload_intent",
                            target_id=intent.id,
                            request_id=f"retention-{intent.id}",
                            metadata_json={"event": "upload_quarantine_retention_expired"},
                            occurred_at=now,
                        )
                    )
                results.append((tombstoned, intent.object_key))
            await session.commit()
            return tuple(results)
