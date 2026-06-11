from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class AdminUserModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
