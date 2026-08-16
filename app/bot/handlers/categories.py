from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.application.errors import NotFoundError
from app.application.services.catalog_service import CatalogService, LocalizedCourse
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

router = Router(name="categories")


async def _language_for(
    callback: CallbackQuery,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> str:
    user = await bot_users.get_by_telegram_id(callback.from_user.id)
    return await localization.resolve_language(user.preferred_language if user else None)


async def _edit(callback: CallbackQuery, text: str, markup: object | None = None) -> None:
    await course_delivery.edit_callback(callback, text, markup)


def _course_access_text(
    course: LocalizedCourse,
    language: str,
    *,
    paid: bool,
) -> str:
    settings = get_settings()
    text = format_course(language, course.name, course.description, course.price)
    invite = course_delivery.invite_link(course.extra, fallback=settings.catalog_invite_link)
    if invite:
        text += f"\n\n{bot_message(language, 'invite_line')}: {invite}"
    if paid:
        download = course_delivery.download_link(course.link, course.extra)
        if download:
            text += f"\n{bot_message(language, 'download_ready')}: {download}"
    return text


async def send_course_access(
    target: object,
    telegram_id: int,
    course: LocalizedCourse,
    language: str,
    orders: OrderService,
    *,
    replace: bool = False,
) -> None:
    paid = await orders.has_paid_course(telegram_id, course.id)
    text = _course_access_text(course, language, paid=paid)
    markup = None if paid else course_detail_keyboard(course.id, language)
    if replace and hasattr(target, "edit_text"):
        await course_delivery.edit_text(target, text, markup)
        return
    await target.answer(text, reply_markup=markup)


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
    if course_delivery.can_use_message(callback.message):
        await send_course_access(
            callback.message,
            callback.from_user.id,
            course,
            language,
            orders,
            replace=True,
        )
