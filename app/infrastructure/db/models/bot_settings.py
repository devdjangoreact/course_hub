from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class BotSettingsModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_token: Mapped[str] = mapped_column(default="")
    backend_url: Mapped[str] = mapped_column(default="")
    app_env: Mapped[str] = mapped_column(default="development")
    admin_session_secret: Mapped[str] = mapped_column(default="")
    log_level: Mapped[str] = mapped_column(default="INFO")
    is_active: Mapped[bool] = mapped_column(default=True)
