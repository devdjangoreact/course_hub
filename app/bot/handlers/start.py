from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.application.services.localization_service import LocalizationService
from app.bot.keyboards.language import language_keyboard
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.messages.catalog import DEFAULT_LANGUAGE
from app.bot.messages.catalog import message as bot_message
from app.domain.entities.bot_user import BotUser
from app.domain.repositories.bot_user_repository import BotUserRepository

router = Router(name="start")


async def _get_user_language(
    telegram_id: int | None,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> str:
    if telegram_id is None:
        return DEFAULT_LANGUAGE
    user = await bot_users.get_by_telegram_id(telegram_id)
    return await localization.resolve_language(user.preferred_language if user else None)


async def _upsert_from_message(message: Message, bot_users: BotUserRepository) -> bool:
    if message.from_user is None:
        return False
    existing = await bot_users.get_by_telegram_id(message.from_user.id)
    await bot_users.upsert(
        BotUser(
            id=existing.id if existing else None,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            preferred_language=existing.preferred_language if existing else DEFAULT_LANGUAGE,
        )
    )
    return existing is None


@router.message(Command("start"))
async def handle_start(
    message: Message,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    is_new = await _upsert_from_message(message, bot_users)
    if is_new:
        await message.answer(
            bot_message(DEFAULT_LANGUAGE, "choose_language"),
            reply_markup=language_keyboard(await localization.list_active_languages()),
        )
        return
    language = await _get_user_language(
        message.from_user.id if message.from_user else None, bot_users, localization
    )
    await message.answer(
        bot_message(language, "welcome"), reply_markup=main_menu_keyboard(language)
    )


@router.callback_query(F.data == "menu:language")
async def handle_language_menu(
    callback: CallbackQuery,
    localization: LocalizationService,
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            bot_message(DEFAULT_LANGUAGE, "choose_language"),
            reply_markup=language_keyboard(await localization.list_active_languages()),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("language:"))
async def handle_language_selected(
    callback: CallbackQuery,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    language = str(callback.data).split(":", 1)[1]
    if not await localization.is_supported(language):
        await callback.answer()
        return
    existing = await bot_users.get_by_telegram_id(callback.from_user.id)
    await bot_users.upsert(
        BotUser(
            id=existing.id if existing else None,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
            preferred_language=language,
        )
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            bot_message(language, "language_saved") + "\n\n" + bot_message(language, "welcome"),
            reply_markup=main_menu_keyboard(language),
        )
    await callback.answer()


@router.message(Command("help"))
async def handle_help(
    message: Message,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    language = await _get_user_language(
        message.from_user.id if message.from_user else None, bot_users, localization
    )
    await message.answer(
        bot_message(language, "welcome"), reply_markup=main_menu_keyboard(language)
    )


@router.callback_query(F.data == "menu:home")
async def handle_home(
    callback: CallbackQuery,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    language = await _get_user_language(callback.from_user.id, bot_users, localization)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            bot_message(language, "welcome"),
            reply_markup=main_menu_keyboard(language),
        )
    await callback.answer()
