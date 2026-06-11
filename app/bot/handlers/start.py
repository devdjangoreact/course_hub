from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.domain.entities.bot_user import BotUser
from app.domain.repositories.bot_user_repository import BotUserRepository

router = Router(name="start")

_WELCOME = "Welcome to Course Hub! Browse courses by category or search."


@router.message(Command("start"))
async def handle_start(message: Message, bot_users: BotUserRepository) -> None:
    if message.from_user is not None:
        await bot_users.upsert(
            BotUser(
                id=None,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
        )
    await message.answer(_WELCOME, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(_WELCOME, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:home")
async def handle_home(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(_WELCOME, reply_markup=main_menu_keyboard())
    await callback.answer()
