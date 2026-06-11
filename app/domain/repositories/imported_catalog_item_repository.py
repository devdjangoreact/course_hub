from abc import ABC, abstractmethod

from app.domain.entities.imported_catalog_item import ImportedCatalogItem


class ImportedCatalogItemRepository(ABC):
    @abstractmethod
    async def get(self, item_id: int) -> ImportedCatalogItem | None: ...

    @abstractmethod
    async def add(self, item: ImportedCatalogItem) -> ImportedCatalogItem: ...

    @abstractmethod
    async def update(self, item: ImportedCatalogItem) -> ImportedCatalogItem: ...

    @abstractmethod
    async def list_by_job(self, parser_job_id: int) -> list[ImportedCatalogItem]: ...

    @abstractmethod
    async def find_duplicate(
        self, source_id: int, external_id: str | None, fingerprint: str
    ) -> ImportedCatalogItem | None: ...
