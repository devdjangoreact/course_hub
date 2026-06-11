# Implementation Plan: Course Hub — FastAPI Backend + Telegram Bot

**Branch**: `001-fastapi-telegram-bot` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-fastapi-telegram-bot/spec.md`

## Summary

Build an async Python service inside the `course_hub` repository that serves a course catalog
(grouped by category, with full-text search) through a Telegram bot, supports orders and payments,
and ships a simple authenticated web admin for managing categories/courses/orders and editing bot
settings (bot token, backend URL). The codebase follows clean architecture (domain → application →
infrastructure → presentation) with the repository pattern and SOLID boundaries so the storage and
delivery mechanisms are swappable. Two run profiles (development/testing and production) are selected
purely by environment configuration, each with its own bot token. Storage is SQLite (async) in
phase 1 with full-text search via FTS5, and the persistence layer is abstracted so PostgreSQL can be
enabled by changing only the `.env` database URL.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Uvicorn, SQLAlchemy 2.0 (async), Alembic, aiosqlite (dev/phase 1)
/ asyncpg (PostgreSQL option), aiogram 3.x, Pydantic v2 + pydantic-settings, SQLAdmin (admin UI),
Passlib/bcrypt (admin password hashing), Loguru, HTTPX. Dependency management with Poetry.

**Storage**: SQLite via `aiosqlite` (async) in phase 1; full-text search via SQLite FTS5 virtual
table kept in sync with the courses table. Switchable to PostgreSQL (`asyncpg`) by changing
`DATABASE_URL` only; Alembic manages schema migrations.

**Testing**: pytest + pytest-asyncio; HTTPX `AsyncClient` for API; aiogram test utilities for bot
handlers; SQLite in-memory/temp file for fast async DB tests. Tests are **required**: all HTTP
endpoints and the full payment lifecycle must be covered (FR-016, SC-008).

**Development environment**: Docker-first. Code, dependencies, and environment run inside containers
during development; Poetry is used **inside the container** (or locally within this submodule
project) and is **never installed globally**.

**Target Platform**: Linux container (Docker), deployed behind the existing infra Traefik routing
for the `course_hub` domain.

**Project Type**: Async web service (FastAPI API + web admin) plus a long-running Telegram bot
worker, in a single repository.

**Performance Goals**: Search returns in < 1s on the phase-1 catalog; bot responds to menu/category
actions promptly under typical free-tier load.

**Constraints**: Fully async end-to-end (DB, HTTP, bot); no blocking I/O in request/handler paths;
no secrets in source control; single small container footprint compatible with the free-tier host;
storage swap (SQLite ↔ PostgreSQL) must require configuration only.

**Scale/Scope**: Phase 1 — single bot, single admin user, modest catalog (hundreds of courses),
low-to-moderate concurrent Telegram traffic.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`infra` `.specify/memory/constitution.md`, v1.3.0) governs the
**infrastructure** project, where each app-repo is a build-only static `nginx:alpine` site. This
feature turns `course_hub` into a dynamic application, which is a deliberate, scoped deviation from
the "static `index.html` only" assumption. The deployment-authority principles still hold and are
respected:

| # | Principle | Plan compliance |
|---|-----------|-----------------|
| I | Repository Responsibility Separation | All app code lives in the `course_hub` app-repo; no deploy/Terraform/Traefik config is added here. PASS |
| II | Single Source of Deployment Truth | Deployment still originates from `infra` via `repository_dispatch`; this repo only builds/pushes its image. PASS |
| III | Domain-Isolated Single-Server Routing | Container exposes no host ports; routed only via Traefik on the `course_hub` domain. PASS |
| IV | Secrets Never Touch Source Control | Bot tokens, DB URLs, payment keys come from env/secrets; `.env*` git-ignored; only `.env.example` committed. PASS |
| VI | Reproducible, Pinned Containers | Image built and pushed to ECR Public with SHA tag; dependencies pinned via Poetry lock. PASS |
| VII | Automated Validation Gates | Existing infra HTTPS/DNS/digest gates apply; app adds a `/health` endpoint for validation. PASS |

Deviation (static-site assumption) is recorded in Complexity Tracking below.

## Project Structure

### Documentation (this feature)

```text
specs/001-fastapi-telegram-bot/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── http-api.md
│   ├── bot-commands.md
│   └── payment-webhook.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root: `course_hub/`)

```text
course_hub/
├── app/
│   ├── main.py                  # FastAPI app factory + lifespan (starts/stops bot)
│   ├── core/
│   │   ├── config.py            # pydantic-settings (APP_ENV, DATABASE_URL, BOT_TOKEN, ...)
│   │   ├── logging.py           # Loguru setup
│   │   └── database.py          # async engine + session factory (SQLite/PostgreSQL)
│   ├── domain/                  # entities + repository interfaces (ports), no framework code
│   │   ├── entities/
│   │   └── repositories/
│   ├── application/             # use cases / services (pure, orchestration)
│   │   └── services/
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── models/          # SQLAlchemy models (one per file, each with `extra` JSON)
│   │   │   ├── repositories/    # repository implementations
│   │   │   └── search/          # FTS5 sync + search query (PG tsvector adapter later)
│   │   ├── payments/            # payment gateway adapter (provider + simulated)
│   │   ├── ratelimit/           # per-user search rate limiter (5/min)
│   │   └── settings_store/      # runtime BotSettings + PaymentSettings persistence
│   ├── api/
│   │   ├── deps.py              # DI: sessions, repositories, services
│   │   └── routers/             # health, catalog, orders, payment webhook
│   ├── admin/                   # SQLAdmin model views + AdminUser auth backend
│   └── bot/
│       ├── runner.py            # aiogram Dispatcher/Bot bootstrap
│       ├── keyboards/           # inline/reply keyboards
│       ├── states.py            # FSM states (search, order)
│       └── handlers/            # start/menu, categories, search, order
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── unit/                    # domain/services, rate limiter
│   ├── integration/            # all HTTP endpoints + full payment lifecycle (required)
│   └── conftest.py
├── pyproject.toml               # Poetry
├── poetry.lock
├── Dockerfile                   # python:3.12-slim, Poetry install, run uvicorn
├── docker-compose.yml           # api+bot service(s), optional postgres profile
├── .env.example                 # documented config; real .env* git-ignored
├── .env.dev.example             # development/testing profile sample
├── .env.prod.example            # production profile sample
├── .dockerignore
└── README.md
```

**Structure Decision**: Single repository, layered clean architecture. `domain` holds entities and
repository interfaces with no framework imports; `application` holds use cases that depend only on
domain ports; `infrastructure` implements those ports (SQLAlchemy, FTS5, payments); `api`, `admin`,
and `bot` are presentation/delivery layers wired through dependency injection. The Telegram bot runs
in the FastAPI lifespan (single container) for phase 1; it can be split into its own process/service
later without touching domain/application code. Storage and search are behind interfaces so the
SQLite→PostgreSQL switch is configuration-only.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `course_hub` becomes a dynamic FastAPI app instead of a static `nginx:alpine` `index.html` | The product requires a Telegram bot, search, orders/payments, and an admin — none of which a static page can provide | A static site cannot serve dynamic catalog, search, bot integration, or admin; no simpler option meets the requirements |
| Layered architecture (domain/application/infrastructure/presentation) + repository pattern | Required for the requested extensibility/scalability (SOLID, clean architecture) and the SQLite→PostgreSQL swap | Direct DB access in handlers would couple storage to delivery and block the configuration-only DB switch and testability |
