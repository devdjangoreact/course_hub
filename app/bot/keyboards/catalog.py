from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.entities.category import Category
from app.domain.entities.course import Course


def categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=category.name, callback_data=f"cat:{category.id}")]
        for category in categories
    ]
    rows.append([InlineKeyboardButton(text="Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def courses_keyboard(courses: list[Course]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=course.name, callback_data=f"course:{course.id}")]
        for course in courses
    ]
    rows.append([InlineKeyboardButton(text="Categories", callback_data="menu:categories")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_detail_keyboard(course_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Order", callback_data=f"order:{course_id}")],
            [InlineKeyboardButton(text="Menu", callback_data="menu:home")],
        ]
    )
