# course_hub

Async FastAPI application with a Telegram bot for browsing courses, full-text search, orders,
payment confirmation, and a simple admin panel.

- Project: `course_hub`
- Service / ECR image: `ddnsteltonicka`
- Domain: `ddnsteltonicka.pp.ua`

## Development

Development is Docker-first. Code, dependencies, and environment run inside containers. Poetry is
installed inside the image, not globally on the host.

1. Copy `.env.dev.example` to `.env` and fill real local secrets.
2. Start the app:

```bash
docker compose up --build
```

3. Seed demo data and the first admin:

```bash
docker compose exec app python -m app.seed
```

Open:

- API health: `http://localhost:8000/health`
- Admin: `http://localhost:8000/admin`

## Configuration

Use `APP_ENV=development` for development/testing and `APP_ENV=production` for production. Use a
different Telegram bot token in each profile.

Multilingual defaults:

```text
SUPPORTED_LANGUAGES=uk,en
DEFAULT_LANGUAGE=uk
SEARCH_SUGGESTION_MIN_CHARS=3
SEARCH_SUGGESTION_LIMIT=5
PARSER_REQUEST_TIMEOUT_SECONDS=10
```

The bot asks new users to choose a language, stores the preference, and reuses it for later catalog,
search, order, and payment messages. Catalog translations fall back to the default course/category
text when a localized field is missing.

SQLite is the phase-1 default:

```text
DATABASE_URL=sqlite+aiosqlite:///./course_hub.db
```

Switch to PostgreSQL by changing only `DATABASE_URL`:

```text
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/course_hub
```

## Payments (lava.top)

Configure payments in the admin panel under **Settings → Payment Settings**
(`http://localhost:8000/admin`). Changes apply immediately without restart:

- **Provider**: `simulated` (local dev) or `lava`
- **API key**: lava.top Public API key
- **Webhook secret**: lava.top Webhook API key (`X-Api-Key`)
- **Currency**: USD, EUR, or RUB
- **Extra**: `{"lava_env": "production", "checkout_mode": "direct"}`

Payment link mode (`checkout_mode` in **Extra** or `PAYMENT_LINK_MODE` in `.env` on first seed):

- `direct` (default) — bot **Pay** button opens the payment provider URL directly
- `checkout` — bot opens `{BACKEND_URL}/api/orders/{id}/checkout` (summary page, then pay)

On first run, values are seeded from `.env` (`PAYMENT_PROVIDER`, `PAYMENT_API_KEY`,
`PAYMENT_SECRET_KEY`, `PAYMENT_CURRENCY`, `LAVA_ENV`, `PAYMENT_LINK_MODE`). Map each course to a lava offer id in
course `extra` (edit the **Course** record):

```json
{ "lava_offer_id": "<offer-uuid-from-lava-dashboard>" }
```

Webhook URL: `{BACKEND_URL}/api/payments/lava/webhook` (event type: **Payment result**).

Development keeps `PAYMENT_PROVIDER=simulated` for local order/payment testing without external calls.

## Tests

Run tests inside Docker:

```bash
docker compose exec app pytest
```

The suite covers health, catalog endpoints, full-text search, order creation, simulated payment,
lava.top webhook handling, payment webhook signature validation/idempotency, admin authentication,
multilingual catalog/search, parser jobs, and the rate limiter.

## Parser Workflow

Admins can configure parser sources and start parser jobs from admin/API flows. Parsed items are saved
as draft/imported review records and are not visible in the bot until approved and activated.

