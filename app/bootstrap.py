from loguru import logger
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import Database
from app.core.domain_host import normalize_bot_username
from app.domain.entities.admin_user import AdminUser
from app.domain.entities.bot_settings import BotSettings
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.entities.telegram_bot import TelegramBot
from app.domain.entities.telegram_channel import TelegramChannel
from app.infrastructure.db.models.supported_language import SupportedLanguageModel
from app.infrastructure.db.models.telegram_bot import TelegramBotModel
from app.infrastructure.db.repositories.telegram_bot_repository import SqlTelegramBotRepository
from app.infrastructure.db.repositories.telegram_channel_repository import (
    SqlTelegramChannelRepository,
)
from app.infrastructure.security.password import hash_password
from app.infrastructure.settings_store.admin_user_repository import SqlAdminUserRepository
from app.infrastructure.settings_store.bot_settings_repository import SqlBotSettingsRepository
from app.infrastructure.settings_store.payment_settings_repository import (
    SqlPaymentSettingsRepository,
)

_LANGUAGE_NAMES = {
    "ru": ("Russian", "Русский"),
    "uk": ("Ukrainian", "Українська"),
    "en": ("English", "English"),
}

_DEFAULT_ADMIN_USERNAME = "admin"
_DEFAULT_ADMIN_PASSWORD = "admin"


def _parse_languages(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


async def _ensure_default_admin(session, settings: Settings) -> None:
    admins = SqlAdminUserRepository(session)
    if await admins.count() > 0:
        return
    username = settings.admin_username.strip() or _DEFAULT_ADMIN_USERNAME
    password = settings.admin_password
    if not password or password == "change-me":
        password = _DEFAULT_ADMIN_PASSWORD
    await admins.add(
        AdminUser(
            id=None,
            username=username,
            password_hash=hash_password(password),
        )
    )
    logger.warning(
        "Created default admin user '{}'. Change the password in the admin panel.",
        username,
    )


async def _resolve_seed_username(token: str, settings: Settings) -> str | None:
    if settings.bot_username.strip():
        return normalize_bot_username(settings.bot_username)
    try:
        from aiogram import Bot

        bot = Bot(token=token)
        try:
            me = await bot.get_me()
        finally:
            await bot.session.close()
    except Exception:
        logger.exception("Failed to resolve bot username via getMe; skip bots seed.")
        return None
    username = getattr(me, "username", None)
    if not username:
        logger.warning("Telegram getMe returned no username; skip bots seed.")
        return None
    return normalize_bot_username(str(username))


async def _ensure_legacy_bot(session, settings: Settings) -> None:
    count = await session.scalar(select(func.count()).select_from(TelegramBotModel))
    if count and int(count) > 0:
        return

    stored = await SqlBotSettingsRepository(session).get()
    token = (stored.bot_token if stored and stored.bot_token else "") or settings.bot_token
    if not token.strip():
        return

    username = await _resolve_seed_username(token, settings)
    if username is None:
        return

    bot = await SqlTelegramBotRepository(session).save(
        TelegramBot(
            id=None,
            username=username,
            token=token,
            webhook_secret=settings.telegram_webhook_secret,
            is_active=True,
            title=username,
        )
    )
    logger.info("Seeded bots row for @{} from legacy token.", username)
    if settings.catalog_channel_id is None or bot.id is None:
        return
    await SqlTelegramChannelRepository(session).save(
        TelegramChannel(
            id=None,
            bot_id=bot.id,
            telegram_chat_id=int(settings.catalog_channel_id),
            discussion_group_id=settings.catalog_discussion_group_id,
            invite_link=settings.catalog_invite_link,
            title="Catalog",
            is_active=True,
        )
    )
    logger.info("Seeded catalog channel {} for bot_id={}.", settings.catalog_channel_id, bot.id)


async def ensure_initial_data(database: Database, settings: Settings) -> None:
    """Seed languages, default admin, and settings rows from env (idempotent)."""
    async with database.session_factory() as session:
        languages = _parse_languages(settings.supported_languages)
        for code in languages:
            model = await session.get(SupportedLanguageModel, code)
            name, native_name = _LANGUAGE_NAMES.get(code, (code.upper(), code.upper()))
            if model is None:
                session.add(
                    SupportedLanguageModel(
                        code=code,
                        name=name,
                        native_name=native_name,
                        is_default=code == settings.default_language,
                    )
                )
            else:
                model.name = name
                model.native_name = native_name
                model.is_default = code == settings.default_language
                model.is_active = True

        if languages:
            stmt = select(SupportedLanguageModel).where(
                SupportedLanguageModel.code.not_in(languages)
            )
            for model in (await session.execute(stmt)).scalars().all():
                model.is_active = False

        await _ensure_default_admin(session, settings)

        bot_settings = SqlBotSettingsRepository(session)
        if await bot_settings.get() is None:
            await bot_settings.save(
                BotSettings(
                    id=None,
                    bot_token=settings.bot_token,
                    backend_url=settings.backend_url,
                    app_env=settings.app_env.value,
                    admin_session_secret=settings.admin_session_secret,
                    log_level=settings.log_level,
                    extra={
                        "supported_languages": settings.supported_languages,
                        "default_language": settings.default_language,
                        "search_rate_limit": settings.search_rate_limit,
                        "search_rate_window_seconds": settings.search_rate_window_seconds,
                        "search_suggestion_min_chars": settings.search_suggestion_min_chars,
                        "search_suggestion_limit": settings.search_suggestion_limit,
                        "parser_request_timeout_seconds": settings.parser_request_timeout_seconds,
                    },
                )
            )

        payment_settings = SqlPaymentSettingsRepository(session)
        if await payment_settings.get() is None:
            await payment_settings.save(
                PaymentSettings(
                    id=None,
                    provider=settings.payment_provider,
                    api_key=settings.payment_api_key or None,
                    secret_key=settings.payment_secret_key or None,
                    currency=settings.payment_currency,
                    extra={
                        "lava_env": settings.lava_env,
                        "checkout_mode": settings.payment_link_mode,
                    },
                )
            )

        await _ensure_legacy_bot(session, settings)
        await session.commit()
