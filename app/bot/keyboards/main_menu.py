from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.messages.catalog import DEFAULT_LANGUAGE, message


def main_menu_keyboard(language_code: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=message(language_code, "categories"),
                    callback_data="menu:categories",
                )
            ],
            [
                InlineKeyboardButton(
                    text=message(language_code, "search"),
                    callback_data="menu:search",
                )
            ],
            [
                InlineKeyboardButton(
                    text=message(language_code, "language"),
                    callback_data="menu:language",
                )
            ],
        ]
    )
