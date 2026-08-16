"""Resolve Telegram bot identity from Bot API (getMe)."""

from __future__ import annotations

import asyncio

from app.bot.webhook_setup import fetch_username


async def fetch_bot_username(token: str) -> str:
    """Return normalized bot username from Telegram. Raises ValueError if unavailable."""
    token = token.strip()
    if not token:
        raise ValueError("Bot token is empty")
    username = await asyncio.to_thread(fetch_username, token)
    if not username:
        raise ValueError("Telegram getMe returned no username")
    return username
