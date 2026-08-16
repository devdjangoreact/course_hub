---
name: vercel-prod-info
description: Fetches Vercel production deployment status and logs via REST API using .env.prod credentials (no CLI). Use when the user asks about production, Vercel logs, prod deploy status, live errors, Telegram webhook on prod, or why prod is down.
---

# Vercel production info

Do not use Vercel CLI. Do not read `.env`, `.env.prod`, or print secrets.
Write output to `logs/vercel-prod.log` and **read that file**. Do not rely on console stdout.

## Command

From repo root:

```bash
python scripts/vercel_prod_info.py --since 24h --skip-runtime
```

Default `--out` is `logs/vercel-prod.log`. Then Read that file.

Narrower:

```bash
python scripts/vercel_prod_info.py --since 1h --query Telegram --skip-runtime
python scripts/vercel_prod_info.py --since 15m --level error --skip-runtime
```

Omit `--skip-runtime` only if you need the live runtime stream (can wait ~12s and often returns empty on idle Hobby).

## Output

- `DEPLOYMENT` — latest production uid, state, url, created time
- `EVENTS` — build/stdout/stderr (use this first)
- `RUNTIME` — live function logs; empty if no traffic

## Rules

- Script loads `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` itself
- Summarize logs; do not paste tokens, cookies, or webhook secrets if they appear
- If the env file is missing keys, say so — do not open the file to hunt for values
