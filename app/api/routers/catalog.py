from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import CatalogServiceDep, SearchServiceDep
from app.api.schemas.category import CategoryOut
from app.api.schemas.course import CourseOut
from app.api.schemas.search import SearchSuggestionOut

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    service: CatalogServiceDep,
    language: str | None = None,
) -> list[CategoryOut]:
    if language:
        categories = await service.list_localized_categories(language)
        return [CategoryOut.from_localized(category) for category in categories]
    categories = await service.list_categories()
    return [CategoryOut.from_entity(category) for category in categories]


@router.get("/categories/{category_id}/courses", response_model=list[CourseOut])
async def list_courses(
    category_id: int,
    service: CatalogServiceDep,
    language: str | None = None,
) -> list[CourseOut]:
    if language:
        courses = await service.list_localized_courses(category_id, language)
        return [CourseOut.from_localized(course) for course in courses]
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


@router.get("/search/suggestions", response_model=list[SearchSuggestionOut])
async def search_suggestions(
    request: Request,
    service: SearchServiceDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    language: str = "uk",
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[SearchSuggestionOut]:
    rate_key = f"http:{request.client.host if request.client else 'unknown'}"
    suggestions = await service.suggest(q, language, rate_key=rate_key, limit=limit)
    return [SearchSuggestionOut.from_entity(suggestion) for suggestion in suggestions]
