from fastapi import APIRouter, status

from app.api.deps import ParserServiceDep
from app.api.schemas.parser import (
    ImportedCatalogItemOut,
    ParserJobOut,
    ParserSourceCreate,
    ParserSourceOut,
)

router = APIRouter(prefix="/api/admin", tags=["parser"])


@router.post(
    "/parser-sources",
    response_model=ParserSourceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_parser_source(
    payload: ParserSourceCreate, service: ParserServiceDep
) -> ParserSourceOut:
    source = await service.create_source(payload.to_entity())
    return ParserSourceOut.from_entity(source)


@router.post("/parser-sources/{source_id}/jobs", response_model=ParserJobOut)
async def start_parser_job(source_id: int, service: ParserServiceDep) -> ParserJobOut:
    job = await service.start_job(source_id)
    return ParserJobOut.from_entity(job)


@router.get("/parser-jobs/{job_id}", response_model=ParserJobOut)
async def get_parser_job(job_id: int, service: ParserServiceDep) -> ParserJobOut:
    job = await service.get_job(job_id)
    return ParserJobOut.from_entity(job)


@router.post("/imported-items/{item_id}/approve", response_model=ImportedCatalogItemOut)
async def approve_imported_item(item_id: int, service: ParserServiceDep) -> ImportedCatalogItemOut:
    item = await service.approve_imported_item(item_id)
    return ImportedCatalogItemOut.from_entity(item)
