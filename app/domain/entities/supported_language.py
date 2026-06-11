from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SupportedLanguage:
    code: str
    name: str
    native_name: str
    is_default: bool = False
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
