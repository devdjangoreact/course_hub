from abc import ABC, abstractmethod

from app.domain.entities.course import Course


class CourseRepository(ABC):
    @abstractmethod
    async def list_active_by_category(self, category_id: int) -> list[Course]: ...

    @abstractmethod
    async def get_active(self, course_id: int) -> Course | None: ...

    @abstractmethod
    async def get(self, course_id: int) -> Course | None: ...

    @abstractmethod
    async def add(self, course: Course) -> Course: ...
