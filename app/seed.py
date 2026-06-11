import asyncio
from decimal import Decimal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap import ensure_initial_data
from app.core.config import get_settings
from app.core.database import Database
from app.domain.entities.category import Category
from app.domain.entities.course import Course
from app.infrastructure.db.init_db import create_schema
from app.infrastructure.db.models.category_translation import CategoryTranslationModel
from app.infrastructure.db.models.course_translation import CourseTranslationModel
from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository

_DEMO: dict[str, list[tuple[str, str, str, str]]] = {
    "Programming": [
        ("Python Basics", "Learn Python from scratch.", "49.00", "https://example.com/python"),
        ("Async FastAPI", "Build async APIs with FastAPI.", "79.00", "https://example.com/fastapi"),
        (
            "Clean Architecture in Python",
            "Layered, SOLID, testable design.",
            "99.00",
            "https://example.com/clean-arch",
        ),
        (
            "SQLAlchemy 2.0 Async",
            "Async ORM, sessions and migrations.",
            "69.00",
            "https://example.com/sqlalchemy",
        ),
    ],
    "Design": [
        ("UI/UX Fundamentals", "Principles of good design.", "59.00", "https://example.com/uiux"),
        (
            "Figma for Beginners",
            "Design interfaces and prototypes in Figma.",
            "39.00",
            "https://example.com/figma",
        ),
        (
            "Design Systems",
            "Build scalable, reusable component systems.",
            "89.00",
            "https://example.com/design-systems",
        ),
    ],
    "DevOps": [
        (
            "Docker Essentials",
            "Containerize and run apps with Docker.",
            "55.00",
            "https://example.com/docker",
        ),
        (
            "CI/CD with GitHub Actions",
            "Automate build, test and deploy pipelines.",
            "75.00",
            "https://example.com/cicd",
        ),
        (
            "Kubernetes Basics",
            "Deploy and scale services on Kubernetes.",
            "120.00",
            "https://example.com/k8s",
        ),
    ],
    "Data Science": [
        (
            "Pandas Crash Course",
            "Data wrangling and analysis with Pandas.",
            "65.00",
            "https://example.com/pandas",
        ),
        (
            "Machine Learning 101",
            "Core ML concepts and first models.",
            "129.00",
            "https://example.com/ml",
        ),
        (
            "SQL for Analytics",
            "Query and analyze data with SQL.",
            "45.00",
            "https://example.com/sql",
        ),
    ],
    "Marketing": [
        (
            "Telegram Bots for Business",
            "Grow sales with Telegram bot funnels.",
            "59.00",
            "https://example.com/tg-bots",
        ),
        (
            "SEO Fundamentals",
            "Rank higher with on-page and technical SEO.",
            "49.00",
            "https://example.com/seo",
        ),
    ],
}

_CATEGORY_TRANSLATIONS_UK = {
    "Programming": "Програмування",
    "Design": "Дизайн",
    "DevOps": "DevOps",
    "Data Science": "Наука про дані",
    "Marketing": "Маркетинг",
}

_COURSE_TRANSLATIONS_UK: dict[str, tuple[str, str]] = {
    "Python Basics": ("Основи Python", "Вивчіть Python з нуля."),
    "Async FastAPI": ("Асинхронний FastAPI", "Створюйте асинхронні API з FastAPI."),
    "Clean Architecture in Python": (
        "Чиста архітектура в Python",
        "Шарова, SOLID і тестована архітектура.",
    ),
    "SQLAlchemy 2.0 Async": (
        "Асинхронний SQLAlchemy 2.0",
        "Асинхронна ORM, сесії та міграції.",
    ),
    "UI/UX Fundamentals": ("Основи UI/UX", "Принципи якісного дизайну."),
    "Figma for Beginners": (
        "Figma для початківців",
        "Проєктуйте інтерфейси та прототипи у Figma.",
    ),
    "Design Systems": (
        "Дизайн-системи",
        "Створюйте масштабовані й повторно використовувані компонентні системи.",
    ),
    "Docker Essentials": (
        "Основи Docker",
        "Контейнеризуйте та запускайте застосунки з Docker.",
    ),
    "CI/CD with GitHub Actions": (
        "CI/CD з GitHub Actions",
        "Автоматизуйте build, test і deploy pipelines.",
    ),
    "Kubernetes Basics": (
        "Основи Kubernetes",
        "Розгортайте та масштабуйте сервіси в Kubernetes.",
    ),
    "Pandas Crash Course": (
        "Швидкий курс Pandas",
        "Обробка й аналіз даних за допомогою Pandas.",
    ),
    "Machine Learning 101": (
        "Основи машинного навчання",
        "Ключові концепції ML і перші моделі.",
    ),
    "SQL for Analytics": (
        "SQL для аналітики",
        "Запитуйте й аналізуйте дані за допомогою SQL.",
    ),
    "Telegram Bots for Business": (
        "Telegram-боти для бізнесу",
        "Збільшуйте продажі через Telegram bot funnels.",
    ),
    "SEO Fundamentals": (
        "Основи SEO",
        "Покращуйте позиції за допомогою on-page і technical SEO.",
    ),
}


async def _add_category_translation(
    session: AsyncSession, category_id: int, language_code: str, name: str
) -> bool:
    stmt = select(CategoryTranslationModel).where(
        CategoryTranslationModel.category_id == category_id,
        CategoryTranslationModel.language_code == language_code,
    )
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        return False
    session.add(
        CategoryTranslationModel(
            category_id=category_id,
            language_code=language_code,
            name=name,
        )
    )
    return True


async def _add_course_translation(
    session: AsyncSession,
    course_id: int,
    language_code: str,
    name: str,
    description: str,
) -> bool:
    stmt = select(CourseTranslationModel).where(
        CourseTranslationModel.course_id == course_id,
        CourseTranslationModel.language_code == language_code,
    )
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        return False
    session.add(
        CourseTranslationModel(
            course_id=course_id,
            language_code=language_code,
            name=name,
            description=description,
        )
    )
    return True


async def seed() -> None:
    settings = get_settings()
    database = Database(settings)
    await create_schema(database, settings)
    await ensure_initial_data(database, settings)

    async with database.session_factory() as session:
        categories = SqlCategoryRepository(session)
        courses = SqlCourseRepository(session)
        existing = {category.name: category for category in await categories.list_all()}
        added_categories = 0
        added_courses = 0
        added_translations = 0
        for category_name, items in _DEMO.items():
            category = existing.get(category_name)
            if category is None:
                category = await categories.add(Category(id=None, name=category_name))
                added_categories += 1
            assert category.id is not None
            translated_category = _CATEGORY_TRANSLATIONS_UK.get(category_name)
            if translated_category is not None:
                added = await _add_category_translation(
                    session, category.id, "uk", translated_category
                )
                added_translations += 1 if added else 0
            present = {course.name for course in await courses.list_active_by_category(category.id)}
            for name, description, price, link in items:
                if name in present:
                    continue
                await courses.add(
                    Course(
                        id=None,
                        name=name,
                        description=description,
                        category_id=category.id,
                        price=Decimal(price),
                        link=link,
                    )
                )
                added_courses += 1
            for course in await courses.list_active_by_category(category.id):
                translated_course = _COURSE_TRANSLATIONS_UK.get(course.name)
                if translated_course is None or course.id is None:
                    continue
                translated_name, translated_description = translated_course
                added = await _add_course_translation(
                    session, course.id, "uk", translated_name, translated_description
                )
                added_translations += 1 if added else 0
        await session.commit()
        logger.info(
            "Seed complete: +{} categories, +{} courses, +{} translations.",
            added_categories,
            added_courses,
            added_translations,
        )
    await database.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
