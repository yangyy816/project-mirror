from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import SyntheticSourceObjectDeletionEvidence, new_id
from mirror_api.providers.base import DeleteResult, SyntheticObjectStorageProvider
from mirror_api.storage_keys import synthetic_raw_storage_reference
from mirror_api.synthetic_dataset.generation_repository import GenerationRepository
from mirror_api.synthetic_dataset.generation_types import GenerationOperationRejected


def _utcnow() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def _transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


@dataclass(frozen=True)
class RawRetentionCleanupResult:
    source_object_id: str
    deletion_result: DeleteResult
    evidence_created: bool


@dataclass(frozen=True)
class RawOrphanCleanupResult:
    outcome: Literal["deleted", "not_found", "referenced"]


class SyntheticRawStorageService:
    """Coordinates exact-reference raw cleanup without making storage a domain authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: SyntheticObjectStorageProvider,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._sessions = session_factory
        self._storage = storage
        self._now = now

    async def delete_failed_attempt_orphan(
        self,
        *,
        item_id: str,
        attempt_id: str,
        storage_reference: str,
    ) -> RawOrphanCleanupResult:
        if storage_reference != synthetic_raw_storage_reference(item_id, attempt_id):
            raise GenerationOperationRejected("orphan_reference_mismatch")
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            observed_item = await repo.item(item_id)
            if observed_item is None:
                raise GenerationOperationRejected("generation_item_not_found")
            batch = await repo.locked_batch(observed_item.batch_id)
            item = await repo.locked_item(item_id)
            if batch is None or item is None or item.batch_id != batch.id:
                raise GenerationOperationRejected("generation_item_not_found")
            job = await repo.locked_job(item.job_id)
            attempt = await repo.locked_attempt(attempt_id)
            await repo.lock_storage_reference(storage_reference)
            if await repo.source_by_storage_reference(storage_reference) is not None:
                return RawOrphanCleanupResult(outcome="referenced")
            if (
                job is None
                or attempt is None
                or attempt.job_id != job.id
                or attempt.status not in {"retryable_failure", "generation_failed"}
                or attempt.finished_at is None
            ):
                raise GenerationOperationRejected("orphan_attempt_not_quiescent")
            result = await self._storage.delete_generated_image(storage_reference=storage_reference)
            return RawOrphanCleanupResult(outcome=result)

    async def cleanup_expired(self, *, limit: int = 100) -> tuple[RawRetentionCleanupResult, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("raw cleanup limit is outside the boundary")
        now = self._now()
        async with self._sessions() as session:
            candidates = await GenerationRepository(session).expired_source_ids(
                now=now, limit=limit
            )
        results: list[RawRetentionCleanupResult] = []
        for source_id in candidates:
            result = await self._cleanup_expired_source(source_id=source_id, now=now)
            if result is not None:
                results.append(result)
        return tuple(results)

    async def _cleanup_expired_source(
        self, *, source_id: str, now: datetime
    ) -> RawRetentionCleanupResult | None:
        async with _transaction(self._sessions) as session:
            repo = GenerationRepository(session)
            source = await repo.locked_source(source_id)
            if source is None:
                return None
            existing = await repo.source_deletion_evidence(source.id)
            if existing is not None:
                return RawRetentionCleanupResult(
                    source_object_id=source.id,
                    deletion_result=cast(DeleteResult, existing.deletion_result),
                    evidence_created=False,
                )
            if source.retention_expires_at > now:
                return None
            await repo.lock_storage_reference(source.storage_reference)
            deletion_result = await self._storage.delete_generated_image(
                storage_reference=source.storage_reference
            )
            session.add(
                SyntheticSourceObjectDeletionEvidence(
                    id=new_id(),
                    source_object_id=source.id,
                    reason_code="retention_expired",
                    deletion_result=deletion_result,
                    actor_kind="system",
                    actor_reference=None,
                    deleted_at=now,
                    created_at=now,
                )
            )
            await session.flush()
            return RawRetentionCleanupResult(
                source_object_id=source.id,
                deletion_result=deletion_result,
                evidence_created=True,
            )
