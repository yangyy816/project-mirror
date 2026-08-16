from __future__ import annotations

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
    Asset,
    AssetDeletionEvent,
    AssetDeletionRequest,
    AssetVariant,
    Job,
    ObjectDeletionEvidence,
    User,
    new_id,
)
from mirror_api.providers.base import ObjectStorageProvider
from mirror_api.security import hmac_digest


class AssetDeletionFailure(Exception):
    pass


class RetryableAssetDeletionFailure(Exception):
    pass


@dataclass(frozen=True)
class AssetDeletionResult:
    request_id: str
    job_id: str
    status: str
    created: bool = False


class AssetDeletionService:
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
        self, *, user_id: str, asset_id: str, idempotency_key: str, request_id: str
    ) -> AssetDeletionResult:
        key_hash = self._key_hash(user_id, idempotency_key)
        async with self._sessions() as session:
            try:
                user = cast(
                    User | None,
                    await session.scalar(select(User).where(User.id == user_id).with_for_update()),
                )
                if user is None or user.status != "active":
                    raise AssetDeletionFailure()
                replay = cast(
                    AssetDeletionRequest | None,
                    await session.scalar(
                        select(AssetDeletionRequest).where(
                            AssetDeletionRequest.idempotency_key_hash == key_hash
                        )
                    ),
                )
                if replay is not None:
                    if replay.owner_user_id != user_id or replay.asset_id != asset_id:
                        raise AssetDeletionFailure()
                    return AssetDeletionResult(
                        request_id=replay.id,
                        job_id=replay.job_id,
                        status=replay.status,
                    )
                assets, depths = await self._locked_dependency_assets(
                    session, user_id=user_id, root_asset_id=asset_id
                )
                if not assets or assets[0].deleted_at is not None:
                    raise AssetDeletionFailure()
                now = self._now()
                for asset in assets:
                    asset.deleted_at = now
                job = Job(
                    id=new_id(),
                    owner_user_id=user_id,
                    job_type="asset_deletion",
                    status="pending",
                    idempotency_key_hash=self._job_key_hash(user_id, idempotency_key),
                    request_id=request_id,
                    payload={"schema_version": "asset-deletion-task-v1"},
                    created_at=now,
                    updated_at=now,
                )
                deletion = AssetDeletionRequest(
                    id=new_id(),
                    owner_user_id=user_id,
                    asset_id=asset_id,
                    job_id=job.id,
                    idempotency_key_hash=key_hash,
                    status="requested",
                    requested_at=now,
                )
                session.add(job)
                await session.flush()
                session.add(deletion)
                await session.flush()
                session.add(
                    AssetDeletionEvent(
                        id=new_id(), request_id=deletion.id, event_type="requested", occurred_at=now
                    )
                )
                await session.commit()
                del depths
                return AssetDeletionResult(
                    request_id=deletion.id,
                    job_id=job.id,
                    status=deletion.status,
                    created=True,
                )
            except Exception:
                await session.rollback()
                raise

    async def process(self, *, job_id: str) -> AssetDeletionResult | None:
        await self._start(job_id)
        targets = await self._targets(job_id)
        if targets is None:
            return None
        request, assets = targets
        for asset in assets:
            if await self._has_evidence(request.id, asset.id):
                continue
            try:
                outcome = await self._storage.delete_sanitized_object(object_key=asset.storage_key)
            except Exception as exc:
                raise RetryableAssetDeletionFailure("private object deletion failed") from exc
            await self._record_evidence(request_id=request.id, asset=asset, outcome=outcome)
        return await self._complete(job_id)

    async def reconcile(self, *, limit: int = 100) -> tuple[str, ...]:
        if limit < 1 or limit > 1_000:
            raise ValueError("asset deletion reconciliation limit must be between 1 and 1000")
        async with self._sessions() as session:
            return tuple(
                await session.scalars(
                    select(Job.id)
                    .join(AssetDeletionRequest, AssetDeletionRequest.job_id == Job.id)
                    .where(
                        Job.job_type == "asset_deletion",
                        AssetDeletionRequest.status.in_(("requested", "processing")),
                    )
                    .order_by(AssetDeletionRequest.requested_at, Job.id)
                    .limit(limit)
                )
            )

    async def _start(self, job_id: str) -> None:
        async with self._sessions() as session:
            request, job = await self._locked_request_job(session, job_id)
            if request is None or job is None or request.status in ("completed", "failed"):
                return
            if request.status == "requested":
                now = self._now()
                request.status = "processing"
                request.started_at = now
                job.status = "processing"
                job.updated_at = now
                session.add(
                    AssetDeletionEvent(
                        id=new_id(),
                        request_id=request.id,
                        event_type="processing_started",
                        occurred_at=now,
                    )
                )
            await session.commit()

    async def _targets(self, job_id: str) -> tuple[AssetDeletionRequest, tuple[Asset, ...]] | None:
        async with self._sessions() as session:
            request, job = await self._locked_request_job(session, job_id)
            if request is None or job is None or request.status == "completed":
                return None
            assets, depths = await self._locked_dependency_assets(
                session, user_id=request.owner_user_id, root_asset_id=request.asset_id
            )
            newly_discovered = [asset for asset in assets if asset.deleted_at is None]
            if newly_discovered:
                tombstoned_at = self._now()
                for asset in newly_discovered:
                    asset.deleted_at = tombstoned_at
                await session.commit()
            ordered = tuple(sorted(assets, key=lambda item: depths[item.id], reverse=True))
            return request, ordered

    async def _record_evidence(self, *, request_id: str, asset: Asset, outcome: str) -> None:
        async with self._sessions() as session:
            request = cast(
                AssetDeletionRequest | None,
                await session.scalar(
                    select(AssetDeletionRequest)
                    .where(
                        AssetDeletionRequest.id == request_id,
                        AssetDeletionRequest.owner_user_id == asset.owner_user_id,
                    )
                    .with_for_update()
                ),
            )
            if request is None:
                raise AssetDeletionFailure()
            await session.execute(
                insert(ObjectDeletionEvidence)
                .values(
                    id=new_id(),
                    owner_user_id=cast(str, asset.owner_user_id),
                    asset_deletion_request_id=request_id,
                    target_asset_id=asset.id,
                    object_kind="asset",
                    outcome=outcome,
                    result_code="deleted" if outcome == "deleted" else "already_absent",
                    completed_at=self._now(),
                )
                .on_conflict_do_nothing(
                    index_elements=["asset_deletion_request_id", "target_asset_id"]
                )
            )
            await session.commit()

    async def _complete(self, job_id: str) -> AssetDeletionResult | None:
        async with self._sessions() as session:
            request, job = await self._locked_request_job(session, job_id)
            if request is None or job is None:
                return None
            if request.status == "completed":
                return AssetDeletionResult(request.id, job.id, request.status)
            assets, _ = await self._locked_dependency_assets(
                session, user_id=request.owner_user_id, root_asset_id=request.asset_id
            )
            rows = list(
                await session.scalars(
                    select(ObjectDeletionEvidence.target_asset_id).where(
                        ObjectDeletionEvidence.asset_deletion_request_id == request.id
                    )
                )
            )
            if {asset.id for asset in assets} != set(rows):
                raise RetryableAssetDeletionFailure("physical deletion evidence is incomplete")
            now = self._now()
            request.status = "completed"
            request.completed_at = now
            request.result_code = "objects_deleted"
            job.status = "completed"
            job.finalized_at = now
            job.result_code = "objects_deleted"
            job.updated_at = now
            session.add(
                AssetDeletionEvent(
                    id=new_id(),
                    request_id=request.id,
                    event_type="completed",
                    result_code="objects_deleted",
                    occurred_at=now,
                )
            )
            await session.commit()
            return AssetDeletionResult(request.id, job.id, request.status)

    async def _has_evidence(self, request_id: str, asset_id: str) -> bool:
        async with self._sessions() as session:
            return (
                await session.scalar(
                    select(ObjectDeletionEvidence.id).where(
                        ObjectDeletionEvidence.asset_deletion_request_id == request_id,
                        ObjectDeletionEvidence.target_asset_id == asset_id,
                    )
                )
                is not None
            )

    @staticmethod
    async def _locked_request_job(
        session: AsyncSession, job_id: str
    ) -> tuple[AssetDeletionRequest | None, Job | None]:
        job = cast(Job | None, await session.get(Job, job_id, with_for_update=True))
        if job is None or job.job_type != "asset_deletion":
            return None, None
        request = cast(
            AssetDeletionRequest | None,
            await session.scalar(
                select(AssetDeletionRequest)
                .where(AssetDeletionRequest.job_id == job.id)
                .with_for_update()
            ),
        )
        return request, job

    @staticmethod
    async def _locked_dependency_assets(
        session: AsyncSession, *, user_id: str, root_asset_id: str
    ) -> tuple[list[Asset], dict[str, int]]:
        assets = list(
            await session.scalars(
                select(Asset).where(Asset.owner_user_id == user_id).with_for_update()
            )
        )
        by_id = {asset.id: asset for asset in assets}
        if root_asset_id not in by_id:
            return [], {}
        variants = list(await session.scalars(select(AssetVariant)))
        children: dict[str, list[str]] = {}
        for variant in variants:
            children.setdefault(variant.source_asset_id, []).append(variant.result_asset_id)
        selected: list[Asset] = []
        depths: dict[str, int] = {root_asset_id: 0}
        pending = [root_asset_id]
        while pending:
            current = pending.pop()
            selected.append(by_id[current])
            for child in children.get(current, []):
                if child in by_id and child not in depths:
                    depths[child] = depths[current] + 1
                    pending.append(child)
        return selected, depths

    def _key_hash(self, user_id: str, value: str) -> str:
        material = hmac_digest(
            "asset-delete:" + dumps([user_id, value], separators=(",", ":")),
            purpose="idempotency",
            keyring=self._hmac_keyring,
            key_id=self._hmac_active_kid,
        )
        return sha256(material.encode()).hexdigest()

    def _job_key_hash(self, user_id: str, value: str) -> str:
        return sha256(("job:" + self._key_hash(user_id, value)).encode()).hexdigest()
