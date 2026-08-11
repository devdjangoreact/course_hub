"""Fail-closed proxy env helpers for the enrich worker."""

from __future__ import annotations

from typing import Mapping

from browser.models import ProxyCredentials


def proxy_line_to_http_url(line: str) -> str:
    return ProxyCredentials.from_line(line).as_http_url()


def require_proxy_env(environ: Mapping[str, str]) -> str:
    missing = [
        k
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
        if not (environ.get(k) or "").strip()
    ]
    if missing:
        raise RuntimeError(
            f"proxy kill-switch: missing env {', '.join(missing)} — refuse direct egress"
        )
    return (environ.get("HTTP_PROXY") or "").strip()
