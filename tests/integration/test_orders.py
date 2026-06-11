from httpx import AsyncClient


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


async def test_simulate_payment_marks_paid(client: AsyncClient, seeded: dict[str, int]) -> None:
    body = await _create_order(client, seeded["course_id"])
    reference = body["payment"]["payment_reference"]

    paid = await client.post(
        "/api/payments/simulate", params={"reference": reference, "result": "succeeded"}
    )
    assert paid.status_code == 200

    order = await client.get(f"/api/orders/{body['order_id']}")
    assert order.json()["status"] == "paid"


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
