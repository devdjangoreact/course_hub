# Phase 0 Research: Course Hub — FastAPI Backend + Telegram Bot

All items below were resolved before planning; no open NEEDS CLARIFICATION remain.

## Web framework & async runtime

- **Decision**: FastAPI on Uvicorn, fully async.
- **Rationale**: First-class async, Pydantic v2 integration, OpenAPI out of the box, mature
  ecosystem for the admin and webhook endpoints.
- **Alternatives considered**: Litestar (smaller community for this team), Flask (sync-first,
  needs extra glue for async), Django (heavier, sync ORM by default).

## Telegram bot library

- **Decision**: aiogram 3.x.
- **Rationale**: Native asyncio, router/Dispatcher architecture, FSM for multi-step flows (search,
  order), inline keyboards for the category menu. Explicitly requested.
- **Alternatives considered**: python-telegram-bot (good, but aiogram requested and is a clean fit
  with the async stack), Telethon (client/MTProto, overkill for a bot).

## Bot lifecycle vs. web app

- **Decision**: Run the bot inside the FastAPI lifespan in a single container for phase 1, using
  long polling.
- **Rationale**: Simplest deploy on the free-tier host (one container), no public webhook/TLS plumb
  needed for the bot itself; payment webhooks still use the FastAPI HTTP layer. The bot bootstrap is
  isolated so it can move to a separate worker/service later without domain changes.
- **Alternatives considered**: Separate bot process/container (more moving parts now), Telegram
  webhook mode (needs extra routing/secret handling; defer).

## ORM & async DB access

- **Decision**: SQLAlchemy 2.0 async ORM with `aiosqlite` (phase 1) and `asyncpg` (PostgreSQL
  option); Alembic for migrations.
- **Rationale**: Single ORM that supports both SQLite and PostgreSQL; async sessions; switching is a
  `DATABASE_URL` change. Repository pattern hides ORM from domain/application layers.
- **Alternatives considered**: Tortoise ORM (smaller ecosystem), encode/databases + raw SQL (more
  manual), SQLModel (couples models to Pydantic, less control for clean architecture).

## Full-text search

- **Decision**: SQLite FTS5 virtual table over course name + description, kept in sync via triggers
  or repository-side writes; search returns relevance-ranked active courses.
- **Rationale**: FTS5 is built into SQLite, fast, and matches the phase-1 requirement; the search
  behavior is behind a `SearchRepository` interface so a PostgreSQL `tsvector`/`websearch_to_tsquery`
  implementation can replace it without changing callers.
- **Alternatives considered**: LIKE/`%term%` scans (no ranking, slow as catalog grows), external
  engines like Meilisearch/Elasticsearch (operationally heavy for free-tier phase 1).

## Configuration & run profiles

- **Decision**: pydantic-settings with an `APP_ENV` switch (`development` / `production`) and
  per-profile `.env` files; each profile carries its own `BOT_TOKEN`, `DATABASE_URL`, and bot
  settings. Runtime-editable bot settings (token, backend URL) are persisted in the DB and override
  env defaults at runtime.
- **Rationale**: Meets the "dev/test vs prod with different bot tokens" and "edit token + backend
  URL in admin" requirements; configuration-only DB switch.
- **Alternatives considered**: Hardcoded settings (violates secrets rule), single shared token
  (cannot separate test from prod).

## Admin panel & admin accounts

- **Decision**: SQLAdmin (async, SQLAlchemy-native) mounted on the FastAPI app, authenticated
  against a persisted `AdminUser` table (passwords hashed with Passlib/bcrypt). Dedicated views edit
  `BotSettings` and `PaymentSettings`. A first admin is seeded from env credentials on initial run.
- **Rationale**: Provides quick CRUD for categories/courses/orders and settings forms with minimal
  code; "simple admin" requirement; persisted accounts (not just env credentials) allow managing
  admins and storing hashed passwords; integrates with the async engine.
- **Alternatives considered**: Env-only single credential (cannot manage/rotate admins, no DB
  record), hand-rolled Jinja2 + HTMX (more code), FastAPI-Admin (Tortoise-based, wrong ORM), Django
  admin (different framework).

## Search rate limiting

- **Decision**: Limit each Telegram user to 5 searches per rolling 60s window via a `RateLimiter`
  interface; phase-1 implementation is an in-memory per-user sliding counter, swappable for a shared
  store (e.g. Redis) later.
- **Rationale**: Meets FR-003a, protects the DB/FTS from abuse, and keeps a clean seam for scaling
  to multiple workers.
- **Alternatives considered**: No limiting (abuse risk), global limit (penalizes unrelated users),
  Redis now (extra infra for phase 1).

## Development environment (Docker-first)

- **Decision**: All development runs in Docker (code, deps, env inside containers); Poetry is used
  inside the container or locally within the submodule, never globally. `docker compose` provides the
  dev workflow with `.env` mounted/loaded.
- **Rationale**: Reproducible, isolated dev matching production; avoids polluting the host;
  consistent with the infra container deployment model.
- **Alternatives considered**: Global Poetry/venv on host (non-reproducible, pollutes host),
  per-developer manual setup (drift).

## Extensible per-item data

- **Decision**: Every entity carries an optional `extra` JSON column (default `{}`) for
  item-specific data without schema changes.
- **Rationale**: Meets FR-015 and supports future fields per item without migrations for every
  small addition.
- **Alternatives considered**: Separate key/value table (heavier joins), no extension point (every
  field needs a migration).

## Payments

- **Decision**: A `PaymentGateway` interface in the domain with two adapters — a simulated/manual
  confirmation adapter for development/testing and a provider adapter behind a webhook — plus an
  idempotent order-status update keyed by payment reference.
- **Rationale**: Keeps the order lifecycle provider-agnostic and testable; lets phase 1 ship with a
  simulated flow while leaving a clean seam for a real provider.
- **Alternatives considered**: Hardcoding one provider now (couples domain to a vendor), skipping
  the abstraction (blocks testing and future providers).

## Logging

- **Decision**: Loguru with structured, leveled logging; intercept Uvicorn/standard logging;
  never log secrets (tokens, payment keys).
- **Rationale**: Requested; simple configuration, good context capture, integrates with the rest of
  the stack.
- **Alternatives considered**: stdlib logging only (more boilerplate), structlog (capable but extra
  setup vs. requested Loguru).

## Architecture & code quality

- **Decision**: Clean architecture layers (domain/application/infrastructure/presentation),
  repository pattern, dependency injection via FastAPI deps, one construct per file, Pydantic models
  for boundaries, type-annotated throughout, formatted with the project's formatter.
- **Rationale**: Meets the explicit OOP/SOLID/clean-architecture/extensibility/scalability request
  and keeps storage/delivery swappable.
- **Alternatives considered**: Single-module script (not scalable), framework-coupled models in
  handlers (violates SOLID and blocks the DB swap).
