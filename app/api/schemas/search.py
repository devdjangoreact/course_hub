from pydantic import BaseModel

from app.domain.repositories.suggestion_search_repository import SearchSuggestion


class SearchSuggestionOut(BaseModel):
    type: str
    id: int
    title: str
    subtitle: str | None
    score: float

    @classmethod
    def from_entity(cls, suggestion: SearchSuggestion) -> "SearchSuggestionOut":
        return cls(
            type=suggestion.type,
            id=suggestion.id,
            title=suggestion.title,
            subtitle=suggestion.subtitle,
            score=suggestion.score,
        )
