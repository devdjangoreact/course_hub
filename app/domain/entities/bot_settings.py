from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BotSettings:
    id: int | None
    bot_token: str
    backend_url: str
    app_env: str = "development"
    admin_session_secret: str = ""
    log_level: str = "INFO"
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
