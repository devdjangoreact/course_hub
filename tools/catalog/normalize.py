"""Normalize Flancki export posts into unified catalog course JSON files."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from course_json import save_course

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    text = value.lower().strip()
    text = _SLUG_RE.sub("-", text).strip("-")
    return text[:80] or "course"


def post_date_stamp(post: dict[str, Any]) -> str:
    raw = post.get("date")
    if isinstance(raw, str) and raw.strip():
        try:
            dt = datetime.fromisoformat(raw)
            return dt.date().isoformat()
        except ValueError:
            if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
                return raw[:10]
    return "unknown-date"


def course_slug(post: dict[str, Any], course_index: int) -> str:
    """Filename/slug: {post_date}_{post_id}_{course_nn} (1-based index in post)."""
    post_id = int(post.get("id") or 0)
    return f"{post_date_stamp(post)}_{post_id}_{course_index:02d}"


def without_download_links(text: str, *download_links: str) -> str:
    cleaned = text
    for download_link in download_links:
        if download_link:
            cleaned = cleaned.replace(download_link, "")
    return cleaned.rstrip()


def course_from_raw(
    *,
    title: str,
    download_link: str,
    post: dict[str, Any],
    course_index: int,
    category_title: str = "Flancki",
) -> dict[str, Any]:
    slug = course_slug(post, course_index)
    year_match = re.search(r"\b((?:19|20)\d{2})\b", title)
    year = int(year_match.group(1)) if year_match else None
    date_raw = post.get("date")
    if year is None and isinstance(date_raw, str) and len(date_raw) >= 4 and date_raw[:4].isdigit():
        year = int(date_raw[:4])
    short = title if len(title) <= 200 else title[:197] + "..."
    promo_text = f"<b>{title}</b>\n\n{short}"
    return {
        "slug": slug,
        "category": {"slug": slugify(category_title), "title": category_title},
        "title": title,
        "short_description": short,
        "price": "0.00",
        "promo": {"text": promo_text, "media": []},
        "full_description": promo_text,
        "download_link": download_link,
        "links": [download_link],
        "authors": [],
        "year": year,
        "tags": [],
        "other": [],
        "original_url": None,
        "telegram": {
            "channel_id": None,
            "discussion_group_id": None,
            "invite_link": None,
            "promo_message_ids": [],
            "full_message_ids": [],
        },
        "source": {
            "adapter": "telegram_flancki_pyrogram",
            "external_id": f"{post.get('chat_id')}:{post.get('id')}:{course_index:02d}",
            "raw_refs": [
                {
                    "post_id": post.get("id"),
                    "chat_id": post.get("chat_id"),
                    "course_index": course_index,
                }
            ],
        },
    }


def normalize_flancki_export(
    posts_path: Path | None = None,
    *,
    category_dir_name: str = "flancki_need_enrich",
) -> list[Path]:
    chat_id = int(config.TG_FLANCKI_CHAT_ID)
    if posts_path is None:
        posts_path = (
            config.REPO_ROOT / "data" / "telegram_exports" / str(chat_id) / "flancki_posts.json"
        )
    if not posts_path.is_file():
        raise SystemExit(f"Missing Flancki export: {posts_path}")
    posts = json.loads(posts_path.read_text(encoding="utf-8"))
    if isinstance(posts, dict):
        posts = posts.get("posts") or []
    written: list[Path] = []
    category_dir = config.CATALOG_ROOT / "categories" / category_dir_name
    category_dir.mkdir(parents=True, exist_ok=True)
    for post in posts:
        course_index = 0
        for item in post.get("courses") or []:
            title = str(item.get("title") or "").strip() or "Untitled"
            link = str(item.get("link") or "").strip()
            if not link:
                continue
            course_index += 1
            course = course_from_raw(
                title=title,
                download_link=link,
                post=post,
                course_index=course_index,
            )
            path = category_dir / f"{course['slug']}.json"
            existing_download = ""
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                existing_download = str(existing.get("download_link") or "")
                course = {**existing, **course}
                for key in (
                    "authors",
                    "tags",
                    "other",
                    "original_url",
                    "short_description",
                    "price",
                    "promo",
                    "full_description",
                    "telegram",
                ):
                    if key in existing:
                        course[key] = existing[key]
                if existing.get("year") is not None:
                    course["year"] = existing["year"]
                course["links"] = list(dict.fromkeys([*(existing.get("links") or []), link]))
            promo = course.get("promo") or {}
            promo_text = without_download_links(
                str(promo.get("text") or ""), existing_download, link
            )
            course["promo"] = {**promo, "text": promo_text}
            course["full_description"] = without_download_links(
                str(course.get("full_description") or ""), existing_download, link
            )
            course["short_description"] = without_download_links(
                str(course.get("short_description") or ""), existing_download, link
            )
            save_course(path, course)
            written.append(path)
    print(f"Normalized {len(written)} course files -> {category_dir}")
    return written


if __name__ == "__main__":
    normalize_flancki_export()
