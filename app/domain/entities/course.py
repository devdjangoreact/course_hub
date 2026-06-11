from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class Course:
    id: int | None
    name: str
    description: str
    category_id: int
    price: Decimal
    link: str
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
