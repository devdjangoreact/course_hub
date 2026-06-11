from abc import ABC, abstractmethod

from app.domain.entities.parser_job import ParserJob


class ParserJobRepository(ABC):
    @abstractmethod
    async def get(self, job_id: int) -> ParserJob | None: ...

    @abstractmethod
    async def add(self, job: ParserJob) -> ParserJob: ...

    @abstractmethod
    async def update(self, job: ParserJob) -> ParserJob: ...

    @abstractmethod
    async def list_by_source(self, source_id: int) -> list[ParserJob]: ...
