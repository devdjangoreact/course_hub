"""Catalog enrich public API — SearXNG + LLM (replaces Perplexity path)."""

from __future__ import annotations

from enrich_searxng.pipeline import enrich_all, enrich_batch, enrich_course

__all__ = ["enrich_all", "enrich_batch", "enrich_course"]
