from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.supported_language import SupportedLanguage
from app.domain.repositories.language_repository import LanguageRepository
from app.infrastructure.db.models.supported_language import SupportedLanguageModel


def _to_entity(model: SupportedLanguageModel) -> SupportedLanguage:
    return SupportedLanguage(
        code=model.code,
        name=model.name,
        native_name=model.native_name,
        is_default=model.is_default,
        is_active=model.is_active,
        extra=dict(model.extra),
    )


class SqlLanguageRepository(LanguageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[SupportedLanguage]:
        stmt = select(SupportedLanguageModel).where(SupportedLanguageModel.is_active.is_(True))
        result = await self._session.execute(stmt.order_by(SupportedLanguageModel.code))
        return [_to_entity(model) for model in result.scalars().all()]

    async def get(self, code: str) -> SupportedLanguage | None:
        model = await self._session.get(SupportedLanguageModel, code)
        return _to_entity(model) if model is not None else None

    async def get_default(self) -> SupportedLanguage:
        stmt = select(SupportedLanguageModel).where(
            SupportedLanguageModel.is_default.is_(True),
            SupportedLanguageModel.is_active.is_(True),
        )
        model = (await self._session.execute(stmt)).scalar_one()
        return _to_entity(model)

    async def add(self, language: SupportedLanguage) -> SupportedLanguage:
        model = SupportedLanguageModel(
            code=language.code,
            name=language.name,
            native_name=language.native_name,
            is_default=language.is_default,
            is_active=language.is_active,
            extra=language.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)
