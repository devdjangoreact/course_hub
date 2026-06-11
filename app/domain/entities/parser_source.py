from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ParserSource:
    id: int | None
    name: str
    source_type: str
    url: str
    is_active: bool = True
    last_status: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
