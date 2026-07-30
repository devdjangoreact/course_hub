from decimal import Decimal

from app.bot.messages.course_formatter import format_course


def test_format_course_uses_localized_labels() -> None:
    text = format_course(
        "uk",
        "Асинхронний FastAPI",
        "Створюйте асинхронні API.",
        Decimal("79.00"),
    )

    assert "Ціна: 79.00" in text
    assert "https://example.com/fastapi" not in text
    assert "Посилання:" not in text


def test_format_course_shortens_long_descriptions() -> None:
    text = format_course("en", "Course", "x" * 1000, Decimal("1.00"))

    assert text.endswith("...")
    assert "..." in text
