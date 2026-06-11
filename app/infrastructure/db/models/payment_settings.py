from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class PaymentSettingsModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "payment_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(default="simulated")
    api_key: Mapped[str | None] = mapped_column(default=None)
    secret_key: Mapped[str | None] = mapped_column(default=None)
    currency: Mapped[str] = mapped_column(default="USD")
    is_active: Mapped[bool] = mapped_column(default=True)
