import pytest

from app.application.errors import ValidationError
from app.application.services.search_service import SearchService
from app.domain.entities.course import Course
from app.domain.repositories.rate_limiter import RateLimiter
from app.domain.repositories.search_repository import SearchRepository
from app.domain.repositories.suggestion_search_repository import (
    SearchSuggestion,
    SuggestionSearchRepository,
)


class AllowAllRateLimiter(RateLimiter):
    async def allow(self, key: str) -> bool:
        return True


class EmptySearchRepository(SearchRepository):
    async def search_active(self, query: str, limit: int = 20) -> list[Course]:
        return []


class FakeSuggestionRepository(SuggestionSearchRepository):
    async def suggest(self, query: str, language_code: str, limit: int) -> list[SearchSuggestion]:
        return [SearchSuggestion("course", 1, "Async FastAPI", "Build APIs.", 1.0)]


@pytest.mark.asyncio
async def test_suggest_rejects_short_queries() -> None:
    service = SearchService(
        EmptySearchRepository(),
        AllowAllRateLimiter(),
        FakeSuggestionRepository(),
    )

    with pytest.raises(ValidationError):
        await service.suggest("fa", "en", "tg:1")


@pytest.mark.asyncio
async def test_suggest_returns_ranked_suggestions() -> None:
    service = SearchService(
        EmptySearchRepository(),
        AllowAllRateLimiter(),
        FakeSuggestionRepository(),
    )

    suggestions = await service.suggest("fas", "en", "tg:1")

    assert suggestions[0].title == "Async FastAPI"
    assert suggestions[0].score == 1.0
