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

Core settings are stored in the database and managed via the Admin Panel under **Settings → App Settings**. The `.env` file is primarily used to seed these settings on the first run. 

To apply changes, restart the application if modifying the `BOT_TOKEN` or `ADMIN_SESSION_SECRET`. Other settings (like `BACKEND_URL` and `LOG_LEVEL`) apply immediately.

Multilingual defaults (seeded from `.env`):

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

For Supabase Free (Vercel/serverless), prefer the Transaction pooler URL on port `6543`. TLS is
enabled automatically when the host contains `supabase.com`.

## Telegram bot modes

Course Hub supports two update transports via env:

- `TELEGRAM_MODE=webhook` (default) — Telegram calls `POST {BACKEND_URL}{TELEGRAM_WEBHOOK_PATH}`.
- `TELEGRAM_MODE=polling` — long polling inside the app process (local/VPS).

When `TELEGRAM_AUTO_SET_WEBHOOK=true` (default):

- webhook mode calls Telegram `setWebhook` on startup (rebinds after `BACKEND_URL` changes, e.g.
  Cloudflare Tunnel ↔ Vercel);
- polling mode calls `deleteWebhook` so an old hook cannot conflict.

Optional `TELEGRAM_WEBHOOK_SECRET` must match Telegram header `X-Telegram-Bot-Api-Secret-Token`.

Local webhook testing: run the API, expose it with Cloudflare Tunnel, set `BACKEND_URL` to the tunnel
HTTPS URL, restart so auto-set rebinds the bot.

## Payments (atlos.io & lava.top)

Configure payments in the admin panel under **Settings → Payment Settings**
(`http://localhost:8000/admin`). Changes apply immediately without restart:

- **Provider**: `simulated` (local dev), `lava`, or `atlos`
- **API key**: atlos.io ApiSecret OR lava.top Public API key
- **Webhook secret**: atlos.io Webhook Secret (`Signature`) OR lava.top Webhook API key (`X-Api-Key`)
- **Currency**: USD, EUR, RUB, etc.
- **Extra**: `{"lava_env": "production", "checkout_mode": "direct"}`

Payment link mode (`checkout_mode` in **Extra** or `PAYMENT_LINK_MODE` in `.env` on first seed):

- `direct` (default) — bot **Pay** button opens the payment provider URL directly
- `checkout` — bot opens `{BACKEND_URL}/api/orders/{id}/checkout` (summary page, then pay)

On first run, values are seeded from `.env` (`PAYMENT_PROVIDER`, `PAYMENT_API_KEY`,
`PAYMENT_SECRET_KEY`, `PAYMENT_CURRENCY`, `PAYMENT_LINK_MODE`). 

Map each course to a specific offer if required (e.g. for lava.top, add `{"lava_offer_id": "uuid"}` in course `extra`).

**Webhook URLs:**
- Atlos.io: `{BACKEND_URL}/api/payments/atlos/webhook`
- Lava.top: `{BACKEND_URL}/api/payments/lava/webhook` (event type: **Payment result**)

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

## Deploy to Vercel (CI/CD)

**Flow:** push / merge to `main` → GitHub Actions runs tests → syncs secrets from **`ENV_PROD`**
(contents of your local `.env.prod`) into Vercel → deploys production.

Never commit `.env` / `.env.prod`. Keep real values only in:
- local `.env.prod` (gitignored), and
- GitHub Actions secret `ENV_PROD` (paste the same file contents).

### One-time setup

1. Create local `.env.prod` from `.env.prod.example` (Supabase, bot, webhook mode, **and**
   `VERCEL_TOKEN` / `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID`).
2. GitHub → **Settings → Secrets and variables → Actions** → one secret:

| Secret | Value |
|--------|--------|
| `ENV_PROD` | **full text** of your local `.env.prod` |

CI reads `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` from that file and deploys.
Do **not** commit `.env.prod`.

3. Optional Variable `VERCEL_PRODUCTION_URL` = `https://your-project.vercel.app`  
   CI overwrites `BACKEND_URL` so Telegram webhook points at prod.

4. Push to `main`. Workflow: `.github/workflows/deploy-vercel.yml`.

### Manual sync (optional)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync-vercel-env.ps1 -EnvFile .env.prod
```

```bash
export VERCEL_TOKEN=...
./scripts/sync-vercel-env.sh .env.prod production
npx vercel --prod
```

Existing ECR/`infra` pipeline in `.github/workflows/build.yml` is unchanged.

## Local catalog toolbox

Logic lives in `tools/catalog/` (not deployed to Vercel). Run **one script** and toggle
steps at the top of the file; secrets stay in `.env`.

```bash
pip install -r tools/catalog/requirements.txt
# edit DO_PARSE / DO_NORMALIZE / DO_ENRICH / DO_POST / DO_SYNC_DB / POST_IDS
python scripts/catalog_pipeline.py
```

`.env`: `TG_*` (parse), `BOT_TOKEN` + `CATALOG_*` (post + Vercel), `AI_*` (enrich), `DATABASE_URL`.

Do not add pyrogram/playwright/boto3 to the app Poetry dependencies.
