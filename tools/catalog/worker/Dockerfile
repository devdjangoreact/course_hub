# Build from repo:
#   docker build -f tools/catalog/worker/Dockerfile -t catalog-enrich-worker tools/catalog
#
# Allowlist only — never COPY publish/, post_channel.py, Bot/Telegram stack.

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/catalog \
    SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml \
    NO_PROXY=localhost,127.0.0.1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      chromium \
      fonts-liberation \
      libnss3 \
      libatk-bridge2.0-0 \
      libgtk-3-0 \
      libx11-xcb1 \
      libxcomposite1 \
      libxdamage1 \
      libxrandr2 \
      libgbm1 \
      libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt /app/worker/requirements.txt
RUN pip install --no-cache-dir -r /app/worker/requirements.txt

# SearXNG (engines use outgoing.proxies from rendered settings.yml)
RUN git clone --depth 1 https://github.com/searxng/searxng.git /opt/searxng \
    && pip install --no-cache-dir -e /opt/searxng

COPY enrich_searxng/ /app/catalog/enrich_searxng/
COPY browser/ /app/catalog/browser/
COPY course_json.py config.py enrich.py /app/catalog/
COPY worker/ /app/worker/

RUN chmod +x /app/worker/entrypoint.sh \
    && mkdir -p /etc/searxng /work

WORKDIR /app/worker
ENTRYPOINT ["/app/worker/entrypoint.sh"]
CMD ["--in", "/work/in.json", "--out", "/work/out.json"]
