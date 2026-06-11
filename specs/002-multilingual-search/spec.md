# Feature Specification: Course Hub — Multilingual Catalog, Bot UX, Parser, and Search Suggestions

**Feature Branch**: `002-multilingual-search`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: Add multilingual categories and courses; add multilingual bot interface with user language selection; persist user language settings and use them when the user returns; improve Telegram display; add a service that can start parsing categories from other resources; support search beyond exact matching and provide suggestion-style choices after 3 typed characters.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose and Persist Bot Language (Priority: P1)

A Telegram user opens the bot, chooses a preferred language, and sees menus, messages, categories,
courses, order prompts, and payment messages in that language on future interactions.

**Why this priority**: Language preference affects every bot interaction. Persisting it makes the
bot usable for returning users without repeated setup.

**Independent Test**: Start the bot as a new user, select a language, restart the conversation, and
confirm the selected language is still used for menus and course discovery.

**Acceptance Scenarios**:

1. **Given** a new bot user has no saved language, **When** they start the bot, **Then** the bot asks
   them to choose from supported languages before showing the main menu.
2. **Given** a user selected a language earlier, **When** they send `/start` again, **Then** the bot
   uses the saved language without asking again.
3. **Given** a user wants to change language, **When** they select the language option, **Then** the
   new language is saved and immediately used.

---

### User Story 2 - Browse Localized Categories and Courses (Priority: P1)

A user browses categories and courses in their selected language. If a translation is missing, the
bot still shows a useful fallback rather than an empty or broken item.

**Why this priority**: Multilingual content is the main catalog value; users should not need to
understand the source language to browse or order.

**Independent Test**: Create localized category and course content in two languages, select each
language as a user, and verify the displayed catalog changes accordingly.

**Acceptance Scenarios**:

1. **Given** a category has translations for the user's language, **When** categories are listed,
   **Then** the localized category name is shown.
2. **Given** a course has localized name and description, **When** the course is displayed, **Then**
   the localized content, price, and action buttons are shown.
3. **Given** a translation is missing for a category or course, **When** it is displayed, **Then** a
   default-language fallback is shown and the item remains usable.

---

### User Story 3 - Search with Suggestions After 3 Characters (Priority: P1)

A user starts typing a search query and receives relevant suggested courses or categories after at
least 3 characters, without requiring exact text matches.

**Why this priority**: Search must remain usable as the catalog grows and users may type partial
words, transliterations, or imperfect terms.

**Independent Test**: Seed courses with related names/descriptions, search using partial and fuzzy
terms of at least 3 characters, and confirm relevant localized suggestions appear.

**Acceptance Scenarios**:

1. **Given** a user types fewer than 3 characters, **When** the query is submitted, **Then** the bot
   asks for at least 3 characters and does not run search.
2. **Given** a user types 3 or more characters, **When** matching catalog items exist, **Then** the
   bot shows suggestion-style choices using Telegram buttons.
3. **Given** the query is not an exact match but is close to existing content, **When** results are
   available, **Then** the closest active matches are shown first.
4. **Given** no useful matches exist, **When** the query is submitted, **Then** the bot shows a
   localized no-results message.

---

### User Story 4 - Improved Telegram Course Presentation (Priority: P2)

A user views categories, courses, order options, and payment status in a clear Telegram-friendly
layout with readable text, structured details, and concise action buttons.

**Why this priority**: Better presentation increases trust and makes ordering easier, but depends on
localized catalog and language preference.

**Independent Test**: Open several categories and courses in Telegram and verify each message is
readable, localized, and has clear navigation/actions.

**Acceptance Scenarios**:

1. **Given** a course is shown in Telegram, **When** the user reads it, **Then** they see name,
   category, description, price, and available actions in a consistent format.
2. **Given** a long course description exists, **When** it is displayed, **Then** the bot keeps the
   message readable and does not exceed Telegram message limits.
3. **Given** the user navigates between lists and details, **When** they tap buttons, **Then** back,
   order, search, and language actions remain clear.

---

### User Story 5 - Import Draft Catalog Data From External Resources (Priority: P3)

An administrator starts a catalog parsing job from configured external resources and reviews imported
categories/courses before making them visible to users.

**Why this priority**: Import reduces manual catalog entry, but imported data must not become visible
without admin review.

**Independent Test**: Configure an allowed source, start parsing, confirm imported items are saved as
draft/inactive, then approve selected items and verify they appear in the bot.

**Acceptance Scenarios**:

1. **Given** an administrator configured an allowed source, **When** they start parsing, **Then** a
   parsing job is created and its status can be viewed.
2. **Given** parsing finds categories or courses, **When** the job completes, **Then** imported items
   are saved as inactive/draft data for review.
3. **Given** imported data duplicates existing catalog items, **When** it is processed, **Then** the
   system avoids duplicate public items and marks possible matches for review.
4. **Given** a source fails or is unavailable, **When** parsing runs, **Then** the failure is recorded
   and the existing catalog remains unchanged.

---

### Edge Cases

- A returning user has a saved language that is no longer supported -> the bot asks them to choose a
  currently supported language.
- A category or course has partial translations -> translated fields are used where available and
  missing fields fall back to the default language.
- The user changes language while viewing a course -> the current view and subsequent actions use
  the new language.
- Search input includes typos, different case, punctuation, or mixed-language text -> the bot returns
  the best available matches or a localized no-results message.
- Search suggestions return too many items -> the bot limits the list and offers a way to refine the
  query.
- Parsed external content is malformed, duplicated, or missing required fields -> invalid entries are
  skipped or marked for admin review, and the job report explains what happened.
- External parsing is started multiple times for the same source -> duplicate public catalog data is
  not created.
- A course is inactive or imported as draft -> it does not appear in bot browsing, search, or order
  flows until approved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support at least Ukrainian and English for the Telegram user interface.
- **FR-002**: System MUST allow a bot user to choose and later change their preferred language.
- **FR-003**: System MUST persist each bot user's language preference and apply it to future
  interactions.
- **FR-004**: System MUST support localized category names for each supported language.
- **FR-005**: System MUST support localized course names and descriptions for each supported
  language.
- **FR-006**: System MUST use a default-language fallback when a localized category or course field is
  missing.
- **FR-007**: System MUST show bot menus, prompts, validation messages, order messages, and payment
  messages in the user's selected language.
- **FR-008**: System MUST provide a clear Telegram-friendly course display including course name,
  category, description, price, and primary actions.
- **FR-009**: System MUST prevent inactive or draft imported courses from appearing in bot browsing,
  search, or new order flows.
- **FR-010**: System MUST search localized category and course content using non-exact matching for
  partial terms, close terms, and relevant descriptions.
- **FR-011**: System MUST require at least 3 meaningful characters before showing search suggestions.
- **FR-012**: System MUST present search suggestions as selectable Telegram actions when matching
  results are found.
- **FR-013**: System MUST keep the existing per-user search rate limit behavior for suggestion and
  full search requests.
- **FR-014**: System MUST let an administrator configure external catalog sources that are allowed
  for parsing.
- **FR-015**: System MUST let an administrator start a parsing job for an allowed external source and
  view its status/result.
- **FR-016**: System MUST save parsed categories and courses as inactive/draft items until an
  administrator reviews and approves them.
- **FR-017**: System MUST record parser job outcomes, including started time, finished time, status,
  source, imported counts, skipped counts, and errors safe for admin display.
- **FR-018**: System MUST avoid creating duplicate public catalog items when parsing or seeding data
  repeatedly.
- **FR-019**: System MUST preserve the existing order and payment behavior while applying localized
  user-facing text.
- **FR-020**: System MUST cover language preference, localized catalog display, suggestion search, and
  parser job behavior with automated tests before implementation is considered complete.

### Key Entities *(include if feature involves data)*

- **LanguagePreference**: a saved preference connecting a bot user to a supported language.
- **LocalizedCategoryContent**: localized display data for a category, including language and name.
- **LocalizedCourseContent**: localized display data for a course, including language, name, and
  description.
- **ParserSource**: an administrator-configured external resource that can be parsed for catalog
  data.
- **ParserJob**: a parsing execution record with source, status, timestamps, counts, and safe error
  details.
- **ImportedCatalogItem**: draft/inactive category or course data produced by parsing and awaiting
  admin review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can choose a language and reach the localized main menu in 3 taps or fewer.
- **SC-002**: A returning user sees the saved language applied on `/start` without repeating language
  selection.
- **SC-003**: 95% of localized catalog views show translated content when translations exist, and a
  default-language fallback when they do not.
- **SC-004**: Search suggestions appear for valid queries of 3 or more characters in under 1 second
  on the phase-1 catalog size.
- **SC-005**: At least 90% of partial-name searches in the test catalog return a relevant selectable
  suggestion.
- **SC-006**: Imported catalog data remains invisible to bot users until reviewed/approved by an
  administrator.
- **SC-007**: Re-running the same parser source does not create duplicate public categories or
  courses.
- **SC-008**: All new language, search suggestion, and parser job flows have automated coverage.

## Assumptions

- Ukrainian is the default language; English is the second supported language for the first
  multilingual release.
- Additional languages should be addable later without changing the user-facing behavior described
  here.
- Telegram does not provide a true native dropdown while typing in normal chat; suggestion-style
  selectable inline buttons are the expected user experience after a query of 3 or more characters.
- External parsing sources are configured by administrators and treated as untrusted input.
- Parsed catalog data is not published automatically; admin review is required before visibility.
- Existing admin authentication, catalog management, order handling, payment behavior, Docker-first
  development, and secret-handling rules remain in force.
