"""Shim for Telegram publish — implementation in `publish.channel` (host-only).

Run from scripts: `python scripts/post_catalog_channel.py`
Docker worker must never copy `publish/` or this file.
"""

from __future__ import annotations

from publish.channel import (  # noqa: F401
    DEFAULT_POST_CATEGORY,
    _bot_call,
    _promo_and_full_texts,
    post_all,
    post_course,
)

if __name__ == "__main__":
    raise SystemExit(
        "Use: python scripts/post_catalog_channel.py"
    )
