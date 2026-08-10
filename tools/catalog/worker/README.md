# Catalog enrich worker (stub)

Placeholder for the next stage: Docker image that runs SearXNG + browser + LLM
enrich with one upstream proxy per container (`HTTP_PROXY` kill-switch).

See `docs/superpowers/specs/2026-08-09-proxied-catalog-worker-docker-design.md`.

- Host orchestrator stub: `../worker_orchestrator.py`
- Enrich implementation (shared): `../enrich_searxng/`
- Telegram publish stays on host: `../publish/` — never copied into this image
