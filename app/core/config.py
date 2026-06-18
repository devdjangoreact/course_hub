from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./course_hub.db"

    bot_token: str = ""
    backend_url: str = "http://localhost:8000"

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
    supported_languages: str = "uk,en"
    default_language: str = "uk"
    search_suggestion_min_chars: int = 3
    search_suggestion_limit: int = 5
    parser_request_timeout_seconds: int = 10

    @property
    def is_development(self) -> bool:
        return self.app_env is AppEnv.DEVELOPMENT

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
