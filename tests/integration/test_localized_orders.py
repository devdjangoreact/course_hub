from decimal import Decimal

import pytest
from fastapi import FastAPI

from app.domain.entities.bot_user import BotUser
from app.domain.entities.category import Category
from app.domain.entities.course import Course
from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository
from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository


@pytest.mark.asyncio
async def test_order_user_language_is_not_reset(app: FastAPI) -> None:
    database = app.state.db
    async with database.session_factory() as session:
        user = await SqlBotUserRepository(session).upsert(
            BotUser(id=None, telegram_id=123, username="student", preferred_language="en")
        )
        category = await SqlCategoryRepository(session).add(Category(id=None, name="Programming"))
        assert category.id is not None
        await SqlCourseRepository(session).add(
            Course(
                id=None,
                name="Async FastAPI",
                description="Build async APIs.",
                category_id=category.id,
                price=Decimal("79.00"),
                link="https://example.com/fastapi",
            )
        )
        await session.commit()

    async with database.session_factory() as session:
        stored = await SqlBotUserRepository(session).get_by_telegram_id(user.telegram_id)

    assert stored is not None
    assert stored.preferred_language == "en"
