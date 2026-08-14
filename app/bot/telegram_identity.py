"""Resolve Telegram bot identity from Bot API (getMe)."""

from __future__ import annotations

from aiogram import Bot

from app.core.domain_host import normalize_bot_username


async def fetch_bot_username(token: str) -> str:
    """Return normalized bot username from Telegram. Raises ValueError if unavailable."""
    token = token.strip()
    if not token:
        raise ValueError("Bot token is empty")
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
    finally:
        await bot.session.close()
    username = getattr(me, "username", None)
    if not username or not str(username).strip():
        raise ValueError("Telegram getMe returned no username")
    return normalize_bot_username(str(username))
