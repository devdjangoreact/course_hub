# Phase 1 Data Model: Multilingual Catalog, Search Suggestions, and Parser Jobs

Storage extends the existing async SQLAlchemy model. All new persisted entities include the existing
shared `extra` JSON field where item-specific structured data is useful. Existing `Category`,
`Course`, `BotUser`, `Order`, `BotSettings`, and `PaymentSettings` remain the source of truth for
catalog identity, users, orders, and runtime settings.

## Existing Entity Changes

### BotUser

| Field | Type | Rules |
|-------|------|-------|
| preferred_language | str | supported language code; default `uk`; user-editable |

Rules:
- If the saved value is unsupported, the bot asks the user to choose a supported language.
- Telegram client language may seed the initial default only when it is supported.
- Existing order relationships are unchanged.

### Category

Base category identity remains unchanged. The existing `name` is the default-language fallback and
remains required.

### Course

Base course identity, price, link, active flag, and order relationship remain unchanged. Existing
`name` and `description` are the default-language fallback values.

## New Entities

### SupportedLanguage

Represents a language the bot and catalog can display.

| Field | Type | Rules |
|-------|------|-------|
| code | str (PK) | ISO-like short code, e.g. `uk`, `en` |
| name | str | display name in default language |
| native_name | str | display name in the language itself |
| is_default | bool | exactly one default language |
| is_active | bool | inactive languages cannot be selected |
| extra | JSON | optional metadata |

Validation:
- Initial active languages: `uk`, `en`.
- Exactly one active default language exists.

### CategoryTranslation

Localized display fields for a category.

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| category_id | int (FK -> Category) | required |
| language_code | str (FK -> SupportedLanguage) | required |
| name | str | required, 1-120 chars |
| extra | JSON | optional metadata |

Validation:
- Unique `(category_id, language_code)`.
- Unique `(language_code, normalized_name)` is recommended for active public categories to reduce
  duplicate display names.
- Missing translation falls back to `Category.name`.

### CourseTranslation

Localized display fields for a course.

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| course_id | int (FK -> Course) | required |
| language_code | str (FK -> SupportedLanguage) | required |
| name | str | required, 1-200 chars |
| description | str | required |
| extra | JSON | optional metadata |

Validation:
- Unique `(course_id, language_code)`.
- Missing fields fall back to the base `Course.name` and `Course.description`.
- Course price, link, active flag, and order behavior remain language-independent.

### ParserSource

Admin-configured external resource allowed for parser jobs.

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| name | str | required, unique |
| source_type | str | e.g. `html`, `json`, `manual_adapter` |
| url | str | required URL |
| is_active | bool | inactive sources cannot start jobs |
| last_status | str | latest job status summary |
| extra | JSON | adapter-specific safe options; no secrets in logs |
| created_at | datetime | set on create |
| updated_at | datetime | set on update |

Validation:
- Only administrators can create/edit sources.
- Source URLs are treated as untrusted input.
- Secrets, if ever required, must be referenced through settings/env and not stored in plain admin
  logs.

### ParserJob

Audit record for one parser run.

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| source_id | int (FK -> ParserSource) | required |
| status | enum | `pending`, `running`, `completed`, `failed`, `cancelled` |
| started_at | datetime \| null | set when processing starts |
| finished_at | datetime \| null | set on terminal status |
| imported_count | int | default 0 |
| skipped_count | int | default 0 |
| error_summary | str \| null | safe for admin display; no secrets/raw tokens |
| extra | JSON | safe report details |
| created_at | datetime | set on create |
| updated_at | datetime | set on update |

State transitions:

```text
pending -> running
running -> completed
running -> failed
running -> cancelled
completed/failed/cancelled -> terminal
```

Rules:
- Re-running the same source creates a new job record.
- Duplicate parsed items are skipped or linked to existing draft/public items for review.
- Failed jobs do not alter existing public catalog visibility.

### ImportedCatalogItem

Draft parsed data waiting for admin review.

| Field | Type | Rules |
|-------|------|-------|
| id | int (PK) | auto |
| parser_job_id | int (FK -> ParserJob) | required |
| item_type | enum | `category`, `course` |
| external_id | str \| null | source-provided identity if available |
| source_url | str \| null | item URL if available |
| fingerprint | str | normalized content fingerprint for dedupe |
| language_code | str | language of parsed content if known |
| payload | JSON | parsed draft fields |
| status | enum | `draft`, `matched`, `approved`, `rejected` |
| matched_category_id | int \| null | possible/existing category match |
| matched_course_id | int \| null | possible/existing course match |
| extra | JSON | safe review metadata |
| created_at | datetime | set on create |
| updated_at | datetime | set on update |

Rules:
- Draft/matched items are not visible to bot users.
- Approving an item creates or updates inactive catalog content first unless an admin explicitly
  activates it.
- Unique `(parser_job_id, fingerprint)` prevents duplicate rows inside one job.
- Cross-job duplicate detection uses `(source_id, external_id)` when available, otherwise fingerprint.

## Search Indexing

Localized search should index:
- Category fallback name and category translations.
- Course fallback name/description and course translations.
- Only active public courses are returned to bot users.

Suggestion results include:
- Result type: category or course.
- Localized display name.
- Localized short description for courses.
- Stable target ID for button callbacks.
- Ranking score.

## Validation Rules

- Supported search queries must contain at least 3 meaningful characters before suggestions run.
- Existing 5-searches-per-minute per-user limit applies to suggestion requests and final searches.
- Missing translations use default-language fallback.
- Inactive courses and draft imported items never appear in bot browsing/search/order flows.
- User-facing text must be localized through the selected language.
- Parser errors recorded for admins must not include credentials, tokens, raw auth headers, or private
  source data.
