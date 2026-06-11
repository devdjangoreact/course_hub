from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.suggestion_search_repository import (
    SearchSuggestion,
    SuggestionSearchRepository,
)
from app.infrastructure.db.models.category import CategoryModel
from app.infrastructure.db.models.category_translation import CategoryTranslationModel
from app.infrastructure.db.models.course import CourseModel
from app.infrastructure.db.models.course_translation import CourseTranslationModel


class LocalizedSuggestionSearchRepository(SuggestionSearchRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def suggest(self, query: str, language_code: str, limit: int) -> list[SearchSuggestion]:
        pattern = f"%{query}%"
        suggestions: list[SearchSuggestion] = []
        seen: set[tuple[str, int]] = set()

        translated_courses = await self._translated_courses(pattern, language_code, limit)
        for course_id, title, description in translated_courses:
            self._append(
                suggestions,
                seen,
                SearchSuggestion("course", course_id, title, description, 1.0),
                limit,
            )

        base_courses = await self._base_courses(pattern, limit)
        for course_id, title, description in base_courses:
            self._append(
                suggestions,
                seen,
                SearchSuggestion("course", course_id, title, description, 0.8),
                limit,
            )

        translated_categories = await self._translated_categories(pattern, language_code, limit)
        for category_id, title in translated_categories:
            self._append(
                suggestions,
                seen,
                SearchSuggestion("category", category_id, title, None, 0.7),
                limit,
            )

        base_categories = await self._base_categories(pattern, limit)
        for category_id, title in base_categories:
            self._append(
                suggestions,
                seen,
                SearchSuggestion("category", category_id, title, None, 0.5),
                limit,
            )

        return suggestions[:limit]

    async def _translated_courses(
        self, pattern: str, language_code: str, limit: int
    ) -> list[tuple[int, str, str]]:
        stmt = (
            select(
                CourseModel.id,
                CourseTranslationModel.name,
                CourseTranslationModel.description,
            )
            .join(CourseModel, CourseTranslationModel.course_id == CourseModel.id)
            .where(
                CourseModel.is_active.is_(True),
                CourseTranslationModel.language_code == language_code,
                or_(
                    CourseTranslationModel.name.ilike(pattern),
                    CourseTranslationModel.description.ilike(pattern),
                ),
            )
            .limit(limit)
        )
        return [(row.id, row.name, row.description) for row in (await self._session.execute(stmt))]

    async def _base_courses(self, pattern: str, limit: int) -> list[tuple[int, str, str]]:
        stmt = (
            select(CourseModel.id, CourseModel.name, CourseModel.description)
            .where(
                CourseModel.is_active.is_(True),
                or_(CourseModel.name.ilike(pattern), CourseModel.description.ilike(pattern)),
            )
            .limit(limit)
        )
        return [(row.id, row.name, row.description) for row in (await self._session.execute(stmt))]

    async def _translated_categories(
        self, pattern: str, language_code: str, limit: int
    ) -> list[tuple[int, str]]:
        stmt = (
            select(CategoryTranslationModel.category_id, CategoryTranslationModel.name)
            .where(
                CategoryTranslationModel.language_code == language_code,
                CategoryTranslationModel.name.ilike(pattern),
            )
            .limit(limit)
        )
        return [(row.category_id, row.name) for row in (await self._session.execute(stmt))]

    async def _base_categories(self, pattern: str, limit: int) -> list[tuple[int, str]]:
        stmt = select(CategoryModel.id, CategoryModel.name).where(CategoryModel.name.ilike(pattern))
        result = await self._session.execute(stmt.limit(limit))
        return [(row.id, row.name) for row in result]

    def _append(
        self,
        suggestions: list[SearchSuggestion],
        seen: set[tuple[str, int]],
        suggestion: SearchSuggestion,
        limit: int,
    ) -> None:
        if len(suggestions) >= limit:
            return
        key = (suggestion.type, suggestion.id)
        if key in seen:
            return
        seen.add(key)
        suggestions.append(suggestion)
