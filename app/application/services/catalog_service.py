from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.application.errors import NotFoundError
from app.domain.entities.category import Category
from app.domain.entities.category_translation import CategoryTranslation
from app.domain.entities.course import Course
from app.domain.entities.course_translation import CourseTranslation
from app.domain.repositories.category_repository import CategoryRepository
from app.domain.repositories.course_repository import CourseRepository
from app.domain.repositories.translation_repository import TranslationRepository


@dataclass(slots=True)
class LocalizedCategory:
    id: int
    name: str
    language: str
    fallback_used: bool


@dataclass(slots=True)
class LocalizedCourse:
    id: int
    name: str
    description: str
    category_id: int
    price: Decimal
    link: str
    language: str
    fallback_used: bool
    extra: dict[str, Any] = field(default_factory=dict)


class CatalogService:
    def __init__(
        self,
        categories: CategoryRepository,
        courses: CourseRepository,
        translations: TranslationRepository | None = None,
    ) -> None:
        self._categories = categories
        self._courses = courses
        self._translations = translations

    async def list_categories(self) -> list[Category]:
        return await self._categories.list_all()

    async def list_localized_categories(self, language_code: str) -> list[LocalizedCategory]:
        categories = await self._categories.list_all()
        translations = await self._category_translation_map(language_code)
        localized: list[LocalizedCategory] = []
        for category in categories:
            assert category.id is not None
            translation = translations.get(category.id)
            localized.append(
                LocalizedCategory(
                    id=category.id,
                    name=translation.name if translation else category.name,
                    language=language_code,
                    fallback_used=translation is None,
                )
            )
        return localized

    async def list_courses(self, category_id: int) -> list[Course]:
        category = await self._categories.get(category_id)
        if category is None:
            raise NotFoundError("Category not found")
        return await self._courses.list_active_by_category(category_id)

    async def list_localized_courses(
        self, category_id: int, language_code: str
    ) -> list[LocalizedCourse]:
        courses = await self.list_courses(category_id)
        translations = await self._course_translation_map(category_id, language_code)
        localized: list[LocalizedCourse] = []
        for course in courses:
            assert course.id is not None
            translation = translations.get(course.id)
            localized.append(
                LocalizedCourse(
                    id=course.id,
                    name=translation.name if translation else course.name,
                    description=translation.description if translation else course.description,
                    category_id=course.category_id,
                    price=course.price,
                    link=course.link,
                    language=language_code,
                    fallback_used=translation is None,
                    extra=dict(course.extra),
                )
            )
        return localized

    async def get_course(self, course_id: int) -> Course:
        course = await self._courses.get_active(course_id)
        if course is None:
            raise NotFoundError("Course not found")
        return course

    async def get_localized_course(self, course_id: int, language_code: str) -> LocalizedCourse:
        course = await self.get_course(course_id)
        return await self._localize_course(course, language_code)

    async def get_localized_course_by_catalog_slug(
        self, catalog_slug: str, language_code: str
    ) -> LocalizedCourse:
        course = await self._courses.get_by_catalog_slug(catalog_slug)
        if course is None or not course.is_active:
            raise NotFoundError("Course not found")
        return await self._localize_course(course, language_code)

    async def _localize_course(self, course: Course, language_code: str) -> LocalizedCourse:
        translation = None
        if self._translations is not None and course.id is not None:
            translation = await self._translations.get_course_translation(course.id, language_code)
        assert course.id is not None
        return LocalizedCourse(
            id=course.id,
            name=translation.name if translation else course.name,
            description=translation.description if translation else course.description,
            category_id=course.category_id,
            price=course.price,
            link=course.link,
            language=language_code,
            fallback_used=translation is None,
            extra=dict(course.extra),
        )

    async def _category_translation_map(self, language_code: str) -> dict[int, CategoryTranslation]:
        if self._translations is None:
            return {}
        translations = await self._translations.list_category_translations(language_code)
        return {translation.category_id: translation for translation in translations}

    async def _course_translation_map(
        self, category_id: int, language_code: str
    ) -> dict[int, CourseTranslation]:
        if self._translations is None:
            return {}
        translations = await self._translations.list_course_translations_by_category(
            category_id, language_code
        )
        return {translation.course_id: translation for translation in translations}
