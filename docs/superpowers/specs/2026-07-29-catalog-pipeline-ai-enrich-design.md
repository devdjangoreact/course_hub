# Catalog pipeline: BotFather post, Flancki parse, AI enrich

**Date:** 2026-07-29  
**Status:** Implemented (first slice)  
**Scope:** Local `tools/catalog/` pipeline (parse → normalize → AI enrich → optional post/sync); BotFather for channel post; Pyrogram user for Flancki source; pluggable AI (nvidia default, openrouter, aws); keys in `.env`; shared catalog channel env also on Vercel.

## Goal

One local pipeline that downloads Flancki posts, writes a **unified course JSON**, enriches metadata with AI (including original public URL for ~2026 courses), and can post via BotFather + sync DB. Full content stays local + private channel; Vercel bot uses DB + channel refs. Parsing/AI libs stay off Vercel.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Approach | Single `run_pipeline.py` + layered modules under `tools/catalog/` |
| Flancki adapter | Port `scripts/download_group_posts.py` → `tools/catalog/parsers/flancki_pyrogram.py` |
| Telegram parse auth | Pyrogram **user** (`TG_API_ID`, `TG_API_HASH`, phone/session) |
| Telegram post auth | **BotFather** `BOT_TOKEN` only (channel created manually) |
| AI providers | `AI_PROVIDER=nvidia\|openrouter\|aws` in env; default **nvidia** |
| NVIDIA | `https://integrate.api.nvidia.com/v1`, model `z-ai/glm-5.2` |
| Secrets | All keys in `.env` (gitignored); `config.py` reads env only |
| Vercel env (app) | `BOT_TOKEN`, `CATALOG_CHANNEL_ID`, `CATALOG_INVITE_LINK` (needed at runtime for invite/copy fallbacks) |
| Vercel must NOT get | Flancki parse code, pyrogram user sessions, AI enrich scripts, `TG_API_*` for catalog tools (optional: omit from prod if unused by app) |
| Unified JSON extras | `links`, `authors`, `year`, `tags`, `other`, `original_url` |
| DB | Catalog fields + short refs in `extra` (`original_url`, `year`, `tags`, channel/promo ids); no full promo/full bodies |

## Out of scope

- Browser Flancki / supersliv adapters (later)
- Committing real API keys or phone numbers
- Running parse/enrich on Vercel

## Architecture

```
[.env local]
  TG_*  → flancki_pyrogram (user)
  BOT_TOKEN + CATALOG_* → post_channel (bot)
  AI_* → enrich
  DATABASE_URL → sync_db

[tools/catalog/run_pipeline.py]
  --parse → raw export under data/telegram_exports/...
  --normalize → data/catalog/categories/.../*.json
  --enrich → AI fills links/authors/year/tags/other/original_url
  --post → Bot API send to CATALOG_CHANNEL_ID, write telegram.* message ids
  --sync-db → upsert Course/Category

[Vercel app]
  BOT_TOKEN, CATALOG_CHANNEL_ID, CATALOG_INVITE_LINK in Settings
  Bot: promo copyMessage / invite / download (existing delivery design)
```

## Unified course JSON (final list item)

Existing fields remain. Add:

| Field | Type | Source |
|-------|------|--------|
| `links` | `string[]` | parse + AI |
| `authors` | `string[]` | AI (and parse if present) |
| `year` | `number \| null` | AI / text |
| `tags` | `string[]` | AI |
| `other` | `array` | AI catch-all notes/objects |
| `original_url` | `string \| null` | AI; required search effort when year is 2026+ or unknown-new |

`download_link` stays the delivery/download URL (from Flancki/source). `original_url` is the public official/course landing page when found.

## Module layout

```
tools/catalog/
  config.py                 # load dotenv from repo .env; expose typed getters
  course_json.py
  normalize.py
  enrich.py
  run_pipeline.py
  post_channel.py           # BOT_TOKEN (HTTP Bot API or pyrogram bot_token)
  sync_db.py                # extend extra with original_url/year/tags
  create_channel.py         # optional/deprecated for bot-only flow; channel manual
  parsers/flancki_pyrogram.py
  ai/base.py
  ai/factory.py
  ai/nvidia.py
  ai/openrouter.py
  ai/aws.py
```

Keep `.vercelignore` entries for `tools/` and `data/`.

## Environment

**Local `.env` / documented in `.env.example`:**

```
# Catalog tools — Telegram user (parse)
TG_API_ID=
TG_API_HASH=
TG_PHONE=
TG_SESSION_NAME=catalog_user
TG_FLANCKI_CHAT_ID=-1001343804259

# Shared with Vercel app — bot + delivery channel
BOT_TOKEN=
CATALOG_CHANNEL_ID=
CATALOG_INVITE_LINK=
CATALOG_DISCUSSION_GROUP_ID=

# AI
AI_PROVIDER=nvidia
NVIDIA_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
AWS_BEDROCK_MODEL_ID=

DATABASE_URL=
```

**Vercel / `.env.prod`:** at minimum `BOT_TOKEN`, `CATALOG_CHANNEL_ID`, `CATALOG_INVITE_LINK` (plus existing app vars). Wire into `app/core/config.py` as `catalog_channel_id`, `catalog_invite_link` for bot fallbacks when course `extra` lacks them.

## Pipeline CLI

```bash
python tools/catalog/run_pipeline.py --parse --enrich
python tools/catalog/run_pipeline.py --enrich --post --sync-db
```

Flags combinable. Default: `--parse --enrich` (no post/sync unless asked).

## AI enrich behaviour

1. Input: title, existing links/text snippet, optional year hint from post date/text.  
2. Output JSON only: `links`, `authors`, `year`, `tags`, `other`, `original_url`.  
3. If `year >= 2026` (or model judges course is current-year): attempt to identify a real public original course URL; if uncertain set `original_url` null and explain in `other`.  
4. Merge into course JSON without wiping `promo` / `full_description` / `telegram` / `source`.  
5. Provider selected via `AI_PROVIDER`; OpenAI-compatible HTTP for nvidia/openrouter; aws via Bedrock runtime (thin wrapper).

## Bot post (BotFather)

- Require `BOT_TOKEN` + `CATALOG_CHANNEL_ID`.  
- Bot must be admin of the channel.  
- Send promo then full_description; write `telegram.*` including `invite_link` from `CATALOG_INVITE_LINK`.  
- Do not require `TG_API_ID` for post.

## Sync DB

Upsert as today (`catalog_slug`). Also set in `extra`: `original_url`, `year`, `tags`, `authors` (short lists), plus existing download/channel/promo refs. Do not store full `other` blobs if large — store truncated or skip; prefer keeping full `other` only in JSON files.

## Security

- Remove hardcoded secrets from any ported `download_group_posts.py` logic.  
- Never commit `.env`.  
- Sessions under `sessions_parogram/` / tools session path — gitignore if not already.

## Implementation order

1. Config from `.env` + example keys; app Settings for `CATALOG_*`.  
2. AI factory (nvidia/openrouter/aws stubs with working nvidia+openrouter).  
3. Port Flancki parser to tools (no secrets in file).  
4. normalize + enrich + extend fixture schema.  
5. `post_channel` on BOT_TOKEN; simplify/skip user create_channel.  
6. `run_pipeline.py` + sync_db extra fields.  
7. Bot fallback to `settings.catalog_channel_id` / invite when extra missing.

## Open points (non-blocking)

- Exact AWS Bedrock model id left to env `AWS_BEDROCK_MODEL_ID`.  
- Whether to delete or thin-wrap `scripts/download_group_posts.py` after port (prefer thin wrapper calling tools, or README pointer only).
