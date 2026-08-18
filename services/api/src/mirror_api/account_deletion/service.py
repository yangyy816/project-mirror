from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import (
    AccountDeletionEvent,
    AccountDeletionRequest,
    Asset,
    ConsentRecord,
    DataExportEvent,
    DataExportRequest,
    Job,
    ObjectDeletionEvidence,
    UploadIntent,
    UploadIntentEvent,
    User,
    UserSession,
    new_id,
)
from mirror_api.providers.base import ObjectStorageProvider
from mirror_api.security import hmac_digest
from mirror_api.storage_keys import data_export_object_key


class AccountDeletionFailure(Exception):
    pass


class RetryableAccountDeletionFailure(Exception):
    pass


@dataclass(frozen=True)
class AccountDeletionResult:
    request_id: str
    job_id: str
    status: str
    requested_at: datetime
    completed_at: datetime | None = None
    created: bool = False


class AccountDeletionService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: ObjectStorageProvider,
        hmac_keyring: dict[str, str],
        hmac_active_kid: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._storage = storage
        self._hmac_keyring = hmac_keyring
        self._hmac_active_kid = hmac_active_kid
        self._now = now or (lambda: datetime.now(UTC))

    async def request_deletion(
        self, *, user_id: str, idempotency_key: str, request_id: str
    ) -> AccountDeletionResult:
        key_hash = self._key_hash(user_id, idempotency_key)
        async with self._sessions() as session:
            try:
                user = cast(
                    User | None,
                    await session.scalar(select(User).where(User.id == user_id).with_for_update()),
                )
                replay = cast(
                    AccountDeletionRequest | None,
                    await session.scalar(
                        select(AccountDeletionRequest).where(
                            AccountDeletionRequest.idempotency_key_hash == key_hash
                        )
                    ),
                )
                if replay is not None:
                    if replay.owner_user_id != user_id:
                        raise AccountDeletionFailure()
                    return self._result(replay)
                if user is None or user.status != "active":
                    raise AccountDeletionFailure()
                now = self._now()
                job = Job(
                    id=new_id(),
                    owner_user_id=user_id,
                    job_type="account_deletion",
                    status="pending",
                    idempotency_key_hash=self._job_key_hash(user_id, idempotency_key),
                    request_id=request_id,
                    payload={"schema_version": "account-deletion-task-v1"},
                    created_at=now,
                    updated_at=now,
                )
                deletion = AccountDeletionRequest(
                    id=new_id(),
                    owner_user_id=user_id,
                    job_id=job.id,
                    idempotency_key_hash=key_hash,
                    status="requested",
                    requested_at=now,
                )
                user.status = "deletion_requested"
                sessions = list(
                    await session.scalars(
                        select(UserSession)
                        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
                        .with_for_update()
                    )
                )
                for user_session in sessions:
                    user_session.revoked_at = now
                    user_session.revocation_reason = "account_deletion"
                session.add(job)
                await session.flush()
                session.add(deletion)
                await session.flush()
                session.add(
                    AccountDeletionEvent(
                        id=new_id(),
                        request_id=deletion.id,
                        event_type="requested",
                        occurred_at=now,
                    )
                )
                await session.commit()
                return AccountDeletionResult(
                    request_id=deletion.id,
                    job_id=job.id,
                    status="requested",
                    requested_at=deletion.requested_at,
                    created=True,
                )
            except Exception:
                await session.rollback()
                raise

    async def process(self, *, job_id: str) -> AccountDeletionResult | None:
        started = await self._prepare(job_id)
        if started is None or started.status == "completed":
            return started
        request_id = started.request_id
        targets = await self._targets(request_id)
        if targets is None:
            return None
        assets, exports, intents, blocked = targets
        for asset in assets:
            if await self._has_asset_evidence(request_id, asset.id):
                continue
            try:
                outcome = await self._storage.delete_sanitized_object(object_key=asset.storage_key)
            except Exception as exc:
                raise RetryableAccountDeletionFailure("account asset deletion failed") from exc
            await self._record_asset_evidence(request_id, asset, outcome)
        for export in exports:
            if await self._has_export_evidence(request_id, export.id):
                continue
            try:
                outcome = await self._storage.delete_data_export(
                    object_key=export.storage_key or data_export_object_key(export.id)
                )
            except Exception as exc:
                raise RetryableAccountDeletionFailure("account export deletion failed") from exc
            await self._record_export_evidence(request_id, export.id, outcome)
        now = self._now()
        for intent in intents:
            if await self._has_quarantine_evidence(request_id, intent.id):
                continue
            if intent.grant_expires_at > now or intent.status not in (
                "promoted",
                "rejected",
                "cancelled",
                "expired",
            ):
                blocked = True
                continue
            try:
                outcome = await self._storage.delete_quarantine_object(object_key=intent.object_key)
            except Exception as exc:
                raise RetryableAccountDeletionFailure("account quarantine deletion failed") from exc
            await self._record_quarantine_evidence(request_id, intent, outcome)
        if blocked:
            raise RetryableAccountDeletionFailure(
                "account deletion awaits terminal work or upload grant expiry"
            )
        return await self._complete(job_id)

    async def current(self, *, user_id: str) -> AccountDeletionResult:
        async with self._sessions() as session:
            request = cast(
                AccountDeletionRequest | None,
                await session.scalar(
                    select(AccountDeletionRequest).where(
                        AccountDeletionRequest.owner_user_id == user_id
                    )
                ),
            )
            if request is None:
                raise AccountDeletionFailure()
            return self._result(request)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        async with self._sessions() as session:
            return tuple(
                await session.scalars(
                    select(Job.id)
                    .join(AccountDeletionRequest, AccountDeletionRequest.job_id == Job.id)
                    .where(AccountDeletionRequest.status.in_(("requested", "processing")))
                    .order_by(AccountDeletionRequest.requested_at, Job.id)
                    .limit(limit)
                )
            )

    async def _prepare(self, job_id: str) -> AccountDeletionResult | None:
        async with self._sessions() as session:
            request, job = await self._locked(session, job_id)
            if request is None or job is None:
                return None
            if request.status == "completed":
                return self._result(request)
            now = self._now()
            if request.status == "requested":
                request.status = "processing"
                request.started_at = now
                job.status = "processing"
                job.updated_at = now
                session.add(
                    AccountDeletionEvent(
                        id=new_id(),
                        request_id=request.id,
                        event_type="processing_started",
                        occurred_at=now,
                    )
                )
            user = cast(
                User | None,
                await session.scalar(
                    select(User).where(User.id == request.owner_user_id).with_for_update()
                ),
            )
            if user is None or user.status not in ("deletion_requested", "deleted"):
                raise AccountDeletionFailure()
            for user_session in await session.scalars(
                select(UserSession)
                .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
                .with_for_update()
            ):
                user_session.revoked_at = now
                user_session.revocation_reason = "account_deletion"
            assets = list(
                await session.scalars(
                    select(Asset).where(Asset.owner_user_id == user.id).with_for_update()
                )
            )
            for asset in assets:
                if asset.deleted_at is None:
                    asset.deleted_at = now
            await self._withdraw_active_consents(session, user.id, job.request_id, now)
            await self._terminalize_pending_work(session, user.id, job.request_id, now)
            await self._fail_unready_exports(session, user.id, now)
            await session.commit()
            return self._result(request)

    async def _withdraw_active_consents(
        self, session: AsyncSession, user_id: str, request_id: str, now: datetime
    ) -> None:
        superseded = select(ConsentRecord.supersedes_id).where(
            ConsentRecord.supersedes_id.is_not(None)
        )
        grants = list(
            await session.scalars(
                select(ConsentRecord)
                .where(
                    ConsentRecord.user_id == user_id,
                    ConsentRecord.action == "grant",
                    ConsentRecord.id.not_in(superseded),
                    (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > now)),
                )
                .with_for_update()
            )
        )
        for grant in grants:
            session.add(
                ConsentRecord(
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
                    source="account_deletion",
                    request_id=request_id,
                    created_at=now,
                )
            )

    async def _terminalize_pending_work(
        self, session: AsyncSession, user_id: str, request_id: str, now: datetime
    ) -> None:
        intents = list(
            await session.scalars(
                select(UploadIntent).where(UploadIntent.owner_user_id == user_id).with_for_update()
            )
        )
        ingestion_jobs = list(
            await session.scalars(
                select(Job)
                .where(Job.owner_user_id == user_id, Job.job_type == "asset_ingestion")
                .with_for_update()
            )
        )
        job_by_intent = {
            job.ingestion_upload_intent_id: job
            for job in ingestion_jobs
            if job.ingestion_upload_intent_id is not None
        }
        for intent in intents:
            if intent.status not in ("awaiting_upload", "uploaded_unverified"):
                continue
            job = job_by_intent.get(intent.id)
            if job is not None and job.status not in ("pending", "cancelled"):
                continue
            intent.status = "cancelled"
            intent.cancelled_at = now
            session.add(
                UploadIntentEvent(
                    id=new_id(),
                    upload_intent_id=intent.id,
                    event_type="cancelled",
                    request_id=request_id,
                    metadata_json={"result_code": "account_deletion_requested"},
                    occurred_at=now,
                )
            )
            if job is not None and job.status == "pending":
                job.status = "cancelled"
                job.finalized_at = now
                job.result_code = "account_deletion_requested"
                job.updated_at = now

    async def _fail_unready_exports(
        self, session: AsyncSession, user_id: str, now: datetime
    ) -> None:
        export_jobs = list(
            await session.scalars(
                select(Job)
                .join(DataExportRequest, DataExportRequest.job_id == Job.id)
                .where(
                    DataExportRequest.owner_user_id == user_id,
                    DataExportRequest.status.in_(("requested", "processing")),
                )
                .order_by(Job.id)
                .with_for_update(of=Job)
            )
        )
        jobs_by_id = {job.id: job for job in export_jobs}
        exports = list(
            await session.scalars(
                select(DataExportRequest)
                .where(
                    DataExportRequest.owner_user_id == user_id,
                    DataExportRequest.status.in_(("requested", "processing")),
                )
                .order_by(DataExportRequest.id)
                .with_for_update()
            )
        )
        for export in exports:
            job = jobs_by_id.get(export.job_id)
            if export.status == "requested":
                export.status = "processing"
                session.add(
                    DataExportEvent(
                        id=new_id(),
                        request_id=export.id,
                        event_type="processing_started",
                        occurred_at=now,
                    )
                )
                await session.flush()
            export.status = "failed"
            export.result_code = "account_deletion_requested"
            if job is not None:
                job.status = "failed"
                job.finalized_at = now
                job.result_code = "account_deletion_requested"
                job.updated_at = now
            session.add(
                DataExportEvent(
                    id=new_id(),
                    request_id=export.id,
                    event_type="failed",
                    result_code="account_deletion_requested",
                    occurred_at=now,
                )
            )

    async def _targets(
        self, request_id: str
    ) -> (
        tuple[tuple[Asset, ...], tuple[DataExportRequest, ...], tuple[UploadIntent, ...], bool]
        | None
    ):
        async with self._sessions() as session:
            request = cast(
                AccountDeletionRequest | None,
                await session.scalar(
                    select(AccountDeletionRequest)
                    .where(AccountDeletionRequest.id == request_id)
                    .with_for_update()
                ),
            )
            if request is None or request.status == "completed":
                return None
            assets = tuple(
                await session.scalars(
                    select(Asset)
                    .where(Asset.owner_user_id == request.owner_user_id)
                    .order_by(Asset.created_at.desc(), Asset.id)
                )
            )
            exports = tuple(
                await session.scalars(
                    select(DataExportRequest)
                    .where(DataExportRequest.owner_user_id == request.owner_user_id)
                    .order_by(DataExportRequest.requested_at.desc(), DataExportRequest.id)
                )
            )
            intents = tuple(
                await session.scalars(
                    select(UploadIntent)
                    .where(UploadIntent.owner_user_id == request.owner_user_id)
                    .order_by(UploadIntent.created_at.desc(), UploadIntent.id)
                )
            )
            blocked = any(
                intent.status not in ("promoted", "rejected", "cancelled", "expired")
                for intent in intents
            )
            return assets, exports, intents, blocked

    async def _complete(self, job_id: str) -> AccountDeletionResult | None:
        async with self._sessions() as session:
            request, job = await self._locked(session, job_id)
            if request is None or job is None:
                return None
            if request.status == "completed":
                return self._result(request)
            user = cast(
                User | None, await session.get(User, request.owner_user_id, with_for_update=True)
            )
            if user is None or user.status != "deletion_requested":
                raise RetryableAccountDeletionFailure("account deletion projection is unavailable")
            assets = set(
                await session.scalars(select(Asset.id).where(Asset.owner_user_id == user.id))
            )
            exports = set(
                await session.scalars(
                    select(DataExportRequest.id).where(DataExportRequest.owner_user_id == user.id)
                )
            )
            intents = set(
                await session.scalars(
                    select(UploadIntent.id).where(UploadIntent.owner_user_id == user.id)
                )
            )
            asset_evidence = set(
                await session.scalars(
                    select(ObjectDeletionEvidence.target_asset_id).where(
                        ObjectDeletionEvidence.account_deletion_request_id == request.id,
                        ObjectDeletionEvidence.object_kind == "asset",
                    )
                )
            )
            export_evidence = set(
                await session.scalars(
                    select(ObjectDeletionEvidence.target_data_export_request_id).where(
                        ObjectDeletionEvidence.account_deletion_request_id == request.id,
                        ObjectDeletionEvidence.object_kind == "data_export",
                    )
                )
            )
            quarantine_evidence = set(
                await session.scalars(
                    select(ObjectDeletionEvidence.target_upload_intent_id).where(
                        ObjectDeletionEvidence.account_deletion_request_id == request.id,
                        ObjectDeletionEvidence.object_kind == "quarantine",
                    )
                )
            )
            active_sessions = await session.scalar(
                select(UserSession.id).where(
                    UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
                )
            )
            active_grant = await session.scalar(
                select(ConsentRecord.id).where(
                    ConsentRecord.user_id == user.id,
                    ConsentRecord.action == "grant",
                    ConsentRecord.id.not_in(
                        select(ConsentRecord.supersedes_id).where(
                            ConsentRecord.supersedes_id.is_not(None)
                        )
                    ),
                    (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > self._now())),
                )
            )
            if (
                assets != asset_evidence
                or exports != export_evidence
                or intents != quarantine_evidence
                or active_sessions is not None
                or active_grant is not None
            ):
                raise RetryableAccountDeletionFailure("account deletion evidence is incomplete")
            now = self._now()
            user.phone_hash = secrets.token_hex(64)
            user.status = "deleted"
            request.status = "completed"
            request.completed_at = now
            request.result_code = "phase1_data_deleted"
            job.status = "completed"
            job.finalized_at = now
            job.result_code = "phase1_data_deleted"
            job.updated_at = now
            session.add(
                AccountDeletionEvent(
                    id=new_id(),
                    request_id=request.id,
                    event_type="completed",
                    result_code="phase1_data_deleted",
                    occurred_at=now,
                )
            )
            await session.commit()
            return self._result(request)

    async def _record_asset_evidence(self, request_id: str, asset: Asset, outcome: str) -> None:
        await self._insert_evidence(
            request_id=request_id,
            owner_user_id=cast(str, asset.owner_user_id),
            target_column="target_asset_id",
            target_id=asset.id,
            object_kind="asset",
            outcome=outcome,
        )

    async def _record_quarantine_evidence(
        self, request_id: str, intent: UploadIntent, outcome: str
    ) -> None:
        await self._insert_evidence(
            request_id=request_id,
            owner_user_id=intent.owner_user_id,
            target_column="target_upload_intent_id",
            target_id=intent.id,
            object_kind="quarantine",
            outcome=outcome,
        )

    async def _record_export_evidence(self, request_id: str, export_id: str, outcome: str) -> None:
        async with self._sessions() as session:
            await self._lock_request_authority(session, request_id)
            job = cast(
                Job | None,
                await session.scalar(
                    select(Job)
                    .join(DataExportRequest, DataExportRequest.job_id == Job.id)
                    .where(DataExportRequest.id == export_id)
                    .with_for_update(of=Job)
                ),
            )
            if job is None or job.job_type != "data_export":
                raise RetryableAccountDeletionFailure("export job authority disappeared")
            export = cast(
                DataExportRequest | None,
                await session.scalar(
                    select(DataExportRequest)
                    .where(DataExportRequest.id == export_id)
                    .with_for_update()
                ),
            )
            if export is None:
                raise RetryableAccountDeletionFailure("export target disappeared")
            now = self._now()
            if export.status == "ready":
                export.status = "expired"
                export.deleted_at = now
                export.result_code = "account_deletion_requested"
                session.add(
                    DataExportEvent(
                        id=new_id(),
                        request_id=export.id,
                        event_type="expired",
                        result_code="account_deletion_requested",
                        occurred_at=now,
                    )
                )
                await session.flush()
            await session.execute(
                insert(ObjectDeletionEvidence)
                .values(
                    id=new_id(),
                    owner_user_id=export.owner_user_id,
                    account_deletion_request_id=request_id,
                    target_data_export_request_id=export.id,
                    object_kind="data_export",
                    outcome=outcome,
                    result_code="deleted" if outcome == "deleted" else "already_absent",
                    completed_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "account_deletion_request_id",
                        "target_data_export_request_id",
                    ]
                )
            )
            await session.commit()

    async def _insert_evidence(
        self,
        *,
        request_id: str,
        owner_user_id: str,
        target_column: str,
        target_id: str,
        object_kind: str,
        outcome: str,
    ) -> None:
        if target_column not in ("target_asset_id", "target_upload_intent_id"):
            raise ValueError("unsupported account deletion evidence target")
        values = {
            "id": new_id(),
            "owner_user_id": owner_user_id,
            "account_deletion_request_id": request_id,
            target_column: target_id,
            "object_kind": object_kind,
            "outcome": outcome,
            "result_code": "deleted" if outcome == "deleted" else "already_absent",
            "completed_at": self._now(),
        }
        async with self._sessions() as session:
            await self._lock_request_authority(session, request_id)
            await session.execute(
                insert(ObjectDeletionEvidence)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["account_deletion_request_id", target_column]
                )
            )
            await session.commit()

    @staticmethod
    async def _lock_request_authority(
        session: AsyncSession, request_id: str
    ) -> AccountDeletionRequest:
        request = cast(
            AccountDeletionRequest | None,
            await session.scalar(
                select(AccountDeletionRequest)
                .where(AccountDeletionRequest.id == request_id)
                .with_for_update()
            ),
        )
        if request is None:
            raise RetryableAccountDeletionFailure("account deletion authority disappeared")
        return request

    async def _has_asset_evidence(self, request_id: str, target_id: str) -> bool:
        return await self._has_evidence(request_id, "target_asset_id", target_id)

    async def _has_export_evidence(self, request_id: str, target_id: str) -> bool:
        return await self._has_evidence(request_id, "target_data_export_request_id", target_id)

    async def _has_quarantine_evidence(self, request_id: str, target_id: str) -> bool:
        return await self._has_evidence(request_id, "target_upload_intent_id", target_id)

    async def _has_evidence(self, request_id: str, target_column: str, target_id: str) -> bool:
        column = getattr(ObjectDeletionEvidence, target_column)
        async with self._sessions() as session:
            return (
                await session.scalar(
                    select(ObjectDeletionEvidence.id).where(
                        ObjectDeletionEvidence.account_deletion_request_id == request_id,
                        column == target_id,
                    )
                )
                is not None
            )

    @staticmethod
    async def _locked(
        session: AsyncSession, job_id: str
    ) -> tuple[AccountDeletionRequest | None, Job | None]:
        job = cast(Job | None, await session.get(Job, job_id, with_for_update=True))
        if job is None or job.job_type != "account_deletion":
            return None, None
        request = cast(
            AccountDeletionRequest | None,
            await session.scalar(
                select(AccountDeletionRequest)
                .where(AccountDeletionRequest.job_id == job.id)
                .with_for_update()
            ),
        )
        return request, job

    @staticmethod
    def _result(request: AccountDeletionRequest) -> AccountDeletionResult:
        return AccountDeletionResult(
            request_id=request.id,
            job_id=request.job_id,
            status=request.status,
            requested_at=request.requested_at,
            completed_at=request.completed_at,
        )

    def _key_hash(self, user_id: str, value: str) -> str:
        material = hmac_digest(
            "account-delete:" + dumps([user_id, value], separators=(",", ":")),
            purpose="idempotency",
            keyring=self._hmac_keyring,
            key_id=self._hmac_active_kid,
        )
        return sha256(material.encode()).hexdigest()

    def _job_key_hash(self, user_id: str, value: str) -> str:
        return sha256(("job:" + self._key_hash(user_id, value)).encode()).hexdigest()
