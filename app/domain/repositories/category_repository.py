from abc import ABC, abstractmethod

from app.domain.entities.category import Category


class CategoryRepository(ABC):
    @abstractmethod
    async def list_all(self) -> list[Category]: ...

    @abstractmethod
    async def get(self, category_id: int) -> Category | None: ...

    @abstractmethod
    async def add(self, category: Category) -> Category: ...
