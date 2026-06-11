from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.category import Category
from app.domain.repositories.category_repository import CategoryRepository
from app.infrastructure.db.models.category import CategoryModel


def _to_entity(model: CategoryModel) -> Category:
    return Category(id=model.id, name=model.name, extra=dict(model.extra))


class SqlCategoryRepository(CategoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Category]:
        result = await self._session.execute(select(CategoryModel).order_by(CategoryModel.name))
        return [_to_entity(row) for row in result.scalars().all()]

    async def get(self, category_id: int) -> Category | None:
        model = await self._session.get(CategoryModel, category_id)
        return _to_entity(model) if model is not None else None

    async def add(self, category: Category) -> Category:
        model = CategoryModel(name=category.name, extra=category.extra)
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)
