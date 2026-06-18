from fastapi import FastAPI
from httpx import AsyncClient

from app.domain.entities.bot_settings import BotSettings
from app.domain.entities.payment_settings import PaymentSettings
from app.infrastructure.settings_store.bot_settings_repository import SqlBotSettingsRepository
from app.infrastructure.settings_store.payment_settings_repository import (
    SqlPaymentSettingsRepository,
)


async def test_admin_requires_login(client: AsyncClient) -> None:
    response = await client.get("/admin/", follow_redirects=False)
    assert response.status_code in (302, 303, 401)


async def test_admin_login_with_seeded_user(client: AsyncClient) -> None:
    response = await client.post(
        "/admin/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


async def test_settings_persist(app: FastAPI) -> None:
    database = app.state.db
    async with database.session_factory() as session:
        bot_repo = SqlBotSettingsRepository(session)
        payment_repo = SqlPaymentSettingsRepository(session)

        await bot_repo.save(
            BotSettings(
                id=1,
                bot_token="updated-token",
                backend_url="https://example.com",
                app_env="production",
                admin_session_secret="session-secret",
                log_level="DEBUG",
            )
        )
        await payment_repo.save(
            PaymentSettings(
                id=1,
                provider="simulated",
                secret_key="updated-secret",
                currency="USD",
            )
        )
        await session.commit()

    async with database.session_factory() as session:
        bot_settings = await SqlBotSettingsRepository(session).get()
        payment_settings = await SqlPaymentSettingsRepository(session).get()

    assert bot_settings is not None
    assert bot_settings.backend_url == "https://example.com"
    assert payment_settings is not None
    assert payment_settings.secret_key == "updated-secret"
