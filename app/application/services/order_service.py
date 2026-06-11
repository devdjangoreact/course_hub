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
    ) -> tuple[Order, PaymentIntent]:
        existing_user = await self._bot_users.get_by_telegram_id(telegram_id)
        user = await self._bot_users.upsert(
            BotUser(
                id=existing_user.id if existing_user else None,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                preferred_language=existing_user.preferred_language if existing_user else "uk",
            )
        )
        course = await self._courses.get_active(course_id)
        if course is None:
            raise NotFoundError("Course not found")
        assert user.id is not None
        order = await self._orders.add(
            Order(
                id=None,
                bot_user_id=user.id,
                course_id=course_id,
                amount=course.price,
                status=OrderStatus.PENDING,
            )
        )
        intent = await self._gateway.create_payment(order, await self._settings())
        order.payment_reference = intent.payment_reference
        order = await self._orders.update(order)
        return order, intent

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

    async def confirm_payment(self, payment_reference: str, result: str) -> Order:
        status = _RESULT_TO_STATUS.get(result)
        if status is None:
            raise ValidationError("Unknown payment result")
        order = await self._orders.get_by_payment_reference(payment_reference)
        if order is None:
            raise NotFoundError("Order not found")
        if order.status.is_terminal:
            return order
        order.status = status
        return await self._orders.update(order)
