"""Load catalog tool settings from repo `.env` (no secrets in this file)."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = REPO_ROOT / "data" / "catalog"
SESSIONS_ROOT = REPO_ROOT / "sessions_parogram"
ENV_PATH = REPO_ROOT / ".env"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    pairs: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        pairs[key] = value
    return pairs


def load_dotenv(path: Path = ENV_PATH) -> None:
    for key, value in _parse_env_file(path).items():
        os.environ.setdefault(key, value)


load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int | None = None) -> int | None:
    raw = env(name)
    if not raw:
        return default
    return int(raw)


def env_bool(name: str, default: bool = False) -> bool:
    raw = env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


# Telegram user (Flancki parse)
TG_API_ID = env_int("TG_API_ID", 0) or 0
TG_API_HASH = env("TG_API_HASH")
TG_PHONE = env("TG_PHONE")
TG_SESSION_NAME = env("TG_SESSION_NAME", "catalog_user")
TG_FLANCKI_CHAT_ID = env_int("TG_FLANCKI_CHAT_ID", -1001343804259) or -1001343804259
TG_PARSE_YEARS = env_int("TG_PARSE_YEARS", 2) or 2
TG_DOWNLOAD_MEDIA = env_bool("TG_DOWNLOAD_MEDIA", True)

# Bot post + Vercel-shared
BOT_TOKEN = env("BOT_TOKEN")
CATALOG_CHANNEL_ID = env_int("CATALOG_CHANNEL_ID")
CATALOG_INVITE_LINK = env("CATALOG_INVITE_LINK")
CATALOG_DISCUSSION_GROUP_ID = env_int("CATALOG_DISCUSSION_GROUP_ID")

# AI
AI_PROVIDER = env("AI_PROVIDER", "nvidia").lower() or "nvidia"
# Enrich must use a web-capable LLM (Perplexity searches itself).
ENRICH_AI_PROVIDER = env("ENRICH_AI_PROVIDER", "perplexity").lower() or "perplexity"
NVIDIA_API_KEY = env("NVIDIA_API_KEY")
NVIDIA_BASE_URL = env("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = env("NVIDIA_MODEL", "z-ai/glm-5.2")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", "openai/gpt-4o-mini")
ENRICH_OPENROUTER_MODEL = env("ENRICH_OPENROUTER_MODEL", "perplexity/sonar-pro")
PERPLEXITY_API_KEY = env("PERPLEXITY_API_KEY")
PERPLEXITY_BASE_URL = env("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")
PERPLEXITY_MODEL = env("PERPLEXITY_MODEL", "sonar-pro")
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_REGION = env("AWS_REGION", "us-east-1")
AWS_BEDROCK_MODEL_ID = env("AWS_BEDROCK_MODEL_ID")

DATABASE_URL = env("DATABASE_URL")

# Proxied browser (nodriver + mitm relay)
PROXIES_PATH = Path(env("PROXIES_PATH") or str(CATALOG_ROOT / "proxies.json"))
RELAY_LOCAL_PORT = env_int("RELAY_LOCAL_PORT", 8899) or 8899
WEBSHERE_PROXY_API_KEY = env("WEBSHERE_PROXY_API_KEY")  # Webshare API token
WEBSHERE_PROXY_MODE = env("WEBSHERE_PROXY_MODE", "direct") or "direct"

# Docker enrich worker (local only)
WORKER_CONCURRENCY = env_int("WORKER_CONCURRENCY", 5) or 5
WORKER_BATCH_SIZE = env_int("WORKER_BATCH_SIZE", 5) or 5
WORKER_IMAGE = env("WORKER_IMAGE", "catalog-enrich-worker") or "catalog-enrich-worker"

# Back-compat aliases used by older scripts in this folder
API_ID = TG_API_ID
API_HASH = TG_API_HASH
SESSION_NAME = TG_SESSION_NAME
CHANNEL_ID = CATALOG_CHANNEL_ID
DISCUSSION_GROUP_ID = CATALOG_DISCUSSION_GROUP_ID
INVITE_LINK = CATALOG_INVITE_LINK or None
