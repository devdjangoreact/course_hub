"""Docker worker entry: batch JSON in → enriched results out (no Telegram)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from browser.direct_session import DirectProxySession
from enrich_searxng.llm import LLM_BACKEND, NVIDIA_MODEL, set_active_http_proxy
from enrich_searxng.worker_job import enrich_job
from proxy_env import require_proxy_env


def build_result(*, ok: bool, meta: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    return {"ok": ok, "meta": meta, "results": results}


def _apply_llm_overrides(llm: dict[str, Any] | None) -> None:
    if not llm:
        return
    backend = llm.get("backend")
    if isinstance(backend, str) and backend.strip():
        os.environ["LLM_BACKEND"] = backend.strip()
    model = llm.get("model")
    if isinstance(model, str) and model.strip():
        backend_now = (os.environ.get("LLM_BACKEND") or LLM_BACKEND or "nvidia").lower()
        if backend_now == "openrouter":
            os.environ["OPENROUTER_MODEL"] = model.strip()
        elif backend_now == "bedrock":
            os.environ["AWS_BEDROCK_MODEL_ID"] = model.strip()
        else:
            os.environ["NVIDIA_MODEL"] = model.strip()
    base_url = llm.get("base_url")
    if isinstance(base_url, str) and base_url.strip():
        backend_now = (os.environ.get("LLM_BACKEND") or LLM_BACKEND or "nvidia").lower()
        if backend_now == "openrouter":
            os.environ["OPENROUTER_BASE_URL"] = base_url.strip()
        else:
            os.environ["NVIDIA_BASE_URL"] = base_url.strip()


def _failed_all_jobs(payload: dict[str, Any], error: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for job in payload.get("jobs") or []:
        course = job.get("course") if isinstance(job.get("course"), dict) else {}
        out.append(
            {
                "id": job.get("id"),
                "ok": False,
                "course": course,
                "destination": "flancki_need_enrich",
                "error": error,
            }
        )
    return out


async def run_batch(payload: dict[str, Any]) -> dict[str, Any]:
    proxy_url = require_proxy_env(os.environ)
    _apply_llm_overrides(payload.get("llm") if isinstance(payload.get("llm"), dict) else None)

    os.environ["SEARXNG_URL"] = "http://127.0.0.1:8080/search"
    os.environ["SEARXNG_USE_SESSION_PROXY"] = "0"
    set_active_http_proxy(proxy_url)

    proxy_line = str(payload.get("proxy") or "").strip()
    if not proxy_line:
        raise RuntimeError("payload.proxy (host:port:user:pass) is required")

    headless = (os.environ.get("BROWSER_HEADLESS") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    meta = {
        "exit_ip": "",
        "proxy": proxy_line,
        "llm_backend": (os.environ.get("LLM_BACKEND") or LLM_BACKEND or "nvidia"),
        "llm_model": (os.environ.get("NVIDIA_MODEL") or NVIDIA_MODEL or ""),
    }

    try:
        async with DirectProxySession.from_line(proxy_line, headless=headless) as session:
            meta["exit_ip"] = session.exit_ip
            results: list[dict[str, Any]] = []
            for job in payload.get("jobs") or []:
                job_id = job.get("id")
                course = job.get("course")
                if not isinstance(course, dict):
                    results.append(
                        {
                            "id": job_id,
                            "ok": False,
                            "course": {},
                            "destination": "flancki_need_enrich",
                            "error": "missing course object",
                        }
                    )
                    continue
                one = await enrich_job(course, session)
                one["id"] = job_id
                results.append(one)
            return build_result(ok=True, meta=meta, results=results)
    except Exception as exc:  # noqa: BLE001 — container-level failure
        err = f"{type(exc).__name__}: {exc}"
        return build_result(ok=False, meta=meta, results=_failed_all_jobs(payload, err))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Catalog enrich worker batch")
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--out", dest="out_path", required=True)
    args = parser.parse_args(argv)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    payload = json.loads(in_path.read_text(encoding="utf-8"))

    try:
        require_proxy_env(os.environ)
    except RuntimeError as exc:
        out_path.write_text(
            json.dumps(
                build_result(
                    ok=False,
                    meta={
                        "exit_ip": "",
                        "proxy": str((payload or {}).get("proxy") or ""),
                        "llm_backend": os.environ.get("LLM_BACKEND") or "",
                        "llm_model": "",
                    },
                    results=_failed_all_jobs(payload if isinstance(payload, dict) else {}, str(exc)),
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(exc, file=sys.stderr)
        return 1

    result = asyncio.run(run_batch(payload))
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
