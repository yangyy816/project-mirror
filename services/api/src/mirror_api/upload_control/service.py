from __future__ import annotations

import hmac
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from json import dumps

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import (
    AuditLog,
    ConsentRecord,
    IdempotencyRecord,
    UploadIntent,
    UploadIntentEvent,
    new_id,
)
from mirror_api.providers.base import ObjectStorageProvider, QuarantineObjectMetadata
from mirror_api.rate_limit import RateLimiter
from mirror_api.security import hmac_digest
from mirror_api.upload_control.repository import ConsentRepository, UploadIntentRepository
from mirror_api.upload_control.types import (
    ConsentFailure,
    ConsentGrantResult,
    ConsentRequirement,
    ConsentState,
    ConsentWithdrawalResult,
    UploadCancellationResult,
    UploadCompletionResult,
    UploadDeclaration,
    UploadIntentCreationResult,
    UploadIntentFailure,
    UploadIntentView,
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


class UploadIntentService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: ObjectStorageProvider,
        rate_limiter: RateLimiter,
        requirement: ConsentRequirement,
        hmac_keyring: Mapping[str, str],
        hmac_active_kid: str,
        rate_limit: int = 10,
        rate_window_seconds: int = 60,
        max_active_intents: int = 3,
        max_pending_bytes: int = 60 * 1024 * 1024,
        now: Callable[[], datetime] | None = None,
        object_key_factory: Callable[[], str] | None = None,
    ) -> None:
        if min(rate_limit, rate_window_seconds, max_active_intents, max_pending_bytes) < 1:
            raise ValueError("upload admission limits must be positive")
        self._sessions = session_factory
        self._storage = storage
        self._limiter = rate_limiter
        self._requirement = requirement
        self._hmac_keyring = hmac_keyring
        self._hmac_active_kid = hmac_active_kid
        self._rate_limit = rate_limit
        self._rate_window_seconds = rate_window_seconds
        self._max_active_intents = max_active_intents
        self._max_pending_bytes = max_pending_bytes
        self._now = now or (lambda: datetime.now(UTC))
        self._object_key_factory = object_key_factory or (
            lambda: f"quarantine/v1/{secrets.token_hex(32)}"
        )

    async def create(
        self,
        *,
        user_id: str,
        declaration: UploadDeclaration,
        idempotency_key: str,
        request_id: str,
    ) -> UploadIntentCreationResult:
        admission = await self._limiter.check(
            bucket="upload-intent-user",
            key=user_id,
            limit=self._rate_limit,
            window_seconds=self._rate_window_seconds,
        )
        if not admission.allowed:
            raise UploadIntentFailure("upload_intent_throttled")
        fingerprint = self._fingerprint(
            {
                "content_type": declaration.content_type,
                "byte_size": declaration.byte_size,
                "sha256": declaration.sha256,
            }
        )
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = UploadIntentRepository(session)
            user = await repo.locked_user(user_id)
            if user is None or user.status != "active":
                raise UploadIntentFailure()
            record, claimed = await repo.claim_idempotency(
                actor_key=f"user:{user_id}",
                scope="upload_intent.create",
                key_hash=self._idempotency_key(idempotency_key),
                request_fingerprint=fingerprint,
                expires_at=now + timedelta(days=1),
                user_id=user_id,
            )
            if not claimed:
                replay_id = self._validate_replay(record, fingerprint)
                replay = await repo.locked_intent(user_id=user_id, intent_id=replay_id)
                if replay is None:
                    raise UploadIntentFailure()
                return UploadIntentCreationResult(
                    intent=self._view(replay),
                    grant=None,
                    created=False,
                )
            consent = await self._active_consent(repo, user_id=user_id, now=now)
            if consent is None:
                raise UploadIntentFailure("purpose_consent_required")
            active_count, pending_bytes = await repo.pending_usage(user_id=user_id)
            if active_count >= self._max_active_intents:
                raise UploadIntentFailure("upload_intent_quota_exceeded")
            if pending_bytes + declaration.byte_size > self._max_pending_bytes:
                raise UploadIntentFailure("upload_byte_quota_exceeded")

            object_key = self._object_key_factory()
            grant = await self._storage.create_private_upload_grant(
                object_key=object_key,
                content_type=declaration.content_type,
                content_length=declaration.byte_size,
                checksum_sha256=declaration.sha256,
            )
            if grant.expires_at <= now or grant.expires_at > now + timedelta(minutes=15):
                raise UploadIntentFailure("invalid_storage_grant")
            intent = UploadIntent(
                id=new_id(),
                owner_user_id=user_id,
                consent_record_id=consent.id,
                object_key=object_key,
                declared_mime_type=declaration.content_type,
                declared_byte_size=declaration.byte_size,
                declared_sha256=declaration.sha256,
                status="awaiting_upload",
                grant_expires_at=grant.expires_at,
                created_at=now,
                updated_at=now,
            )
            session.add(intent)
            session.add_all(
                (
                    self._event(intent.id, "created", request_id, now),
                    self._event(intent.id, "grant_issued", request_id, now),
                )
            )
            await session.flush()
            self._complete_idempotency(record, intent.id, 201, now)
            self._audit(session, user_id, "upload_intent_created", intent.id, request_id, now)
            return UploadIntentCreationResult(
                intent=self._view(intent),
                grant=grant,
                created=True,
            )

    async def get(self, *, user_id: str, intent_id: str) -> UploadIntentView:
        async with self._sessions() as session:
            intent = await UploadIntentRepository(session).intent(
                user_id=user_id,
                intent_id=intent_id,
            )
        if intent is None:
            raise UploadIntentFailure()
        return self._view(intent)

    async def complete(
        self,
        *,
        user_id: str,
        intent_id: str,
        idempotency_key: str,
        request_id: str,
    ) -> UploadCompletionResult:
        now = self._now()
        fingerprint = self._fingerprint({"intent_id": intent_id})
        cleanup_key: str | None = None
        failure_code: str | None = None
        result: UploadCompletionResult | None = None
        async with transaction(self._sessions) as session:
            repo = UploadIntentRepository(session)
            user = await repo.locked_user(user_id)
            if user is None or user.status != "active":
                raise UploadIntentFailure()
            record, claimed = await repo.claim_idempotency(
                actor_key=f"user:{user_id}",
                scope="upload_intent.complete",
                key_hash=self._idempotency_key(idempotency_key),
                request_fingerprint=fingerprint,
                expires_at=now + timedelta(days=1),
                user_id=user_id,
            )
            intent = await repo.locked_intent(user_id=user_id, intent_id=intent_id)
            if intent is None:
                raise UploadIntentFailure()
            if not claimed:
                replay_id = self._validate_replay(record, fingerprint)
                if replay_id != intent.id or intent.status != "uploaded_unverified":
                    raise UploadIntentFailure()
                return UploadCompletionResult(intent=self._view(intent), completed=False)

            if intent.status in ("cancelled", "expired"):
                cleanup_key = intent.object_key
                failure_code = f"upload_intent_{intent.status}"
            elif intent.status == "uploaded_unverified":
                self._complete_idempotency(record, intent.id, 200, now)
                result = UploadCompletionResult(intent=self._view(intent), completed=False)
            elif intent.status != "awaiting_upload":
                raise UploadIntentFailure()
            elif now >= intent.grant_expires_at:
                intent.status = "expired"
                intent.expired_at = now
                intent.updated_at = now
                session.add(self._event(intent.id, "expired", request_id, now))
                cleanup_key = intent.object_key
                failure_code = "upload_intent_expired"
            elif await self._active_consent(repo, user_id=user_id, now=now) is None:
                intent.status = "cancelled"
                intent.cancelled_at = now
                intent.updated_at = now
                session.add(self._event(intent.id, "cancelled", request_id, now))
                cleanup_key = intent.object_key
                failure_code = "purpose_consent_required"
            else:
                metadata = await self._storage.inspect_quarantine_object(
                    object_key=intent.object_key
                )
                if metadata is None:
                    raise UploadIntentFailure("upload_object_missing")
                if not self._metadata_matches(intent, metadata):
                    intent.status = "cancelled"
                    intent.cancelled_at = now
                    intent.updated_at = now
                    session.add(self._event(intent.id, "cancelled", request_id, now))
                    cleanup_key = intent.object_key
                    failure_code = "upload_metadata_mismatch"
                else:
                    intent.status = "uploaded_unverified"
                    intent.uploaded_at = metadata.uploaded_at
                    intent.updated_at = now
                    session.add(self._event(intent.id, "upload_completed", request_id, now))
                    self._complete_idempotency(record, intent.id, 200, now)
                    self._audit(
                        session,
                        user_id,
                        "upload_intent_completed",
                        intent.id,
                        request_id,
                        now,
                    )
                    result = UploadCompletionResult(intent=self._view(intent), completed=True)
            if failure_code is not None:
                self._complete_idempotency(record, intent.id, 409, now)
                self._audit(
                    session,
                    user_id,
                    "upload_intent_tombstoned",
                    intent.id,
                    request_id,
                    now,
                )
        if cleanup_key is not None:
            try:
                await self._storage.delete_quarantine_object(object_key=cleanup_key)
            except Exception as exc:
                raise UploadIntentFailure("quarantine_cleanup_failed") from exc
        if failure_code is not None:
            raise UploadIntentFailure(failure_code)
        if result is None:  # pragma: no cover - exhaustive state handling
            raise RuntimeError("upload completion produced no result")
        return result

    async def cancel(
        self,
        *,
        user_id: str,
        intent_id: str,
        request_id: str,
    ) -> UploadCancellationResult:
        now = self._now()
        object_key: str
        changed = False
        async with transaction(self._sessions) as session:
            repo = UploadIntentRepository(session)
            intent = await repo.locked_intent(user_id=user_id, intent_id=intent_id)
            if intent is None:
                raise UploadIntentFailure()
            if intent.status in ("processing", "promoted"):
                raise UploadIntentFailure()
            object_key = intent.object_key
            if intent.status not in ("cancelled", "expired"):
                intent.status = "cancelled"
                intent.cancelled_at = now
                intent.updated_at = now
                session.add(self._event(intent.id, "cancelled", request_id, now))
                self._audit(
                    session,
                    user_id,
                    "upload_intent_cancelled",
                    intent.id,
                    request_id,
                    now,
                )
                changed = True
        try:
            cleanup = await self._storage.delete_quarantine_object(object_key=object_key)
        except Exception as exc:
            raise UploadIntentFailure("quarantine_cleanup_failed") from exc
        return UploadCancellationResult(
            intent_id=intent_id,
            cancelled=changed,
            cleanup_result=cleanup,
        )

    async def _active_consent(
        self, repo: UploadIntentRepository, *, user_id: str, now: datetime
    ) -> ConsentRecord | None:
        return await repo.active_exact_consent(
            user_id=user_id,
            consent_type=self._requirement.consent_type,
            purpose=self._requirement.purpose_code,
            purpose_version=self._requirement.purpose_version,
            scope=self._requirement.scope,
            policy_code=self._requirement.policy_code,
            policy_version=self._requirement.policy_version,
            policy_digest=self._requirement.policy_digest,
            now=now,
        )

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
            raise UploadIntentFailure("idempotency_conflict")
        if record.state != "completed" or record.response_reference is None:
            raise UploadIntentFailure()
        return record.response_reference

    @staticmethod
    def _complete_idempotency(
        record: IdempotencyRecord,
        response_reference: str,
        response_status: int,
        now: datetime,
    ) -> None:
        record.response_reference = response_reference
        record.response_status = response_status
        record.state = "completed"
        record.completed_at = now

    @staticmethod
    def _metadata_matches(intent: UploadIntent, metadata: QuarantineObjectMetadata) -> bool:
        return (
            metadata.byte_size == intent.declared_byte_size
            and metadata.content_type == intent.declared_mime_type
            and hmac.compare_digest(metadata.sha256, intent.declared_sha256)
        )

    @staticmethod
    def _view(intent: UploadIntent) -> UploadIntentView:
        return UploadIntentView(
            intent_id=intent.id,
            status=intent.status,  # type: ignore[arg-type]
            declaration=UploadDeclaration(
                content_type=intent.declared_mime_type,
                byte_size=intent.declared_byte_size,
                sha256=intent.declared_sha256,
            ),
            grant_expires_at=intent.grant_expires_at,
            uploaded_at=intent.uploaded_at,
            cancelled_at=intent.cancelled_at,
            expired_at=intent.expired_at,
        )

    @staticmethod
    def _event(
        intent_id: str,
        event_type: str,
        request_id: str,
        occurred_at: datetime,
    ) -> UploadIntentEvent:
        return UploadIntentEvent(
            id=new_id(),
            upload_intent_id=intent_id,
            event_type=event_type,
            request_id=request_id,
            metadata_json={"event": event_type},
            occurred_at=occurred_at,
        )

    @staticmethod
    def _audit(
        session: AsyncSession,
        user_id: str,
        action: str,
        target_id: str,
        request_id: str,
        occurred_at: datetime,
    ) -> None:
        session.add(
            AuditLog(
                id=new_id(),
                actor_type="user",
                actor_id=user_id,
                action=action,
                target_type="upload_intent",
                target_id=target_id,
                request_id=request_id,
                metadata_json={"event": action},
                occurred_at=occurred_at,
            )
        )
