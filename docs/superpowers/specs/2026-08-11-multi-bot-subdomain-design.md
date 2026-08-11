# Multi-bot subdomain routing — design

**Date:** 2026-08-11  
**Status:** Design approved; implementation plan at `docs/superpowers/plans/2026-08-11-multi-bot-subdomain.md`  
**Scope:** Unlimited Telegram bots on one FastAPI process; each bot reached via `{bot_username}.{base_domain}/api/telegram/webhook`; per-bot channels (each with one discussion group) and channel course sets; shared catalog + shared Atlos payments for MVP.

## Goal

Run many Telegram bots behind one FastAPI app. Incoming webhooks use a per-bot subdomain so the process can resolve which bot the update belongs to. Persist bots, channels, and channel↔course links in the DB. Keep selling from the full category tree in DM; use channel membership for themed public/private channel catalogs. Track `bot_id` and `channel_id` on orders.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Process model | **One** FastAPI process; in-memory registry of active bots |
| Routing | Host subdomain = bot `username` → bot row; path stays `/api/telegram/webhook` |
| Webhook URL | `https://{bot_username}.{base_domain}/api/telegram/webhook` |
| Base domain | `BASE_DOMAIN` (DB/extra or env) if set; else host from `backend_url` (DB then `.env`) |
| DNS / TLS | **Cloudflare** (`*.base_domain` → origin); app only parses `Host` |
| Webhook secret | **Per-bot** `webhook_secret`; if set, verify `X-Telegram-Bot-Api-Secret-Token`; if empty, no check for that bot |
| Catalog in bot DM | **All categories** (shared); bots accept orders from the full tree |
| Channels per bot | **N** channels per bot (public and private) |
| Channel ↔ group | **1 channel → exactly 1 discussion group** (nullable until linked) |
| Channel courses | `channel_courses` M2M; same course may appear on many channels; each channel has its own themed set |
| Payments MVP | **One shared Atlos** (conceptually bound to the root category that contains all categories) |
| Payments later | Combine / split by category branches |
| Order attribution | `orders.bot_id` + `orders.channel_id` (channel nullable if purchase is DM-only) |
| Bot users | Still keyed by `telegram_id` globally; no per-bot user split in MVP |
| Global settings row | Keep `bot_settings` for app-wide config (domain, admin secret, languages…); runtime tokens live in `bots` |
| Approach | Host → bot + tables `bots` / `channels` / `channel_courses` (not path-only routing, not JSON-in-extra) |

## Out of scope (v1)

- Per-bot or per-category payment credentials (after MVP)
- Multi-bot long polling as primary production mode (webhook + Cloudflare)
- Separate process/container per bot
- Changing catalog enrich / Docker worker publish pipeline beyond reading bot/channel IDs when posting
- Splitting `bot_users` per bot

## Architecture

```
Cloudflare: *.example.com → same origin
                │
                ▼
         FastAPI (1 process)
                │
     Host: mybot.example.com
                │
                ▼
   resolve username=mybot → bots row
                │
                ▼
   verify webhook_secret (if set)
                │
                ▼
   aiogram Bot/Dispatcher for that bot
                │
                ▼
   handlers (shared) + context.bot_id
                │
     orders(bot_id, channel_id?)
                │
                ▼
   Atlos webhook (shared) → notify via order.bot_id
```

### Domain resolution

1. Read `Host` (ignore port).
2. If host equals `base_domain` or `www.{base_domain}` → not a bot webhook host (admin/API as today).
3. If host is `{username}.{base_domain}` → lookup active bot by normalized username.
4. Missing / inactive → `404`.

Username: lowercase, no `@`, must match Telegram bot username used as subdomain.

### setWebhook

On startup (if auto-set enabled) and when admin saves a bot:

- Active + token → `setWebhook(url, secret_token=webhook_secret or omit)`
- Inactive → `deleteWebhook` for that token when practical

URL built as `https://{username}.{base_domain}/api/telegram/webhook`.

## Data model

### `bots`

| Column | Type / notes |
|--------|----------------|
| id | PK |
| username | unique, lowercase, subdomain key |
| token | Telegram bot token |
| webhook_secret | string; empty = no verification |
| is_active | bool |
| title | optional admin label |
| notes | optional |
| extra | JSON |
| created_at / updated_at | timestamps |

### `channels`

| Column | Type / notes |
|--------|----------------|
| id | PK |
| bot_id | FK → bots |
| telegram_chat_id | Telegram channel id |
| discussion_group_id | nullable; at most one group per channel |
| is_public | channel visibility flag |
| discussion_is_public | group visibility flag |
| invite_link | public/invite URL for the **channel** |
| discussion_invite_link | public/invite URL for the **group** |
| title | optional |
| slug | optional |
| is_active | bool |
| extra | JSON |
| created_at / updated_at | timestamps |

Constraints: one channel belongs to one bot; one discussion group id per channel row.

### `channel_courses`

| Column | Notes |
|--------|--------|
| channel_id | FK |
| course_id | FK |
| unique (channel_id, course_id) | |
| extra | JSON (optional metadata on the link) |

### `orders` (additions)

| Column | Notes |
|--------|--------|
| bot_id | FK → bots; which bot took / should notify |
| channel_id | FK → channels; which channel the payment/flow came from; **nullable** for DM-only |

### Global settings / payments

- `bot_settings` (or equivalent): `backend_url` / base domain, session secret, log level, language/search extras — DB then `.env`.
- Deprecate using `bot_settings.bot_token` for runtime after migration (migrate into `bots`).
- `payment_settings`: shared Atlos as today (root-level).

### `bot_users`

Unchanged identity model (`telegram_id`).

## Runtime behavior

### Startup

1. Load global settings (DB → env).
2. Load active bots with tokens → build registry `username → {bot_id, Bot, webhook_secret, …}`.
3. Shared handler routers; middleware injects current `bot_id` / Bot into context.
4. `setWebhook` per active bot when configured.

### Webhook handler

1. Parse Host → username.
2. Resolve registry (DB fallback on miss / cold start).
3. Optional secret check.
4. `feed_update` on that bot only.

### Orders & delivery

- Create order with `bot_id` from bot context; set `channel_id` when the flow is channel-originated.
- Payment webhooks remain shared; after pay, notify via the Bot instance for `order.bot_id`.
- Invite/delivery links prefer channel `invite_link` / `discussion_invite_link` when `channel_id` present; else existing course.extra / global fallbacks.

### Dev polling

Optional single-bot polling from env / one selected username; not the multi-bot production path.

## Admin (sqladmin)

- **Bots** CRUD (mask token + webhook_secret).
- **Channels** CRUD including public links and extras.
- **Channel courses** link management.
- **Orders** show `bot_id`, `channel_id`.
- **App settings**: global domain/url; stop treating global bot_token as the live multi-bot source after migration.
- On bot save: refresh registry + set/delete webhook.

## Migration

1. Alembic: create `bots`, `channels`, `channel_courses`; add nullable `orders.bot_id`, `orders.channel_id`.
2. Seed one `bots` row from current `bot_settings.bot_token` / `BOT_TOKEN`; username from Telegram `getMe` or `BOT_USERNAME` if set; `webhook_secret` from `TELEGRAM_WEBHOOK_SECRET` if present.
3. Seed one `channels` row from `CATALOG_CHANNEL_ID`, `CATALOG_DISCUSSION_GROUP_ID`, `CATALOG_INVITE_LINK` when present.
4. Existing orders leave `bot_id` / `channel_id` null; new orders populate them.

## Cloudflare checklist (ops, not app code)

- Wildcard DNS `*.example.com` → same origin as apex.
- SSL mode appropriate for origin (e.g. Full/Strict).
- Apex/`www` for admin and non-bot HTTP; bot traffic on subdomains.

## Success criteria

- Two active bots with distinct usernames each receive updates only on their subdomain webhook URL.
- Wrong subdomain or inactive bot → 404; wrong secret (when configured) → 401.
- Admin can attach multiple channels to one bot; each channel has one discussion group and its own course set.
- New orders store `bot_id`; channel-originated orders store `channel_id`.
- Paid notify goes out on the bot recorded on the order.
- Base domain resolves from DB with `.env` fallback.

## Implementation defaults (locked)

- **Dispatcher:** one shared `Dispatcher` + middleware that injects the current bot (`bot_id`, `Bot` instance); not one dispatcher per bot.
- **Base domain precedence:** `BASE_DOMAIN` (DB `bot_settings` / extra or env) if set; else hostname parsed from `backend_url` (DB then `.env` `BACKEND_URL`). Document in `.env.example`.
- **Webhook path:** keep existing `TELEGRAM_WEBHOOK_PATH` default `/api/telegram/webhook` (shared path; bot identity from Host only).
