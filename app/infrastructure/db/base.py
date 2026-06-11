from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON}


class ExtraMixin:
    """Adds the extensible per-item JSON field shared by every entity (FR-015)."""

    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
