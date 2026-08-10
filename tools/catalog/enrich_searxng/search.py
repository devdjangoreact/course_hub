"""SearXNG client (SEARXNG_URL / SEARXNG_URLS)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

import config
from .llm import requests_proxies

REQUEST_TIMEOUT = 10
MAX_CANDIDATES = 5

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080/search")
_SEARXNG_URLS_RAW = (os.environ.get("SEARXNG_URLS") or "").strip()
SEARXNG_URLS = (
    [u.strip() for u in _SEARXNG_URLS_RAW.split(",") if u.strip()]
    if _SEARXNG_URLS_RAW
    else [SEARXNG_URL]
)
SEARXNG_USE_SESSION_PROXY = config.env_bool("SEARXNG_USE_SESSION_PROXY", False)


def _search_searxng_one(base_url: str, query: str, num_results: int) -> list[dict]:
    """Query one SearXNG instance. Returns [{title, url, snippet}, ...]."""
    params = {"q": query, "format": "json"}
    kwargs: dict[str, Any] = {"params": params, "timeout": REQUEST_TIMEOUT}
    if SEARXNG_USE_SESSION_PROXY:
        proxies = requests_proxies()
        if proxies:
            kwargs["proxies"] = proxies
    resp = requests.get(base_url, **kwargs)
    resp.raise_for_status()
    results = resp.json().get("results", [])[:num_results]
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in results
        if r.get("url")
    ]


def search_searxng(query: str, num_results: int = MAX_CANDIDATES) -> list[dict]:
    """
    Query one or more SearXNG instances in parallel; merge/dedupe by URL.

    Engine→web proxy belongs in each instance settings.yml (outgoing.proxies).
    SEARXNG_USE_SESSION_PROXY only wraps client→SearXNG HTTP.
    """
    urls = SEARXNG_URLS
    if len(urls) == 1:
        return _search_searxng_one(urls[0], query, num_results)[:num_results]

    merged: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        futures = {
            pool.submit(_search_searxng_one, url, query, num_results): url
            for url in urls
        }
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                items = fut.result()
            except Exception as exc:
                print(f"  searxng fail {src}: {exc}")
                continue
            for item in items:
                key = item["url"]
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
    return merged[:num_results]
