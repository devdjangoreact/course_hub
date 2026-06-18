# Research: lava.top Payment Integration

**Feature**: `003-lava-payments` | **Date**: 2026-06-17

## Provider selection

- **Decision**: Use official `lava-top-sdk` (Python) for invoice creation and webhook parsing.
- **Rationale**: SDK matches OpenAPI spec, handles currencies/methods, and provides
  `parse_webhook` / signature helpers; reduces hand-rolled HTTP errors.
- **Alternatives considered**: Raw httpx to gate API (more maintenance); unofficial wrappers
  (less maintained).

## Sync SDK in async app

- **Decision**: Wrap synchronous SDK calls in `asyncio.to_thread`.
- **Rationale**: Keeps FastAPI/aiogram handlers non-blocking without adding a sync HTTP client to the
  event loop.
- **Alternatives considered**: Fork SDK to async httpx (out of scope).

## Webhook authentication

- **Decision**: Validate `X-Api-Key` header against `payment_settings.secret_key` (webhook key shared
  with lava.top dashboard).
- **Rationale**: Matches lava.top docs for "Your service's API key" webhook auth mode.
- **Alternatives considered**: Basic auth (not used in our deployment); HMAC `signature` header (SDK
  supports it but dashboard config uses X-Api-Key).

## Course-to-offer mapping

- **Decision**: Store `lava_offer_id` in `courses.extra` JSON.
- **Rationale**: FR-010; avoids migration; consistent with existing `extra` pattern for extensibility.
- **Alternatives considered**: New DB column (unnecessary migration for one UUID field).

## Buyer email

- **Decision**: Persist `payment_email` in `bot_users.extra`; bot prompts when missing for lava orders.
- **Rationale**: lava.top requires email for invoice creation; Telegram users rarely expose email.
- **Alternatives considered**: Synthetic emails from telegram_id (poor deliverability/receipts).

## Payment reference

- **Decision**: Store lava invoice/contract `id` returned by `create_one_time_payment` as
  `order.payment_reference`.
- **Rationale**: Webhook payload includes `contractId` for lookup; matches existing order lookup by
  reference.
- **Alternatives considered**: Internal order id only (webhook would not carry it reliably).

## Scope boundaries

- **Decision**: One-time purchases only; no subscription webhooks in v1.
- **Rationale**: Course Hub sells individual courses; subscription flow adds recurring webhook type and
  billing periods not required now.
- **Alternatives considered**: Full subscription support (deferred).

## Environment

- **Decision**: `lava_env` in `payment_settings.extra` (`sandbox` | `production`), default `production`.
- **Rationale**: SDK supports both; sandbox for operator testing before go-live.
- **Alternatives considered**: Separate env var only (admin panel cannot change without redeploy).

## IP allowlisting

- **Decision**: Document lava webhook source IP `158.60.60.174` in quickstart for operators; no app-level
  IP filter (Traefik/firewall responsibility).
- **Rationale**: Constitution keeps infra concerns in infra repo.
- **Alternatives considered**: Application IP middleware (duplicates infra controls).
