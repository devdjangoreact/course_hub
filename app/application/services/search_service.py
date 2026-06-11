from app.application.errors import RateLimitedError, ValidationError
from app.domain.entities.course import Course
from app.domain.repositories.rate_limiter import RateLimiter
from app.domain.repositories.search_repository import SearchRepository
from app.domain.repositories.suggestion_search_repository import (
    SearchSuggestion,
    SuggestionSearchRepository,
)

_MAX_QUERY_LENGTH = 100
_MIN_SUGGESTION_LENGTH = 3


class SearchService:
    def __init__(
        self,
        search: SearchRepository,
        rate_limiter: RateLimiter,
        suggestions: SuggestionSearchRepository | None = None,
        suggestion_min_chars: int = _MIN_SUGGESTION_LENGTH,
        suggestion_limit: int = 5,
    ) -> None:
        self._search = search
        self._rate_limiter = rate_limiter
        self._suggestions = suggestions
        self._suggestion_min_chars = suggestion_min_chars
        self._suggestion_limit = suggestion_limit

    async def search(self, raw_query: str, rate_key: str) -> list[Course]:
        query = raw_query.strip()
        if not query:
            raise ValidationError("Search query must not be empty")
        if len(query) > _MAX_QUERY_LENGTH:
            query = query[:_MAX_QUERY_LENGTH]
        if not await self._rate_limiter.allow(rate_key):
            raise RateLimitedError("Too many searches, please slow down")
        return await self._search.search_active(query)

    async def suggest(
        self,
        raw_query: str,
        language_code: str,
        rate_key: str,
        limit: int | None = None,
    ) -> list[SearchSuggestion]:
        query = raw_query.strip()
        if len(query) < self._suggestion_min_chars:
            raise ValidationError("Search query must be at least 3 characters")
        if len(query) > _MAX_QUERY_LENGTH:
            query = query[:_MAX_QUERY_LENGTH]
        if not await self._rate_limiter.allow(rate_key):
            raise RateLimitedError("Too many searches, please slow down")
        if self._suggestions is None:
            return []
        bounded_limit = min(limit or self._suggestion_limit, self._suggestion_limit)
        return await self._suggestions.suggest(query, language_code, bounded_limit)
