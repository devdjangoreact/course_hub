#!/usr/bin/env bash
set -euo pipefail

: "${HTTP_PROXY:?HTTP_PROXY required}"
: "${HTTPS_PROXY:?HTTPS_PROXY required}"
: "${ALL_PROXY:?ALL_PROXY required}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1}"
export SEARXNG_SETTINGS_PATH="${SEARXNG_SETTINGS_PATH:-/etc/searxng/settings.yml}"

python /app/worker/render_searxng_settings.py

# SearXNG from image install (see Dockerfile)
export SEARXNG_SETTINGS_PATH
python -m searx.webapp &
SEARX_PID=$!

deadline=$((SECONDS + 60))
until curl -fsS "http://127.0.0.1:8080/" >/dev/null 2>&1; do
  if ! kill -0 "$SEARX_PID" 2>/dev/null; then
    echo "SearXNG exited before ready" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "SearXNG ready timeout" >&2
    exit 1
  fi
  sleep 1
done

exec python /app/worker/app.py "$@"
