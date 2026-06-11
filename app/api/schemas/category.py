from pydantic import BaseModel

from app.application.services.catalog_service import LocalizedCategory
from app.domain.entities.category import Category


class CategoryOut(BaseModel):
    id: int
    name: str
    language: str | None = None
    fallback_used: bool = False

    @classmethod
    def from_entity(cls, category: Category) -> "CategoryOut":
        assert category.id is not None
        return cls(id=category.id, name=category.name)

    @classmethod
    def from_localized(cls, category: LocalizedCategory) -> "CategoryOut":
        return cls(
            id=category.id,
            name=category.name,
            language=category.language,
            fallback_used=category.fallback_used,
        )
