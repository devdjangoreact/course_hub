# Telegram webhook mode + Supabase Free config

**Date:** 2026-07-27  
**Status:** Approved for planning  
**Scope:** Single-bot env profiles; multi-bot deferred to backlog

## Goal

Add an env-driven Telegram update mode so the app can run on serverless (Vercel) with webhooks by default, while keeping long polling available for local/VPS profiles. Document Supabase Free Postgres URL for production. Do not implement multi-bot in this change.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Approach | Env mode + one webhook HTTP route |
| Default mode | `TELEGRAM_MODE=webhook` |
| Auto Telegram API rebind | `TELEGRAM_AUTO_SET_WEBHOOK` (default `true`): webhook → `setWebhook`, polling → `deleteWebhook` |
| Bot cardinality | One bot per process/env profile |
| FSM / rate limit store | Keep in-memory (`MemoryStorage`, `InMemoryRateLimiter`); Upstash backlog |
| Parser on production | Out of scope for this change (parser remains local-only by ops choice) |
| Tests | Not required unless asked later |

## Config / env

New `Settings` fields (code defaults; override via `.env`):

| Variable | Default | Values / notes |
|----------|---------|----------------|
| `TELEGRAM_MODE` | `webhook` | `webhook` \| `polling` |
| `TELEGRAM_AUTO_SET_WEBHOOK` | `true` | Controls both `setWebhook` and `deleteWebhook` on startup |
| `TELEGRAM_WEBHOOK_PATH` | `/api/telegram/webhook` | Path mounted on the FastAPI app |
| `TELEGRAM_WEBHOOK_SECRET` | `""` | If non-empty, require `X-Telegram-Bot-Api-Secret-Token` |

Existing fields reused:

- `BOT_TOKEN` — Telegram bot token
- `BACKEND_URL` — public base URL; webhook URL = `{BACKEND_URL}{TELEGRAM_WEBHOOK_PATH}`
- `DATABASE_URL` — SQLite for local; Supabase Postgres for production

Rebinding behaviour:

- Changing `BACKEND_URL` (Cloudflare Tunnel ↔ Vercel) and restarting with `TELEGRAM_AUTO_SET_WEBHOOK=true` re-registers the bot to the current URL.
- With `TELEGRAM_AUTO_SET_WEBHOOK=false`, the app only receives/polls; set/delete webhook is manual.

Env example files to update: `.env.example`, `.env.dev.example`, `.env.prod.example`. Short README section for modes + Supabase.

## Runtime (lifespan + BotApp)

Startup order remains: schema → seed → runtime settings → rate limiter → payment gateway → bot.

Then:

1. Build `BotApp` (dispatcher + `Bot` instance used for payment notifications).
2. If no token → disable bot (warning), same as today.
3. If `TELEGRAM_MODE=webhook`:
   - Do **not** start polling.
   - If auto flag → `setWebhook(url, secret_token=...)`.
4. If `TELEGRAM_MODE=polling`:
   - If auto flag → `deleteWebhook()`.
   - Start `start_polling` as today.

Shutdown:

- Polling: stop polling, cancel task, close session.
- Webhook: close bot session only (no polling task).

Payment notify continues via `bot_app.notify_payment_status` using the started `Bot` (no polling required for `send_message`).

Vercel cold start with auto-set may call `setWebhook` again with the same URL (idempotent; acceptable on free tier).

## HTTP webhook endpoint

- Method/path: `POST {TELEGRAM_WEBHOOK_PATH}` (default `/api/telegram/webhook`).
- If mode is not `webhook` → respond `404`.
- If secret configured and header mismatches → `401`.
- Parse Telegram `Update`, call `dispatcher.feed_update(bot, update)`.
- Return `200` after handling; log handler errors without unnecessarily failing the whole delivery when avoidable.

Code shape:

- Thin API router registered from `main.py`.
- set/delete/feed logic owned by `BotApp` (or a small helper next to `runner.py`).

Local: Cloudflare Tunnel → set `BACKEND_URL` to the tunnel HTTPS URL.  
Prod: `BACKEND_URL` = Vercel (or custom) HTTPS URL.

## Supabase Free

Config-only (no Supabase SDK):

```text
# Transaction pooler (recommended for serverless / Vercel)
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

Optional commented direct host (`:5432`) for Alembic/DDL from a laptop if the pooler misbehaves with migrations.

`Database` / engine: keep URL-driven setup. Add minimal Postgres `connect_args` (e.g. SSL) only if required for Supabase + asyncpg during implementation.

## Out of scope / backlog

- Multi-bot: several tokens per process, per-bot mode/webhook overrides with shared defaults.
- Upstash (or other shared store) for FSM and rate limiting.
- Disabling parser routes on production via env (ops can simply not call them).
- `vercel.json` / Vercel project wiring (ask before adding).
- Automated tests for webhook mode (ask before adding).

## Success criteria

1. With default env (`TELEGRAM_MODE=webhook`, auto-set on), app does not poll and registers webhook to `{BACKEND_URL}{path}`.
2. Switching to `polling` with auto-set removes webhook and starts polling without conflict.
3. Valid Telegram updates on the webhook path are processed by existing handlers.
4. Invalid/missing secret (when configured) is rejected with `401`.
5. `.env.prod.example` documents Supabase Free pooler `DATABASE_URL`.
6. README documents both modes and how URL rebinding works.
7. Multi-bot remains undocumented as implemented behaviour (backlog only).

## Implementation touchpoints (expected)

- `app/core/config.py` — new settings + enum/str validation
- `app/bot/runner.py` — mode branching, set/delete webhook, feed update
- `app/api/routers/` — telegram webhook router (new file; allowed for this feature)
- `app/main.py` — lifespan behaviour + include router
- `.env*.example`, `README.md` — docs
- Possibly `app/core/database.py` — SSL/connect args for Supabase if needed
