"""Own the payment side end to end: settings validation, Atlos postback, live verification.

Single owner of "payments are configured and actually take money", for every caller: the
admin form, the order service, the deploy script and CI. Settings behave the same no matter
which path wrote them, and one function decides whether payments are live.

Stdlib only on purpose: the deploy script imports this from CI, where app dependencies
(sqlalchemy, httpx, asyncpg) are not installed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlparse

# Providers RoutingPaymentGateway can serve, and the settings each one needs to take money.
# Everything else (admin choices, validation, deploy gate) reads this map, so a new provider
# is declared once.
PROVIDER_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "simulated": (),
    "atlos": ("api_key", "secret_key"),
}
CHECKOUT_MODES = ("direct", "checkout")
ATLOS_WEBHOOK_PATH = "/api/payments/atlos/webhook"
# Synthetic buyer for the deploy probe. Telegram ids are positive, so 0 collides with nobody.
PROBE_TELEGRAM_ID = 0
USER_AGENT = "course-hub-payments-probe"
_TIMEOUT = 30


def _request(url: str, body: dict[str, Any] | None = None, *, timeout: int) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    # Cloudflare in front of the bot hosts answers 403 (error 1010) to urllib's default agent.
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw.strip() else raw[:200]
        except json.JSONDecodeError:
            return exc.code, raw[:200]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def _short(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)[:200] if payload is not None else ""


def extra_dict(extra: Any) -> dict[str, Any]:
    """payment_settings.extra reaches us as a dict from the ORM and as JSON text from asyncpg."""
    if isinstance(extra, str):
        try:
            extra = json.loads(extra or "{}")
        except json.JSONDecodeError:
            return {}
    return extra if isinstance(extra, dict) else {}


def checkout_mode(extra: Any) -> str:
    """Configured link mode as stored; validation is what rejects an unknown one."""
    return str(extra_dict(extra).get("checkout_mode", "direct"))


def settings_problem(row: Mapping[str, Any]) -> str:
    """Why this payment_settings row cannot take money, or an empty string. Never leaks keys."""
    label = f"payment_settings#{row.get('id', 'new')}"
    provider = str(row.get("provider") or "").strip().lower()
    if provider not in PROVIDER_REQUIREMENTS:
        known = ", ".join(sorted(PROVIDER_REQUIREMENTS))
        return f"{label}: unknown provider {provider or '(empty)'}, expected one of {known}"
    missing = [
        field for field in PROVIDER_REQUIREMENTS[provider] if not str(row.get(field) or "").strip()
    ]
    if missing:
        return f"{label}: provider {provider} needs {', '.join(missing)}"
    currency = str(row.get("currency") or "").strip()
    if len(currency) != 3 or not currency.isalpha():
        return f"{label}: currency {currency or '(empty)'} is not a 3-letter code"
    mode = checkout_mode(row.get("extra"))
    if mode not in CHECKOUT_MODES:
        return f"{label}: checkout_mode {mode} is not one of {', '.join(CHECKOUT_MODES)}"
    return ""


def settings_problems(rows: Iterable[Mapping[str, Any]]) -> str:
    """Check every row: the runtime picks one, and any row can become the one it picks."""
    reasons = [reason for reason in (settings_problem(row) for row in rows) if reason]
    return "; ".join(reasons)


def atlos_postback_url(backend_url: str) -> str | None:
    """Where Atlos confirms a paid invoice, or None when this host is unreachable for it."""
    parsed = urlparse(backend_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return None
    if host in {"localhost", "127.0.0.1"} or host.endswith((".ngrok-free.app", ".ngrok.io")):
        return None
    return f"{backend_url.rstrip('/')}{ATLOS_WEBHOOK_PATH}"


def cheapest_course_id(base_url: str, *, timeout: int = _TIMEOUT) -> tuple[int, str]:
    """Cheapest priced course in the live catalog, so the probe pins no course id."""
    status, categories = _request(f"{base_url}/api/categories", timeout=timeout)
    if status != 200 or not isinstance(categories, list):
        return 0, f"GET /api/categories -> HTTP {status} {_short(categories)}"
    best: tuple[float, int] | None = None
    for category in categories:
        if not isinstance(category, dict) or category.get("id") is None:
            continue
        status, courses = _request(
            f"{base_url}/api/categories/{category['id']}/courses", timeout=timeout
        )
        if status != 200 or not isinstance(courses, list):
            continue
        for course in courses:
            if not isinstance(course, dict) or course.get("id") is None:
                continue
            try:
                price = float(course.get("price") or 0)
            except (TypeError, ValueError):
                continue
            # A free course would ask the provider for a zero invoice, which proves nothing.
            if price <= 0:
                continue
            if best is None or price < best[0]:
                best = (price, int(course["id"]))
    if best is None:
        return 0, "catalog has no priced course to probe with"
    return best[1], ""


def ensure_payments(
    *,
    base_url: str,
    rows: Iterable[Mapping[str, Any]] = (),
    backend_url: str = "",
    telegram_id: int = PROBE_TELEGRAM_ID,
    timeout: int = _TIMEOUT,
) -> tuple[str, str]:
    """Prove payments work here: valid settings, a reachable postback, one real invoice.

    Returns (failure reason, summary). An empty reason means an invoice was really created.
    """
    base = base_url.rstrip("/")
    if not base.startswith("http"):
        return f"base_url {base or '(empty)'} is not an http(s) URL", ""

    rows = list(rows)
    problem = settings_problems(rows)
    if problem:
        return problem, ""

    postback_host = (backend_url or base).rstrip("/")
    uses_atlos = any(str(row.get("provider") or "").strip().lower() == "atlos" for row in rows)
    if uses_atlos and not atlos_postback_url(postback_host):
        return (
            f"atlos is configured but {postback_host} yields no postback URL, "
            "so paid invoices would never be confirmed",
            "",
        )

    course_id, reason = cheapest_course_id(base, timeout=timeout)
    if reason:
        return reason, ""

    status, payload = _request(
        f"{base}/api/orders",
        {
            "telegram_id": telegram_id,
            "course_id": course_id,
            "username": "payments-probe",
            "full_name": "Payments Probe",
        },
        timeout=timeout,
    )
    if status != 201 or not isinstance(payload, dict):
        return f"POST /api/orders -> HTTP {status} {_short(payload)}", ""
    payment = payload.get("payment")
    pay_url = payment.get("pay_url") if isinstance(payment, dict) else None
    if not isinstance(pay_url, str) or not pay_url.strip():
        return f"order {payload.get('order_id')} was created without a payment link", ""
    return "", (
        f"payments live: {len(rows)} settings row(s) checked, order {payload.get('order_id')} "
        f"for course {course_id} -> {pay_url}"
    )
