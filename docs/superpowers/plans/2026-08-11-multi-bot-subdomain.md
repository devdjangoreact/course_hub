# Multi-bot Subdomain Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve unlimited Telegram bots from one FastAPI process via `{bot_username}.{base_domain}/api/telegram/webhook`, with DB-backed bots/channels/channel_courses and `bot_id`/`channel_id` on orders.

**Architecture:** Host header selects the bot; one shared aiogram `Dispatcher` + in-memory registry of `Bot` instances; Cloudflare owns wildcard DNS/TLS. Shared catalog + shared Atlos remain; channel tables hold per-channel course sets and invite links.

**Tech Stack:** FastAPI, aiogram 3, SQLAlchemy async, Alembic, sqladmin, pytest/httpx (existing test stack).

**Spec:** `docs/superpowers/specs/2026-08-11-multi-bot-subdomain-design.md`

## Global Constraints

- One FastAPI process; bot identity from `Host` subdomain only; webhook path stays `/api/telegram/webhook` (or `TELEGRAM_WEBHOOK_PATH`).
- Webhook URL: `https://{bot_username}.{base_domain}/api/telegram/webhook`.
- Base domain: `BASE_DOMAIN` (env or `bot_settings.extra["base_domain"]`) if set; else hostname from `backend_url` (DB then env).
- Per-bot `webhook_secret`; empty → no secret check for that bot.
- Bot DM catalog = all categories; `channel_courses` is for channel membership/publish, not DM filtering in v1.
- 1 bot → N channels; 1 channel → 1 discussion group (nullable until set).
- Payments: one shared Atlos (no per-bot keys in v1).
- `orders.bot_id` required for new bot-originated orders; `orders.channel_id` nullable (DM-only).
- Do not read or commit `.env` / real tokens; mask secrets in admin.
- Prefer minimal diffs; no drive-by refactors.
- Commit only when the user explicitly asks (skip commit steps unless requested).
- Ask before creating files outside the paths listed in this plan.
- Code and docs in English; user-facing chat replies may stay as today.
- After code changes in a session, run `npx graphify hook-rebuild` when finishing a batch of app code edits.

## File structure

| File | Responsibility |
|------|----------------|
| `app/core/domain_host.py` | Pure helpers: normalize username, parse bot username from Host, resolve base domain, build webhook URL |
| `app/core/config.py` | Add `base_domain: str = ""` |
| `app/domain/entities/telegram_bot.py` | `TelegramBot` dataclass |
| `app/domain/entities/telegram_channel.py` | `TelegramChannel` dataclass |
| `app/domain/repositories/telegram_bot_repository.py` | Protocol |
| `app/domain/repositories/telegram_channel_repository.py` | Protocol |
| `app/infrastructure/db/models/telegram_bot.py` | ORM `bots` |
| `app/infrastructure/db/models/telegram_channel.py` | ORM `channels` |
| `app/infrastructure/db/models/channel_course.py` | ORM `channel_courses` |
| `app/infrastructure/db/models/order.py` | Add `bot_id`, `channel_id` |
| `app/infrastructure/db/models/__init__.py` | Register new models |
| `app/infrastructure/db/repositories/telegram_bot_repository.py` | SQL impl |
| `app/infrastructure/db/repositories/telegram_channel_repository.py` | SQL impl |
| `app/infrastructure/db/init_db.py` | SQLite column patches for `orders.bot_id` / `orders.channel_id` |
| `alembic/versions/0003_multi_bot_subdomain.py` | Migration + optional data notes |
| `app/bot/registry.py` | In-memory `BotRegistry` |
| `app/bot/runner.py` | Multi-bot start/stop/handle_update/notify/setWebhook |
| `app/bot/middleware.py` | Inject `bot_id` from registry entry |
| `app/bot/context.py` | Optional: nothing heavy; keep `BotRuntime` |
| `app/api/routers/telegram.py` | Host → bot; per-bot secret |
| `app/domain/entities/order.py` | `bot_id`, `channel_id` |
| `app/application/services/order_service.py` | Pass attribution into `create_order` |
| `app/bot/handlers/order.py` | Pass `bot_id` (channel_id when available) |
| `app/infrastructure/db/repositories/order_repository.py` | Persist new FKs |
| `app/application/services/runtime_settings.py` | Resolve `base_domain` into runtime |
| `app/admin/views.py` | Bot / Channel / ChannelCourse admin; order columns |
| `app/bootstrap.py` (or small helper) | Seed first bot/channel from legacy token/env if `bots` empty |
| `.env.example` | `BASE_DOMAIN`, note multi-bot |
| `tests/unit/test_domain_host.py` | Host/base_domain/webhook URL helpers |
| `tests/integration/test_telegram_webhook_multi_bot.py` | Host routing + secret |

---

### Task 1: Host / base_domain helpers

**Files:**
- Create: `app/core/domain_host.py`
- Modify: `app/core/config.py` — add `base_domain: str = ""`
- Modify: `.env.example` — document `BASE_DOMAIN=`
- Test: `tests/unit/test_domain_host.py`

**Interfaces:**
- Produces:
  - `normalize_bot_username(raw: str) -> str` — strip `@`, lower, strip
  - `bot_username_from_host(host: str, base_domain: str) -> str | None` — `None` if apex, `www`, empty subdomain, or host does not end with `.{base_domain}`
  - `hostname_from_url(url: str) -> str` — parse netloc, strip port
  - `resolve_base_domain(*, base_domain: str, backend_url: str) -> str` — prefer non-empty `base_domain`, else hostname from URL
  - `webhook_url_for_bot(*, username: str, base_domain: str, webhook_path: str) -> str` — `https://{username}.{base_domain}{path}`

- [ ] **Step 1: Write failing unit tests**

Create `tests/unit/test_domain_host.py`:

```python
from app.core.domain_host import (
    bot_username_from_host,
    normalize_bot_username,
    resolve_base_domain,
    webhook_url_for_bot,
)


def test_normalize_bot_username() -> None:
    assert normalize_bot_username("@MyBot") == "mybot"


def test_bot_username_from_host() -> None:
    assert bot_username_from_host("shop.example.com", "example.com") == "shop"
    assert bot_username_from_host("example.com", "example.com") is None
    assert bot_username_from_host("www.example.com", "example.com") is None
    assert bot_username_from_host("shop.other.com", "example.com") is None


def test_resolve_base_domain_prefers_explicit() -> None:
    assert resolve_base_domain(base_domain="bots.example.com", backend_url="https://api.example.com") == "bots.example.com"
    assert resolve_base_domain(base_domain="", backend_url="https://api.example.com:443/") == "api.example.com"


def test_webhook_url_for_bot() -> None:
    assert (
        webhook_url_for_bot(username="shop", base_domain="example.com", webhook_path="/api/telegram/webhook")
        == "https://shop.example.com/api/telegram/webhook"
    )
```

- [ ] **Step 2: Run tests — expect import/fail**

Run: `pytest tests/unit/test_domain_host.py -v`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement helpers + config + `.env.example`**

`app/core/domain_host.py` — stdlib only (`urllib.parse.urlparse`).

In `Settings` add: `base_domain: str = ""`.

In `.env.example` after `BACKEND_URL`:

```text
# Optional explicit apex for bot subdomains; if empty, hostname of BACKEND_URL is used
# Webhook per bot: https://{bot_username}.{BASE_DOMAIN}/api/telegram/webhook
BASE_DOMAIN=
```

- [ ] **Step 4: Re-run tests — expect PASS**

Run: `pytest tests/unit/test_domain_host.py -v`

---

### Task 2: ORM models + Alembic + SQLite patches

**Files:**
- Create: `app/infrastructure/db/models/telegram_bot.py`
- Create: `app/infrastructure/db/models/telegram_channel.py`
- Create: `app/infrastructure/db/models/channel_course.py`
- Modify: `app/infrastructure/db/models/order.py`
- Modify: `app/infrastructure/db/models/__init__.py`
- Modify: `app/infrastructure/db/init_db.py`
- Create: `alembic/versions/0003_multi_bot_subdomain.py`

**Interfaces:**
- Produces table names: `bots`, `channels`, `channel_courses`
- `OrderModel.bot_id: int | None`, `OrderModel.channel_id: int | None` (FK, nullable, indexed)

- [ ] **Step 1: Add models**

`TelegramBotModel` (`__tablename__ = "bots"`): `id`, `username` (unique String), `token`, `webhook_secret` default `""`, `is_active` default True, `title` default `""`, `notes` default `""`, `ExtraMixin`, `TimestampMixin`.

`TelegramChannelModel` (`channels`): `id`, `bot_id` FK `bots.id`, `telegram_chat_id` (BigInteger-compatible; use `sa.BigInteger` or `Mapped[int]`), `discussion_group_id` nullable int, `is_public` bool, `discussion_is_public` bool, `invite_link` str, `discussion_invite_link` str, `title` str, `slug` str, `is_active` bool, Extra + Timestamp.

`ChannelCourseModel` (`channel_courses`): `id`, `channel_id` FK, `course_id` FK, UniqueConstraint(`channel_id`, `course_id`), ExtraMixin (no timestamps required unless you want consistency — include TimestampMixin for consistency with other link tables if any; otherwise Extra only is fine per spec).

`OrderModel`: add

```python
bot_id: Mapped[int | None] = mapped_column(ForeignKey("bots.id"), nullable=True, index=True, default=None)
channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id"), nullable=True, index=True, default=None)
```

Register imports in `models/__init__.py` + `__all__`.

- [ ] **Step 2: SQLite patches for existing DBs**

In `_SQLITE_COLUMN_PATCHES` add:

```python
"orders": {
    "bot_id": "INTEGER",
    "channel_id": "INTEGER",
},
```

(New tables come from `create_all`; patches only for new columns on old `orders`.)

- [ ] **Step 3: Alembic `0003_multi_bot_subdomain`**

- `revises: 0002_multilingual_search`
- `upgrade`: create three tables; `op.add_column` for orders FKs (nullable)
- `downgrade`: drop columns/tables in reverse order

- [ ] **Step 4: Smoke import**

Run: `python -c "from app.infrastructure.db.models import TelegramBotModel, TelegramChannelModel, ChannelCourseModel; print('ok')"`  
Expected: `ok`

---

### Task 3: Domain entities + repositories

**Files:**
- Create: `app/domain/entities/telegram_bot.py`
- Create: `app/domain/entities/telegram_channel.py`
- Create: `app/domain/repositories/telegram_bot_repository.py`
- Create: `app/domain/repositories/telegram_channel_repository.py`
- Create: `app/infrastructure/db/repositories/telegram_bot_repository.py`
- Create: `app/infrastructure/db/repositories/telegram_channel_repository.py`
- Modify: `app/domain/entities/order.py`
- Modify: `app/infrastructure/db/repositories/order_repository.py`

**Interfaces:**
- `TelegramBot`: `id`, `username`, `token`, `webhook_secret`, `is_active`, `title`, `notes`, `extra`
- `TelegramChannel`: fields matching model (including invite links + flags + `extra`)
- `TelegramBotRepository`: `list_active() -> list[TelegramBot]`, `get_by_username(username: str) -> TelegramBot | None`, `get(id: int) -> TelegramBot | None`, `save(bot: TelegramBot) -> TelegramBot`
- `TelegramChannelRepository`: `list_by_bot(bot_id: int) -> list[TelegramChannel]`, `get(id: int) -> TelegramChannel | None`, `save(...)`, `set_courses(channel_id: int, course_ids: list[int]) -> None` (optional in v1 — admin M2M via sqladmin may be enough; if skipping `set_courses`, still implement `list_course_ids(channel_id) -> list[int]` for later publish)
- `Order`: add `bot_id: int | None = None`, `channel_id: int | None = None`; repository `add`/`_to_entity`/`update` persist them

- [ ] **Step 1: Implement entities + repos (mirror `SqlBotSettingsRepository` style)**

- [ ] **Step 2: Quick assert via existing pytest DB fixture if available** — or a tiny async test inserting a bot and selecting by username in `tests/unit/test_telegram_bot_repository.py` using the project’s `db_session` fixture from `tests/conftest.py` (reuse patterns from other repo tests; if none exist, skip dedicated test and rely on Task 5 integration).

---

### Task 4: BotRegistry + BotApp multi-bot lifecycle

**Files:**
- Create: `app/bot/registry.py`
- Modify: `app/bot/runner.py`
- Modify: `app/bot/middleware.py`
- Modify: `app/application/services/runtime_settings.py` — expose `base_domain: str` on `RuntimeSettings`

**Interfaces:**
- `class BotRegistry`:
  - `get(username: str) -> RegisteredBot | None`
  - `get_by_id(bot_id: int) -> RegisteredBot | None`
  - `all_active() -> list[RegisteredBot]`
  - `replace_all(entries: list[RegisteredBot]) -> None`
  - `upsert(entry: RegisteredBot) -> None`
  - `remove(username: str) -> None`
- `RegisteredBot` dataclass: `bot_id: int`, `username: str`, `token: str`, `webhook_secret: str`, `aiogram_bot: Bot`
- `BotApp.start`: load active bots from DB; if none and env/legacy `bot_settings.bot_token` present, do **not** invent username silently — bootstrap is Task 7. For empty registry log warning and return.
- Shared `Dispatcher` via existing `build_dispatcher`; `handle_update(update, *, registered: RegisteredBot)` feeds that bot.
- `set_webhook_for(registered, base_domain, path)` using `webhook_url_for_bot` + `secret_token` if secret non-empty.
- `notify_payment_status(..., bot_id: int | None)`: resolve `RegisteredBot` by `bot_id`; if missing, try legacy single bot / log and return.
- Middleware: expect `data` already to contain `hub_bot_id` set by webhook layer **or** read from `event.bot` token map — prefer webhook sets `request`-level; for aiogram, set on `BotApp.handle_update` by storing `current` on a contextvar or passing via middleware init that reads `registry` + matches `data["bot"].token`. Simplest: in `handle_update`, set `contextvars.ContextVar("hub_bot_id")`; middleware reads it into `data["hub_bot_id"]`.

- [ ] **Step 1: Implement `registry.py` + ContextVar helper in same file or `app/bot/bot_context.py`**

```python
# sketch
_hub_bot_id: ContextVar[int | None] = ContextVar("hub_bot_id", default=None)

def set_hub_bot_id(bot_id: int | None) -> Token: ...
def get_hub_bot_id() -> int | None: ...
```

- [ ] **Step 2: Refactor `BotApp`** to multi-bot registry; keep polling mode: only first active bot or env token bot for local polling (document in log).

- [ ] **Step 3: Middleware injects `data["hub_bot_id"] = get_hub_bot_id()`**

- [ ] **Step 4: Manual sanity** — app imports: `python -c "from app.bot.runner import BotApp; print('ok')"`

---

### Task 5: Telegram webhook Host routing

**Files:**
- Modify: `app/api/routers/telegram.py`
- Test: `tests/integration/test_telegram_webhook_multi_bot.py`

**Interfaces:**
- Consumes: `BotApp.registry` (or `get_registered(username)`), `RuntimeSettings.base_domain` / env settings
- On POST: parse `request.headers["host"]` → username → registry; 404 if missing; 401 if secret mismatch; else `handle_update`

- [ ] **Step 1: Write failing integration test**

Use FastAPI `AsyncClient` + override/seed two fake registry entries (or patch `BotApp`). Minimal approach:

```python
async def test_webhook_routes_by_host(client, app):
    # arrange: install FakeBotApp with two usernames on app.state.bot_app
    ...
    r = await client.post(
        "/api/telegram/webhook",
        headers={"host": "alpha.example.com"},
        json={"update_id": 1},
    )
    assert r.status_code == 200
    # assert fake recorded username == "alpha"

async def test_webhook_unknown_host_404(client, app):
    ...
    assert r.status_code == 404

async def test_webhook_bad_secret_401(client, app):
    ...
```

Wire `base_domain` to `example.com` via settings fixture / env.

- [ ] **Step 2: Implement router changes**

Replace global `telegram_webhook_secret` check with per-bot secret. Keep mode check (`TELEGRAM_MODE=webhook`).

- [ ] **Step 3: Tests PASS**

Run: `pytest tests/integration/test_telegram_webhook_multi_bot.py -v`

---

### Task 6: Order attribution (`bot_id` / `channel_id`)

**Files:**
- Modify: `app/application/services/order_service.py`
- Modify: `app/bot/handlers/order.py`
- Modify: `app/api/routers/orders.py` (HTTP create path: `bot_id`/`channel_id` optional/null unless you add API fields — default null for HTTP)
- Modify: payment notify call sites in `app/api/routers/orders.py` to pass `order.bot_id`
- Modify: `app/bot/runner.py` `notify_payment_status` signature
- Test: extend `tests/integration/test_orders.py` or add focused test that create_order stores `bot_id`

**Interfaces:**
- `OrderService.create_order(..., bot_id: int | None = None, channel_id: int | None = None)`
- Handler: `bot_id=data["hub_bot_id"]`; `channel_id` from FSM/callback payload only if already present — v1 DM flow passes `channel_id=None`. If callback data later encodes channel, parse then; do not invent channel.

- [ ] **Step 1: Thread fields through entity → repository → service → handler**

- [ ] **Step 2: Notify uses `order.bot_id`**

```python
await bot_app.notify_payment_status(user.telegram_id, order.id, order.status.value, bot_id=order.bot_id)
```

- [ ] **Step 3: Delivery invites** — when `order.channel_id` set, load channel and prefer `invite_link` / `discussion_invite_link` over env fallbacks inside `notify_payment_status` (small change in runner).

- [ ] **Step 4: Run** `pytest tests/integration/test_orders.py tests/integration/test_payments.py -v` — fix regressions.

---

### Task 7: Bootstrap seed from legacy single-bot config

**Files:**
- Modify: `app/bootstrap.py` (or create `app/infrastructure/db/seed_bots.py` imported from bootstrap)
- Read patterns in existing `ensure_initial_data`

**Behavior:**
1. If `bots` table already has rows → no-op.
2. Else token = `bot_settings.bot_token` or `settings.bot_token`; if empty → no-op.
3. Username = `settings` optional `BOT_USERNAME` / `bot_username` env if you add it; else call Telegram `getMe` with that token (aiogram `Bot(token).get_me()`); on failure log and skip seed.
4. Insert `bots` row with `webhook_secret=settings.telegram_webhook_secret`.
5. If `catalog_channel_id` set → insert one `channels` row linked to that bot with discussion/invite from settings.

- [ ] **Step 1: Implement seed; call from `ensure_initial_data`**

- [ ] **Step 2: Add `bot_username: str = ""` to Settings + `.env.example` as optional override for seed without getMe

- [ ] **Step 3: Smoke** — empty bots + token in test DB → one bot row (unit/integration with mocked getMe if needed)

---

### Task 8: Admin views

**Files:**
- Modify: `app/admin/views.py`
- Modify: `ALL_VIEWS` list at bottom of same file

**Views:**
- `TelegramBotAdmin`: list username, is_active, updated_at; form token/webhook_secret masked like existing `_mask_secret`; category "Telegram"
- `TelegramChannelAdmin`: bot_id, telegram_chat_id, discussion_group_id, is_public, discussion_is_public, invite links, is_active, extra
- `ChannelCourseAdmin`: channel_id, course_id, extra
- `OrderAdmin`: add `bot_id`, `channel_id` to `column_list`
- `AppSettingsAdmin`: keep `backend_url`; add description that bot tokens live under Bots; optional show `extra.base_domain` via existing extra JSON (no new column required — document that `extra.base_domain` overrides)

**Webhook refresh on save (MVP):**  
sqladmin `on_model_change` for bots is best-effort: log “restart app or call reload” if wiring `app.state.bot_app` is awkward. Prefer: add `BotApp.reload_from_db()` and call it from a small admin hook if `request.app` is available; if not reliable in sqladmin, document restart-required for v1 and still `setWebhook` inside `reload_from_db` used at startup.

Minimum for v1 acceptance: startup loads all bots; admin CRUD persists; restart picks up changes. Optional same-process reload if easy.

- [ ] **Step 1: Add three ModelViews + update OrderAdmin**

- [ ] **Step 2: Open `/admin` locally and confirm views render** (manual)

---

### Task 9: RuntimeSettings base_domain + startup setWebhook URLs

**Files:**
- Modify: `app/application/services/runtime_settings.py`
- Modify: `app/bot/runner.py` (use resolved base_domain, not full backend_url host incorrectly)

**Logic:**

```python
base_domain=resolve_base_domain(
    base_domain=_extra_str(extra, "base_domain", env.base_domain),
    backend_url=stored.backend_url if stored and stored.backend_url else env.backend_url,
)
```

Startup `setWebhook` must use `webhook_url_for_bot`, **not** `backend_url + path` (breaking change from single-bot URL shape — intentional per spec).

- [ ] **Step 1: Wire fields**

- [ ] **Step 2: Update any docs that still show single webhook URL** — only if a short note exists in README; otherwise skip. Spec already documents Cloudflare.

---

### Task 10: Verification checklist (no new scope)

- [ ] **Step 1: Unit** `pytest tests/unit/test_domain_host.py -v`

- [ ] **Step 2: Integration** `pytest tests/integration/test_telegram_webhook_multi_bot.py tests/integration/test_orders.py tests/integration/test_payments.py -v`

- [ ] **Step 3: Manual Cloudflare** (ops): `*.base_domain` → origin; two bot usernames; `setWebhook` URLs match; send `/start` to each bot.

- [ ] **Step 4:** `npx graphify hook-rebuild`

- [ ] **Step 5:** Update spec status line to `Implemented` only after user accepts — do not mark done early.

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Host subdomain routing | 1, 5 |
| Webhook URL shape | 1, 4, 9 |
| Base domain precedence | 1, 9 |
| Per-bot webhook_secret | 2, 4, 5 |
| Tables bots/channels/channel_courses + extra | 2, 3 |
| Channel public links | 2, 8 |
| orders.bot_id / channel_id | 2, 3, 6 |
| Shared Dispatcher + registry | 4 |
| Shared Atlos / full DM catalog | unchanged; 6 only attribution |
| Admin CRUD | 8 |
| Legacy seed | 7 |
| Cloudflare | Task 10 ops checklist (no code) |

**Out of scope left out of plan (intentional):** per-category payments, multi-bot polling production, publish pipeline rewiring beyond reading channel IDs later.
