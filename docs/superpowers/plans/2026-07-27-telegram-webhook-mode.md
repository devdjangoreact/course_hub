# Telegram Webhook Mode + Supabase Free Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add env-driven Telegram `webhook` (default) vs `polling` modes with optional auto `setWebhook`/`deleteWebhook`, plus Supabase Free `DATABASE_URL` docs for Vercel-ready deploys.

**Architecture:** Keep a single `BotApp` that owns Bot + Dispatcher. On startup, branch on `TELEGRAM_MODE`: webhook registers Telegram webhook and serves updates via `POST` route; polling deletes webhook (if auto) and runs `start_polling`. One bot per process; multi-bot stays backlog.

**Tech Stack:** FastAPI, aiogram 3.x, pydantic-settings, SQLAlchemy async, Supabase Postgres (URL only).

## Global Constraints

- Single bot per env profile; do not implement multi-bot.
- Default `TELEGRAM_MODE=webhook`; `TELEGRAM_AUTO_SET_WEBHOOK=true` controls both set and delete.
- Keep `MemoryStorage` and `InMemoryRateLimiter` (no Upstash).
- Do not add automated tests unless the user asks (spec + user rule); verify manually.
- Do not create `vercel.json` unless the user asks.
- Do not read or commit `.env`.
- Ask before creating files outside the paths listed in this plan.
- Prefer minimal diffs; no drive-by refactors.
- Code and docs in English; user-facing chat may be Ukrainian/English.

## File structure

| File | Responsibility |
|------|----------------|
| `app/core/config.py` | `TelegramMode` enum + new settings fields |
| `app/bot/runner.py` | Mode start/stop, set/delete webhook, `handle_update` |
| `app/api/routers/telegram.py` | HTTP webhook endpoint (create) |
| `app/main.py` | Include telegram router; lifespan already calls `BotApp.start/stop` |
| `app/core/database.py` | SSL connect_args when URL host is Supabase |
| `.env.example`, `.env.dev.example`, `.env.prod.example` | Document new vars + Supabase URL |
| `README.md` | Short bot-mode + Supabase section |
| `tests/conftest.py` | Disable auto webhook in tests for safety |

---

### Task 1: Settings for Telegram mode

**Files:**
- Modify: `app/core/config.py`
- Modify: `tests/conftest.py` (safety env only)

**Interfaces:**
- Produces: `TelegramMode` (`StrEnum`: `WEBHOOK = "webhook"`, `POLLING = "polling"`)
- Produces on `Settings`:
  - `telegram_mode: TelegramMode = TelegramMode.WEBHOOK`
  - `telegram_auto_set_webhook: bool = True`
  - `telegram_webhook_path: str = "/api/telegram/webhook"`
  - `telegram_webhook_secret: str = ""`

- [ ] **Step 1: Add enum and fields to `app/core/config.py`**

After `AppEnv`, add:

```python
class TelegramMode(StrEnum):
    WEBHOOK = "webhook"
    POLLING = "polling"
```

Inside `Settings`, after `bot_token` / `backend_url` (or near other bot settings), add:

```python
    telegram_mode: TelegramMode = TelegramMode.WEBHOOK
    telegram_auto_set_webhook: bool = True
    telegram_webhook_path: str = "/api/telegram/webhook"
    telegram_webhook_secret: str = ""
```

Keep existing imports; `StrEnum` is already imported.

- [ ] **Step 2: Harden test fixture env**

In `tests/conftest.py` inside the `app` fixture, after other `monkeypatch.setenv` calls, add:

```python
    monkeypatch.setenv("TELEGRAM_MODE", "webhook")
    monkeypatch.setenv("TELEGRAM_AUTO_SET_WEBHOOK", "false")
```

(`BOT_TOKEN` stays empty so Telegram API is not called.)

- [ ] **Step 3: Smoke-check settings load**

Run:

```bash
python -c "from app.core.config import get_settings, TelegramMode; get_settings.cache_clear(); s=get_settings(); print(s.telegram_mode, s.telegram_auto_set_webhook, s.telegram_webhook_path)"
```

Expected: `TelegramMode.WEBHOOK True /api/telegram/webhook` (or `webhook True /api/telegram/webhook` depending on print).

- [ ] **Step 4: Commit**

```bash
git add app/core/config.py tests/conftest.py
git commit -m "feat: add Telegram mode settings (webhook default)"
```

---

### Task 2: BotApp webhook/polling lifecycle

**Files:**
- Modify: `app/bot/runner.py`

**Interfaces:**
- Consumes: `Settings.telegram_mode`, `telegram_auto_set_webhook`, `telegram_webhook_path`, `telegram_webhook_secret`, `backend_url`; DB `BotSettings.bot_token` / `backend_url` as today
- Produces:
  - `async def start(self) -> None` — mode-aware
  - `async def stop(self) -> None` — mode-aware
  - `async def handle_update(self, update: Update) -> None` — feeds dispatcher
  - `async def notify_payment_status(...)` — unchanged behaviour

- [ ] **Step 1: Extend imports and helpers in `app/bot/runner.py`**

Ensure these imports exist:

```python
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from loguru import logger

from app.core.config import TelegramMode
```

Add private helpers on `BotApp` (same class):

```python
    async def _resolve_backend_url(self) -> str:
        async with self._runtime.database.session_factory() as session:
            stored = await SqlBotSettingsRepository(session).get()
        if stored is not None and stored.backend_url:
            return stored.backend_url.rstrip("/")
        return self._runtime.env_settings.backend_url.rstrip("/")

    def _webhook_url(self, backend_url: str) -> str:
        path = self._runtime.env_settings.telegram_webhook_path
        if not path.startswith("/"):
            path = "/" + path
        return f"{backend_url}{path}"
```

- [ ] **Step 2: Rewrite `start` / `stop` and add `handle_update`**

Replace `start` / `stop` with:

```python
    async def start(self) -> None:
        token = await self._resolve_token()
        if not token:
            logger.warning("Bot token is not configured; Telegram bot is disabled.")
            return
        settings = self._runtime.env_settings
        self._bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self._dispatcher = build_dispatcher(self._runtime)

        if settings.telegram_mode is TelegramMode.WEBHOOK:
            if settings.telegram_auto_set_webhook:
                url = self._webhook_url(await self._resolve_backend_url())
                secret = settings.telegram_webhook_secret or None
                await self._bot.set_webhook(url=url, secret_token=secret)
                logger.info("Telegram webhook set to {}", url)
            else:
                logger.info("Telegram webhook mode (auto-set disabled).")
            return

        if settings.telegram_auto_set_webhook:
            await self._bot.delete_webhook(drop_pending_updates=False)
            logger.info("Telegram webhook deleted for polling mode.")
        self._task = asyncio.create_task(self._dispatcher.start_polling(self._bot))
        logger.info("Telegram bot started (long polling).")

    async def stop(self) -> None:
        if self._dispatcher is not None and self._task is not None:
            await self._dispatcher.stop_polling()
            self._task.cancel()
            self._task = None
        if self._bot is not None:
            await self._bot.session.close()
        logger.info("Telegram bot stopped.")

    async def handle_update(self, update: Update) -> None:
        if self._bot is None or self._dispatcher is None:
            logger.warning("Ignoring Telegram update; bot is not started.")
            return
        await self._dispatcher.feed_update(self._bot, update)
```

Keep `notify_payment_status` and `build_dispatcher` unchanged.

- [ ] **Step 3: Syntax check**

Run:

```bash
python -c "from app.bot.runner import BotApp; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add app/bot/runner.py
git commit -m "feat: support Telegram webhook and polling modes in BotApp"
```

---

### Task 3: HTTP Telegram webhook router

**Files:**
- Create: `app/api/routers/telegram.py`
- Modify: `app/main.py`
- Modify: `app/api/routers/__init__.py` only if other routers are exported there (currently empty — leave empty unless needed)

**Interfaces:**
- Consumes: `request.app.state.bot_app` (`BotApp`), `request.app.state.settings` (`Settings`)
- Produces: FastAPI route `POST {telegram_webhook_path}` registered on the app

- [ ] **Step 1: Create `app/api/routers/telegram.py`**

```python
from fastapi import APIRouter, Header, HTTPException, Request
from aiogram.types import Update

from app.core.config import TelegramMode

router = APIRouter(tags=["telegram"])


def build_telegram_router(webhook_path: str) -> APIRouter:
    path = webhook_path if webhook_path.startswith("/") else f"/{webhook_path}"
    telegram_router = APIRouter(tags=["telegram"])

    @telegram_router.post(path)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        settings = request.app.state.settings
        if settings.telegram_mode is not TelegramMode.WEBHOOK:
            raise HTTPException(status_code=404, detail="Telegram webhook disabled")

        expected = settings.telegram_webhook_secret
        if expected and x_telegram_bot_api_secret_token != expected:
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

        bot_app = getattr(request.app.state, "bot_app", None)
        if bot_app is None:
            raise HTTPException(status_code=503, detail="Bot is not ready")

        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": getattr(bot_app, "_bot", None)})
        await bot_app.handle_update(update)
        return {"ok": True}

    return telegram_router
```

If `Update.model_validate(..., context=...)` fails against installed aiogram version, fall back to:

```python
        update = Update(**payload)
```

or aiogram’s recommended parse helper for that version — keep validation minimal and working.

Remove unused module-level `router` if only `build_telegram_router` is used (prefer only the factory to avoid dead code):

Final file should export **only** `build_telegram_router` (no unused `router` global).

- [ ] **Step 2: Register router in `app/main.py`**

Add import:

```python
from app.api.routers.telegram import build_telegram_router
```

Inside `create_app()`, after other `include_router` calls:

```python
    app.include_router(build_telegram_router(settings.telegram_webhook_path))
```

Lifespan already calls `bot_app.start()` / `stop()` — no structural change required beyond ensuring `app.state.bot_app` exists before requests (already true after startup).

- [ ] **Step 3: Manual route check (no Telegram token needed)**

Start app locally with empty/disabled bot or:

```bash
# from project venv / docker as you normally run
python -c "from app.main import create_app; app=create_app(); print([r.path for r in app.routes if hasattr(r,'path') and 'telegram' in r.path])"
```

Expected: list containing `/api/telegram/webhook`.

Optional httpx against running server with `TELEGRAM_MODE=polling` → POST webhook expects `404`.

- [ ] **Step 4: Commit**

```bash
git add app/api/routers/telegram.py app/main.py
git commit -m "feat: add Telegram webhook HTTP endpoint"
```

---

### Task 4: Supabase SSL connect args

**Files:**
- Modify: `app/core/database.py`

**Interfaces:**
- Consumes: `Settings.database_url`, `Settings.is_sqlite`
- Produces: engine with `ssl=True` connect_args when host contains `supabase.com`

- [ ] **Step 1: Update `create_engine` in `app/core/database.py`**

Replace connect_args construction with:

```python
def create_engine(settings: Settings) -> AsyncEngine:
    connect_args: dict = {}
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False
    elif "supabase.com" in settings.database_url:
        # Supabase requires TLS; keep local Docker Postgres unaffected.
        connect_args["ssl"] = True
    return create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        connect_args=connect_args,
    )
```

- [ ] **Step 2: Import/syntax check**

```bash
python -c "from app.core.database import create_engine; from app.core.config import Settings; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/core/database.py
git commit -m "fix: enable TLS for Supabase Postgres connections"
```

---

### Task 5: Env examples + README

**Files:**
- Modify: `.env.example`
- Modify: `.env.dev.example`
- Modify: `.env.prod.example`
- Modify: `README.md`

**Interfaces:**
- Produces: documented defaults matching Task 1; prod Supabase pooler example; operator notes for mode switching

- [ ] **Step 1: Update `.env.example`**

After the Telegram bot block (`BOT_TOKEN` / `BACKEND_URL`), add:

```text
# Telegram update transport: webhook (default, Vercel/serverless) | polling (local/VPS)
TELEGRAM_MODE=webhook
# On startup: webhook -> setWebhook(BACKEND_URL+path); polling -> deleteWebhook
TELEGRAM_AUTO_SET_WEBHOOK=true
TELEGRAM_WEBHOOK_PATH=/api/telegram/webhook
# Optional shared secret; Telegram sends X-Telegram-Bot-Api-Secret-Token
TELEGRAM_WEBHOOK_SECRET=

# Database notes:
# Supabase Free (Vercel) Transaction pooler example:
# DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
# Direct (migrations if pooler blocks DDL):
# DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

Keep existing SQLite default `DATABASE_URL` as-is.

- [ ] **Step 2: Update `.env.dev.example`**

Add (dev-friendly override — polling without public URL):

```text
TELEGRAM_MODE=polling
TELEGRAM_AUTO_SET_WEBHOOK=true
TELEGRAM_WEBHOOK_PATH=/api/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=
```

Comment: for local webhook + Cloudflare Tunnel, set `TELEGRAM_MODE=webhook` and `BACKEND_URL=https://<tunnel>`.

- [ ] **Step 3: Update `.env.prod.example`**

Replace SQLite-centric DB comments with:

```text
# Supabase Free — Transaction pooler (recommended for Vercel/serverless)
# DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
# Direct connection (Alembic/DDL from laptop if needed):
# DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
DATABASE_URL=sqlite+aiosqlite:///./course_hub.db
```

Add Telegram mode block for production:

```text
TELEGRAM_MODE=webhook
TELEGRAM_AUTO_SET_WEBHOOK=true
TELEGRAM_WEBHOOK_PATH=/api/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=
```

Ensure `BACKEND_URL` comment says it must be the public HTTPS origin used for `setWebhook`.

- [ ] **Step 4: Update `README.md`**

After Configuration (or near bot notes), add a short section:

```markdown
## Telegram bot modes

Course Hub supports two update transports via env:

- `TELEGRAM_MODE=webhook` (default) — Telegram calls `POST {BACKEND_URL}{TELEGRAM_WEBHOOK_PATH}`.
- `TELEGRAM_MODE=polling` — long polling inside the app process (local/VPS).

When `TELEGRAM_AUTO_SET_WEBHOOK=true` (default):

- webhook mode calls Telegram `setWebhook` on startup (rebinds after `BACKEND_URL` changes, e.g. Cloudflare Tunnel ↔ Vercel);
- polling mode calls `deleteWebhook` so an old hook cannot conflict.

Optional `TELEGRAM_WEBHOOK_SECRET` must match Telegram header `X-Telegram-Bot-Api-Secret-Token`.

Local webhook testing: run the API, expose it with Cloudflare Tunnel, set `BACKEND_URL` to the tunnel HTTPS URL, restart so auto-set rebinds the bot.

## Supabase (production database)

Point `DATABASE_URL` at Supabase Free Postgres (asyncpg). Prefer the Transaction pooler URL on port `6543` for serverless. TLS is enabled automatically when the URL host contains `supabase.com`.
```

Keep existing SQLite/Postgres switch paragraph; align wording so it does not contradict.

- [ ] **Step 5: Commit**

```bash
git add .env.example .env.dev.example .env.prod.example README.md
git commit -m "docs: document Telegram webhook mode and Supabase Free URL"
```

---

### Task 6: End-to-end operator verification

**Files:** none (verification only)

- [ ] **Step 1: Polling path (local)**

1. In `.env`: `TELEGRAM_MODE=polling`, `TELEGRAM_AUTO_SET_WEBHOOK=true`, valid `BOT_TOKEN`.
2. Start app (`docker compose up` or uvicorn as usual).
3. Confirm logs: webhook deleted (or equivalent) and `long polling`.
4. Send `/start` to the bot — handlers respond.

- [ ] **Step 2: Webhook path (tunnel or staging)**

1. Set `TELEGRAM_MODE=webhook`, `TELEGRAM_AUTO_SET_WEBHOOK=true`, `BACKEND_URL=https://<public>`.
2. Restart app; confirm log `Telegram webhook set to https://.../api/telegram/webhook`.
3. POST a minimal fake update without secret (if secret empty) or with correct secret — expect `{"ok": true}` (update may no-op).
4. Wrong secret → `401`. With `TELEGRAM_MODE=polling` → `404` on same path.

- [ ] **Step 3: Rebind check**

Change `BACKEND_URL` to a new public URL, restart with auto-set on — Telegram should target the new URL (confirm via `getWebhookInfo` with Bot API or bot behaviour).

- [ ] **Step 4: Final commit only if fixes were needed**

If verification found bugs, fix minimally and commit with a focused message (e.g. `fix: correct Telegram Update parsing on webhook`). If nothing to fix, do not create an empty commit.

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| `TELEGRAM_MODE` default webhook | Task 1 |
| Auto set/delete via `TELEGRAM_AUTO_SET_WEBHOOK` | Task 2 |
| Webhook HTTP path + secret header | Task 3 |
| No polling in webhook mode | Task 2 |
| Payment notify still works | Task 2 (Bot kept without polling) |
| Supabase Free URL docs | Task 5 |
| TLS for supabase.com | Task 4 |
| README modes + rebind | Task 5 |
| Multi-bot backlog only | Global Constraints / no task |
| No Upstash / no forced tests / no vercel.json | Global Constraints |

No TBD placeholders. Method names consistent: `handle_update`, `build_telegram_router`, `TelegramMode`.
