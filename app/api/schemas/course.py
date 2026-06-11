from decimal import Decimal

from pydantic import BaseModel

from app.domain.entities.course import Course


class CourseOut(BaseModel):
    id: int
    name: str
    description: str
    category_id: int
    price: Decimal
    link: str

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
