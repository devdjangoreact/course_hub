from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin


class CourseTranslationModel(Base, ExtraMixin):
    __tablename__ = "course_translations"
    __table_args__ = (UniqueConstraint("course_id", "language_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    language_code: Mapped[str] = mapped_column(ForeignKey("supported_languages.code"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str] = mapped_column()
