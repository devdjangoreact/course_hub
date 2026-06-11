from httpx import AsyncClient


async def test_list_categories(client: AsyncClient, seeded: dict[str, int]) -> None:
    response = await client.get("/api/categories")
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "Programming" in names


async def test_list_courses_in_category(client: AsyncClient, seeded: dict[str, int]) -> None:
    response = await client.get(f"/api/categories/{seeded['category_id']}/courses")
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 1
    assert courses[0]["id"] == seeded["course_id"]


async def test_list_courses_unknown_category(client: AsyncClient) -> None:
    response = await client.get("/api/categories/9999/courses")
    assert response.status_code == 404
