from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import redis.asyncio as redis
from redis.exceptions import RedisError

from mirror_api.rate_limit import FakeRateLimiter, RateLimitUnavailable, RedisRateLimiter


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value


class RecordingRedis:
    def __init__(self, result: list[int]) -> None:
        self.result = result
        self.calls: list[tuple[str, int, tuple[object, ...]]] = []

    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> list[int]:
        self.calls.append((script, numkeys, keys_and_args))
        return self.result


class BrokenRedis:
    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> list[int]:
        del script, numkeys, keys_and_args
        raise OSError("redis unavailable")


@pytest.mark.asyncio
async def test_fake_limiter_is_deterministic_and_expires_windows() -> None:
    clock = Clock()
    limiter = FakeRateLimiter(now=clock.now)
    assert (
        await limiter.check(bucket="phone", key="hmac-phone", limit=2, window_seconds=10)
    ).allowed
    assert (
        await limiter.check(bucket="phone", key="hmac-phone", limit=2, window_seconds=10)
    ).allowed
    assert not (
        await limiter.check(bucket="phone", key="hmac-phone", limit=2, window_seconds=10)
    ).allowed
    clock.value = 10
    assert (
        await limiter.check(bucket="phone", key="hmac-phone", limit=2, window_seconds=10)
    ).allowed


@pytest.mark.asyncio
async def test_redis_limiter_uses_atomic_eval_and_fails_closed() -> None:
    client = RecordingRedis([6, 58])
    result = await RedisRateLimiter(client).check(
        bucket="ip", key="hmac-ip", limit=5, window_seconds=60
    )
    assert not result.allowed
    assert client.calls[0][1] == 1
    with pytest.raises(RateLimitUnavailable):
        await RedisRateLimiter(BrokenRedis()).check(
            bucket="ip", key="hmac-ip", limit=5, window_seconds=60
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_limiter_executes_atomic_increment_limit_and_expiry() -> None:
    redis_url = os.getenv("TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("TEST_REDIS_URL is unavailable locally")

    client = redis.from_url(redis_url, decode_responses=True)
    prefix = f"mirror:test-rate-limit:{uuid.uuid4().hex}"
    limiter = RedisRateLimiter(client, prefix=prefix)
    redis_key = f"{prefix}:phone:hmac-sentinel"
    try:
        await client.ping()
    except RedisError:
        await client.aclose()
        pytest.skip("TEST_REDIS_URL is unavailable locally")

    try:
        results = await asyncio.gather(
            *(
                limiter.check(bucket="phone", key="hmac-sentinel", limit=2, window_seconds=1)
                for _ in range(3)
            )
        )
        assert sorted(result.allowed for result in results) == [False, True, True]
        assert await client.ttl(redis_key) in {0, 1}

        await asyncio.sleep(1.1)
        reset = await limiter.check(bucket="phone", key="hmac-sentinel", limit=2, window_seconds=1)
        assert reset.allowed
        assert reset.remaining == 1
    finally:
        await client.delete(redis_key)
        await client.aclose()
