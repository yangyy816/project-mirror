from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.models import (
    AgeAssuranceRecord,
    IdempotencyRecord,
    InviteCode,
    PhoneVerificationChallenge,
    PolicyAcceptanceRecord,
    User,
    UserSession,
    new_id,
)


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def locked_challenge(self, challenge_id: str) -> PhoneVerificationChallenge | None:
        return cast(
            PhoneVerificationChallenge | None,
            await self.session.scalar(
                select(PhoneVerificationChallenge)
                .where(PhoneVerificationChallenge.id == challenge_id)
                .with_for_update()
            ),
        )

    async def locked_user_for_phone(self, phone_hash: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(
                select(User).where(User.phone_hash == phone_hash).with_for_update()
            ),
        )

    async def locked_invite(self, invite_code_id: str) -> InviteCode | None:
        return cast(
            InviteCode | None,
            await self.session.scalar(
                select(InviteCode).where(InviteCode.id == invite_code_id).with_for_update()
            ),
        )

    async def locked_session(self, token_id: str) -> UserSession | None:
        return cast(
            UserSession | None,
            await self.session.scalar(
                select(UserSession).where(UserSession.token_id == token_id).with_for_update()
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
        user_id: str | None = None,
    ) -> tuple[IdempotencyRecord, bool]:
        """Atomically create a claim, or lock and return the existing claim."""
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
            actor_key=actor_key, scope=scope, key_hash=key_hash, lock=True
        )
        if record is None:  # pragma: no cover - concurrent delete is unsupported
            raise RuntimeError("idempotency claim was not found")
        return record, False

    async def revoke_family(self, family_id: str, *, reason: str, now: datetime) -> None:
        await self.session.execute(
            update(UserSession)
            .where(UserSession.family_id == family_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revocation_reason=reason)
        )

    async def has_current_verified_assurance(self, user_id: str, now: datetime) -> bool:
        statement = select(AgeAssuranceRecord.id).where(
            AgeAssuranceRecord.user_id == user_id,
            AgeAssuranceRecord.result == "verified",
            (AgeAssuranceRecord.expires_at.is_(None)) | (AgeAssuranceRecord.expires_at >= now),
        )
        return (await self.session.scalar(statement)) is not None

    async def has_policy(self, user_id: str, *, code: str, version: str, digest: str) -> bool:
        statement = select(PolicyAcceptanceRecord.id).where(
            PolicyAcceptanceRecord.user_id == user_id,
            PolicyAcceptanceRecord.document_code == code,
            PolicyAcceptanceRecord.document_version == version,
            PolicyAcceptanceRecord.document_digest == digest,
        )
        return (await self.session.scalar(statement)) is not None
