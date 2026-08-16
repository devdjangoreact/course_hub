"""Register and verify a Telegram webhook. Single owner of this step for every caller.

Used by the admin bot form, app startup and the deploy script, so a bot is configured
identically no matter how it enters the database.

Stdlib only on purpose: the deploy script imports this from CI, where app dependencies
(aiogram, asyncpg) are not installed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.core.domain_host import normalize_bot_username, webhook_url_for_bot

# ponytail: mirrors Dispatcher.resolve_used_update_types(); widen if handlers gain a type.
REQUIRED_UPDATES = ["message", "callback_query"]
DEFAULT_WEBHOOK_PATH = "/api/telegram/webhook"
_TIMEOUT = 20


def _api(token: str, method: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    """Call the Bot API. Never log the request URL: it embeds the token."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return exc.code, {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {"description": str(exc)}


def _ok(status: int, payload: Any) -> bool:
    return status == 200 and isinstance(payload, dict) and payload.get("ok") is True


def _result(status: int, payload: Any) -> dict[str, Any]:
    if not _ok(status, payload):
        return {}
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def _describe(payload: Any) -> str:
    return str(payload.get("description") or "") if isinstance(payload, dict) else ""


def fetch_username(token: str) -> str:
    """Normalized bot username from getMe, or an empty string when unavailable."""
    me = _result(*_api(token.strip(), "getMe"))
    return normalize_bot_username(str(me.get("username") or ""))


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


def ensure_webhook(
    *,
    username: str,
    token: str,
    base_domain: str,
    secret: str = "",
    webhook_path: str = DEFAULT_WEBHOOK_PATH,
) -> str:
    """Point the webhook at this bot's host when it drifted, then verify it really is live.

    Returns an empty string on success, otherwise a human-readable failure reason.
    """
    token = token.strip()
    if not token:
        return f"@{username}: empty token"
    if not base_domain.strip():
        return f"@{username}: no base_domain, cannot build a webhook host"
    path = webhook_path if webhook_path.startswith("/") else f"/{webhook_path}"
    expected = webhook_url_for_bot(username=username, base_domain=base_domain, webhook_path=path)

    info = _result(*_api(token, "getWebhookInfo"))
    widened = merged_allowed_updates(info.get("allowed_updates"))
    if str(info.get("url") or "") != expected or widened is not None:
        body: dict[str, Any] = {"url": expected}
        if widened is not None:
            body["allowed_updates"] = widened
        if secret.strip():
            body["secret_token"] = secret.strip()
        status, payload = _api(token, "setWebhook", body)
        if not _ok(status, payload):
            return f"@{username}: setWebhook failed (HTTP {status}) {_describe(payload)}".strip()

    final = _result(*_api(token, "getWebhookInfo"))
    live = str(final.get("url") or "")
    if live != expected:
        return f"@{username}: webhook is {live or '(none)'}, expected {expected}"
    allowed = final.get("allowed_updates")
    if not allows_required(allowed):
        return f"@{username}: allowed_updates={allowed} misses {REQUIRED_UPDATES}"
    return ""
