# Quickstart & Validation: Course Hub

Validates the feature end-to-end. See [data-model.md](./data-model.md) and
[contracts/](./contracts/) for details referenced here.

## Prerequisites

- Docker + Docker Compose (development is Docker-first; Poetry runs inside the container, not
  globally on the host).
- A Telegram bot token for the development/testing profile (separate from production).

## Configuration profiles

Two profiles selected by `APP_ENV`, each with its own bot token:

- Development/testing: copy `.env.dev.example` → `.env` (`APP_ENV=development`,
  `DATABASE_URL=sqlite+aiosqlite:///./course_hub_dev.db`, dev `BOT_TOKEN`).
- Production: copy `.env.prod.example` → `.env` (`APP_ENV=production`, prod `BOT_TOKEN`,
  `DATABASE_URL=sqlite+aiosqlite:///./course_hub.db` for phase 1).

PostgreSQL switch (config-only): set
`DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/course_hub` and run migrations — no code
changes.

## Run (Docker-first)

```bash
docker compose up --build
# run migrations + seed inside the running container
docker compose exec app alembic upgrade head
docker compose exec app python -m app.seed   # demo data + first admin + settings defaults
```

The bot starts with the app (long polling) when a valid token is configured. Poetry/dependencies live
inside the image; nothing is installed globally on the host.

## Optional: run inside the container without recreating

```bash
docker compose exec app pytest        # run the test suite in the container
docker compose exec app bash          # shell into the dev container
```

## Validation scenarios

1. **Health** (infra gate): `curl -sSf http://localhost:8000/health` → `status: ok` with the active
   `env`.
2. **Browse (US1)**: in Telegram send `/start` → main menu; tap `Categories` → category list; tap a
   category → its active courses.
3. **Search (US2)**: tap `Search`, send a known keyword → ranked active matches; send gibberish →
   "no results"; send blank → re-prompt.
4. **Search rate limit (SC-007)**: send 6 searches within a minute → the 6th is throttled with a
   "please slow down" message.
5. **Order + payment (US3)**: open a course → `Order` → a `pending` order is created; in development,
   call the simulated confirmation → order becomes `paid` and the bot notifies the user; repeat the
   callback → no duplicate effect (idempotent).
6. **Admin (US4)**: open `/admin`, sign in with the seeded admin account, create a category + course
   → they appear in the bot; edit bot token + backend URL and payment settings → values persist;
   anonymous access is blocked.
7. **DB switch (SC-005)**: change `DATABASE_URL` to PostgreSQL, run `alembic upgrade head`, start the
   app → it boots and the scenarios above pass with no code edits.

## Tests

```bash
docker compose exec app pytest
```

Required coverage: all HTTP endpoints and the full payment process (FR-016, SC-008), plus unit tests
(domain/services, rate limiter) and bot handler tests against a temporary SQLite database.
