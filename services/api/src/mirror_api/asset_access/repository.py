from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.models import Asset, User


class AssetAccessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_owned_assets(self, *, user_id: str) -> list[Asset]:
        statement = (
            select(Asset)
            .join(User, User.id == Asset.owner_user_id)
            .where(
                Asset.owner_user_id == user_id,
                Asset.deleted_at.is_(None),
                User.status == "active",
            )
            .order_by(Asset.created_at.desc(), Asset.id.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def active_owned_asset(self, *, user_id: str, asset_id: str) -> Asset | None:
        return cast(
            Asset | None,
            await self.session.scalar(
                select(Asset)
                .join(User, User.id == Asset.owner_user_id)
                .where(
                    Asset.id == asset_id,
                    Asset.owner_user_id == user_id,
                    Asset.deleted_at.is_(None),
                    User.status == "active",
                )
            ),
        )

    async def active_asset_by_reference(self, *, asset_id: str) -> Asset | None:
        return cast(
            Asset | None,
            await self.session.scalar(
                select(Asset)
                .join(User, User.id == Asset.owner_user_id)
                .where(
                    Asset.id == asset_id,
                    Asset.deleted_at.is_(None),
                    User.status == "active",
                )
            ),
        )
