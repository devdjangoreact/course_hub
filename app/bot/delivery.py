from typing import Any


def promo_message_ids(extra: dict[str, Any]) -> list[int]:
    raw = extra.get("promo_message_ids") or []
    return [int(x) for x in raw]


def full_message_ids(extra: dict[str, Any]) -> list[int]:
    raw = extra.get("full_message_ids") or []
    return [int(x) for x in raw]


def channel_id(extra: dict[str, Any], fallback: int | None = None) -> int | None:
    value = extra.get("channel_id")
    if value is not None:
        return int(value)
    return fallback


def download_link(course_link: str, extra: dict[str, Any]) -> str:
    value = extra.get("download_link")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return course_link


def invite_link(extra: dict[str, Any], fallback: str | None = None) -> str | None:
    value = extra.get("invite_link")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None
