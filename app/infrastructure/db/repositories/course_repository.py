from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.course import Course
from app.domain.repositories.course_repository import CourseRepository
from app.infrastructure.db.models.course import CourseModel


def _to_entity(model: CourseModel) -> Course:
    return Course(
        id=model.id,
        name=model.name,
        description=model.description,
        category_id=model.category_id,
        price=model.price,
        link=model.link,
        is_active=model.is_active,
        extra=dict(model.extra),
    )


class SqlCourseRepository(CourseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_by_category(self, category_id: int) -> list[Course]:
        stmt = (
            select(CourseModel)
            .where(CourseModel.category_id == category_id, CourseModel.is_active.is_(True))
            .order_by(CourseModel.name)
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def get_active(self, course_id: int) -> Course | None:
        stmt = select(CourseModel).where(
            CourseModel.id == course_id, CourseModel.is_active.is_(True)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def get(self, course_id: int) -> Course | None:
        model = await self._session.get(CourseModel, course_id)
        return _to_entity(model) if model is not None else None

    async def get_by_catalog_slug(self, slug: str) -> Course | None:
        stmt = select(CourseModel).where(
            CourseModel.extra["catalog_slug"].as_string() == slug,
            CourseModel.is_active.is_(True),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def add(self, course: Course) -> Course:
        model = CourseModel(
            name=course.name,
            description=course.description,
            category_id=course.category_id,
            price=course.price,
            link=course.link,
            is_active=course.is_active,
            extra=course.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def update(self, course: Course) -> Course:
        if course.id is None:
            raise ValueError("Cannot update a course without an id")
        model = await self._session.get(CourseModel, course.id)
        if model is None:
            raise ValueError("Course not found")
        model.name = course.name
        model.description = course.description
        model.category_id = course.category_id
        model.price = course.price
        model.link = course.link
        model.is_active = course.is_active
        model.extra = course.extra
        await self._session.flush()
        return _to_entity(model)
