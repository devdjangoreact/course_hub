from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Categories", callback_data="menu:categories")],
            [InlineKeyboardButton(text="Search", callback_data="menu:search")],
        ]
    )
