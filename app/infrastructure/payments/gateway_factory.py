from loguru import logger

from app.application.errors import ValidationError
from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.payment_gateway import PaymentGateway
from app.infrastructure.payments.atlos_gateway import AtlosPaymentGateway
from app.infrastructure.payments.simulated_gateway import SimulatedPaymentGateway


class RoutingPaymentGateway(PaymentGateway):
    """Delegates to simulated or atlos based on persisted payment settings."""

    def __init__(self, backend_url: str) -> None:
        self._simulated = SimulatedPaymentGateway(backend_url)
        self._atlos = AtlosPaymentGateway(backend_url)

    async def create_payment(
        self,
        order: Order,
        settings: PaymentSettings,
        *,
        buyer_email: str | None = None,
    ) -> PaymentIntent:
        if settings.provider == "atlos":
            try:
                return await self._atlos.create_payment(
                    order,
                    settings,
                    buyer_email=buyer_email,
                )
            except ValidationError:
                logger.warning("ATLOS invoice failed; using hosted test payment page")
                return await self._simulated.create_payment(
                    order, settings, buyer_email=buyer_email
                )
        return await self._simulated.create_payment(
            order,
            settings,
            buyer_email=buyer_email,
        )

    def verify_signature(self, payload: bytes, signature: str, settings: PaymentSettings) -> bool:
        if settings.provider == "atlos":
            return self._atlos.verify_signature(payload, signature, settings)
        return self._simulated.verify_signature(payload, signature, settings)


def build_payment_gateway(backend_url: str) -> PaymentGateway:
    return RoutingPaymentGateway(backend_url)
