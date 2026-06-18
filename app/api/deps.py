from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.catalog_service import CatalogService
from app.application.services.order_service import OrderService
from app.application.services.parser_service import ParserService
from app.application.services.runtime_settings import RuntimeSettings, load_runtime_settings
from app.application.services.search_service import SearchService
from app.container import (
    build_catalog_service,
    build_language_repository,
    build_order_service,
    build_parser_service,
    build_search_service,
)
from app.core.config import Settings, get_settings
from app.core.database import Database
from app.domain.repositories.language_repository import LanguageRepository
from app.domain.repositories.payment_gateway import PaymentGateway
from app.domain.repositories.rate_limiter import RateLimiter


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def get_payment_gateway(request: Request) -> PaymentGateway:
    return request.app.state.payment_gateway


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_runtime_settings(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RuntimeSettings:
    return await load_runtime_settings(session, get_settings())


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RuntimeSettingsDep = Annotated[RuntimeSettings, Depends(get_runtime_settings)]


def get_catalog_service(session: SessionDep) -> CatalogService:
    return build_catalog_service(session)


def get_language_repository(session: SessionDep) -> LanguageRepository:
    return build_language_repository(session)


def get_search_service(
    session: SessionDep,
    runtime: RuntimeSettingsDep,
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SearchService:
    return build_search_service(session, runtime, rate_limiter)


def get_order_service(
    session: SessionDep,
    gateway: Annotated[PaymentGateway, Depends(get_payment_gateway)],
) -> OrderService:
    return build_order_service(session, gateway)


def get_parser_service(session: SessionDep) -> ParserService:
    return build_parser_service(session)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
LanguageRepositoryDep = Annotated[LanguageRepository, Depends(get_language_repository)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
ParserServiceDep = Annotated[ParserService, Depends(get_parser_service)]
