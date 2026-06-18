import hmac

from app.application.errors import NotFoundError, ValidationError
from app.domain.entities.bot_user import BotUser
from app.domain.entities.order import Order
from app.domain.entities.order_status import OrderStatus
from app.domain.entities.payment_intent import PaymentIntent
from app.domain.entities.payment_settings import PaymentSettings
from app.domain.repositories.bot_user_repository import BotUserRepository
from app.domain.repositories.course_repository import CourseRepository
from app.domain.repositories.order_repository import OrderRepository
from app.domain.repositories.payment_gateway import PaymentGateway
from app.domain.repositories.payment_settings_repository import PaymentSettingsRepository
from app.infrastructure.payments.lava_helpers import lava_offer_id, payment_email

_RESULT_TO_STATUS: dict[str, OrderStatus] = {
    "succeeded": OrderStatus.PAID,
    "failed": OrderStatus.FAILED,
    "cancelled": OrderStatus.CANCELLED,
}

_LAVA_EVENT_TO_RESULT: dict[str, str] = {
    "payment.success": "succeeded",
    "payment.failed": "failed",
    "payment.cancelled": "cancelled",
}


class OrderService:
    def __init__(
        self,
        bot_users: BotUserRepository,
        courses: CourseRepository,
        orders: OrderRepository,
        payment_gateway: PaymentGateway,
        payment_settings: PaymentSettingsRepository,
    ) -> None:
        self._bot_users = bot_users
        self._courses = courses
        self._orders = orders
        self._gateway = payment_gateway
        self._payment_settings = payment_settings

    async def _settings(self) -> PaymentSettings:
        settings = await self._payment_settings.get()
        if settings is None:
            return PaymentSettings(id=None, provider="simulated")
        return settings

    async def create_order(
        self,
        telegram_id: int,
        course_id: int,
        username: str | None = None,
        full_name: str | None = None,
    ) -> tuple[Order, PaymentIntent]:
        existing_user = await self._bot_users.get_by_telegram_id(telegram_id)
        user = await self._bot_users.upsert(
            BotUser(
                id=existing_user.id if existing_user else None,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                preferred_language=existing_user.preferred_language if existing_user else "uk",
                extra=existing_user.extra if existing_user else {},
            )
        )
        course = await self._courses.get_active(course_id)
        if course is None:
            raise NotFoundError("Course not found")
        assert user.id is not None
        settings = await self._settings()
        offer_id: str | None = None
        buyer_email: str | None = None
        if settings.provider == "lava":
            offer_id = lava_offer_id(course.extra)
            if offer_id is None:
                raise ValidationError("Course is not configured for lava payments")
            buyer_email = payment_email(user.extra)
            if buyer_email is None:
                raise ValidationError("Buyer email is required for lava payments")
        order = await self._orders.add(
            Order(
                id=None,
                bot_user_id=user.id,
                course_id=course_id,
                amount=course.price,
                status=OrderStatus.PENDING,
            )
        )
        intent = await self._gateway.create_payment(
            order,
            settings,
            lava_offer_id_value=offer_id,
            buyer_email=buyer_email,
        )
        order.payment_reference = intent.payment_reference
        if intent.pay_url:
            order.extra = {**order.extra, "pay_url": intent.pay_url}
        order = await self._orders.update(order)
        return order, intent

    async def get_checkout_pay_url(self, order_id: int) -> str:
        order = await self.get_order(order_id)
        if order.status.is_terminal:
            raise ValidationError("Order is already finalized")
        pay_url = order.extra.get("pay_url")
        if not isinstance(pay_url, str) or not pay_url.strip():
            raise NotFoundError("Payment link not found")
        return pay_url.strip()

    async def get_order(self, order_id: int) -> Order:
        order = await self._orders.get(order_id)
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def get_order_user(self, order: Order) -> BotUser:
        user = await self._bot_users.get(order.bot_user_id)
        if user is None:
            raise NotFoundError("Order user not found")
        return user

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return self._gateway.verify_signature(payload, signature, await self._settings())

    async def verify_lava_webhook(self, api_key: str) -> bool:
        settings = await self._settings()
        secret = settings.secret_key or ""
        if not secret or not api_key:
            return False
        return hmac.compare_digest(api_key, secret)

    async def confirm_lava_webhook(
        self, payment_reference: str, event_type: str
    ) -> tuple[Order, bool]:
        result = _LAVA_EVENT_TO_RESULT.get(event_type)
        if result is None:
            raise ValidationError("Unknown lava event type")
        return await self.confirm_payment(payment_reference, result)

    async def uses_lava_provider(self) -> bool:
        settings = await self._settings()
        return settings.provider == "lava"

    async def payment_currency(self) -> str:
        return (await self._settings()).currency

    async def payment_link_mode(self) -> str:
        mode = str((await self._settings()).extra.get("checkout_mode", "direct"))
        return mode if mode in ("direct", "checkout") else "direct"

    async def confirm_payment(self, payment_reference: str, result: str) -> tuple[Order, bool]:
        status = _RESULT_TO_STATUS.get(result)
        if status is None:
            raise ValidationError("Unknown payment result")
        order = await self._orders.get_by_payment_reference(payment_reference)
        if order is None:
            raise NotFoundError("Order not found")
        if order.status.is_terminal:
            return order, False
        order.status = status
        return await self._orders.update(order), True
