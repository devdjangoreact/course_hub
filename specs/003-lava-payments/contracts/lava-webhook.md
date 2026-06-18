# Contract: lava.top Webhook

Receives lava.top **Payment result** events and updates orders idempotently.

## Endpoint

`POST /api/payments/lava/webhook`

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Api-Key` | Yes | Webhook API key configured in lava.top and stored as `payment_settings.secret_key` |
| `Content-Type` | Yes | `application/json` |

Requests failing authentication return **401** and are logged without secrets.

### Body (lava.top native shape)

```json
{
  "eventType": "payment.success",
  "contractId": "uuid-of-invoice-or-contract",
  "product": {
    "id": "product-uuid",
    "title": "Course name"
  },
  "buyer": {
    "email": "buyer@example.com"
  }
}
```

Supported `eventType` values for this endpoint:

| eventType | Order status |
|-----------|--------------|
| `payment.success` | `paid` |
| `payment.failed` | `failed` |
| `payment.cancelled` | `cancelled` |

## Behavior

1. Verify `X-Api-Key` matches configured webhook secret.
2. Parse body; extract `contractId` as payment reference.
3. Look up order by `payment_reference`.
4. Map `eventType` to target status.
5. Apply idempotent update (no duplicate notifications for terminal states).
6. Notify buyer via Telegram bot on status change.
7. Return **200** `{ "ok": true }` on success.

## Responses

| Code | Meaning |
|------|---------|
| 200 | Processed or already applied |
| 401 | Invalid or missing `X-Api-Key` |
| 404 | Unknown payment reference |
| 422 | Malformed payload or unknown event type |

## Notes

- Configure this URL in lava.top: `{BACKEND_URL}/api/payments/lava/webhook`
- Webhook type: **Payment result** (not Recurring payment)
- lava.top retries failed deliveries up to 20 times; idempotency is required
