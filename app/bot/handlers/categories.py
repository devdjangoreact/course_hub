from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.application.errors import NotFoundError
from app.application.services.catalog_service import CatalogService, LocalizedCourse
from app.application.services.delivery_mailer import DeliveryMailer
from app.application.services.localization_service import LocalizationService
from app.application.services.order_service import OrderService
from app.bot import delivery as course_delivery
from app.bot.keyboards.catalog import (
    categories_keyboard,
    course_detail_keyboard,
    courses_keyboard,
)
from app.bot.messages.catalog import message as bot_message
from app.bot.messages.course_formatter import format_course
from app.core.config import get_settings
from app.domain.repositories.bot_user_repository import BotUserRepository
from app.infrastructure.email.smtp_mailer import SmtpMailer
from app.infrastructure.payments.lava_helpers import payment_email

router = Router(name="categories")


def _smtp_mailer() -> SmtpMailer:
    settings = get_settings()
    return SmtpMailer(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        from_addr=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
    )


async def _language_for(
    callback: CallbackQuery,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> str:
    user = await bot_users.get_by_telegram_id(callback.from_user.id)
    return await localization.resolve_language(user.preferred_language if user else None)


async def _edit(callback: CallbackQuery, text: str, markup: object | None = None) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[arg-type]
    await callback.answer()


async def send_course_access(
    target: Message,
    telegram_id: int,
    course: LocalizedCourse,
    language: str,
    orders: OrderService,
) -> None:
    settings = get_settings()
    paid = await orders.has_paid_course(telegram_id, course.id)
    channel = course_delivery.channel_id(course.extra, fallback=settings.catalog_channel_id)
    message_ids = []
    if course.extra.get("public_text_sanitized") is True:
        message_ids = [
            *course_delivery.promo_message_ids(course.extra),
            *course_delivery.full_message_ids(course.extra),
        ]
    copied = False
    if target.bot is not None and channel is not None:
        for message_id in message_ids:
            try:
                await target.bot.copy_message(
                    chat_id=telegram_id,
                    from_chat_id=channel,
                    message_id=message_id,
                )
                copied = True
            except Exception:
                logger.exception(
                    "copy_message failed channel={} message_id={}", channel, message_id
                )

    order_markup = None if paid else course_detail_keyboard(course.id, language)
    if not copied:
        await target.answer(
            format_course(language, course.name, course.description, course.price),
            reply_markup=order_markup,
        )

    invite = course_delivery.invite_link(course.extra, fallback=settings.catalog_invite_link)
    lines = []
    if invite:
        lines.append(f"{bot_message(language, 'invite_line')}: {invite}")
    if paid:
        download = course_delivery.download_link(course.link, course.extra)
        if download:
            lines.append(f"{bot_message(language, 'download_ready')}: {download}")
    if lines:
        await target.answer(
            "\n".join(lines),
            reply_markup=order_markup if copied and not paid else None,
        )
    elif copied and not paid:
        await target.answer(course.name, reply_markup=order_markup)


@router.callback_query(F.data == "menu:categories")
async def show_categories(
    callback: CallbackQuery,
    catalog: CatalogService,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    language = await _language_for(callback, bot_users, localization)
    categories = await catalog.list_localized_categories(language)
    if not categories:
        await _edit(callback, "No categories yet.")
        return
    await _edit(
        callback,
        bot_message(language, "categories"),
        categories_keyboard(categories, language),
    )


@router.callback_query(F.data.startswith("cat:"))
async def show_courses(
    callback: CallbackQuery,
    catalog: CatalogService,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    category_id = int(str(callback.data).split(":", 1)[1])
    language = await _language_for(callback, bot_users, localization)
    try:
        courses = await catalog.list_localized_courses(category_id, language)
    except NotFoundError:
        await _edit(callback, "Category not found.")
        return
    if not courses:
        await _edit(callback, "No courses yet in this category.")
        return
    await _edit(callback, bot_message(language, "categories"), courses_keyboard(courses, language))


@router.callback_query(F.data.startswith("course:promo_email:"))
async def send_promo_email(
    callback: CallbackQuery,
    catalog: CatalogService,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    course_id = int(str(callback.data).rsplit(":", 1)[1])
    language = await _language_for(callback, bot_users, localization)
    user = await bot_users.get_by_telegram_id(callback.from_user.id)
    email = payment_email(user.extra) if user is not None else None
    if email is None:
        await callback.answer(bot_message(language, "promo_email_missing"), show_alert=True)
        return
    try:
        course = await catalog.get_localized_course(course_id, language)
    except NotFoundError:
        await callback.answer(bot_message(language, "course_not_found"), show_alert=True)
        return
    try:
        DeliveryMailer(_smtp_mailer()).send_promo(email, course.name, course.description)
    except Exception:
        logger.exception("Failed to send promo email for course_id={}", course_id)
        await callback.answer(bot_message(language, "promo_unavailable"), show_alert=True)
        return
    await callback.answer(bot_message(language, "promo_email_sent"))


@router.callback_query(F.data.startswith("course:promo:"))
async def send_promo(
    callback: CallbackQuery,
    catalog: CatalogService,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    course_id = int(str(callback.data).rsplit(":", 1)[1])
    language = await _language_for(callback, bot_users, localization)
    try:
        course = await catalog.get_localized_course(course_id, language)
    except NotFoundError:
        await callback.answer(bot_message(language, "course_not_found"), show_alert=True)
        return
    channel = course_delivery.channel_id(course.extra, fallback=get_settings().catalog_channel_id)
    message_ids = (
        course_delivery.promo_message_ids(course.extra)
        if course.extra.get("public_text_sanitized") is True
        else []
    )
    if callback.bot is None or channel is None or not message_ids:
        await callback.answer(bot_message(language, "promo_unavailable"), show_alert=True)
        if isinstance(callback.message, Message):
            await callback.message.answer(course.description)
        return
    copied = False
    for mid in message_ids:
        try:
            await callback.bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=channel,
                message_id=mid,
            )
            copied = True
        except Exception:
            logger.exception("copy_message failed channel={} message_id={}", channel, mid)
    if not copied and isinstance(callback.message, Message):
        await callback.message.answer(course.description)
    await callback.answer()


@router.callback_query(F.data.startswith("course:"))
async def show_course(
    callback: CallbackQuery,
    catalog: CatalogService,
    orders: OrderService,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    course_id = int(str(callback.data).split(":", 1)[1])
    language = await _language_for(callback, bot_users, localization)
    try:
        course = await catalog.get_localized_course(course_id, language)
    except NotFoundError:
        await _edit(callback, "Course not found.")
        return
    if isinstance(callback.message, Message):
        await send_course_access(callback.message, callback.from_user.id, course, language, orders)
    await callback.answer()
