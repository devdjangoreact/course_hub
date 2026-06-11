from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.application.errors import NotFoundError
from app.application.services.localization_service import LocalizationService
from app.application.services.order_service import OrderService
from app.bot.messages.catalog import message as bot_message
from app.domain.repositories.bot_user_repository import BotUserRepository

router = Router(name="order")


@router.callback_query(F.data.startswith("order:"))
async def create_order(
    callback: CallbackQuery,
    orders: OrderService,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    if callback.from_user is None:
        await callback.answer("Unable to identify user.")
        return
    user = await bot_users.get_by_telegram_id(callback.from_user.id)
    language = await localization.resolve_language(user.preferred_language if user else None)
    course_id = int(str(callback.data).split(":", 1)[1])
    try:
        order, intent = await orders.create_order(
            telegram_id=callback.from_user.id,
            course_id=course_id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
        )
    except NotFoundError:
        await callback.answer(bot_message(language, "course_not_found"))
        return
    text = intent.instructions
    if intent.pay_url is not None:
        text += f"\n\n{bot_message(language, 'pay_here')}: {intent.pay_url}"
    if isinstance(callback.message, Message):
        await callback.message.answer(text)
    await callback.answer(f"{bot_message(language, 'order_created')} #{order.id}.")
