from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import CatalogServiceDep, SearchServiceDep
from app.api.schemas.category import CategoryOut
from app.api.schemas.course import CourseOut

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(service: CatalogServiceDep) -> list[CategoryOut]:
    categories = await service.list_categories()
    return [CategoryOut.from_entity(category) for category in categories]


@router.get("/categories/{category_id}/courses", response_model=list[CourseOut])
async def list_courses(category_id: int, service: CatalogServiceDep) -> list[CourseOut]:
    courses = await service.list_courses(category_id)
    return [CourseOut.from_entity(course) for course in courses]


@router.get("/courses/search", response_model=list[CourseOut])
async def search_courses(
    request: Request,
    service: SearchServiceDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
) -> list[CourseOut]:
    rate_key = f"http:{request.client.host if request.client else 'unknown'}"
    courses = await service.search(q, rate_key=rate_key)
    return [CourseOut.from_entity(course) for course in courses]
