import pytest

from app.application.services.parser_service import ParserService
from app.domain.entities.imported_catalog_item import ImportedCatalogItem
from app.domain.entities.parser_job import ParserJob
from app.domain.entities.parser_source import ParserSource
from app.domain.repositories.catalog_parser import CatalogParser, ParsedCatalogItem, ParserResult
from app.domain.repositories.imported_catalog_item_repository import ImportedCatalogItemRepository
from app.domain.repositories.parser_job_repository import ParserJobRepository
from app.domain.repositories.parser_source_repository import ParserSourceRepository


class FakeSources(ParserSourceRepository):
    source = ParserSource(id=1, name="Example", source_type="html", url="https://example.com")

    async def list_all(self) -> list[ParserSource]:
        return [self.source]

    async def get(self, source_id: int) -> ParserSource | None:
        return self.source if source_id == 1 else None

    async def add(self, source: ParserSource) -> ParserSource:
        return source

    async def update(self, source: ParserSource) -> ParserSource:
        self.source = source
        return source


class FakeJobs(ParserJobRepository):
    async def get(self, job_id: int) -> ParserJob | None:
        return None

    async def add(self, job: ParserJob) -> ParserJob:
        job.id = 1
        return job

    async def update(self, job: ParserJob) -> ParserJob:
        return job

    async def list_by_source(self, source_id: int) -> list[ParserJob]:
        return []


class FakeImportedItems(ImportedCatalogItemRepository):
    def __init__(self) -> None:
        self.items: list[ImportedCatalogItem] = []

    async def get(self, item_id: int) -> ImportedCatalogItem | None:
        return None

    async def add(self, item: ImportedCatalogItem) -> ImportedCatalogItem:
        self.items.append(item)
        return item

    async def update(self, item: ImportedCatalogItem) -> ImportedCatalogItem:
        return item

    async def list_by_job(self, parser_job_id: int) -> list[ImportedCatalogItem]:
        return self.items

    async def find_duplicate(
        self, source_id: int, external_id: str | None, fingerprint: str
    ) -> ImportedCatalogItem | None:
        return next((item for item in self.items if item.fingerprint == fingerprint), None)


class DuplicateParser(CatalogParser):
    async def parse(self, source: ParserSource) -> ParserResult:
        parsed = ParsedCatalogItem(
            item_type="category",
            external_id="cat-1",
            fingerprint="same",
            language_code="en",
            payload={"name": "Programming"},
        )
        return ParserResult(items=[parsed, parsed])


@pytest.mark.asyncio
async def test_parser_service_skips_duplicate_items() -> None:
    imported_items = FakeImportedItems()
    service = ParserService(FakeSources(), FakeJobs(), imported_items, DuplicateParser())

    job = await service.start_job(1)

    assert job.imported_count == 1
    assert job.skipped_count == 1
