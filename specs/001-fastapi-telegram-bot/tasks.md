# Tasks: Course Hub — FastAPI Backend + Telegram Bot

**Input**: Design documents from `specs/001-fastapi-telegram-bot/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are **required** (explicitly requested). All HTTP endpoints and the full payment
process MUST be covered (FR-016, SC-008).

**Dev environment**: Docker-first. Run everything (code, deps, env) in containers; Poetry runs inside
the container or locally in this submodule — never installed globally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (browse), US2 (search), US3 (orders/payments), US4 (admin/settings)
- Paths are relative to the repo root (`course_hub/`)

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Initialize Poetry project `pyproject.toml` (Python 3.12) with deps: fastapi, uvicorn,
  sqlalchemy[asyncio], alembic, aiosqlite, asyncpg, aiogram, pydantic, pydantic-settings, sqladmin,
  passlib[bcrypt], loguru, httpx; dev deps: pytest, pytest-asyncio, ruff, black, mypy.
- [ ] T002 [P] Create the `app/` package skeleton (`core/`, `domain/`, `application/`,
  `infrastructure/`, `api/`, `admin/`, `bot/`) with `__init__.py` files per plan structure.
- [ ] T003 [P] Configure tooling: `ruff`/`black`/`mypy` settings in `pyproject.toml` and a
  `.dockerignore`.
- [ ] T004 [P] Create `.env.example`, `.env.dev.example`, `.env.prod.example` documenting
  `APP_ENV`, `DATABASE_URL`, `BOT_TOKEN`, `BACKEND_URL`, admin seed credentials, payment keys;
  confirm `.env*` is git-ignored.
- [ ] T004a Create Docker-first dev setup: `Dockerfile` + `docker-compose.yml` so the app, deps
  (Poetry inside the image), and `.env` run in containers — no global Poetry on the host.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Implement `app/core/config.py` (pydantic-settings: `APP_ENV` dev/prod switch,
  `DATABASE_URL`, secrets) — one settings class, env-driven.
- [ ] T006 [P] Implement `app/core/logging.py` (Loguru setup, intercept stdlib/uvicorn, redact
  secrets).
- [ ] T007 Implement `app/core/database.py` (async engine + `async_sessionmaker`, works for SQLite
  and PostgreSQL from `DATABASE_URL`).
- [ ] T008 Define domain repository interfaces (ports) in `app/domain/repositories/`
  (`category_repository.py`, `course_repository.py`, `search_repository.py`,
  `bot_user_repository.py`, `order_repository.py`, `admin_user_repository.py`,
  `bot_settings_repository.py`, `payment_settings_repository.py`, `payment_gateway.py`,
  `rate_limiter.py`) — one per file.
- [ ] T009 Define domain entities in `app/domain/entities/` (`category.py`, `course.py`,
  `bot_user.py`, `order.py`, `admin_user.py`, `bot_settings.py`, `payment_settings.py`) —
  framework-free, one per file; each carries an optional `extra` dict.
- [ ] T010 Create SQLAlchemy models in `app/infrastructure/db/models/` (one per file) for Category,
  Course, BotUser, Order, AdminUser, BotSettings, PaymentSettings per data-model.md. Add a shared
  `extra` JSON column (default `{}`) to every model via a mixin.
- [ ] T011 Initialize Alembic (`alembic/`) and create the initial migration for all tables
  (including the `extra` JSON column on each).
- [ ] T012 Create the FTS5 virtual table + sync (triggers or repo writes) for course
  name/description in a migration and `app/infrastructure/db/search/`.
- [ ] T013 Implement `app/api/deps.py` (DI: session, repository, and service providers) and the
  FastAPI app factory `app/main.py` with lifespan + `/health` router in `app/api/routers/`.
- [ ] T014 Implement `app/seed.py` to load demo categories/courses and seed the first AdminUser +
  BotSettings/PaymentSettings defaults from env.

**Checkpoint**: Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 — Browse courses by category (Priority: P1) 🎯 MVP

**Goal**: After `/start`, users browse categories and a category's active courses in Telegram.

**Independent Test**: Seed data, `/start`, tap a category, see its active courses.

- [ ] T015 [TEST] [P] [US1] Integration tests for `GET /api/categories` and
  `GET /api/categories/{id}/courses` (incl. empty/404 cases) in `tests/integration/test_categories.py`.
- [ ] T016 [P] [US1] Implement `CategoryRepository` impl in
  `app/infrastructure/db/repositories/category_repository.py`.
- [ ] T017 [P] [US1] Implement `CourseRepository` impl (list active by category) in
  `app/infrastructure/db/repositories/course_repository.py`.
- [ ] T018 [US1] Implement `CatalogService` in `app/application/services/catalog_service.py`
  (list categories, list active courses by category) — depends on T016, T017.
- [ ] T019 [P] [US1] Read endpoints `GET /api/categories`,
  `GET /api/categories/{id}/courses` in `app/api/routers/catalog.py`.
- [ ] T020 [US1] Bot bootstrap `app/bot/runner.py` (aiogram Bot/Dispatcher) wired into the app
  lifespan; main menu keyboard in `app/bot/keyboards/`.
- [ ] T021 [US1] Bot handlers `app/bot/handlers/start.py` (upsert BotUser, main menu) and
  `app/bot/handlers/categories.py` (category list → course list → course detail).
- [ ] T022 [US1] Add validation/empty-state handling and Loguru logging for US1 flows.

**Checkpoint**: US1 fully functional and demoable (MVP).

---

## Phase 4: User Story 2 — Full-text course search (Priority: P1)

**Goal**: Users search active courses by keyword, ranked by relevance.

**Independent Test**: Send a matching query → ranked active matches; gibberish → no results.

- [ ] T023 [TEST] [P] [US2] Integration test for `GET /api/courses/search?q=` (match, no-match,
  invalid) in `tests/integration/test_search.py`.
- [ ] T023a [TEST] [P] [US2] Unit test for the search rate limiter (5/min, 6th throttled) in
  `tests/unit/test_rate_limiter.py`.
- [ ] T024 [US2] Implement `SearchRepository` (FTS5) in
  `app/infrastructure/db/search/fts5_search_repository.py` (ranked, active-only).
- [ ] T024a [US2] Implement the `RateLimiter` port impl (in-memory per-user, 5/60s) in
  `app/infrastructure/ratelimit/in_memory_rate_limiter.py`.
- [ ] T025 [US2] Implement `SearchService` in `app/application/services/search_service.py`
  (trim/validate query, length limit, apply rate limit) — depends on T024, T024a.
- [ ] T026 [P] [US2] Endpoint `GET /api/courses/search?q=` in `app/api/routers/catalog.py`.
- [ ] T027 [US2] Bot search flow `app/bot/handlers/search.py` + FSM states in `app/bot/states.py`
  (prompt, results, no-results, re-prompt on empty, throttle message on limit).

**Checkpoint**: US1 + US2 work independently.

---

## Phase 5: User Story 3 — Orders & payments (Priority: P2)

**Goal**: Users order a course; payment confirmation updates the order idempotently and notifies.

**Independent Test**: Create order → simulate payment → order `paid`; repeat callback → no dup.

- [ ] T028 [TEST] [P] [US3] Integration tests for the full payment process: order creation, webhook
  success/failure/cancel, idempotent repeat callback, and the dev `simulate` flow in
  `tests/integration/test_orders.py` and `tests/integration/test_payments.py`.
- [ ] T029 [P] [US3] Implement `BotUserRepository` (persist/upsert users) and `OrderRepository`
  impls in `app/infrastructure/db/repositories/`.
- [ ] T030 [US3] Implement `PaymentGateway` adapters in `app/infrastructure/payments/` (simulated for
  dev, provider for prod), reading config from `PaymentSettings`.
- [ ] T030a [US3] Implement `PaymentSettingsRepository` impl in
  `app/infrastructure/settings_store/payment_settings_repository.py`.
- [ ] T031 [US3] Implement `OrderService` in `app/application/services/order_service.py`
  (create pending order with price snapshot; idempotent status transitions) — depends on T029, T030.
- [ ] T032 [P] [US3] Endpoints `POST /api/orders`, `GET /api/orders/{id}`,
  `POST /api/payments/webhook`, and dev-only `POST /api/payments/simulate` in
  `app/api/routers/orders.py`.
- [ ] T033 [US3] Bot order flow `app/bot/handlers/order.py` (order button → payment instructions;
  notify user on paid/failed/cancel).
- [ ] T034 [US3] Webhook signature verification + idempotency guard + Loguru logging (no secrets).

**Checkpoint**: US1–US3 work independently.

---

## Phase 6: User Story 4 — Admin panel & bot settings (Priority: P2)

**Goal**: Authenticated admin manages categories/courses/orders and edits bot token + backend URL.

**Independent Test**: Sign in, create category+course (appear in bot); edit token+backend URL persist.

- [ ] T035 [TEST] [P] [US4] Integration tests for admin auth (persisted AdminUser, reject anon) and
  BotSettings/PaymentSettings persistence in `tests/integration/test_admin.py`.
- [ ] T036 [US4] Implement `BotSettingsRepository` and `AdminUserRepository` impls in
  `app/infrastructure/settings_store/` (single-row BotSettings, env-seeded admin; bcrypt hashing).
- [ ] T037 [US4] Configure SQLAdmin in `app/admin/` with an auth backend that authenticates against
  persisted `AdminUser` (hashed passwords) and model views for Category, Course, Order, AdminUser.
- [ ] T038 [US4] Add BotSettings and PaymentSettings views/forms in `app/admin/` to edit bot token +
  backend URL and payment provider/keys/currency; apply updated bot token to the running bot.
- [ ] T039 [US4] Mount admin on the app in `app/main.py`; ensure unauthenticated access is blocked.

**Checkpoint**: All user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T040 Finalize `docker-compose.yml` for prod profile + optional `postgres` profile and pin the
  production image build (extends the Docker-first dev setup from T004a).
- [ ] T041 [P] Write `README.md`: setup, Docker-first dev, profiles (dev/prod), SQLite→PostgreSQL
  switch, run/Docker, validation steps.
- [ ] T042 Verify SQLite→PostgreSQL switch is config-only (`DATABASE_URL` + `alembic upgrade head`).
- [ ] T043 Security pass: confirm no secrets in source/logs; `.env*` ignored; admin protected;
  passwords hashed.
- [ ] T044 Verify test coverage: all HTTP endpoints and the full payment process are tested
  (FR-016, SC-008); run `pytest`.
- [ ] T045 Run quickstart.md validation scenarios end-to-end.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** blocks everything.
- **US1 (P1)** and **US2 (P1)** can follow Phase 2; US2 depends on the catalog/search foundation.
- **US3 (P2)** and **US4 (P2)** follow Phase 2; US4 (admin) makes content that US1/US2/US3 surface.
- **Polish (Phase 7)** last.

### Within each story

- Repositories → services → endpoints/bot handlers.
- Domain ports (Phase 2) before infrastructure implementations.

## Implementation Strategy

- MVP = Phase 1 + Phase 2 + US1, then validate and demo.
- Add US2 (search), then US3 (orders/payments), then US4 (admin/settings) incrementally.
- Keep one construct per file, type everything, no `any`, format on save, log errors with context.
