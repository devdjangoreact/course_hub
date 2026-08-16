import base64
import hashlib
import hmac
import json
from decimal import Decimal

from httpx import AsyncClient

from app.domain.entities.order import Order
from app.domain.entities.order_status import OrderStatus
from app.domain.entities.payment_settings import PaymentSettings
from app.infrastructure.db.repositories.order_repository import SqlOrderRepository
from app.infrastructure.payments.atlos_gateway import AtlosPaymentGateway
from app.infrastructure.settings_store.payment_settings_repository import (
    SqlPaymentSettingsRepository,
)


def _atlos_sign(secret: str, raw: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()


class _InvoiceResponse:
    status_code = 200
    text = ""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"Id": "inv1", "PaymentLink": "https://atlos.io/payment/inv1"}


class _FakeAtlosClient:
    last: dict[str, object] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    async def __aenter__(self) -> "_FakeAtlosClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    async def post(self, url: str, headers: dict[str, str] | None = None, json: dict | None = None):
        type(self).last = {"url": url, "headers": headers or {}, "json": json or {}}
        return _InvoiceResponse()


async def _enable_atlos(app, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.payments.atlos_gateway.httpx.AsyncClient", _FakeAtlosClient
    )
    async with app.state.db.session_factory() as session:
        payment_settings = SqlPaymentSettingsRepository(session)
        current = await payment_settings.get()
        assert current is not None
        await payment_settings.save(
            PaymentSettings(
                id=current.id,
                provider="atlos",
                api_key="merchant-id",
                secret_key="atlos-secret",
                currency=current.currency,
                extra=current.extra,
            )
        )
        await session.commit()


async def test_atlos_create_payment_sends_postback_and_returns_link() -> None:
    gateway = AtlosPaymentGateway("https://hub.example")
    captured: dict[str, object] = {}

    class Client(_FakeAtlosClient):
        async def post(
            self, url: str, headers: dict[str, str] | None = None, json: dict | None = None
        ):
            captured.update({"url": url, "headers": headers or {}, "json": json or {}})
            return _InvoiceResponse()

    import app.infrastructure.payments.atlos_gateway as module

    original = module.httpx.AsyncClient
    module.httpx.AsyncClient = Client  # type: ignore[misc, assignment]
    try:
        intent = await gateway.create_payment(
            Order(
                id=3,
                bot_user_id=1,
                course_id=1,
                amount=Decimal("79.00"),
                status=OrderStatus.PENDING,
            ),
            PaymentSettings(
                id=1, provider="atlos", api_key="mid", secret_key="sec", currency="USD"
            ),
        )
    finally:
        module.httpx.AsyncClient = original  # type: ignore[misc]

    assert intent.pay_url == "https://atlos.io/payment/inv1"
    assert captured["url"] == "https://api.atlos.io/gateway/rest/Invoice/Create"
    assert captured["headers"] == {"ApiSecret": "sec"}
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["MerchantId"] == "mid"
    assert body["PostbackUrl"] == "https://hub.example/api/payments/atlos/webhook"
    assert intent.payment_reference.startswith("atlos-3-")


async def test_atlos_order_and_webhook_marks_paid(
    client: AsyncClient, app, seeded: dict[str, int], monkeypatch
) -> None:
    await _enable_atlos(app, monkeypatch)
    created = await client.post(
        "/api/orders", json={"telegram_id": 9001, "course_id": seeded["course_id"]}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["payment"]["pay_url"] == "https://atlos.io/payment/inv1"
    reference = body["payment"]["payment_reference"]
    assert str(reference).startswith("atlos-")

    raw = json.dumps({"OrderId": reference, "Status": 100}, separators=(",", ":")).encode()
    response = await client.post(
        "/api/payments/atlos/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "Signature": _atlos_sign("atlos-secret", raw)},
    )
    assert response.status_code == 200
    order = await client.get(f"/api/orders/{body['order_id']}")
    assert order.json()["status"] == "paid"


async def test_atlos_webhook_invalid_signature_rejected(
    client: AsyncClient, app, seeded: dict[str, int], monkeypatch
) -> None:
    await _enable_atlos(app, monkeypatch)
    created = await client.post(
        "/api/orders", json={"telegram_id": 9002, "course_id": seeded["course_id"]}
    )
    reference = created.json()["payment"]["payment_reference"]
    raw = json.dumps({"OrderId": reference, "Status": 100}).encode()
    response = await client.post(
        "/api/payments/atlos/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "Signature": "nope"},
    )
    assert response.status_code == 401


async def test_atlos_webhook_idempotent(
    client: AsyncClient, app, seeded: dict[str, int], monkeypatch
) -> None:
    await _enable_atlos(app, monkeypatch)
    created = await client.post(
        "/api/orders", json={"telegram_id": 9003, "course_id": seeded["course_id"]}
    )
    body = created.json()
    raw = json.dumps(
        {"OrderId": body["payment"]["payment_reference"], "Status": 100},
        separators=(",", ":"),
    ).encode()
    headers = {"Content-Type": "application/json", "Signature": _atlos_sign("atlos-secret", raw)}
    first = await client.post("/api/payments/atlos/webhook", content=raw, headers=headers)
    second = await client.post("/api/payments/atlos/webhook", content=raw, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    async with app.state.db.session_factory() as session:
        order = await SqlOrderRepository(session).get(body["order_id"])
        assert order is not None
        assert order.status == OrderStatus.PAID


async def test_atlos_failure_does_not_use_simulated_pay_page(
    client: AsyncClient, app, seeded: dict[str, int], monkeypatch
) -> None:
    import httpx

    class Boom:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        async def __aenter__(self) -> "Boom":
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def post(self, *args: object, **kwargs: object):
            del args, kwargs
            raise httpx.ConnectError("atlos down")

    await _enable_atlos(app, monkeypatch)
    monkeypatch.setattr("app.infrastructure.payments.atlos_gateway.httpx.AsyncClient", Boom)
    created = await client.post(
        "/api/orders", json={"telegram_id": 9010, "course_id": seeded["course_id"]}
    )
    assert created.status_code == 422
    assert "simulate" not in str(created.json()).lower()
