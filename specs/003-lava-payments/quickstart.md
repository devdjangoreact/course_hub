# Quickstart: lava.top Payment Integration

**Feature**: `003-lava-payments`

## Prerequisites

1. lava.top author account with **Public API** key created.
2. Webhook configured in lava.top:
   - URL: `https://<your-domain>/api/payments/lava/webhook`
   - Event type: **Payment result**
   - Auth: **Your service's API key** → value stored as `PAYMENT_SECRET_KEY`
3. Digital product/offer created in lava.top; copy offer UUID.

## Environment (production)

```env
PAYMENT_PROVIDER=lava
PAYMENT_API_KEY=<lava-public-api-key>
PAYMENT_SECRET_KEY=<your-webhook-api-key-shared-with-lava>
PAYMENT_CURRENCY=USD
```

Optional in payment settings `extra` (via admin or bootstrap):

- `lava_env`: `sandbox` or `production`
- `payment_method`: `STRIPE`, `PAYPAL`, `UNLIMINT`, or `BANK131`

## Course setup

Set `lava_offer_id` on the course (admin `extra` field or seed data):

```json
{ "lava_offer_id": "836b9fc5-7ae9-4a27-9642-592bc44072b7" }
```

## Local development (simulated)

```env
PAYMENT_PROVIDER=simulated
PAYMENT_SECRET_KEY=testsecret
```

Run existing order + simulate flow — no lava.top credentials needed.

## Manual test (lava)

1. Start app with `PAYMENT_PROVIDER=lava` and valid keys.
2. Open Telegram bot → select course → **Order**.
3. Enter email when prompted.
4. Open payment link → complete checkout on lava.top.
5. Confirm webhook delivered (lava dashboard → Webhook history).
6. Verify order status `paid` in admin and bot notification.

## Webhook IP

Allow inbound HTTPS from `158.160.60.174` if using firewall rules.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| No payment link | Course `lava_offer_id`, API key, buyer email |
| 401 on webhook | `PAYMENT_SECRET_KEY` matches lava webhook auth key |
| Order stays pending | Webhook URL reachable over HTTPS; check lava webhook history |
| Wrong currency | Offer currency vs `PAYMENT_CURRENCY` alignment |
