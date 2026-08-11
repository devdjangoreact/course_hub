from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TelegramBot:
    id: int | None
    username: str
    token: str
    webhook_secret: str = ""
    is_active: bool = True
    title: str = ""
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
