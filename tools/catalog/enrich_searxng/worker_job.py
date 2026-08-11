"""Worker-facing enrich: in-memory course in → course + destination out (no FS moves)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

Destination = Literal["flancki", "flancki_need_enrich"]

_FLANCKI_NAME = "flancki"


def destination_name(dest: Optional[Path]) -> Destination:
    if dest is not None and dest.name == _FLANCKI_NAME:
        return "flancki"
    return "flancki_need_enrich"


async def enrich_job(course: dict[str, Any], session: Any) -> dict[str, Any]:
    """Run one enrich; never raises — errors become ok=False."""
    from .pipeline import enrich_course, set_other

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
