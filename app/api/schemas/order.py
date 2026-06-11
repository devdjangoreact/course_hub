from decimal import Decimal

from pydantic import BaseModel

from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent


class OrderCreate(BaseModel):
    telegram_id: int
    course_id: int
    username: str | None = None
    full_name: str | None = None


class PaymentOut(BaseModel):
    payment_reference: str
    instructions: str
    pay_url: str | None = None

    @classmethod
    def from_entity(cls, intent: PaymentIntent) -> "PaymentOut":
        return cls(
            payment_reference=intent.payment_reference,
            instructions=intent.instructions,
            pay_url=intent.pay_url,
        )


class OrderOut(BaseModel):
    order_id: int
    status: str
    amount: Decimal

    @classmethod
    def from_entity(cls, order: Order) -> "OrderOut":
        assert order.id is not None
        return cls(order_id=order.id, status=order.status.value, amount=order.amount)


class OrderCreatedOut(OrderOut):
    payment: PaymentOut
