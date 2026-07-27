from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import TelegramMode


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

        expected = settings.telegram_webhook_secret
        if expected and x_telegram_bot_api_secret_token != expected:
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

        bot_app = getattr(request.app.state, "bot_app", None)
        if bot_app is None:
            raise HTTPException(status_code=503, detail="Bot is not ready")

        payload = await request.json()
        update = Update.model_validate(payload)
        await bot_app.handle_update(update)
        return {"ok": True}

    return telegram_router
