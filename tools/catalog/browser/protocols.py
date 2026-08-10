"""Narrow interfaces for proxy browser stack (ISP / DIP)."""

from __future__ import annotations

from typing import Optional, Protocol

from .models import ProxyCredentials, ProxyEndpoint


class ProxyPool(Protocol):
    def __len__(self) -> int: ...

    def round_robin_indices(self) -> list[int]: ...

    def get(self, index: int) -> ProxyEndpoint: ...

    def mark(
        self,
        index: int,
        *,
        works: bool,
        error: Optional[str] = None,
        expected_ip: Optional[str] = None,
    ) -> None: ...

    def advance(self, used_index: int) -> None: ...


class ProxyRelay(Protocol):
    @property
    def listen_host(self) -> str: ...

    @property
    def listen_port(self) -> int: ...

    def start(self, credentials: ProxyCredentials) -> None: ...

    def wait_ready(self, timeout: float = 10.0) -> None: ...

    def stop(self) -> None: ...


class Browser(Protocol):
    async def start(self, *, local_relay_port: int) -> None: ...

    async def stop(self) -> None: ...

    async def get_html(self, url: str, wait_s: float = 3.0) -> str: ...


class LeakChecker(Protocol):
    async def verify(self, browser: Browser, expected_ip: str = "") -> str: ...
