from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery, LinkPreviewOptions, User
from loguru import logger

from app.application.errors import NotFoundError, ValidationError
from app.application.services.catalog_service import CatalogService
from app.application.services.localization_service import LocalizationService
from app.application.services.order_service import OrderService
from app.application.services.runtime_settings import RuntimeSettings
from app.bot import delivery as course_delivery
from app.bot.keyboards.catalog import payment_url_keyboard
from app.bot.messages.catalog import message as bot_message
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.repositories.bot_user_repository import BotUserRepository

router = Router(name="order")

_NO_LINK_PREVIEW = LinkPreviewOptions(is_disabled=True)


async def _language_for(
    telegram_id: int,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> str:
    user = await bot_users.get_by_telegram_id(telegram_id)
    return await localization.resolve_language(user.preferred_language if user else None)


async def _category_name(
    catalog: CatalogService, category_id: int, language: str
) -> str:
    for category in await catalog.list_localized_categories(language):
        if category.id == category_id:
            return category.name
    return "—"


async def _payment_service_label(orders: OrderService, language: str) -> str:
    if await orders.uses_atlos_provider():
        return bot_message(language, "payment_provider_atlos")
    return bot_message(language, "payment_provider_simulated")


async def _create_order_for_user(
    orders: OrderService,
    from_user: User,
    course_id: int,
    bot_id: int | None = None,
    channel_id: int | None = None,
) -> tuple[int, PaymentIntent]:
    order, intent = await orders.create_order(
        telegram_id=from_user.id,
        course_id=course_id,
        username=from_user.username,
        full_name=from_user.full_name,
        bot_id=bot_id,
        channel_id=channel_id,
    )
    assert order.id is not None
    return order.id, intent


async def _pay_button_url(
    runtime: RuntimeSettings,
    orders: OrderService,
    order_id: int,
    intent: PaymentIntent,
) -> str | None:
    if not intent.pay_url:
        return None
    if await orders.payment_link_mode() == "checkout":
        return f"{runtime.backend_url.rstrip('/')}/api/orders/{order_id}/checkout"
    return intent.pay_url


async def _send_payment_summary(
    callback: CallbackQuery,
    *,
    language: str,
    runtime: RuntimeSettings,
    catalog: CatalogService,
    orders: OrderService,
    course_id: int,
    order_id: int,
    amount: Decimal,
    intent: PaymentIntent,
) -> None:
    course = await catalog.get_localized_course(course_id, language)
    category_name = await _category_name(catalog, course.category_id, language)
    currency = await orders.payment_currency()
    text = bot_message(language, "order_payment_summary").format(
        order_id=order_id,
        course_name=course.name,
        category_name=category_name,
        payment_service=await _payment_service_label(orders, language),
        amount=amount,
        currency=currency,
    )
    pay_url = await _pay_button_url(runtime, orders, order_id, intent)
    markup = payment_url_keyboard(pay_url, language) if pay_url else None
    await course_delivery.reply_callback(
        callback, text, markup, link_preview_options=_NO_LINK_PREVIEW
    )


@router.callback_query(F.data.regexp(r"^order:\d+$"))
async def create_order(
    callback: CallbackQuery,
    orders: OrderService,
    catalog: CatalogService,
    runtime: RuntimeSettings,
    bot_users: BotUserRepository,
    localization: LocalizationService,
    hub_bot_id: int | None = None,
) -> None:
    if callback.from_user is None:
        await callback.answer("Unable to identify user.")
        return
    await callback.answer()

    language = await _language_for(callback.from_user.id, bot_users, localization)
    course_id = int(str(callback.data).split(":", 1)[1])

    try:
        order_id, intent = await _create_order_for_user(
            orders, callback.from_user, course_id, bot_id=hub_bot_id
        )
    except NotFoundError:
        logger.error("order create: course not found course_id={}", course_id)
        await course_delivery.reply_callback(
            callback, bot_message(language, "course_not_found")
        )
        return
    except ValidationError as exc:
        logger.opt(exception=exc).error("order create failed course_id={}", course_id)
        await course_delivery.reply_callback(callback, str(exc))
        return

    course = await catalog.get_localized_course(course_id, language)
    await _send_payment_summary(
        callback,
        language=language,
        runtime=runtime,
        catalog=catalog,
        orders=orders,
        course_id=course_id,
        order_id=order_id,
        amount=course.price,
        intent=intent,
    )
