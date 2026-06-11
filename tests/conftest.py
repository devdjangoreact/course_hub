import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(autouse=True)
def ensure_current_event_loop() -> None:
    policy = asyncio.DefaultEventLoopPolicy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop_policy(policy)
    asyncio.set_event_loop(loop)


@pytest_asyncio.fixture
async def app(tmp_path, monkeypatch) -> AsyncIterator[FastAPI]:
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("BOT_TOKEN", "")
    monkeypatch.setenv("PAYMENT_SECRET_KEY", "testsecret")
    monkeypatch.setenv("PAYMENT_PROVIDER", "simulated")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    get_settings.cache_clear()

    from app.bootstrap import ensure_initial_data
    from app.infrastructure.db.init_db import create_schema
    from app.main import create_app

    app = create_app()
    database = app.state.db
    settings: Settings = app.state.settings
    await create_schema(database, settings)
    await ensure_initial_data(database, settings)

    yield app

    await database.dispose()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def seeded(app: FastAPI) -> dict[str, int]:
    """Insert one category with one active course; return their ids."""
    from app.domain.entities.category import Category
    from app.domain.entities.course import Course
    from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
    from app.infrastructure.db.repositories.course_repository import SqlCourseRepository

    database = app.state.db
    async with database.session_factory() as session:
        category = await SqlCategoryRepository(session).add(Category(id=None, name="Programming"))
        assert category.id is not None
        course = await SqlCourseRepository(session).add(
            Course(
                id=None,
                name="Async FastAPI",
                description="Build async APIs with FastAPI and SQLAlchemy.",
                category_id=category.id,
                price=Decimal("79.00"),
                link="https://example.com/fastapi",
            )
        )
        await session.commit()
        assert course.id is not None
        return {"category_id": category.id, "course_id": course.id}
