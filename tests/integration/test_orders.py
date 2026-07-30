import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.infrastructure.db.repositories.bot_user_repository import SqlBotUserRepository
from app.infrastructure.db.repositories.order_repository import SqlOrderRepository


async def _create_order(client: AsyncClient, course_id: int) -> dict[str, object]:
    response = await client.post(
        "/api/orders",
        json={"telegram_id": 12345, "course_id": course_id, "username": "tester"},
    )
    assert response.status_code == 201
    return response.json()


async def test_create_order(client: AsyncClient, seeded: dict[str, int]) -> None:
    body = await _create_order(client, seeded["course_id"])
    assert body["status"] == "pending"
    assert body["payment"]["payment_reference"].startswith("sim_")


async def test_create_order_unknown_course(client: AsyncClient) -> None:
    response = await client.post("/api/orders", json={"telegram_id": 1, "course_id": 9999})
    assert response.status_code == 404


async def test_get_order(client: AsyncClient, seeded: dict[str, int]) -> None:
    body = await _create_order(client, seeded["course_id"])
    response = await client.get(f"/api/orders/{body['order_id']}")
    assert response.status_code == 200
    assert response.json()["order_id"] == body["order_id"]


async def test_simulate_payment_marks_paid(
    app: FastAPI, client: AsyncClient, seeded: dict[str, int]
) -> None:
    notifications: list[tuple[int, int, str]] = []

    class FakeBotApp:
        async def notify_payment_status(self, telegram_id: int, order_id: int, status: str) -> None:
            notifications.append((telegram_id, order_id, status))

    app.state.bot_app = FakeBotApp()
    body = await _create_order(client, seeded["course_id"])
    reference = body["payment"]["payment_reference"]

    paid = await client.post(
        "/api/payments/simulate", params={"reference": reference, "result": "succeeded"}
    )
    assert paid.status_code == 200

    order = await client.get(f"/api/orders/{body['order_id']}")
    assert order.json()["status"] == "paid"
    assert notifications == [(12345, body["order_id"], "paid")]


async def test_paid_order_grants_course_access(
    app: FastAPI, client: AsyncClient, seeded: dict[str, int]
) -> None:
    body = await _create_order(client, seeded["course_id"])
    reference = body["payment"]["payment_reference"]
    await client.post(
        "/api/payments/simulate", params={"reference": reference, "result": "succeeded"}
    )

    async with app.state.db.session_factory() as session:
        user = await SqlBotUserRepository(session).get_by_telegram_id(12345)
        assert user is not None
        assert user.id is not None
        assert await SqlOrderRepository(session).has_paid_course(user.id, seeded["course_id"])


@pytest.mark.parametrize(
    ("result", "expected_status"),
    [("failed", "failed"), ("cancelled", "cancelled")],
)
async def test_unsuccessful_payment_does_not_grant_course_access(
    app: FastAPI,
    client: AsyncClient,
    seeded: dict[str, int],
    result: str,
    expected_status: str,
) -> None:
    body = await _create_order(client, seeded["course_id"])
    reference = body["payment"]["payment_reference"]

    response = await client.post(
        "/api/payments/simulate", params={"reference": reference, "result": result}
    )

    assert response.status_code == 200
    order = await client.get(f"/api/orders/{body['order_id']}")
    assert order.json()["status"] == expected_status
    async with app.state.db.session_factory() as session:
        user = await SqlBotUserRepository(session).get_by_telegram_id(12345)
        assert user is not None
        assert user.id is not None
        assert not await SqlOrderRepository(session).has_paid_course(user.id, seeded["course_id"])


async def test_simulate_payment_idempotent(client: AsyncClient, seeded: dict[str, int]) -> None:
    body = await _create_order(client, seeded["course_id"])
    reference = body["payment"]["payment_reference"]

    first = await client.post(
        "/api/payments/simulate", params={"reference": reference, "result": "succeeded"}
    )
    second = await client.post(
        "/api/payments/simulate", params={"reference": reference, "result": "failed"}
    )
    assert first.status_code == 200
    assert second.status_code == 200

    order = await client.get(f"/api/orders/{body['order_id']}")
    assert order.json()["status"] == "paid"
