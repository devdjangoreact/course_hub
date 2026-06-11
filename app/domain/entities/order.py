from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.domain.entities.order_status import OrderStatus


@dataclass(slots=True)
class Order:
    id: int | None
    bot_user_id: int
    course_id: int
    amount: Decimal
    status: OrderStatus = OrderStatus.PENDING
    payment_reference: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
