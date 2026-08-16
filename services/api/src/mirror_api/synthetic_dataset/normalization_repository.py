from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.models import (
    Asset,
    SyntheticAssetRecord,
    SyntheticSourceObject,
    SyntheticSourceObjectDeletionEvidence,
)


class SyntheticNormalizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def locked_source(self, source_object_id: str) -> SyntheticSourceObject | None:
        return cast(
            SyntheticSourceObject | None,
            await self._session.scalar(
                select(SyntheticSourceObject)
                .where(SyntheticSourceObject.id == source_object_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    async def source_was_deleted(self, source_object_id: str) -> bool:
        evidence_id = await self._session.scalar(
            select(SyntheticSourceObjectDeletionEvidence.id).where(
                SyntheticSourceObjectDeletionEvidence.source_object_id == source_object_id
            )
        )
        return evidence_id is not None

    async def locked_record_by_source(self, source_object_id: str) -> SyntheticAssetRecord | None:
        return cast(
            SyntheticAssetRecord | None,
            await self._session.scalar(
                select(SyntheticAssetRecord)
                .where(SyntheticAssetRecord.source_object_id == source_object_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    async def locked_record(self, record_id: str) -> SyntheticAssetRecord | None:
        return cast(
            SyntheticAssetRecord | None,
            await self._session.scalar(
                select(SyntheticAssetRecord)
                .where(SyntheticAssetRecord.id == record_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    async def record(self, record_id: str) -> SyntheticAssetRecord | None:
        return cast(
            SyntheticAssetRecord | None,
            await self._session.scalar(
                select(SyntheticAssetRecord).where(SyntheticAssetRecord.id == record_id)
            ),
        )

    async def asset(self, asset_id: str) -> Asset | None:
        return cast(
            Asset | None,
            await self._session.scalar(select(Asset).where(Asset.id == asset_id)),
        )

    def add(self, value: object) -> None:
        self._session.add(value)

    async def flush(self) -> None:
        await self._session.flush()
