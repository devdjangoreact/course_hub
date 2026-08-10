"""Orchestrates relay + nodriver + leak check + round-robin proxy pool."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .leak_check import IpLeakChecker
from .models import FetchResult
from .nodriver_browser import create_browser
from .protocols import Browser, LeakChecker, ProxyPool, ProxyRelay
from .proxy_pool import JsonProxyPool
from .relay import MitmUpstreamRelay


class ProxyBrowserSession:
    """
    High-level reusable session:
      one browser per session; only local mitm relay switches upstream proxy.
    Fail-closed: never falls back to direct network.
    """

    def __init__(
        self,
        pool: ProxyPool,
        relay: ProxyRelay,
        browser: Browser,
        leak_checker: LeakChecker,
    ) -> None:
        self._pool = pool
        self._relay = relay
        self._browser = browser
        self._leak_checker = leak_checker
        self._active_index: Optional[int] = None
        self._exit_ip: str = ""

    @classmethod
    def from_defaults(
        cls,
        proxies_path: Path,
        relay_port: int = 8899,
        *,
        headless: bool = True,
    ) -> ProxyBrowserSession:
        return cls(
            pool=JsonProxyPool(proxies_path),
            relay=MitmUpstreamRelay(listen_port=relay_port),
            browser=create_browser(headless=headless),
            leak_checker=IpLeakChecker(),
        )

    @property
    def exit_ip(self) -> str:
        return self._exit_ip

    @property
    def active_proxy_id(self) -> Optional[str]:
        if self._active_index is None:
            return None
        return self._pool.get(self._active_index).id

    @property
    def proxy_url(self) -> Optional[str]:
        """Active upstream proxy as http://user:pass@host:port (not the local relay)."""
        if self._active_index is None:
            return None
        return self._pool.get(self._active_index).credentials.as_http_url()

    async def open(self) -> ProxyBrowserSession:
        """Try proxies in round-robin until leak check passes (one browser)."""
        last_error = "all proxies failed"
        for index in self._pool.round_robin_indices():
            try:
                await self._activate(index)
                return self
            except Exception as exc:
                last_error = str(exc)
                self._pool.mark(index, works=False, error=last_error[:500])
                self._pool.advance(index)
                self._relay.stop()
        await self._browser.stop()
        raise RuntimeError(last_error)

    async def _activate(self, index: int) -> None:
        endpoint = self._pool.get(index)
        self._relay.start(endpoint.credentials)
        self._relay.wait_ready()
        await self._browser.start(local_relay_port=self._relay.listen_port)
        seen_ip = await self._leak_checker.verify(
            self._browser, expected_ip=endpoint.expected_ip
        )
        self._pool.mark(
            index,
            works=True,
            error=None,
            expected_ip=seen_ip if not endpoint.expected_ip else None,
        )
        self._pool.advance(index)
        self._active_index = index
        self._exit_ip = seen_ip

    async def fetch(self, url: str, wait_s: float = 3.0) -> FetchResult:
        if self._active_index is None:
            await self.open()
        assert self._active_index is not None
        html = await self._browser.get_html(url, wait_s=wait_s)
        endpoint = self._pool.get(self._active_index)
        return FetchResult(
            html=html,
            proxy_id=endpoint.id,
            exit_ip=self._exit_ip,
            url=url,
        )

    async def close(self) -> None:
        await self._browser.stop()
        self._relay.stop()
        self._active_index = None
        self._exit_ip = ""

    async def __aenter__(self) -> ProxyBrowserSession:
        return await self.open()

    async def __aexit__(self, *args: object) -> None:
        await self.close()
