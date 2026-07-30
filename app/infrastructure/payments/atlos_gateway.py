import base64
import hashlib
import hmac
import uuid

import httpx
from loguru import logger

from app.application.errors import ValidationError
from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.payment_gateway import PaymentGateway


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
            raise ValidationError("ATLOS merchant ID is not configured")
        if not settings.secret_key:
            raise ValidationError("ATLOS API secret is not configured")

        payment_reference = f"atlos-{order.id}-{uuid.uuid4().hex[:8]}"
        request_data: dict[str, object] = {
            "MerchantId": settings.api_key,
            "OrderId": payment_reference,
            "OrderAmount": float(order.amount),
            "OrderCurrency": settings.currency,
            "Memo": f"Course Hub order #{order.id}",
            "SendEmail": False,
        }
        if buyer_email:
            request_data["UserEmail"] = buyer_email

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.atlos.io/gateway/rest/Invoice/Create",
                    headers={"ApiSecret": settings.secret_key},
                    json=request_data,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.opt(exception=exc).error("ATLOS invoice creation failed")
            raise ValidationError("Payment provider is temporarily unavailable") from exc

        invoice_id = data.get("Id") if isinstance(data, dict) else None
        pay_url = data.get("PaymentLink") if isinstance(data, dict) else None
        if not isinstance(invoice_id, str) or not isinstance(pay_url, str):
            raise ValidationError("Payment provider returned an incomplete response")

        logger.info(
            "Created ATLOS invoice {} for order {} with reference {}",
            invoice_id,
            order.id,
            payment_reference,
        )

        return PaymentIntent(
            payment_reference=payment_reference,
            instructions=f"Complete the payment using ATLOS. Order #{order.id}",
            pay_url=pay_url,
        )

    def verify_signature(self, payload: bytes, signature: str, settings: PaymentSettings) -> bool:
        secret = settings.secret_key or ""
        if not secret or not signature:
            return False
        expected = base64.b64encode(
            hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)
