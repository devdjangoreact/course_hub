import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.infrastructure.db.models.imported_catalog_item import ImportedCatalogItemModel
from app.infrastructure.db.models.parser_job import ParserJobModel
from app.infrastructure.db.models.parser_source import ParserSourceModel


@pytest.mark.asyncio
async def test_approve_imported_item_marks_reviewed_without_publishing(
    app: FastAPI, client: AsyncClient
) -> None:
    async with app.state.db.session_factory() as session:
        source = ParserSourceModel(name="Example", source_type="html", url="https://example.com")
        session.add(source)
        await session.flush()
        job = ParserJobModel(source_id=source.id, status="completed")
        session.add(job)
        await session.flush()
        item = ImportedCatalogItemModel(
            parser_job_id=job.id,
            item_type="course",
            fingerprint="course-1",
            language_code="en",
            payload={"name": "Imported Course"},
        )
        session.add(item)
        await session.commit()
        item_id = item.id

    response = await client.post(f"/api/admin/imported-items/{item_id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
