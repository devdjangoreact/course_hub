import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from app.bot.context import BotRuntime
from app.bot.handlers import categories, order, search, start
from app.bot.messages.catalog import DEFAULT_LANGUAGE
from app.bot.messages.catalog import message as bot_message
from app.bot.middleware import ServicesMiddleware
from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository
from app.infrastructure.settings_store.bot_settings_repository import SqlBotSettingsRepository


def build_dispatcher(runtime: BotRuntime) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    middleware = ServicesMiddleware(runtime)
    dispatcher.message.middleware(middleware)
    dispatcher.callback_query.middleware(middleware)
    dispatcher.include_router(start.router)
    dispatcher.include_router(categories.router)
    dispatcher.include_router(search.router)
    dispatcher.include_router(order.router)
    return dispatcher


class BotApp:
    """Owns the aiogram bot lifecycle (long polling) inside the FastAPI app."""

    def __init__(self, runtime: BotRuntime) -> None:
        self._runtime = runtime
        self._bot: Bot | None = None
        self._dispatcher: Dispatcher | None = None
        self._task: asyncio.Task[None] | None = None

    async def _resolve_token(self) -> str:
        async with self._runtime.database.session_factory() as session:
            stored = await SqlBotSettingsRepository(session).get()
        if stored is not None and stored.bot_token:
            return stored.bot_token
        return self._runtime.env_settings.bot_token

    async def start(self) -> None:
        token = await self._resolve_token()
        if not token:
            logger.warning("Bot token is not configured; Telegram bot is disabled.")
            return
        self._bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self._dispatcher = build_dispatcher(self._runtime)
        self._task = asyncio.create_task(self._dispatcher.start_polling(self._bot))
        logger.info("Telegram bot started (long polling).")

    async def stop(self) -> None:
        if self._dispatcher is not None:
            await self._dispatcher.stop_polling()
        if self._task is not None:
            self._task.cancel()
        if self._bot is not None:
            await self._bot.session.close()
        logger.info("Telegram bot stopped.")

    async def notify_payment_status(self, telegram_id: int, order_id: int, status: str) -> None:
        if self._bot is None:
            return
        async with self._runtime.database.session_factory() as session:
            user = await SqlBotUserRepository(session).get_by_telegram_id(telegram_id)
        language = user.preferred_language if user is not None else DEFAULT_LANGUAGE
        await self._bot.send_message(
            telegram_id,
            f"{bot_message(language, 'payment_status')} #{order_id}: {status}.",
        )
