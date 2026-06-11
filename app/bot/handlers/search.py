from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.errors import RateLimitedError, ValidationError
from app.application.services.localization_service import LocalizationService
from app.application.services.search_service import SearchService
from app.bot.keyboards.catalog import suggestions_keyboard
from app.bot.messages.catalog import DEFAULT_LANGUAGE
from app.bot.messages.catalog import message as bot_message
from app.bot.states import SearchStates
from app.domain.repositories.bot_user_repository import BotUserRepository

router = Router(name="search")


@router.callback_query(F.data == "menu:search")
async def prompt_search(
    callback: CallbackQuery,
    state: FSMContext,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    language = await _language_for(callback.from_user.id, bot_users, localization)
    await state.set_state(SearchStates.awaiting_query)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(bot_message(language, "search_prompt"))
    await callback.answer()


@router.message(SearchStates.awaiting_query)
async def run_search(
    message: Message,
    state: FSMContext,
    search: SearchService,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    language = await _language_for(user_id, bot_users, localization)
    try:
        suggestions = await search.suggest(message.text or "", language, rate_key=f"tg:{user_id}")
    except ValidationError:
        await message.answer(bot_message(language, "search_too_short"))
        return
    except RateLimitedError:
        await message.answer(bot_message(language, "search_rate_limited"))
        return
    if not suggestions:
        await state.clear()
        await message.answer(bot_message(language, "search_no_results"))
        return
    await state.set_state(SearchStates.viewing_suggestions)
    await message.answer(
        bot_message(language, "search_results"),
        reply_markup=suggestions_keyboard(suggestions, language),
    )


async def _language_for(
    telegram_id: int,
    bot_users: BotUserRepository,
    localization: LocalizationService,
) -> str:
    user = await bot_users.get_by_telegram_id(telegram_id)
    if user is None:
        return DEFAULT_LANGUAGE
    return await localization.resolve_language(user.preferred_language)
