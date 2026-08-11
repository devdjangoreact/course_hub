"""Nodriver Chrome wrapper: proxy via local relay, WebRTC leak flags."""

from __future__ import annotations

import asyncio
from typing import Any

from .models import ProxyCredentials


def chrome_proxy_server_arg(credentials: ProxyCredentials) -> str:
    """Chrome --proxy-server value (no userinfo; auth via CDP)."""
    return f"http://{credentials.host}:{credentials.port}"


_WEBRTC_ARGS = [
    "--disable-features=WebRtcHideLocalIpsWithMdns",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
]


async def _enable_proxy_auth(tab: Any, *, username: str, password: str) -> None:
    from nodriver import cdp

    async def on_auth(event: cdp.fetch.AuthRequired) -> None:
        asyncio.create_task(
            tab.send(
                cdp.fetch.continue_with_auth(
                    request_id=event.request_id,
                    auth_challenge_response=cdp.fetch.AuthChallengeResponse(
                        response="ProvideCredentials",
                        username=username,
                        password=password,
                    ),
                )
            )
        )

    async def on_paused(event: cdp.fetch.RequestPaused) -> None:
        asyncio.create_task(
            tab.send(cdp.fetch.continue_request(request_id=event.request_id))
        )

    tab.add_handler(cdp.fetch.AuthRequired, on_auth)
    tab.add_handler(cdp.fetch.RequestPaused, on_paused)
    await tab.send(cdp.fetch.enable(handle_auth_requests=True))


class NodriverBrowser:
    """Browser launcher/session: local mitm relay port OR direct ProxyCredentials."""

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._browser: Any = None
        self._relay_port: int | None = None
        self._proxy: ProxyCredentials | None = None

    @property
    def raw(self) -> Any:
        return self._browser

    @property
    def started(self) -> bool:
        return self._browser is not None

    async def start(
        self,
        *,
        local_relay_port: int | None = None,
        proxy: ProxyCredentials | None = None,
    ) -> None:
        if local_relay_port is not None and proxy is not None:
            raise ValueError("provide exactly one of local_relay_port or proxy")
        if local_relay_port is None and proxy is None:
            raise ValueError("provide exactly one of local_relay_port or proxy")

        if proxy is not None:
            if self._browser is not None and self._proxy == proxy:
                return
            if self._browser is not None:
                await self.stop()

            import nodriver as uc

            self._browser = await uc.start(
                headless=self._headless,
                browser_args=[
                    f"--proxy-server={chrome_proxy_server_arg(proxy)}",
                    *_WEBRTC_ARGS,
                ],
            )
            await _enable_proxy_auth(
                self._browser.main_tab,
                username=proxy.username,
                password=proxy.password,
            )
            self._proxy = proxy
            return

        assert local_relay_port is not None
        if self._browser is not None and self._relay_port == local_relay_port:
            return
        if self._browser is not None:
            await self.stop()

        import nodriver as uc

        # mitmproxy MITM CA is not trusted by Chrome — ignore for local relay only
        self._browser = await uc.start(
            headless=self._headless,
            browser_args=[
                f"--proxy-server=127.0.0.1:{local_relay_port}",
                "--ignore-certificate-errors",
                "--allow-insecure-localhost",
                *_WEBRTC_ARGS,
            ],
        )
        self._relay_port = local_relay_port

    async def stop(self) -> None:
        browser = self._browser
        self._browser = None
        self._relay_port = None
        self._proxy = None
        if browser is None:
            return
        # nodriver.Browser.stop() fire-and-forgets aclose + terminate without
        # awaiting process.wait(); on Windows Proactor that leaves PIPE
        # transports unclosed → "I/O operation on closed pipe" at exit.
        try:
            await browser.aclose()
        except Exception:
            pass
        proc = getattr(browser, "_process", None)
        if proc is not None and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
        if proc is not None:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is None:
                    continue
                try:
                    stream.close()
                except Exception:
                    pass
                wait_closed = getattr(stream, "wait_closed", None)
                if wait_closed is not None:
                    try:
                        await wait_closed()
                    except Exception:
                        pass
        try:
            browser._process = None
            browser._process_pid = None
        except Exception:
            pass

    async def get_html(self, url: str, wait_s: float = 3.0) -> str:
        if self._browser is None:
            raise RuntimeError("browser not started")
        page = await self._browser.get(url)
        if wait_s > 0:
            await page.sleep(wait_s)
        content = await page.get_content()
        return content or ""

    async def __aenter__(self) -> NodriverBrowser:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()


def create_browser(*, headless: bool = True) -> NodriverBrowser:
    return NodriverBrowser(headless=headless)
