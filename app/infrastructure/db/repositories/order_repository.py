from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.order import Order
from app.domain.entities.order_status import OrderStatus
from app.domain.repositories.order_repository import OrderRepository
from app.infrastructure.db.models.order import OrderModel


def _to_entity(model: OrderModel) -> Order:
    return Order(
        id=model.id,
        bot_user_id=model.bot_user_id,
        course_id=model.course_id,
        amount=model.amount,
        status=OrderStatus(model.status),
        payment_reference=model.payment_reference,
        extra=dict(model.extra),
    )


class SqlOrderRepository(OrderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, order: Order) -> Order:
        model = OrderModel(
            bot_user_id=order.bot_user_id,
            course_id=order.course_id,
            amount=order.amount,
            status=order.status.value,
            payment_reference=order.payment_reference,
            extra=order.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get(self, order_id: int) -> Order | None:
        model = await self._session.get(OrderModel, order_id)
        return _to_entity(model) if model is not None else None

    async def get_by_payment_reference(self, payment_reference: str) -> Order | None:
        stmt = select(OrderModel).where(OrderModel.payment_reference == payment_reference)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def update(self, order: Order) -> Order:
        if order.id is None:
            raise ValueError("Cannot update an order without an id")
        model = await self._session.get(OrderModel, order.id)
        if model is None:
            raise ValueError("Order not found")
        model.status = order.status.value
        model.payment_reference = order.payment_reference
        model.extra = order.extra
        await self._session.flush()
        return _to_entity(model)
