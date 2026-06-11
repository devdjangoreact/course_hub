from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.catalog_service import CatalogService
from app.application.services.order_service import OrderService
from app.application.services.search_service import SearchService
from app.core.config import Settings
from app.domain.repositories.payment_gateway import PaymentGateway
from app.domain.repositories.rate_limiter import RateLimiter
from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository
from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository
from app.infrastructure.db.repositories.order_repository import SqlOrderRepository
from app.infrastructure.db.search.fts5_search_repository import Fts5SearchRepository
from app.infrastructure.db.search.like_search_repository import LikeSearchRepository
from app.infrastructure.settings_store.payment_settings_repository import (
    SqlPaymentSettingsRepository,
)


def build_catalog_service(session: AsyncSession) -> CatalogService:
    return CatalogService(SqlCategoryRepository(session), SqlCourseRepository(session))


def build_search_service(
    session: AsyncSession, settings: Settings, rate_limiter: RateLimiter
) -> SearchService:
    search = Fts5SearchRepository(session) if settings.is_sqlite else LikeSearchRepository(session)
    return SearchService(search, rate_limiter)


def build_order_service(session: AsyncSession, gateway: PaymentGateway) -> OrderService:
    return OrderService(
        SqlBotUserRepository(session),
        SqlCourseRepository(session),
        SqlOrderRepository(session),
        gateway,
        SqlPaymentSettingsRepository(session),
    )
