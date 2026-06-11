# Phase 1 Data Model: Course Hub

Storage: SQLAlchemy 2.0 async models. SQLite (phase 1) with an FTS5 virtual table; the same models
map to PostgreSQL by changing `DATABASE_URL`. All timestamps are timezone-aware UTC. Money is stored
as an integer minor unit (e.g. cents) or `Numeric` to avoid float precision issues.

**Shared field**: every persisted entity includes an optional structured field `extra` of type JSON
(`JSON` on SQLite, `JSONB` on PostgreSQL via SQLAlchemy `JSON`), default `{}`, for item-specific data
that needs no schema change (FR-015). The attribute is named `extra` (not `metadata`, which is
reserved by SQLAlchemy Declarative).

## Entities

### Category

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| name | str | required, unique, 1–120 chars |
| extra | JSON | optional item-specific data, default `{}` |
| created_at | datetime | set on create |

Relationships: has many `Course`.

### Course

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| name | str | required, 1–200 chars |
| description | str | required, free text |
| category_id | int (FK → Category) | required |
| price | Numeric/int-minor | required, ≥ 0 |
| link | str (URL) | required, valid URL |
| is_active | bool | default true |
| extra | JSON | optional item-specific data, default `{}` |
| created_at | datetime | set on create |
| updated_at | datetime | set on update |

Relationships: belongs to one `Category`; has many `Order`.
Indexes: `category_id`; FTS5 over (`name`, `description`).

### BotUser

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| telegram_id | int | required, unique |
| username | str \| null | optional |
| full_name | str \| null | optional |
| extra | JSON | optional item-specific data, default `{}` |
| created_at | datetime | set on create |

Relationships: has many `Order`. Persisted so returning users are recognized across sessions
(FR-014).

### Order

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| bot_user_id | int (FK → BotUser) | required |
| course_id | int (FK → Course) | required |
| amount | Numeric/int-minor | required, snapshot of course price at order time |
| status | enum | one of: `pending`, `paid`, `failed`, `cancelled`; default `pending` |
| payment_reference | str \| null | unique when set; used for idempotent updates |
| extra | JSON | optional item-specific data, default `{}` |
| created_at | datetime | set on create |
| updated_at | datetime | set on update |

Relationships: belongs to one `BotUser` and one `Course`.

**State transitions**:

```text
pending → paid       (successful payment confirmation)
pending → failed     (payment provider reports failure)
pending → cancelled  (user/admin cancels)
paid    → (terminal)
failed  → pending    (retry creates/links a new attempt; status reset on retry)
```

Confirmation is idempotent: a repeated callback for the same `payment_reference` does not change a
terminal order again.

### AdminUser (persisted admin account)

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| username | str | required, unique |
| password_hash | str | required; password hashed (e.g. bcrypt/argon2), never plaintext, never logged |
| is_active | bool | default true |
| extra | JSON | optional item-specific data, default `{}` |
| created_at | datetime | set on create |

The admin panel authenticates against this table (FR-006a). A first admin is seeded from env
credentials on initial run.

### BotSettings (runtime-editable, single row)

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | single row (id = 1) |
| bot_token | str (secret) | required to run the bot; never logged |
| backend_url | str (URL) | required, base/callback URL |
| is_active | bool | default true |
| extra | JSON | optional item-specific data, default `{}` |
| updated_at | datetime | set on update |

Env values seed defaults on first run; admin edits override and persist.

### PaymentSettings (runtime-editable, single row)

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | single row (id = 1) |
| provider | str | payment provider identifier (e.g. `simulated`, real provider name) |
| api_key | str (secret) \| null | provider API key; never logged |
| secret_key | str (secret) \| null | provider/webhook secret; never logged |
| currency | str | default currency code (e.g. `USD`) |
| is_active | bool | default true |
| extra | JSON | optional provider-specific options, default `{}` |
| updated_at | datetime | set on update |

Env values seed defaults on first run; admin edits override and persist (FR-007a).

### CourseSearchIndex (SQLite FTS5 virtual table)

- Columns: `name`, `description`, plus `content_rowid` linking to `Course.id`.
- Kept in sync on course create/update/delete (triggers or repository writes).
- Query returns `Course.id` list ranked by FTS5 `rank`, filtered to `is_active = true`.
- PostgreSQL variant (future): a `tsvector` column + GIN index; same `SearchRepository` interface.

## Search rate limiting (FR-003a)

- Each Telegram user may run at most 5 searches per rolling 60-second window.
- Implemented in the bot/application layer behind a `RateLimiter` interface (in-memory per-user
  counter in phase 1; swappable for a shared store later). The 6th attempt within the window is
  rejected with a friendly throttling message.

## Validation rules (from requirements)

- Only `is_active = true` courses are exposed to bot users (lists, search, new orders) — FR-010.
- Search input is trimmed and length-limited; empty/whitespace is rejected — FR-003, FR-011.
- Search is rate-limited to 5/min per user — FR-003a.
- Admin routes require authentication against persisted `AdminUser` accounts — FR-012, FR-006a.
- Admin passwords are stored hashed, never plaintext — FR-006a.
- Payment callbacks are validated and applied idempotently — FR-005, FR-011.
- Secrets (bot token, payment keys) are never written to logs — FR-013.
- Every entity exposes an optional `extra` JSON field — FR-015.
