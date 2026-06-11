from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CourseTranslation:
    id: int | None
    course_id: int
    language_code: str
    name: str
    description: str
    extra: dict[str, Any] = field(default_factory=dict)
