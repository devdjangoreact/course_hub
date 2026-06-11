from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AdminUser:
    id: int | None
    username: str
    password_hash: str
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
