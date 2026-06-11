from pydantic import BaseModel

from app.domain.entities.category import Category


class CategoryOut(BaseModel):
    id: int
    name: str

    @classmethod
    def from_entity(cls, category: Category) -> "CategoryOut":
        assert category.id is not None
        return cls(id=category.id, name=category.name)
