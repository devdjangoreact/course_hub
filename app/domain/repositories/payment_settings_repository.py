from abc import ABC, abstractmethod

from app.domain.entities.payment_settings import PaymentSettings


class PaymentSettingsRepository(ABC):
    @abstractmethod
    async def get(self) -> PaymentSettings | None: ...

    @abstractmethod
    async def save(self, settings: PaymentSettings) -> PaymentSettings: ...
