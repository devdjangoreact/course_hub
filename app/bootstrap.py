from loguru import logger

from app.core.config import Settings
from app.core.database import Database
from app.domain.entities.admin_user import AdminUser
from app.domain.entities.bot_settings import BotSettings
from app.domain.entities.payment_settings import PaymentSettings
from app.infrastructure.security.password import hash_password
from app.infrastructure.settings_store.admin_user_repository import SqlAdminUserRepository
from app.infrastructure.settings_store.bot_settings_repository import SqlBotSettingsRepository
from app.infrastructure.settings_store.payment_settings_repository import (
    SqlPaymentSettingsRepository,
)


async def ensure_initial_data(database: Database, settings: Settings) -> None:
    """Seed the first admin account and settings rows from env (idempotent)."""
    async with database.session_factory() as session:
        admins = SqlAdminUserRepository(session)
        if await admins.get_by_username(settings.admin_username) is None:
            await admins.add(
                AdminUser(
                    id=None,
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )
            logger.info("Seeded initial admin user '{}'.", settings.admin_username)

        bot_settings = SqlBotSettingsRepository(session)
        if await bot_settings.get() is None:
            await bot_settings.save(
                BotSettings(
                    id=None,
                    bot_token=settings.bot_token,
                    backend_url=settings.backend_url,
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
                )
            )
        await session.commit()
