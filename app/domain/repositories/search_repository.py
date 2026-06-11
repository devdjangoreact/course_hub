from abc import ABC, abstractmethod

from app.domain.entities.course import Course


class SearchRepository(ABC):
    @abstractmethod
    async def search_active(self, query: str, limit: int = 20) -> list[Course]: ...
