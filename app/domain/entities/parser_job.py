from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.entities.parser_job_status import ParserJobStatus


@dataclass(slots=True)
class ParserJob:
    id: int | None
    source_id: int
    status: ParserJobStatus = ParserJobStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    imported_count: int = 0
    skipped_count: int = 0
    error_summary: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
