from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.parser_job import ParserJob
from app.domain.entities.parser_job_status import ParserJobStatus
from app.domain.repositories.parser_job_repository import ParserJobRepository
from app.infrastructure.db.models.parser_job import ParserJobModel


def _to_entity(model: ParserJobModel) -> ParserJob:
    return ParserJob(
        id=model.id,
        source_id=model.source_id,
        status=ParserJobStatus(model.status),
        started_at=model.started_at,
        finished_at=model.finished_at,
        imported_count=model.imported_count,
        skipped_count=model.skipped_count,
        error_summary=model.error_summary,
        extra=dict(model.extra),
    )


class SqlParserJobRepository(ParserJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, job_id: int) -> ParserJob | None:
        model = await self._session.get(ParserJobModel, job_id)
        return _to_entity(model) if model is not None else None

    async def add(self, job: ParserJob) -> ParserJob:
        model = ParserJobModel(
            source_id=job.source_id,
            status=job.status.value,
            started_at=job.started_at,
            finished_at=job.finished_at,
            imported_count=job.imported_count,
            skipped_count=job.skipped_count,
            error_summary=job.error_summary,
            extra=job.extra,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def update(self, job: ParserJob) -> ParserJob:
        assert job.id is not None
        model = await self._session.get(ParserJobModel, job.id)
        if model is None:
            return await self.add(job)
        model.status = job.status.value
        model.started_at = job.started_at
        model.finished_at = job.finished_at
        model.imported_count = job.imported_count
        model.skipped_count = job.skipped_count
        model.error_summary = job.error_summary
        model.extra = job.extra
        await self._session.flush()
        return _to_entity(model)

    async def list_by_source(self, source_id: int) -> list[ParserJob]:
        stmt = select(ParserJobModel).where(ParserJobModel.source_id == source_id)
        result = await self._session.execute(stmt.order_by(ParserJobModel.id.desc()))
        return [_to_entity(model) for model in result.scalars().all()]
