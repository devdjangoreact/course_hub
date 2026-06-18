# Contract: Payment Gateway (lava adapter)

Extends the existing `PaymentGateway` port with a lava.top implementation.

## Interface (unchanged)

```text
create_payment(order, settings) -> PaymentIntent
verify_signature(payload, signature, settings) -> bool
```

## LavaPaymentGateway — create_payment

**Preconditions**

- `settings.provider == "lava"`
- `settings.api_key` is set
- Course `extra.lava_offer_id` is set
- Buyer `payment_email` available (from caller)

**Actions**

1. Call `lava-top-sdk` `create_one_time_payment` with:
   - `email` = buyer payment email
   - `offer_id` = course `lava_offer_id`
   - `currency` = `settings.currency`
   - optional `payment_method` from `settings.extra`
2. Return `PaymentIntent`:
   - `payment_reference` = lava payment `id`
   - `pay_url` = lava `paymentUrl`
   - `instructions` = localized-ready text including order id and amount

**Errors**

- Missing offer id → `ValidationError` ("Course is not configured for lava payments")
- Missing API key → `ValidationError`
- Provider API error → log and `ValidationError` with safe message

## LavaPaymentGateway — verify_signature

Used only for the generic `/api/payments/webhook` path (simulated HMAC). For lava, webhook auth
happens on `/api/payments/lava/webhook` via `X-Api-Key` comparison:

```text
hmac.compare_digest(provided_key, settings.secret_key)
```

## Gateway factory

```text
build_payment_gateway(provider: str, backend_url: str) -> PaymentGateway
```

| provider | implementation |
|----------|----------------|
| `simulated` | `SimulatedPaymentGateway` |
| `lava` | `LavaPaymentGateway` |
| other | `ValidationError` at startup |

## Simulated gateway (unchanged)

Continues to serve development/CI with HMAC `X-Signature` on `/api/payments/webhook`.
