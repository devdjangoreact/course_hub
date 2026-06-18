from dataclasses import dataclass

from app.core.config import Settings
from app.core.database import Database
from app.domain.repositories.payment_gateway import PaymentGateway
from app.domain.repositories.rate_limiter import RateLimiter


@dataclass(slots=True)
class BotRuntime:
    """Shared dependencies handed to bot handlers via middleware."""

    database: Database
    env_settings: Settings
    rate_limiter: RateLimiter
    payment_gateway: PaymentGateway
