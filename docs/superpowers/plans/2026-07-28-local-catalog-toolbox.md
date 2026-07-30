# Local Catalog Toolbox + Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local-only catalog toolbox (fixture JSON → private channel post → DB sync) and Vercel bot/email delivery (promo before pay, download link after pay) without deploying parsers or Pyrogram/Playwright to Vercel.

**Architecture:** `tools/catalog/` + `data/catalog/` are source of truth and stay off Vercel via `.vercelignore`. Scripts upsert catalog rows into Postgres (`name`/`description`/`price`/`link` + `extra` refs). The FastAPI bot reads DB only: copies promo from the private channel (or falls back to short description), and on paid webhook sends download link (+ invite) in Telegram and email.

**Tech Stack:** Python 3.12, Pyrogram (local tools only), SQLAlchemy async + existing `Course`/`Category` models, aiogram 3, stdlib `smtplib` for email.

## Global Constraints

- Do not put `tools/` or `data/` content into Vercel deploy; never add pyrogram/playwright to root Poetry / `requirements.txt`.
- Do not implement Flancki/supersliv parsers in this plan (adapters later).
- Do not store `promo.text` or `full_description` bodies in the database.
- Map JSON → DB: `title`→`name`, `short_description`→`description`, `download_link`→`link` and `extra.download_link`; invite/message ids only in `extra`.
- Upsert key: `extra.catalog_slug` (and category matched by `extra.catalog_slug` on category or by unique `categories.name` = `category.title`).
- Do not add automated tests unless the user asks; verify manually.
- Do not read or commit `.env` / `.env.prod`.
- Ask before creating files outside the paths listed in this plan.
- Prefer minimal diffs; no drive-by refactors.
- Code and docs in English; bot user-facing strings may be Ukrainian/English via existing `app/bot/messages/catalog.py`.
- Commit only when the user asks (skip commit steps unless explicitly requested in the session).

## File structure

| File | Responsibility |
|------|----------------|
| `.vercelignore` | Exclude `tools/`, `data/` from Vercel upload |
| `tools/catalog/requirements.txt` | Local-only deps (pyrogram, tgcrypto optional) |
| `tools/catalog/config.py` | Hardcoded/local script parameters (paths, TG api, channel, DB URL env name) |
| `tools/catalog/course_json.py` | Load/save unified course JSON |
| `tools/catalog/create_channel.py` | Create private channel + linked discussion; write ids into config side file or print for paste |
| `tools/catalog/post_channel.py` | Post promo/full from JSON; write `telegram.*` back |
| `tools/catalog/sync_db.py` | Upsert category/course into app DB |
| `data/catalog/categories/test/sample-python-basics.json` | Fixture (already exists; keep schema aligned) |
| `app/domain/repositories/course_repository.py` | Add `update` + `get_by_catalog_slug` |
| `app/infrastructure/db/repositories/course_repository.py` | Implement new methods |
| `app/domain/repositories/category_repository.py` | Add `get_by_name` / `update` if missing |
| `app/infrastructure/db/repositories/category_repository.py` | Implement |
| `app/bot/messages/catalog.py` | Strings: promo button, download after pay, missing download |
| `app/bot/keyboards/catalog.py` | Promo callback button on course detail |
| `app/bot/handlers/categories.py` | Send promo on button / course open |
| `app/bot/delivery.py` | Pure helpers: build download message; resolve promo ids from `extra` |
| `app/bot/runner.py` | Enrich `notify_payment_status` with download/invite when status is `paid` |
| `app/application/services/delivery_mailer.py` | Send post-pay (and optional promo) email via SMTP |
| `app/infrastructure/email/smtp_mailer.py` | stdlib SMTP send |
| `app/core/config.py` | SMTP settings (optional; empty = email disabled) |
| `app/api/routers/orders.py` | After paid notify, also trigger email if configured |
| `README.md` | Short section: local catalog toolbox |

---

### Task 1: Vercel isolation + tools scaffold

**Files:**
- Create: `.vercelignore`
- Create: `tools/catalog/requirements.txt`
- Create: `tools/catalog/config.py`
- Create: `tools/catalog/course_json.py`
- Modify: `README.md` (short subsection only)

**Interfaces:**
- Produces: `tools.catalog.config` module attributes used by later scripts:
  - `CATALOG_ROOT` → repo-relative `data/catalog`
  - `API_ID`, `API_HASH`, `SESSION_NAME`, `BOT_TOKEN` (strings; fill locally)
  - `CHANNEL_ID`, `DISCUSSION_GROUP_ID`, `INVITE_LINK` (nullable ints/str after create)
  - `DATABASE_URL` read from `os.environ["DATABASE_URL"]` at runtime (do not hardcode secrets)
- Produces: `load_course(path: Path) -> dict`, `save_course(path: Path, data: dict) -> None`, `iter_course_json_files(root: Path) -> list[Path]`

- [ ] **Step 1: Create `.vercelignore`**

```
tools
data
```

- [ ] **Step 2: Create `tools/catalog/requirements.txt`**

```
pyrogram>=2.0.106
tgcrypto>=1.2.5
sqlalchemy[asyncio]>=2.0.36
asyncpg>=0.30.0
aiosqlite>=0.20.0
```

(Note: scripts may also run with the app venv that already has SQLAlchemy; pyrogram must not be added to root Poetry.)

- [ ] **Step 3: Create `tools/catalog/config.py`**

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = REPO_ROOT / "data" / "catalog"

# Fill locally before running scripts (do not commit real secrets).
API_ID = 0
API_HASH = ""
SESSION_NAME = "catalog_user"
BOT_TOKEN = ""

# Set by create_channel.py output / paste after first run.
CHANNEL_ID: int | None = None
DISCUSSION_GROUP_ID: int | None = None
INVITE_LINK: str | None = None
```

- [ ] **Step 4: Create `tools/catalog/course_json.py`**

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_course(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_course(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def iter_course_json_files(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("categories/*/*.json") if p.is_file())
```

- [ ] **Step 5: README subsection**

Add under an existing ops/local section (or new short heading):

```markdown
## Local catalog toolbox

Parsing, channel posting, and DB sync live in `tools/catalog/` and `data/catalog/`.
They are excluded from Vercel (see `.vercelignore`). Install tool deps separately:

`pip install -r tools/catalog/requirements.txt`

Do not add pyrogram/playwright to the app Poetry dependencies.
```

- [ ] **Step 6: Manual check**

```bash
python -c "from pathlib import Path; from tools.catalog.course_json import load_course; p=Path('data/catalog/categories/test/sample-python-basics.json'); d=load_course(p); print(d['slug'], d['title'])"
```

Expected: `sample-python-basics Python Basics (sample)`

If `tools` is not a package, run via:

```bash
cd tools/catalog && python -c "from course_json import load_course; ..."
```

Prefer adding empty `tools/__init__.py` and `tools/catalog/__init__.py` only if import path requires it; otherwise keep scripts runnable as `python tools/catalog/sync_db.py` with `sys.path` tweaks inside each script:

```python
# at top of each script after future imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

Use that pattern in Tasks 2–4 scripts.

- [ ] **Step 7: Commit only if user asked**

---

### Task 2: `create_channel.py` (Pyrogram user client)

**Files:**
- Create: `tools/catalog/create_channel.py`

**Interfaces:**
- Consumes: `config.API_ID`, `API_HASH`, `SESSION_NAME`
- Produces: prints `CHANNEL_ID`, `DISCUSSION_GROUP_ID`, `INVITE_LINK`; operator pastes into `config.py`
- Telegram: private channel titled from config constant `CHANNEL_TITLE = "Course Hub Delivery"`; discussion group `CHANNEL_TITLE + " Chat"`

- [ ] **Step 1: Implement script**

```python
"""Create a private channel + linked discussion group. Run locally only."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pyrogram import Client
from pyrogram.raw import functions, types

import config

CHANNEL_TITLE = "Course Hub Delivery"
CHANNEL_ABOUT = "Private delivery channel for Course Hub"


async def main() -> None:
    if not config.API_ID or not config.API_HASH:
        raise SystemExit("Set API_ID and API_HASH in tools/catalog/config.py")

    async with Client(
        config.SESSION_NAME,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
    ) as app:
        channel = await app.create_channel(CHANNEL_TITLE, CHANNEL_ABOUT)
        # Link discussion: create a supergroup and associate (Telegram UI equivalent).
        # Pyrogram helper: create_supergroup then set discussion via raw API.
        chat = await app.create_supergroup(CHANNEL_TITLE + " Chat", "Discussion")
        await app.invoke(
            functions.channels.SetDiscussionGroup(
                broadcast=await app.resolve_peer(channel.id),
                group=await app.resolve_peer(chat.id),
            )
        )
        link = await app.create_chat_invite_link(channel.id, name="course-hub")
        print("CHANNEL_ID =", channel.id)
        print("DISCUSSION_GROUP_ID =", chat.id)
        print("INVITE_LINK =", link.invite_link)
        print("Paste these into tools/catalog/config.py")


if __name__ == "__main__":
    asyncio.run(main())
```

If `SetDiscussionGroup` import path differs in installed Pyrogram version, adjust to the version’s raw functions (verify against installed package docs during implementation). Fail with a clear message if the raw call is unsupported; operator can link discussion manually in Telegram Desktop and still paste IDs/invite.

- [ ] **Step 2: Manual run (operator)**

```bash
pip install -r tools/catalog/requirements.txt
python tools/catalog/create_channel.py
```

Expected: three printed values; first login may ask for phone/code in terminal.

- [ ] **Step 3: Paste into `config.py`**

Set `CHANNEL_ID`, `DISCUSSION_GROUP_ID`, `INVITE_LINK`.

---

### Task 3: `post_channel.py`

**Files:**
- Create: `tools/catalog/post_channel.py`
- Modify: fixture JSON only via script output (no hand-edit required)

**Interfaces:**
- Consumes: course JSON path (default: fixture), `config.CHANNEL_ID`, `INVITE_LINK`, Pyrogram session
- Produces: updates course `telegram` block:
  - `channel_id`, `discussion_group_id`, `invite_link`
  - `promo_message_ids: list[int]`
  - `full_message_ids: list[int]`
- Posts HTML/text: send `promo.text` then `full_description` as separate messages (media optional; skip missing media files with a warning)

- [ ] **Step 1: Implement script**

```python
"""Post promo + full description from course JSON into the private channel."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pyrogram import Client

import config
from course_json import load_course, save_course

DEFAULT_COURSE = (
    config.CATALOG_ROOT / "categories" / "test" / "sample-python-basics.json"
)


async def main() -> None:
    path = DEFAULT_COURSE
    if config.CHANNEL_ID is None:
        raise SystemExit("Set CHANNEL_ID in config.py (run create_channel.py first)")

    data = load_course(path)
    async with Client(
        config.SESSION_NAME,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
    ) as app:
        promo = await app.send_message(
            config.CHANNEL_ID,
            data["promo"]["text"],
        )
        full = await app.send_message(
            config.CHANNEL_ID,
            data["full_description"],
        )
        data["telegram"] = {
            "channel_id": config.CHANNEL_ID,
            "discussion_group_id": config.DISCUSSION_GROUP_ID,
            "invite_link": config.INVITE_LINK,
            "promo_message_ids": [promo.id],
            "full_message_ids": [full.id],
        }
        save_course(path, data)
        print("Updated", path)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Manual run**

```bash
python tools/catalog/post_channel.py
```

Expected: fixture JSON `telegram.promo_message_ids` non-empty; messages visible in channel.

---

### Task 4: `sync_db.py` + repository upsert support

**Files:**
- Create: `tools/catalog/sync_db.py`
- Modify: `app/domain/repositories/course_repository.py`
- Modify: `app/infrastructure/db/repositories/course_repository.py`
- Modify: `app/domain/repositories/category_repository.py`
- Modify: `app/infrastructure/db/repositories/category_repository.py`

**Interfaces:**
- CourseRepository gains:
  - `async def get_by_catalog_slug(self, slug: str) -> Course | None`
  - `async def update(self, course: Course) -> Course`
- CategoryRepository gains:
  - `async def get_by_name(self, name: str) -> Category | None`
  - `async def update(self, category: Category) -> Category` (only if needed; else recreate fields on add only)
- `sync_db` upserts from all JSON under `CATALOG_ROOT` or single path; sets:
  - `extra["catalog_slug"] = slug`
  - `extra["download_link"]`, `extra["invite_link"]`, `extra["channel_id"]`, `extra["promo_message_ids"]`
  - `link = download_link`
  - does not write promo/full bodies

- [ ] **Step 1: Extend category repository**

In domain ABC add:

```python
async def get_by_name(self, name: str) -> Category | None: ...
```

Implement with `select(CategoryModel).where(CategoryModel.name == name)`.

- [ ] **Step 2: Extend course repository**

```python
async def get_by_catalog_slug(self, slug: str) -> Course | None: ...
async def update(self, course: Course) -> Course: ...
```

Implementation sketch for slug lookup (works on SQLite + Postgres with SQLAlchemy JSON):

```python
stmt = select(CourseModel).where(
    CourseModel.extra["catalog_slug"].as_string() == slug
)
```

`update`: load by `course.id`, assign fields + `extra`, `flush`, return entity.

- [ ] **Step 3: Implement `sync_db.py`**

Use app session factory:

```python
"""Upsert catalog JSON into Course Hub DB. Local only."""
from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import config
from course_json import iter_course_json_files, load_course

from app.domain.entities.category import Category
from app.domain.entities.course import Course
from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository


async def sync_one(session, data: dict) -> None:
    categories = SqlCategoryRepository(session)
    courses = SqlCourseRepository(session)
    cat_title = data["category"]["title"]
    category = await categories.get_by_name(cat_title)
    if category is None:
        category = await categories.add(
            Category(id=None, name=cat_title, extra={"catalog_slug": data["category"]["slug"]})
        )
    slug = data["slug"]
    download = data["download_link"]
    tg = data.get("telegram") or {}
    extra = {
        "catalog_slug": slug,
        "download_link": download,
        "invite_link": tg.get("invite_link"),
        "channel_id": tg.get("channel_id"),
        "promo_message_ids": tg.get("promo_message_ids") or [],
    }
    existing = await courses.get_by_catalog_slug(slug)
    if existing is None:
        assert category.id is not None
        await courses.add(
            Course(
                id=None,
                name=data["title"],
                description=data["short_description"],
                category_id=category.id,
                price=Decimal(str(data["price"])),
                link=download,
                is_active=True,
                extra=extra,
            )
        )
    else:
        existing.name = data["title"]
        existing.description = data["short_description"]
        existing.price = Decimal(str(data["price"]))
        existing.link = download
        existing.extra = {**existing.extra, **extra}
        await courses.update(existing)


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL in the environment")
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    files = iter_course_json_files(config.CATALOG_ROOT)
    async with session_factory() as session:
        for path in files:
            await sync_one(session, load_course(path))
            print("synced", path.name)
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

Align `Category` entity constructor with the real dataclass fields in `app/domain/entities/category.py` during implementation (read file; do not invent fields).

- [ ] **Step 4: Manual sync against local SQLite**

```bash
# from repo root, with app venv
set DATABASE_URL=sqlite+aiosqlite:///./course_hub.db
python tools/catalog/sync_db.py
```

Expected: prints `synced sample-python-basics.json`; course visible via admin or:

```bash
python -c "..."  # optional quick select
```

---

### Task 5: Bot promo before payment

**Files:**
- Create: `app/bot/delivery.py`
- Modify: `app/bot/messages/catalog.py`
- Modify: `app/bot/keyboards/catalog.py`
- Modify: `app/bot/handlers/categories.py`

**Interfaces:**
- `delivery.promo_message_ids(extra: dict) -> list[int]`
- `delivery.channel_id(extra: dict) -> int | None`
- `delivery.download_link(course_link: str, extra: dict) -> str` — prefer `extra["download_link"]` else `course_link`
- `delivery.invite_link(extra: dict) -> str | None`
- Keyboard: add button `course:promo:{id}` labeled via `promo_materials`
- Handler: on `course:promo:{id}`, `copy_message` from `channel_id` for each promo id; on failure send `short_description` only

- [ ] **Step 1: Add `app/bot/delivery.py`**

```python
from typing import Any


def promo_message_ids(extra: dict[str, Any]) -> list[int]:
    raw = extra.get("promo_message_ids") or []
    return [int(x) for x in raw]


def channel_id(extra: dict[str, Any]) -> int | None:
    value = extra.get("channel_id")
    return int(value) if value is not None else None


def download_link(course_link: str, extra: dict[str, Any]) -> str:
    value = extra.get("download_link")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return course_link


def invite_link(extra: dict[str, Any]) -> str | None:
    value = extra.get("invite_link")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
```

- [ ] **Step 2: Messages + keyboard**

Add keys `promo_materials`, `promo_unavailable`, `download_ready`, `invite_line` (uk + en) in `catalog.py`.

Extend `course_detail_keyboard` with promo button:

```python
InlineKeyboardButton(
    text=message(language_code, "promo_materials"),
    callback_data=f"course:promo:{course_id}",
)
```

- [ ] **Step 3: Handler**

New callback `F.data.startswith("course:promo:")`:
1. Load localized course.
2. Resolve channel + promo ids via `delivery`.
3. If bot + channel + ids: `await callback.bot.copy_message(chat_id=user_id, from_chat_id=channel_id, message_id=mid)` for each id.
4. Else: `answer` with course description / `promo_unavailable`.

Keep existing `course:{id}` card as short description (no automatic promo flood on every open).

- [ ] **Step 4: Manual check in bot**

Open sample course → tap promo → receive channel copy or fallback text.

---

### Task 6: Post-payment download in bot (+ invite)

**Files:**
- Modify: `app/bot/runner.py`
- Modify: `app/bot/messages/catalog.py` (if not done)
- Modify: `app/api/routers/orders.py` only if notify signature must change
- Modify: `app/application/services/order_service.py` if need course on notify

**Interfaces:**
- Change `BotApp.notify_payment_status` to accept optional delivery fields **or** load order→course inside notify when `status == "paid"`:
  - send status line (existing)
  - send download URL message
  - send invite link if present
- If download missing: send static `download_missing` message and log error

- [ ] **Step 1: Enrich notify**

Inside `notify_payment_status`, when `status == "paid"` (compare to `OrderStatus.PAID.value`):
1. Open DB session; load order by id; load course by `order.course_id`.
2. Build text with `download_link(course.link, course.extra)` and optional `invite_link`.
3. `send_message` to `telegram_id`.

Keep failed/cancelled as status-only messages.

- [ ] **Step 2: Manual check**

Use existing `/payments/simulate` in development or test webhook to mark order paid; confirm DM contains download URL.

---

### Task 7: Email after payment (SMTP) + optional promo email hook

**Files:**
- Create: `app/infrastructure/email/smtp_mailer.py`
- Create: `app/application/services/delivery_mailer.py`
- Modify: `app/core/config.py`
- Modify: `app/bot/runner.py` or `app/api/routers/orders.py` to call mailer after paid
- Modify: `.env.example` / `.env.dev.example` / `.env.prod.example` (document keys only)

**Interfaces:**
- Settings (defaults empty/disabled):
  - `smtp_host: str = ""`
  - `smtp_port: int = 587`
  - `smtp_user: str = ""`
  - `smtp_password: str = ""`
  - `smtp_from: str = ""`
  - `smtp_use_tls: bool = True`
- `SmtpMailer.send(to: str, subject: str, body: str) -> None` — no-op log if host empty
- `DeliveryMailer.send_paid_course(to: str, course_name: str, download_url: str, invite: str | None) -> None`
- Buyer email: reuse `payment_email(user.extra)` from lava helpers; if missing, skip email and log

- [ ] **Step 1: Config fields**

Add SMTP fields to `Settings` with env names `SMTP_HOST`, etc.

- [ ] **Step 2: `smtp_mailer.py`**

```python
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class SmtpMailer:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_addr
        self._use_tls = use_tls

    @property
    def enabled(self) -> bool:
        return bool(self._host and self._from)

    def send(self, to: str, subject: str, body: str) -> None:
        if not self.enabled:
            logger.info("SMTP disabled; skip email to %s", to)
            return
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(msg)
```

- [ ] **Step 3: Call after paid**

From `notify_payment_status` path or orders webhook after `applied` and `paid`: construct mailer from settings; send; catch exceptions, log, do not raise (payment must stay applied).

- [ ] **Step 4: Optional promo email**

Add bot callback `course:promo_email:{id}` only if user has saved payment email; send `short_description` + note (not full channel media). If no email, answer with prompt to set email via order flow. Keep minimal.

- [ ] **Step 5: Manual check**

With SMTP empty: paid flow still works; logs “SMTP disabled”. With SMTP configured in local env: receive mail containing download URL.

---

### Task 8: Spec status + final manual walkthrough

**Files:**
- Modify: `docs/superpowers/specs/2026-07-28-local-catalog-toolbox-design.md` status line to `Implemented (first vertical slice)` when done

- [ ] **Step 1: End-to-end checklist**

1. Fixture JSON loads.
2. Channel created / ids in config (or skipped if reusing).
3. `post_channel` writes message ids.
4. `sync_db` upserts course.
5. Bot: course card + promo button.
6. Simulate paid → bot download (+ invite) + email skip/send.
7. Confirm Vercel deploy deps unchanged (no pyrogram in `pyproject.toml`).

- [ ] **Step 2: Update spec status**

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Local toolbox off Vercel / `.vercelignore` | Task 1 |
| Unified JSON + fixture | Task 1 (existing fixture) + Task 3 write-back |
| create_channel | Task 2 |
| post_channel | Task 3 |
| sync_db metadata only | Task 4 |
| Promo before pay in bot | Task 5 |
| Download (+ invite) after pay in bot | Task 6 |
| Email after pay (+ optional promo email) | Task 7 |
| Parsers Flancki/supersliv | Out of scope (explicit) |
| No full bodies in DB | Task 4 |

## Placeholder / consistency check

- Extra keys locked: `catalog_slug`, `download_link`, `invite_link`, `channel_id`, `promo_message_ids`.
- Delivery helpers used by Tasks 5–7 share `app/bot/delivery.py`.
- No TBD steps left; Pyrogram discussion-link may need version-specific raw API tweak called out in Task 2.
