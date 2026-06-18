from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.admin.setup import setup_admin
from app.api.routers import catalog, health, orders, parser
from app.application.errors import (
    ApplicationError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from app.bootstrap import ensure_initial_data
from app.bot.context import BotRuntime
from app.bot.runner import BotApp
from app.core.config import get_settings
from app.core.database import Database
from app.core.logging import setup_logging
from app.infrastructure.db.init_db import create_schema
from app.infrastructure.payments.gateway_factory import build_payment_gateway
from app.infrastructure.ratelimit.in_memory_rate_limiter import InMemoryRateLimiter

_STATUS_MAP: dict[type[ApplicationError], int] = {
    NotFoundError: 404,
    ValidationError: 422,
    RateLimitedError: 429,
}


async def _application_error_handler(_: Request, exc: Exception) -> JSONResponse:
    status_code = _STATUS_MAP.get(type(exc), 400) if isinstance(exc, ApplicationError) else 400
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    database: Database = app.state.db
    await create_schema(database, settings)
    await ensure_initial_data(database, settings)
    bot_app = BotApp(
        BotRuntime(
            database=database,
            settings=settings,
            rate_limiter=app.state.rate_limiter,
            payment_gateway=app.state.payment_gateway,
        )
    )
    app.state.bot_app = bot_app
    await bot_app.start()
    try:
        yield
    finally:
        await bot_app.stop()
        await database.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="Course Hub", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = Database(settings)
    app.state.rate_limiter = InMemoryRateLimiter(
        settings.search_rate_limit, settings.search_rate_window_seconds
    )
    app.state.payment_gateway = build_payment_gateway(settings.backend_url)

    app.include_router(health.router)
    app.include_router(catalog.router)
    app.include_router(orders.router)
    app.include_router(parser.router)

    app.add_exception_handler(ApplicationError, _application_error_handler)

    setup_admin(app, app.state.db, settings)
    return app


app = create_app()
