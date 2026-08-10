"""Proxy / browser value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote


@dataclass(frozen=True)
class ProxyCredentials:
    host: str
    port: int
    username: str
    password: str

    @classmethod
    def from_line(cls, raw: str) -> ProxyCredentials:
        parts = raw.strip().split(":")
        if len(parts) < 4:
            raise ValueError(f"proxy must be host:port:user:pass, got {raw!r}")
        return cls(
            host=parts[0],
            port=int(parts[1]),
            username=parts[2],
            password=":".join(parts[3:]),
        )

    def as_line(self) -> str:
        return f"{self.host}:{self.port}:{self.username}:{self.password}"

    def as_http_url(self) -> str:
        """http://user:pass@host:port for requests/httpx/OpenAI."""
        user = quote(self.username, safe="")
        password = quote(self.password, safe="")
        return f"http://{user}:{password}@{self.host}:{self.port}"


@dataclass
class ProxyEndpoint:
    id: str
    credentials: ProxyCredentials
    expected_ip: str = ""
    works: Optional[bool] = None
    last_checked: Optional[str] = None
    last_error: Optional[str] = None
    plan_id: Any = None
    proxy_type: str = ""
    proxy_subtype: str = ""
    mode: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], fallback_id: str) -> ProxyEndpoint:
        line = str(data.get("proxy") or "")
        return cls(
            id=str(data.get("id") or fallback_id),
            credentials=ProxyCredentials.from_line(line),
            expected_ip=str(data.get("expected_ip") or "").strip(),
            works=data.get("works"),
            last_checked=data.get("last_checked"),
            last_error=data.get("last_error"),
            plan_id=data.get("plan_id"),
            proxy_type=str(data.get("proxy_type") or ""),
            proxy_subtype=str(data.get("proxy_subtype") or ""),
            mode=str(data.get("mode") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proxy": self.credentials.as_line(),
            "expected_ip": self.expected_ip,
            "works": self.works,
            "last_checked": self.last_checked,
            "last_error": self.last_error,
            "plan_id": self.plan_id,
            "proxy_type": self.proxy_type,
            "proxy_subtype": self.proxy_subtype,
            "mode": self.mode,
        }


@dataclass
class FetchResult:
    html: str
    proxy_id: str
    exit_ip: str
    url: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
