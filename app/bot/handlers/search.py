from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.errors import RateLimitedError, ValidationError
from app.application.services.search_service import SearchService
from app.bot.keyboards.catalog import courses_keyboard
from app.bot.states import SearchStates

router = Router(name="search")


@router.callback_query(F.data == "menu:search")
async def prompt_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.awaiting_query)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Send a search term:")
    await callback.answer()


@router.message(SearchStates.awaiting_query)
async def run_search(message: Message, state: FSMContext, search: SearchService) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        courses = await search.search(message.text or "", rate_key=f"tg:{user_id}")
    except ValidationError:
        await message.answer("Please send a valid search term.")
        return
    except RateLimitedError:
        await message.answer("Please slow down and try again in a moment.")
        return
    await state.clear()
    if not courses:
        await message.answer("No results, try another term.")
        return
    await message.answer("Results:", reply_markup=courses_keyboard(courses))
