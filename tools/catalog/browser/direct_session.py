"""Single upstream proxy session for Docker worker (no mitm relay)."""

from __future__ import annotations

from .leak_check import IpLeakChecker
from .models import FetchResult, ProxyCredentials
from .nodriver_browser import create_browser


class DirectProxySession:
    def __init__(
        self,
        credentials: ProxyCredentials,
        *,
        proxy_id: str = "worker",
        headless: bool = True,
        expected_ip: str = "",
    ) -> None:
        self._credentials = credentials
        self._proxy_id = proxy_id
        self._expected_ip = expected_ip
        self._browser = create_browser(headless=headless)
        self._leak = IpLeakChecker()
        self._exit_ip = ""

    @classmethod
    def from_line(
        cls,
        proxy_line: str,
        *,
        proxy_id: str = "worker",
        headless: bool = True,
        expected_ip: str = "",
    ) -> DirectProxySession:
        return cls(
            ProxyCredentials.from_line(proxy_line),
            proxy_id=proxy_id,
            headless=headless,
            expected_ip=expected_ip,
        )

    @property
    def exit_ip(self) -> str:
        return self._exit_ip

    @property
    def active_proxy_id(self) -> str:
        return self._proxy_id

    @property
    def proxy_url(self) -> str:
        return self._credentials.as_http_url()

    async def open(self) -> DirectProxySession:
        await self._browser.start(proxy=self._credentials)
        self._exit_ip = await self._leak.verify(
            self._browser, expected_ip=self._expected_ip
        )
        return self

    async def close(self) -> None:
        await self._browser.stop()

    async def fetch(self, url: str, *, wait_s: float = 3.0) -> FetchResult:
        html = await self._browser.get_html(url, wait_s=wait_s)
        return FetchResult(
            html=html,
            proxy_id=self._proxy_id,
            exit_ip=self._exit_ip,
            url=url,
        )

    async def __aenter__(self) -> DirectProxySession:
        return await self.open()

    async def __aexit__(self, *args: object) -> None:
        await self.close()
