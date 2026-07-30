"""Shared runner for local catalog steps (called from scripts/)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_CATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(_CATALOG))
sys.path.insert(0, str(_CATALOG / "parsers"))


def run_pipeline(
    *,
    parse: bool = False,
    normalize: bool = False,
    enrich: bool = False,
    post: bool = False,
    sync_db: bool = False,
    course_limit: int | None = None,
    enrich_limit: int | None = None,
    post_ids: list[int] | None = None,
    enrich_newest_first: bool = True,
    force_repost: bool = False,
) -> None:
    selected_post_ids = set(post_ids) if post_ids else None
    if parse:
        from flancki_pyrogram import run_parse

        run_parse()

    if normalize or parse:
        from normalize import normalize_flancki_export

        normalize_flancki_export()

    if enrich:
        from enrich import enrich_all

        enrich_all(
            limit=enrich_limit if enrich_limit is not None else course_limit,
            post_ids=selected_post_ids,
            newest_first=enrich_newest_first,
        )

    selected_paths = None
    if sync_db or post:
        import config
        from course_json import select_course_json_files

        selected_paths = select_course_json_files(
            config.CATALOG_ROOT,
            limit=course_limit,
            post_ids=selected_post_ids,
            newest_first=enrich_newest_first,
        )

    sync_main = None
    if sync_db and selected_paths is not None:
        from sync_db import main as sync_main

        asyncio.run(sync_main(paths=selected_paths))

    if post and selected_paths is not None:
        from post_channel import post_all

        post_all(paths=selected_paths, force=force_repost)

    if sync_main is not None and post and selected_paths is not None:
        asyncio.run(sync_main(paths=selected_paths))
