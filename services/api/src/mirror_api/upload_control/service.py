from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from json import dumps

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import (
    AuditLog,
    ConsentRecord,
    IdempotencyRecord,
    UploadIntentEvent,
    new_id,
)
from mirror_api.security import hmac_digest
from mirror_api.upload_control.repository import ConsentRepository
from mirror_api.upload_control.types import (
    ConsentFailure,
    ConsentGrantResult,
    ConsentRequirement,
    ConsentState,
    ConsentWithdrawalResult,
)
from mirror_api.upload_control.uow import transaction


class ConsentService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        requirement: ConsentRequirement,
        hmac_keyring: Mapping[str, str],
        hmac_active_kid: str,
        source: str = "web_beta",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._requirement = requirement
        self._hmac_keyring = hmac_keyring
        self._hmac_active_kid = hmac_active_kid
        self._source = source
        self._now = now or (lambda: datetime.now(UTC))

    async def current_state(self, *, user_id: str) -> ConsentState:
        async with self._sessions() as session:
            records = await ConsentRepository(session).user_consents(user_id)
        return self._derive_state(records, self._now())

    async def grant(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        request_id: str,
    ) -> ConsentGrantResult:
        now = self._now()
        fingerprint = self._fingerprint(self._requirement_payload())
        async with transaction(self._sessions) as session:
            repo = ConsentRepository(session)
            user = await repo.locked_user(user_id)
            if user is None or user.status != "active":
                raise ConsentFailure("active_user_required")
            record, claimed = await repo.claim_idempotency(
                actor_key=f"user:{user_id}",
                scope="consent.grant",
                key_hash=self._idempotency_key(idempotency_key),
                request_fingerprint=fingerprint,
                expires_at=now + timedelta(days=1),
                user_id=user_id,
            )
            if not claimed:
                replay = self._validate_replay(record, fingerprint)
                grant = await session.get(ConsentRecord, replay)
                if grant is None or grant.action != "grant":
                    raise ConsentFailure()
                return self._grant_result(grant, created=False)

            records = await repo.user_consents(user_id, lock=True)
            current = self._derive_state(records, now)
            if current.status == "granted" and current.grant_id is not None:
                grant = await session.get(ConsentRecord, current.grant_id)
                if grant is None:  # pragma: no cover - state derived from the same transaction
                    raise RuntimeError("current consent grant disappeared")
                self._complete_idempotency(record, grant.id, now)
                return self._grant_result(grant, created=False)

            grant = ConsentRecord(
                id=new_id(),
                user_id=user_id,
                consent_type=self._requirement.consent_type,
                purpose=self._requirement.purpose_code,
                purpose_version=self._requirement.purpose_version,
                scope=self._requirement.scope,
                policy_code=self._requirement.policy_code,
                policy_version=self._requirement.policy_version,
                policy_digest=self._requirement.policy_digest,
                action="grant",
                granted_at=now,
                source=self._source,
                request_id=request_id,
            )
            session.add(grant)
            await session.flush()
            self._complete_idempotency(record, grant.id, now)
            self._audit(
                session,
                user_id=user_id,
                action="purpose_consent_granted",
                target_id=grant.id,
                request_id=request_id,
                event="purpose_consent_granted",
            )
            return self._grant_result(grant, created=True)

    async def withdraw(
        self,
        *,
        user_id: str,
        grant_id: str,
        idempotency_key: str,
        request_id: str,
    ) -> ConsentWithdrawalResult:
        now = self._now()
        fingerprint = self._fingerprint({"grant_id": grant_id})
        async with transaction(self._sessions) as session:
            repo = ConsentRepository(session)
            user = await repo.locked_user(user_id)
            if user is None:
                raise ConsentFailure()
            record, claimed = await repo.claim_idempotency(
                actor_key=f"user:{user_id}",
                scope="consent.withdraw",
                key_hash=self._idempotency_key(idempotency_key),
                request_fingerprint=fingerprint,
                expires_at=now + timedelta(days=1),
                user_id=user_id,
            )
            if not claimed:
                replay = self._validate_replay(record, fingerprint)
                withdrawal = await session.get(ConsentRecord, replay)
                if withdrawal is None or withdrawal.action != "withdraw":
                    raise ConsentFailure()
                return self._withdrawal_result(withdrawal, created=False)

            grant = await repo.locked_grant(user_id=user_id, grant_id=grant_id)
            if grant is None:
                raise ConsentFailure()
            existing = await repo.withdrawal_for_grant(grant.id)
            if existing is not None:
                self._complete_idempotency(record, existing.id, now)
                return self._withdrawal_result(existing, created=False)

            withdrawal = ConsentRecord(
                id=new_id(),
                user_id=user_id,
                consent_type=grant.consent_type,
                purpose=grant.purpose,
                purpose_version=grant.purpose_version,
                scope=grant.scope,
                policy_code=grant.policy_code,
                policy_version=grant.policy_version,
                policy_digest=grant.policy_digest,
                action="withdraw",
                supersedes_id=grant.id,
                withdrawn_at=now,
                source=self._source,
                request_id=request_id,
            )
            session.add(withdrawal)
            await session.flush()
            cancelled_ids = await repo.cancel_unpromoted_intents(
                user_id=user_id,
                consent_record_id=grant.id,
                cancelled_at=now,
            )
            for intent_id in cancelled_ids:
                session.add(
                    UploadIntentEvent(
                        id=new_id(),
                        upload_intent_id=intent_id,
                        event_type="cancelled",
                        request_id=request_id,
                        metadata_json={"reason": "consent_withdrawn"},
                        occurred_at=now,
                    )
                )
            self._complete_idempotency(record, withdrawal.id, now)
            self._audit(
                session,
                user_id=user_id,
                action="purpose_consent_withdrawn",
                target_id=withdrawal.id,
                request_id=request_id,
                event="purpose_consent_withdrawn",
            )
            return self._withdrawal_result(withdrawal, created=True)

    def _derive_state(self, records: list[ConsentRecord], now: datetime) -> ConsentState:
        withdrawals = {
            record.supersedes_id
            for record in records
            if record.action == "withdraw" and record.supersedes_id is not None
        }
        grants = [record for record in records if record.action == "grant"]
        exact = [record for record in grants if self._matches_requirement(record)]
        exact.sort(key=lambda record: record.created_at, reverse=True)
        for grant in exact:
            if grant.id not in withdrawals and (grant.expires_at is None or grant.expires_at > now):
                return ConsentState(
                    status="granted",
                    requirement=self._requirement,
                    grant_id=grant.id,
                    granted_at=grant.granted_at,
                    expires_at=grant.expires_at,
                )
        if exact and exact[0].id in withdrawals:
            return ConsentState(
                status="withdrawn",
                requirement=self._requirement,
                grant_id=exact[0].id,
                granted_at=exact[0].granted_at,
                expires_at=exact[0].expires_at,
            )
        if exact:
            return ConsentState(
                status="missing",
                requirement=self._requirement,
                missing_reason="expired",
            )
        return ConsentState(
            status="missing",
            requirement=self._requirement,
            missing_reason="version_mismatch" if grants else "absent",
        )

    def _matches_requirement(self, record: ConsentRecord) -> bool:
        return (
            record.consent_type == self._requirement.consent_type
            and record.purpose == self._requirement.purpose_code
            and record.purpose_version == self._requirement.purpose_version
            and record.policy_code == self._requirement.policy_code
            and record.policy_version == self._requirement.policy_version
            and record.policy_digest == self._requirement.policy_digest
            and record.scope == self._requirement.scope
        )

    def _requirement_payload(self) -> dict[str, object]:
        return {
            "consent_type": self._requirement.consent_type,
            "purpose_code": self._requirement.purpose_code,
            "purpose_version": self._requirement.purpose_version,
            "policy_code": self._requirement.policy_code,
            "policy_version": self._requirement.policy_version,
            "policy_digest": self._requirement.policy_digest,
            "scope": self._requirement.scope,
        }

    def _idempotency_key(self, key: str) -> str:
        return hmac_digest(
            key,
            purpose="idempotency",
            keyring=self._hmac_keyring,
            key_id=self._hmac_active_kid,
        )

    @staticmethod
    def _fingerprint(payload: Mapping[str, object]) -> str:
        canonical = dumps(dict(payload), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _validate_replay(record: IdempotencyRecord, fingerprint: str) -> str:
        if record.request_fingerprint != fingerprint:
            raise ConsentFailure("idempotency_conflict")
        if record.state != "completed" or record.response_reference is None:
            raise ConsentFailure()
        return record.response_reference

    @staticmethod
    def _complete_idempotency(
        record: IdempotencyRecord, response_reference: str, now: datetime
    ) -> None:
        record.response_reference = response_reference
        record.response_status = 201
        record.state = "completed"
        record.completed_at = now

    @staticmethod
    def _grant_result(grant: ConsentRecord, *, created: bool) -> ConsentGrantResult:
        if grant.granted_at is None:  # pragma: no cover - database check invariant
            raise RuntimeError("consent grant has no granted_at")
        return ConsentGrantResult(
            grant_id=grant.id,
            granted_at=grant.granted_at,
            expires_at=grant.expires_at,
            created=created,
        )

    @staticmethod
    def _withdrawal_result(withdrawal: ConsentRecord, *, created: bool) -> ConsentWithdrawalResult:
        if withdrawal.withdrawn_at is None or withdrawal.supersedes_id is None:
            raise RuntimeError("consent withdrawal is incomplete")
        return ConsentWithdrawalResult(
            withdrawal_id=withdrawal.id,
            grant_id=withdrawal.supersedes_id,
            withdrawn_at=withdrawal.withdrawn_at,
            created=created,
        )

    def _audit(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        action: str,
        target_id: str,
        request_id: str,
        event: str,
    ) -> None:
        session.add(
            AuditLog(
                id=new_id(),
                actor_type="user",
                actor_id=user_id,
                action=action,
                target_type="consent_record",
                target_id=target_id,
                request_id=request_id,
                metadata_json={"event": event},
                occurred_at=self._now(),
            )
        )
