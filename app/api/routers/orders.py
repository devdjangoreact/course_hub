import json
from html import escape
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from app.api.deps import CatalogServiceDep, OrderServiceDep, SettingsDep
from app.application.errors import NotFoundError
from app.api.schemas.atlos_webhook import AtlosWebhookIn
from app.api.schemas.order import OrderCreate, OrderCreatedOut, OrderOut, PaymentOut
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
        "atlos.io" if await service.uses_atlos_provider() else "Тестова оплата"
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


@router.post("/payments/atlos/webhook")
async def atlos_payment_webhook(
    request: Request,
    payload: AtlosWebhookIn,
    service: OrderServiceDep,
    signature: Annotated[str, Header(alias="Signature")] = "",
) -> dict[str, bool]:
    if not await service.verify_webhook(await request.body(), signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    if payload.status != 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown status"
        )
    order, applied = await service.confirm_payment(payload.order_id, "succeeded")
    if applied:
        user = await service.get_order_user(order)
        bot_app = getattr(request.app.state, "bot_app", None)
        if order.id is not None and bot_app is not None:
            await bot_app.notify_payment_status(
                user.telegram_id, order.id, order.status.value, bot_id=order.bot_id
            )
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
            await bot_app.notify_payment_status(
                user.telegram_id, order.id, order.status.value, bot_id=order.bot_id
            )
    return {"ok": True}


def _simulate_pay_page_html(
    *,
    order_id: int,
    amount: str,
    currency: str,
    reference: str,
    sig: str,
    paid: bool,
) -> str:
    if paid:
        body = f"<h1>Замовлення #{order_id}</h1><p>Оплату підтверджено.</p>"
    else:
        body = f"""
  <h1>Замовлення #{order_id}</h1>
  <dl>
    <dt>Сервіс оплати</dt><dd>Тестова оплата</dd>
    <dt>Сума</dt><dd>{escape(amount)} {escape(currency)}</dd>
  </dl>
  <form method="post" action="/api/payments/simulate/pay?reference={escape(reference)}&amp;sig={escape(sig)}">
    <button class="btn" type="submit">Оплатити</button>
  </form>"""
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
    button.btn, a.btn {{
      display: inline-block; margin-top: 1.5rem; padding: 0.75rem 1.25rem;
      background: #2481cc; color: #fff; text-decoration: none; border-radius: 8px; border: 0;
      font-size: 1rem; cursor: pointer;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


async def _simulate_pay_response(
    request: Request,
    service: OrderServiceDep,
    reference: str,
    sig: str,
    *,
    confirm: bool,
) -> HTMLResponse:
    try:
        order = await service.verify_simulate_pay(reference, sig)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    paid = order.status.is_terminal
    if confirm and not paid:
        order, applied = await service.confirm_payment(reference, "succeeded")
        paid = True
        if applied:
            user = await service.get_order_user(order)
            bot_app = getattr(request.app.state, "bot_app", None)
            if order.id is not None and bot_app is not None:
                await bot_app.notify_payment_status(
                    user.telegram_id, order.id, order.status.value, bot_id=order.bot_id
                )
    assert order.id is not None
    html = _simulate_pay_page_html(
        order_id=order.id,
        amount=str(order.amount),
        currency=await service.payment_currency(),
        reference=reference,
        sig=sig,
        paid=paid,
    )
    return HTMLResponse(content=html)


@router.get("/payments/simulate/pay", response_class=HTMLResponse)
async def simulate_pay_page(
    request: Request,
    service: OrderServiceDep,
    reference: Annotated[str, Query()],
    sig: Annotated[str, Query()] = "",
) -> HTMLResponse:
    return await _simulate_pay_response(request, service, reference, sig, confirm=False)


@router.post("/payments/simulate/pay", response_class=HTMLResponse)
async def simulate_pay_confirm(
    request: Request,
    service: OrderServiceDep,
    reference: Annotated[str, Query()],
    sig: Annotated[str, Query()] = "",
) -> HTMLResponse:
    return await _simulate_pay_response(request, service, reference, sig, confirm=True)


@router.post("/payments/simulate")
async def simulate_payment(
    request: Request,
    service: OrderServiceDep,
    settings: SettingsDep,
    reference: Annotated[str, Query()],
    result: Annotated[str, Query()] = "succeeded",
) -> dict[str, bool]:
    if not settings.is_development:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    order, applied = await service.confirm_payment(reference, result)
    if applied:
        user = await service.get_order_user(order)
        bot_app = getattr(request.app.state, "bot_app", None)
        if order.id is not None and bot_app is not None:
            await bot_app.notify_payment_status(
                user.telegram_id, order.id, order.status.value, bot_id=order.bot_id
            )
    return {"ok": True}
