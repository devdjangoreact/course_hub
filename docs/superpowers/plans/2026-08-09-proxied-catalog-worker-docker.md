# Proxied Catalog Worker (Docker) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run publication-prep enrich (SearXNG → browser fetch → pluggable LLM → quality gate) inside local Docker workers, one authenticated upstream proxy per container, with a host orchestrator that waves concurrent containers and persists JSON — never Telegram, never Vercel.

**Architecture:** Shared enrich logic stays in `tools/catalog/enrich_searxng/`. Worker image starts localhost SearXNG, fails closed without `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`, runs a batch I/O contract via `worker/app.py`, and talks to the net only through that proxy (Chrome via `--proxy-server=host:port` + CDP 407 auth — **no mitm**). Host `worker_orchestrator.py` slices courses × proxies, `docker run`s waves, writes results under `data/catalog/`. Publish stays host-only in `tools/catalog/publish/`.

**Tech Stack:** Python 3.12, Docker, SearXNG (in-container), nodriver/Chromium, existing `enrich_searxng` (openai/httpx/requests), `data/catalog/proxies.json`.

## Global Constraints

- Local-only: worker image, orchestrator, in-worker SearXNG, nodriver, proxy tooling **must not** ship to Vercel; keep everything under `tools/` (already in `.vercelignore`).
- Proxy model: container env `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` (+ auth URL). No mitmproxy / local CONNECT relay in the worker path.
- Proxy change = recreate container (same image, new env). No hot-swap.
- One proxy per container for the whole in-container batch (`BATCH_SIZE`, default 5).
- Host waves: up to `WORKER_CONCURRENCY` containers (default 5); each gets a distinct proxy from `proxies.json`.
- Canonical enrich = SearXNG pipeline under `tools/catalog/enrich_searxng/` (already re-exported by `enrich.py`). Do not revive Perplexity `enrich.py` behavior.
- Worker job v1 = enrich/prep only. **No** Telegram API, **no** `publish/`, **no** `post_channel`, **no** `BOT_TOKEN` in the image or `docker run` env.
- Secrets stay on host `.env`; orchestrator forwards only enrich/LLM/proxy keys.
- LLM is pluggable via `LLM_BACKEND` (`nvidia` | `openrouter` | `bedrock`); one backend per worker run; fail closed if a backend cannot honor proxy.
- `NO_PROXY=localhost,127.0.0.1` so in-container SearXNG is not tunnelled.
- Do not read or commit `.env` / real secrets; do not commit `proxies.json` credentials if they appear dirty.
- Prefer minimal diffs; no drive-by refactors of host mitm path (it may remain for host fallback until this path replaces it).
- Commit only when the user explicitly asks (skip commit steps in a session unless requested).
- Ask before creating files outside the paths listed in this plan.
- Code and docs in English.

## Already done (do not redo)

| Item | Location |
|------|----------|
| SearXNG enrich package | `tools/catalog/enrich_searxng/` |
| Public enrich re-export | `tools/catalog/enrich.py` → `enrich_all` / `enrich_batch` / `enrich_course` |
| Thin script wrapper | `scripts/enrich_with_searxng.py` |
| Host publish split | `tools/catalog/publish/channel.py`, `post_channel.py` shim |
| `run_pipeline` calls SearXNG enrich (host/mitm path) | `tools/catalog/run_pipeline.py` |
| Stubs only | `tools/catalog/worker/Dockerfile`, `worker/README.md`, `worker_orchestrator.py` |

## File structure

| File | Responsibility |
|------|----------------|
| `tools/catalog/browser/nodriver_browser.py` | Add **direct** proxy start (host:port + CDP auth); keep existing relay start for host path |
| `tools/catalog/browser/direct_session.py` | Single-proxy session for worker: open → leak check → `fetch()`; no mitm |
| `tools/catalog/browser/__init__.py` | Export `DirectProxySession` |
| `tools/catalog/browser/protocols.py` | Widen `Browser.start` to support direct proxy (optional kwargs) |
| `tools/catalog/enrich_searxng/worker_job.py` | Pure in-memory enrich one course → `(course, destination, error)` for worker I/O |
| `tools/catalog/worker/app.py` | Read batch JSON, require proxy env, run jobs, write result JSON |
| `tools/catalog/worker/entrypoint.sh` | Start SearXNG → wait ready → `python -m app` → exit |
| `tools/catalog/worker/searxng/` | Minimal SearXNG settings template (outgoing proxy filled at start) |
| `tools/catalog/worker/requirements.txt` | Enrich + browser + LLM only (no pyrogram) |
| `tools/catalog/worker/Dockerfile` | Real image; COPY allowlist — never `publish/` / `post_channel.py` |
| `tools/catalog/worker/README.md` | Build/run notes |
| `tools/catalog/worker_orchestrator.py` | Waves, `docker run`, persist courses, mark bad proxies |
| `tools/catalog/config.py` | `WORKER_CONCURRENCY`, worker batch defaults if missing |
| `.env.example` | Document `WORKER_*` / confirm `LLM_BACKEND` |
| `scripts/catalog_pipeline.py` | Optional `DO_ENRICH_DOCKER` flag |
| `tools/catalog/run_pipeline.py` | Optional `enrich_docker` → call orchestrator |
| `tests/unit/test_worker_io.py` | Proxy URL helpers, fail-closed, I/O contract, destination mapping |

---

### Task 1: Direct-proxy nodriver (no mitm)

**Files:**
- Modify: `tools/catalog/browser/protocols.py`
- Modify: `tools/catalog/browser/nodriver_browser.py`
- Create: `tools/catalog/browser/direct_session.py`
- Modify: `tools/catalog/browser/__init__.py`
- Test: `tests/unit/test_worker_io.py` (credentials → Chrome args only; no live Chrome)

**Interfaces:**
- Consumes: `ProxyCredentials` (`host`, `port`, `username`, `password`, `as_http_url()`, `as_line()`)
- Produces:
  - `NodriverBrowser.start(*, local_relay_port: int \| None = None, proxy: ProxyCredentials \| None = None) -> None` — exactly one of relay port or proxy required
  - `class DirectProxySession` with:
    - `async def open(self) -> DirectProxySession`
    - `async def close(self) -> None`
    - `async def __aenter__` / `__aexit__`
    - `async def fetch(self, url: str, *, wait_s: float = 3.0) -> FetchResult` (same shape `enrich_searxng.fetch` expects)
    - properties: `exit_ip: str`, `active_proxy_id: str`, `proxy_url: str`
  - `DirectProxySession.from_line(proxy_line: str, *, proxy_id: str = "worker", headless: bool = True) -> DirectProxySession`

- [ ] **Step 1: Write failing unit tests for proxy URL / Chrome arg helpers**

Create `tests/unit/test_worker_io.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

CATALOG = Path(__file__).resolve().parents[2] / "tools" / "catalog"
sys.path.insert(0, str(CATALOG))

from browser.models import ProxyCredentials  # noqa: E402
from browser.nodriver_browser import chrome_proxy_server_arg  # noqa: E402


def test_chrome_proxy_server_arg_is_host_port_only():
    creds = ProxyCredentials.from_line("1.2.3.4:80:user:p@ss:word")
    assert chrome_proxy_server_arg(creds) == "http://1.2.3.4:80"


def test_proxy_credentials_as_http_url_quotes():
    creds = ProxyCredentials.from_line("1.2.3.4:80:user:p@ss")
    assert creds.as_http_url().startswith("http://user:p%40ss@1.2.3.4:80")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_worker_io.py::test_chrome_proxy_server_arg_is_host_port_only -v`

Expected: FAIL — `chrome_proxy_server_arg` not defined (or import error).

- [ ] **Step 3: Implement `chrome_proxy_server_arg` + widen `NodriverBrowser.start`**

In `nodriver_browser.py` add:

```python
def chrome_proxy_server_arg(credentials: ProxyCredentials) -> str:
    """Chrome --proxy-server value (no userinfo; auth via CDP)."""
    return f"http://{credentials.host}:{credentials.port}"
```

Update `Browser` protocol in `protocols.py`:

```python
class Browser(Protocol):
    async def start(
        self,
        *,
        local_relay_port: int | None = None,
        proxy: ProxyCredentials | None = None,
    ) -> None: ...

    async def stop(self) -> None: ...

    async def get_html(self, url: str, wait_s: float = 3.0) -> str: ...
```

Change `NodriverBrowser.start` so:

- If `proxy` is set: launch with `--proxy-server={chrome_proxy_server_arg(proxy)}` (no `--ignore-certificate-errors` required for non-mitm). Register CDP auth handler for username/password (Fetch domain `authRequired` / enable handleAuthRequests). Do **not** start mitm.
- If `local_relay_port` is set: keep current behavior (`--proxy-server=127.0.0.1:{port}` + ignore certs).
- If neither or both: `raise ValueError("provide exactly one of local_relay_port or proxy")`.

Keep `create_browser` unchanged.

- [ ] **Step 4: Implement `DirectProxySession`**

Create `tools/catalog/browser/direct_session.py`:

```python
"""Single upstream proxy session for Docker worker (no mitm relay)."""

from __future__ import annotations

from typing import Optional

from .leak_check import IpLeakChecker
from .models import FetchResult, ProxyCredentials
from .nodriver_browser import create_browser


class DirectProxySession:
    def __init__(
        self,
        credentials: ProxyCredentials,
        *,
        proxy_id: str = "worker",
        headless: bool = True,
        expected_ip: str = "",
    ) -> None:
        self._credentials = credentials
        self._proxy_id = proxy_id
        self._expected_ip = expected_ip
        self._browser = create_browser(headless=headless)
        self._leak = IpLeakChecker()
        self._exit_ip = ""

    @classmethod
    def from_line(
        cls,
        proxy_line: str,
        *,
        proxy_id: str = "worker",
        headless: bool = True,
        expected_ip: str = "",
    ) -> DirectProxySession:
        return cls(
            ProxyCredentials.from_line(proxy_line),
            proxy_id=proxy_id,
            headless=headless,
            expected_ip=expected_ip,
        )

    @property
    def exit_ip(self) -> str:
        return self._exit_ip

    @property
    def active_proxy_id(self) -> str:
        return self._proxy_id

    @property
    def proxy_url(self) -> str:
        return self._credentials.as_http_url()

    async def open(self) -> DirectProxySession:
        await self._browser.start(proxy=self._credentials)
        self._exit_ip = await self._leak.verify(
            self._browser, expected_ip=self._expected_ip
        )
        return self

    async def close(self) -> None:
        await self._browser.stop()

    async def fetch(self, url: str, *, wait_s: float = 3.0) -> FetchResult:
        html = await self._browser.get_html(url, wait_s=wait_s)
        return FetchResult(
            html=html,
            proxy_id=self._proxy_id,
            exit_ip=self._exit_ip,
            url=url,
        )

    async def __aenter__(self) -> DirectProxySession:
        return await self.open()

    async def __aexit__(self, *args: object) -> None:
        await self.close()
```

Export from `browser/__init__.py`.

Update host `ProxyBrowserSession` call sites of `browser.start(local_relay_port=...)` to still pass the keyword (compatible).

- [ ] **Step 5: Run unit tests**

Run: `pytest tests/unit/test_worker_io.py -v`

Expected: PASS for the two credential/arg tests.

- [ ] **Step 6: Commit** (only if user asked)

```bash
git add tools/catalog/browser/nodriver_browser.py tools/catalog/browser/direct_session.py tools/catalog/browser/protocols.py tools/catalog/browser/__init__.py tests/unit/test_worker_io.py
git commit -m "feat(catalog): add direct-proxy nodriver session for worker"
```

---

### Task 2: In-memory worker enrich job (destination hint, no shutil)

**Files:**
- Create: `tools/catalog/enrich_searxng/worker_job.py`
- Modify: `tools/catalog/enrich_searxng/__init__.py` (optional export)
- Modify: `tests/unit/test_worker_io.py`

**Interfaces:**
- Consumes: `enrich_course(course, session)` from `pipeline.py` (returns `(course, Path | None)` where `FLANCKI_DIR` means success)
- Produces:
  - `destination_name(dest: Path | None) -> Literal["flancki", "flancki_need_enrich"]`
  - `async def enrich_job(course: dict, session: DirectProxySession) -> dict` with keys: `ok`, `course`, `destination`, `error`

Mapping (matches host behavior):
- `dest is FLANCKI_DIR` (or name `flancki`) → `"flancki"`
- else → `"flancki_need_enrich"` (stay / quality fail / skip)

- [ ] **Step 1: Add failing tests for destination mapping**

Append to `tests/unit/test_worker_io.py`:

```python
from pathlib import Path
from enrich_searxng.worker_job import destination_name  # noqa: E402


def test_destination_name_flancki():
    assert destination_name(Path("/x/categories/flancki")) == "flancki"


def test_destination_name_none_is_need_enrich():
    assert destination_name(None) == "flancki_need_enrich"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/unit/test_worker_io.py::test_destination_name_flancki -v`

Expected: FAIL — module missing.

- [ ] **Step 3: Implement `worker_job.py`**

```python
"""Worker-facing enrich: in-memory course in → course + destination out (no FS moves)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from .pipeline import FLANCKI_DIR, enrich_course, set_other

Destination = Literal["flancki", "flancki_need_enrich"]


def destination_name(dest: Optional[Path]) -> Destination:
    if dest is not None and dest.name == FLANCKI_DIR.name:
        return "flancki"
    return "flancki_need_enrich"


async def enrich_job(course: dict[str, Any], session: Any) -> dict[str, Any]:
    """Run one enrich; never raises — errors become ok=False."""
    try:
        enriched, dest = await enrich_course(course, session)
        return {
            "ok": True,
            "course": enriched,
            "destination": destination_name(dest),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 — per-job isolation
        set_other(course, skip_reason=f"enrich_crash: {type(exc).__name__}")
        return {
            "ok": False,
            "course": course,
            "destination": "flancki_need_enrich",
            "error": f"{type(exc).__name__}: {exc}",
        }
```

Note: `enrich_course` already accepts any session with `.fetch` / `.active_proxy_id` / `.exit_ip` — `DirectProxySession` matches. Do **not** call `refresh_proxies_before_run` inside the worker.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_worker_io.py -v`

Expected: PASS.

- [ ] **Step 5: Commit** (only if user asked)

```bash
git add tools/catalog/enrich_searxng/worker_job.py tests/unit/test_worker_io.py
git commit -m "feat(catalog): add in-memory enrich_job for Docker worker"
```

---

### Task 3: Worker I/O contract + fail-closed proxy env

**Files:**
- Create: `tools/catalog/worker/app.py`
- Create: `tools/catalog/worker/__init__.py` (empty)
- Modify: `tests/unit/test_worker_io.py`

**Interfaces:**
- Produces:
  - `def require_proxy_env(environ: Mapping[str, str]) -> str` — returns proxy URL; raises `SystemExit`/`RuntimeError` if any of `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` missing/empty
  - `def proxy_line_to_http_url(line: str) -> str` — `host:port:user:pass` → `http://user:pass@host:port`
  - `def build_result(*, ok, meta, results) -> dict`
  - `async def run_batch(payload: dict) -> dict` — I/O contract from design spec
  - CLI: `python app.py --in /work/in.json --out /work/out.json`

Input/output JSON shapes are exactly those in the design spec (`jobs[]`, `results[]`, `meta.exit_ip`, `meta.llm_backend`).

Secrets never appear in JSON; only optional `llm.backend` / `model` / `base_url` overrides.

- [ ] **Step 1: Write failing tests for fail-closed + URL helper**

```python
import os
import pytest
from worker.app import require_proxy_env, proxy_line_to_http_url  # adjust sys.path


def test_require_proxy_env_fails_when_missing(monkeypatch):
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)
    with pytest.raises(RuntimeError, match="HTTP_PROXY"):
        require_proxy_env(os.environ)


def test_require_proxy_env_ok(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://u:p@h:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://u:p@h:1")
    monkeypatch.setenv("ALL_PROXY", "http://u:p@h:1")
    assert require_proxy_env(os.environ) == "http://u:p@h:1"


def test_proxy_line_to_http_url():
    assert proxy_line_to_http_url("10.0.0.1:8080:alice:s3cret") == (
        "http://alice:s3cret@10.0.0.1:8080"
    )
```

For imports: tests add both `tools/catalog` and `tools/catalog/worker` to `sys.path`, or implement helpers in a small `tools/catalog/worker/proxy_env.py` imported as `from proxy_env import ...` when running inside the image. Prefer **`tools/catalog/worker/proxy_env.py`** pure helpers (no Docker) so unit tests stay simple:

- Create: `tools/catalog/worker/proxy_env.py` with `require_proxy_env`, `proxy_line_to_http_url`
- `app.py` imports them

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/unit/test_worker_io.py::test_require_proxy_env_fails_when_missing -v`

- [ ] **Step 3: Implement `proxy_env.py` + `app.py`**

`proxy_env.py`:

```python
from __future__ import annotations

from typing import Mapping
from urllib.parse import quote

from browser.models import ProxyCredentials


def proxy_line_to_http_url(line: str) -> str:
    return ProxyCredentials.from_line(line).as_http_url()


def require_proxy_env(environ: Mapping[str, str]) -> str:
    missing = [
        k
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
        if not (environ.get(k) or "").strip()
    ]
    if missing:
        raise RuntimeError(
            f"proxy kill-switch: missing env {', '.join(missing)} — refuse direct egress"
        )
    return (environ.get("HTTP_PROXY") or "").strip()
```

`app.py` sketch (full implementation in repo; keep logic short):

1. Parse `--in` / `--out`.
2. `require_proxy_env(os.environ)`.
3. Apply optional `payload["llm"]` overrides into `os.environ` (`LLM_BACKEND`, `NVIDIA_MODEL` / `OPENROUTER_MODEL`, base URL) — never write secrets from JSON.
4. `set_active_http_proxy(os.environ["HTTP_PROXY"])` so LLM uses kill-switch.
5. Force SearXNG client to localhost: `SEARXNG_URL=http://127.0.0.1:8080/search`, `SEARXNG_USE_SESSION_PROXY=0`.
6. Open `DirectProxySession.from_line(payload["proxy"])` (or derive line from env if payload omits — prefer payload `proxy` field as in spec).
7. For each job: `enrich_job(job["course"], session)`; attach `id`.
8. Write output JSON; process exit `0` if container-level ok (leak check passed); individual job failures stay in `results[].ok=false`.
9. If leak check / session open fails: write `{"ok": false, "meta": {...}, "results": [...all failed...]}` and exit `1`.

Wire `sys.path` inside the container so `import enrich_searxng` and `import browser` resolve (Dockerfile will `PYTHONPATH=/app/catalog`).

- [ ] **Step 4: Run unit tests**

Run: `pytest tests/unit/test_worker_io.py -v`

Expected: PASS.

- [ ] **Step 5: Commit** (only if user asked)

```bash
git add tools/catalog/worker/proxy_env.py tools/catalog/worker/app.py tools/catalog/worker/__init__.py tests/unit/test_worker_io.py
git commit -m "feat(catalog): worker batch I/O + fail-closed proxy env"
```

---

### Task 4: Dockerfile + entrypoint + SearXNG + worker requirements

**Files:**
- Replace: `tools/catalog/worker/Dockerfile`
- Create: `tools/catalog/worker/entrypoint.sh`
- Create: `tools/catalog/worker/requirements.txt`
- Create: `tools/catalog/worker/searxng/settings.yml.template` (or minimal settings)
- Modify: `tools/catalog/worker/README.md`

**Interfaces:**
- Image entrypoint: start SearXNG on `127.0.0.1:8080` with `outgoing.proxies` set from `HTTP_PROXY`, then run `python /app/worker/app.py ...`
- Build context: `tools/catalog/` (parent) **or** `tools/catalog/worker/` with explicit `COPY` of sibling packages — prefer build context `tools/catalog` so COPY can allowlist:

```dockerfile
# build: docker build -f tools/catalog/worker/Dockerfile -t catalog-enrich-worker tools/catalog
COPY enrich_searxng/ /app/catalog/enrich_searxng/
COPY browser/ /app/catalog/browser/
COPY course_json.py config.py enrich.py /app/catalog/
COPY worker/ /app/worker/
# NEVER: publish/, post_channel.py, parsers/, sync_db.py, create_channel.py
```

- [ ] **Step 1: Write `worker/requirements.txt`**

```
nodriver>=0.45
requests>=2.31
beautifulsoup4>=4.12
openai>=1.40
httpx>=0.27
# optional bedrock:
# boto3>=1.34
```

Do **not** include pyrogram, mitmproxy, sqlalchemy.

- [ ] **Step 2: Write `entrypoint.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

: "${HTTP_PROXY:?HTTP_PROXY required}"
: "${HTTPS_PROXY:?HTTPS_PROXY required}"
: "${ALL_PROXY:?ALL_PROXY required}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1}"

# Render SearXNG settings with outgoing proxy = $HTTP_PROXY, bind 127.0.0.1:8080
python /app/worker/render_searxng_settings.py

# Start SearXNG in background (exact binary depends on base image layout)
searxng-run &  # or: python -m searx.webapp &
# Wait until http://127.0.0.1:8080/search responds or timeout → exit 1

exec python /app/worker/app.py "$@"
```

Implement `render_searxng_settings.py` next to it: read template, substitute proxy URL, write to SearXNG config path. Keep it <40 lines.

Base image choice (lock in implementation): `python:3.12-slim-bookworm` + install Chromium deps for nodriver + install SearXNG via pip or git. If SearXNG install is too heavy, document using a two-process supervisor; do **not** pull Telegram deps.

- [ ] **Step 3: Replace stub Dockerfile** with a buildable file that:
  - Installs Chromium/deps + `requirements.txt`
  - COPYs allowlisted modules only
  - `ENV PYTHONPATH=/app/catalog`
  - `ENTRYPOINT ["/app/worker/entrypoint.sh"]`
  - `CMD ["--in", "/work/in.json", "--out", "/work/out.json"]`

- [ ] **Step 4: Update README** with build/run example:

```bash
docker build -f tools/catalog/worker/Dockerfile -t catalog-enrich-worker tools/catalog
docker run --rm \
  -e HTTP_PROXY=http://user:pass@host:port \
  -e HTTPS_PROXY=http://user:pass@host:port \
  -e ALL_PROXY=http://user:pass@host:port \
  -e NO_PROXY=localhost,127.0.0.1 \
  -e LLM_BACKEND=nvidia \
  -e NVIDIA_API_KEY \
  -e NVIDIA_MODEL \
  -e NVIDIA_BASE_URL \
  -v "$PWD/tmp/in.json:/work/in.json:ro" \
  -v "$PWD/tmp/out.json:/work/out.json" \
  catalog-enrich-worker
```

Negative check: omit `HTTP_PROXY` → non-zero exit.

- [ ] **Step 5: Build image locally to verify Dockerfile parses**

Run: `docker build -f tools/catalog/worker/Dockerfile -t catalog-enrich-worker tools/catalog`

Expected: image builds (or fix until it does). If SearXNG install blocks, stop and ask user before adding extra system packages.

- [ ] **Step 6: Commit** (only if user asked)

```bash
git add tools/catalog/worker/
git commit -m "feat(catalog): buildable enrich worker image (no Telegram)"
```

---

### Task 5: Host orchestrator waves

**Files:**
- Replace: `tools/catalog/worker_orchestrator.py`
- Modify: `tools/catalog/config.py` (add defaults)
- Modify: `.env.example` (document vars)
- Modify: `tests/unit/test_worker_io.py` (pure wave slicing helpers)

**Interfaces:**
- Produces:
  - `load_working_proxies(path: Path) -> list[ProxyEndpoint]` — `works is not False`
  - `plan_wave(courses: list[Path], proxies: list[ProxyEndpoint], *, concurrency: int, batch_size: int) -> list[WaveWorker]` where each `WaveWorker` has `proxy`, `paths: list[Path]`
  - `persist_results(out: dict, catalog_root: Path) -> None` — write course JSON; if `destination=="flancki"` move/copy into `categories/flancki/`, else `categories/flancki_need_enrich/`; merge `other.enrich_quality`
  - `mark_proxy_failed(proxies_path, proxy_line_or_id, error: str) -> None`
  - `run_waves(*, limit, concurrency, batch_size, image) -> int`
  - CLI: `python tools/catalog/worker_orchestrator.py` (with `sys.path` like other tools) or `python -m` after path insert

Defaults: `BATCH_SIZE=5`, `WORKER_CONCURRENCY=5`, image `catalog-enrich-worker`.

Env forwarded into container (**allowlist only**):
`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `LLM_BACKEND`, `NVIDIA_*`, `OPENROUTER_*`, `AWS_*` / Bedrock model, `BROWSER_HEADLESS`, `LLM_HTTP_TIMEOUT`, `LLM_RETRIES`  
**Never:** `BOT_TOKEN`, `TG_*`, `CATALOG_CHANNEL_*`, `DATABASE_URL`, Webshare keys (host refreshes proxies before waves if desired).

Algorithm (from spec):

```
courses ← pending JSON under flancki_need_enrich
proxies ← working pool
while courses remaining:
  n ← min(WORKER_CONCURRENCY, ceil(remaining/BATCH_SIZE), len(proxies))
  start n containers async (docker run --rm)
  wait all
  persist; mark bad proxies on container/network failure
```

Use `subprocess` to `docker` CLI (no Docker SDK dependency unless already present — prefer CLI).

- [ ] **Step 1: Tests for `plan_wave`**

```python
from pathlib import Path
from worker_orchestrator import plan_wave

class P:
    def __init__(self, id): self.id = id

def test_plan_wave_splits_batches():
    courses = [Path(f"{i}.json") for i in range(12)]
    proxies = [P("a"), P("b"), P("c")]
    waves = plan_wave(courses, proxies, concurrency=2, batch_size=5)
    # first wave only — function returns one wave's worker list
    assert len(waves) == 2
    assert len(waves[0].paths) == 5
    assert len(waves[1].paths) == 5
```

Implement `plan_wave` to return the next wave only (caller loops), **or** return all waves; pick one and test it consistently — prefer **next wave** helper `take_wave(courses, proxies, ...)` mutating remaining lists for simplicity.

- [ ] **Step 2: Implement orchestrator**

Replace stub `main()` with real runner. Temp dirs under `data/catalog/.worker_runs/<uuid>/` for `in.json`/`out.json` mounts (gitignored if needed — add `data/catalog/.worker_runs/` to `.gitignore` only if not already ignored by a parent rule; ask before editing `.gitignore` if uncertain).

On container exit ≠ 0 or `ok: false` with proxy/network error: `mark_proxy_failed`. Policy v1: fail that batch’s jobs to `flancki_need_enrich` with skip_reason; do **not** auto-fallback to host non-proxied enrich.

- [ ] **Step 3: Config + `.env.example`**

```python
WORKER_CONCURRENCY = env_int("WORKER_CONCURRENCY", 5) or 5
WORKER_BATCH_SIZE = env_int("WORKER_BATCH_SIZE", 5) or 5
WORKER_IMAGE = env("WORKER_IMAGE", "catalog-enrich-worker") or "catalog-enrich-worker"
```

Document in `.env.example` (no secrets).

- [ ] **Step 4: Run unit tests**

Run: `pytest tests/unit/test_worker_io.py -v`

Expected: PASS.

- [ ] **Step 5: Commit** (only if user asked)

```bash
git add tools/catalog/worker_orchestrator.py tools/catalog/config.py .env.example tests/unit/test_worker_io.py
git commit -m "feat(catalog): Docker wave orchestrator for proxied enrich"
```

---

### Task 6: Pipeline flag + smoke checklist

**Files:**
- Modify: `tools/catalog/run_pipeline.py`
- Modify: `scripts/catalog_pipeline.py`
- Modify: `tools/catalog/worker/README.md` (smoke commands)

**Interfaces:**
- `run_pipeline(..., enrich_docker: bool = False)` — when True, call orchestrator instead of host `enrich_all`
- `DO_ENRICH_DOCKER = False` in `catalog_pipeline.py`; if True, sets enrich via docker and should not also run host mitm enrich

- [ ] **Step 1: Wire flag**

In `run_pipeline.py`:

```python
def run_pipeline(..., enrich_docker: bool = False, ...):
    ...
    if enrich or enrich_docker:
        if enrich_docker:
            from worker_orchestrator import run_waves
            run_waves(
                limit=enrich_limit if enrich_limit is not None else course_limit,
                category_dir=category_dir,
            )
        else:
            from enrich import enrich_all
            enrich_all(...)
```

In `catalog_pipeline.py` add `DO_ENRICH_DOCKER = False` and pass it through.

- [ ] **Step 2: Manual smoke (local; ask user before running if costly)**

1. **Negative:** `docker run --rm catalog-enrich-worker` without proxy env → exit ≠ 0.
2. **One-course:** one proxy, one job JSON, assert `meta.exit_ip` present and `results[0].course` has enrich fields or skip_reason.
3. **Wave:** `WORKER_CONCURRENCY=2`, `WORKER_BATCH_SIZE=2`, two proxies — two containers, distinct `meta.proxy` / exit IPs.
4. Confirm `.vercelignore` still contains `tools` (already does).

- [ ] **Step 3: Commit** (only if user asked)

```bash
git add tools/catalog/run_pipeline.py scripts/catalog_pipeline.py tools/catalog/worker/README.md
git commit -m "feat(catalog): optional enrich-via-docker pipeline flag"
```

---

## Spec coverage checklist (self-review)

| Spec requirement | Task |
|------------------|------|
| Local-only Docker worker + host orchestrator | 4, 5 |
| One proxy per container; kill-switch env; fail closed | 3, 4 |
| No mitm in worker path | 1, 4 |
| Waves + concurrency + batch size | 5 |
| SearXNG inside worker + NO_PROXY | 4 |
| Direct proxy browser | 1 |
| Pluggable LLM via env | 3, 4, 5 allowlist |
| I/O contract JSON | 3 |
| Persist / routing flancki vs need_enrich on host | 2, 5 |
| No Telegram in image | 4 COPY allowlist |
| `run_pipeline` / catalog flag | 6 |
| Replace Perplexity enrich | already done — verify only |
| Vercel exclusion | `.vercelignore` + under `tools/` |
| Smoke / negative tests | 3 unit + 6 manual |

## Out of scope (do not implement in this plan)

- Hot-swap proxy inside a running container
- Generic browser ops RPC
- Containerized Telegram publish
- iptables/redsocks forced egress (env kill-switch only)
- Removing host mitm path (deprecate later)
