from decimal import Decimal

from httpx import AsyncClient

from app.domain.entities.bot_user import BotUser
from app.domain.entities.order import Order
from app.domain.entities.order_status import OrderStatus
from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository
from app.infrastructure.db.repositories.order_repository import SqlOrderRepository
from app.infrastructure.settings_store.payment_settings_repository import (
    SqlPaymentSettingsRepository,
)
from app.domain.entities.payment_settings import PaymentSettings


async def _seed_lava_order(app, course_id: int, payment_reference: str) -> int:
    database = app.state.db
    async with database.session_factory() as session:
        users = SqlBotUserRepository(session)
        user = await users.upsert(
            BotUser(id=None, telegram_id=4242, username="lava", full_name="Lava Tester")
        )
        assert user.id is not None
        orders = SqlOrderRepository(session)
        order = await orders.add(
            Order(
                id=None,
                bot_user_id=user.id,
                course_id=course_id,
                amount=Decimal("79.00"),
                status=OrderStatus.PENDING,
                payment_reference=payment_reference,
            )
        )
        payment_settings = SqlPaymentSettingsRepository(session)
        current = await payment_settings.get()
        if current is not None:
            await payment_settings.save(
                PaymentSettings(
                    id=current.id,
                    provider="lava",
                    api_key=current.api_key,
                    secret_key="testsecret",
                    currency=current.currency,
                    extra=current.extra,
                )
            )
        await session.commit()
        assert order.id is not None
        return order.id


async def test_lava_webhook_valid_key_marks_paid(
    client: AsyncClient, app, seeded: dict[str, int]
) -> None:
    reference = "lava-contract-abc"
    order_id = await _seed_lava_order(app, seeded["course_id"], reference)

    response = await client.post(
        "/api/payments/lava/webhook",
        json={"eventType": "payment.success", "contractId": reference},
        headers={"X-Api-Key": "testsecret"},
    )
    assert response.status_code == 200

    order = await client.get(f"/api/orders/{order_id}")
    assert order.json()["status"] == "paid"


async def test_lava_webhook_invalid_key_rejected(
    client: AsyncClient, app, seeded: dict[str, int]
) -> None:
    reference = "lava-contract-denied"
    await _seed_lava_order(app, seeded["course_id"], reference)

    response = await client.post(
        "/api/payments/lava/webhook",
        json={"eventType": "payment.success", "contractId": reference},
        headers={"X-Api-Key": "wrong-key"},
    )
    assert response.status_code == 401


async def test_lava_webhook_idempotent(client: AsyncClient, app, seeded: dict[str, int]) -> None:
    reference = "lava-contract-idem"
    order_id = await _seed_lava_order(app, seeded["course_id"], reference)
    payload = {"eventType": "payment.success", "contractId": reference}
    headers = {"X-Api-Key": "testsecret"}

    first = await client.post("/api/payments/lava/webhook", json=payload, headers=headers)
    second = await client.post("/api/payments/lava/webhook", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    order = await client.get(f"/api/orders/{order_id}")
    assert order.json()["status"] == "paid"
