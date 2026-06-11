from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.parser_source import ParserSource
from app.domain.repositories.parser_source_repository import ParserSourceRepository
from app.infrastructure.db.models.parser_source import ParserSourceModel


def _to_entity(model: ParserSourceModel) -> ParserSource:
    return ParserSource(
        id=model.id,
        name=model.name,
        source_type=model.source_type,
        url=model.url,
        is_active=model.is_active,
        last_status=model.last_status,
        extra=dict(model.extra),
    )


class SqlParserSourceRepository(ParserSourceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[ParserSource]:
        result = await self._session.execute(
            select(ParserSourceModel).order_by(ParserSourceModel.name)
        )
        return [_to_entity(model) for model in result.scalars().all()]

    async def get(self, source_id: int) -> ParserSource | None:
        model = await self._session.get(ParserSourceModel, source_id)
        return _to_entity(model) if model is not None else None

    async def add(self, source: ParserSource) -> ParserSource:
        model = ParserSourceModel(
            name=source.name,
            source_type=source.source_type,
            url=source.url,
            is_active=source.is_active,
            last_status=source.last_status,
            extra=source.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def update(self, source: ParserSource) -> ParserSource:
        assert source.id is not None
        model = await self._session.get(ParserSourceModel, source.id)
        if model is None:
            return await self.add(source)
        model.name = source.name
        model.source_type = source.source_type
        model.url = source.url
        model.is_active = source.is_active
        model.last_status = source.last_status
        model.extra = source.extra
        await self._session.flush()
        return _to_entity(model)
