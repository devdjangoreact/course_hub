import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_suggestions_reject_short_query(client: AsyncClient) -> None:
    response = await client.get("/api/search/suggestions?q=fa&language=en")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_suggestions_return_partial_course_match(
    client: AsyncClient, seeded: dict[str, int]
) -> None:
    response = await client.get("/api/search/suggestions?q=Fast&language=en")

    assert response.status_code == 200
    assert response.json()[0]["type"] == "course"
    assert response.json()[0]["title"] == "Async FastAPI"
