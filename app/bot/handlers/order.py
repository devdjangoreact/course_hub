from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.application.errors import NotFoundError
from app.application.services.order_service import OrderService

router = Router(name="order")


@router.callback_query(F.data.startswith("order:"))
async def create_order(callback: CallbackQuery, orders: OrderService) -> None:
    if callback.from_user is None:
        await callback.answer("Unable to identify user.")
        return
    course_id = int(str(callback.data).split(":", 1)[1])
    try:
        order, intent = await orders.create_order(
            telegram_id=callback.from_user.id,
            course_id=course_id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
        )
    except NotFoundError:
        await callback.answer("Course not found.")
        return
    text = intent.instructions
    if intent.pay_url is not None:
        text += f"\n\nPay here: {intent.pay_url}"
    if isinstance(callback.message, Message):
        await callback.message.answer(text)
    await callback.answer(f"Order #{order.id} created.")
