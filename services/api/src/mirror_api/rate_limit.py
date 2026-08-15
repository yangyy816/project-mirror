from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class RateLimitUnavailable(RuntimeError):
    """Raised when a fail-closed rate-limit decision cannot be made."""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter(Protocol):
    async def check(
        self, *, bucket: str, key: str, limit: int, window_seconds: int
    ) -> RateLimitResult: ...


class RedisEvalClient(Protocol):
    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> list[int]: ...


class FakeRateLimiter:
    """Deterministic in-memory limiter for development, test, and CI only."""

    def __init__(self, *, now: Callable[[], float] | None = None) -> None:
        self._now = now or time.monotonic
        self._buckets: dict[str, tuple[float, int]] = {}

    async def check(
        self, *, bucket: str, key: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate-limit limit and window must be positive")
        identifier = f"{bucket}:{key}"
        now = self._now()
        expires_at, count = self._buckets.get(identifier, (now + window_seconds, 0))
        if now >= expires_at:
            expires_at, count = now + window_seconds, 0
        count += 1
        self._buckets[identifier] = (expires_at, count)
        retry_after = max(0, int(expires_at - now))
        if count > limit:
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)
        return RateLimitResult(
            allowed=True,
            remaining=limit - count,
            retry_after_seconds=retry_after,
        )


_INCREMENT_WITH_EXPIRY = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


class RedisRateLimiter:
    """Redis-backed limiter; a Redis error is deliberately not converted to allow."""

    def __init__(self, client: RedisEvalClient, *, prefix: str = "mirror:rate-limit") -> None:
        self._client = client
        self._prefix = prefix

    async def check(
        self, *, bucket: str, key: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate-limit limit and window must be positive")
        redis_key = f"{self._prefix}:{bucket}:{key}"
        try:
            result = await self._client.eval(_INCREMENT_WITH_EXPIRY, 1, redis_key, window_seconds)
            count, ttl = (int(value) for value in result)
        except Exception as exc:
            raise RateLimitUnavailable("rate limiter unavailable") from exc
        retry_after = max(0, ttl)
        if count > limit:
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)
        return RateLimitResult(
            allowed=True,
            remaining=limit - count,
            retry_after_seconds=retry_after,
        )
