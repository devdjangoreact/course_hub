# Tasks: Course Hub — lava.top Payment Integration

**Input**: Design documents from `/specs/003-lava-payments/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Integration tests for lava webhook (explicit in spec success criteria).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

**Purpose**: Add dependency and configuration scaffolding

- [X] T001 Add `lava-top-sdk` to `pyproject.toml` and update lockfile via Poetry
- [X] T002 [P] Add `LAVA_ENV` and lava payment env vars to `.env.example`, `.env.dev.example`, `.env.prod.example`
- [X] T003 [P] Extend `app/core/config.py` with `lava_env` setting

---

## Phase 2: Foundational

**Purpose**: Gateway factory and shared helpers blocking all user stories

- [X] T004 Create `app/infrastructure/payments/gateway_factory.py` with `build_payment_gateway()`
- [X] T005 [P] Add `app/infrastructure/payments/lava_helpers.py` for currency/method mapping and email validation
- [X] T006 Wire gateway factory in `app/main.py` replacing direct `SimulatedPaymentGateway` construction
- [X] T007 Extend `app/bootstrap.py` to seed `lava_env` in payment settings `extra`

**Checkpoint**: Provider selection works at startup for `simulated` and `lava`

---

## Phase 3: User Story 1 — Pay via lava.top (Priority: P1) 🎯 MVP

**Goal**: Create lava invoice and return payment URL on order

**Independent Test**: Order a mapped course with email → receive `pay_url` and lava `payment_reference`

### Implementation

- [X] T008 [US1] Implement `LavaPaymentGateway` in `app/infrastructure/payments/lava_gateway.py`
- [X] T009 [US1] Extend `OrderService.create_order` to resolve course `lava_offer_id` and buyer email in `app/application/services/order_service.py`
- [X] T010 [US1] Pass course entity to gateway (extend `PaymentGateway.create_payment` signature or load course in gateway via repository — prefer passing offer id through order flow)

**Checkpoint**: Lava payment link issued for configured course

---

## Phase 4: User Story 2 — Webhook confirmation (Priority: P1)

**Goal**: Idempotent lava webhook updates orders and notifies users

**Independent Test**: POST valid lava webhook → order `paid`; repeat → no duplicate notify

### Tests

- [X] T011 [P] [US2] Integration tests in `tests/integration/test_lava_payments.py` (auth, success, idempotency, invalid key)

### Implementation

- [X] T012 [US2] Add `app/api/schemas/lava_webhook.py` for lava payload parsing
- [X] T013 [US2] Add `POST /api/payments/lava/webhook` in `app/api/routers/orders.py`
- [X] T014 [US2] Add `OrderService.confirm_lava_webhook()` with event-type mapping in `app/application/services/order_service.py`

**Checkpoint**: Webhook flow complete and tested

---

## Phase 5: User Story 3 — Buyer email collection (Priority: P2)

**Goal**: Bot collects and saves email before lava checkout

**Independent Test**: New user prompted for email; second order reuses saved email

### Implementation

- [X] T015 [US3] Add localized email prompt/validation messages in `app/bot/messages/catalog.py`
- [X] T016 [US3] Implement email collection state in `app/bot/handlers/order.py`
- [X] T017 [US3] Persist `payment_email` on `BotUser.extra` via `BotUserRepository`

**Checkpoint**: Email flow works for lava provider

---

## Phase 6: User Story 4 — Simulated provider unchanged (Priority: P2)

**Goal**: Development/CI path unaffected

**Independent Test**: Existing `tests/integration/test_payments.py` and `test_orders.py` pass

- [X] T018 [US4] Verify simulated gateway and `/api/payments/webhook` HMAC path unchanged; fix regressions if any

---

## Phase 7: Polish

- [X] T019 [P] Update `README.md` with lava.top setup summary
- [ ] T020 Run quickstart validation checklist manually (document in PR)

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 + US2 (can parallelize after T006) → US3 → US4 → Polish
- US2 tests (T011) can be written before T012–T014 (TDD)

## Implementation Strategy

1. Complete Phases 1–2 (foundation)
2. US1: payment link creation
3. US2: webhook + tests (MVP for production)
4. US3: email UX
5. US4: regression check
