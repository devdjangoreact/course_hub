from app.application.errors import NotFoundError
from app.domain.entities.category import Category
from app.domain.entities.course import Course
from app.domain.repositories.category_repository import CategoryRepository
from app.domain.repositories.course_repository import CourseRepository


class CatalogService:
    def __init__(
        self,
        categories: CategoryRepository,
        courses: CourseRepository,
    ) -> None:
        self._categories = categories
        self._courses = courses

    async def list_categories(self) -> list[Category]:
        return await self._categories.list_all()

    async def list_courses(self, category_id: int) -> list[Course]:
        category = await self._categories.get(category_id)
        if category is None:
            raise NotFoundError("Category not found")
        return await self._courses.list_active_by_category(category_id)

    async def get_course(self, course_id: int) -> Course:
        course = await self._courses.get_active(course_id)
        if course is None:
            raise NotFoundError("Course not found")
        return course
