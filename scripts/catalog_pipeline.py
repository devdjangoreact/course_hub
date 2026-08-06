"""Local catalog pipeline — edit params below, then run:

  python scripts/catalog_pipeline.py

Secrets: `.env` (TG_*, BOT_TOKEN, CATALOG_*, AI_*, DATABASE_URL).
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
# Normalize writes here; enrich/post/sync-db read only this folder.
CATEGORY_DIR = "flancki_need_enrich"
# The same selection is used by enrich, post, and sync-db.
POST_IDS: list[int] = []
# Initial end-to-end batch: 10 newest courses.
COURSE_LIMIT: int | None = 10
ENRICH_LIMIT: int | None = 10
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
        course_limit=COURSE_LIMIT,
        enrich_limit=ENRICH_LIMIT,
        post_ids=POST_IDS or None,
        enrich_newest_first=ENRICH_NEWEST_FIRST,
        force_repost=FORCE_REPOST,
    )


if __name__ == "__main__":
    main()
