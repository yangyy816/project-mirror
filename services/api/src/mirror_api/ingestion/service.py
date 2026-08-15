from __future__ import annotations

import re
import secrets
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from json import dumps

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.image_sanitizer import (
    ImageSanitizationError,
    SanitizedImage,
    sanitize_async_image_stream,
)
from mirror_api.ingestion.repository import IngestionRepository
from mirror_api.ingestion.types import (
    IngestionFailure,
    IngestionJobClaim,
    IngestionJobResult,
    IngestionJobView,
)
from mirror_api.ingestion.uow import transaction
from mirror_api.models import (
    Asset,
    AssetIngestionRecord,
    AuditLog,
    ConsentRecord,
    IdempotencyRecord,
    Job,
    JobAttempt,
    UploadIntent,
    UploadIntentEvent,
    new_id,
)
from mirror_api.providers import SanitizedObjectConflictError
from mirror_api.providers.base import ObjectStorageProvider, SanitizedObjectMetadata
from mirror_api.security import hmac_digest
from mirror_api.upload_control.types import ConsentRequirement

_INGESTION_JOB_TYPE = "asset_ingestion"
_IDEMPOTENCY_SCOPE = "asset_ingestion.create"
_JOB_PAYLOAD = {"schema_version": "ingestion-job-v1"}
_PROMOTED_CODE = "ingestion_promoted"
_AUTHORIZATION_REVOKED = "authorization_revoked"
_RETENTION_EXPIRED = "quarantine_retention_expired"
_SANITIZED_CONFLICT = "sanitized_object_conflict"
_TRANSIENT_STORAGE_FAILURE = "transient_storage_failure"
_CANCELLED_BEFORE_CLAIM = "ingestion_cancelled_before_claim"


class IngestionService:
    """Application-owned authoritative ingestion state machine.

    It deliberately exposes no HTTP, task-broker, object-key, or raw-image payload.
    A runner may only receive job ids/lease tokens and invoke these methods.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: ObjectStorageProvider,
        requirement: ConsentRequirement,
        hmac_keyring: Mapping[str, str],
        hmac_active_kid: str,
        lease_seconds: int = 300,
        idempotency_ttl_seconds: int = 86_400,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if lease_seconds < 1 or lease_seconds > 3_600:
            raise ValueError("ingestion lease duration must be between 1 and 3600 seconds")
        if idempotency_ttl_seconds < 1:
            raise ValueError("ingestion idempotency TTL must be positive")
        self._sessions = session_factory
        self._storage = storage
        self._requirement = requirement
        self._hmac_keyring = hmac_keyring
        self._hmac_active_kid = hmac_active_kid
        self._lease_seconds = lease_seconds
        self._idempotency_ttl_seconds = idempotency_ttl_seconds
        self._now = now or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        user_id: str,
        intent_id: str,
        idempotency_key: str,
        request_id: str,
    ) -> IngestionJobResult:
        now = self._now()
        fingerprint = self._fingerprint({"intent_id": intent_id})
        async with transaction(self._sessions) as session:
            repo = IngestionRepository(session)
            user = await repo.locked_user(user_id)
            if user is None or user.status != "active":
                raise IngestionFailure()
            record, claimed = await repo.claim_idempotency(
                actor_key=f"user:{user_id}",
                scope=_IDEMPOTENCY_SCOPE,
                key_hash=self._idempotency_key(idempotency_key),
                request_fingerprint=fingerprint,
                expires_at=now + timedelta(seconds=self._idempotency_ttl_seconds),
                user_id=user_id,
            )
            intent = await repo.locked_intent(user_id=user_id, intent_id=intent_id)
            if intent is None:
                raise IngestionFailure()
            if not claimed:
                job_id = self._replayed_job_id(record, fingerprint)
                replay = await repo.owned_job(user_id=user_id, job_id=job_id)
                if replay is None or replay.ingestion_upload_intent_id != intent.id:
                    raise IngestionFailure()
                return IngestionJobResult(job=self._view(replay), created=False)

            existing = await repo.job_for_intent(user_id=user_id, intent_id=intent.id, lock=True)
            if existing is not None:
                self._complete_idempotency(record, existing.id, now)
                return IngestionJobResult(job=self._view(existing), created=False)
            failure = await self._creation_authority_failure(
                repo, user_id=user_id, intent=intent, now=now
            )
            if failure is not None:
                raise IngestionFailure(failure)
            job = Job(
                id=new_id(),
                job_type=_INGESTION_JOB_TYPE,
                status="pending",
                idempotency_key_hash=self._job_idempotency_key(user_id, idempotency_key),
                request_id=request_id,
                payload=dict(_JOB_PAYLOAD),
                owner_user_id=user_id,
                ingestion_upload_intent_id=intent.id,
                attempt_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(job)
            await session.flush()
            self._complete_idempotency(record, job.id, now)
            self._audit(session, user_id, "asset_ingestion_job_created", job.id, request_id, now)
            return IngestionJobResult(job=self._view(job), created=True)

    async def get(self, *, user_id: str, job_id: str) -> IngestionJobView:
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = IngestionRepository(session)
            user = await repo.locked_user(user_id)
            if user is None or user.status != "active":
                raise IngestionFailure()
            job = await repo.owned_job(user_id=user_id, job_id=job_id)
            if job is None or job.ingestion_upload_intent_id is None:
                raise IngestionFailure()
            intent = await repo.locked_intent(
                user_id=user_id, intent_id=job.ingestion_upload_intent_id
            )
            if (
                intent is None
                or await self._current_consent(repo, user_id=user_id, now=now) is None
            ):
                raise IngestionFailure()
            return self._view(job)

    async def claim(self, *, job_id: str) -> IngestionJobClaim | None:
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = IngestionRepository(session)
            job = await repo.locked_job(job_id=job_id)
            if job is None or job.owner_user_id is None or job.ingestion_upload_intent_id is None:
                return None
            if job.status in ("promoted", "rejected", "cancelled"):
                return None
            if (
                job.status == "leased"
                and job.lease_expires_at is not None
                and job.lease_expires_at > now
            ):
                return None
            user = await repo.locked_user(job.owner_user_id)
            intent = await repo.locked_intent(
                user_id=job.owner_user_id, intent_id=job.ingestion_upload_intent_id
            )
            if user is None or intent is None:
                return None
            if job.status == "pending" and intent.status == "cancelled":
                self._set_cancelled(job, now=now)
                self._audit(
                    session,
                    self._owner_id(job),
                    "asset_ingestion_cancelled_before_claim",
                    job.id,
                    job.request_id,
                    now,
                )
                return None
            failure = await self._claim_authority_failure(
                repo,
                user_id=job.owner_user_id,
                user_active=user.status == "active",
                intent=intent,
                now=now,
            )
            if job.status == "leased":
                await self._finish_attempt(
                    repo,
                    job_id=job.id,
                    lease_token=job.lease_token,
                    outcome="retryable_failure",
                    code=_TRANSIENT_STORAGE_FAILURE,
                    now=now,
                )
            lease_token = secrets.token_hex(32)
            job.status = "leased"
            job.attempt_count += 1
            job.lease_token = lease_token
            job.lease_acquired_at = now
            job.lease_expires_at = now + timedelta(seconds=self._lease_seconds)
            job.updated_at = now
            if intent.status == "uploaded_unverified":
                intent.status = "processing"
                intent.processing_started_at = now
                intent.updated_at = now
                session.add(self._event(intent.id, "processing_started", job.request_id, now))
            await session.flush()
            session.add(
                JobAttempt(
                    id=new_id(),
                    job_id=job.id,
                    attempt=job.attempt_count,
                    status="leased",
                    lease_token=lease_token,
                    started_at=now,
                )
            )
            await session.flush()
            if failure is not None:
                await self._reject_locked(
                    session, repo, job=job, intent=intent, code=failure, now=now
                )
                return None
            self._audit(
                session,
                job.owner_user_id,
                "asset_ingestion_job_leased",
                job.id,
                job.request_id,
                now,
            )
            return IngestionJobClaim(
                job_id=job.id,
                request_id=job.request_id,
                lease_token=lease_token,
                attempt=job.attempt_count,
                lease_expires_at=job.lease_expires_at,
            )

    async def process(self, *, claim: IngestionJobClaim) -> IngestionJobResult | None:
        """Run a claimed job without exposing its quarantine key to a runner."""
        intent = await self._verify_claim_before_read(claim)
        if intent is None:
            return await self._result_if_final(claim.job_id)
        try:
            sanitized = await sanitize_async_image_stream(
                self._storage.stream_quarantine_object(object_key=intent.object_key),
                declared_mime_type=intent.declared_mime_type,
            )
        except ImageSanitizationError as exc:
            return await self.reject(claim=claim, code=exc.code)
        except Exception:
            await self.retry(claim=claim, code=_TRANSIENT_STORAGE_FAILURE)
            return None
        try:
            stored = await self._storage.create_sanitized_object_if_absent(
                object_key=self._sanitized_key(claim.job_id),
                content_type=sanitized.content_type,
                content_length=sanitized.byte_size,
                checksum_sha256=sanitized.sha256,
                body=self._sanitized_body(sanitized),
            )
        except SanitizedObjectConflictError:
            return await self.reject(claim=claim, code=_SANITIZED_CONFLICT)
        except Exception:
            await self.retry(claim=claim, code=_TRANSIENT_STORAGE_FAILURE)
            return None
        if not self._stored_matches(stored, sanitized):
            return await self.reject(claim=claim, code=_SANITIZED_CONFLICT)
        return await self.promote(claim=claim, sanitized=sanitized)

    async def promote(
        self, *, claim: IngestionJobClaim, sanitized: SanitizedImage
    ) -> IngestionJobResult | None:
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = IngestionRepository(session)
            job, intent = await self._locked_claim(repo, claim)
            if job is None or intent is None:
                return await self._final_result_locked(repo, claim.job_id)
            failure = await self._final_authority_failure(repo, job=job, intent=intent, now=now)
            if failure is not None:
                return await self._reject_locked(
                    session, repo, job=job, intent=intent, code=failure, now=now
                )
            asset = Asset(
                id=new_id(),
                owner_user_id=job.owner_user_id,
                asset_role="original",
                storage_key=self._sanitized_key(job.id),
                mime_type=sanitized.content_type,
                byte_size=sanitized.byte_size,
                width=sanitized.width,
                height=sanitized.height,
                sha256=sanitized.sha256,
                synthetic=False,
                is_ai_generated=False,
                is_ai_modified=False,
                created_at=now,
                updated_at=now,
            )
            session.add(asset)
            self._set_final(
                job, intent, outcome="promoted", code=_PROMOTED_CODE, now=now, asset_id=asset.id
            )
            await session.flush()
            session.add(
                AssetIngestionRecord(
                    id=new_id(),
                    owner_user_id=job.owner_user_id,
                    upload_intent_id=intent.id,
                    job_id=job.id,
                    outcome="promoted",
                    result_asset_id=asset.id,
                    result_code=_PROMOTED_CODE,
                    sanitizer_version=sanitized.version,
                    finalized_at=now,
                )
            )
            await self._finish_attempt(
                repo,
                job_id=job.id,
                lease_token=claim.lease_token,
                outcome="promoted",
                code=_PROMOTED_CODE,
                now=now,
            )
            session.add(self._event(intent.id, "promoted", job.request_id, now))
            self._audit(
                session,
                self._owner_id(job),
                "asset_ingestion_promoted",
                job.id,
                job.request_id,
                now,
            )
            return IngestionJobResult(job=self._view(job))

    async def reject(self, *, claim: IngestionJobClaim, code: str) -> IngestionJobResult | None:
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = IngestionRepository(session)
            job, intent = await self._locked_claim(repo, claim)
            if job is None or intent is None:
                return await self._final_result_locked(repo, claim.job_id)
            return await self._reject_locked(
                session, repo, job=job, intent=intent, code=code, now=now
            )

    async def retry(self, *, claim: IngestionJobClaim, code: str) -> None:
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = IngestionRepository(session)
            job, _ = await self._locked_claim(repo, claim)
            if job is None:
                return
            attempt = await repo.attempt_for_lease(job_id=job.id, lease_token=claim.lease_token)
            if attempt is None:
                return
            job.status = "pending"
            job.lease_token = None
            job.lease_acquired_at = None
            job.lease_expires_at = None
            job.updated_at = now
            attempt.status = "retryable_failure"
            attempt.result_code = code
            attempt.error_code = code
            attempt.finished_at = now
            self._audit(
                session,
                self._owner_id(job),
                "asset_ingestion_retryable",
                job.id,
                job.request_id,
                now,
            )

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        if limit < 1 or limit > 1_000:
            raise ValueError("reconciliation limit must be between 1 and 1000")
        async with self._sessions() as session:
            return await IngestionRepository(session).reconciliation_candidates(
                now=self._now(), limit=limit
            )

    async def _verify_claim_before_read(self, claim: IngestionJobClaim) -> UploadIntent | None:
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = IngestionRepository(session)
            job, intent = await self._locked_claim(repo, claim)
            if job is None or intent is None:
                return None
            failure = await self._final_authority_failure(repo, job=job, intent=intent, now=now)
            if failure is not None:
                await self._reject_locked(
                    session, repo, job=job, intent=intent, code=failure, now=now
                )
                return None
            return intent

    async def _creation_authority_failure(
        self, repo: IngestionRepository, *, user_id: str, intent: UploadIntent, now: datetime
    ) -> str | None:
        if intent.status != "uploaded_unverified":
            return "upload_intent_not_ready"
        if intent.uploaded_at is None or intent.quarantine_retention_deadline is None:
            return "upload_intent_not_ready"
        if intent.quarantine_retention_deadline <= now:
            return _RETENTION_EXPIRED
        if await self._current_consent(repo, user_id=user_id, now=now) is None:
            return _AUTHORIZATION_REVOKED
        return None

    async def _claim_authority_failure(
        self,
        repo: IngestionRepository,
        *,
        user_id: str,
        user_active: bool,
        intent: UploadIntent,
        now: datetime,
    ) -> str | None:
        if not user_active or await self._current_consent(repo, user_id=user_id, now=now) is None:
            return _AUTHORIZATION_REVOKED
        if intent.status not in ("uploaded_unverified", "processing"):
            return "upload_intent_not_ready"
        if (
            intent.quarantine_retention_deadline is None
            or intent.quarantine_retention_deadline <= now
        ):
            return _RETENTION_EXPIRED
        return None

    async def _final_authority_failure(
        self, repo: IngestionRepository, *, job: Job, intent: UploadIntent, now: datetime
    ) -> str | None:
        if job.owner_user_id is None:
            return _AUTHORIZATION_REVOKED
        user = await repo.locked_user(job.owner_user_id)
        if user is None or user.status != "active":
            return _AUTHORIZATION_REVOKED
        if await self._current_consent(repo, user_id=job.owner_user_id, now=now) is None:
            return _AUTHORIZATION_REVOKED
        if intent.status != "processing":
            return "upload_intent_not_ready"
        if (
            intent.quarantine_retention_deadline is None
            or intent.quarantine_retention_deadline <= now
        ):
            return _RETENTION_EXPIRED
        return None

    async def _current_consent(
        self, repo: IngestionRepository, *, user_id: str, now: datetime
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

    async def _locked_claim(
        self, repo: IngestionRepository, claim: IngestionJobClaim
    ) -> tuple[Job | None, UploadIntent | None]:
        job = await repo.locked_job(job_id=claim.job_id)
        if (
            job is None
            or job.owner_user_id is None
            or job.ingestion_upload_intent_id is None
            or job.status != "leased"
            or job.lease_token != claim.lease_token
            or job.lease_expires_at is None
            or job.lease_expires_at <= self._now()
        ):
            return None, None
        intent = await repo.locked_intent(
            user_id=job.owner_user_id, intent_id=job.ingestion_upload_intent_id
        )
        if intent is None:
            return None, None
        return job, intent

    async def _reject_locked(
        self,
        session: AsyncSession,
        repo: IngestionRepository,
        *,
        job: Job,
        intent: UploadIntent,
        code: str,
        now: datetime,
    ) -> IngestionJobResult:
        existing = await repo.final_record(job_id=job.id)
        if existing is not None:
            return IngestionJobResult(job=self._view(job))
        lease_token = job.lease_token
        self._set_final(job, intent, outcome="rejected", code=code, now=now, asset_id=None)
        await session.flush()
        session.add(
            AssetIngestionRecord(
                id=new_id(),
                owner_user_id=job.owner_user_id or "",
                upload_intent_id=intent.id,
                job_id=job.id,
                outcome="rejected",
                result_code=code,
                finalized_at=now,
            )
        )
        await self._finish_attempt(
            repo,
            job_id=job.id,
            lease_token=lease_token,
            outcome="rejected",
            code=code,
            now=now,
        )
        session.add(self._event(intent.id, "rejected", job.request_id, now))
        self._audit(
            session, self._owner_id(job), "asset_ingestion_rejected", job.id, job.request_id, now
        )
        return IngestionJobResult(job=self._view(job))

    async def _final_result_locked(
        self, repo: IngestionRepository, job_id: str
    ) -> IngestionJobResult | None:
        job = await repo.locked_job(job_id=job_id)
        if job is None or job.status not in ("promoted", "rejected", "cancelled"):
            return None
        return IngestionJobResult(job=self._view(job))

    async def _result_if_final(self, job_id: str) -> IngestionJobResult | None:
        async with transaction(self._sessions) as session:
            return await self._final_result_locked(IngestionRepository(session), job_id)

    @staticmethod
    def _set_final(
        job: Job,
        intent: UploadIntent,
        *,
        outcome: str,
        code: str,
        now: datetime,
        asset_id: str | None,
    ) -> None:
        job.status = outcome
        job.lease_token = None
        job.lease_acquired_at = None
        job.lease_expires_at = None
        job.finalized_at = now
        job.result_asset_id = asset_id
        job.result_code = code
        job.updated_at = now
        intent.status = outcome
        intent.finalized_at = now
        intent.updated_at = now

    @staticmethod
    def _set_cancelled(job: Job, *, now: datetime) -> None:
        job.status = "cancelled"
        job.lease_token = None
        job.lease_acquired_at = None
        job.lease_expires_at = None
        job.finalized_at = now
        job.result_asset_id = None
        job.result_code = _CANCELLED_BEFORE_CLAIM
        job.updated_at = now

    @staticmethod
    async def _finish_attempt(
        repo: IngestionRepository,
        *,
        job_id: str,
        lease_token: str | None,
        outcome: str,
        code: str,
        now: datetime,
    ) -> None:
        if lease_token is None:
            raise RuntimeError("leased ingestion job has no lease token")
        attempt = await repo.attempt_for_lease(job_id=job_id, lease_token=lease_token)
        if attempt is None:
            raise RuntimeError("current ingestion lease attempt is missing")
        attempt.status = outcome
        attempt.result_code = code
        if outcome == "retryable_failure":
            attempt.error_code = code
        attempt.finished_at = now

    @staticmethod
    def _event(
        intent_id: str, event_type: str, request_id: str, now: datetime
    ) -> UploadIntentEvent:
        return UploadIntentEvent(
            id=new_id(),
            upload_intent_id=intent_id,
            event_type=event_type,
            request_id=request_id,
            metadata_json={"event": event_type},
            occurred_at=now,
        )

    @staticmethod
    def _audit(
        session: AsyncSession,
        user_id: str,
        action: str,
        target_id: str,
        request_id: str,
        now: datetime,
    ) -> None:
        session.add(
            AuditLog(
                id=new_id(),
                actor_type="user",
                actor_id=user_id,
                action=action,
                target_type="ingestion_job",
                target_id=target_id,
                request_id=request_id,
                metadata_json={"event": action},
                occurred_at=now,
            )
        )

    def _idempotency_key(self, value: str) -> str:
        return hmac_digest(
            f"ingestion-create:{value}",
            purpose="idempotency",
            keyring=self._hmac_keyring,
            key_id=self._hmac_active_kid,
        )

    def _job_idempotency_key(self, user_id: str, value: str) -> str:
        material = hmac_digest(
            "ingestion-job:" + dumps([user_id, value], ensure_ascii=True, separators=(",", ":")),
            purpose="idempotency",
            keyring=self._hmac_keyring,
            key_id=self._hmac_active_kid,
        )
        return sha256(material.encode()).hexdigest()

    @staticmethod
    def _fingerprint(payload: Mapping[str, object]) -> str:
        canonical = dumps(dict(payload), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _replayed_job_id(record: IdempotencyRecord, fingerprint: str) -> str:
        if record.request_fingerprint != fingerprint:
            raise IngestionFailure("idempotency_conflict")
        if record.state != "completed" or record.response_reference is None:
            raise IngestionFailure()
        return record.response_reference

    @staticmethod
    def _complete_idempotency(record: IdempotencyRecord, job_id: str, now: datetime) -> None:
        record.response_reference = job_id
        record.response_status = 202
        record.state = "completed"
        record.completed_at = now

    @staticmethod
    def _view(job: Job) -> IngestionJobView:
        return IngestionJobView(
            job_id=job.id,
            status=job.status,  # type: ignore[arg-type]
            result_code=job.result_code,
            asset_id=job.result_asset_id,
            finalized_at=job.finalized_at,
        )

    @staticmethod
    async def _sanitized_body(image: SanitizedImage) -> AsyncIterator[bytes]:
        yield image.bytes_value

    @staticmethod
    def _stored_matches(stored: SanitizedObjectMetadata, image: SanitizedImage) -> bool:
        return (
            stored.byte_size == image.byte_size
            and stored.content_type == image.content_type
            and stored.sha256 == image.sha256
        )

    @staticmethod
    def _owner_id(job: Job) -> str:
        if job.owner_user_id is None:  # pragma: no cover - database lifecycle invariant
            raise RuntimeError("ingestion job has no owner")
        return job.owner_user_id

    @staticmethod
    def _sanitized_key(job_id: str) -> str:
        if re.fullmatch(r"[0-9a-f]{32}", job_id) is None:
            raise ValueError("ingestion job id must use the opaque 32-character syntax")
        return f"sanitized/v1/{job_id}"
