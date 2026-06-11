from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class BotUserModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(default=None)
    full_name: Mapped[str | None] = mapped_column(default=None)
    preferred_language: Mapped[str] = mapped_column(default="uk", index=True)
