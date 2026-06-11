from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin
from app.infrastructure.db.models.category import CategoryModel


class CourseModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str] = mapped_column()
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    link: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    category: Mapped[CategoryModel] = relationship(back_populates="courses")
