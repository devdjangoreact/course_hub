"""Post enriched course JSON to the catalog channel via BotFather BOT_TOKEN."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import config
from course_json import load_course, save_course, select_course_json_files

# Default folder after SearXNG enrich (publication-ready).
DEFAULT_POST_CATEGORY = "flancki"
_BOT_429_RETRIES = 5


def _retry_after_seconds(detail: str, fallback: float = 5.0) -> float:
    try:
        data = json.loads(detail)
        raw = (data.get("parameters") or {}).get("retry_after")
        if raw is not None:
            return max(float(raw), 1.0)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return fallback


def _bot_call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not config.BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in .env")
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/{method}"
    data = json.dumps(payload).encode("utf-8")
    last_detail = ""
    for attempt in range(_BOT_429_RETRIES + 1):
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < _BOT_429_RETRIES:
                wait = _retry_after_seconds(last_detail)
                print(f"  Telegram 429 on {method}; sleep {wait:.0f}s then retry")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Telegram Bot API {method} failed: {last_detail}") from exc
        if not body.get("ok"):
            if body.get("error_code") == 429 and attempt < _BOT_429_RETRIES:
                wait = _retry_after_seconds(json.dumps(body))
                print(f"  Telegram 429 on {method}; sleep {wait:.0f}s then retry")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Telegram Bot API {method} error: {body}")
        return body["result"]
    raise RuntimeError(f"Telegram Bot API {method} failed: {last_detail}")


def _public_text(text: str, download_link: str) -> str:
    return text.replace(download_link, "").rstrip() if download_link else text.rstrip()


def _order_markup(bot_username: str, slug: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Замовити",
                    "url": f"https://t.me/{bot_username}?start=course_{slug}",
                }
            ]
        ]
    }


def _message_payload(text: str, markup: dict[str, Any]) -> dict[str, Any]:
    return {
        "chat_id": config.CATALOG_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": markup,
    }


def _promo_and_full_texts(data: dict[str, Any]) -> tuple[str, str]:
    """Prefer enrich `telegram_post` for the promo message; keep full_description."""
    download_link = str(data.get("download_link") or "")
    telegram_post = str(data.get("telegram_post") or "").strip()
    promo_raw = telegram_post or str((data.get("promo") or {}).get("text") or "")
    full_raw = str(data.get("full_description") or "").strip() or promo_raw
    return (
        _public_text(promo_raw, download_link),
        _public_text(full_raw, download_link),
    )


def _message_url(channel_id: Any, message_id: int) -> str:
    """Private/public channel post link: https://t.me/c/<id>/<message_id>."""
    cid = int(channel_id)
    raw = str(cid)
    # Supergroup/channel ids look like -100xxxxxxxxxx → t.me/c/xxxxxxxxxx/N
    internal = raw[4:] if raw.startswith("-100") else str(abs(cid))
    return f"https://t.me/c/{internal}/{int(message_id)}"


def _with_post_urls(telegram: dict[str, Any]) -> dict[str, Any]:
    channel_id = telegram.get("channel_id") or config.CATALOG_CHANNEL_ID
    promo_ids = [int(x) for x in (telegram.get("promo_message_ids") or [])]
    full_ids = [int(x) for x in (telegram.get("full_message_ids") or [])]
    promo_urls = [_message_url(channel_id, mid) for mid in promo_ids] if channel_id else []
    full_urls = [_message_url(channel_id, mid) for mid in full_ids] if channel_id else []
    return {
        **telegram,
        "promo_post_urls": promo_urls,
        "full_post_urls": full_urls,
        "promo_post_url": promo_urls[0] if promo_urls else None,
        "full_post_url": full_urls[0] if full_urls else None,
    }


def _print_post_links(path: Path, telegram: dict[str, Any], *, action: str) -> None:
    print(f"{action} {path.name}")
    for label, key in (("promo", "promo_post_url"), ("full", "full_post_url")):
        url = telegram.get(key)
        if url:
            print(f"  {label}: {url}")


def _save_public_state(
    path: Path,
    data: dict[str, Any],
    telegram: dict[str, Any],
    promo_text: str,
    full_text: str,
) -> dict[str, Any]:
    telegram = _with_post_urls(telegram)
    data["promo"] = {**(data.get("promo") or {}), "text": promo_text}
    data["full_description"] = full_text
    data["telegram"] = {**telegram, "public_text_sanitized": True}
    save_course(path, data)
    return data["telegram"]


def post_course(path: Path, *, bot_username: str, force: bool = False) -> bool:
    if config.CATALOG_CHANNEL_ID is None:
        raise SystemExit("Set CATALOG_CHANNEL_ID in .env")
    data = load_course(path)
    telegram = data.get("telegram") or {}
    promo_text, full_text = _promo_and_full_texts(data)
    markup = _order_markup(bot_username, str(data["slug"]))
    if telegram.get("promo_message_ids") and not force:
        existing_messages = [
            *((message_id, promo_text) for message_id in telegram["promo_message_ids"]),
            *((message_id, full_text) for message_id in telegram.get("full_message_ids") or []),
        ]
        for message_id, text in existing_messages:
            try:
                _bot_call(
                    "editMessageText",
                    {**_message_payload(text, markup), "message_id": message_id},
                )
            except RuntimeError as exc:
                if "message is not modified" not in str(exc):
                    raise
        if not telegram.get("full_message_ids"):
            full = _bot_call("sendMessage", _message_payload(full_text, markup))
            telegram["full_message_ids"] = [full["message_id"]]
        if not telegram.get("channel_id"):
            telegram["channel_id"] = config.CATALOG_CHANNEL_ID
        saved = _save_public_state(path, data, telegram, promo_text, full_text)
        _print_post_links(path, saved, action="updated already posted")
        return False

    telegram = {
        **telegram,
        "channel_id": config.CATALOG_CHANNEL_ID,
        "discussion_group_id": config.CATALOG_DISCUSSION_GROUP_ID,
        "invite_link": config.CATALOG_INVITE_LINK or None,
        "promo_message_ids": list(telegram.get("promo_message_ids") or []),
        "full_message_ids": list(telegram.get("full_message_ids") or []),
    }
    promo = _bot_call(
        "sendMessage",
        _message_payload(promo_text, markup),
    )
    telegram["promo_message_ids"] = list(
        dict.fromkeys([*telegram["promo_message_ids"], promo["message_id"]])
    )
    _save_public_state(path, data, telegram, promo_text, full_text)
    full = _bot_call(
        "sendMessage",
        _message_payload(full_text, markup),
    )
    telegram["full_message_ids"] = list(
        dict.fromkeys([*telegram["full_message_ids"], full["message_id"]])
    )
    saved = _save_public_state(path, data, telegram, promo_text, full_text)
    _print_post_links(path, saved, action="posted")
    return True


def post_all(
    *,
    paths: list[Path] | None = None,
    limit: int | None = None,
    post_ids: set[int] | None = None,
    newest_first: bool = True,
    force: bool = False,
    category_dirs: set[str] | None = None,
) -> int:
    files = (
        paths
        if paths is not None
        else select_course_json_files(
            config.CATALOG_ROOT,
            limit=limit,
            post_ids=post_ids,
            newest_first=newest_first,
            category_dirs=category_dirs or {DEFAULT_POST_CATEGORY},
        )
    )
    if not files:
        return 0
    bot_username = str(_bot_call("getMe", {}).get("username") or "").lstrip("@")
    if not bot_username:
        raise RuntimeError("Telegram Bot API getMe returned no username")
    posted = 0
    for i, path in enumerate(files):
        if i:
            time.sleep(1.2)  # stay under Bot API flood limits across a batch
        posted += int(post_course(path, bot_username=bot_username, force=force))
    return posted


if __name__ == "__main__":
    post_all()
