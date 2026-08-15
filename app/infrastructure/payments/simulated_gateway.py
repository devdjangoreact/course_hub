import hashlib
import hmac
import uuid

from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.payment_gateway import PaymentGateway


def simulate_pay_signature(secret: str, reference: str) -> str:
    return hmac.new(
        (secret or "simulated").encode(),
        f"simulate-pay:{reference}".encode(),
        hashlib.sha256,
    ).hexdigest()


def simulate_pay_url(backend_url: str, secret: str, reference: str) -> str:
    sig = simulate_pay_signature(secret, reference)
    return f"{backend_url.rstrip('/')}/api/payments/simulate/pay?reference={reference}&sig={sig}"


class SimulatedPaymentGateway(PaymentGateway):
    """Issues a hosted test-pay page (same UX as Atlos: HTTPS GET, then Pay)."""

    def __init__(self, backend_url: str) -> None:
        self._backend_url = backend_url.rstrip("/")

    async def create_payment(
        self,
        order: Order,
        settings: PaymentSettings,
        *,
        buyer_email: str | None = None,
    ) -> PaymentIntent:
        del buyer_email
        reference = f"sim_{uuid.uuid4().hex}"
        pay_url = simulate_pay_url(self._backend_url, settings.secret_key or "", reference)
        instructions = (
            f"Order #{order.id} created for {order.amount} {settings.currency}. "
            "Complete the test payment using the provided link."
        )
        return PaymentIntent(
            payment_reference=reference, instructions=instructions, pay_url=pay_url
        )

    def verify_signature(self, payload: bytes, signature: str, settings: PaymentSettings) -> bool:
        secret = (settings.secret_key or "").encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
