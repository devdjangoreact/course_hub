# Proxied catalog worker (Docker) — publication-ready enrich

**Date:** 2026-08-09  
**Status:** Design approved (pending implementation plan)  
**Scope:** Local-only Docker worker + host orchestrator that runs course parse/fetch + AI enrich to Telegram-publication-ready JSON, with one authenticated upstream proxy per container (no mitm relay). Parallel containers for throughput. Never deployed to Vercel.

## Goal

Prepare course records to a JSON ready for a **later, separate** Telegram post step: search (SearXNG), page fetch (browser), LLM field extraction / quality gate. Canonical enrich behavior is today’s `scripts/enrich_with_searxng.py` (not the old Perplexity `tools/catalog/enrich.py`), but:

- All outbound traffic from a worker goes through **one** proxy set on the container (kill-switch model).
- No intermediate mitm/local relay bridge.
- Host runs many workers in waves (e.g. 5 containers × 5 courses), each container a different proxy.
- Inside one container, proxy does **not** change for the whole batch.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Runtime location | **Local only** (dev machine / local Docker). Not part of Vercel/serverless deploy |
| Vercel deploy | Worker image, orchestrator, SearXNG-in-worker, nodriver, proxy tooling **must not** ship to Vercel. **All feature code/files live under `tools/`** (already in `.vercelignore`) |
| Proxy model | Container env `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` (+ auth URL). No mitmproxy relay |
| Proxy change | Recreate container (same image, new env). No hot-swap without restart |
| Batching | One proxy per container for entire in-container loop (e.g. `BATCH_SIZE=5`) |
| Parallelism | Host orchestrator starts up to `WORKER_CONCURRENCY` containers; each gets a distinct proxy from `proxies.json` |
| Waves | When a wave finishes, take next course slice + next proxies, start new containers |
| Canonical enrich | Logic of `scripts/enrich_with_searxng.py` (SearXNG + browser fetch + pluggable LLM + quality gate) |
| Replace | `tools/catalog/enrich.py` (Perplexity self-search path) — **replace** with the SearXNG-based enrich moved under `tools/catalog/`; `run_pipeline` must call the new module |
| Worker job (v1) | Only enrich/prep: SearXNG → fetch pages → LLM → course JSON + routing hint (`flancki` / `need_enrich`). **No Telegram API** |
| Telegram publish | **Separate host path** — `tools/catalog/publish/` (shim `post_channel.py`). Never imported, never installed, never run inside the worker image |
| Generic browser ops API | **Out of v1**; same worker image is the future home if needed |
| SearXNG | Runs **inside** each worker (localhost). `NO_PROXY=localhost,127.0.0.1` so local SearXNG is not tunnelled |
| Browser | nodriver/Chrome with **direct** proxy URL (`user:pass@host:port`), not local relay |
| LLM | **Pluggable by settings** — same backends as `enrich_with_searxng.py` (`LLM_BACKEND` / provider env). Not hardcoded to one vendor |
| LLM traffic | All selected providers’ outbound calls go through the container proxy kill switch (where the SDK allows; Bedrock via AWS env proxy if used) |
| Code layout | Feature implementation under `tools/` — orchestrator, worker, Dockerfile, shared enrich/LLM. Migrate body of `scripts/enrich_with_searxng.py` into `tools/catalog/`; script may remain a thin wrapper or be removed later |
| Orchestrator | Host Python under `tools/catalog/`; talks Docker CLI or API; persists JSON on host. Does **not** call Bot API |
| Secrets | Stay in host `.env`; orchestrator forwards **only enrich/LLM/proxy keys** into `docker run` — never `BOT_TOKEN` / channel secrets into the worker |
| Existing mitm stack | Deprecated for this path; may remain under `tools/catalog/browser/` until worker path replaces host enrich |

## Out of scope (v1)

- Hot-swap proxy inside a running container
- mitm / local CONNECT relay
- **Any Telegram publish / Bot API / `post_channel` inside the container**
- Vercel/production hosting of worker or SearXNG
- Multi-op generic browser RPC (`parse_site`, etc.)
- Changing Bot / payment / DB sync flows (stay host-only, separate from worker)

## Architecture

```
[Host — local only]
  .env, data/catalog/, proxies.json
  orchestrator
    → wave: pick CONCURRENCY proxies + BATCH_SIZE courses each
    → docker run --rm worker
         -e HTTP_PROXY=http://user:pass@host:port
         -e HTTPS_PROXY=...
         -e ALL_PROXY=...
         -e NO_PROXY=localhost,127.0.0.1
         -e LLM_BACKEND=nvidia|openrouter|bedrock|...
         -e <provider keys/base URL/model from host .env>
         -v batch.json → result.json
    → write courses back (flancki / need_enrich)

[Worker container — ephemeral]
  SearXNG (127.0.0.1)
  nodriver Chrome     ──┐
  LLM (active backend)──┼──▶ upstream proxy (kill switch)
  (no direct net)     ──┘
```

### LLM providers (settings-driven)

Worker must not assume a single LLM vendor. Selection and credentials come from host settings (same contract as canonical `enrich_with_searxng` logic after it lives under `tools/catalog/`):

| Setting | Role |
|---------|------|
| `LLM_BACKEND` (or existing `AI_PROVIDER` alias if unified) | Chooses implementation: `nvidia` \| `openrouter` \| `bedrock` \| future backends |
| Provider-specific env | e.g. `NVIDIA_*`, `OPENROUTER_*`, `AWS_*` / Bedrock model id — only what the active backend needs |
| Model / base URL | From env; overridable per run if orchestrator passes them |

Rules:

1. **One active backend per worker run** (from host env at `docker run`); all jobs in that batch use it.
2. Switching provider = change host `.env` / orchestrator env and start a new wave (no code change in image for known backends).
3. Adding a new provider = extend the shared enrich LLM adapter inside the worker; image rebuild only when new deps are required.
4. Judge / retry LLM calls use the **same** active backend and the **same** proxy.
5. If a backend cannot honor HTTP proxy env (edge case), document it and either skip that backend for the worker path or use the SDK’s supported proxy hook — fail closed rather than silently going direct.

### Wave algorithm

```
courses ← pending publication-prep JSON
proxies ← pool (round-robin / works-first)
while courses remaining:
  workers ← min(WORKER_CONCURRENCY, remaining courses, available proxies)
  for i in 0..workers-1:
    jobs ← next BATCH_SIZE courses
    proxy ← next proxy
    start container(proxy, jobs)  # async
  wait all
  persist results; mark bad proxies if container/network failed
```

Defaults (configurable): `BATCH_SIZE=5`, `WORKER_CONCURRENCY=5`.

## Worker I/O contract

**Input** (stdin or mounted JSON):

```json
{
  "proxy": "host:port:user:pass",
  "llm": {
    "backend": "nvidia",
    "model": "optional-override",
    "base_url": "optional-override"
  },
  "jobs": [
    { "id": "2024-07-28_1528_03", "course": { } }
  ]
}
```

`llm` in the payload is optional if fully supplied via container env; when present it overrides model/base_url for that run. Secrets stay in env, never in the JSON file.

**Output**:

```json
{
  "ok": true,
  "meta": {
    "exit_ip": "x.x.x.x",
    "proxy": "host:port:user:pass",
    "llm_backend": "nvidia",
    "llm_model": "z-ai/glm-5.2"
  },
  "results": [
    {
      "id": "2024-07-28_1528_03",
      "ok": true,
      "course": { },
      "destination": "flancki" | "flancki_need_enrich" | null,
      "error": null
    }
  ]
}
```

Host is responsible for filesystem moves/`other.enrich_quality` persistence consistent with current enrich script behavior.

## Layout under `tools/` (locked)

```
tools/catalog/
  enrich.py                   # REPLACES Perplexity enrich — SearXNG pipeline (from scripts/enrich_with_searxng.py)
  worker/                     # Docker worker + entrypoint (enrich only)
    Dockerfile                # must NOT COPY post_channel / Bot deps
    docker-compose.yml        # optional local helper only
    requirements.txt          # enrich + browser + LLM (+ SearXNG), no pyrogram/Bot publish stack
    entrypoint.sh             # start SearXNG → run jobs → exit
    app.py                    # batch loop, I/O contract → calls tools.catalog enrich
    ...
  worker_orchestrator.py      # host: waves, docker run, persist results (no Telegram)
  publish/                    # HOST ONLY — Telegram publish; never in worker image
    channel.py
  post_channel.py             # thin shim → publish.channel
  browser/                    # direct-proxy path for worker (no mitm in this feature)
  ...
```

- No Dockerfile / worker package at repo root.
- Migrate `scripts/enrich_with_searxng.py` → `tools/catalog/` (replace `enrich.py`); update `run_pipeline` to use it.
- `post_channel.py` stays on host; pipeline order remains enrich-worker → (later) post on host.
- `.vercelignore` already lists `tools/` — sufficient for deploy exclusion.

## Docker image (sketch)

- Build context: `tools/catalog/worker/` (local only).
- Base: Debian/Ubuntu with Chromium deps + Python.
- Packages: SearXNG (or official image layers / supervised process), nodriver, enrich dependencies from `tools/catalog/`.
- Entrypoint: start SearXNG locally → run worker job loop → exit non-zero on hard failure.
- Fail closed: if proxy env missing, refuse to run (no accidental direct egress for job traffic).
- Image build and `docker run` only on local machines; CI may build optionally later, but **not** Vercel.

## Host integration

- Orchestrator: `tools/catalog/worker_orchestrator.py` (name flexible). Optional: `catalog_pipeline` / `run_pipeline` flag for enrich-via-docker.
- Enrich module under `tools/catalog/` is the single implementation used by worker and (optional) host fallback.
- Telegram: only after enrich results are on disk — invoke existing `post_channel` on the host. Worker image build context must exclude publish modules (explicit COPY allowlist preferred).
- Data paths stay `data/catalog/`; not code.

## Error handling

| Failure | Behavior |
|---------|----------|
| Container cannot reach net via proxy / leak check fails | Mark proxy `works=false`, fail that batch’s jobs or retry once on another proxy (orchestrator policy) |
| Single course LLM/search fail | `ok=false` for that job; other jobs in batch continue |
| SearXNG down inside worker | Whole container fails; orchestrator may retry batch with new proxy |
| Docker missing / image missing | Orchestrator errors clearly; no host fallback to direct (non-proxied) enrich unless explicitly opted in later |

## Testing (local)

- One-course smoke: single container, one proxy, assert `meta.exit_ip` and enriched fields.
- Wave smoke: 2 containers × 2 jobs, different proxies.
- Negative: missing `HTTP_PROXY` → worker exits non-zero.
- Confirm Vercel build still ignores worker/Docker/orchestrator paths.

## Relation to prior work

- Extends catalog AI enrich (`2026-07-29-catalog-pipeline-ai-enrich-design.md`) with an isolated network boundary.
- **Replaces** `tools/catalog/enrich.py` (Perplexity) with the SearXNG pipeline from `scripts/enrich_with_searxng.py`.
- Replaces the fragile host mitm+nodriver relay path for that enrich.
- `post_channel` / sync-db remain **host-only**, never containerized in this feature.

## Success criteria

1. Local wave can process multiple batches with concurrent containers and distinct proxies.
2. No mitm relay in the worker path.
3. Output course JSON matches `enrich_with_searxng` quality/routing rules (ready for a separate host publish step).
4. Vercel deploy artifact does not include worker runtime, Docker image build context secrets, or orchestrator execution.
5. Active LLM backend is selected only from settings/env; at least the existing backends (`nvidia`, `openrouter`, `bedrock`) are supported without hardcoding a single vendor in the worker entrypoint.
6. Feature code/Docker under `tools/`; canonical enrich lives in `tools/catalog/` replacing old `enrich.py`.
7. Worker image contains no Telegram publish code (`post_channel`, Bot API client, channel posting).

