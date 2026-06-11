from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class SearchSuggestion:
    type: str
    id: int
    title: str
    subtitle: str | None
    score: float


class SuggestionSearchRepository(ABC):
    @abstractmethod
    async def suggest(
        self, query: str, language_code: str, limit: int
    ) -> list[SearchSuggestion]: ...
