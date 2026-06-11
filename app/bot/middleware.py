from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.bot.context import BotRuntime
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
        async with runtime.database.session_factory() as session:
            data["catalog"] = build_catalog_service(session)
            data["localization"] = build_localization_service(session)
            data["search"] = build_search_service(session, runtime.settings, runtime.rate_limiter)
            data["orders"] = build_order_service(session, runtime.payment_gateway)
            data["bot_users"] = SqlBotUserRepository(session)
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
