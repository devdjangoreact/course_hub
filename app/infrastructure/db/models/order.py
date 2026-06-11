from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.order_status import OrderStatus
from app.infrastructure.db.base import Base, ExtraMixin, TimestampMixin


class OrderModel(Base, ExtraMixin, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(
        String(16), default=OrderStatus.PENDING.value, index=True
    )
    payment_reference: Mapped[str | None] = mapped_column(unique=True, default=None)
