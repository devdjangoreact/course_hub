from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Category:
    id: int | None
    name: str
    extra: dict[str, Any] = field(default_factory=dict)
