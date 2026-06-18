import asyncio
import hmac

from loguru import logger

from app.application.errors import ValidationError
from app.domain.entities.order import Order
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.payment_gateway import PaymentGateway
from app.infrastructure.payments.lava_helpers import lava_offer_id


class LavaPaymentGateway(PaymentGateway):
    """Creates lava.top one-time payments and validates webhook API keys."""

    async def create_payment(
        self,
        order: Order,
        settings: PaymentSettings,
        *,
        lava_offer_id_value: str | None = None,
        buyer_email: str | None = None,
    ) -> PaymentIntent:
        if not settings.api_key:
            raise ValidationError("Lava payment API key is not configured")
        if not lava_offer_id_value:
            raise ValidationError("Course is not configured for lava payments")
        if not buyer_email:
            raise ValidationError("Buyer email is required for lava payments")

        payment = await asyncio.to_thread(
            _create_lava_payment,
            api_key=settings.api_key,
            lava_env=str(settings.extra.get("lava_env", "production")),
            email=buyer_email,
            offer_id=lava_offer_id_value,
            currency=settings.currency,
            payment_method=str(settings.extra.get("payment_method", "")).strip() or None,
        )

        instructions = (
            f"Order #{order.id} — complete payment for {order.amount} {settings.currency} "
            "using the link below."
        )
        return PaymentIntent(
            payment_reference=payment["id"],
            instructions=instructions,
            pay_url=payment["payment_url"],
        )

    def verify_signature(
        self, payload: bytes, signature: str, settings: PaymentSettings
    ) -> bool:
        secret = settings.secret_key or ""
        if not secret or not signature:
            return False
        return hmac.compare_digest(signature, secret)


def _create_lava_payment(
    *,
    api_key: str,
    lava_env: str,
    email: str,
    offer_id: str,
    currency: str,
    payment_method: str | None,
) -> dict[str, str]:
    from lava_top_sdk import Currency, LavaClient, LavaClientConfig, PaymentMethod

    try:
        parsed_currency = Currency[currency.upper()]
    except KeyError as exc:
        raise ValidationError(f"Unsupported lava currency: {currency}") from exc

    config = LavaClientConfig(api_key=api_key, env=lava_env)
    client = LavaClient(config)

    kwargs: dict[str, object] = {
        "email": email,
        "offer_id": offer_id,
        "currency": parsed_currency,
    }
    if payment_method:
        try:
            kwargs["payment_method"] = PaymentMethod[payment_method.upper()]
        except KeyError as exc:
            raise ValidationError(f"Unsupported lava payment method: {payment_method}") from exc

    try:
        payment = client.create_one_time_payment(**kwargs)
    except Exception as exc:
        logger.error("Lava payment creation failed", exc_info=exc)
        raise ValidationError("Payment provider is temporarily unavailable") from exc

    payment_id = str(getattr(payment, "id", "") or "")
    payment_url = str(getattr(payment, "paymentUrl", "") or getattr(payment, "payment_url", ""))
    if not payment_id or not payment_url:
        raise ValidationError("Payment provider returned an incomplete response")

    return {"id": payment_id, "payment_url": payment_url}
