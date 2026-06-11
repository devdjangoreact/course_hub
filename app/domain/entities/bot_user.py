from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BotUser:
    id: int | None
    telegram_id: int
    username: str | None = None
    full_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
