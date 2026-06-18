import json
from html import escape
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from app.api.deps import CatalogServiceDep, OrderServiceDep, SettingsDep
from app.api.schemas.order import OrderCreate, OrderCreatedOut, OrderOut, PaymentOut
from app.api.schemas.lava_webhook import LavaWebhookIn
from app.api.schemas.payment import PaymentWebhookIn

router = APIRouter(prefix="/api", tags=["orders"])


@router.post("/orders", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, service: OrderServiceDep) -> OrderCreatedOut:
    order, intent = await service.create_order(
        telegram_id=payload.telegram_id,
        course_id=payload.course_id,
        username=payload.username,
        full_name=payload.full_name,
    )
    base = OrderOut.from_entity(order)
    return OrderCreatedOut(
        order_id=base.order_id,
        status=base.status,
        amount=base.amount,
        payment=PaymentOut.from_entity(intent),
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, service: OrderServiceDep) -> OrderOut:
    order = await service.get_order(order_id)
    return OrderOut.from_entity(order)


def _checkout_page_html(
    *,
    order_id: int,
    course_name: str,
    category_name: str,
    payment_service: str,
    amount: str,
    currency: str,
    pay_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Оплата замовлення #{order_id}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 32rem; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ font-size: 1.25rem; }}
    dl {{ line-height: 1.6; }}
    dt {{ color: #555; margin-top: 0.5rem; }}
    dd {{ margin: 0 0 0.25rem 0; font-weight: 600; }}
    a.btn {{
      display: inline-block; margin-top: 1.5rem; padding: 0.75rem 1.25rem;
      background: #2481cc; color: #fff; text-decoration: none; border-radius: 8px;
    }}
  </style>
</head>
<body>
  <h1>Замовлення #{order_id}</h1>
  <dl>
    <dt>Товар</dt><dd>{escape(course_name)}</dd>
    <dt>Категорія</dt><dd>{escape(category_name)}</dd>
    <dt>Сервіс оплати</dt><dd>{escape(payment_service)}</dd>
    <dt>Сума</dt><dd>{escape(amount)} {escape(currency)}</dd>
  </dl>
  <a class="btn" href="{escape(pay_url)}">Перейти до оплати</a>
</body>
</html>"""


@router.get("/orders/{order_id}/checkout", response_class=HTMLResponse)
async def order_checkout_page(
    order_id: int,
    service: OrderServiceDep,
    catalog: CatalogServiceDep,
) -> HTMLResponse:
    try:
        order = await service.get_order(order_id)
        pay_url = await service.get_checkout_pay_url(order_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    course = await catalog.get_localized_course(order.course_id, "uk")
    category_name = "—"
    for category in await catalog.list_localized_categories("uk"):
        if category.id == course.category_id:
            category_name = category.name
            break
    payment_service = (
        "lava.top" if await service.uses_lava_provider() else "Тестова оплата"
    )
    html = _checkout_page_html(
        order_id=order_id,
        course_name=course.name,
        category_name=category_name,
        payment_service=payment_service,
        amount=str(order.amount),
        currency=await service.payment_currency(),
        pay_url=pay_url,
    )
    return HTMLResponse(content=html)


@router.post("/payments/lava/webhook")
async def lava_payment_webhook(
    request: Request,
    payload: LavaWebhookIn,
    service: OrderServiceDep,
    x_api_key: Annotated[str, Header(alias="X-Api-Key")] = "",
) -> dict[str, bool]:
    if not await service.verify_lava_webhook(x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    order, applied = await service.confirm_lava_webhook(payload.contract_id, payload.event_type)
    if applied:
        user = await service.get_order_user(order)
        bot_app = getattr(request.app.state, "bot_app", None)
        if order.id is not None and bot_app is not None:
            await bot_app.notify_payment_status(user.telegram_id, order.id, order.status.value)
    return {"ok": True}


@router.post("/payments/webhook")
async def payment_webhook(
    request: Request,
    payload: PaymentWebhookIn,
    service: OrderServiceDep,
    x_signature: Annotated[str, Header()] = "",
) -> dict[str, bool]:
    raw = json.dumps(payload.model_dump(), separators=(",", ":"), sort_keys=True).encode("utf-8")
    if not await service.verify_webhook(raw, x_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    order, applied = await service.confirm_payment(payload.payment_reference, payload.status)
    if applied:
        user = await service.get_order_user(order)
        bot_app = getattr(request.app.state, "bot_app", None)
        if order.id is not None and bot_app is not None:
            await bot_app.notify_payment_status(user.telegram_id, order.id, order.status.value)
    return {"ok": True}


@router.post("/payments/simulate")
async def simulate_payment(
    service: OrderServiceDep,
    settings: SettingsDep,
    reference: Annotated[str, Query()],
    result: Annotated[str, Query()] = "succeeded",
) -> dict[str, bool]:
    if not settings.is_development:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await service.confirm_payment(reference, result)
    return {"ok": True}