from dataclasses import dataclass, field
from typing import Any

from app.domain.entities.imported_catalog_item_status import ImportedCatalogItemStatus


@dataclass(slots=True)
class ImportedCatalogItem:
    id: int | None
    parser_job_id: int
    item_type: str
    fingerprint: str
    language_code: str
    payload: dict[str, Any]
    status: ImportedCatalogItemStatus = ImportedCatalogItemStatus.DRAFT
    external_id: str | None = None
    source_url: str | None = None
    matched_category_id: int | None = None
    matched_course_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)
