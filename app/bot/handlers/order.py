from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message, User

from app.application.errors import NotFoundError, ValidationError
from app.application.services.catalog_service import CatalogService
from app.application.services.localization_service import LocalizationService
from app.application.services.order_service import OrderService
from app.bot.keyboards.catalog import payment_email_confirm_keyboard, payment_url_keyboard
from app.bot.messages.catalog import message as bot_message
from app.bot.states import OrderStates
from app.application.services.runtime_settings import RuntimeSettings
from app.domain.entities.bot_user import BotUser
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.repositories.bot_user_repository import BotUserRepository
from app.infrastructure.payments.lava_helpers import is_valid_payment_email, payment_email

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
    if await orders.uses_lava_provider():
        return bot_message(language, "payment_provider_lava")
    return bot_message(language, "payment_provider_simulated")


async def _create_order_for_user(
    orders: OrderService,
    from_user: User,
    course_id: int,
) -> tuple[int, PaymentIntent]:
    order, intent = await orders.create_order(
        telegram_id=from_user.id,
        course_id=course_id,
        username=from_user.username,
        full_name=from_user.full_name,
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
    target: Message,
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
    await target.answer(text, reply_markup=markup, link_preview_options=_NO_LINK_PREVIEW)


async def _prompt_payment_email(
    target: Message,
    state: FSMContext,
    language: str,
    course_id: int,
) -> None:
    await state.set_state(OrderStates.awaiting_payment_email)
    await state.update_data(course_id=course_id)
    await target.answer(bot_message(language, "payment_email_prompt"))


async def _prompt_saved_email_confirm(
    target: Message,
    language: str,
    course_id: int,
    email: str,
) -> None:
    await target.answer(
        bot_message(language, "payment_email_confirm").format(email=email),
        reply_markup=payment_email_confirm_keyboard(course_id, language),
    )


async def _finalize_order(
    target: Message,
    *,
    language: str,
    runtime: RuntimeSettings,
    catalog: CatalogService,
    orders: OrderService,
    from_user: User,
    course_id: int,
) -> None:
    try:
        order_id, intent = await _create_order_for_user(orders, from_user, course_id)
    except NotFoundError:
        await target.answer(bot_message(language, "course_not_found"))
        return
    except ValidationError as exc:
        await target.answer(str(exc))
        return

    course = await catalog.get_localized_course(course_id, language)
    await _send_payment_summary(
        target,
        language=language,
        runtime=runtime,
        catalog=catalog,
        orders=orders,
        course_id=course_id,
        order_id=order_id,
        amount=course.price,
        intent=intent,
    )


@router.callback_query(F.data.regexp(r"^order:\d+$"))
async def create_order(
    callback: CallbackQuery,
    state: FSMContext,
    orders: OrderService,
    catalog: CatalogService,
    runtime: RuntimeSettings,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    if callback.from_user is None:
        await callback.answer("Unable to identify user.")
        return
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    language = await _language_for(callback.from_user.id, bot_users, localization)
    course_id = int(str(callback.data).split(":", 1)[1])

    if await orders.uses_lava_provider():
        user = await bot_users.get_by_telegram_id(callback.from_user.id)
        saved_email = payment_email(user.extra) if user else None
        if saved_email is None:
            await _prompt_payment_email(callback.message, state, language, course_id)
            await callback.answer()
            return
        await _prompt_saved_email_confirm(callback.message, language, course_id, saved_email)
        await callback.answer()
        return

    try:
        order_id, intent = await _create_order_for_user(orders, callback.from_user, course_id)
    except NotFoundError:
        await callback.answer(bot_message(language, "course_not_found"))
        return
    except ValidationError as exc:
        await callback.answer(str(exc))
        return

    course = await catalog.get_localized_course(course_id, language)
    await _send_payment_summary(
        callback.message,
        language=language,
        runtime=runtime,
        catalog=catalog,
        orders=orders,
        course_id=course_id,
        order_id=order_id,
        amount=course.price,
        intent=intent,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order:email:use:"))
async def use_saved_payment_email(
    callback: CallbackQuery,
    catalog: CatalogService,
    orders: OrderService,
    runtime: RuntimeSettings,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        await callback.answer()
        return
    language = await _language_for(callback.from_user.id, bot_users, localization)
    course_id = int(str(callback.data).rsplit(":", 1)[1])
    await _finalize_order(
        callback.message,
        language=language,
        runtime=runtime,
        catalog=catalog,
        orders=orders,
        from_user=callback.from_user,
        course_id=course_id,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order:email:change:"))
async def change_payment_email(
    callback: CallbackQuery,
    state: FSMContext,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        await callback.answer()
        return
    language = await _language_for(callback.from_user.id, bot_users, localization)
    course_id = int(str(callback.data).rsplit(":", 1)[1])
    await _prompt_payment_email(callback.message, state, language, course_id)
    await callback.answer()


@router.message(OrderStates.awaiting_payment_email)
async def receive_payment_email(
    message: Message,
    state: FSMContext,
    orders: OrderService,
    catalog: CatalogService,
    runtime: RuntimeSettings,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    if message.from_user is None:
        return
    language = await _language_for(message.from_user.id, bot_users, localization)
    email = (message.text or "").strip()
    if not is_valid_payment_email(email):
        await message.answer(bot_message(language, "payment_email_invalid"))
        return

    data = await state.get_data()
    course_id = int(data["course_id"])
    existing = await bot_users.get_by_telegram_id(message.from_user.id)
    extra = dict(existing.extra) if existing else {}
    extra["payment_email"] = email
    await bot_users.upsert(
        BotUser(
            id=existing.id if existing else None,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            preferred_language=existing.preferred_language if existing else language,
            extra=extra,
        )
    )
    await state.clear()
    await _finalize_order(
        message,
        language=language,
        runtime=runtime,
        catalog=catalog,
        orders=orders,
        from_user=message.from_user,
        course_id=course_id,
    )
