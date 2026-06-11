import asyncio
from decimal import Decimal

from loguru import logger

from app.bootstrap import ensure_initial_data
from app.core.config import get_settings
from app.core.database import Database
from app.domain.entities.category import Category
from app.domain.entities.course import Course
from app.infrastructure.db.init_db import create_schema
from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository

_DEMO: dict[str, list[tuple[str, str, str, str]]] = {
    "Programming": [
        ("Python Basics", "Learn Python from scratch.", "49.00", "https://example.com/python"),
        ("Async FastAPI", "Build async APIs with FastAPI.", "79.00", "https://example.com/fastapi"),
        ("Clean Architecture in Python", "Layered, SOLID, testable design.", "99.00", "https://example.com/clean-arch"),
        ("SQLAlchemy 2.0 Async", "Async ORM, sessions and migrations.", "69.00", "https://example.com/sqlalchemy"),
    ],
    "Design": [
        ("UI/UX Fundamentals", "Principles of good design.", "59.00", "https://example.com/uiux"),
        ("Figma for Beginners", "Design interfaces and prototypes in Figma.", "39.00", "https://example.com/figma"),
        ("Design Systems", "Build scalable, reusable component systems.", "89.00", "https://example.com/design-systems"),
    ],
    "DevOps": [
        ("Docker Essentials", "Containerize and run apps with Docker.", "55.00", "https://example.com/docker"),
        ("CI/CD with GitHub Actions", "Automate build, test and deploy pipelines.", "75.00", "https://example.com/cicd"),
        ("Kubernetes Basics", "Deploy and scale services on Kubernetes.", "120.00", "https://example.com/k8s"),
    ],
    "Data Science": [
        ("Pandas Crash Course", "Data wrangling and analysis with Pandas.", "65.00", "https://example.com/pandas"),
        ("Machine Learning 101", "Core ML concepts and first models.", "129.00", "https://example.com/ml"),
        ("SQL for Analytics", "Query and analyze data with SQL.", "45.00", "https://example.com/sql"),
    ],
    "Marketing": [
        ("Telegram Bots for Business", "Grow sales with Telegram bot funnels.", "59.00", "https://example.com/tg-bots"),
        ("SEO Fundamentals", "Rank higher with on-page and technical SEO.", "49.00", "https://example.com/seo"),
    ],
}


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
        for category_name, items in _DEMO.items():
            category = existing.get(category_name)
            if category is None:
                category = await categories.add(Category(id=None, name=category_name))
                added_categories += 1
            assert category.id is not None
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
        await session.commit()
        logger.info(
            "Seed complete: +{} categories, +{} courses.", added_categories, added_courses
        )
    await database.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
