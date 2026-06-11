import time
from collections import defaultdict, deque

from app.domain.repositories.rate_limiter import RateLimiter


class InMemoryRateLimiter(RateLimiter):
    """Sliding-window per-key limiter (phase 1). Swappable for a shared store later."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self._window
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True
