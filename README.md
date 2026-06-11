# course_hub

Async FastAPI application with a Telegram bot for browsing courses, full-text search, orders,
payment confirmation, and a simple admin panel.

- Project: `course_hub`
- Service / ECR image: `ddnsteltonicka`
- Domain: `ddnsteltonicka.pp.ua`

## Development

Development is Docker-first. Code, dependencies, and environment run inside containers. Poetry is
installed inside the image, not globally on the host.

1. Copy `.env.dev.example` to `.env` and fill real local secrets.
2. Start the app:

```bash
docker compose up --build
```

3. Seed demo data and the first admin:

```bash
docker compose exec app python -m app.seed
```

Open:

- API health: `http://localhost:8000/health`
- Admin: `http://localhost:8000/admin`

## Configuration

Use `APP_ENV=development` for development/testing and `APP_ENV=production` for production. Use a
different Telegram bot token in each profile.

SQLite is the phase-1 default:

```text
DATABASE_URL=sqlite+aiosqlite:///./course_hub.db
```

Switch to PostgreSQL by changing only `DATABASE_URL`:

```text
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/course_hub
```

## Tests

Run tests inside Docker:

```bash
docker compose exec app pytest
```

The suite covers health, catalog endpoints, full-text search, order creation, simulated payment,
payment webhook signature validation/idempotency, admin authentication, and the rate limiter.

