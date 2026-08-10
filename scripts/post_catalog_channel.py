"""Post enriched courses from data/catalog/categories/flancki to Telegram.

  python scripts/post_catalog_channel.py

Uses BOT_TOKEN + CATALOG_* from repo .env. Host-only (not Docker worker).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "catalog"))

from publish.channel import DEFAULT_POST_CATEGORY, post_all  # noqa: E402


# None = every JSON in flancki/
POST_LIMIT: int | None = None
POST_IDS: list[int] = []
FORCE_REPOST = False


def main() -> None:
    posted = post_all(
        limit=POST_LIMIT,
        post_ids=set(POST_IDS) if POST_IDS else None,
        category_dirs={DEFAULT_POST_CATEGORY},
        force=FORCE_REPOST,
    )
    print(f"done: {posted} new channel post(s) from categories/{DEFAULT_POST_CATEGORY}/")


if __name__ == "__main__":
    main()
