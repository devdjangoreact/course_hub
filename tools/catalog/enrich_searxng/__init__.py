"""SearXNG + LLM catalog enrich (canonical implementation)."""

from .pipeline import enrich_all, enrich_batch, enrich_course

__all__ = ["enrich_all", "enrich_batch", "enrich_course"]
