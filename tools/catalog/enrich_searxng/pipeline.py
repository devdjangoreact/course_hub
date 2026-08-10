"""Enrich course / batch / routing (flancki vs flancki_need_enrich)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

import config
from browser import ProxyBrowserSession, refresh_proxies_from_webshare
from course_json import load_course, save_course, select_course_json_files

from .fetch import fetch_page
from .llm import (
    LLM_BACKEND,
    LLM_HTTP_PROXY,
    LLM_USE_SESSION_PROXY,
    NVIDIA_BASE_URL,
    NVIDIA_MODEL,
    llm_proxy_url,
    set_active_http_proxy,
)
from .quality import extract_metadata_with_quality, parse_course_date
from .search import SEARXNG_URLS, SEARXNG_USE_SESSION_PROXY, search_searxng
from .taxonomy import merge_taxonomy

CATEGORIES = config.CATALOG_ROOT / "categories"
NEED_ENRICH_DIR = CATEGORIES / "flancki_need_enrich"
FLANCKI_DIR = CATEGORIES / "flancki"
BATCH_SIZE = config.env_int("BATCH_SIZE", 2) or 2
BROWSER_HEADLESS = config.env_bool("BROWSER_HEADLESS", True)
WEBSHERE_PROXY_MODE = (os.environ.get("WEBSHERE_PROXY_MODE") or "direct").strip() or "direct"


def _parse_plan_ids() -> list[int] | None:
    raw = (os.environ.get("WEBSHERE_PROXY_PLAN_IDS") or "").strip()
    if not raw:
        return None
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def refresh_proxies_before_run() -> int:
    """Update proxies.json from Webshare using WEBSHERE_PROXY_API_KEY."""
    api_key = (config.WEBSHERE_PROXY_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("WEBSHERE_PROXY_API_KEY is missing in .env")
    count = refresh_proxies_from_webshare(
        api_key,
        config.PROXIES_PATH,
        mode=WEBSHERE_PROXY_MODE,
        plan_ids=_parse_plan_ids(),
    )
    print(f"proxies refreshed: {count} -> {config.PROXIES_PATH}")
    return count


def set_other(course: dict[str, Any], **fields: Any) -> None:
    """Merge into `other` whether it is a dict or a list of dicts."""
    other = course.get("other")
    if isinstance(other, dict):
        other.update(fields)
        return
    if isinstance(other, list):
        for item in other:
            if isinstance(item, dict):
                item.update(fields)
                return
        other.append(fields)
        return
    course["other"] = dict(fields)


def is_free(extracted: dict[str, Any]) -> bool:
    # Catalog dump often has placeholder price "0.00" — trust LLM extraction only.
    if extracted.get("is_free") is True:
        return True
    price = extracted.get("price")
    if price is None:
        return False
    text = str(price).strip().lower().replace(",", ".")
    if text in {"0", "0.0", "0.00", "free", "бесплатно", "бесплатный"}:
        return True
    try:
        return float(text) == 0.0
    except ValueError:
        return False


def has_useful_enrich(extracted: dict[str, Any]) -> bool:
    """Option A: any useful LLM field means move to flancki."""
    if extracted.get("price") is not None:
        return True
    if extracted.get("course_date"):
        return True
    for key in (
        "short_description",
        "promo_text",
        "full_description",
        "telegram_post",
    ):
        val = extracted.get(key)
        if isinstance(val, str) and val.strip():
            return True
    if extracted.get("authors"):
        return True
    if extracted.get("tags"):
        return True
    if extracted.get("category"):
        return True
    if extracted.get("subcategory"):
        return True
    return False


def apply_full_enrich(course: dict[str, Any], extracted: dict[str, Any], pages: list[dict]) -> None:
    course["enrich_sources"] = [p["url"] for p in pages if p.get("url")]

    raw_url = extracted.get("original_url")
    if isinstance(raw_url, str) and raw_url.strip():
        course["original_url"] = raw_url.strip()
        links = list(course.get("links") or [])
        if course["original_url"] not in links:
            links.append(course["original_url"])
            course["links"] = links
    else:
        course["original_url"] = None

    course["is_free"] = is_free(extracted)

    # Catalog sell price is fixed; never store source RUB prices.
    if course["is_free"]:
        course["price"] = "0"
    else:
        course["price"] = "5"

    if extracted.get("course_date"):
        set_other(course, course_date=extracted["course_date"])

    if extracted.get("year") is not None:
        course["year"] = extracted["year"]
    elif extracted.get("course_date"):
        parsed = parse_course_date(extracted["course_date"])
        if parsed:
            course["year"] = parsed.year

    if extracted.get("authors"):
        course["authors"] = list(extracted["authors"])
    if extracted.get("tags"):
        course["tags"] = list(extracted["tags"])

    cat = extracted.get("category")
    if isinstance(cat, str) and cat.strip():
        course["topic_category"] = cat.strip()
    sub = extracted.get("subcategory")
    if isinstance(sub, str) and sub.strip():
        course["subcategory"] = sub.strip()

    short = extracted.get("short_description")
    if isinstance(short, str) and short.strip():
        course["short_description"] = short.strip()

    promo = extracted.get("promo_text")
    if isinstance(promo, str) and promo.strip():
        course["promo"] = {
            **(course.get("promo") or {}),
            "text": promo.strip(),
            "media": list((course.get("promo") or {}).get("media") or []),
        }
        course["full_description"] = promo.strip()
    elif (
        isinstance(extracted.get("full_description"), str) and extracted["full_description"].strip()
    ):
        course["full_description"] = extracted["full_description"].strip()

    telegram_post = extracted.get("telegram_post")
    if isinstance(telegram_post, str) and telegram_post.strip():
        course["telegram_post"] = telegram_post.strip()

    merge_taxonomy(extracted)


async def enrich_course(
    course: dict[str, Any],
    session: ProxyBrowserSession,
) -> tuple[dict[str, Any], Path | None]:
    """Enrich one course. Returns (course, destination_dir|None)."""
    query = f"{course['title']} офіційна сторінка"
    print(f"  search: {query[:100]}")
    candidates = search_searxng(query)
    if not candidates:
        print("  skip: no searxng hits")
        set_other(course, skip_reason="no_searxng_hits")
        return course, None

    print(f"  fetch {len(candidates)} page(s) via nodriver/proxy")
    pages: list[dict] = []
    for c in candidates:
        page = await fetch_page(session, c["url"])
        if page:
            pages.append(page)
    if not pages:
        print("  skip: no pages fetched")
        set_other(course, skip_reason="no_pages_fetched")
        return course, None

    # If date missing on first pass sources, one extra SearXNG query (agent prompt rule).
    if not any(p.get("json_ld_date") for p in pages):
        date_query = f"{course['title']} дата старта"
        print(f"  search date: {date_query[:100]}")
        extra = search_searxng(date_query, num_results=3)
        for c in extra:
            page = await fetch_page(session, c["url"])
            if page:
                pages.append(page)

    print(f"  llm ({LLM_BACKEND})…")
    extracted, quality = extract_metadata_with_quality(
        course["title"],
        pages,
        download_link=str(course.get("download_link") or ""),
    )

    apply_full_enrich(course, extracted, pages)
    set_other(
        course,
        enrich_quality={
            "attempts": quality.get("attempts"),
            "checklist_ok": quality.get("checklist_ok"),
            "checklist_fails": quality.get("checklist_fails") or [],
            "judge": quality.get("judge"),
            "proxy_id": session.active_proxy_id,
            "exit_ip": session.exit_ip,
        },
    )

    checklist_ok = bool(quality.get("checklist_ok"))
    judge = quality.get("judge") or {}
    judge_ok = True if judge.get("skipped") else bool(judge.get("pass", False))
    if judge.get("skipped") is None and not judge:
        judge_ok = checklist_ok

    if not checklist_ok or not judge_ok:
        reason = extracted.get("skip_reason") or "enrich_quality_gate_failed"
        if quality.get("checklist_fails"):
            reason = "checklist: " + "; ".join(quality["checklist_fails"][:3])
        elif judge.get("reasons"):
            reason = "judge: " + "; ".join(str(r) for r in judge["reasons"][:3])
        set_other(course, skip_reason=reason)
        print(f"  stay in need_enrich: {reason}")
        return course, None

    if not has_useful_enrich(extracted):
        reason = extracted.get("skip_reason") or "no_useful_enrich_fields"
        set_other(course, skip_reason=reason)
        print(f"  stay in need_enrich: {reason}")
        return course, None

    return course, FLANCKI_DIR


async def _enrich_paths(files: list[Path]) -> int:
    if not files:
        print(f"no json to enrich")
        return 0

    FLANCKI_DIR.mkdir(parents=True, exist_ok=True)

    print(f"backend={LLM_BACKEND} model={NVIDIA_MODEL} base={NVIDIA_BASE_URL}")
    print(f"batch={len(files)}")
    print(
        f"browser proxies={config.PROXIES_PATH} relay=127.0.0.1:{config.RELAY_LOCAL_PORT} "
        f"headless={int(BROWSER_HEADLESS)}"
    )
    print(f"searxng n={len(SEARXNG_URLS)} urls={SEARXNG_URLS}")

    refresh_proxies_before_run()

    session = ProxyBrowserSession.from_defaults(
        proxies_path=config.PROXIES_PATH,
        relay_port=config.RELAY_LOCAL_PORT,
        headless=BROWSER_HEADLESS,
    )

    done = 0
    async with session:
        print(f"proxy OK id={session.active_proxy_id} exit_ip={session.exit_ip}")
        if LLM_USE_SESSION_PROXY or SEARXNG_USE_SESSION_PROXY:
            set_active_http_proxy(session.proxy_url)
        elif LLM_HTTP_PROXY:
            set_active_http_proxy(LLM_HTTP_PROXY)
        print(
            f"llm_proxy={'on' if llm_proxy_url() else 'off'} "
            f"searxng_client_proxy={int(SEARXNG_USE_SESSION_PROXY)}"
        )
        for path in files:
            print(f"enrich {path.name}")
            course = load_course(path)
            try:
                enriched, dest = await enrich_course(course, session)
            except Exception as exc:  # noqa: BLE001 — one bad course must not kill batch
                print(f"  failed {path.name}: {type(exc).__name__}: {exc}")
                set_other(course, skip_reason=f"enrich_crash: {type(exc).__name__}")
                save_course(path, course)
                print(f"done {path.name} (kept in need_enrich after crash)")
                continue
            save_course(path, enriched)
            if dest is None:
                print(
                    f"done {path.name} (kept in need_enrich) "
                    f"original_url={enriched.get('original_url')}"
                )
            else:
                target = dest / path.name
                shutil.move(str(path), str(target))
                print(
                    f"done {path.name} -> {dest.name}/ "
                    f"original_url={enriched.get('original_url')}"
                )
            done += 1
    return done


async def enrich_batch(limit: int = BATCH_SIZE) -> int:
    """Enrich first `limit` JSON files from need_enrich; move to flancki when ok."""
    files = sorted(NEED_ENRICH_DIR.glob("*.json"))[:limit]
    if not files:
        print(f"no json in {NEED_ENRICH_DIR}")
        return 0
    print(f"from {NEED_ENRICH_DIR}")
    return await _enrich_paths(files)


def enrich_all(
    limit: int | None = None,
    post_ids: set[int] | None = None,
    newest_first: bool = True,
    category_dirs: set[str] | None = None,
) -> int:
    """Sync entry used by run_pipeline (SearXNG path)."""
    dirs = category_dirs if category_dirs is not None else {"flancki_need_enrich"}
    files = select_course_json_files(
        config.CATALOG_ROOT,
        limit=limit,
        post_ids=post_ids,
        newest_first=newest_first,
        category_dirs=dirs,
    )
    return asyncio.run(_enrich_paths(files))
