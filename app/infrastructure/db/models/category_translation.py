from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin


class CategoryTranslationModel(Base, ExtraMixin):
    __tablename__ = "category_translations"
    __table_args__ = (UniqueConstraint("category_id", "language_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    language_code: Mapped[str] = mapped_column(ForeignKey("supported_languages.code"), index=True)
    name: Mapped[str] = mapped_column(index=True)
