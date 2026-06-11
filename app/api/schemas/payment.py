from pydantic import BaseModel


class PaymentWebhookIn(BaseModel):
    payment_reference: str
    status: str
