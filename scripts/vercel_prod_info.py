#!/usr/bin/env python3
"""Fetch Vercel production deployment status + runtime logs via REST API (no CLI).

Reads VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID from .env.prod.
Does not print secret values.

Usage (from repo root):
  python scripts/vercel_prod_info.py
  python scripts/vercel_prod_info.py --since 15m --limit 100 --query Telegram
  python scripts/vercel_prod_info.py --level error --since 1h

Writes to logs/vercel-prod.log by default (not stdout).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from deploy_with_env_vercel import (  # noqa: E402
    REPO_ROOT,
    http_json,
    parse_env,
    vercel_headers,
    vercel_team_qs,
)

REQUIRED = ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID")
SINCE_RE = re.compile(r"^(\d+)([smhd])$", re.I)


def load_keys(env_file: Path) -> dict[str, str]:
    path = env_file if env_file.is_absolute() else REPO_ROOT / env_file
    if not path.is_file():
        raise RuntimeError(f"Missing env file: {path}")
    keys = parse_env(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if not keys.get(k, "").strip()]
    if missing:
        raise RuntimeError(f"Missing keys in {path.name}: {', '.join(missing)}")
    return keys


def parse_since_ms(text: str) -> int:
    now = int(time.time() * 1000)
    match = SINCE_RE.fullmatch(text.strip())
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        mul = {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}[unit]
        return now - amount * mul
    try:
        value = int(text)
    except ValueError:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    if value < 10_000_000_000:
        return value * 1000
    return value


def iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_production(token: str, org_id: str, project_id: str) -> dict[str, Any]:
    qs = urllib.parse.urlencode(
        {
            "projectId": project_id,
            "target": "production",
            "limit": 1,
            "state": "READY,ERROR,BUILDING",
            **({"teamId": org_id} if org_id else {}),
        }
    )
    status, payload = http_json(
        "GET",
        f"https://api.vercel.com/v6/deployments?{qs}",
        headers=vercel_headers(token),
    )
    if status != 200:
        raise RuntimeError(f"List deployments failed: HTTP {status} {payload}")
    items = payload.get("deployments") or []
    if not items:
        raise RuntimeError("No production deployments found.")
    return items[0]


def print_deployment(dep: dict[str, Any]) -> None:
    created = dep.get("created") or dep.get("createdAt") or 0
    print("DEPLOYMENT", flush=True)
    print(f"  uid:        {dep.get('uid') or dep.get('id')}", flush=True)
    print(f"  state:      {dep.get('state') or dep.get('readyState')}", flush=True)
    print(f"  url:        {dep.get('url')}", flush=True)
    print(f"  created:    {iso_ms(int(created)) if created else '?'}", flush=True)
    print(f"  inspector:  {dep.get('inspectorUrl') or '-'}", flush=True)
    err = dep.get("errorMessage")
    if err:
        print(f"  error:      {err}", flush=True)


def format_runtime(row: dict[str, Any]) -> str:
    ts = iso_ms(int(row.get("timestampInMs") or 0))
    level = str(row.get("level") or "?").upper()
    source = row.get("source") or "?"
    method = row.get("requestMethod") or ""
    path = row.get("requestPath") or ""
    code = row.get("responseStatusCode")
    req = f"{method} {path}".strip()
    if code is not None:
        req = f"{req} {code}".strip()
    msg = (row.get("message") or "").replace("\n", " ").strip()
    parts = [ts, level, source]
    if req:
        parts.append(req)
    if msg:
        parts.append(msg)
    return " | ".join(parts)


def matches_filters(
    *,
    ts_ms: int,
    since_ms: int,
    text: str,
    level: str,
    query: str,
    level_filter: str,
) -> bool:
    if ts_ms and ts_ms < since_ms:
        return False
    if level_filter and level.lower() != level_filter.lower():
        return False
    if query and query.lower() not in text.lower():
        return False
    return True


def fetch_runtime_logs(
    token: str,
    org_id: str,
    project_id: str,
    deployment_id: str,
    *,
    since_ms: int,
    limit: int,
    query: str,
    level_filter: str,
    timeout: float,
) -> list[str]:
    # ponytail: live NDJSON stream can block forever on Windows; cap with a daemon thread.
    box: list[list[str] | BaseException] = []

    def worker() -> None:
        try:
            box.append(
                _read_runtime_stream(
                    token,
                    org_id,
                    project_id,
                    deployment_id,
                    since_ms=since_ms,
                    limit=limit,
                    query=query,
                    level_filter=level_filter,
                    timeout=timeout,
                )
            )
        except BaseException as exc:
            box.append(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout + 2)
    if thread.is_alive():
        return []
    if not box:
        return []
    result = box[0]
    if isinstance(result, BaseException):
        raise RuntimeError(str(result)) from result
    return result


def _read_runtime_stream(
    token: str,
    org_id: str,
    project_id: str,
    deployment_id: str,
    *,
    since_ms: int,
    limit: int,
    query: str,
    level_filter: str,
    timeout: float,
) -> list[str]:
    url = (
        f"https://api.vercel.com/v1/projects/{urllib.parse.quote(project_id)}"
        f"/deployments/{urllib.parse.quote(deployment_id)}/runtime-logs"
        f"{vercel_team_qs(org_id)}"
    )
    request = urllib.request.Request(
        url,
        headers={**vercel_headers(token), "Accept": "application/stream+json"},
        method="GET",
    )
    lines: list[str] = []
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(request, timeout=min(timeout, 15)) as response:
            sock = getattr(getattr(response, "fp", None), "raw", None)
            sock = getattr(sock, "_sock", None)
            if sock is not None:
                sock.settimeout(5)
            while len(lines) < limit and time.monotonic() < deadline:
                try:
                    raw = response.readline()
                except (TimeoutError, OSError):
                    break
                if not raw:
                    break
                text = raw.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                blob = " ".join(
                    str(row.get(k) or "")
                    for k in ("message", "requestPath", "requestMethod", "level", "source")
                )
                if not matches_filters(
                    ts_ms=int(row.get("timestampInMs") or 0),
                    since_ms=since_ms,
                    text=blob,
                    level=str(row.get("level") or ""),
                    query=query,
                    level_filter=level_filter,
                ):
                    continue
                lines.append(format_runtime(row))
    except TimeoutError:
        return lines
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Runtime logs HTTP {exc.code}: {body}") from exc
    return lines


def format_event(item: dict[str, Any]) -> str:
    created = int(item.get("created") or item.get("date") or 0)
    kind = item.get("type") or "?"
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    text = str(payload.get("text") or item.get("text") or "").replace("\n", " ").strip()
    proxy = payload.get("proxy") if isinstance(payload.get("proxy"), dict) else {}
    path = proxy.get("path") or ""
    method = proxy.get("method") or ""
    code = proxy.get("statusCode") or payload.get("statusCode")
    req = f"{method} {path}".strip()
    if code is not None:
        req = f"{req} {code}".strip()
    parts = [iso_ms(created) if created else "?", kind.upper()]
    if req:
        parts.append(req)
    if text:
        parts.append(text)
    return " | ".join(parts)


def fetch_events(
    token: str,
    org_id: str,
    deployment_id: str,
    *,
    since_ms: int,
    limit: int,
    query: str,
    level_filter: str,
) -> list[str]:
    qs = {
        "direction": "backward",
        "limit": str(min(limit, 1000)),
        "since": str(since_ms),
        **({"teamId": org_id} if org_id else {}),
    }
    status, payload = http_json(
        "GET",
        f"https://api.vercel.com/v3/deployments/{urllib.parse.quote(deployment_id)}/events"
        f"?{urllib.parse.urlencode(qs)}",
        headers=vercel_headers(token),
    )
    if status != 200:
        raise RuntimeError(f"Deployment events HTTP {status} {payload}")
    items = payload if isinstance(payload, list) else payload.get("events") or []
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "")
        if level_filter == "error" and kind.lower() not in {"stderr", "fatal", "exit"}:
            continue
        blob = json.dumps(item, ensure_ascii=False)
        created = int(item.get("created") or item.get("date") or 0)
        if not matches_filters(
            ts_ms=created,
            since_ms=since_ms,
            text=blob,
            level=kind,
            query=query,
            level_filter="",
        ):
            continue
        lines.append(format_event(item))
        if len(lines) >= limit:
            break
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env.prod")
    parser.add_argument("--since", default="15m", help="Lookback: 15m, 1h, 24h, or ISO time")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--query", default="", help="Substring filter")
    parser.add_argument("--level", default="", help="Runtime log level, e.g. error")
    parser.add_argument("--timeout", type=float, default=12)
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Skip live runtime-log stream; events only",
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "logs" / "vercel-prod.log"),
        help="Write output to this file instead of stdout",
    )
    args = parser.parse_args()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    keys = load_keys(Path(args.env_file))
    token = keys["VERCEL_TOKEN"].strip()
    org_id = keys["VERCEL_ORG_ID"].strip()
    project_id = keys["VERCEL_PROJECT_ID"].strip()
    since_ms = parse_since_ms(args.since)
    limit = max(1, min(args.limit, 1000))

    with out_path.open("w", encoding="utf-8") as fh, redirect_stdout(fh):
        dep = latest_production(token, org_id, project_id)
        print_deployment(dep)
        dep_id = str(dep.get("uid") or dep.get("id") or "")
        print(
            f"\nWINDOW since={iso_ms(since_ms)} query={args.query or '-'} "
            f"level={args.level or '-'}",
            flush=True,
        )

        print("\nEVENTS", flush=True)
        try:
            events = fetch_events(
                token,
                org_id,
                dep_id,
                since_ms=since_ms,
                limit=limit,
                query=args.query,
                level_filter=args.level,
            )
        except RuntimeError as exc:
            print(f"  {exc}")
            events = []
        if events:
            print("\n".join(events), flush=True)
        else:
            print("  (none)", flush=True)

        if args.skip_runtime:
            print("\nRUNTIME\n  (skipped)", flush=True)
            return 0

        print("\nRUNTIME", flush=True)
        try:
            runtime = fetch_runtime_logs(
                token,
                org_id,
                project_id,
                dep_id,
                since_ms=since_ms,
                limit=limit,
                query=args.query,
                level_filter=args.level,
                timeout=args.timeout,
            )
        except RuntimeError as exc:
            print(f"  {exc}", flush=True)
            runtime = []
        if runtime:
            print("\n".join(runtime), flush=True)
        else:
            print("  (none)", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        err_path = REPO_ROOT / "logs" / "vercel-prod.log"
        err_path.parent.mkdir(parents=True, exist_ok=True)
        err_path.write_text(str(exc), encoding="utf-8")
        raise SystemExit(1) from exc
