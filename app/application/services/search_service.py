from app.application.errors import RateLimitedError, ValidationError
from app.domain.entities.course import Course
from app.domain.repositories.rate_limiter import RateLimiter
from app.domain.repositories.search_repository import SearchRepository

_MAX_QUERY_LENGTH = 100


class SearchService:
    def __init__(self, search: SearchRepository, rate_limiter: RateLimiter) -> None:
        self._search = search
        self._rate_limiter = rate_limiter

    async def search(self, raw_query: str, rate_key: str) -> list[Course]:
        query = raw_query.strip()
        if not query:
            raise ValidationError("Search query must not be empty")
        if len(query) > _MAX_QUERY_LENGTH:
            query = query[:_MAX_QUERY_LENGTH]
        if not await self._rate_limiter.allow(rate_key):
            raise RateLimitedError("Too many searches, please slow down")
        return await self._search.search_active(query)
