from abc import ABC, abstractmethod

from app.domain.entities.parser_source import ParserSource


class ParserSourceRepository(ABC):
    @abstractmethod
    async def list_all(self) -> list[ParserSource]: ...

    @abstractmethod
    async def get(self, source_id: int) -> ParserSource | None: ...

    @abstractmethod
    async def add(self, source: ParserSource) -> ParserSource: ...

    @abstractmethod
    async def update(self, source: ParserSource) -> ParserSource: ...
