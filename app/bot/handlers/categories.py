from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.application.errors import NotFoundError
from app.application.services.catalog_service import CatalogService
from app.bot.keyboards.catalog import (
    categories_keyboard,
    course_detail_keyboard,
    courses_keyboard,
)
from app.domain.entities.course import Course

router = Router(name="categories")


def _format_course(course: Course) -> str:
    return (
        f"<b>{course.name}</b>\n\n"
        f"{course.description}\n\n"
        f"Price: {course.price}\n"
        f"Link: {course.link}"
    )


async def _edit(callback: CallbackQuery, text: str, markup: object | None = None) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[arg-type]
    await callback.answer()


@router.callback_query(F.data == "menu:categories")
async def show_categories(callback: CallbackQuery, catalog: CatalogService) -> None:
    categories = await catalog.list_categories()
    if not categories:
        await _edit(callback, "No categories yet.")
        return
    await _edit(callback, "Choose a category:", categories_keyboard(categories))


@router.callback_query(F.data.startswith("cat:"))
async def show_courses(callback: CallbackQuery, catalog: CatalogService) -> None:
    category_id = int(str(callback.data).split(":", 1)[1])
    try:
        courses = await catalog.list_courses(category_id)
    except NotFoundError:
        await _edit(callback, "Category not found.")
        return
    if not courses:
        await _edit(callback, "No courses yet in this category.")
        return
    await _edit(callback, "Courses:", courses_keyboard(courses))


@router.callback_query(F.data.startswith("course:"))
async def show_course(callback: CallbackQuery, catalog: CatalogService) -> None:
    course_id = int(str(callback.data).split(":", 1)[1])
    try:
        course = await catalog.get_course(course_id)
    except NotFoundError:
        await _edit(callback, "Course not found.")
        return
    await _edit(callback, _format_course(course), course_detail_keyboard(course_id))
