from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.models import ConsentRecord, IdempotencyRecord, UploadIntent, User, new_id


class ConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def locked_user(self, user_id: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(select(User).where(User.id == user_id).with_for_update()),
        )

    async def user_consents(self, user_id: str, *, lock: bool = False) -> list[ConsentRecord]:
        statement: Select[tuple[ConsentRecord]] = select(ConsentRecord).where(
            ConsentRecord.user_id == user_id
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def locked_grant(self, *, user_id: str, grant_id: str) -> ConsentRecord | None:
        return cast(
            ConsentRecord | None,
            await self.session.scalar(
                select(ConsentRecord)
                .where(
                    ConsentRecord.id == grant_id,
                    ConsentRecord.user_id == user_id,
                    ConsentRecord.action == "grant",
                )
                .with_for_update()
            ),
        )

    async def withdrawal_for_grant(self, grant_id: str) -> ConsentRecord | None:
        return cast(
            ConsentRecord | None,
            await self.session.scalar(
                select(ConsentRecord).where(
                    ConsentRecord.action == "withdraw",
                    ConsentRecord.supersedes_id == grant_id,
                )
            ),
        )

    async def idempotency(
        self, *, actor_key: str, scope: str, key_hash: str, lock: bool = False
    ) -> IdempotencyRecord | None:
        statement: Select[tuple[IdempotencyRecord]] = select(IdempotencyRecord).where(
            IdempotencyRecord.actor_key == actor_key,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key_hash == key_hash,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(IdempotencyRecord | None, await self.session.scalar(statement))

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
        statement = (
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
        inserted_id = await self.session.scalar(statement)
        if inserted_id is not None:
            record = await self.session.get(IdempotencyRecord, inserted_id)
            if record is None:  # pragma: no cover - PostgreSQL RETURNING invariant
                raise RuntimeError("idempotency claim disappeared")
            return record, True
        record = await self.idempotency(
            actor_key=actor_key,
            scope=scope,
            key_hash=key_hash,
            lock=True,
        )
        if record is None:  # pragma: no cover - concurrent delete is unsupported
            raise RuntimeError("idempotency claim was not found")
        return record, False

    async def cancel_unpromoted_intents(
        self, *, user_id: str, consent_record_id: str, cancelled_at: datetime
    ) -> tuple[str, ...]:
        result = await self.session.execute(
            update(UploadIntent)
            .where(
                UploadIntent.owner_user_id == user_id,
                UploadIntent.consent_record_id == consent_record_id,
                UploadIntent.status.in_(("awaiting_upload", "uploaded_unverified")),
            )
            .values(status="cancelled", cancelled_at=cancelled_at)
            .returning(UploadIntent.id)
        )
        return tuple(result.scalars().all())
