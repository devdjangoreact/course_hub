from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PaymentSettings:
    id: int | None
    provider: str
    api_key: str | None = None
    secret_key: str | None = None
    currency: str = "USD"
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
