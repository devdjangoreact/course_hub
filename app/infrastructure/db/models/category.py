from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class CategoryModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)

    courses: Mapped[list["CourseModel"]] = relationship(  # noqa: F821
        back_populates="category", cascade="all, delete-orphan"
    )
