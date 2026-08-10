"""Thin entry → tools.catalog SearXNG enrich (same CLI as before)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Host CLI: LLM goes direct. Browser/SearXNG keep their own proxy settings.
os.environ["LLM_USE_SESSION_PROXY"] = "0"
os.environ["LLM_HTTP_PROXY"] = ""

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "catalog"))

from enrich_searxng.pipeline import enrich_batch  # noqa: E402

if __name__ == "__main__":
    asyncio.run(enrich_batch())
