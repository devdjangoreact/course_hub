# Tasks: Course Hub — Multilingual Catalog, Bot UX, Parser, and Search Suggestions

**Input**: Design documents from `specs/002-multilingual-search/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required by FR-020. Add focused coverage for language preference, localized
catalog display, suggestion search, parser jobs, and existing localized order/payment behavior. Do not
run tests unless explicitly requested.

**Dev environment**: Docker-first. Use commands from `sites/course_hub`; Poetry runs inside Docker or
inside this submodule only, never globally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 language preference, US2 localized catalog, US3 suggestions, US4 Telegram display,
  US5 parser workflow
- Paths are relative to the repo root (`course_hub/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare existing project for the multilingual/parser feature without changing behavior.

- [ ] T001 Review `pyproject.toml` and keep existing dependencies unless implementation proves a small parser/search dependency is required
- [ ] T002 [P] Add feature configuration defaults for supported/default languages in `app/core/config.py`
- [ ] T003 [P] Add parser/search configuration defaults for suggestion minimum length and maximum suggestions in `app/core/config.py`
- [ ] T004 [P] Create package directories with `__init__.py` files in `app/bot/messages/` and `app/infrastructure/parsers/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared domain, persistence, and service contracts required before user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Define `SupportedLanguage` domain entity in `app/domain/entities/supported_language.py`
- [ ] T006 [P] Define translation domain entities in `app/domain/entities/category_translation.py` and `app/domain/entities/course_translation.py`
- [ ] T007 [P] Define parser domain entities in `app/domain/entities/parser_source.py`, `app/domain/entities/parser_job.py`, and `app/domain/entities/imported_catalog_item.py`
- [ ] T008 Define localization repository ports in `app/domain/repositories/language_repository.py` and `app/domain/repositories/translation_repository.py`
- [ ] T009 [P] Define parser repository and parser adapter ports in `app/domain/repositories/parser_source_repository.py`, `app/domain/repositories/parser_job_repository.py`, `app/domain/repositories/imported_catalog_item_repository.py`, and `app/domain/repositories/catalog_parser.py`
- [ ] T010 [P] Define suggestion search repository port in `app/domain/repositories/suggestion_search_repository.py`
- [ ] T011 Add SQLAlchemy models for `SupportedLanguage`, category translations, and course translations in `app/infrastructure/db/models/`
- [ ] T012 [P] Add SQLAlchemy models for parser sources, parser jobs, and imported catalog items in `app/infrastructure/db/models/`
- [ ] T013 Update model exports in `app/infrastructure/db/models/__init__.py`
- [ ] T014 Add Alembic migration for language, translation, parser, and bot user language fields in `alembic/versions/`
- [ ] T015 Update SQLite schema helper and localized search table setup in `app/infrastructure/db/init_db.py`
- [ ] T016 Update seed/bootstrap data for supported languages and demo translations in `app/bootstrap.py` and `app/seed.py`
- [ ] T017 Wire foundational repositories/services in `app/container.py` and `app/api/deps.py`

**Checkpoint**: Foundation ready. User story implementation can now begin.

---

## Phase 3: User Story 1 - Choose and Persist Bot Language (Priority: P1) MVP

**Goal**: A Telegram user chooses a language, the preference is persisted, and future bot interactions
use that language.

**Independent Test**: New user starts bot, selects Ukrainian or English, sends `/start` again, and the
saved language is used without asking again.

### Tests for User Story 1

- [ ] T018 [P] [US1] Add unit tests for language fallback and supported-language validation in `tests/unit/test_localization_service.py`
- [ ] T019 [P] [US1] Add bot integration tests for first-run language selection and returning-user language reuse in `tests/integration/test_bot_language.py`

### Implementation for User Story 1

- [ ] T020 [P] [US1] Implement `LanguageRepository` in `app/infrastructure/db/repositories/language_repository.py`
- [ ] T021 [P] [US1] Update `BotUserRepository` to read/write `preferred_language` in `app/infrastructure/db/repositories/bot_user_repository.py`
- [ ] T022 [US1] Implement `LocalizationService` in `app/application/services/localization_service.py`
- [ ] T023 [P] [US1] Create localized bot message catalog in `app/bot/messages/catalog.py`
- [ ] T024 [P] [US1] Create language selection keyboard in `app/bot/keyboards/language.py`
- [ ] T025 [US1] Update `/start` and language-change flow in `app/bot/handlers/start.py`
- [ ] T026 [US1] Register language handlers and dependencies in `app/bot/runner.py` and `app/bot/middleware.py`

**Checkpoint**: US1 works independently and can be demoed as the MVP.

---

## Phase 4: User Story 2 - Browse Localized Categories and Courses (Priority: P1)

**Goal**: Users browse localized category and course content with default-language fallback.

**Independent Test**: Select Ukrainian and English as different users and verify category/course
display changes while missing translations fall back safely.

### Tests for User Story 2

- [ ] T027 [P] [US2] Add unit tests for category/course translation fallback in `tests/unit/test_catalog_localization.py`
- [ ] T028 [P] [US2] Add integration tests for `GET /api/categories?language=` and `GET /api/categories/{category_id}/courses?language=` in `tests/integration/test_localized_catalog.py`
- [ ] T029 [P] [US2] Add bot integration tests for localized category and course browsing in `tests/integration/test_bot_localized_catalog.py`

### Implementation for User Story 2

- [ ] T030 [P] [US2] Implement translation repositories in `app/infrastructure/db/repositories/translation_repository.py`
- [ ] T031 [US2] Extend `CatalogService` with localized category/course read methods in `app/application/services/catalog_service.py`
- [ ] T032 [P] [US2] Update category/course response schemas with language and fallback metadata in `app/api/schemas/category.py` and `app/api/schemas/course.py`
- [ ] T033 [US2] Update catalog endpoints for optional `language` query parameter in `app/api/routers/catalog.py`
- [ ] T034 [US2] Update Telegram category/course handlers to use localized catalog output in `app/bot/handlers/categories.py`
- [ ] T035 [US2] Add SQLAdmin views for category and course translations in `app/admin/views.py`

**Checkpoint**: US1 and US2 work independently with localized catalog fallback.

---

## Phase 5: User Story 3 - Search with Suggestions After 3 Characters (Priority: P1)

**Goal**: Users receive localized selectable suggestions for partial/non-exact search queries of at
least 3 meaningful characters.

**Independent Test**: Search with 2 characters asks for more input; search with 3+ partial characters
shows localized selectable suggestions; rate limit still applies.

### Tests for User Story 3

- [ ] T036 [P] [US3] Add unit tests for suggestion query validation and ranking in `tests/unit/test_suggestion_search.py`
- [ ] T037 [P] [US3] Add integration tests for `GET /api/search/suggestions` in `tests/integration/test_search_suggestions.py`
- [ ] T038 [P] [US3] Add bot integration tests for suggestion buttons, no-results, and throttling in `tests/integration/test_bot_search_suggestions.py`

### Implementation for User Story 3

- [ ] T039 [US3] Implement localized suggestion search adapter in `app/infrastructure/db/search/localized_suggestion_search_repository.py`
- [ ] T040 [US3] Extend `SearchService` with suggestion search, 3-character minimum, localization, and existing rate limit in `app/application/services/search_service.py`
- [ ] T041 [P] [US3] Add suggestion response schemas in `app/api/schemas/search.py`
- [ ] T042 [US3] Add `GET /api/search/suggestions` endpoint in `app/api/routers/catalog.py`
- [ ] T043 [P] [US3] Add suggestion inline keyboard builders in `app/bot/keyboards/catalog.py`
- [ ] T044 [US3] Update Telegram search handler to show localized suggestion buttons in `app/bot/handlers/search.py`
- [ ] T045 [US3] Update FSM states for suggestion selection in `app/bot/states.py`

**Checkpoint**: US1-US3 provide multilingual discovery with selectable search suggestions.

---

## Phase 6: User Story 4 - Improved Telegram Course Presentation (Priority: P2)

**Goal**: Telegram course, navigation, order, and payment messages are readable and localized.

**Independent Test**: View courses, navigate back/search/order, and confirm all user-facing text is
localized and formatted consistently.

### Tests for User Story 4

- [ ] T046 [P] [US4] Add unit tests for Telegram course message formatting in `tests/unit/test_telegram_course_formatter.py`
- [ ] T047 [P] [US4] Add bot integration tests for localized course display and navigation buttons in `tests/integration/test_bot_course_display.py`
- [ ] T048 [P] [US4] Add integration tests ensuring order/payment messages use saved language in `tests/integration/test_localized_orders.py`

### Implementation for User Story 4

- [ ] T049 [P] [US4] Implement Telegram course formatter in `app/bot/messages/course_formatter.py`
- [ ] T050 [P] [US4] Update main menu and navigation keyboards for localized labels in `app/bot/keyboards/main_menu.py` and `app/bot/keyboards/catalog.py`
- [ ] T051 [US4] Update category and course detail rendering to use the formatter in `app/bot/handlers/categories.py`
- [ ] T052 [US4] Localize order creation and payment status text in `app/bot/handlers/order.py`
- [ ] T053 [US4] Update bot payment notifications to use user language in `app/bot/runner.py`
- [ ] T054 [US4] Add message-length safeguards for long course descriptions in `app/bot/messages/course_formatter.py`

**Checkpoint**: Telegram UX is localized, readable, and compatible with existing order/payment flows.

---

## Phase 7: User Story 5 - Import Draft Catalog Data From External Resources (Priority: P3)

**Goal**: Admins configure parser sources, start parser jobs, review draft imported items, and approve
selected data without auto-publishing unsafe content.

**Independent Test**: Configure a source, start parsing, confirm draft items are created, approve an
item, and re-run the same source without duplicate public catalog items.

### Tests for User Story 5

- [ ] T055 [P] [US5] Add unit tests for parser normalization and safe error reporting in `tests/unit/test_catalog_parser.py`
- [ ] T056 [P] [US5] Add unit tests for parser dedupe/fingerprint behavior in `tests/unit/test_parser_dedupe.py`
- [ ] T057 [P] [US5] Add integration tests for parser source/job/admin API contract in `tests/integration/test_parser_jobs.py`
- [ ] T058 [P] [US5] Add integration tests for imported item approval staying inactive until admin activation in `tests/integration/test_imported_catalog_review.py`

### Implementation for User Story 5

- [ ] T059 [P] [US5] Implement parser source repository in `app/infrastructure/db/repositories/parser_source_repository.py`
- [ ] T060 [P] [US5] Implement parser job repository in `app/infrastructure/db/repositories/parser_job_repository.py`
- [ ] T061 [P] [US5] Implement imported catalog item repository in `app/infrastructure/db/repositories/imported_catalog_item_repository.py`
- [ ] T062 [P] [US5] Implement catalog parser adapter skeleton in `app/infrastructure/parsers/catalog_parser.py`
- [ ] T063 [US5] Implement parser orchestration service in `app/application/services/parser_service.py`
- [ ] T064 [US5] Add parser source, job, and imported item schemas in `app/api/schemas/parser.py`
- [ ] T065 [US5] Add parser admin endpoints in `app/api/routers/parser.py`
- [ ] T066 [US5] Register parser router and dependencies in `app/api/routers/__init__.py`, `app/api/deps.py`, and `app/main.py`
- [ ] T067 [US5] Add SQLAdmin views for parser sources, parser jobs, and imported catalog item review in `app/admin/views.py`
- [ ] T068 [US5] Implement imported item approval workflow in `app/application/services/parser_service.py`

**Checkpoint**: Parser workflow is admin-controlled, auditable, idempotent, and draft-safe.

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Final quality, documentation, and safety pass across all user stories.

- [ ] T069 [P] Update `README.md` with multilingual setup, parser workflow, and Docker-first validation steps
- [ ] T070 [P] Update `.env.example`, `.env.dev.example`, and `.env.prod.example` with new language/search/parser settings
- [ ] T071 [P] Update `specs/002-multilingual-search/quickstart.md` if implementation changes validation commands or paths
- [ ] T072 Run formatting/linting for changed Python files through Docker in `sites/course_hub`
- [ ] T073 Run targeted tests for language, localized catalog, suggestions, Telegram display, and parser workflows through Docker in `sites/course_hub`
- [ ] T074 Run full `pytest` through Docker in `sites/course_hub`
- [ ] T075 Security pass: verify parser errors, logs, settings, and admin views do not expose secrets in `app/core/logging.py`, `app/application/services/parser_service.py`, and `app/admin/views.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 (Phase 3)**: Starts after Foundational and is the MVP.
- **US2 (Phase 4)**: Depends on Foundational and benefits from US1 language selection; still testable through API language parameters.
- **US3 (Phase 5)**: Depends on Foundational and localized catalog data from US2.
- **US4 (Phase 6)**: Depends on US1-US3 for localized messages and discovery flows.
- **US5 (Phase 7)**: Depends on Foundational and US2 catalog translation model; can be developed after US2.
- **Polish (Phase 8)**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: No user-story dependency.
- **US2 (P1)**: Uses language/fallback services from US1 for bot flow; API behavior is independently testable.
- **US3 (P1)**: Uses US2 localized catalog and search indexing.
- **US4 (P2)**: Uses US1 language preference, US2 localized catalog, and US3 navigation/search components.
- **US5 (P3)**: Uses catalog/translation models from US2; does not block bot MVP.

### Within Each User Story

- Tests first, expected to fail before implementation.
- Domain/repository models before services.
- Services before API endpoints and bot handlers.
- Admin views after persistence and services.
- Checkpoint validation before moving to the next priority.

---

## Parallel Opportunities

- T002-T004 can run in parallel.
- T006, T007, T009, T010, and T012 can run in parallel after T005 starts.
- Test tasks within each story can run in parallel.
- Repository implementations in US5 (T059-T061) can run in parallel.
- Polish documentation tasks T069-T071 can run in parallel.

---

## Parallel Example: User Story 3

```text
Task: "Add unit tests for suggestion query validation and ranking in tests/unit/test_suggestion_search.py"
Task: "Add integration tests for GET /api/search/suggestions in tests/integration/test_search_suggestions.py"
Task: "Add bot integration tests for suggestion buttons, no-results, and throttling in tests/integration/test_bot_search_suggestions.py"
```

After tests are written, these implementation tasks can proceed in parallel where file ownership does
not overlap:

```text
Task: "Add suggestion response schemas in app/api/schemas/search.py"
Task: "Add suggestion inline keyboard builders in app/bot/keyboards/catalog.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 language selection and persistence.
3. Validate new and returning user language behavior in Telegram.
4. Stop and demo before expanding catalog/search behavior.

### Incremental Delivery

1. US1 -> language preference and localized bot shell.
2. US2 -> localized catalog browsing.
3. US3 -> suggestion search after 3 characters.
4. US4 -> polished Telegram rendering and localized order/payment text.
5. US5 -> parser workflow and admin review.

### Quality Gates

- Do not publish parser imports without admin review.
- Do not expose inactive/draft courses in bot browsing, search, or orders.
- Preserve existing order/payment idempotency.
- Keep all secrets out of logs, commits, and admin-safe error summaries.
- Run tests only when explicitly requested.
