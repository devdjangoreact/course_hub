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

_RESULT_TO_STATUS: dict[str, OrderStatus] = {
    "succeeded": OrderStatus.PAID,
    "failed": OrderStatus.FAILED,
    "cancelled": OrderStatus.CANCELLED,
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
        bot_id: int | None = None,
        channel_id: int | None = None,
    ) -> tuple[Order, PaymentIntent]:
        existing_user = await self._bot_users.get_by_telegram_id(telegram_id)
        user = await self._bot_users.upsert(
            BotUser(
                id=existing_user.id if existing_user else None,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                preferred_language=existing_user.preferred_language if existing_user else "ru",
                extra=existing_user.extra if existing_user else {},
            )
        )
        course = await self._courses.get_active(course_id)
        if course is None:
            raise NotFoundError("Course not found")
        assert user.id is not None
        settings = await self._settings()
        raw_email = user.extra.get("payment_email")
        buyer_email = raw_email.strip() if isinstance(raw_email, str) and raw_email.strip() else None
        order = await self._orders.add(
            Order(
                id=None,
                bot_user_id=user.id,
                course_id=course_id,
                amount=course.price,
                status=OrderStatus.PENDING,
                bot_id=bot_id,
                channel_id=channel_id,
            )
        )
        intent = await self._gateway.create_payment(
            order,
            settings,
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

    async def has_paid_course(self, telegram_id: int, course_id: int) -> bool:
        user = await self._bot_users.get_by_telegram_id(telegram_id)
        if user is None or user.id is None:
            return False
        return await self._orders.has_paid_course(user.id, course_id)

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return self._gateway.verify_signature(payload, signature, await self._settings())

    async def uses_atlos_provider(self) -> bool:
        settings = await self._settings()
        return settings.provider == "atlos"

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

    async def get_order_by_payment_reference(self, payment_reference: str) -> Order:
        order = await self._orders.get_by_payment_reference(payment_reference)
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def verify_simulate_pay(self, reference: str, sig: str) -> Order:
        from app.infrastructure.payments.simulated_gateway import simulate_pay_signature

        settings = await self._settings()
        expected = simulate_pay_signature(settings.secret_key or "", reference)
        if not sig or not hmac.compare_digest(expected, sig):
            raise NotFoundError("Order not found")
        return await self.get_order_by_payment_reference(reference)
