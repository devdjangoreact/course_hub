from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery


async def edit_text(message: object, text: str, markup: object | None = None) -> None:
    try:
        await message.edit_text(text, reply_markup=markup)  # type: ignore[union-attr]
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def edit_callback(callback: CallbackQuery, text: str, markup: object | None = None) -> None:
    message = callback.message
    try:
        if message is not None and hasattr(message, "edit_text"):
            try:
                await edit_text(message, text, markup)
            except TelegramBadRequest:
                try:
                    await _send_callback_text(callback, text, markup)
                except TelegramBadRequest:
                    await _send_callback_text(callback, text, None)
        else:
            try:
                await _send_callback_text(callback, text, markup)
            except TelegramBadRequest:
                await _send_callback_text(callback, text, None)
    finally:
        try:
            await callback.answer()
        except TelegramBadRequest:
            pass


async def _send_callback_text(
    callback: CallbackQuery, text: str, markup: object | None = None, **kwargs: object
) -> None:
    message = callback.message
    if callback.bot is not None and callback.from_user is not None:
        await callback.bot.send_message(
            callback.from_user.id, text, reply_markup=markup, **kwargs
        )
        return
    if message is not None and hasattr(message, "answer"):
        await message.answer(text, reply_markup=markup, **kwargs)  # type: ignore[union-attr]


async def reply_callback(
    callback: CallbackQuery,
    text: str,
    markup: object | None = None,
    **kwargs: object,
) -> None:
    if can_use_message(callback.message):
        await callback.message.answer(text, reply_markup=markup, **kwargs)  # type: ignore[union-attr]
        return
    await _send_callback_text(callback, text, markup, **kwargs)


def can_use_message(message: object | None) -> bool:
    return message is not None and hasattr(message, "answer")


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
