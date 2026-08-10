"""Local catalog pipeline — edit params below, then run:

  python scripts/catalog_pipeline.py

Secrets: `.env` (TG_*, BOT_TOKEN, CATALOG_*, AI_*, DATABASE_URL).

Enrich and Telegram publish are separate:
  - enrich uses CATEGORY_DIR (need_enrich)
  - post uses POST_CATEGORY_DIR (flancki); prefer scripts/post_catalog_channel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "catalog"))

from run_pipeline import run_pipeline  # noqa: E402  # pyright: ignore[reportMissingImports]

# --- what to run ---
DO_PARSE = False
DO_NORMALIZE = False
DO_ENRICH = False
DO_POST = False
DO_SYNC_DB = True

# --- course selection ---
CATEGORY_DIR = "flancki_need_enrich"
POST_CATEGORY_DIR = "flancki"
POST_IDS: list[int] = []
COURSE_LIMIT: int | None = 10
ENRICH_LIMIT: int | None = 10
# None = all JSON under POST_CATEGORY_DIR
POST_LIMIT: int | None = None
ENRICH_NEWEST_FIRST = True
FORCE_REPOST = False
# ------------------


def main() -> None:
    run_pipeline(
        parse=DO_PARSE,
        normalize=DO_NORMALIZE,
        enrich=DO_ENRICH,
        post=DO_POST,
        sync_db=DO_SYNC_DB,
        category_dir=CATEGORY_DIR,
        post_category_dir=POST_CATEGORY_DIR,
        course_limit=COURSE_LIMIT,
        enrich_limit=ENRICH_LIMIT,
        post_limit=POST_LIMIT,
        post_ids=POST_IDS or None,
        enrich_newest_first=ENRICH_NEWEST_FIRST,
        force_repost=FORCE_REPOST,
    )


if __name__ == "__main__":
    main()
