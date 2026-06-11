from decimal import Decimal

import pytest

from app.application.services.catalog_service import CatalogService
from app.domain.entities.category import Category
from app.domain.entities.category_translation import CategoryTranslation
from app.domain.entities.course import Course
from app.domain.entities.course_translation import CourseTranslation
from app.domain.repositories.category_repository import CategoryRepository
from app.domain.repositories.course_repository import CourseRepository
from app.domain.repositories.translation_repository import TranslationRepository


class FakeCategoryRepository(CategoryRepository):
    async def list_all(self) -> list[Category]:
        return [Category(id=1, name="Programming")]

    async def get(self, category_id: int) -> Category | None:
        return Category(id=category_id, name="Programming")

    async def add(self, category: Category) -> Category:
        return category


class FakeCourseRepository(CourseRepository):
    async def list_active_by_category(self, category_id: int) -> list[Course]:
        return [
            Course(
                id=2,
                name="Async FastAPI",
                description="Build async APIs.",
                category_id=category_id,
                price=Decimal("79.00"),
                link="https://example.com/fastapi",
            )
        ]

    async def get_active(self, course_id: int) -> Course | None:
        return Course(
            id=course_id,
            name="Async FastAPI",
            description="Build async APIs.",
            category_id=1,
            price=Decimal("79.00"),
            link="https://example.com/fastapi",
        )

    async def get(self, course_id: int) -> Course | None:
        return await self.get_active(course_id)

    async def add(self, course: Course) -> Course:
        return course


class FakeTranslationRepository(TranslationRepository):
    async def get_category_translation(
        self, category_id: int, language_code: str
    ) -> CategoryTranslation | None:
        return CategoryTranslation(
            id=1, category_id=category_id, language_code=language_code, name="Програмування"
        )

    async def list_category_translations(self, language_code: str) -> list[CategoryTranslation]:
        return [
            CategoryTranslation(
                id=1, category_id=1, language_code=language_code, name="Програмування"
            )
        ]

    async def get_course_translation(
        self, course_id: int, language_code: str
    ) -> CourseTranslation | None:
        return None

    async def list_course_translations_by_category(
        self, category_id: int, language_code: str
    ) -> list[CourseTranslation]:
        return []

    async def add_category_translation(
        self, translation: CategoryTranslation
    ) -> CategoryTranslation:
        return translation

    async def add_course_translation(self, translation: CourseTranslation) -> CourseTranslation:
        return translation


@pytest.mark.asyncio
async def test_localized_categories_use_translation() -> None:
    service = CatalogService(
        FakeCategoryRepository(), FakeCourseRepository(), FakeTranslationRepository()
    )

    categories = await service.list_localized_categories("uk")

    assert categories[0].name == "Програмування"
    assert categories[0].fallback_used is False


@pytest.mark.asyncio
async def test_localized_courses_fall_back_to_base_content() -> None:
    service = CatalogService(
        FakeCategoryRepository(), FakeCourseRepository(), FakeTranslationRepository()
    )

    courses = await service.list_localized_courses(1, "uk")

    assert courses[0].name == "Async FastAPI"
    assert courses[0].fallback_used is True
