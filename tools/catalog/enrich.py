"""AI-enrich course JSON via an LLM that searches the web itself (Perplexity)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "ai"))

import config
from course_json import load_course, save_course, select_course_json_files
from factory import get_enrich_ai_client

SYSTEM = """You are a research assistant with live internet access.
Search the public web yourself for the given online course by its title.
Find the official page where this course is sold or marketed (school storefront,
author landing, GetCourse, Skillbox, Udemy, etc.).
Use that sales page as the source of truth to enrich catalog fields.

Return ONLY a JSON object:
{
  "original_url": string|null,
  "links": string[],
  "authors": string[],
  "year": number|null,
  "tags": string[],
  "other": [],
  "price": string|null,
  "short_description": string,
  "promo_text": string
}

Rules:
- original_url must be a real URL you found online for selling/presenting this course.
- Do not invent URLs. If not found, original_url=null and explain in other.
- Ignore pirate dump links (cloud.mail.ru public dumps, random drive mirrors) for original_url.
- short_description: 1-3 sentences for a bot catalog.
- promo_text: concise Telegram HTML sales blurb based on the official page.
- price: numeric price from the sales page without currency, or null.
- Keep language close to the course title language when possible.
"""


def _merge_list(existing: list[Any], incoming: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for item in [*(existing or []), *(incoming or [])]:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if not isinstance(item, str) else item
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _is_enrichable(path: Path, data: dict[str, Any]) -> bool:
    adapter = str((data.get("source") or {}).get("adapter") or "")
    if adapter == "manual_fixture":
        return False
    category = data.get("category") or {}
    if str(category.get("slug") or "") == "test":
        return False
    if path.parent.name == "test":
        return False
    return True


def enrich_course(data: dict[str, Any], client: Any) -> dict[str, Any]:
    title = str(data.get("title") or "").strip()
    if not title:
        raise ValueError("course title is empty")

    user = (
        f"Course title: {title}\n"
        f"Existing dump/download link (not the sales page): {data.get('download_link')}\n"
        "Search the internet for this course and return the JSON enrichment."
    )
    result = client.chat_json(SYSTEM, user)

    original = result.get("original_url")
    data["original_url"] = str(original).strip() if isinstance(original, str) and original.strip() else None

    data["links"] = _merge_list(
        list(data.get("links") or []),
        [
            *(result.get("links") or []),
            *([data["original_url"]] if data.get("original_url") else []),
        ],
    )
    data["authors"] = _merge_list(list(data.get("authors") or []), list(result.get("authors") or []))
    if result.get("year") is not None:
        data["year"] = result.get("year")
    if result.get("price") is not None:
        data["price"] = str(result["price"])
    data["tags"] = _merge_list(list(data.get("tags") or []), list(result.get("tags") or []))
    data["other"] = _merge_list(list(data.get("other") or []), list(result.get("other") or []))

    short = result.get("short_description")
    if isinstance(short, str) and short.strip():
        data["short_description"] = short.strip()

    promo = result.get("promo_text")
    if isinstance(promo, str) and promo.strip():
        data["promo"] = {
            **(data.get("promo") or {}),
            "text": promo.strip(),
            "media": list((data.get("promo") or {}).get("media") or []),
        }
        data["full_description"] = promo.strip()

    return data


def enrich_all(
    limit: int | None = None,
    post_ids: set[int] | None = None,
    newest_first: bool = True,
    category_dirs: set[str] | None = None,
) -> int:
    client = get_enrich_ai_client()
    files = select_course_json_files(
        config.CATALOG_ROOT,
        limit=limit,
        post_ids=post_ids,
        newest_first=newest_first,
        category_dirs=category_dirs,
    )
    count = 0
    for path in files:
        data = load_course(path)
        if not _is_enrichable(path, data):
            continue
        print("enrich", path.name)
        enriched = enrich_course(data, client)
        save_course(path, enriched)
        count += 1
        print("enriched", path.name, "->", enriched.get("original_url"))
    return count


if __name__ == "__main__":
    enrich_all()
