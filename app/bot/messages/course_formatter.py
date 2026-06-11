from decimal import Decimal

from app.bot.messages.catalog import message as bot_message

_MAX_DESCRIPTION_CHARS = 900


def format_course(
    language_code: str,
    name: str,
    description: str,
    price: Decimal,
    link: str,
    category_name: str | None = None,
) -> str:
    display_description = _shorten(description)
    category_line = (
        f"{bot_message(language_code, 'course_category')}: {category_name}\n"
        if category_name
        else ""
    )
    return (
        f"<b>{name}</b>\n"
        f"{category_line}"
        f"{bot_message(language_code, 'course_price')}: {price}\n\n"
        f"{display_description}\n\n"
        f"{bot_message(language_code, 'course_link')}: {link}"
    )


def _shorten(value: str) -> str:
    if len(value) <= _MAX_DESCRIPTION_CHARS:
        return value
    return value[: _MAX_DESCRIPTION_CHARS - 3].rstrip() + "..."
