from typing import Any

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class ImportedCatalogItemModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "imported_catalog_items"
    __table_args__ = (UniqueConstraint("parser_job_id", "fingerprint"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    parser_job_id: Mapped[int] = mapped_column(ForeignKey("parser_jobs.id"), index=True)
    item_type: Mapped[str] = mapped_column(index=True)
    external_id: Mapped[str | None] = mapped_column(default=None, index=True)
    source_url: Mapped[str | None] = mapped_column(default=None)
    fingerprint: Mapped[str] = mapped_column(index=True)
    language_code: Mapped[str] = mapped_column(index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(default="draft", index=True)
    matched_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), default=None
    )
    matched_course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), default=None)
