from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class TelegramChannelModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id"), index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    discussion_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    is_public: Mapped[bool] = mapped_column(default=False)
    discussion_is_public: Mapped[bool] = mapped_column(default=False)
    invite_link: Mapped[str] = mapped_column(default="")
    discussion_invite_link: Mapped[str] = mapped_column(default="")
    title: Mapped[str] = mapped_column(default="")
    slug: Mapped[str] = mapped_column(default="")
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
