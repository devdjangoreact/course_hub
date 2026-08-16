from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

CATALOG = Path(__file__).resolve().parents[2] / "tools" / "catalog"
WORKER = CATALOG / "worker"
pytest.importorskip("requests")
sys.path.insert(0, str(CATALOG))
sys.path.insert(0, str(WORKER))

from browser.models import ProxyCredentials  # noqa: E402
from browser.nodriver_browser import chrome_proxy_server_arg  # noqa: E402
from proxy_env import proxy_line_to_http_url, require_proxy_env  # noqa: E402
from worker_orchestrator import plan_wave  # noqa: E402


def test_chrome_proxy_server_arg_is_host_port_only():
    creds = ProxyCredentials.from_line("1.2.3.4:80:user:p@ss:word")
    assert chrome_proxy_server_arg(creds) == "http://1.2.3.4:80"


def test_proxy_credentials_as_http_url_quotes():
    creds = ProxyCredentials.from_line("1.2.3.4:80:user:p@ss")
    assert creds.as_http_url().startswith("http://user:p%40ss@1.2.3.4:80")


def test_destination_name_flancki():
    pytest.importorskip("bs4")
    from enrich_searxng.worker_job import destination_name

    assert destination_name(Path("/x/categories/flancki")) == "flancki"


def test_destination_name_none_is_need_enrich():
    pytest.importorskip("bs4")
    from enrich_searxng.worker_job import destination_name

    assert destination_name(None) == "flancki_need_enrich"


def test_require_proxy_env_fails_when_missing(monkeypatch):
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)
    with pytest.raises(RuntimeError, match="HTTP_PROXY"):
        require_proxy_env(os.environ)


def test_require_proxy_env_ok(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://u:p@h:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://u:p@h:1")
    monkeypatch.setenv("ALL_PROXY", "http://u:p@h:1")
    assert require_proxy_env(os.environ) == "http://u:p@h:1"


def test_proxy_line_to_http_url():
    assert proxy_line_to_http_url("10.0.0.1:8080:alice:s3cret") == (
        "http://alice:s3cret@10.0.0.1:8080"
    )


def test_plan_wave_splits_batches():
    class P:
        def __init__(self, id):  # noqa: A002
            self.id = id

    courses = [Path(f"{i}.json") for i in range(12)]
    proxies = [P("a"), P("b"), P("c")]
    waves = plan_wave(courses, proxies, concurrency=2, batch_size=5)
    assert len(waves) == 2
    assert len(waves[0].paths) == 5
    assert len(waves[1].paths) == 5
