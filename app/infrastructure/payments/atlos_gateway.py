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
from app.infrastructure.payments.setup import atlos_postback_url


class AtlosPaymentGateway(PaymentGateway):
    """Creates Atlos one-time payments."""

    def __init__(self, backend_url: str = "") -> None:
        self._backend_url = backend_url.rstrip("/")

    async def create_payment(
        self,
        order: Order,
        settings: PaymentSettings,
        *,
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
        if self._backend_url:
            postback = atlos_postback_url(self._backend_url)
            if postback:
                request_data["PostbackUrl"] = postback

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.atlos.io/gateway/rest/Invoice/Create",
                    headers={"ApiSecret": settings.secret_key},
                    json=request_data,
                )
                if response.status_code >= 400:
                    logger.error(
                        "ATLOS invoice HTTP {} body={}",
                        response.status_code,
                        response.text[:500],
                    )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.opt(exception=exc).error("ATLOS invoice creation failed")
            raise ValidationError("Payment provider is temporarily unavailable") from exc

        payload = data if isinstance(data, dict) else {}
        invoice_id = payload.get("Id")
        pay_url = payload.get("PaymentLink")
        if invoice_id is not None:
            invoice_id = str(invoice_id)
        if not invoice_id or not isinstance(pay_url, str) or not pay_url.strip():
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
