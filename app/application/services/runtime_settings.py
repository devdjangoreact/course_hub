from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.entities.bot_settings import BotSettings
from app.infrastructure.settings_store.bot_settings_repository import SqlBotSettingsRepository


def _extra_int(extra: dict[str, Any], key: str, default: int) -> int:
    value = extra.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extra_str(extra: dict[str, Any], key: str, default: str) -> str:
    value = extra.get(key)
    return str(value) if value is not None and str(value).strip() else default


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    app_env: str
    backend_url: str
    admin_session_secret: str
    log_level: str
    bot_token: str
    supported_languages: str
    default_language: str
    search_rate_limit: int
    search_rate_window_seconds: int
    search_suggestion_min_chars: int
    search_suggestion_limit: int
    parser_request_timeout_seconds: int
    is_sqlite: bool

    @classmethod
    def from_sources(cls, env: Settings, stored: BotSettings | None) -> RuntimeSettings:
        extra = dict(stored.extra) if stored is not None else {}
        return cls(
            app_env=stored.app_env if stored and stored.app_env else env.app_env.value,
            backend_url=stored.backend_url if stored and stored.backend_url else env.backend_url,
            admin_session_secret=(
                stored.admin_session_secret
                if stored and stored.admin_session_secret
                else env.admin_session_secret
            ),
            log_level=stored.log_level if stored and stored.log_level else env.log_level,
            bot_token=stored.bot_token if stored and stored.bot_token else env.bot_token,
            supported_languages=_extra_str(extra, "supported_languages", env.supported_languages),
            default_language=_extra_str(extra, "default_language", env.default_language),
            search_rate_limit=_extra_int(extra, "search_rate_limit", env.search_rate_limit),
            search_rate_window_seconds=_extra_int(
                extra, "search_rate_window_seconds", env.search_rate_window_seconds
            ),
            search_suggestion_min_chars=_extra_int(
                extra, "search_suggestion_min_chars", env.search_suggestion_min_chars
            ),
            search_suggestion_limit=_extra_int(
                extra, "search_suggestion_limit", env.search_suggestion_limit
            ),
            parser_request_timeout_seconds=_extra_int(
                extra, "parser_request_timeout_seconds", env.parser_request_timeout_seconds
            ),
            is_sqlite=env.is_sqlite,
        )


async def load_runtime_settings(session: AsyncSession, env: Settings) -> RuntimeSettings:
    stored = await SqlBotSettingsRepository(session).get()
    return RuntimeSettings.from_sources(env, stored)
