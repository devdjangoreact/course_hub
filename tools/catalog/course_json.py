from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_course(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_course(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def iter_course_json_files(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("categories/*/*.json") if p.is_file())


def select_course_json_files(
    root: Path,
    *,
    limit: int | None = None,
    post_ids: set[int] | None = None,
    newest_first: bool = True,
) -> list[Path]:
    files = iter_course_json_files(root)
    files = [path for path in files if path.parent.name != "test"]
    files.sort(key=lambda path: path.name, reverse=newest_first)
    if post_ids:
        files = [
            path
            for path in files
            if (post_id := _post_id_from_filename(path)) is not None and post_id in post_ids
        ]
    return files[:limit] if limit is not None else files


def _post_id_from_filename(path: Path) -> int | None:
    parts = path.stem.split("_")
    if len(parts) >= 3 and parts[1].isdigit():
        return int(parts[1])
    return None
