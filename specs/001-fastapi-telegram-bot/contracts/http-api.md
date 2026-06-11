# Contract: HTTP API (FastAPI)

Base: the service exposes a small HTTP surface for health checks, the payment webhook, and the
mounted admin. The catalog/search/order flows are primarily consumed through the Telegram bot, but
read endpoints are provided so the same domain services are reusable and testable over HTTP.

## Health

`GET /health`

- 200 → `{ "status": "ok", "env": "development" | "production" }`
- Used by the infra validation gate.

## Catalog (read)

`GET /api/categories`

- 200 → `[{ "id": int, "name": str }]`

`GET /api/categories/{category_id}/courses`

- 200 → `[{ "id": int, "name": str, "description": str, "price": str, "link": str }]`
  (active courses only)
- 404 → category not found

`GET /api/courses/search?q=<term>`

- 200 → ranked list of active courses matching `q` (name/description)
- 422 → empty/invalid `q`

## Orders

`POST /api/orders`

- body → `{ "telegram_id": int, "course_id": int }`
- 201 → `{ "order_id": int, "status": "pending", "amount": str, "payment": { ... } }`
- 404 → course not found or inactive

`GET /api/orders/{order_id}`

- 200 → `{ "order_id": int, "status": str, "amount": str }`

## Admin

- `GET /admin` (and CRUD sub-routes) → SQLAdmin UI, authentication required against a persisted
  `AdminUser` (hashed password).
- Dedicated settings views edit `BotSettings` (bot token, backend URL) and `PaymentSettings`
  (provider, keys, currency).
- Model views for Category, Course, Order (and AdminUser management).
- Unauthenticated access redirects to login / returns 401.

## Conventions

- All responses JSON; money serialized as a decimal string.
- Errors use FastAPI's standard `{ "detail": ... }` shape with appropriate status codes.
- Input validated by Pydantic v2 schemas; no `any`-typed payloads.
