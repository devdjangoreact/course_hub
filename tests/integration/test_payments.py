import hashlib
import hmac
import json

from httpx import AsyncClient

_SECRET = b"testsecret"


def _sign(payload: dict[str, str]) -> tuple[str, str]:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(_SECRET, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return raw, signature


async def _create_order(client: AsyncClient, course_id: int) -> dict[str, object]:
    response = await client.post("/api/orders", json={"telegram_id": 999, "course_id": course_id})
    assert response.status_code == 201
    return response.json()


async def test_webhook_valid_signature_marks_paid(
    client: AsyncClient, seeded: dict[str, int]
) -> None:
    body = await _create_order(client, seeded["course_id"])
    payload = {"payment_reference": body["payment"]["payment_reference"], "status": "succeeded"}
    raw, signature = _sign(payload)

    response = await client.post(
        "/api/payments/webhook",
        content=raw,
        headers={"X-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200

    order = await client.get(f"/api/orders/{body['order_id']}")
    assert order.json()["status"] == "paid"


async def test_webhook_invalid_signature_rejected(
    client: AsyncClient, seeded: dict[str, int]
) -> None:
    body = await _create_order(client, seeded["course_id"])
    payload = {"payment_reference": body["payment"]["payment_reference"], "status": "succeeded"}
    raw, _ = _sign(payload)

    response = await client.post(
        "/api/payments/webhook",
        content=raw,
        headers={"X-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert response.status_code == 401


async def test_webhook_idempotent(client: AsyncClient, seeded: dict[str, int]) -> None:
    body = await _create_order(client, seeded["course_id"])
    payload = {"payment_reference": body["payment"]["payment_reference"], "status": "succeeded"}
    raw, signature = _sign(payload)
    headers = {"X-Signature": signature, "Content-Type": "application/json"}

    first = await client.post("/api/payments/webhook", content=raw, headers=headers)
    second = await client.post("/api/payments/webhook", content=raw, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    order = await client.get(f"/api/orders/{body['order_id']}")
    assert order.json()["status"] == "paid"
