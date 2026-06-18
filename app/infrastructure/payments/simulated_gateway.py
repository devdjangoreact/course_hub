import hashlib
import hmac
import uuid

from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.payment_gateway import PaymentGateway


class SimulatedPaymentGateway(PaymentGateway):
    """Phase-1 gateway: issues a reference and a simulate URL; verifies an HMAC signature."""

    def __init__(self, backend_url: str) -> None:
        self._backend_url = backend_url.rstrip("/")

    async def create_payment(
        self,
        order: Order,
        settings: PaymentSettings,
        *,
        lava_offer_id_value: str | None = None,
        buyer_email: str | None = None,
    ) -> PaymentIntent:
        reference = f"sim_{uuid.uuid4().hex}"
        pay_url = (
            f"{self._backend_url}/api/payments/simulate?reference={reference}&result=succeeded"
        )
        instructions = (
            f"Order #{order.id} created for {order.amount} {settings.currency}. "
            "Complete the simulated payment using the provided link."
        )
        return PaymentIntent(
            payment_reference=reference, instructions=instructions, pay_url=pay_url
        )

    def verify_signature(self, payload: bytes, signature: str, settings: PaymentSettings) -> bool:
        secret = (settings.secret_key or "").encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
