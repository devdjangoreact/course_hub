# Implementation Plan: Course Hub — Multilingual Catalog, Bot UX, Parser, and Search Suggestions

**Branch**: `002-multilingual-search` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-multilingual-search/spec.md`

## Summary

Extend the existing async FastAPI + aiogram `course_hub` app with localized catalog content,
persisted Telegram language preferences, improved Telegram message presentation, partial/fuzzy
search suggestions after 3 characters, and an admin-triggered parser workflow that imports external
catalog data as draft/inactive records for review. The implementation keeps the current clean
architecture boundaries: domain entities and repository ports stay framework-free, application
services orchestrate localization/search/parser flows, infrastructure implements SQLAlchemy search
and parser adapters, and API/admin/bot layers only present use cases.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Existing stack: FastAPI, Uvicorn, SQLAlchemy 2.0 async, Alembic,
aiosqlite/asyncpg, aiogram 3.x, Pydantic v2, pydantic-settings, SQLAdmin, Loguru, HTTPX, bcrypt,
pytest, pytest-asyncio. Add only small parser/search dependencies if implementation tasks prove they
are required; prefer standard library + existing HTTPX/SQLAlchemy first.

**Storage**: Existing SQLite phase-1 database via async SQLAlchemy, with Alembic migrations. Add
translation tables for category/course localized fields, language preference on bot users, parser
source/job tables, and search indexing over localized content. PostgreSQL remains a configuration
switch through `DATABASE_URL`.

**Testing**: pytest + pytest-asyncio. Add focused unit tests for language fallback, message formatting,
suggestion ranking, and parser idempotency; integration tests for HTTP/admin parser endpoints and bot
language/search flows. Do not run tests unless explicitly requested.

**Development environment**: Docker-first. All app commands continue to run through Docker/Poetry in
the `course_hub` submodule; no global Poetry install and no secrets committed.

**Target Platform**: Linux container behind existing Traefik routing for the `course_hub` domain.

**Project Type**: Async web service + SQLAdmin panel + long-running Telegram bot worker in one
repository.

**Performance Goals**: Search suggestions return in under 1 second on the phase-1 catalog; language
lookup/fallback adds no visible delay to bot menu and course display.

**Constraints**: Fully async request and bot paths; Telegram message size/readability limits; parser
input is untrusted; imported content is not public until admin review; secrets and parser credentials
are never logged; current order/payment behavior must remain compatible.

**Scale/Scope**: First multilingual release supports Ukrainian and English, a modest catalog
(hundreds to low thousands of courses), one bot, single admin workflow, and configured parser sources
started manually by admins.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The infra constitution governs deployment authority and secret handling. This feature remains inside
the `course_hub` app-repo and does not add Terraform, Traefik, SSH, or deployment logic.

| # | Principle | Plan compliance |
|---|-----------|-----------------|
| I | Repository Responsibility Separation | App logic stays in `course_hub`; infra repo remains deployment authority. PASS |
| II | Single Source of Deployment Truth | No deploy workflow or Traefik changes are added here. PASS |
| III | Domain-Isolated Single-Server Routing | App remains routed by existing infra; no host port changes. PASS |
| IV | Secrets Never Touch Source Control | Parser credentials, bot tokens, and payment keys stay in env/admin settings and logs redact secrets. PASS |
| VI | Reproducible, Pinned Containers | Dependencies remain in Poetry/Docker build artifacts. PASS |
| VII | Automated Validation Gates | Existing infra gates still apply; app-level tests cover new behavior. PASS |

Post-design re-check: PASS. The feature adds application data and behavior only; no additional
constitution deviation beyond the already accepted dynamic-app scope from `001-fastapi-telegram-bot`.

## Project Structure

### Documentation (this feature)

```text
specs/002-multilingual-search/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── http-api.md
│   ├── bot-interactions.md
│   └── parser-source.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root: `course_hub/`)

```text
course_hub/
├── app/
│   ├── domain/
│   │   ├── entities/            # language, localized content, parser source/job entities
│   │   └── repositories/        # localization, suggestion search, parser ports
│   ├── application/
│   │   └── services/            # localization, catalog display, parser orchestration
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── models/          # translation and parser SQLAlchemy models
│   │   │   ├── repositories/    # localized catalog/parser repositories
│   │   │   └── search/          # localized suggestion search adapter
│   │   └── parsers/             # source fetch/parse adapters
│   ├── api/
│   │   └── routers/             # parser/source endpoints if needed outside SQLAdmin
│   ├── admin/                   # SQLAdmin views for translations and parser review
│   └── bot/
│       ├── handlers/            # language selection, localized browse/search/order
│       ├── keyboards/           # language and suggestion keyboards
│       └── messages/            # localized UI text catalog
├── alembic/versions/            # migrations for new tables/indexes
└── tests/
    ├── unit/                    # localization/search/parser services
    └── integration/             # API/admin/bot flows
```

**Structure Decision**: Preserve the existing layered architecture. Store localized catalog content
as related entities instead of JSON-only blobs so admin editing, fallback logic, uniqueness, and
localized search can be validated and indexed. Keep parser imports draft/inactive until admin review.
Implement Telegram suggestions with inline keyboards because normal Telegram chat does not support a
native dropdown while typing.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Additional localization and parser entities | Multilingual content, user preferences, parser audit trail, and draft review need queryable state and lifecycle | Storing everything only in existing `extra` JSON would make search, validation, admin review, and duplicate detection fragile |
