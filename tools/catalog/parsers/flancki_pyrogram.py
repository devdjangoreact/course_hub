"""Download Telegram Flancki posts → flancki_posts.json (credentials from .env)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyrogram import Client

import config

URL_RE = re.compile(r"https?://[^\s<>\"']+")
BATCH_SIZE = 100


def phone_dir_name(phone: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if not cleaned:
        raise SystemExit("Invalid TG_PHONE")
    return cleaned


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_courses(text: str) -> list[dict[str, str]]:
    courses: list[dict[str, str]] = []
    if not text or not text.strip():
        return courses
    for block in re.split(r"\n\s*\n", text.strip()):
        title_parts: list[str] = []
        links: list[str] = []
        for raw in block.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.lower().startswith("пароль"):
                continue
            urls = URL_RE.findall(line)
            if urls:
                links.extend(urls)
            else:
                title_parts.append(line)
        title = " ".join(title_parts).strip()
        if not links:
            continue
        for link in links:
            courses.append({"title": title, "link": link.rstrip(").,;]")})
    return courses


def enrich_post(row: dict) -> dict:
    row["courses"] = parse_courses(row.get("text") or "")
    return row


def export_paths(chat_id: int) -> tuple[Path, Path, Path]:
    root = config.REPO_ROOT / "data" / "telegram_exports" / str(chat_id)
    return root, root / "flancki_posts.json", root / "flancki_posts.jsonl"


def load_posts(posts_path: Path, jsonl_path: Path) -> list[dict]:
    posts: list[dict] = []
    if posts_path.exists():
        data = json.loads(posts_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            posts = data
        elif isinstance(data, dict) and isinstance(data.get("posts"), list):
            posts = data["posts"]
    elif jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    posts.append(json.loads(line))
        print(f"Migrated {len(posts)} posts from {jsonl_path.name}")
    for row in posts:
        enrich_post(row)
    return posts


def save_posts(export_root: Path, posts_path: Path, posts: list[dict]) -> None:
    export_root.mkdir(parents=True, exist_ok=True)
    ordered = sorted(posts, key=lambda p: int(p.get("id") or 0), reverse=True)
    posts_path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def range_from_posts(posts: list[dict]) -> tuple[int, int, datetime | None]:
    min_id = 0
    max_id = 0
    oldest: datetime | None = None
    for row in posts:
        msg_id = int(row.get("id") or 0)
        if not msg_id:
            continue
        if max_id == 0 or msg_id > max_id:
            max_id = msg_id
        if min_id == 0 or msg_id < min_id:
            min_id = msg_id
            oldest = ensure_utc(datetime.fromisoformat(row["date"])) if row.get("date") else None
    return min_id, max_id, oldest


def has_post_today(posts: list[dict]) -> bool:
    today = datetime.now(timezone.utc).date()
    for row in posts:
        raw = row.get("date")
        if not raw:
            continue
        dt = ensure_utc(datetime.fromisoformat(raw))
        if dt and dt.date() == today:
            return True
    return False


def message_to_row(message, chat_id: int, media_rel: str | None) -> dict:
    text = message.text or message.caption or ""
    return enrich_post(
        {
            "id": message.id,
            "date": message.date.isoformat() if message.date else None,
            "chat_id": message.chat.id if message.chat else chat_id,
            "from_user_id": message.from_user.id if message.from_user else None,
            "text": text,
            "courses": [],
            "media_type": str(message.media) if message.media else None,
            "media_file": media_rel,
            "views": message.views,
            "forwards": message.forwards,
            "reply_to_message_id": message.reply_to_message_id,
        }
    )


def before_cutoff(message, cutoff: datetime) -> bool:
    msg_date = ensure_utc(message.date)
    return msg_date is not None and msg_date < cutoff


def download_media_safe(app: Client, message, media_dir: Path, out_dir: Path) -> str | None:
    if not config.TG_DOWNLOAD_MEDIA or not message.media:
        return None
    try:
        path = app.download_media(message, file_name=str(media_dir / f"{message.id}_"))
    except ValueError:
        return None
    if not path:
        return None
    return str(Path(path).relative_to(out_dir)).replace("\\", "/")


def run_parse() -> Path:
    if not config.TG_API_ID or not config.TG_API_HASH:
        raise SystemExit("Set TG_API_ID and TG_API_HASH in .env")
    if not config.TG_PHONE:
        raise SystemExit("Set TG_PHONE in .env")

    chat_id = int(config.TG_FLANCKI_CHAT_ID)
    export_root, posts_path, jsonl_path = export_paths(chat_id)
    posts = load_posts(posts_path, jsonl_path)
    by_id = {int(p["id"]): p for p in posts if p.get("id") is not None}
    min_id, max_id, oldest = range_from_posts(posts)
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * config.TG_PARSE_YEARS)

    if posts:
        save_posts(export_root, posts_path, list(by_id.values()))
        courses_n = sum(len(p.get("courses") or []) for p in by_id.values())
        print(f"Saved JSON: {len(by_id)} posts, {courses_n} courses -> {posts_path}")

    if has_post_today(list(by_id.values())):
        print("Post from today already saved — skip Telegram download")
        return posts_path

    phone = phone_dir_name(config.TG_PHONE)
    workdir = config.SESSIONS_ROOT / phone
    session_file = workdir / "account.session"
    if not session_file.exists():
        raise SystemExit(f"No session: {session_file}. Run scripts/create_pyrogram_session.py first.")

    media_dir = export_root / "media"
    export_root.mkdir(parents=True, exist_ok=True)
    if config.TG_DOWNLOAD_MEDIA:
        media_dir.mkdir(parents=True, exist_ok=True)

    app = Client(
        name="account",
        api_id=config.TG_API_ID,
        api_hash=config.TG_API_HASH,
        workdir=str(workdir),
    )

    saved = 0
    pending = 0

    def flush() -> None:
        nonlocal pending
        if pending == 0:
            return
        save_posts(export_root, posts_path, list(by_id.values()))
        print(f"... {saved} new posts flushed (min={min_id} max={max_id})")
        pending = 0

    def write_one(message) -> None:
        nonlocal saved, min_id, max_id, pending
        if message.id in by_id:
            return
        media_rel = download_media_safe(app, message, media_dir, export_root)
        row = message_to_row(message, chat_id, media_rel)
        by_id[message.id] = row
        saved += 1
        pending += 1
        if max_id == 0 or message.id > max_id:
            max_id = message.id
        if min_id == 0 or message.id < min_id:
            min_id = message.id
        if pending >= BATCH_SIZE:
            flush()

    with app:
        if max_id:
            print(f"Fetch newer than id={max_id}")
            for message in app.get_chat_history(chat_id):
                if message.id <= max_id:
                    break
                write_one(message)

        if not max_id:
            print("Full download (newest → cutoff)")
            for message in app.get_chat_history(chat_id):
                if before_cutoff(message, cutoff):
                    break
                write_one(message)
        elif oldest is None or oldest > cutoff:
            print(f"Continue older from id<{min_id} until {cutoff.date()}")
            for message in app.get_chat_history(chat_id, offset_id=min_id):
                if before_cutoff(message, cutoff):
                    break
                write_one(message)
        flush()

    print(f"OK: +{saved} posts -> {posts_path}")
    return posts_path


if __name__ == "__main__":
    run_parse()
