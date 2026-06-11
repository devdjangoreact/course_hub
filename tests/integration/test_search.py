from httpx import AsyncClient


async def test_search_matches(client: AsyncClient, seeded: dict[str, int]) -> None:
    response = await client.get("/api/courses/search", params={"q": "fastapi"})
    assert response.status_code == 200
    results = response.json()
    assert any(item["id"] == seeded["course_id"] for item in results)


async def test_search_no_match(client: AsyncClient, seeded: dict[str, int]) -> None:
    response = await client.get("/api/courses/search", params={"q": "zzzznotfound"})
    assert response.status_code == 200
    assert response.json() == []


async def test_search_empty_query_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/courses/search", params={"q": ""})
    assert response.status_code == 422
