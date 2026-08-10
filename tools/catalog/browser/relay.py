"""mitmproxy upstream CONNECT relay bound to 127.0.0.1 only."""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from .models import ProxyCredentials


class MitmUpstreamRelay:
    """
    Local relay: Chrome → 127.0.0.1:port → upstream authenticated proxy.
    Fail-closed: wait_ready raises if relay does not come up.
    """

    def __init__(self, listen_port: int = 8899, listen_host: str = "127.0.0.1") -> None:
        if listen_host != "127.0.0.1":
            raise ValueError("listen_host must be 127.0.0.1 (no 0.0.0.0)")
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._proc: Optional[subprocess.Popen[str]] = None

    @property
    def listen_host(self) -> str:
        return self._listen_host

    @property
    def listen_port(self) -> int:
        return self._listen_port

    @staticmethod
    def _mitmdump_cmd() -> list[str]:
        # PATH may omit venv Scripts when launched as .venv/Scripts/python.exe
        name = "mitmdump.exe" if sys.platform == "win32" else "mitmdump"
        sibling = Path(sys.executable).resolve().parent / name
        if sibling.is_file():
            return [str(sibling)]
        exe = shutil.which("mitmdump")
        if exe:
            return [exe]
        return [sys.executable, "-m", "mitmproxy.tools.dump"]

    def start(self, credentials: ProxyCredentials) -> None:
        self.stop()
        cmd = [
            *self._mitmdump_cmd(),
            "--mode",
            f"upstream:http://{credentials.host}:{credentials.port}",
            "--upstream-auth",
            f"{credentials.username}:{credentials.password}",
            "--listen-host",
            self._listen_host,
            "--listen-port",
            str(self._listen_port),
            "--set",
            "connection_strategy=lazy",
            "--set",
            "ssl_insecure=true",
            "--quiet",
        ]
        # DEVNULL: PIPE fills and deadlocks mitmdump on Windows
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if self._proc.poll() is not None:
            self._proc = None
            raise RuntimeError("relay exited immediately")

    def wait_ready(self, timeout: float = 10.0) -> None:
        start = time.time()
        while time.time() - start < timeout:
            if self._proc is not None and self._proc.poll() is not None:
                raise RuntimeError("relay died during wait")
            try:
                with socket.create_connection(
                    (self._listen_host, self._listen_port), timeout=1
                ):
                    return
            except (ConnectionRefusedError, OSError, TimeoutError):
                time.sleep(0.3)
        raise RuntimeError(
            "Relay did not start — aborting, no direct-connection fallback"
        )

    def stop(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    def __enter__(self) -> MitmUpstreamRelay:
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
