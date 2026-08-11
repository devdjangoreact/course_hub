"""Host orchestrator: Docker worker waves for proxied catalog enrich (no Telegram)."""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CATALOG = Path(__file__).resolve().parent
if str(_CATALOG) not in sys.path:
    sys.path.insert(0, str(_CATALOG))

import config
from browser.models import ProxyEndpoint
from course_json import load_course, save_course, select_course_json_files

_ENV_ALLOWLIST = (
    "LLM_BACKEND",
    "NVIDIA_API_KEY",
    "NVIDIA_BASE_URL",
    "NVIDIA_MODEL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_MODEL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "AWS_BEDROCK_MODEL_ID",
    "BROWSER_HEADLESS",
    "LLM_HTTP_TIMEOUT",
    "LLM_RETRIES",
    "LLM_USE_SESSION_PROXY",
    "ENRICH_FETCH_WAIT_S",
)


@dataclass
class WaveWorker:
    proxy: ProxyEndpoint
    paths: list[Path]


def load_working_proxies(path: Path) -> list[ProxyEndpoint]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("proxies")
    if not isinstance(raw, list):
        return []
    out: list[ProxyEndpoint] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        ep = ProxyEndpoint.from_dict(item, fallback_id=f"proxy-{i + 1}")
        if ep.works is False:
            continue
        out.append(ep)
    return out


def plan_wave(
    courses: list[Path],
    proxies: list[ProxyEndpoint],
    *,
    concurrency: int,
    batch_size: int,
) -> list[WaveWorker]:
    """Return the next wave only (does not mutate inputs)."""
    if not courses or not proxies or concurrency < 1 or batch_size < 1:
        return []
    max_workers = min(concurrency, len(proxies), (len(courses) + batch_size - 1) // batch_size)
    workers: list[WaveWorker] = []
    offset = 0
    for i in range(max_workers):
        chunk = courses[offset : offset + batch_size]
        if not chunk:
            break
        workers.append(WaveWorker(proxy=proxies[i], paths=list(chunk)))
        offset += batch_size
    return workers


def take_wave(
    courses: list[Path],
    proxies: list[ProxyEndpoint],
    *,
    concurrency: int,
    batch_size: int,
) -> list[WaveWorker]:
    """Plan one wave and remove used courses/proxies from the mutable lists."""
    wave = plan_wave(courses, proxies, concurrency=concurrency, batch_size=batch_size)
    used_courses = sum(len(w.paths) for w in wave)
    del courses[:used_courses]
    del proxies[: len(wave)]
    return wave


def mark_proxy_failed(proxies_path: Path, proxy_line_or_id: str, error: str) -> None:
    data = json.loads(proxies_path.read_text(encoding="utf-8"))
    raw = data.get("proxies")
    if not isinstance(raw, list):
        return
    needle = proxy_line_or_id.strip()
    for item in raw:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "") == needle or str(item.get("proxy") or "") == needle:
            item["works"] = False
            item["last_error"] = error[:500]
            break
    proxies_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def persist_results(out: dict[str, Any], catalog_root: Path) -> None:
    flancki = catalog_root / "categories" / "flancki"
    need = catalog_root / "categories" / "flancki_need_enrich"
    flancki.mkdir(parents=True, exist_ok=True)
    need.mkdir(parents=True, exist_ok=True)

    for item in out.get("results") or []:
        if not isinstance(item, dict):
            continue
        course = item.get("course")
        if not isinstance(course, dict):
            continue
        job_id = str(item.get("id") or course.get("id") or "").strip()
        dest_name = item.get("destination") or "flancki_need_enrich"
        dest_dir = flancki if dest_name == "flancki" else need
        # Prefer existing filename under need_enrich / flancki
        path = _resolve_course_path(catalog_root, job_id, course)
        target = dest_dir / (path.name if path else f"{job_id or 'course'}.json")
        if path and path.resolve() != target.resolve():
            save_course(target, course)
            if path.is_file() and path.parent != target.parent:
                path.unlink(missing_ok=True)
        else:
            save_course(target, course)


def _resolve_course_path(
    catalog_root: Path, job_id: str, course: dict[str, Any]
) -> Path | None:
    categories = catalog_root / "categories"
    if job_id:
        for folder in ("flancki_need_enrich", "flancki"):
            candidate = categories / folder / f"{job_id}.json"
            if candidate.is_file():
                return candidate
        matches = list(categories.glob(f"*/{job_id}.json"))
        if matches:
            return matches[0]
    # fallback: title-based not used; write new file
    return None


def _docker_env_for_proxy(proxy_url: str) -> list[str]:
    args: list[str] = [
        "-e",
        f"HTTP_PROXY={proxy_url}",
        "-e",
        f"HTTPS_PROXY={proxy_url}",
        "-e",
        f"ALL_PROXY={proxy_url}",
        "-e",
        "NO_PROXY=localhost,127.0.0.1",
    ]
    for key in _ENV_ALLOWLIST:
        val = os.environ.get(key)
        if val is not None and str(val).strip() != "":
            args.extend(["-e", f"{key}={val}"])
    return args


def _run_one_container(
    *,
    image: str,
    proxy: ProxyEndpoint,
    paths: list[Path],
    run_dir: Path,
) -> tuple[WaveWorker, dict[str, Any], int]:
    worker = WaveWorker(proxy=proxy, paths=paths)
    run_dir.mkdir(parents=True, exist_ok=True)
    in_path = run_dir / "in.json"
    out_path = run_dir / "out.json"
    jobs = []
    for path in paths:
        course = load_course(path)
        jobs.append({"id": path.stem, "course": course})
    payload = {
        "proxy": proxy.credentials.as_line(),
        "llm": {"backend": os.environ.get("LLM_BACKEND") or "nvidia"},
        "jobs": jobs,
    }
    in_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if out_path.exists():
        out_path.unlink()
    out_path.write_text("{}\n", encoding="utf-8")

    proxy_url = proxy.credentials.as_http_url()
    cmd = [
        "docker",
        "run",
        "--rm",
        *_docker_env_for_proxy(proxy_url),
        "-v",
        f"{in_path.resolve()}:/work/in.json:ro",
        "-v",
        f"{out_path.resolve()}:/work/out.json",
        image,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        result = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception:
        result = {
            "ok": False,
            "meta": {"proxy": proxy.credentials.as_line(), "exit_ip": ""},
            "results": [],
            "error": proc.stderr[-2000:] if proc.stderr else "empty worker output",
        }
    if proc.returncode != 0 and isinstance(result, dict):
        result["ok"] = False
    return worker, result if isinstance(result, dict) else {"ok": False, "results": []}, proc.returncode


def run_waves(
    *,
    limit: int | None = None,
    concurrency: int | None = None,
    batch_size: int | None = None,
    image: str | None = None,
    category_dir: str = "flancki_need_enrich",
) -> int:
    concurrency = concurrency if concurrency is not None else config.WORKER_CONCURRENCY
    batch_size = batch_size if batch_size is not None else config.WORKER_BATCH_SIZE
    image = image or config.WORKER_IMAGE

    courses = select_course_json_files(
        config.CATALOG_ROOT,
        limit=limit,
        newest_first=True,
        category_dirs={category_dir},
    )
    proxies = load_working_proxies(config.PROXIES_PATH)
    if not courses:
        print(f"no courses in {category_dir}")
        return 0
    if not proxies:
        raise RuntimeError(f"no working proxies in {config.PROXIES_PATH}")

    runs_root = config.CATALOG_ROOT / ".worker_runs" / uuid.uuid4().hex
    runs_root.mkdir(parents=True, exist_ok=True)
    done = 0
    wave_no = 0
    remaining_courses = list(courses)
    remaining_proxies = list(proxies)

    while remaining_courses and remaining_proxies:
        wave = take_wave(
            remaining_courses,
            remaining_proxies,
            concurrency=concurrency,
            batch_size=batch_size,
        )
        if not wave:
            break
        wave_no += 1
        print(f"wave {wave_no}: {len(wave)} container(s)")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(wave)) as pool:
            futs = [
                pool.submit(
                    _run_one_container,
                    image=image,
                    proxy=w.proxy,
                    paths=w.paths,
                    run_dir=runs_root / f"w{wave_no}_{i}",
                )
                for i, w in enumerate(wave)
            ]
            for fut in concurrent.futures.as_completed(futs):
                worker, result, code = fut.result()
                persist_results(result, config.CATALOG_ROOT)
                done += len(worker.paths)
                if code != 0 or not result.get("ok", False):
                    err = str(result.get("error") or f"docker exit {code}")
                    mark_proxy_failed(
                        config.PROXIES_PATH,
                        worker.proxy.id,
                        err,
                    )
                    print(
                        f"  proxy {worker.proxy.id} failed: {err[:200]}"
                    )
                else:
                    print(
                        f"  proxy {worker.proxy.id} ok exit_ip={result.get('meta', {}).get('exit_ip')}"
                    )

    print(f"orchestrator done courses={done} runs={runs_root}")
    return done


def main() -> None:
    limit = config.env_int("ENRICH_LIMIT") or config.env_int("WORKER_COURSE_LIMIT")
    run_waves(limit=limit)


if __name__ == "__main__":
    main()
