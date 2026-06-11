from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class ParserSourceModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "parser_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    source_type: Mapped[str] = mapped_column(index=True)
    url: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    last_status: Mapped[str | None] = mapped_column(default=None)
