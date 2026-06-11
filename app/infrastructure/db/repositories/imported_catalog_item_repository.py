from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.imported_catalog_item import ImportedCatalogItem
from app.domain.entities.imported_catalog_item_status import ImportedCatalogItemStatus
from app.domain.repositories.imported_catalog_item_repository import (
    ImportedCatalogItemRepository,
)
from app.infrastructure.db.models.imported_catalog_item import ImportedCatalogItemModel
from app.infrastructure.db.models.parser_job import ParserJobModel


def _to_entity(model: ImportedCatalogItemModel) -> ImportedCatalogItem:
    return ImportedCatalogItem(
        id=model.id,
        parser_job_id=model.parser_job_id,
        item_type=model.item_type,
        external_id=model.external_id,
        source_url=model.source_url,
        fingerprint=model.fingerprint,
        language_code=model.language_code,
        payload=dict(model.payload),
        status=ImportedCatalogItemStatus(model.status),
        matched_category_id=model.matched_category_id,
        matched_course_id=model.matched_course_id,
        extra=dict(model.extra),
    )


class SqlImportedCatalogItemRepository(ImportedCatalogItemRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, item_id: int) -> ImportedCatalogItem | None:
        model = await self._session.get(ImportedCatalogItemModel, item_id)
        return _to_entity(model) if model is not None else None

    async def add(self, item: ImportedCatalogItem) -> ImportedCatalogItem:
        model = ImportedCatalogItemModel(
            parser_job_id=item.parser_job_id,
            item_type=item.item_type,
            external_id=item.external_id,
            source_url=item.source_url,
            fingerprint=item.fingerprint,
            language_code=item.language_code,
            payload=item.payload,
            status=item.status.value,
            matched_category_id=item.matched_category_id,
            matched_course_id=item.matched_course_id,
            extra=item.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def update(self, item: ImportedCatalogItem) -> ImportedCatalogItem:
        assert item.id is not None
        model = await self._session.get(ImportedCatalogItemModel, item.id)
        if model is None:
            return await self.add(item)
        model.status = item.status.value
        model.matched_category_id = item.matched_category_id
        model.matched_course_id = item.matched_course_id
        model.extra = item.extra
        await self._session.flush()
        return _to_entity(model)

    async def list_by_job(self, parser_job_id: int) -> list[ImportedCatalogItem]:
        stmt = select(ImportedCatalogItemModel).where(
            ImportedCatalogItemModel.parser_job_id == parser_job_id
        )
        result = await self._session.execute(stmt.order_by(ImportedCatalogItemModel.id))
        return [_to_entity(model) for model in result.scalars().all()]

    async def find_duplicate(
        self, source_id: int, external_id: str | None, fingerprint: str
    ) -> ImportedCatalogItem | None:
        stmt = (
            select(ImportedCatalogItemModel)
            .join(ParserJobModel, ImportedCatalogItemModel.parser_job_id == ParserJobModel.id)
            .where(ParserJobModel.source_id == source_id)
        )
        if external_id:
            stmt = stmt.where(ImportedCatalogItemModel.external_id == external_id)
        else:
            stmt = stmt.where(ImportedCatalogItemModel.fingerprint == fingerprint)
        model = (await self._session.execute(stmt.limit(1))).scalar_one_or_none()
        return _to_entity(model) if model is not None else None
