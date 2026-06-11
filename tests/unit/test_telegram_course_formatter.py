from decimal import Decimal

from app.bot.messages.course_formatter import format_course


def test_format_course_uses_localized_labels() -> None:
    text = format_course(
        "uk",
        "Асинхронний FastAPI",
        "Створюйте асинхронні API.",
        Decimal("79.00"),
        "https://example.com/fastapi",
    )

    assert "Ціна: 79.00" in text
    assert "Посилання: https://example.com/fastapi" in text


def test_format_course_shortens_long_descriptions() -> None:
    text = format_course("en", "Course", "x" * 1000, Decimal("1.00"), "https://example.com")

    assert text.endswith("Link: https://example.com")
    assert "..." in text
