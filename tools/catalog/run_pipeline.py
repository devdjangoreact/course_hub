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
    category_dir: str = "flancki_need_enrich",
    post_category_dir: str = "flancki",
    course_limit: int | None = None,
    enrich_limit: int | None = None,
    post_limit: int | None = None,
    post_ids: list[int] | None = None,
    enrich_newest_first: bool = True,
    force_repost: bool = False,
) -> None:
    """
    Enrich and Telegram publish are separate steps:
    - enrich / normalize use `category_dir` (default need_enrich)
    - post uses `post_category_dir` (default flancki)
    - sync_db alone uses `category_dir`; after post, sync uses `post_category_dir`
    """
    selected_post_ids = set(post_ids) if post_ids else None

    if parse:
        from flancki_pyrogram import run_parse

        run_parse()

    if normalize or parse:
        from normalize import normalize_flancki_export

        normalize_flancki_export(category_dir_name=category_dir)

    if enrich:
        from enrich import enrich_all

        enrich_all(
            limit=enrich_limit if enrich_limit is not None else course_limit,
            post_ids=selected_post_ids,
            newest_first=enrich_newest_first,
            category_dirs={category_dir},
        )

    if sync_db and not post:
        _sync_selected(
            category_dirs={category_dir},
            course_limit=course_limit,
            post_ids=selected_post_ids,
            newest_first=enrich_newest_first,
        )

    if post:
        import config
        from course_json import select_course_json_files
        from publish.channel import post_all

        post_paths = select_course_json_files(
            config.CATALOG_ROOT,
            limit=post_limit,
            post_ids=selected_post_ids,
            newest_first=enrich_newest_first,
            category_dirs={post_category_dir},
        )
        if post_paths:
            post_all(paths=post_paths, force=force_repost)

    if sync_db and post:
        _sync_selected(
            category_dirs={post_category_dir},
            course_limit=post_limit,
            post_ids=selected_post_ids,
            newest_first=enrich_newest_first,
        )


def _sync_selected(
    *,
    category_dirs: set[str],
    course_limit: int | None,
    post_ids: set[int] | None,
    newest_first: bool,
) -> None:
    import config
    from course_json import select_course_json_files
    from sync_db import main as sync_main

    paths = select_course_json_files(
        config.CATALOG_ROOT,
        limit=course_limit,
        post_ids=post_ids,
        newest_first=newest_first,
        category_dirs=category_dirs,
    )
    if paths:
        asyncio.run(sync_main(paths=paths))
