from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import Select, exists, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from mirror_api.models import (
    AssetIngestionRecord,
    ConsentRecord,
    IdempotencyRecord,
    Job,
    JobAttempt,
    UploadIntent,
    User,
    new_id,
)


class IngestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def locked_user(self, user_id: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(select(User).where(User.id == user_id).with_for_update()),
        )

    async def active_exact_consent(
        self,
        *,
        user_id: str,
        consent_type: str,
        purpose: str,
        purpose_version: str,
        scope: dict[str, object],
        policy_code: str,
        policy_version: str,
        policy_digest: str,
        now: datetime,
    ) -> ConsentRecord | None:
        withdrawal = aliased(ConsentRecord)
        withdrawn = exists(
            select(withdrawal.id).where(
                withdrawal.action == "withdraw",
                withdrawal.supersedes_id == ConsentRecord.id,
            )
        )
        return cast(
            ConsentRecord | None,
            await self.session.scalar(
                select(ConsentRecord)
                .where(
                    ConsentRecord.user_id == user_id,
                    ConsentRecord.action == "grant",
                    ConsentRecord.consent_type == consent_type,
                    ConsentRecord.purpose == purpose,
                    ConsentRecord.purpose_version == purpose_version,
                    ConsentRecord.scope.cast(JSONB) == sql_cast(scope, JSONB),
                    ConsentRecord.policy_code == policy_code,
                    ConsentRecord.policy_version == policy_version,
                    ConsentRecord.policy_digest == policy_digest,
                    (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > now)),
                    ~withdrawn,
                )
                .order_by(ConsentRecord.created_at.desc())
                .limit(1)
                .with_for_update()
            ),
        )

    async def locked_intent(self, *, user_id: str, intent_id: str) -> UploadIntent | None:
        return cast(
            UploadIntent | None,
            await self.session.scalar(
                select(UploadIntent)
                .where(UploadIntent.id == intent_id, UploadIntent.owner_user_id == user_id)
                .with_for_update()
            ),
        )

    async def locked_job(self, *, job_id: str) -> Job | None:
        return cast(
            Job | None,
            await self.session.scalar(
                select(Job)
                .where(Job.id == job_id, Job.job_type == "asset_ingestion")
                .with_for_update()
            ),
        )

    async def owned_job(self, *, user_id: str, job_id: str) -> Job | None:
        return cast(
            Job | None,
            await self.session.scalar(
                select(Job).where(
                    Job.id == job_id,
                    Job.job_type == "asset_ingestion",
                    Job.owner_user_id == user_id,
                )
            ),
        )

    async def job_for_intent(
        self, *, user_id: str, intent_id: str, lock: bool = False
    ) -> Job | None:
        statement: Select[tuple[Job]] = select(Job).where(
            Job.job_type == "asset_ingestion",
            Job.owner_user_id == user_id,
            Job.ingestion_upload_intent_id == intent_id,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(Job | None, await self.session.scalar(statement))

    async def attempt_for_lease(self, *, job_id: str, lease_token: str) -> JobAttempt | None:
        return cast(
            JobAttempt | None,
            await self.session.scalar(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_id, JobAttempt.lease_token == lease_token)
                .with_for_update()
            ),
        )

    async def final_record(self, *, job_id: str) -> AssetIngestionRecord | None:
        return cast(
            AssetIngestionRecord | None,
            await self.session.scalar(
                select(AssetIngestionRecord).where(AssetIngestionRecord.job_id == job_id)
            ),
        )

    async def claim_idempotency(
        self,
        *,
        actor_key: str,
        scope: str,
        key_hash: str,
        request_fingerprint: str,
        expires_at: datetime,
        user_id: str,
    ) -> tuple[IdempotencyRecord, bool]:
        inserted_id = await self.session.scalar(
            insert(IdempotencyRecord)
            .values(
                id=new_id(),
                user_id=user_id,
                actor_key=actor_key,
                scope=scope,
                key_hash=key_hash,
                request_fingerprint=request_fingerprint,
                state="in_progress",
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=["actor_key", "scope", "key_hash"])
            .returning(IdempotencyRecord.id)
        )
        if inserted_id is not None:
            record = await self.session.get(IdempotencyRecord, inserted_id)
            if record is None:  # pragma: no cover - PostgreSQL RETURNING invariant
                raise RuntimeError("idempotency claim disappeared")
            return record, True
        record = cast(
            IdempotencyRecord | None,
            await self.session.scalar(
                select(IdempotencyRecord)
                .where(
                    IdempotencyRecord.actor_key == actor_key,
                    IdempotencyRecord.scope == scope,
                    IdempotencyRecord.key_hash == key_hash,
                )
                .with_for_update()
            ),
        )
        if record is None:  # pragma: no cover - unsupported concurrent delete
            raise RuntimeError("idempotency claim was not found")
        return record, False

    async def reconciliation_candidates(self, *, now: datetime, limit: int) -> tuple[str, ...]:
        statement = (
            select(Job.id)
            .where(
                Job.job_type == "asset_ingestion",
                or_(
                    Job.status == "pending",
                    (Job.status == "leased") & (Job.lease_expires_at <= now),
                ),
            )
            .order_by(Job.created_at, Job.id)
            .limit(limit)
        )
        return tuple((await self.session.scalars(statement)).all())
