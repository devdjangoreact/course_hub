#!/usr/bin/env python3
"""Sync .env.prod → ENV_PROD, optional Cloudflare+Vercel domain, redeploy, verify.

Does not print secret values. Requires: gh auth login.

Optional domain setup (Proxied + SSL Full strict) when CLOUDFLARE_API_TOKEN is set:
  CUSTOM_DOMAIN=codehelp.pp.ua
  BASE_DOMAIN=codehelp.pp.ua   # webhook hosts: https://{bot_username}.{BASE_DOMAIN}/api/telegram/webhook
  CLOUDFLARE_API_TOKEN=...
  CLOUDFLARE_ACCOUNT_ID=...   # optional
  CLOUDFLARE_ZONE_ID=...      # optional
  CUSTOM_DOMAIN_WWW=true      # optional, also configure www

Each run also adds Vercel + Cloudflare wildcard `*.CUSTOM_DOMAIN` so bot subdomains
hit Cloudflare → Vercel, and removes a stale catch-all A/AAAA (63.185.31.246).
Explicit Vercel hostnames are added for every active bot in the database (hyphenated;
Vercel rejects `_` in labels). If Vercel Hobby rejects `*.domain`, those DB hosts
are the fallback.

Every deploy path registers the Telegram webhook when it drifted and then verifies it via
getWebhookInfo; a webhook that is missing or points elsewhere fails the deploy.

Usage (from repo root):
  python scripts/deploy_with_env_vercel.py
  python scripts/deploy_with_env_vercel.py --skip-domain
  python scripts/deploy_with_env_vercel.py --no-redeploy
  python scripts/deploy_with_env_vercel.py --webhooks-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = (
    "DATABASE_URL",
    "BOT_TOKEN",
    "BACKEND_URL",
    "VERCEL_TOKEN",
    "VERCEL_ORG_ID",
    "VERCEL_PROJECT_ID",
)
FALSEY = {"false", "0", "no", "off"}
TRUTHY = {"true", "1", "yes", "on"}
# ponytail: mirrors Dispatcher.resolve_used_update_types(); widen if handlers gain a type.
REQUIRED_UPDATES = ["message", "callback_query"]
DEFAULT_WEBHOOK_PATH = "/api/telegram/webhook"
DEFAULT_VERCEL_URL = "https://course-hub-six-sigma.vercel.app"
VERCEL_CNAME = "cname.vercel-dns.com"
STALE_CATCHALL_IP = "63.185.31.246"


def parse_env(raw: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        pairs[key] = value
    return pairs


def resolve_executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32":
        for candidate in (f"{name}.cmd", f"{name}.exe", f"{name}.bat"):
            found = shutil.which(candidate)
            if found:
                return found
    return None


def run(
    cmd: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    resolved = list(cmd)
    exe = resolve_executable(resolved[0])
    if exe:
        resolved[0] = exe
    try:
        result = subprocess.run(
            resolved,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            cwd=REPO_ROOT,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {resolved[0]}") from exc
    if check and result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{err}")
    return result


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    timeout: float = 60,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req_headers = dict(headers)
    if body is not None:
        req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            payload: Any = json.loads(raw) if raw.strip() else {}
            return response.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload


def hostname_from_url(value: str) -> str:
    text = value.strip()
    if "://" not in text:
        text = "https://" + text
    return (urllib.parse.urlparse(text).hostname or "").lower()


def resolve_webhook_base_domain(keys: dict[str, str]) -> str:
    """Host that bot subdomains hang off: BASE_DOMAIN, else CUSTOM_DOMAIN, else BACKEND_URL."""
    for candidate in (
        keys.get("BASE_DOMAIN", ""),
        keys.get("CUSTOM_DOMAIN", ""),
        keys.get("BACKEND_URL", ""),
    ):
        host = hostname_from_url(candidate)
        if host:
            return host
    return ""


def resolve_custom_domain(keys: dict[str, str]) -> str:
    custom = keys.get("CUSTOM_DOMAIN", "").strip().lower()
    if custom:
        return hostname_from_url(custom)
    backend_host = hostname_from_url(keys.get("BACKEND_URL", ""))
    if backend_host and not backend_host.endswith(".vercel.app"):
        return backend_host
    return ""


def cloudflare_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def find_cloudflare_zone(
    token: str,
    domain: str,
    *,
    account_id: str = "",
    zone_id: str = "",
) -> dict[str, Any]:
    headers = cloudflare_headers(token)
    if zone_id:
        status, payload = http_json(
            "GET",
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}",
            headers=headers,
        )
        if status != 200 or not payload.get("success"):
            raise RuntimeError(f"Cloudflare zone get failed: HTTP {status} {payload}")
        return payload["result"]

    labels = domain.split(".")
    candidates = [".".join(labels[i:]) for i in range(0, len(labels) - 1)]
    for name in candidates:
        query = {"name": name, "per_page": "50"}
        if account_id:
            query["account.id"] = account_id
        url = "https://api.cloudflare.com/client/v4/zones?" + urllib.parse.urlencode(query)
        status, payload = http_json("GET", url, headers=headers)
        if status != 200 or not payload.get("success"):
            raise RuntimeError(f"Cloudflare zones list failed: HTTP {status} {payload}")
        results = payload.get("result") or []
        for zone in results:
            if str(zone.get("name", "")).lower() == name:
                return zone
    raise RuntimeError(
        f"Cloudflare zone not found for {domain}. "
        "Add the site in Cloudflare or set CLOUDFLARE_ZONE_ID."
    )


def vercel_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def vercel_team_qs(org_id: str) -> str:
    return "?" + urllib.parse.urlencode({"teamId": org_id}) if org_id else ""


def add_vercel_domain(token: str, org_id: str, project_id: str, domain: str) -> None:
    url = (
        f"https://api.vercel.com/v10/projects/{urllib.parse.quote(project_id)}/domains"
        f"{vercel_team_qs(org_id)}"
    )
    status, payload = http_json(
        "POST",
        url,
        headers=vercel_headers(token),
        body={"name": domain},
    )
    if status in (200, 201):
        print(f"OK  Vercel domain added: {domain}")
        return
    err = str(payload)
    if status == 409 or "already" in err.lower() or "exist" in err.lower():
        print(f"OK  Vercel domain already present: {domain}")
        return
    # Some responses use error.code
    code = ""
    if isinstance(payload, dict):
        error = payload.get("error") or {}
        if isinstance(error, dict):
            code = str(error.get("code", ""))
    if code in {"domain_already_in_use", "domain_already_exists"}:
        print(f"OK  Vercel domain already present: {domain}")
        return
    raise RuntimeError(f"Vercel add domain failed: HTTP {status} {payload}")


def _vercel_error_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)
    error = payload.get("error") or {}
    if isinstance(error, dict):
        return f"{error.get('code', '')} {error.get('message', '')}".strip()
    return str(payload)


def vercel_rejects_wildcard(status: int, payload: Any) -> bool:
    text = _vercel_error_text(payload).lower()
    return status in {400, 402, 403} and any(
        needle in text
        for needle in (
            "hobby",
            "wildcard",
            "upgrade",
            "pro plan",
            "not available on",
        )
    )


def list_cloudflare_dns_records(token: str, zone_id: str) -> list[dict[str, Any]]:
    headers = cloudflare_headers(token)
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            "https://api.cloudflare.com/client/v4/zones/"
            f"{zone_id}/dns_records?"
            + urllib.parse.urlencode({"per_page": "100", "page": str(page)})
        )
        status, payload = http_json("GET", url, headers=headers)
        if status != 200 or not payload.get("success"):
            raise RuntimeError(f"Cloudflare DNS list-all failed: HTTP {status} {payload}")
        batch = payload.get("result") or []
        records.extend(r for r in batch if isinstance(r, dict))
        info = payload.get("result_info") or {}
        total_pages = int(info.get("total_pages") or 1)
        if page >= total_pages or not batch:
            break
        page += 1
    return records


def delete_stale_catchall_records(token: str, zone_id: str, zone_name: str) -> None:
    """Remove wildcard A/AAAA/CNAME and any record still pointing at the old AWS IP."""
    headers = cloudflare_headers(token)
    zone_l = zone_name.lower()
    wildcard_names = {"*", f"*.{zone_l}"}
    for rec in list_cloudflare_dns_records(token, zone_id):
        rtype = str(rec.get("type", "")).upper()
        if rtype not in {"A", "AAAA", "CNAME"}:
            continue
        name = str(rec.get("name", "")).lower()
        content = str(rec.get("content", "")).strip()
        is_wildcard = name in wildcard_names
        is_stale_ip = content == STALE_CATCHALL_IP
        if not is_wildcard and not is_stale_ip:
            continue
        if rtype == "CNAME" and "vercel-dns" in content.lower():
            continue
        cid = rec.get("id")
        if not cid:
            continue
        del_status, del_payload = http_json(
            "DELETE",
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{cid}",
            headers=headers,
        )
        if del_status != 200 or not del_payload.get("success"):
            raise RuntimeError(
                f"Cloudflare DNS delete failed for {rtype} {name} ({content}): "
                f"HTTP {del_status} {del_payload}"
            )
        print(f"OK  Removed conflicting {rtype} record: {name} -> {content}")


def add_vercel_wildcard_or_hosts(
    token: str,
    org_id: str,
    project_id: str,
    domain: str,
    usernames: list[str],
) -> None:
    wildcard = f"*.{domain}"
    url = (
        f"https://api.vercel.com/v10/projects/{urllib.parse.quote(project_id)}/domains"
        f"{vercel_team_qs(org_id)}"
    )
    status, payload = http_json(
        "POST",
        url,
        headers=vercel_headers(token),
        body={"name": wildcard},
    )
    if status in (200, 201):
        print(f"OK  Vercel domain added: {wildcard}")
        return
    err = str(payload)
    code = ""
    if isinstance(payload, dict):
        error = payload.get("error") or {}
        if isinstance(error, dict):
            code = str(error.get("code", ""))
    if (
        status == 409
        or "already" in err.lower()
        or "exist" in err.lower()
        or code in {"domain_already_in_use", "domain_already_exists"}
    ):
        print(f"OK  Vercel domain already present: {wildcard}")
        return
    if vercel_rejects_wildcard(status, payload):
        print(
            f"WARNING: Vercel Hobby (or current plan) forbids {wildcard}: "
            f"{_vercel_error_text(payload)}. Falling back to explicit bot hostnames from DB."
        )
        add_explicit_bot_vercel_hosts(token, org_id, project_id, domain, usernames)
        return
    raise RuntimeError(f"Vercel add domain failed: HTTP {status} {payload}")


def vercel_label_for_username(username: str) -> str:
    return username.lstrip("@").strip().lower().replace("_", "-")


def _import_asyncpg() -> Any:
    try:
        import asyncpg

        return asyncpg
    except ImportError:
        extra = [REPO_ROOT / ".venv" / "Lib" / "site-packages"]
        lib = REPO_ROOT / ".venv" / "lib"
        if lib.is_dir():
            extra.extend(lib.glob("python*/site-packages"))
        for path in extra:
            if path.is_dir() and str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import asyncpg

        return asyncpg


def list_active_bots(database_url: str) -> list[tuple[str, str, str]]:
    """Return (username, token, webhook_secret) for active bots. Never prints secrets."""
    try:
        asyncpg = _import_asyncpg()
    except ImportError:
        print("WARNING: asyncpg missing; skip DB bot host list.")
        return []

    dsn = database_url.strip().replace("postgresql+asyncpg://", "postgresql://")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://") :]

    async def fetch() -> list[tuple[str, str, str]]:
        conn = await asyncpg.connect(dsn, timeout=8)
        try:
            rows = await conn.fetch(
                "select username, token, coalesce(webhook_secret, '') as webhook_secret "
                "from bots where is_active is true"
            )
        finally:
            await conn.close()
        out: list[tuple[str, str, str]] = []
        for row in rows:
            username = str(row["username"] or "").strip()
            if not username:
                continue
            out.append((username, str(row["token"] or ""), str(row["webhook_secret"] or "")))
        return out

    try:
        return asyncio.run(fetch())
    except Exception as exc:  # noqa: BLE001 - deploy continues with wildcard only
        print(f"WARNING: could not list bots from DB ({type(exc).__name__}); skip explicit hosts.")
        return []


def add_explicit_bot_vercel_hosts(
    token: str,
    org_id: str,
    project_id: str,
    domain: str,
    usernames: list[str],
) -> None:
    seen: set[str] = set()
    for username in usernames:
        host = f"{vercel_label_for_username(username)}.{domain}"
        if host in seen:
            continue
        seen.add(host)
        add_vercel_domain(token, org_id, project_id, host)


def telegram_api(token: str, method: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    """Call Bot API. Never prints the token; callers must not log the URL."""
    return http_json(
        "POST" if body is not None else "GET",
        f"https://api.telegram.org/bot{token}/{method}",
        headers={},
        body=body,
        timeout=20,
    )


def telegram_ok(status: int, payload: Any) -> bool:
    return status == 200 and isinstance(payload, dict) and payload.get("ok") is True


def telegram_result(status: int, payload: Any) -> dict[str, Any]:
    if not telegram_ok(status, payload):
        return {}
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def telegram_username(token: str) -> str:
    return str(telegram_result(*telegram_api(token, "getMe")).get("username") or "")


def allows_required(allowed: Any) -> bool:
    """Telegram omits allowed_updates when it delivers every type, which is wide enough."""
    if not isinstance(allowed, list):
        return True
    return set(REQUIRED_UPDATES) <= set(allowed)


def merged_allowed_updates(allowed: Any) -> list[str] | None:
    """None keeps Telegram's current setting; a list widens a restricted one in place."""
    if allows_required(allowed):
        return None
    return sorted(set(allowed) | set(REQUIRED_UPDATES))


def webhook_url_for(username: str, base_domain: str, webhook_path: str) -> str:
    path = webhook_path if webhook_path.startswith("/") else f"/{webhook_path}"
    return f"https://{vercel_label_for_username(username)}.{base_domain}{path}"


def fallback_bot_from_env(keys: dict[str, str]) -> list[tuple[str, str, str]]:
    """Single bot from BOT_TOKEN, for deploys that cannot reach the database (CI)."""
    token = keys.get("BOT_TOKEN", "").strip()
    if not token:
        return []
    username = keys.get("BOT_USERNAME", "").strip() or telegram_username(token)
    if not username:
        print("WARNING: BOT_TOKEN set but getMe failed; cannot resolve webhook host.")
        return []
    print(f"Using BOT_TOKEN bot @{username} (no bot list from DB).")
    return [(username, token, keys.get("TELEGRAM_WEBHOOK_SECRET", "").strip())]


def ensure_telegram_webhooks(
    bots: list[tuple[str, str, str]],
    *,
    base_domain: str,
    webhook_path: str,
) -> list[str]:
    """Register drifted webhooks, then verify via getWebhookInfo. Returns failure reasons."""
    failures: list[str] = []
    for username, token, secret in bots:
        token = token.strip()
        if not token:
            failures.append(f"@{username}: empty token")
            continue
        expected = webhook_url_for(username, base_domain, webhook_path)
        info = telegram_result(*telegram_api(token, "getWebhookInfo"))
        current = str(info.get("url") or "")
        widened = merged_allowed_updates(info.get("allowed_updates"))
        if current == expected and widened is None:
            print(f"OK  webhook already registered @{username} -> {expected}")
        else:
            body: dict[str, Any] = {"url": expected}
            if widened is not None:
                body["allowed_updates"] = widened
            if secret.strip():
                body["secret_token"] = secret.strip()
            status, payload = telegram_api(token, "setWebhook", body)
            if not telegram_ok(status, payload):
                failures.append(f"@{username}: setWebhook failed HTTP {status}")
                continue
            print(f"OK  setWebhook @{username}: {current or '(none)'} -> {expected}")
            if widened is not None:
                print(f"    allowed_updates widened to {widened}")

        info = telegram_result(*telegram_api(token, "getWebhookInfo"))
        final = str(info.get("url") or "")
        if final != expected:
            failures.append(f"@{username}: webhook is {final or '(none)'}, expected {expected}")
            continue
        if not allows_required(info.get("allowed_updates")):
            failures.append(
                f"@{username}: allowed_updates={info.get('allowed_updates')} "
                f"misses {REQUIRED_UPDATES}"
            )
            continue
        last_error = str(info.get("last_error_message") or "")
        if last_error:
            print(f"WARNING @{username}: Telegram last delivery error: {last_error}")
        print(f"OK  verified @{username} (pending={info.get('pending_update_count')})")
    return failures


def ensure_webhooks_or_fail(
    keys: dict[str, str],
    *,
    base_domain: str,
    bots: list[tuple[str, str, str]],
) -> None:
    """Single entry point used by every deploy path. Raises when a webhook is not live."""
    targets = bots or fallback_bot_from_env(keys)
    if not targets:
        raise RuntimeError("no bots to configure: DB list empty and BOT_TOKEN missing")
    failures = ensure_telegram_webhooks(
        targets,
        base_domain=base_domain,
        webhook_path=keys.get("TELEGRAM_WEBHOOK_PATH", "").strip() or DEFAULT_WEBHOOK_PATH,
    )
    if failures:
        raise RuntimeError("Telegram webhook verification failed: " + "; ".join(failures))
    print(f"OK  {len(targets)} Telegram webhook(s) configured and verified.")


def vercel_recommended_cname(token: str, org_id: str, domain: str) -> str:
    url = (
        f"https://api.vercel.com/v6/domains/{urllib.parse.quote(domain)}/config"
        f"{vercel_team_qs(org_id)}"
    )
    status, payload = http_json("GET", url, headers=vercel_headers(token))
    if status != 200:
        print(f"WARNING: Vercel domain config HTTP {status}; using {VERCEL_CNAME}")
        return VERCEL_CNAME
    cnames = payload.get("recommendedCNAME") or []
    if cnames and isinstance(cnames, list):
        first = cnames[0]
        if isinstance(first, dict) and first.get("value"):
            return str(first["value"])
        if isinstance(first, str) and first:
            return first
    return VERCEL_CNAME


def upsert_cloudflare_cname(
    token: str,
    zone_id: str,
    *,
    name: str,
    content: str,
    proxied: bool = True,
) -> None:
    headers = cloudflare_headers(token)
    list_url = (
        "https://api.cloudflare.com/client/v4/zones/"
        f"{zone_id}/dns_records?"
        + urllib.parse.urlencode({"name": name, "per_page": "100"})
    )
    status, payload = http_json("GET", list_url, headers=headers)
    if status != 200 or not payload.get("success"):
        raise RuntimeError(f"Cloudflare DNS list failed: HTTP {status} {payload}")

    records = payload.get("result") or []
    body = {
        "type": "CNAME",
        "name": name,
        "content": content.rstrip("."),
        "ttl": 1,
        "proxied": proxied,
    }

    cname_records = [r for r in records if str(r.get("type", "")).upper() == "CNAME"]
    conflicts = [
        r
        for r in records
        if str(r.get("type", "")).upper() in {"A", "AAAA", "CNAME"}
        and str(r.get("id", ""))
        not in {str(c.get("id", "")) for c in cname_records[:1]}
    ]

    # Apex often has A/AAAA placeholders; replace them with proxied CNAME.
    for conflict in conflicts:
        cid = conflict["id"]
        ctype = conflict.get("type")
        ccontent = conflict.get("content")
        del_status, del_payload = http_json(
            "DELETE",
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{cid}",
            headers=headers,
        )
        if del_status != 200 or not del_payload.get("success"):
            raise RuntimeError(
                f"Cloudflare DNS delete failed for {ctype} {name} ({ccontent}): "
                f"HTTP {del_status} {del_payload}"
            )
        print(f"OK  Removed conflicting {ctype} record: {name} -> {ccontent}")

    if cname_records:
        record_id = cname_records[0]["id"]
        status, payload = http_json(
            "PUT",
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}",
            headers=headers,
            body=body,
        )
        if status != 200 or not payload.get("success"):
            raise RuntimeError(f"Cloudflare DNS update failed: HTTP {status} {payload}")
        print(f"OK  Cloudflare CNAME updated: {name} -> {content} (proxied={proxied})")
        return

    status, payload = http_json(
        "POST",
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
        headers=headers,
        body=body,
    )
    if status not in (200, 201) or not payload.get("success"):
        raise RuntimeError(f"Cloudflare DNS create failed: HTTP {status} {payload}")
    print(f"OK  Cloudflare CNAME created: {name} -> {content} (proxied={proxied})")


def set_cloudflare_ssl_strict(token: str, zone_id: str) -> None:
    headers = cloudflare_headers(token)
    status, payload = http_json(
        "PATCH",
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/settings/ssl",
        headers=headers,
        body={"value": "strict"},
    )
    if status != 200 or not payload.get("success"):
        print(f"WARNING: could not set SSL Full (strict): HTTP {status} {payload}")
        return
    print("OK  Cloudflare SSL mode = full (strict)")


def set_cloudflare_https_always(token: str, zone_id: str) -> None:
    headers = cloudflare_headers(token)
    status, payload = http_json(
        "PATCH",
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/settings/always_use_https",
        headers=headers,
        body={"value": "on"},
    )
    if status != 200 or not payload.get("success"):
        print(f"WARNING: could not enable Always Use HTTPS: HTTP {status}")
        return
    print("OK  Cloudflare Always Use HTTPS = on")


def setup_custom_domain(keys: dict[str, str], *, include_www: bool) -> str:
    token_cf = keys.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token_cf:
        print("Skip domain setup: CLOUDFLARE_API_TOKEN not set.")
        return ""

    domain = resolve_custom_domain(keys)
    if not domain:
        print("Skip domain setup: set CUSTOM_DOMAIN or non-vercel BACKEND_URL.")
        return ""

    print(f"Setting up custom domain (proxied): {domain}")
    base_domain = keys.get("BASE_DOMAIN", "").strip()
    if not base_domain:
        print(
            f"WARNING: BASE_DOMAIN is empty while CUSTOM_DOMAIN={domain}; "
            "runtime setWebhook falls back to BACKEND_URL host. "
            f"Set BASE_DOMAIN={domain} in .env.prod"
        )
    elif hostname_from_url(base_domain) != domain and base_domain.lower() != domain:
        print(f"WARNING: BASE_DOMAIN host differs from CUSTOM_DOMAIN={domain}")

    zone = find_cloudflare_zone(
        token_cf,
        domain,
        account_id=keys.get("CLOUDFLARE_ACCOUNT_ID", "").strip(),
        zone_id=keys.get("CLOUDFLARE_ZONE_ID", "").strip(),
    )
    zone_id = str(zone["id"])
    zone_name = str(zone["name"])
    print(f"OK  Cloudflare zone: {zone_name} ({zone_id})")

    vercel_token = keys["VERCEL_TOKEN"].strip()
    org_id = keys["VERCEL_ORG_ID"].strip()
    project_id = keys["VERCEL_PROJECT_ID"].strip()

    add_vercel_domain(vercel_token, org_id, project_id, domain)
    bots = list_active_bots(keys["DATABASE_URL"])
    usernames = [username for username, _, _ in bots]
    print(f"OK  {len(usernames)} active bot(s) from DB")
    add_vercel_wildcard_or_hosts(vercel_token, org_id, project_id, domain, usernames)
    add_explicit_bot_vercel_hosts(vercel_token, org_id, project_id, domain, usernames)
    cname_target = vercel_recommended_cname(vercel_token, org_id, domain)

    delete_stale_catchall_records(token_cf, zone_id, zone_name)
    upsert_cloudflare_cname(
        token_cf,
        zone_id,
        name=domain,
        content=cname_target,
        proxied=True,
    )
    upsert_cloudflare_cname(
        token_cf,
        zone_id,
        name=f"*.{domain}",
        content=cname_target,
        proxied=True,
    )

    if include_www:
        www = f"www.{domain}"
        add_vercel_domain(vercel_token, org_id, project_id, www)
        www_target = vercel_recommended_cname(vercel_token, org_id, www)
        upsert_cloudflare_cname(
            token_cf,
            zone_id,
            name=www,
            content=www_target,
            proxied=True,
        )

    set_cloudflare_ssl_strict(token_cf, zone_id)
    set_cloudflare_https_always(token_cf, zone_id)

    expected_backend = f"https://{domain}"
    current_backend = keys.get("BACKEND_URL", "").rstrip("/")
    if current_backend != expected_backend:
        print(
            f"WARNING: BACKEND_URL is {current_backend or '(empty)'}; "
            f"for Telegram webhook use {expected_backend} in .env.prod"
        )
    return expected_backend


def sync_github_production_url(repo: str, backend_url: str) -> None:
    """Keep CI from overwriting BACKEND_URL with an old Vercel alias."""
    print(f"Updating GitHub variable VERCEL_PRODUCTION_URL={backend_url}")
    result = run(
        [
            "gh",
            "variable",
            "set",
            "VERCEL_PRODUCTION_URL",
            "--repo",
            repo,
            "--body",
            backend_url,
        ],
        check=False,
    )
    if result.returncode != 0:
        print(
            "WARNING: could not set VERCEL_PRODUCTION_URL. "
            "CI may overwrite BACKEND_URL on deploy."
        )
        return
    print("OK  VERCEL_PRODUCTION_URL updated.")


def probe_health(base_url: str, *, timeout: float = 60) -> tuple[int, float, str]:
    url = base_url.rstrip("/") + "/health"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, time.perf_counter() - started, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, time.perf_counter() - started, body
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, time.perf_counter() - started, f"connection_error: {exc}"


def probe_health_retries(
    base_url: str, *, attempts: int = 3, timeout: float = 45
) -> tuple[int, float, str]:
    last = (0, 0.0, "not_attempted")
    for i in range(1, attempts + 1):
        code, elapsed, body = probe_health(base_url, timeout=timeout)
        last = (code, elapsed, body)
        if code == 200:
            return last
        print(f"  attempt {i}/{attempts}: HTTP {code}  {elapsed:.2f}s  {body[:120]}")
        if i < attempts:
            time.sleep(5 * i)
    return last


def resolve_probe_urls(repo: str, backend_url: str, custom_https: str = "") -> list[str]:
    urls: list[str] = []
    for candidate in (custom_https, backend_url):
        value = candidate.rstrip("/")
        if value.startswith("http") and value not in urls:
            urls.append(value)
    result = run(
        [
            "gh",
            "variable",
            "get",
            "VERCEL_PRODUCTION_URL",
            "--repo",
            repo,
        ],
        check=False,
    )
    var_url = (result.stdout or "").strip().rstrip("/")
    if var_url.startswith("http") and var_url not in urls:
        urls.append(var_url)
    if DEFAULT_VERCEL_URL not in urls:
        urls.append(DEFAULT_VERCEL_URL)
    return urls


def wait_for_run(repo: str, run_id: str) -> str:
    print(f"Waiting for CI run {run_id}...")
    result = run(
        ["gh", "run", "watch", run_id, "--repo", repo, "--exit-status"],
        check=False,
        timeout=1800,
    )
    conclusion = run(
        [
            "gh",
            "run",
            "view",
            run_id,
            "--repo",
            repo,
            "--json",
            "conclusion,status,url",
            "--jq",
            '.conclusion + "|" + .status + "|" + .url',
        ]
    ).stdout.strip()
    parts = conclusion.split("|", 2)
    conc = parts[0] if parts else ""
    status = parts[1] if len(parts) > 1 else ""
    url = parts[2] if len(parts) > 2 else ""
    print(f"CI status={status} conclusion={conc} url={url}")
    if result.returncode != 0 or conc != "success":
        raise RuntimeError(f"CI did not succeed: {conclusion}")
    return url


def check_telegram_logs() -> bool:
    npx = resolve_executable("npx")
    if npx is None:
        print("WARNING: npx not found; skip Vercel log check.")
        return False
    try:
        result = run(
            [
                npx,
                "--yes",
                "vercel",
                "logs",
                "--environment",
                "production",
                "--since",
                "15m",
                "--expand",
                "--limit",
                "30",
                "--no-branch",
                "--query",
                "Telegram",
            ],
            check=False,
            timeout=120,
        )
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        print(f"WARNING: Vercel log check skipped ({exc}).")
        return False
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    disabled = "Telegram webhook mode (auto-set disabled)" in text
    still_sets = "Telegram webhook set to" in text
    if disabled and not still_sets:
        print("OK  Logs: auto-set disabled.")
        return True
    if still_sets:
        print("FAIL Logs still show setWebhook. ENV_PROD may still have auto-set=true.")
        return False
    if disabled:
        print("OK  Logs: auto-set disabled (also saw older setWebhook lines).")
        return True
    print("WARNING: No Telegram startup line in recent logs yet. Hit /health once more later.")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env.prod")
    parser.add_argument("--repo", default="devdjangoreact/course_hub")
    parser.add_argument("--workflow", default="deploy-vercel.yml")
    parser.add_argument("--no-redeploy", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-domain", action="store_true")
    parser.add_argument(
        "--webhooks-only",
        action="store_true",
        help="Only register and verify Telegram webhooks (no gh, no Vercel, no redeploy).",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = REPO_ROOT / env_path
    if not env_path.is_file():
        print(f"Env file not found: {env_path}", file=sys.stderr)
        return 1

    raw = env_path.read_text(encoding="utf-8")
    if not raw.strip():
        print(f"Env file is empty: {env_path}", file=sys.stderr)
        return 1

    keys = parse_env(raw)

    if args.webhooks_only:
        base_domain = resolve_webhook_base_domain(keys)
        if not base_domain:
            print(
                "Set BASE_DOMAIN, CUSTOM_DOMAIN or BACKEND_URL to register webhooks.",
                file=sys.stderr,
            )
            return 1
        dsn = keys.get("DATABASE_URL", "").strip()
        ensure_webhooks_or_fail(
            keys,
            base_domain=base_domain,
            bots=list_active_bots(dsn) if dsn else [],
        )
        return 0

    if shutil.which("gh") is None:
        print("gh CLI not found. Install GitHub CLI and run: gh auth login", file=sys.stderr)
        return 1

    for key in REQUIRED_KEYS:
        if not keys.get(key, "").strip():
            print(f"Missing {key}= in {env_path}", file=sys.stderr)
            return 1

    auto_set = keys.get("TELEGRAM_AUTO_SET_WEBHOOK")
    if auto_set is None:
        print(
            "ERROR: TELEGRAM_AUTO_SET_WEBHOOK missing. Set to false in .env.prod.",
            file=sys.stderr,
        )
        return 1
    print(f"TELEGRAM_AUTO_SET_WEBHOOK={auto_set}")
    if auto_set.strip().lower() not in FALSEY:
        print(
            "ERROR: TELEGRAM_AUTO_SET_WEBHOOK must be false for this sync.",
            file=sys.stderr,
        )
        return 1

    backend = keys["BACKEND_URL"].rstrip("/")
    if "devdjangoreacts-projects" in backend:
        print(
            "ERROR: BACKEND_URL is SSO-protected team URL. "
            f"Use custom domain or {DEFAULT_VERCEL_URL}",
            file=sys.stderr,
        )
        return 1

    custom_preview = resolve_custom_domain(keys)
    if custom_preview and not keys.get("BASE_DOMAIN", "").strip():
        print(
            f"WARNING: BASE_DOMAIN is empty while CUSTOM_DOMAIN={custom_preview}; "
            f"set BASE_DOMAIN={custom_preview} so setWebhook uses bot subdomains."
        )

    custom_https = ""
    if not args.skip_domain:
        include_www = keys.get("CUSTOM_DOMAIN_WWW", "").strip().lower() in TRUTHY
        try:
            custom_https = setup_custom_domain(keys, include_www=include_www)
        except RuntimeError as exc:
            print(f"ERROR domain setup: {exc}", file=sys.stderr)
            return 1
        if custom_https:
            sync_github_production_url(args.repo, custom_https)

    webhook_base = resolve_webhook_base_domain(keys)
    if not webhook_base:
        print(
            "ERROR: set BASE_DOMAIN, CUSTOM_DOMAIN or BACKEND_URL so bots get a webhook host.",
            file=sys.stderr,
        )
        return 1
    dsn = keys.get("DATABASE_URL", "").strip()
    ensure_webhooks_or_fail(
        keys,
        base_domain=webhook_base,
        bots=list_active_bots(dsn) if dsn else [],
    )

    print(f"Updating GitHub secret ENV_PROD for {args.repo} (values hidden)...")
    run(
        ["gh", "secret", "set", "ENV_PROD", "--repo", args.repo],
        input_text=raw if raw.endswith("\n") else raw + "\n",
    )
    print("OK  ENV_PROD updated.")

    if args.no_redeploy:
        print("Skipped redeploy (--no-redeploy).")
        return 0

    print(f"Re-running latest '{args.workflow}' workflow...")
    run_id = run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            args.repo,
            "--workflow",
            args.workflow,
            "--limit",
            "1",
            "--json",
            "databaseId",
            "--jq",
            ".[0].databaseId",
        ]
    ).stdout.strip()
    if not run_id:
        print(f"No workflow runs found for {args.workflow}", file=sys.stderr)
        return 1

    run(["gh", "run", "rerun", run_id, "--repo", args.repo])
    print(f"OK  Redeploy started: run {run_id}")

    try:
        wait_for_run(args.repo, run_id)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.skip_verify:
        print("Skipped verify (--skip-verify).")
        return 0

    print("Waiting 20s for DNS/SSL/alias...")
    time.sleep(20)

    probe_urls = resolve_probe_urls(args.repo, backend, custom_https=custom_https)
    print("Probe candidates: " + ", ".join(probe_urls))

    working: str | None = None
    for candidate in probe_urls:
        print(f"Probe cold {candidate}/health ...")
        code1, t1, body1 = probe_health_retries(candidate, attempts=4, timeout=45)
        print(f"cold  HTTP {code1}  {t1:.2f}s  body={body1[:80]}")
        if code1 != 200:
            continue
        time.sleep(1)
        print(f"Probe warm {candidate}/health ...")
        code2, t2, body2 = probe_health(candidate, timeout=45)
        print(f"warm  HTTP {code2}  {t2:.2f}s  body={body2[:80]}")
        if code2 == 200:
            working = candidate
            break

    if working is None:
        print(
            "FAIL /health unreachable on all probe URLs. "
            "If custom domain is new, wait for Cloudflare/Vercel SSL (up to ~5–15 min) "
            f"or temporarily use {DEFAULT_VERCEL_URL}.",
            file=sys.stderr,
        )
        return 1

    if working.rstrip("/") != backend:
        if hostname_from_url(backend) == hostname_from_url(working):
            pass
        elif hostname_from_url(backend) and not hostname_from_url(backend).endswith(
            ".vercel.app"
        ):
            print(
                f"WARNING: custom domain {backend} not ready yet "
                f"(DNS/SSL can take 5–15 min). Verified app via {working}. "
                "Keep BACKEND_URL as the custom domain; re-check later:"
            )
            print(f"  curl.exe -sS -w \"%{{http_code}} %{{time_total}}s\\n\" {backend}/health")
        else:
            print(
                f"WARNING: BACKEND_URL ({backend}) did not respond; "
                f"verified via {working}."
            )

    try:
        ok_logs = check_telegram_logs()
    except Exception as exc:  # noqa: BLE001 - verify step must not crash deploy success
        print(f"WARNING: log check failed ({exc}); deploy itself succeeded.")
        ok_logs = False
    if not ok_logs and auto_set.strip().lower() in FALSEY:
        print("Retry log check after another /health...")
        probe_health(working, timeout=45)
        time.sleep(3)
        try:
            ok_logs = check_telegram_logs()
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: log check failed ({exc}).")
            ok_logs = False

    if not ok_logs:
        print(
            "DONE with warnings. Deploy OK. Check logs later if needed:\n"
            "  npx vercel logs --environment production --since 15m --query Telegram",
            file=sys.stderr,
        )
        return 2

    print("DONE  Env synced, deploy green, webhook auto-set disabled.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
