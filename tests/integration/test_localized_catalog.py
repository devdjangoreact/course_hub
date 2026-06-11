import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.infrastructure.db.models.category_translation import CategoryTranslationModel
from app.infrastructure.db.models.course_translation import CourseTranslationModel


@pytest.mark.asyncio
async def test_categories_return_localized_names(
    app: FastAPI, client: AsyncClient, seeded: dict[str, int]
) -> None:
    async with app.state.db.session_factory() as session:
        session.add(
            CategoryTranslationModel(
                category_id=seeded["category_id"],
                language_code="uk",
                name="Програмування",
            )
        )
        await session.commit()

    response = await client.get("/api/categories?language=uk")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Програмування"
    assert response.json()[0]["fallback_used"] is False


@pytest.mark.asyncio
async def test_courses_fall_back_when_translation_missing(
    client: AsyncClient, seeded: dict[str, int]
) -> None:
    response = await client.get(f"/api/categories/{seeded['category_id']}/courses?language=uk")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Async FastAPI"
    assert response.json()[0]["fallback_used"] is True


@pytest.mark.asyncio
async def test_courses_return_localized_content(
    app: FastAPI, client: AsyncClient, seeded: dict[str, int]
) -> None:
    async with app.state.db.session_factory() as session:
        session.add(
            CourseTranslationModel(
                course_id=seeded["course_id"],
                language_code="uk",
                name="Асинхронний FastAPI",
                description="Створюйте асинхронні API з FastAPI.",
            )
        )
        await session.commit()

    response = await client.get(f"/api/categories/{seeded['category_id']}/courses?language=uk")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Асинхронний FastAPI"
    assert response.json()[0]["fallback_used"] is False
