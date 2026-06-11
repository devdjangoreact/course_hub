from dataclasses import dataclass


@dataclass(slots=True)
class PaymentIntent:
    """Result of asking the payment gateway to start a payment for an order."""

    payment_reference: str
    instructions: str
    pay_url: str | None = None
