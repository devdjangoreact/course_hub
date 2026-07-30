# Local catalog toolbox + delivery (channel / bot / email)

**Date:** 2026-07-28  
**Status:** Implemented (first vertical slice)  
**Scope:** Architecture for local course ingest/storage, private Telegram channel delivery, DB catalog sync, bot + email promo/download flow. Real parsers (Flancki / supersliv) deferred to a later phase.

## Goal

Keep full course content and parsing tooling **off Vercel**. Local JSON is the source of truth. A private Telegram channel (+ linked discussion group) and email deliver content to buyers. Postgres on Vercel stores only catalog structure. The bot shows short catalog text, sends **promo before payment**, and sends **download link after payment** (email mirrors the same post-payment delivery; promo email optional).

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Overall approach | Local toolbox in-repo (`tools/catalog/`) + `data/catalog/` JSON; Vercel app only consumes DB |
| Source of truth | Local JSON per course (unified schema for all adapters) |
| Full content storage | Local files + private TG channel archive (not DB, not Vercel filesystem) |
| Customer TG access | Private channel + linked discussion; bot sends invite link (no per-post ACL in Telegram) |
| DB fields | Map JSON → existing `Course`: `title`→`name`, `short_description`→`description`, category, `price`; refs in `extra` (and optionally `link` for download) |
| Parse / post / sync-db | Separate local scripts; settings hardcoded in script/config files |
| Parser backends (later) | Named adapters: `telegram_flancki_pyrogram`, `telegram_flancki_browser`, `browser_supersliv_biz`, extensible |
| Browser role | Per-adapter (TG Web or site); not one global mode |
| First vertical slice | Fixture JSON → create channel → post → sync_db → bot promo/download + email after pay |
| Email | After order: download link (+ access). Also usable as promo/ad material before pay |
| Vercel | No parser/post code; no pyrogram/playwright in deploy deps; `.vercelignore` for `tools/`, `data/` |

## Out of scope (this design / first plan)

- Adapter-specific parsing rules (e.g. one TG post → many courses)
- Website scrape implementation for supersliv.biz
- Multi-account public republish automation details (enabled by local JSON; scripts later)
- Changing payment provider logic beyond hooks to send download/promo

## Architecture

```
[Local only]
  tools/catalog/          create_channel, post_channel, sync_db, parsers/* (later)
  data/catalog/**/*.json  source of truth (full text, media paths, telegram refs)

       │ sync_db
       ▼
[Vercel app]
  Postgres: category + course catalog + extra refs
  Bot: short desc; promo before pay; download_link (+ invite) after pay
  Email: promo optional; download after pay
```

### Isolation from Vercel

- Code lives under `tools/catalog/`; data under `data/catalog/`.
- `.vercelignore` includes `tools/` and `data/`.
- Deploy requirements / Poetry main dependencies must **not** include pyrogram, playwright, or other ingest-only libs.
- `tools/catalog/requirements.txt` is for local runs only.

### Local layout

```
tools/catalog/
  requirements.txt
  config.py              # script parameters (channel, DB URL, bot tokens for user client, etc.)
  create_channel.py
  post_channel.py
  sync_db.py
  parsers/               # later: flancki_pyrogram, flancki_browser, supersliv_biz

data/catalog/
  categories/
    <category_slug>/
      <course_slug>.json
      media/             # optional local assets referenced by JSON
```

Fixture already added for pipeline checks:

- `data/catalog/categories/test/sample-python-basics.json`

## Unified course JSON schema

Required conceptual fields (all adapters normalize to this):

| Field | Role |
|-------|------|
| `slug` | Stable id for files and upsert |
| `category.slug` / `category.title` | Category grouping |
| `title` | Catalog + channel title |
| `short_description` | DB + bot catalog card |
| `price` | Catalog price |
| `promo.text` / `promo.media[]` | Advertising materials **before** payment |
| `full_description` | Full readable Telegram-oriented body for archive/repost |
| `download_link` | Course download URL **after** payment |
| `telegram.*` | Filled by `post_channel`: `channel_id`, `discussion_group_id`, `invite_link`, `promo_message_ids`, `full_message_ids` |
| `source.adapter` / `external_id` / `raw_refs` | Provenance for dedup and re-parse |

## Local scripts (first slice)

Parameters live in the script or `tools/catalog/config.py` (not required on Vercel).

1. **`create_channel`** — create private channel, link discussion group, store ids/invite in config or JSON side state.
2. **`post_channel`** — read course JSON, post promo and/or full description (+ media), write `telegram.*` message ids and invite back into JSON.
3. **`sync_db`** — upsert category + course: `title`→`name`, `short_description`→`description`, category, price; put `download_link`, invite, `promo_message_ids`, `channel_id` into `Course.extra` (optionally also `Course.link` = download). Do **not** store full promo/full_description bodies in DB.

Parsers later only write/update the same JSON files; they do not talk to Vercel directly except via optional local `sync_db`.

## Bot + email delivery (`app/` on Vercel)

Uses only DB (+ Telegram Bot API against channel the bot can access).

| Moment | Bot | Email |
|--------|-----|--------|
| Browse course (before pay) | Show `short_description`; send **promo** (prefer `copyMessage` from channel using `extra.promo_message_ids`, else short fallback) | Optional promo / ad material |
| After successful payment | Send **`download_link`**; optionally private channel **invite** | Same: download link (+ access if configured) |

No requirement for per-user access to a single channel post (Telegram does not support that). Access model is: channel membership via invite and/or direct download link in DM/email.

## Data flow (happy path)

1. Author or parser produces `data/catalog/.../<course>.json`.
2. Operator runs `create_channel` once (or reuses existing channel).
3. Operator runs `post_channel` for courses to publish.
4. Operator runs `sync_db` against production/dev `DATABASE_URL`.
5. User in bot sees catalog from DB → promo before pay → pays → bot + email send download link.

## Error handling (design level)

- `post_channel` / `sync_db` fail closed: do not partial-mark JSON telegram refs without successful post; sync skips courses missing required catalog fields.
- Bot: if promo message ids missing, fall back to `short_description` only; if download_link missing after pay, log and notify operator path (static error message to user).
- Email failures must not roll back payment; log and allow retry/resend.

## Testing

- Use fixture JSON to verify post → sync → bot paths.
- Do not add automated test suite unless explicitly requested.

## Implementation order

1. `.vercelignore` + document local-only deps.
2. Formalize JSON schema + keep/extend fixture.
3. `create_channel` / `post_channel` / `sync_db` local scripts.
4. Bot handlers: promo before pay, download (+ invite) after pay.
5. Email after pay (and optional promo email).
6. Later: parser adapters writing the same JSON.

## Open points (non-blocking)

- Exact email provider already in app vs new mailer — resolve during planning by inspecting existing payments/notify code.
- Default for first implementation: set both `Course.link` and `extra.download_link` to the same download URL so existing bot link UI keeps working; invite stays in `extra.invite_link` only.
