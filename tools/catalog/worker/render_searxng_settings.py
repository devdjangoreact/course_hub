"""Render SearXNG settings.yml with container HTTP_PROXY (outgoing)."""

from __future__ import annotations

import os
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "searxng" / "settings.yml.template"
OUT = Path(os.environ.get("SEARXNG_SETTINGS_PATH") or "/etc/searxng/settings.yml")


def main() -> None:
    proxy = (os.environ.get("HTTP_PROXY") or "").strip()
    if not proxy:
        raise SystemExit("HTTP_PROXY required to render SearXNG settings")
    text = TEMPLATE.read_text(encoding="utf-8").replace("__HTTP_PROXY__", proxy)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"searxng settings -> {OUT}")


if __name__ == "__main__":
    main()
