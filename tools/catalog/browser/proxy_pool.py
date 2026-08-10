"""JSON-backed round-robin proxy pool with works=true/false marks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .models import ProxyEndpoint


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonProxyPool:
    """Persist proxies + next_index to a JSON file (SRP: storage + rotation)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._next_index = 0
        self._proxies: list[ProxyEndpoint] = []
        self.reload()

    @property
    def path(self) -> Path:
        return self._path

    def reload(self) -> None:
        if not self._path.is_file():
            raise RuntimeError(f"proxies file missing: {self._path}")
        data = json.loads(self._path.read_text(encoding="utf-8"))
        raw_list = data.get("proxies")
        if not isinstance(raw_list, list) or not raw_list:
            raise RuntimeError(f"no proxies in {self._path}")
        self._proxies = [
            ProxyEndpoint.from_dict(item, fallback_id=f"proxy-{i + 1}")
            for i, item in enumerate(raw_list)
            if isinstance(item, dict)
        ]
        if not self._proxies:
            raise RuntimeError(f"no valid proxies in {self._path}")
        self._next_index = int(data.get("next_index") or 0) % len(self._proxies)

    def _save(self) -> None:
        payload: dict[str, Any] = {
            "next_index": self._next_index,
            "proxies": [p.to_dict() for p in self._proxies],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def __len__(self) -> int:
        return len(self._proxies)

    def round_robin_indices(self) -> list[int]:
        n = len(self._proxies)
        start = self._next_index % n
        return [(start + offset) % n for offset in range(n)]

    def get(self, index: int) -> ProxyEndpoint:
        return self._proxies[index]

    def mark(
        self,
        index: int,
        *,
        works: bool,
        error: Optional[str] = None,
        expected_ip: Optional[str] = None,
    ) -> None:
        endpoint = self._proxies[index]
        endpoint.works = works
        endpoint.last_checked = _now_iso()
        endpoint.last_error = error
        if expected_ip:
            endpoint.expected_ip = expected_ip
        self._save()

    def advance(self, used_index: int) -> None:
        self._next_index = (used_index + 1) % len(self._proxies)
        self._save()
