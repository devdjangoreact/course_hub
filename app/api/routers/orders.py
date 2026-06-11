import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from app.api.deps import OrderServiceDep, SettingsDep
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
    order = await service.confirm_payment(payload.payment_reference, payload.status)
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
