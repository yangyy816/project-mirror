from __future__ import annotations

import asyncio
from dataclasses import dataclass

import redis.asyncio as redis
from sqlalchemy import create_engine, text

from mirror_api.config import Settings, get_settings


@dataclass(frozen=True)
class DependencyStatus:
    database: str
    redis: str

    @property
    def ready(self) -> bool:
        return self.database == "available" and self.redis == "available"


def _probe_database(database_url: str) -> str:
    try:
        engine = create_engine(
            database_url, pool_pre_ping=True, connect_args={"connect_timeout": 1}
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return "available"
    except Exception:
        return "unavailable"


async def _probe_redis(redis_url: str) -> str:
    client = redis.from_url(  # type: ignore[no-untyped-call]
        redis_url, socket_connect_timeout=1, socket_timeout=1
    )
    try:
        return "available" if await client.ping() else "unavailable"
    except Exception:
        return "unavailable"
    finally:
        await client.aclose()


async def probe_dependencies(settings: Settings | None = None) -> DependencyStatus:
    resolved = settings or get_settings()
    database, redis_state = await asyncio.gather(
        asyncio.to_thread(_probe_database, resolved.database_url),
        _probe_redis(resolved.redis_url),
    )
    return DependencyStatus(database=database, redis=redis_state)
