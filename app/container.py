from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.catalog_service import CatalogService
from app.application.services.localization_service import LocalizationService
from app.application.services.order_service import OrderService
from app.application.services.parser_service import ParserService
from app.application.services.search_service import SearchService
from app.application.services.runtime_settings import RuntimeSettings
from app.domain.repositories.language_repository import LanguageRepository
from app.domain.repositories.payment_gateway import PaymentGateway
from app.domain.repositories.rate_limiter import RateLimiter
from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository
from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository
from app.infrastructure.db.repositories.imported_catalog_item_repository import (
    SqlImportedCatalogItemRepository,
)
from app.infrastructure.db.repositories.language_repository import SqlLanguageRepository
from app.infrastructure.db.repositories.order_repository import SqlOrderRepository
from app.infrastructure.db.repositories.parser_job_repository import SqlParserJobRepository
from app.infrastructure.db.repositories.parser_source_repository import SqlParserSourceRepository
from app.infrastructure.db.repositories.translation_repository import SqlTranslationRepository
from app.infrastructure.db.search.fts5_search_repository import Fts5SearchRepository
from app.infrastructure.db.search.like_search_repository import LikeSearchRepository
from app.infrastructure.db.search.localized_suggestion_search_repository import (
    LocalizedSuggestionSearchRepository,
)
from app.infrastructure.parsers.catalog_parser import HttpCatalogParser
from app.infrastructure.settings_store.payment_settings_repository import (
    SqlPaymentSettingsRepository,
)


def build_catalog_service(session: AsyncSession) -> CatalogService:
    return CatalogService(
        SqlCategoryRepository(session),
        SqlCourseRepository(session),
        SqlTranslationRepository(session),
    )


def build_language_repository(session: AsyncSession) -> LanguageRepository:
    return SqlLanguageRepository(session)


def build_localization_service(session: AsyncSession) -> LocalizationService:
    return LocalizationService(build_language_repository(session))


def build_search_service(
    session: AsyncSession, runtime: RuntimeSettings, rate_limiter: RateLimiter
) -> SearchService:
    search = (
        Fts5SearchRepository(session) if runtime.is_sqlite else LikeSearchRepository(session)
    )
    return SearchService(
        search,
        rate_limiter,
        LocalizedSuggestionSearchRepository(session),
        runtime.search_suggestion_min_chars,
        runtime.search_suggestion_limit,
    )


def build_order_service(session: AsyncSession, gateway: PaymentGateway) -> OrderService:
    return OrderService(
        SqlBotUserRepository(session),
        SqlCourseRepository(session),
        SqlOrderRepository(session),
        gateway,
        SqlPaymentSettingsRepository(session),
    )


def build_parser_service(session: AsyncSession) -> ParserService:
    return ParserService(
        SqlParserSourceRepository(session),
        SqlParserJobRepository(session),
        SqlImportedCatalogItemRepository(session),
        HttpCatalogParser(),
    )
