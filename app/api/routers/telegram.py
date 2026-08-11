from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from app.application.services.runtime_settings import load_runtime_settings
from app.bot.registry import RegisteredBot
from app.core.config import TelegramMode
from app.core.domain_host import bot_username_from_host


def build_telegram_router(webhook_path: str) -> APIRouter:
    path = webhook_path if webhook_path.startswith("/") else f"/{webhook_path}"
    telegram_router = APIRouter(tags=["telegram"])

    @telegram_router.post(path)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        settings = request.app.state.settings
        if settings.telegram_mode is not TelegramMode.WEBHOOK:
            raise HTTPException(status_code=404, detail="Telegram webhook disabled")

        bot_app = getattr(request.app.state, "bot_app", None)
        if bot_app is None:
            raise HTTPException(status_code=503, detail="Bot is not ready")

        runtime = getattr(request.app.state, "runtime_settings", None)
        if runtime is None:
            async with request.app.state.db.session_factory() as session:
                runtime = await load_runtime_settings(session, settings)
        base_domain = runtime.base_domain
        host = request.headers.get("host") or ""
        username = bot_username_from_host(host, base_domain)
        if username is None:
            raise HTTPException(status_code=404, detail="Unknown Telegram bot host")

        registered: RegisteredBot | None = bot_app.registry.get(username)
        if registered is None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        if registered.webhook_secret and x_telegram_bot_api_secret_token != registered.webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

        payload = await request.json()
        update = Update.model_validate(payload)
        await bot_app.handle_update(update, registered=registered)
        return {"ok": True}

    return telegram_router
