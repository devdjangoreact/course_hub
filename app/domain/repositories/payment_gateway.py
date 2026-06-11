from abc import ABC, abstractmethod

from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings


class PaymentGateway(ABC):
    @abstractmethod
    async def create_payment(self, order: Order, settings: PaymentSettings) -> PaymentIntent: ...

    @abstractmethod
    def verify_signature(
        self, payload: bytes, signature: str, settings: PaymentSettings
    ) -> bool: ...
