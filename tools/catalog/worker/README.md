# Catalog enrich worker (Docker)

Local-only image: SearXNG + nodriver + LLM enrich behind one upstream proxy
(`HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` kill-switch). No Telegram / Bot API.

Design: `docs/superpowers/specs/2026-08-09-proxied-catalog-worker-docker-design.md`

## Build

```bash
docker build -f tools/catalog/worker/Dockerfile -t catalog-enrich-worker tools/catalog
```

## Run (one batch)

```bash
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

Negative: omit `HTTP_PROXY` → non-zero exit.

## Host waves

```bash
# from repo root, with tools/catalog on PYTHONPATH via script habit:
python tools/catalog/worker_orchestrator.py
```

Or pipeline flag `DO_ENRICH_DOCKER=True` in `scripts/catalog_pipeline.py`.

## Smoke checklist

1. Missing proxy env → exit ≠ 0
2. One course + one proxy → `meta.exit_ip` set
3. Two containers × two jobs → distinct `meta.proxy`
4. Confirm `.vercelignore` still lists `tools`
