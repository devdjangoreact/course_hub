from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.catalog_service import CatalogService
from app.application.services.order_service import OrderService
from app.application.services.search_service import SearchService
from app.container import build_catalog_service, build_order_service, build_search_service
from app.core.config import Settings, get_settings
from app.core.database import Database
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


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_catalog_service(session: SessionDep) -> CatalogService:
    return build_catalog_service(session)


def get_search_service(
    session: SessionDep,
    settings: SettingsDep,
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SearchService:
    return build_search_service(session, settings, rate_limiter)


def get_order_service(
    session: SessionDep,
    gateway: Annotated[PaymentGateway, Depends(get_payment_gateway)],
) -> OrderService:
    return build_order_service(session, gateway)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
