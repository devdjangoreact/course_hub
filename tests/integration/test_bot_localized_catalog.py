from decimal import Decimal

from app.application.services.catalog_service import LocalizedCategory, LocalizedCourse
from app.bot.keyboards.catalog import categories_keyboard, courses_keyboard


def test_category_keyboard_uses_localized_names() -> None:
    markup = categories_keyboard(
        [
            LocalizedCategory(
                id=1,
                name="Програмування",
                language="uk",
                fallback_used=False,
            )
        ]
    )

    assert markup.inline_keyboard[0][0].text == "Програмування"


def test_course_keyboard_uses_localized_names() -> None:
    markup = courses_keyboard(
        [
            LocalizedCourse(
                id=1,
                name="Асинхронний FastAPI",
                description="Створюйте асинхронні API.",
                category_id=1,
                price=Decimal("79.00"),
                link="https://example.com/fastapi",
                language="uk",
                fallback_used=False,
            )
        ]
    )

    assert markup.inline_keyboard[0][0].text == "Асинхронний FastAPI"
