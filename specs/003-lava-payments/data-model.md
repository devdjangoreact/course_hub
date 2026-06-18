# Data Model: lava.top Payment Integration

**Feature**: `003-lava-payments` | **Date**: 2026-06-17

No new tables or Alembic migrations. This feature extends existing entities via `extra` JSON and
configuration.

## PaymentSettings (existing)

| Field | lava usage |
|-------|------------|
| `provider` | `"lava"` selects LavaPaymentGateway |
| `api_key` | lava.top Public API key (outbound requests) |
| `secret_key` | Webhook API key (inbound `X-Api-Key`) |
| `currency` | `USD`, `EUR`, or `RUB` per lava rules |
| `extra.lava_env` | `"sandbox"` or `"production"` |
| `extra.payment_method` | Optional lava `PaymentMethod` name (e.g. `STRIPE`) |

## Course (existing)

| extra key | Type | Description |
|-----------|------|-------------|
| `lava_offer_id` | string (UUID) | lava.top offer id for one-time purchase |

**Validation**: Required when `provider=lava` and user orders the course.

## BotUser (existing)

| extra key | Type | Description |
|-----------|------|-------------|
| `payment_email` | string | Buyer email for lava checkout; reused on later orders |

## Order (existing)

| Field | lava usage |
|-------|------------|
| `payment_reference` | lava invoice/contract id from `create_one_time_payment` |
| `status` | Unchanged lifecycle: `pending` → `paid` / `failed` / `cancelled` |

## State transitions (webhook-driven)

```text
pending --payment.success--> paid
pending --payment.failed--> failed
pending --payment.cancelled--> cancelled (if sent)
paid    --any duplicate--> paid (no side effects)
```

## Relationships

- `Order` → `Course` (course supplies `lava_offer_id`)
- `Order` → `BotUser` (user supplies `payment_email`)
- `PaymentSettings` → gateway adapter selection at runtime
