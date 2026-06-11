from pydantic import BaseModel, Field, HttpUrl

from app.domain.entities.imported_catalog_item import ImportedCatalogItem
from app.domain.entities.parser_job import ParserJob
from app.domain.entities.parser_source import ParserSource


class ParserSourceCreate(BaseModel):
    name: str
    source_type: str
    url: HttpUrl
    is_active: bool = True
    extra: dict[str, object] = Field(default_factory=dict)

    def to_entity(self) -> ParserSource:
        return ParserSource(
            id=None,
            name=self.name,
            source_type=self.source_type,
            url=str(self.url),
            is_active=self.is_active,
            extra=self.extra,
        )


class ParserSourceOut(BaseModel):
    id: int
    name: str
    source_type: str
    url: str
    is_active: bool

    @classmethod
    def from_entity(cls, source: ParserSource) -> "ParserSourceOut":
        assert source.id is not None
        return cls(
            id=source.id,
            name=source.name,
            source_type=source.source_type,
            url=source.url,
            is_active=source.is_active,
        )


class ParserJobOut(BaseModel):
    id: int
    source_id: int
    status: str
    imported_count: int
    skipped_count: int
    error_summary: str | None

    @classmethod
    def from_entity(cls, job: ParserJob) -> "ParserJobOut":
        assert job.id is not None
        return cls(
            id=job.id,
            source_id=job.source_id,
            status=job.status.value,
            imported_count=job.imported_count,
            skipped_count=job.skipped_count,
            error_summary=job.error_summary,
        )


class ImportedCatalogItemOut(BaseModel):
    id: int
    parser_job_id: int
    item_type: str
    status: str

    @classmethod
    def from_entity(cls, item: ImportedCatalogItem) -> "ImportedCatalogItemOut":
        assert item.id is not None
        return cls(
            id=item.id,
            parser_job_id=item.parser_job_id,
            item_type=item.item_type,
            status=item.status.value,
        )
