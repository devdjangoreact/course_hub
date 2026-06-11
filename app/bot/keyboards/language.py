from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.entities.supported_language import SupportedLanguage


def language_keyboard(languages: list[SupportedLanguage]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=language.native_name,
                    callback_data=f"language:{language.code}",
                )
            ]
            for language in languages
        ]
    )
