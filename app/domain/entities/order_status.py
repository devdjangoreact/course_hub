from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (OrderStatus.PAID, OrderStatus.FAILED, OrderStatus.CANCELLED)
