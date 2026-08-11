from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TelegramChannel:
    id: int | None
    bot_id: int
    telegram_chat_id: int
    discussion_group_id: int | None = None
    is_public: bool = False
    discussion_is_public: bool = False
    invite_link: str = ""
    discussion_invite_link: str = ""
    title: str = ""
    slug: str = ""
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
