from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.auth.types import PersistedAuthFailure


@asynccontextmanager
async def transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Open one short PostgreSQL transaction for an application operation."""
    async with session_factory() as session:
        try:
            yield session
        except PersistedAuthFailure as signal:
            # Only explicitly selected security state changes are durable on failure.
            await session.commit()
            raise signal.failure from signal
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
