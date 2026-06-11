from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.course import Course
from app.domain.repositories.search_repository import SearchRepository
from app.infrastructure.db.models.course import CourseModel


class LikeSearchRepository(SearchRepository):
    """Portable fallback search (ILIKE) used on non-SQLite backends.

    A PostgreSQL `tsvector` implementation can replace this without changing callers.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_active(self, query: str, limit: int = 20) -> list[Course]:
        term = query.strip()
        if not term:
            return []
        pattern = f"%{term}%"
        stmt = (
            select(CourseModel)
            .where(
                CourseModel.is_active.is_(True),
                or_(CourseModel.name.ilike(pattern), CourseModel.description.ilike(pattern)),
            )
            .order_by(CourseModel.name)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            Course(
                id=model.id,
                name=model.name,
                description=model.description,
                category_id=model.category_id,
                price=model.price,
                link=model.link,
                is_active=model.is_active,
                extra=dict(model.extra),
            )
            for model in result.scalars().all()
        ]
