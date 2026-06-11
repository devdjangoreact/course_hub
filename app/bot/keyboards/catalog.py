from typing import Protocol

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.messages.catalog import DEFAULT_LANGUAGE, message
from app.domain.repositories.suggestion_search_repository import SearchSuggestion


class NamedItem(Protocol):
    id: int | None
    name: str


def categories_keyboard(
    categories: list[NamedItem], language_code: str = DEFAULT_LANGUAGE
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=category.name, callback_data=f"cat:{category.id}")]
        for category in categories
    ]
    rows.append(
        [InlineKeyboardButton(text=message(language_code, "menu"), callback_data="menu:home")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def courses_keyboard(
    courses: list[NamedItem], language_code: str = DEFAULT_LANGUAGE
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=course.name, callback_data=f"course:{course.id}")]
        for course in courses
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=message(language_code, "categories"), callback_data="menu:categories"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_detail_keyboard(
    course_id: int, language_code: str = DEFAULT_LANGUAGE
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=message(language_code, "order"), callback_data=f"order:{course_id}"
                )
            ],
            [InlineKeyboardButton(text=message(language_code, "menu"), callback_data="menu:home")],
        ]
    )


def suggestions_keyboard(
    suggestions: list[SearchSuggestion], language_code: str = DEFAULT_LANGUAGE
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{suggestion.title}",
                callback_data=_suggestion_callback(suggestion),
            )
        ]
        for suggestion in suggestions
    ]
    rows.append(
        [InlineKeyboardButton(text=message(language_code, "search"), callback_data="menu:search")]
    )
    rows.append(
        [InlineKeyboardButton(text=message(language_code, "menu"), callback_data="menu:home")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _suggestion_callback(suggestion: SearchSuggestion) -> str:
    if suggestion.type == "category":
        return f"cat:{suggestion.id}"
    return f"course:{suggestion.id}"
