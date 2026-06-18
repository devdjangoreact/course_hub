import re

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_payment_email(value: str) -> bool:
    return bool(_EMAIL_PATTERN.match(value.strip()))


def lava_offer_id(course_extra: dict[str, object]) -> str | None:
    raw = course_extra.get("lava_offer_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def payment_email(user_extra: dict[str, object]) -> str | None:
    raw = user_extra.get("payment_email")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
