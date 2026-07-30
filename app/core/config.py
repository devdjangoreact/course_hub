import os
from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class TelegramMode(StrEnum):
    WEBHOOK = "webhook"
    POLLING = "polling"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./course_hub.db"

    bot_token: str = ""
    backend_url: str = "http://localhost:8000"

    telegram_mode: TelegramMode = TelegramMode.WEBHOOK
    telegram_auto_set_webhook: bool = True
    telegram_webhook_path: str = "/api/telegram/webhook"
    telegram_webhook_secret: str = ""

    admin_username: str = "admin"
    admin_password: str = "change-me"
    admin_session_secret: str = "change-me-too"

    payment_provider: str = "simulated"
    payment_api_key: str = ""
    payment_secret_key: str = ""
    payment_currency: str = "USD"
    lava_env: str = "production"
    payment_link_mode: str = "direct"

    log_level: str = "INFO"

    search_rate_limit: int = 5
    search_rate_window_seconds: int = 60
    supported_languages: str = "ru,uk,en"
    default_language: str = "ru"
    search_suggestion_min_chars: int = 3
    search_suggestion_limit: int = 5
    parser_request_timeout_seconds: int = 10

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    catalog_channel_id: int | None = None
    catalog_invite_link: str = ""
    catalog_discussion_group_id: int | None = None

    @property
    def is_development(self) -> bool:
        return self.app_env is AppEnv.DEVELOPMENT

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_vercel(self) -> bool:
        return os.environ.get("VERCEL") == "1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
