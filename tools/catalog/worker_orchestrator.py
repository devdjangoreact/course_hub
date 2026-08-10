"""Host orchestrator stub — Docker worker waves (next stage).

Next stage: pick proxies + course batches, `docker run` workers with
HTTP_PROXY kill-switch, persist results. No Telegram / Bot API here.
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError(
        "worker_orchestrator: Docker wave runner not implemented yet "
        "(see docs/superpowers/specs/2026-08-09-proxied-catalog-worker-docker-design.md)"
    )


if __name__ == "__main__":
    main()
