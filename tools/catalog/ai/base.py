from __future__ import annotations

from typing import Any, Protocol


class AiClient(Protocol):
    def chat_json(self, system: str, user: str) -> dict[str, Any]: ...
