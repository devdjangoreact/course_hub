from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.application.errors import NotFoundError
from app.application.services.catalog_service import CatalogService
from app.application.services.localization_service import LocalizationService
from app.bot.keyboards.catalog import (
    categories_keyboard,
    course_detail_keyboard,
    courses_keyboard,
)
from app.bot.messages.catalog import message as bot_message
from app.bot.messages.course_formatter import format_course
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
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[arg-type]
    await callback.answer()


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
    await _edit(
        callback,
        format_course(language, course.name, course.description, course.price, course.link),
        course_detail_keyboard(course_id, language),
    )
