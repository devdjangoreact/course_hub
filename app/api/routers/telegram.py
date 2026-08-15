from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request
from loguru import logger

from app.application.services.runtime_settings import load_runtime_settings
from app.bot.registry import BotRegistry, RegisteredBot
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
        request_host = request.headers.get("host") or ""
        forwarded_host = request.headers.get("x-forwarded-host") or ""
        registered, username = _registered_bot(
            bot_app.registry,
            _host_candidates(host=request_host, forwarded_host=forwarded_host),
            runtime.base_domain,
        )
        if registered is None:
            logger.warning(
                "telegram webhook bot not found host={!r} forwarded={!r} username={!r}",
                request_host,
                forwarded_host,
                username,
            )
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        if (
            registered.webhook_secret
            and x_telegram_bot_api_secret_token != registered.webhook_secret
        ):
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

        update_id: object = None
        try:
            payload = await request.json()
            update_id = payload.get("update_id") if isinstance(payload, dict) else None
            logger.info(
                "telegram webhook host={!r} forwarded={!r} username={!r} update_id={!r}",
                request_host,
                forwarded_host,
                registered.username,
                update_id,
            )
            update = Update.model_validate(payload, context={"bot": registered.aiogram_bot})
            await bot_app.handle_update(update, registered=registered)
            return {"ok": True}
        except Exception:
            logger.exception(
                "telegram webhook failed host={!r} forwarded={!r} username={!r} update_id={!r}",
                request_host,
                forwarded_host,
                registered.username,
                update_id,
            )
            raise

    return telegram_router


def _host_candidates(*, host: str, forwarded_host: str) -> list[str]:
    candidates: list[str] = []
    for raw in (host, *(part.strip() for part in forwarded_host.split(",") if part.strip())):
        value = raw.strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def _registered_bot(
    registry: BotRegistry, hosts: list[str], base_domain: str
) -> tuple[RegisteredBot | None, str | None]:
    username: str | None = None
    for host in hosts:
        username = bot_username_from_host(host, base_domain)
        if username is not None:
            found = registry.get(username)
            if found is not None:
                return found, username
    active = registry.all_active()
    if len(active) == 1:
        return active[0], username
    return None, username
