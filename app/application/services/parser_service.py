from datetime import UTC, datetime

from app.application.errors import NotFoundError, ValidationError
from app.domain.entities.imported_catalog_item import ImportedCatalogItem
from app.domain.entities.imported_catalog_item_status import ImportedCatalogItemStatus
from app.domain.entities.parser_job import ParserJob
from app.domain.entities.parser_job_status import ParserJobStatus
from app.domain.entities.parser_source import ParserSource
from app.domain.repositories.catalog_parser import CatalogParser
from app.domain.repositories.imported_catalog_item_repository import ImportedCatalogItemRepository
from app.domain.repositories.parser_job_repository import ParserJobRepository
from app.domain.repositories.parser_source_repository import ParserSourceRepository


class ParserService:
    def __init__(
        self,
        sources: ParserSourceRepository,
        jobs: ParserJobRepository,
        imported_items: ImportedCatalogItemRepository,
        parser: CatalogParser,
    ) -> None:
        self._sources = sources
        self._jobs = jobs
        self._imported_items = imported_items
        self._parser = parser

    async def create_source(self, source: ParserSource) -> ParserSource:
        return await self._sources.add(source)

    async def get_job(self, job_id: int) -> ParserJob:
        job = await self._jobs.get(job_id)
        if job is None:
            raise NotFoundError("Parser job not found")
        return job

    async def start_job(self, source_id: int) -> ParserJob:
        source = await self._sources.get(source_id)
        if source is None:
            raise NotFoundError("Parser source not found")
        if not source.is_active:
            raise ValidationError("Parser source is inactive")
        job = await self._jobs.add(
            ParserJob(
                id=None,
                source_id=source_id,
                status=ParserJobStatus.RUNNING,
                started_at=_now(),
            )
        )
        result = await self._parser.parse(source)
        assert job.id is not None
        imported_count = 0
        skipped_count = 0
        for parsed in result.items:
            duplicate = await self._imported_items.find_duplicate(
                source_id, parsed.external_id, parsed.fingerprint
            )
            if duplicate is not None:
                skipped_count += 1
                continue
            await self._imported_items.add(
                ImportedCatalogItem(
                    id=None,
                    parser_job_id=job.id,
                    item_type=parsed.item_type,
                    external_id=parsed.external_id,
                    source_url=parsed.source_url,
                    fingerprint=parsed.fingerprint,
                    language_code=parsed.language_code,
                    payload=parsed.payload,
                )
            )
            imported_count += 1
        job.imported_count = imported_count
        job.skipped_count = skipped_count
        job.finished_at = _now()
        if result.errors:
            job.status = ParserJobStatus.FAILED
            job.error_summary = "; ".join(result.errors[:3])
        else:
            job.status = ParserJobStatus.COMPLETED
        source.last_status = job.status.value
        await self._sources.update(source)
        return await self._jobs.update(job)

    async def approve_imported_item(self, item_id: int) -> ImportedCatalogItem:
        item = await self._imported_items.get(item_id)
        if item is None:
            raise NotFoundError("Imported item not found")
        item.status = ImportedCatalogItemStatus.APPROVED
        return await self._imported_items.update(item)


def _now() -> datetime:
    return datetime.now(UTC)
