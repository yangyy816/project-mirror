from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from json import dumps
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.data_export.archive import (
    ARCHIVE_SCHEMA_VERSION,
    ExportArchive,
    ExportArchiveBuilder,
    ExportArchiveFailure,
)
from mirror_api.models import (
    Asset,
    ConsentRecord,
    DataExportEvent,
    DataExportRequest,
    Job,
    ObjectDeletionEvidence,
    PolicyAcceptanceRecord,
    User,
    new_id,
)
from mirror_api.providers.base import ObjectStorageProvider, PrivateDownloadGrant
from mirror_api.providers.local import (
    LocalDownloadRedemption,
    LocalObjectStorageProvider,
)
from mirror_api.security import hmac_digest
from mirror_api.storage_keys import data_export_object_key


class DataExportFailure(Exception):
    pass


class RetryableDataExportFailure(Exception):
    pass


class DataExportAccessDenied(Exception):
    pass


@dataclass(frozen=True)
class DataExportResult:
    export_id: str
    job_id: str
    status: str
    schema_version: str
    requested_at: datetime
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    created: bool = False


class DataExportService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage: ObjectStorageProvider,
        hmac_keyring: dict[str, str],
        hmac_active_kid: str,
        retention_seconds: int = 3600,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if retention_seconds < 300 or retention_seconds > 86_400:
            raise ValueError("data export retention must be between 5 minutes and 24 hours")
        self._sessions = session_factory
        self._storage = storage
        self._hmac_keyring = hmac_keyring
        self._hmac_active_kid = hmac_active_kid
        self._retention_seconds = retention_seconds
        self._now = now or (lambda: datetime.now(UTC))

    async def request_export(
        self, *, user_id: str, idempotency_key: str, request_id: str
    ) -> DataExportResult:
        key_hash = self._key_hash(user_id, idempotency_key)
        async with self._sessions() as session:
            try:
                user = cast(
                    User | None,
                    await session.scalar(select(User).where(User.id == user_id).with_for_update()),
                )
                replay = cast(
                    DataExportRequest | None,
                    await session.scalar(
                        select(DataExportRequest).where(
                            DataExportRequest.idempotency_key_hash == key_hash
                        )
                    ),
                )
                if replay is not None:
                    if replay.owner_user_id != user_id:
                        raise DataExportFailure()
                    return self._result(replay)
                if user is None or user.status != "active":
                    raise DataExportFailure()
                now = self._now()
                job = Job(
                    id=new_id(),
                    owner_user_id=user_id,
                    job_type="data_export",
                    status="pending",
                    idempotency_key_hash=self._job_key_hash(user_id, idempotency_key),
                    request_id=request_id,
                    payload={"schema_version": "data-export-task-v1"},
                    created_at=now,
                    updated_at=now,
                )
                export = DataExportRequest(
                    id=new_id(),
                    owner_user_id=user_id,
                    job_id=job.id,
                    idempotency_key_hash=key_hash,
                    status="requested",
                    schema_version=ARCHIVE_SCHEMA_VERSION,
                    requested_at=now,
                )
                session.add(job)
                await session.flush()
                session.add(export)
                await session.flush()
                session.add(
                    DataExportEvent(
                        id=new_id(),
                        request_id=export.id,
                        event_type="requested",
                        occurred_at=now,
                    )
                )
                await session.commit()
                return DataExportResult(
                    export_id=export.id,
                    job_id=job.id,
                    status="requested",
                    schema_version=export.schema_version,
                    requested_at=export.requested_at,
                    created=True,
                )
            except Exception:
                await session.rollback()
                raise

    async def process(self, *, job_id: str) -> DataExportResult | None:
        started = await self._start(job_id)
        if started is None:
            return None
        if started.status in ("ready", "failed", "expired"):
            return started
        snapshot = await self._snapshot(started.export_id)
        if snapshot is None:
            await self._fail(job_id, "account_not_active")
            return await self._by_job(job_id)
        user, policies, consents, assets = snapshot
        try:
            archive = await ExportArchiveBuilder(storage=self._storage).build(
                user=user,
                policies=policies,
                consents=consents,
                assets=assets,
                generated_at=started.requested_at,
            )
        except ExportArchiveFailure as exc:
            raise RetryableDataExportFailure("data export source verification failed") from exc
        key = data_export_object_key(started.export_id)
        try:
            ready = await self._publish_and_mark_ready(
                job_id=job_id,
                object_key=key,
                archive=archive,
            )
        finally:
            archive.close()
        if ready is not None:
            return ready
        await self._fail(job_id, "account_not_active")
        return await self._by_job(job_id)

    async def get_export(self, *, user_id: str, export_id: str) -> DataExportResult:
        async with self._sessions() as session:
            export = cast(
                DataExportRequest | None,
                await session.scalar(
                    select(DataExportRequest)
                    .join(User, User.id == DataExportRequest.owner_user_id)
                    .where(
                        DataExportRequest.id == export_id,
                        DataExportRequest.owner_user_id == user_id,
                        User.status == "active",
                    )
                ),
            )
            if export is None:
                raise DataExportAccessDenied()
            return self._result(export)

    async def create_download_grant(self, *, user_id: str, export_id: str) -> PrivateDownloadGrant:
        export = await self._downloadable(user_id=user_id, export_id=export_id)
        metadata = await self._storage.inspect_data_export(object_key=cast(str, export.storage_key))
        if metadata is None or not (
            metadata.byte_size == export.byte_size
            and hmac.compare_digest(metadata.sha256, cast(str, export.sha256))
        ):
            raise DataExportAccessDenied()
        return await self._storage.create_private_download_grant(
            object_key=cast(str, export.storage_key), request_reference=export.id
        )

    async def redeem_local_download(
        self, *, grant_id: str, authorization: str
    ) -> LocalDownloadRedemption:
        if not isinstance(self._storage, LocalObjectStorageProvider):
            raise DataExportAccessDenied()
        redemption = await self._storage.redeem_private_download_grant(
            grant_id=grant_id, authorization=authorization
        )
        export = await self._downloadable_by_reference(export_id=redemption.request_reference)
        if not (
            redemption.content_type == "application/zip"
            and redemption.content_length == export.byte_size
            and hmac.compare_digest(redemption.sha256, cast(str, export.sha256))
        ):
            raise DataExportAccessDenied()
        return redemption

    async def cleanup_expired(self, *, limit: int = 100) -> tuple[str, ...]:
        if limit < 1 or limit > 1_000:
            raise ValueError("data export cleanup limit must be between 1 and 1000")
        async with self._sessions() as session:
            export_ids = tuple(
                await session.scalars(
                    select(DataExportRequest.id)
                    .where(
                        DataExportRequest.status == "ready",
                        DataExportRequest.expires_at <= self._now(),
                    )
                    .order_by(DataExportRequest.expires_at, DataExportRequest.id)
                    .limit(limit)
                )
            )
        completed: list[str] = []
        for export_id in export_ids:
            if await self._expire_one(export_id):
                completed.append(export_id)
        return tuple(completed)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        async with self._sessions() as session:
            return tuple(
                await session.scalars(
                    select(Job.id)
                    .join(DataExportRequest, DataExportRequest.job_id == Job.id)
                    .where(DataExportRequest.status.in_(("requested", "processing")))
                    .order_by(DataExportRequest.requested_at, Job.id)
                    .limit(limit)
                )
            )

    async def _start(self, job_id: str) -> DataExportResult | None:
        async with self._sessions() as session:
            export, job = await self._locked(session, job_id)
            if export is None or job is None:
                return None
            if export.status in ("ready", "failed", "expired"):
                return self._result(export)
            if export.status == "requested":
                now = self._now()
                export.status = "processing"
                job.status = "processing"
                job.updated_at = now
                session.add(
                    DataExportEvent(
                        id=new_id(),
                        request_id=export.id,
                        event_type="processing_started",
                        occurred_at=now,
                    )
                )
            await session.commit()
            return self._result(export)

    async def _snapshot(
        self, export_id: str
    ) -> (
        tuple[
            User,
            tuple[PolicyAcceptanceRecord, ...],
            tuple[ConsentRecord, ...],
            tuple[Asset, ...],
        ]
        | None
    ):
        async with self._sessions() as session:
            export = await session.get(DataExportRequest, export_id)
            if export is None:
                return None
            user = cast(
                User | None,
                await session.scalar(
                    select(User).where(User.id == export.owner_user_id, User.status == "active")
                ),
            )
            if user is None:
                return None
            policies = tuple(
                await session.scalars(
                    select(PolicyAcceptanceRecord)
                    .where(PolicyAcceptanceRecord.user_id == user.id)
                    .order_by(PolicyAcceptanceRecord.accepted_at, PolicyAcceptanceRecord.id)
                )
            )
            consents = tuple(
                await session.scalars(
                    select(ConsentRecord)
                    .where(ConsentRecord.user_id == user.id)
                    .order_by(ConsentRecord.created_at, ConsentRecord.id)
                )
            )
            assets = tuple(
                await session.scalars(
                    select(Asset)
                    .where(Asset.owner_user_id == user.id, Asset.deleted_at.is_(None))
                    .order_by(Asset.created_at, Asset.id)
                )
            )
            return user, policies, consents, assets

    async def _publish_and_mark_ready(
        self, *, job_id: str, object_key: str, archive: ExportArchive
    ) -> DataExportResult | None:
        async with self._sessions() as session:
            try:
                owner_user_id = cast(
                    str | None,
                    await session.scalar(
                        select(DataExportRequest.owner_user_id)
                        .join(Job, Job.id == DataExportRequest.job_id)
                        .where(Job.id == job_id, Job.job_type == "data_export")
                    ),
                )
                if owner_user_id is None:
                    return None
                user = cast(
                    User | None,
                    await session.scalar(
                        select(User).where(User.id == owner_user_id).with_for_update()
                    ),
                )
                if user is None or user.status != "active":
                    return None
                export, job = await self._locked(session, job_id)
                if export is None or job is None or export.owner_user_id != user.id:
                    raise RetryableDataExportFailure("export publication authority changed")
                if export.status == "ready":
                    if not (
                        export.storage_key == object_key
                        and export.byte_size == archive.byte_size
                        and hmac.compare_digest(cast(str, export.sha256), archive.sha256)
                    ):
                        raise RetryableDataExportFailure("ready export metadata conflict")
                    return self._result(export)
                if export.status != "processing":
                    return None

                # Publication happens while holding the same User row lock used by
                # account-deletion admission. Therefore deletion either observes a
                # committed ready export and removes it, or freezes the account
                # before this method can publish anything.
                await self._storage.create_data_export_if_absent(
                    object_key=object_key,
                    content_length=archive.byte_size,
                    checksum_sha256=archive.sha256,
                    body=archive.body(),
                )
                now = self._now()
                export.status = "ready"
                export.storage_key = object_key
                export.byte_size = archive.byte_size
                export.sha256 = archive.sha256
                export.ready_at = now
                export.expires_at = now + timedelta(seconds=self._retention_seconds)
                export.result_code = "archive_ready"
                job.status = "completed"
                job.finalized_at = now
                job.result_code = "archive_ready"
                job.updated_at = now
                session.add(
                    DataExportEvent(
                        id=new_id(),
                        request_id=export.id,
                        event_type="ready",
                        result_code="archive_ready",
                        occurred_at=now,
                    )
                )
                await session.commit()
                return self._result(export)
            except RetryableDataExportFailure:
                await session.rollback()
                raise
            except Exception as exc:
                await session.rollback()
                raise RetryableDataExportFailure(
                    "private export archive publication failed"
                ) from exc

    async def _fail(self, job_id: str, result_code: str) -> None:
        async with self._sessions() as session:
            export, job = await self._locked(session, job_id)
            if export is None or job is None or export.status in ("ready", "failed", "expired"):
                return
            now = self._now()
            export.status = "failed"
            export.result_code = result_code
            job.status = "failed"
            job.finalized_at = now
            job.result_code = result_code
            job.updated_at = now
            session.add(
                DataExportEvent(
                    id=new_id(),
                    request_id=export.id,
                    event_type="failed",
                    result_code=result_code,
                    occurred_at=now,
                )
            )
            await session.commit()

    async def _expire_one(self, export_id: str) -> bool:
        async with self._sessions() as session:
            export = cast(
                DataExportRequest | None,
                await session.scalar(
                    select(DataExportRequest)
                    .where(DataExportRequest.id == export_id)
                    .with_for_update()
                ),
            )
            if (
                export is None
                or export.status != "ready"
                or export.expires_at is None
                or export.expires_at > self._now()
            ):
                return False
            key = cast(str, export.storage_key)
        try:
            outcome = await self._storage.delete_data_export(object_key=key)
        except Exception as exc:
            raise RetryableDataExportFailure("expired export deletion failed") from exc
        async with self._sessions() as session:
            export = cast(
                DataExportRequest | None,
                await session.scalar(
                    select(DataExportRequest)
                    .where(DataExportRequest.id == export_id)
                    .with_for_update()
                ),
            )
            if export is None or export.status == "expired":
                return export is not None
            if (
                export.status != "ready"
                or export.expires_at is None
                or export.expires_at > self._now()
            ):
                raise RetryableDataExportFailure("export expiry state changed during cleanup")
            now = self._now()
            await session.execute(
                insert(ObjectDeletionEvidence)
                .values(
                    id=new_id(),
                    owner_user_id=export.owner_user_id,
                    data_export_request_id=export.id,
                    target_data_export_request_id=export.id,
                    object_kind="data_export",
                    outcome=outcome,
                    result_code="deleted" if outcome == "deleted" else "already_absent",
                    completed_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["data_export_request_id", "target_data_export_request_id"]
                )
            )
            export.status = "expired"
            export.deleted_at = now
            export.result_code = "retention_expired"
            session.add(
                DataExportEvent(
                    id=new_id(),
                    request_id=export.id,
                    event_type="expired",
                    result_code="retention_expired",
                    occurred_at=now,
                )
            )
            await session.commit()
            return True

    async def _downloadable(self, *, user_id: str, export_id: str) -> DataExportRequest:
        async with self._sessions() as session:
            export = cast(
                DataExportRequest | None,
                await session.scalar(
                    select(DataExportRequest)
                    .join(User, User.id == DataExportRequest.owner_user_id)
                    .where(
                        DataExportRequest.id == export_id,
                        DataExportRequest.owner_user_id == user_id,
                        DataExportRequest.status == "ready",
                        DataExportRequest.expires_at > self._now(),
                        User.status == "active",
                    )
                ),
            )
            if export is None:
                raise DataExportAccessDenied()
            return export

    async def _downloadable_by_reference(self, *, export_id: str) -> DataExportRequest:
        async with self._sessions() as session:
            export = cast(
                DataExportRequest | None,
                await session.scalar(
                    select(DataExportRequest)
                    .join(User, User.id == DataExportRequest.owner_user_id)
                    .where(
                        DataExportRequest.id == export_id,
                        DataExportRequest.status == "ready",
                        DataExportRequest.expires_at > self._now(),
                        User.status == "active",
                    )
                ),
            )
            if export is None:
                raise DataExportAccessDenied()
            return export

    async def _by_job(self, job_id: str) -> DataExportResult | None:
        async with self._sessions() as session:
            export = cast(
                DataExportRequest | None,
                await session.scalar(
                    select(DataExportRequest).where(DataExportRequest.job_id == job_id)
                ),
            )
            return None if export is None else self._result(export)

    @staticmethod
    async def _locked(
        session: AsyncSession, job_id: str
    ) -> tuple[DataExportRequest | None, Job | None]:
        job = cast(Job | None, await session.get(Job, job_id, with_for_update=True))
        if job is None or job.job_type != "data_export":
            return None, None
        export = cast(
            DataExportRequest | None,
            await session.scalar(
                select(DataExportRequest)
                .where(DataExportRequest.job_id == job.id)
                .with_for_update()
            ),
        )
        return export, job

    @staticmethod
    def _result(export: DataExportRequest) -> DataExportResult:
        return DataExportResult(
            export_id=export.id,
            job_id=export.job_id,
            status=export.status,
            schema_version=export.schema_version,
            requested_at=export.requested_at,
            ready_at=export.ready_at,
            expires_at=export.expires_at,
        )

    def _key_hash(self, user_id: str, value: str) -> str:
        material = hmac_digest(
            "data-export:" + dumps([user_id, value], separators=(",", ":")),
            purpose="idempotency",
            keyring=self._hmac_keyring,
            key_id=self._hmac_active_kid,
        )
        return sha256(material.encode()).hexdigest()

    def _job_key_hash(self, user_id: str, value: str) -> str:
        return sha256(("job:" + self._key_hash(user_id, value)).encode()).hexdigest()
