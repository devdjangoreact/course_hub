from collections.abc import AsyncIterator
import os
import ssl

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings


def async_database_url(url: str) -> str:
    """Ensure Postgres URLs use the asyncpg driver for create_async_engine."""
    if url.startswith(("postgresql+asyncpg://", "sqlite+")):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    return url


def _supabase_ssl_context() -> ssl.SSLContext:
    # Pooler presents a chain Vercel's CA store rejects ("self-signed in chain").
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def create_engine(settings: Settings) -> AsyncEngine:
    url = async_database_url(settings.database_url)
    connect_args: dict = {}
    engine_kwargs: dict = {"echo": False, "future": True}
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False
    elif "supabase.com" in url:
        connect_args["ssl"] = _supabase_ssl_context()
        # Transaction pooler (port 6543) + asyncpg: disable prepared statement cache
        if "pooler.supabase.com" in url or ":6543" in url:
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0
    if os.environ.get("VERCEL") == "1":
        engine_kwargs["poolclass"] = NullPool
    return create_async_engine(url, connect_args=connect_args, **engine_kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Database:
    """Holds the async engine and session factory for the app lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._engine = create_engine(settings)
        self._session_factory = create_session_factory(self._engine)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self._engine.dispose()
