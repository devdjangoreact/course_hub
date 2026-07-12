import uuid
import logging

from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.exceptions import ValidationError
from app.domain.repositories.payment_gateway import PaymentGateway

logger = logging.getLogger(__name__)

class AtlosPaymentGateway(PaymentGateway):
    """Creates Atlos one-time payments."""

    async def create_payment(
        self,
        order: Order,
        settings: PaymentSettings,
        *,
        lava_offer_id_value: str | None = None,
        buyer_email: str | None = None,
    ) -> PaymentIntent:
        if not settings.api_key:
            raise ValidationError("Atlos payment API key is not configured")

        payment_reference = f"atlos-{order.id}-{uuid.uuid4().hex[:8]}"
        
        # Placeholder for actual Atlos API call
        pay_url = f"https://atlos.io/pay/{payment_reference}"
        
        logger.info(f"Created Atlos payment intent for order {order.id}: {payment_reference}")

        return PaymentIntent(
            payment_reference=payment_reference,
            instructions=f"Complete the payment using Atlos. Order #{order.id}",
            pay_url=pay_url,
        )

    def verify_signature(
        self, payload: bytes, signature: str, settings: PaymentSettings
    ) -> bool:
        # TODO: Implement actual Atlos signature verification
        return True
