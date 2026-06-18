# Feature Specification: Course Hub — lava.top Payment Integration

**Feature Branch**: `003-lava-payments`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "Integrate lava.top payment service (https://developers.lava.top/) for accepting course purchase payments in Course Hub."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pay for a course via lava.top (Priority: P1)

A Telegram user selects a course and taps **Order**. The bot creates a pending order and returns a
secure payment link from lava.top. The user completes payment on the lava.top checkout page.

**Why this priority**: Real monetization is the core outcome of integrating a payment provider.

**Independent Test**: Configure lava.top credentials and a course offer mapping, create an order from
the bot, open the returned payment URL, and confirm a pending order exists with a lava payment
reference.

**Acceptance Scenarios**:

1. **Given** payment provider is set to lava.top and the course has a mapped lava offer, **When** the
   user orders the course with a valid email, **Then** the bot returns a lava.top payment link and
   the order stays `pending`.
2. **Given** lava.top credentials are missing or invalid, **When** an order is created, **Then** the
   user receives a clear error and no broken payment link is shown.
3. **Given** the course has no lava offer mapping, **When** the user tries to order with lava.top
   enabled, **Then** the bot explains the course is not available for purchase yet.

---

### User Story 2 - Payment confirmation via webhook (Priority: P1)

When lava.top reports a payment result, Course Hub updates the matching order and notifies the buyer
in Telegram. Duplicate webhook deliveries must not change an already-finalized order or send duplicate
notifications.

**Why this priority**: Without reliable confirmation, paid users would not receive access or status
updates.

**Independent Test**: Send a valid lava.top `payment.success` webhook for a pending order and confirm
the order becomes `paid` and the user is notified once; resend the same webhook and confirm no
duplicate side effects.

**Acceptance Scenarios**:

1. **Given** a pending order with a lava payment reference, **When** lava.top sends
   `payment.success`, **Then** the order becomes `paid` and the user is notified.
2. **Given** a pending order, **When** lava.top sends `payment.failed`, **Then** the order becomes
   `failed` and the user can retry.
3. **Given** an order already `paid`, **When** the same success webhook is delivered again, **Then**
   the system returns success without duplicate notifications.
4. **Given** a webhook with invalid authentication, **When** it is received, **Then** the request is
   rejected and the order is unchanged.

---

### User Story 3 - Collect buyer email for checkout (Priority: P2)

lava.top requires a buyer email to create a payment. When a user orders with lava.top and has no saved
payment email, the bot asks for one, validates the format, saves it for future orders, and continues
checkout.

**Why this priority**: Email is required by the provider; collecting it in-bot keeps the purchase flow
self-contained.

**Independent Test**: Order a course as a new user with lava.top enabled, provide an email when
prompted, and confirm the payment link is issued; order again and confirm the saved email is reused.

**Acceptance Scenarios**:

1. **Given** a user has no saved payment email, **When** they tap **Order** with lava.top enabled,
   **Then** the bot asks for an email address.
2. **Given** the user enters a valid email, **When** checkout continues, **Then** the email is saved
   and used for the lava.top payment.
3. **Given** the user enters an invalid email, **When** they submit it, **Then** the bot asks again
   with a validation message in the user's language.

---

### User Story 4 - Keep simulated payments for development (Priority: P2)

Developers and testers can still run the full order lifecycle locally using the existing simulated
payment provider without lava.top credentials.

**Why this priority**: Preserves fast local testing and CI behavior established in phase 1.

**Independent Test**: Set provider to `simulated`, create an order, confirm via simulate endpoint,
and verify order status updates as before.

**Acceptance Scenarios**:

1. **Given** `PAYMENT_PROVIDER=simulated`, **When** an order is created, **Then** the simulated
   payment link and HMAC webhook flow work unchanged.
2. **Given** production uses lava.top, **When** development uses simulated, **Then** no lava.top
   credentials are required locally.

---

### Edge Cases

- lava.top webhook retries (up to 20 attempts) must remain idempotent.
- Course price in Course Hub may differ from lava offer price; lava offer price is authoritative at
  checkout.
- Unsupported currency or payment method combinations are rejected with a user-friendly message.
- Network or provider errors during invoice creation leave the order `pending` or `failed` with a
  logged error (no secrets in logs).
- Orders created before switching providers keep their existing payment references.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support `lava` as a payment provider alongside the existing `simulated`
  provider, selected via configuration.
- **FR-002**: System MUST create a lava.top one-time payment (invoice) when a user orders a course
  mapped to a lava offer.
- **FR-003**: System MUST store the lava payment/contract identifier as the order payment reference.
- **FR-004**: System MUST expose an HTTPS webhook endpoint for lava.top **Payment result** events
  (`payment.success`, `payment.failed`).
- **FR-005**: System MUST authenticate incoming lava.top webhooks using the configured webhook API
  key (`X-Api-Key` header).
- **FR-006**: System MUST map lava events to order statuses: success → `paid`, failed → `failed`,
  cancelled → `cancelled`.
- **FR-007**: System MUST process webhooks idempotently for terminal order states.
- **FR-008**: System MUST notify the buyer via Telegram when payment status changes after a webhook.
- **FR-009**: System MUST allow admins to configure lava API key, webhook key, currency, and
  environment (sandbox/production) through existing payment settings (env seed + admin panel).
- **FR-010**: System MUST store a lava offer identifier per course (via course `extra`) for mapping.
- **FR-011**: System MUST collect and persist a buyer email before lava checkout when none is saved.
- **FR-012**: System MUST NOT log payment API keys, webhook secrets, or full webhook payloads
  containing sensitive data.
- **FR-013**: System MUST keep the simulated payment flow fully functional when selected.

### Key Entities

- **PaymentSettings**: Provider (`simulated` | `lava`), API key, webhook secret, currency, lava
  environment flag in `extra`.
- **Course**: Optional `lava_offer_id` in `extra` linking to a lava.top product offer.
- **Order**: Existing lifecycle; `payment_reference` holds lava contract/invoice id for lava orders.
- **BotUser**: Optional saved `payment_email` in `extra` for repeat checkout.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A buyer with a mapped course and valid email can reach a lava.top checkout page in under
  30 seconds from tapping **Order**.
- **SC-002**: 100% of authenticated `payment.success` webhooks for valid pending orders update the
  order to `paid` exactly once.
- **SC-003**: Duplicate webhook deliveries for the same paid order produce zero additional Telegram
  notifications.
- **SC-004**: Development environments using `simulated` provider complete the full order/payment test
  flow without external network calls to lava.top.
- **SC-005**: Invalid webhook authentication is rejected with HTTP 401 in 100% of test cases.

## Assumptions

- Scope is **one-time course purchases** only; subscription billing via lava.top is out of scope for
  this feature.
- Each sellable course has a corresponding offer created in the lava.top author dashboard; admins copy
  the offer UUID into the course record.
- Production webhooks use HTTPS and the `X-Api-Key` authentication method configured in lava.top.
- lava.top outbound webhook IP `158.160.60.174` may be allowlisted at the infrastructure layer
  (documented for operators; not enforced in application code).
- Supported currencies follow lava.top rules: USD/EUR for international methods, RUB for BANK131.
- Existing multilingual order/payment bot messages from feature `002-multilingual-search` are reused.
