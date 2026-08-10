"""Refresh data/catalog/proxies.json from Webshare Proxy List API."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import requests

WEBSHARE_LIST_URL = "https://proxy.webshare.io/api/v2/proxy/list/"
WEBSHARE_PLANS_URL = "https://proxy.webshare.io/api/v2/subscription/plan/"
DEFAULT_PAGE_SIZE = 100

# Username flags that force IP rotation — strip them (sticky instead for backbone).
_ROTATE_TOKEN = re.compile(r"(?i)(?:^|-)rotate(?:-|$)")


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Token {api_key}"}


def _strip_rotate(username: str) -> str:
    """Remove -rotate segments from Webshare username."""
    parts = [p for p in str(username).split("-") if p and p.lower() != "rotate"]
    return "-".join(parts) if parts else str(username)


def _with_sticky_session(username: str, session_key: str) -> str:
    """
    Backbone sticky session (not rotate).
    Format: {user}[-cc]-{numericSessionId}
    """
    base = _strip_rotate(username)
    if re.search(r"-\d+$", base):
        return base
    sticky = abs(hash(session_key)) % 10_000_000
    return f"{base}-{sticky}"


def _list_active_plans(api_key: str) -> list[dict[str, Any]]:
    page = 1
    out: list[dict[str, Any]] = []
    while True:
        resp = requests.get(
            WEBSHARE_PLANS_URL,
            params={"page": page, "page_size": 50},
            headers=_headers(api_key),
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("results") or []
        for item in batch:
            if isinstance(item, dict) and item.get("status") == "active":
                out.append(item)
        if not payload.get("next"):
            break
        page += 1
    return out


def _mode_for_plan(plan: dict[str, Any], default_mode: str) -> str:
    """Residential pools require backbone; shared/datacenter use direct."""
    subtype = str(plan.get("proxy_subtype") or "").lower()
    ptype = str(plan.get("proxy_type") or "").lower()
    if "residential" in subtype or "residential" in ptype:
        return "backbone"
    if "mobile" in subtype or "mobile" in ptype:
        return "backbone"
    return default_mode if default_mode in {"direct", "backbone"} else "direct"


def _fetch_plan_proxies(
    api_key: str,
    *,
    mode: str,
    plan_id: int | None,
    page_size: int,
) -> list[dict[str, Any]]:
    page = 1
    results: list[dict[str, Any]] = []
    while True:
        params: dict[str, Any] = {"mode": mode, "page": page, "page_size": page_size}
        if plan_id is not None:
            params["plan_id"] = plan_id
        resp = requests.get(
            WEBSHARE_LIST_URL,
            params=params,
            headers=_headers(api_key),
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("results") or []
        if not isinstance(batch, list):
            raise RuntimeError("Webshare API: unexpected results payload")
        results.extend(item for item in batch if isinstance(item, dict))
        if not payload.get("next"):
            break
        page += 1
    return results


def _proxy_line(item: dict[str, Any], *, mode: str) -> Optional[str]:
    user_raw = item.get("username")
    password = item.get("password")
    port = item.get("port")
    if user_raw is None or password is None or port is None:
        return None

    user = _strip_rotate(str(user_raw))
    host = item.get("proxy_address")
    if mode == "backbone" or not host:
        # Backbone gateway; sticky session — never -rotate
        host = "p.webshare.io"
        user = _with_sticky_session(user, session_key=str(item.get("id") or f"{host}:{port}:{user}"))
        # Common username/password ports for backbone
        if int(port) not in {80, 1080, 3128} and not (9999 <= int(port) <= 19999):
            port = 80
    return f"{host}:{port}:{user}:{password}"


def refresh_proxies_from_webshare(
    api_key: str,
    path: Path,
    *,
    mode: str = "direct",
    only_valid: bool = True,
    page_size: int = DEFAULT_PAGE_SIZE,
    plan_ids: list[int] | None = None,
) -> int:
    """
    Pull proxies from Webshare (all active plans by default) and rewrite proxies.json.

    - mode=direct: connect to each proxy_address:port (shared/datacenter).
    - residential/mobile plans forced to backbone + sticky session (no -rotate).
    Keeps next_index and works/last_* for unchanged proxy lines.
    """
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("WEBSHERE_PROXY_API_KEY is empty")

    plans = _list_active_plans(key)
    if plan_ids:
        wanted = set(plan_ids)
        plans = [p for p in plans if int(p.get("id") or -1) in wanted]
    if not plans:
        # Fallback: default plan only (old behaviour)
        plans = [{"id": None, "proxy_subtype": "", "proxy_type": ""}]

    remote: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
    for plan in plans:
        pid = plan.get("id")
        plan_id = int(pid) if pid is not None else None
        plan_mode = _mode_for_plan(plan, mode)
        try:
            batch = _fetch_plan_proxies(
                key, mode=plan_mode, plan_id=plan_id, page_size=page_size
            )
        except requests.HTTPError:
            # residential plans reject direct — retry backbone
            if plan_mode != "backbone":
                plan_mode = "backbone"
                batch = _fetch_plan_proxies(
                    key, mode=plan_mode, plan_id=plan_id, page_size=page_size
                )
            else:
                raise
        for item in batch:
            remote.append((item, plan_mode, plan))

    if only_valid:
        remote = [(p, m, pl) for p, m, pl in remote if p.get("valid") is not False]

    previous: dict[str, Any] = {}
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous = {}

    old_by_line: dict[str, dict[str, Any]] = {}
    for item in previous.get("proxies") or []:
        if isinstance(item, dict) and item.get("proxy"):
            old_by_line[str(item["proxy"])] = item

    proxies: list[dict[str, Any]] = []
    seen_lines: set[str] = set()
    for item, plan_mode, plan in remote:
        line = _proxy_line(item, mode=plan_mode)
        if not line or line in seen_lines:
            continue
        # Drop any leftover rotate endpoints
        user_part = line.split(":")[2] if line.count(":") >= 3 else ""
        if _ROTATE_TOKEN.search(user_part):
            continue
        seen_lines.add(line)
        prev = old_by_line.get(line, {})
        proxy_id = str(item.get("id") or prev.get("id") or f"webshare-{len(proxies) + 1}")
        expected = ""
        if plan_mode == "direct" and item.get("proxy_address"):
            expected = str(prev.get("expected_ip") or item.get("proxy_address") or "")
        proxies.append(
            {
                "id": proxy_id,
                "proxy": line,
                "expected_ip": expected,
                "works": prev.get("works"),
                "last_checked": prev.get("last_checked"),
                "last_error": prev.get("last_error"),
                "plan_id": plan.get("id"),
                "proxy_type": plan.get("proxy_type"),
                "proxy_subtype": plan.get("proxy_subtype"),
                "mode": plan_mode,
            }
        )

    if not proxies:
        raise RuntimeError("Webshare API returned no usable proxies")

    next_index = int(previous.get("next_index") or 0) % len(proxies)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"next_index": next_index, "proxies": proxies},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(proxies)
