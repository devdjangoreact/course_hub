# Feature Specification: Course Hub — FastAPI Backend + Telegram Bot

**Feature Branch**: `001-fastapi-telegram-bot`

**Created**: 2026-06-11

**Status**: Draft

**Input**: User description: Build an async Python service for `course_hub` that exposes courses
grouped by category with full-text search through a Telegram bot, lets users place orders/payments,
and provides a simple admin panel (including bot token and backend URL configuration). Two run
profiles (development/testing and production) with separate bot tokens; SQLite in phase 1 with an
easy switch to PostgreSQL via environment configuration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse courses by category in Telegram (Priority: P1)

A prospective student opens the Telegram bot, sees a menu, picks a category from the list, and
browses the courses inside it. Each course shows its name, description, price, and a link.

**Why this priority**: Discovery of courses is the core value of the bot; without it the product
delivers nothing.

**Independent Test**: Start the bot with seeded categories and courses, send `/start`, tap a
category, and confirm the active courses for that category are listed with their details.

**Acceptance Scenarios**:

1. **Given** the bot is running and categories exist, **When** the user sends `/start`, **Then** a
   menu with a "Categories" entry and a "Search" entry is shown.
2. **Given** the categories list is shown, **When** the user selects a category, **Then** only the
   active courses in that category are listed.
3. **Given** a category has no active courses, **When** the user selects it, **Then** a friendly
   "no courses yet" message is shown.

---

### User Story 2 - Full-text course search in Telegram (Priority: P1)

A user wants a specific topic and types keywords. The bot returns matching courses ranked by
relevance across course name and description.

**Why this priority**: Search complements browsing and is required by the request; it makes large
catalogs usable.

**Independent Test**: Seed several courses, trigger search, send a query that matches a subset, and
confirm only relevant active courses are returned.

**Acceptance Scenarios**:

1. **Given** the user chose "Search", **When** they send a text query, **Then** active courses
   whose name or description match are returned, most relevant first.
2. **Given** a query matches nothing, **When** it is sent, **Then** a "no results" message is shown.
3. **Given** a query is empty or whitespace, **When** it is sent, **Then** the bot asks for a valid
   search term.

---

### User Story 3 - Place an order and pay (Priority: P2)

After choosing a course, the user taps "Order", the bot creates an order, and guides the user
through payment. The order status reflects the payment outcome.

**Why this priority**: Monetization; valuable but depends on discovery (P1) existing first.

**Independent Test**: Select a course, create an order, simulate a successful payment callback, and
confirm the order moves to a paid state and the user is notified.

**Acceptance Scenarios**:

1. **Given** a course is shown, **When** the user taps "Order", **Then** a pending order is created
   and a payment instruction/link is returned.
2. **Given** a pending order, **When** payment succeeds, **Then** the order becomes paid and the
   user receives a confirmation.
3. **Given** a pending order, **When** payment fails or is cancelled, **Then** the order is marked
   failed/cancelled and the user can retry.

---

### User Story 4 - Manage catalog and bot settings in admin panel (Priority: P2)

An administrator (a persisted admin account) signs in to a simple web admin to create/edit/delete
categories and courses, view orders, and edit bot settings — including the bot token and the backend
(callback/base) URL — and payment settings.

**Why this priority**: Operators need to manage content and configuration without redeploying;
required by the request but not needed for the very first browsing demo.

**Independent Test**: Sign in to the admin, create a category and a course, confirm they appear in
the bot; update the bot token and backend URL and confirm the values are persisted.

**Acceptance Scenarios**:

1. **Given** the admin is signed in, **When** they create a category and a course, **Then** the new
   items are persisted and visible to the bot.
2. **Given** the admin edits the bot token and backend URL, **When** they save, **Then** the new
   values are persisted and used by the bot/runtime.
3. **Given** the admin edits payment settings, **When** they save, **Then** the new values are
   persisted and used by the payment flow.
4. **Given** an anonymous visitor, **When** they open an admin page, **Then** access is denied until
   authenticated against a persisted admin account.

---

### Edge Cases

- The configured bot token is missing or invalid at startup → the service reports a clear,
  actionable error and the admin can still load to fix settings.
- A user sends search queries too quickly → requests beyond the per-user rate limit are throttled
  with a friendly "please slow down" message.
- Search query contains special characters or very long input → input is sanitized/limited and does
  not break the search.
- A course is deactivated while a user is viewing it → it no longer appears in lists/search and
  cannot be newly ordered.
- A payment callback arrives twice for the same order → the order state change is idempotent.
- The catalog is empty → the bot and admin both render empty states without errors.
- Switching the database target (SQLite ↔ PostgreSQL) must not require code changes, only
  configuration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST present a Telegram menu after `/start` offering category browsing and
  search.
- **FR-002**: System MUST list categories and, for a selected category, list its active courses with
  name, description, price, and link.
- **FR-003**: System MUST provide full-text search over course name and description and return
  active matches ranked by relevance.
- **FR-003a**: System MUST rate-limit Telegram search to at most 5 searches per user per minute and
  return a friendly throttling message when the limit is exceeded.
- **FR-004**: System MUST allow a user to create an order for a course and track its lifecycle
  (pending → paid / failed / cancelled).
- **FR-005**: System MUST accept payment confirmation and update the corresponding order
  idempotently, then notify the user.
- **FR-006**: System MUST provide a simple admin panel, authenticated against persisted admin
  accounts, to manage categories, courses, and to view orders.
- **FR-006a**: System MUST persist admin user accounts (credentials stored securely as hashes, never
  plaintext) and authenticate the admin panel against them.
- **FR-007**: System MUST let an administrator view and edit bot settings, including the bot token
  and the backend (base/callback) URL, and persist them.
- **FR-007a**: System MUST persist payment settings (provider configuration/keys) as a separate,
  admin-editable entity, with secrets never logged.
- **FR-008**: System MUST support two run profiles — development/testing and production — selected by
  configuration, each with its own bot token and settings.
- **FR-009**: System MUST persist data in SQLite by default and allow switching to PostgreSQL purely
  via configuration, with no source-code changes.
- **FR-010**: System MUST only expose active courses to bot users; inactive courses are hidden from
  lists, search, and new orders.
- **FR-011**: System MUST validate and sanitize all external input (search queries, admin forms,
  payment callbacks) and reject malformed input with clear messages.
- **FR-012**: System MUST restrict admin functionality to authenticated administrators.
- **FR-013**: System MUST record key operational events and errors with enough context for
  troubleshooting, without leaking secrets.
- **FR-014**: System MUST persist Telegram bot users so returning users are recognized across
  sessions and linked to their orders.
- **FR-015**: Every persisted entity MUST include an extensible, optional structured (JSON) field
  for item-specific data that does not require a schema change to populate.
- **FR-016**: All HTTP endpoints and the full payment process MUST be covered by automated tests.

### Key Entities *(include if feature involves data)*

Every entity below also carries an optional structured (JSON) `extra` field for item-specific data
(FR-015).

- **Category**: a grouping of courses. Attributes: name. Relationship: has many Courses.
- **Course**: a sellable course. Attributes: name, description, category (reference), price, link,
  active flag. Relationship: belongs to one Category; has many Orders.
- **BotUser**: a persisted Telegram user interacting with the bot. Attributes: Telegram id,
  name/username, first-seen. Relationship: has many Orders.
- **Order**: a purchase intent for a course. Attributes: buyer (BotUser), course (reference),
  amount, status (pending/paid/failed/cancelled), created/updated timestamps, payment reference.
- **AdminUser**: a persisted administrator account for the admin panel. Attributes: username, hashed
  password, active flag.
- **BotSettings**: runtime-editable bot configuration. Attributes: bot token, backend/base URL, plus
  other adjustable bot options.
- **PaymentSettings**: runtime-editable payment configuration. Attributes: provider, API/secret keys
  (never logged), currency, and provider-specific options.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from `/start` to viewing a category's courses in 3 taps or fewer.
- **SC-002**: Search returns results for a matching query in under 1 second on the phase-1 catalog.
- **SC-003**: 95% of valid orders reach a terminal state (paid/failed/cancelled) without manual
  intervention.
- **SC-004**: An administrator can create a category and a course and see it in the bot in under 2
  minutes, with no redeploy.
- **SC-005**: Switching from SQLite to PostgreSQL is completed by changing configuration only, with
  zero code edits, and the app starts successfully against both.
- **SC-006**: The same build runs in both development/testing and production profiles using only
  configuration differences (including distinct bot tokens).
- **SC-007**: A user is limited to 5 searches per minute; the 6th within the window is throttled with
  a clear message.
- **SC-008**: 100% of HTTP endpoints and the payment lifecycle are exercised by automated tests.

## Assumptions

- The bot operates in a single language for phase 1; localization is out of scope.
- Payment integration in phase 1 may use a single provider or a simulated/manual confirmation flow;
  the order lifecycle and idempotent confirmation are the binding requirements.
- The admin panel is a simple tool in phase 1 authenticated against persisted admin accounts (login
  with hashed passwords), not a multi-role RBAC system.
- Development runs entirely in Docker (code, dependencies, and environment inside containers); Poetry
  is used inside the container or locally within the submodule project, never installed globally.
- Full-text search in phase 1 uses the database's built-in capabilities and is expected to scale to
  PostgreSQL search later without changing the user-facing behavior.
- Media/file uploads for courses are out of scope for phase 1 (links only).
- The service is deployed as a container behind the existing infra (Traefik) routing for the
  `course_hub` domain.
