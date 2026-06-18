# Implementation Plan: Course Hub — lava.top Payment Integration

**Branch**: `003-lava-payments` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-lava-payments/spec.md`

## Summary

Add a production-ready `lava` payment adapter to the existing `PaymentGateway` abstraction. When
`PAYMENT_PROVIDER=lava`, order creation calls the lava.top invoice API (via `lava-top-sdk`) using a
per-course `lava_offer_id` and the buyer's saved email. A dedicated webhook route authenticates
`X-Api-Key`, maps `payment.success` / `payment.failed` to order statuses idempotently, and notifies
the Telegram bot. The simulated provider remains the default for development and CI.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Existing stack (FastAPI, SQLAlchemy async, aiogram, Pydantic v2, httpx,
Loguru) plus `lava-top-sdk` for invoice creation and webhook parsing.

**Storage**: No new tables. Reuse `payment_settings`, `orders`, `courses.extra`, `bot_users.extra`.

**Testing**: pytest + pytest-asyncio. Add integration tests for lava webhook auth/mapping/idempotency
with a test double gateway; keep existing simulated payment tests unchanged.

**Development environment**: Docker-first via Poetry in the `course_hub` submodule.

**Target Platform**: Linux container behind existing Traefik routing.

**Project Type**: Async web service + Telegram bot worker.

**Performance Goals**: Payment link issuance within a few seconds (provider-bound); webhook
processing under 1 second excluding bot notification.

**Constraints**: Fully async paths (wrap sync SDK with `asyncio.to_thread`); never log secrets;
preserve existing simulated flow; localized bot messages; idempotent webhooks.

**Scale/Scope**: One-time course purchases only; single lava webhook type (Payment result); modest
order volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Plan compliance |
|---|-----------|-----------------|
| I | Repository Responsibility Separation | App logic in `course_hub` only. PASS |
| II | Single Source of Deployment Truth | No infra/deploy changes. PASS |
| III | Domain-Isolated Single-Server Routing | No host/port changes. PASS |
| IV | Secrets Never Touch Source Control | Keys in env/admin settings; logs redact secrets. PASS |
| VI | Reproducible, Pinned Containers | New dep pinned in Poetry lock. PASS |
| VII | Automated Validation Gates | Existing gates apply; new integration tests added. PASS |

Post-design re-check: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/003-lava-payments/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── lava-webhook.md
│   └── payment-gateway.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root: `course_hub/`)

```text
course_hub/
├── app/
│   ├── domain/repositories/payment_gateway.py   # unchanged interface
│   ├── application/services/order_service.py      # email + lava error paths
│   ├── infrastructure/payments/
│   │   ├── simulated_gateway.py                 # unchanged
│   │   ├── lava_gateway.py                      # new
│   │   └── gateway_factory.py                   # new
│   ├── api/
│   │   ├── routers/orders.py                    # lava webhook route
│   │   └── schemas/lava_webhook.py              # new
│   └── bot/handlers/order.py                    # email collection flow
├── tests/integration/
│   ├── test_payments.py                           # unchanged (simulated)
│   └── test_lava_payments.py                    # new
└── pyproject.toml                                 # lava-top-sdk dep
```

**Structure Decision**: Extend the existing `PaymentGateway` port with a lava adapter and factory.
No schema migration — mapping and email live in `extra` JSON columns already present.

## Complexity Tracking

No constitution violations requiring justification.
