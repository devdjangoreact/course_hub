from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class TelegramBotModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    token: Mapped[str] = mapped_column(default="")
    webhook_secret: Mapped[str] = mapped_column(default="")
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    title: Mapped[str] = mapped_column(default="")
    notes: Mapped[str] = mapped_column(default="")
