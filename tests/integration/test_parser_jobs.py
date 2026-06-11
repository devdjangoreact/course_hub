import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_parser_source_and_start_job(client: AsyncClient) -> None:
    source_response = await client.post(
        "/api/admin/parser-sources",
        json={
            "name": "Example",
            "source_type": "html",
            "url": "https://example.com/courses",
            "is_active": True,
        },
    )
    assert source_response.status_code == 201

    source_id = source_response.json()["id"]
    job_response = await client.post(f"/api/admin/parser-sources/{source_id}/jobs")

    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_get_parser_job(client: AsyncClient) -> None:
    source_response = await client.post(
        "/api/admin/parser-sources",
        json={
            "name": "Example",
            "source_type": "html",
            "url": "https://example.com/courses",
            "is_active": True,
        },
    )
    source_id = source_response.json()["id"]
    job_id = (await client.post(f"/api/admin/parser-sources/{source_id}/jobs")).json()["id"]

    response = await client.get(f"/api/admin/parser-jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["id"] == job_id
