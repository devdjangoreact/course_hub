import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from loguru import logger

from app.application.services.delivery_mailer import DeliveryMailer
from app.application.services.runtime_settings import load_runtime_settings
from app.bot import delivery as course_delivery
from app.bot.context import BotRuntime
from app.bot.handlers import categories, order, search, start
from app.bot.messages.catalog import DEFAULT_LANGUAGE
from app.bot.messages.catalog import message as bot_message
from app.bot.middleware import ServicesMiddleware
from app.bot.registry import (
    BotRegistry,
    RegisteredBot,
    reset_hub_bot_id,
    set_hub_bot_id,
)
from app.core.config import TelegramMode
from app.core.domain_host import webhook_url_for_bot
from app.domain.entities.order_status import OrderStatus
from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository
from app.infrastructure.db.repositories.order_repository import SqlOrderRepository
from app.infrastructure.db.repositories.telegram_bot_repository import SqlTelegramBotRepository
from app.infrastructure.db.repositories.telegram_channel_repository import (
    SqlTelegramChannelRepository,
)
from app.infrastructure.email.smtp_mailer import SmtpMailer
from app.infrastructure.payments.lava_helpers import payment_email


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
    """Owns multi-bot aiogram lifecycle (webhook or long polling) inside the FastAPI app."""

    def __init__(self, runtime: BotRuntime) -> None:
        self._runtime = runtime
        self.registry = BotRegistry()
        self._dispatcher: Dispatcher | None = None
        self._task: asyncio.Task[None] | None = None

    async def set_webhook_for(
        self, registered: RegisteredBot, base_domain: str, path: str
    ) -> None:
        if not path.startswith("/"):
            path = "/" + path
        url = webhook_url_for_bot(
            username=registered.username,
            base_domain=base_domain,
            webhook_path=path,
        )
        secret = registered.webhook_secret or None
        try:
            await registered.aiogram_bot.set_webhook(url=url, secret_token=secret)
            logger.info("Telegram webhook set for @{} to {}", registered.username, url)
        except TelegramRetryAfter as exc:
            logger.warning(
                "Telegram setWebhook rate-limited (retry after {}s); continuing. bot=@{} url={}",
                exc.retry_after,
                registered.username,
                url,
            )
        except TelegramAPIError:
            logger.exception(
                "Telegram setWebhook failed for @{}; continuing without blocking startup.",
                registered.username,
            )

    async def start(self) -> None:
        self._dispatcher = build_dispatcher(self._runtime)
        async with self._runtime.database.session_factory() as session:
            bots = await SqlTelegramBotRepository(session).list_active()
            runtime_settings = await load_runtime_settings(session, self._runtime.env_settings)

        if not bots:
            logger.warning(
                "No active bots in DB; Telegram bot is disabled "
                "(bootstrap empty registry from env token is Task 7)."
            )
            return

        entries: list[RegisteredBot] = []
        for row in bots:
            if row.id is None or not row.token:
                logger.warning("Skipping bot username={!r}: missing id or token", row.username)
                continue
            aiogram_bot = Bot(
                token=row.token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            entries.append(
                RegisteredBot(
                    bot_id=row.id,
                    username=row.username,
                    token=row.token,
                    webhook_secret=row.webhook_secret,
                    aiogram_bot=aiogram_bot,
                )
            )
        if not entries:
            logger.warning("No usable active bots after load; Telegram bot is disabled.")
            return

        self.registry.replace_all(entries)
        settings = self._runtime.env_settings
        path = settings.telegram_webhook_path
        base_domain = runtime_settings.base_domain

        if settings.telegram_mode is TelegramMode.WEBHOOK:
            if settings.telegram_auto_set_webhook:
                if not base_domain:
                    logger.warning(
                        "base_domain is empty; skipping setWebhook for {} bot(s).",
                        len(entries),
                    )
                else:
                    for registered in entries:
                        await self.set_webhook_for(registered, base_domain, path)
            else:
                logger.info("Telegram webhook mode (auto-set disabled); {} bot(s) loaded.", len(entries))
            return

        first = entries[0]
        if len(entries) > 1:
            logger.info(
                "Telegram polling mode: using first active bot @{} (id={}); "
                "{} other bot(s) ignored until webhook mode.",
                first.username,
                first.bot_id,
                len(entries) - 1,
            )
        if settings.telegram_auto_set_webhook:
            try:
                await first.aiogram_bot.delete_webhook(drop_pending_updates=False)
                logger.info("Telegram webhook deleted for polling mode (@{}).", first.username)
            except TelegramAPIError:
                logger.exception("Telegram deleteWebhook failed; continuing with polling.")
        assert self._dispatcher is not None
        self._task = asyncio.create_task(self._dispatcher.start_polling(first.aiogram_bot))
        logger.info("Telegram bot started (long polling) as @{}.", first.username)

    async def stop(self) -> None:
        if self._dispatcher is not None and self._task is not None:
            await self._dispatcher.stop_polling()
            self._task.cancel()
            self._task = None
        for registered in self.registry.all_active():
            await registered.aiogram_bot.session.close()
        self.registry.replace_all([])
        logger.info("Telegram bot stopped.")

    async def handle_update(self, update: Update, *, registered: RegisteredBot) -> None:
        if self._dispatcher is None:
            logger.warning("Ignoring Telegram update; bot is not started.")
            return
        token = set_hub_bot_id(registered.bot_id)
        try:
            await self._dispatcher.feed_update(registered.aiogram_bot, update)
        finally:
            reset_hub_bot_id(token)

    def _resolve_notify_bot(self, bot_id: int | None) -> RegisteredBot | None:
        if bot_id is not None:
            registered = self.registry.get_by_id(bot_id)
            if registered is not None:
                return registered
            logger.warning("No registered bot for bot_id={}; trying legacy single bot.", bot_id)
        active = self.registry.all_active()
        if len(active) == 1:
            return active[0]
        if not active:
            logger.warning("Cannot notify payment status; no bots in registry.")
        else:
            logger.warning(
                "Cannot notify payment status; bot_id={!r} missing and {} bots registered.",
                bot_id,
                len(active),
            )
        return None

    async def notify_payment_status(
        self,
        telegram_id: int,
        order_id: int,
        status: str,
        bot_id: int | None = None,
    ) -> None:
        registered = self._resolve_notify_bot(bot_id)
        if registered is None:
            return
        bot = registered.aiogram_bot
        async with self._runtime.database.session_factory() as session:
            user = await SqlBotUserRepository(session).get_by_telegram_id(telegram_id)
            order = await SqlOrderRepository(session).get(order_id)
            course = None
            channel = None
            if order is not None:
                course = await SqlCourseRepository(session).get(order.course_id)
                if order.channel_id is not None:
                    channel = await SqlTelegramChannelRepository(session).get(order.channel_id)
        language = user.preferred_language if user is not None else DEFAULT_LANGUAGE
        await bot.send_message(
            telegram_id,
            f"{bot_message(language, 'payment_status')} #{order_id}: {status}.",
        )
        if status != OrderStatus.PAID.value or course is None:
            return

        url = course_delivery.download_link(course.link, course.extra)
        channel_invite = ""
        if channel is not None:
            channel_invite = channel.invite_link or channel.discussion_invite_link or ""
        invite = course_delivery.invite_link(
            course.extra,
            fallback=channel_invite or self._runtime.env_settings.catalog_invite_link,
        )
        if not url.strip():
            logger.error("Missing download link for course_id={} order_id={}", course.id, order_id)
            await bot.send_message(telegram_id, bot_message(language, "download_missing"))
            return

        download_text = f"{bot_message(language, 'download_ready')}: {url}"
        if invite:
            download_text += f"\n{bot_message(language, 'invite_line')}: {invite}"
        await bot.send_message(telegram_id, download_text)

        email = payment_email(user.extra) if user is not None else None
        if email is None:
            logger.info("No buyer email for telegram_id={}; skip paid email", telegram_id)
            return
        settings = self._runtime.env_settings
        mailer = DeliveryMailer(
            SmtpMailer(
                host=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                from_addr=settings.smtp_from,
                use_tls=settings.smtp_use_tls,
            )
        )
        try:
            mailer.send_paid_course(email, course.name, url, invite)
        except Exception:
            logger.exception("Failed to send paid course email for order_id={}", order_id)
