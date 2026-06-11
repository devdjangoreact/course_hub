# Quickstart: Validate Multilingual Search Feature

This guide describes validation scenarios for the multilingual catalog, Telegram bot UX, search
suggestions, and parser workflow.

## Prerequisites

- Work from `sites/course_hub`.
- Use the Docker-first development workflow.
- `.env` contains local development values and is not committed.
- Database migrations for this feature have been applied.

## Setup

```powershell
docker compose up -d --build
docker compose exec app python -m app.seed
```

Expected:
- Application starts successfully.
- Seed data is present.
- Supported languages include Ukrainian and English.

## Scenario 1: Language Selection

1. Open the Telegram bot as a new user.
2. Send `/start`.
3. Select Ukrainian.
4. Send `/start` again.

Expected:
- First run asks for language.
- Later runs use Ukrainian automatically.
- The language menu can switch to English and persists the new value.

## Scenario 2: Localized Catalog

1. Select a language.
2. Open categories.
3. Open a category.
4. Open a course.

Expected:
- Category and course text use the selected language when available.
- Missing translations fall back to the default language.
- Inactive/draft imported courses do not appear.

## Scenario 3: Search Suggestions

1. Open Search.
2. Send fewer than 3 characters.
3. Send a 3+ character partial query.

Expected:
- Short input asks for at least 3 characters.
- Valid input returns selectable Telegram buttons.
- Suggestions include close/partial matches, not only exact matches.
- Existing 5-per-minute search rate limit still applies.

## Scenario 4: Course Display and Order Text

1. Open a localized course.
2. Review displayed text and action buttons.
3. Start an order.
4. Simulate payment confirmation.

Expected:
- Course details are readable and consistently formatted.
- Order and payment messages use the selected language.
- Payment confirmation remains idempotent.

## Scenario 5: Parser Workflow

1. Sign in to admin.
2. Configure an allowed parser source.
3. Start a parser job.
4. Review job status and imported draft items.
5. Approve selected items.

Expected:
- Parser job status is visible.
- Imported data is draft/inactive until reviewed.
- Re-running the same source does not create duplicate public catalog items.
- Parser errors are safe for admin display and do not leak secrets.

The same flow is available through `/api/admin/parser-sources`,
`/api/admin/parser-sources/{source_id}/jobs`, `/api/admin/parser-jobs/{job_id}`, and
`/api/admin/imported-items/{item_id}/approve`.

## Automated Validation

When explicitly requested, run the feature test suite through Docker/Poetry:

```powershell
docker compose run --rm app pytest
```

Expected:
- Language preference, localized catalog display, suggestion search, parser jobs, and existing
  order/payment behavior are covered and passing.
