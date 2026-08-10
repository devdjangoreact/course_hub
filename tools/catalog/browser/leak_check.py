"""Exit-IP verification through the browser (no direct requests)."""

from __future__ import annotations

import re

from .protocols import Browser

LEAK_CHECK_URL = "https://ip.smartproxy.com/json"
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class IpLeakChecker:
    def __init__(self, check_url: str = LEAK_CHECK_URL, wait_s: float = 2.0) -> None:
        self._check_url = check_url
        self._wait_s = wait_s

    async def verify(self, browser: Browser, expected_ip: str = "") -> str:
        content = await browser.get_html(self._check_url, wait_s=self._wait_s)
        if expected_ip and expected_ip not in content:
            raise RuntimeError(
                f"IP mismatch/leak — expected {expected_ip!r} not in response"
            )
        match = IP_RE.search(content)
        if not match:
            raise RuntimeError("no public IP found in leak-check response")
        return match.group(0)
