# Phase 0 Research: Multilingual Search Feature

## Decision: Store translations in dedicated related tables

**Rationale**: Category and course translations need validation, uniqueness per language, admin
editing, fallback behavior, and search indexing. Dedicated tables make these requirements explicit and
testable while keeping the existing base `Category` and `Course` entities stable.

**Alternatives considered**:
- JSON translations inside `extra`: simple, but weak for search, constraints, admin editing, and
  duplicate detection.
- Separate category/course per language: easy display, but duplicates catalog identity and complicates
  orders, pricing, activation, and imports.

## Decision: Persist language preference on existing bot users

**Rationale**: The bot already persists `BotUser`. Adding a preferred language to that user record
keeps returning-user behavior simple and avoids a separate one-row preference table unless future
settings grow beyond language.

**Alternatives considered**:
- Separate `LanguagePreference` table: flexible, but more joins and no clear value for the first
  preference.
- Rely on Telegram client language: useful as an initial default, but users must be able to override
  it and keep that choice.

## Decision: Use a centralized localized message catalog for bot UI text

**Rationale**: Menus, validation messages, order/payment text, empty states, and errors need consistent
language handling. A small message catalog keeps handlers readable and makes missing translations
obvious in tests.

**Alternatives considered**:
- Inline text in handlers: fastest initially, but duplicates strings and makes language switching
  error-prone.
- External translation service: unnecessary for Ukrainian/English phase 1 and adds operational risk.

## Decision: Implement Telegram suggestions with inline keyboards after 3 characters

**Rationale**: Telegram chat does not provide a native dropdown for free-text typing. Inline buttons
after a submitted query provide a Telegram-native, selectable suggestion experience and match the
requirement without pretending unsupported UI exists.

**Alternatives considered**:
- True dropdown/autocomplete: not available in normal Telegram bot chat.
- Return only text results: simpler, but less usable and does not satisfy "selectable suggestions".

## Decision: Extend search to localized partial/fuzzy matching behind the existing search port

**Rationale**: The system already has a search abstraction. Extending it to search localized names and
descriptions preserves API/bot use cases while allowing SQLite phase-1 implementation and PostgreSQL
later. Results should combine active filtering, user language preference, fallback content, and stable
ranking.

**Alternatives considered**:
- Exact-only `LIKE`: too weak for partial/fuzzy requirements.
- External search service: too heavy for phase 1 and unnecessary for the expected catalog size.

## Decision: Parser output is draft/inactive and requires admin review

**Rationale**: External sources are untrusted and can contain malformed, duplicated, outdated, or
legally questionable content. Keeping imported data invisible until admin review protects bot users
and preserves catalog quality.

**Alternatives considered**:
- Auto-publish parsed data: fastest, but unsafe and conflicts with draft visibility requirements.
- Manual copy/paste only: safe, but does not provide the requested parser service.

## Decision: Parser jobs are idempotent per source/item identity

**Rationale**: Admins may retry failed jobs or run the same source multiple times. The parser must
track source URLs/external IDs/content fingerprints so repeated runs do not create duplicate public
items and can surface possible matches for review.

**Alternatives considered**:
- Always create new draft items: easier, but quickly pollutes review workflow.
- Update existing public catalog automatically: risky because source data can be wrong or stale.
