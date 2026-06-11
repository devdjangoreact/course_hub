from decimal import Decimal

from pydantic import BaseModel

from app.application.services.catalog_service import LocalizedCourse
from app.domain.entities.course import Course


class CourseOut(BaseModel):
    id: int
    name: str
    description: str
    category_id: int
    price: Decimal
    link: str
    language: str | None = None
    fallback_used: bool = False

    @classmethod
    def from_entity(cls, course: Course) -> "CourseOut":
        assert course.id is not None
        return cls(
            id=course.id,
            name=course.name,
            description=course.description,
            category_id=course.category_id,
            price=course.price,
            link=course.link,
        )

    @classmethod
    def from_localized(cls, course: LocalizedCourse) -> "CourseOut":
        return cls(
            id=course.id,
            name=course.name,
            description=course.description,
            category_id=course.category_id,
            price=course.price,
            link=course.link,
            language=course.language,
            fallback_used=course.fallback_used,
        )
