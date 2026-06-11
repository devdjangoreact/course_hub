from app.infrastructure.ratelimit.in_memory_rate_limiter import InMemoryRateLimiter


async def test_allows_up_to_limit() -> None:
    limiter = InMemoryRateLimiter(limit=5, window_seconds=60)
    results = [await limiter.allow("user:1") for _ in range(5)]
    assert all(results)


async def test_blocks_over_limit() -> None:
    limiter = InMemoryRateLimiter(limit=5, window_seconds=60)
    for _ in range(5):
        assert await limiter.allow("user:1")
    assert await limiter.allow("user:1") is False


async def test_isolated_per_key() -> None:
    limiter = InMemoryRateLimiter(limit=5, window_seconds=60)
    for _ in range(5):
        await limiter.allow("user:1")
    assert await limiter.allow("user:2") is True
