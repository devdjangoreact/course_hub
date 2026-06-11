from abc import ABC, abstractmethod

from app.domain.entities.category_translation import CategoryTranslation
from app.domain.entities.course_translation import CourseTranslation


class TranslationRepository(ABC):
    @abstractmethod
    async def get_category_translation(
        self, category_id: int, language_code: str
    ) -> CategoryTranslation | None: ...

    @abstractmethod
    async def list_category_translations(self, language_code: str) -> list[CategoryTranslation]: ...

    @abstractmethod
    async def get_course_translation(
        self, course_id: int, language_code: str
    ) -> CourseTranslation | None: ...

    @abstractmethod
    async def list_course_translations_by_category(
        self, category_id: int, language_code: str
    ) -> list[CourseTranslation]: ...

    @abstractmethod
    async def add_category_translation(
        self, translation: CategoryTranslation
    ) -> CategoryTranslation: ...

    @abstractmethod
    async def add_course_translation(self, translation: CourseTranslation) -> CourseTranslation: ...
