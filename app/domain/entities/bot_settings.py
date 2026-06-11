from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BotSettings:
    id: int | None
    bot_token: str
    backend_url: str
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
