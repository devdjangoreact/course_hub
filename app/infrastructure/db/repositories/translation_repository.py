from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.category_translation import CategoryTranslation
from app.domain.entities.course_translation import CourseTranslation
from app.domain.repositories.translation_repository import TranslationRepository
from app.infrastructure.db.models.category_translation import CategoryTranslationModel
from app.infrastructure.db.models.course import CourseModel
from app.infrastructure.db.models.course_translation import CourseTranslationModel


def _category_to_entity(model: CategoryTranslationModel) -> CategoryTranslation:
    return CategoryTranslation(
        id=model.id,
        category_id=model.category_id,
        language_code=model.language_code,
        name=model.name,
        extra=dict(model.extra),
    )


def _course_to_entity(model: CourseTranslationModel) -> CourseTranslation:
    return CourseTranslation(
        id=model.id,
        course_id=model.course_id,
        language_code=model.language_code,
        name=model.name,
        description=model.description,
        extra=dict(model.extra),
    )


class SqlTranslationRepository(TranslationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_category_translation(
        self, category_id: int, language_code: str
    ) -> CategoryTranslation | None:
        stmt = select(CategoryTranslationModel).where(
            CategoryTranslationModel.category_id == category_id,
            CategoryTranslationModel.language_code == language_code,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _category_to_entity(model) if model is not None else None

    async def list_category_translations(self, language_code: str) -> list[CategoryTranslation]:
        stmt = select(CategoryTranslationModel).where(
            CategoryTranslationModel.language_code == language_code
        )
        result = await self._session.execute(stmt)
        return [_category_to_entity(model) for model in result.scalars().all()]

    async def get_course_translation(
        self, course_id: int, language_code: str
    ) -> CourseTranslation | None:
        stmt = select(CourseTranslationModel).where(
            CourseTranslationModel.course_id == course_id,
            CourseTranslationModel.language_code == language_code,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _course_to_entity(model) if model is not None else None

    async def list_course_translations_by_category(
        self, category_id: int, language_code: str
    ) -> list[CourseTranslation]:
        stmt = (
            select(CourseTranslationModel)
            .join(CourseModel, CourseTranslationModel.course_id == CourseModel.id)
            .where(
                CourseTranslationModel.language_code == language_code,
                CourseModel.category_id == category_id,
            )
        )
        result = await self._session.execute(stmt)
        return [_course_to_entity(model) for model in result.scalars().all()]

    async def add_category_translation(
        self, translation: CategoryTranslation
    ) -> CategoryTranslation:
        model = CategoryTranslationModel(
            category_id=translation.category_id,
            language_code=translation.language_code,
            name=translation.name,
            extra=translation.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _category_to_entity(model)

    async def add_course_translation(self, translation: CourseTranslation) -> CourseTranslation:
        model = CourseTranslationModel(
            course_id=translation.course_id,
            language_code=translation.language_code,
            name=translation.name,
            description=translation.description,
            extra=translation.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _course_to_entity(model)
