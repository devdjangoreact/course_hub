from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger

from app.application.services.runtime_settings import load_runtime_settings
from app.bot.context import BotRuntime
from app.bot.registry import get_hub_bot_id
from app.container import (
    build_catalog_service,
    build_localization_service,
    build_order_service,
    build_search_service,
)
from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository


class ServicesMiddleware(BaseMiddleware):
    """Opens a DB session per update and injects ready-to-use services."""

    def __init__(self, runtime: BotRuntime) -> None:
        self._runtime = runtime

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        runtime = self._runtime
        label = _event_label(event)
        if isinstance(event, CallbackQuery):
            try:
                await event.answer()
            except TelegramBadRequest:
                pass
        async with runtime.database.session_factory() as session:
            runtime_settings = await load_runtime_settings(session, runtime.env_settings)
            data["catalog"] = build_catalog_service(session)
            data["localization"] = build_localization_service(session)
            data["search"] = build_search_service(session, runtime_settings, runtime.rate_limiter)
            data["orders"] = build_order_service(session, runtime.payment_gateway)
            data["bot_users"] = SqlBotUserRepository(session)
            data["runtime"] = runtime_settings
            data["hub_bot_id"] = get_hub_bot_id()
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                logger.exception("telegram handler failed {}", label)
                raise


def _event_label(event: TelegramObject) -> str:
    if isinstance(event, CallbackQuery):
        return f"CallbackQuery data={event.data!r}"
    if isinstance(event, Message):
        return f"Message text={(event.text or '')[:80]!r}"
    return type(event).__name__
