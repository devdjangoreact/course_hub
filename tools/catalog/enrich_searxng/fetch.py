"""Page fetch + HTML parse for catalog enrich.

Uses a browser session with `.fetch(url, wait_s=...)`. Today that is
ProxyBrowserSession (host); later a direct-proxy session can plug in without
changing this module's call shape.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, Protocol

from bs4 import BeautifulSoup

MAX_PAGE_CHARS = 4000
FETCH_WAIT_S = float(os.environ.get("ENRICH_FETCH_WAIT_S", "3"))


class FetchSession(Protocol):
    async def fetch(self, url: str, *, wait_s: float = ...) -> Any: ...


def parse_page_html(url: str, html: str) -> Optional[dict]:
    """Parse fetched HTML into enrich source fields (no network)."""
    if not html or not html.strip():
        return None

    soup = BeautifulSoup(html, "html.parser")

    def meta(name: str, attr: str = "name") -> str:
        tag = soup.find("meta", attrs={attr: name})
        return tag.get("content", "").strip() if tag else ""

    og_title = meta("og:title", "property")
    og_description = meta("og:description", "property")

    json_ld_year = None
    json_ld_date = None
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            date_str = item.get("datePublished") or item.get("dateCreated")
            if not date_str:
                continue
            raw = str(date_str)
            if not json_ld_date:
                m_full = re.search(r"(20\d{2}-\d{2}-\d{2})", raw)
                if m_full:
                    json_ld_date = m_full.group(1)
            match = re.search(r"(20\d{2})", raw)
            if match:
                json_ld_year = int(match.group(1))

    body_text = soup.get_text(separator=" ", strip=True)[:MAX_PAGE_CHARS]

    return {
        "url": url,
        "og_title": og_title,
        "og_description": og_description,
        "json_ld_year": json_ld_year,
        "json_ld_date": json_ld_date,
        "body_text": body_text,
    }


async def fetch_page(session: FetchSession, url: str) -> Optional[dict]:
    """Fetch URL via browser session, then parse HTML."""
    try:
        result = await session.fetch(url, wait_s=FETCH_WAIT_S)
    except Exception as exc:
        print(f"  fetch fail: {url[:80]} ({exc})")
        return None
    return parse_page_html(url, result.html)
