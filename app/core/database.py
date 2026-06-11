from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
    return create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        connect_args=connect_args,
    )


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
