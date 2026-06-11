# Contract: Payment Webhook

Endpoint that receives payment results and updates the corresponding order idempotently.

## Endpoint

`POST /api/payments/webhook`

Headers:

- A provider signature/secret header (verified before processing). Requests failing verification are
  rejected with 401 and logged (without the secret).

Body (provider-shaped; normalized internally):

```json
{
  "payment_reference": "string",
  "order_id": 123,
  "status": "succeeded | failed | cancelled",
  "amount": "string"
}
```

## Behavior

- Look up the order by `payment_reference` (or `order_id`).
- Apply the mapped status transition:
  - `succeeded` → order `paid`
  - `failed` → order `failed`
  - `cancelled` → order `cancelled`
- **Idempotent**: if the order is already in the target terminal state, return 200 without
  re-applying side effects (no duplicate user notifications).
- On success, notify the buyer through the bot.

## Responses

- 200 → `{ "ok": true }` (processed or already-applied)
- 401 → signature verification failed
- 404 → unknown order/payment reference
- 422 → malformed payload

## Development/testing

- A simulated payment adapter exposes a way to confirm an order without a real provider (e.g. a
  guarded `POST /api/payments/simulate` available only when `APP_ENV=development`), so the order
  lifecycle is testable end-to-end without external dependencies.
