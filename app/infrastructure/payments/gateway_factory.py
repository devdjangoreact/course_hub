from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.payment_gateway import PaymentGateway
from app.infrastructure.payments.lava_gateway import LavaPaymentGateway
from app.infrastructure.payments.simulated_gateway import SimulatedPaymentGateway


class RoutingPaymentGateway(PaymentGateway):
    """Delegates to simulated or lava based on persisted payment settings."""

    def __init__(self, backend_url: str) -> None:
        self._simulated = SimulatedPaymentGateway(backend_url)
        self._lava = LavaPaymentGateway()

    async def create_payment(
        self,
        order: Order,
        settings: PaymentSettings,
        *,
        lava_offer_id_value: str | None = None,
        buyer_email: str | None = None,
    ) -> PaymentIntent:
        if settings.provider == "lava":
            return await self._lava.create_payment(
                order,
                settings,
                lava_offer_id_value=lava_offer_id_value,
                buyer_email=buyer_email,
            )
        return await self._simulated.create_payment(
            order,
            settings,
            lava_offer_id_value=lava_offer_id_value,
            buyer_email=buyer_email,
        )

    def verify_signature(
        self, payload: bytes, signature: str, settings: PaymentSettings
    ) -> bool:
        return self._simulated.verify_signature(payload, signature, settings)


def build_payment_gateway(backend_url: str) -> PaymentGateway:
    return RoutingPaymentGateway(backend_url)
