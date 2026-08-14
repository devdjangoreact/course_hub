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


def _bot_call(
    method: str, payload: dict[str, Any], *, token: str | None = None
) -> dict[str, Any]:
    bot_token = (token or config.BOT_TOKEN or "").strip()
    if not bot_token:
        raise SystemExit("Set BOT_TOKEN in .env")
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
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
                    "text": "Заказать",
                    "url": f"https://t.me/{bot_username}?start=course_{slug}",
                }
            ]
        ]
    }


def _message_payload(text: str, markup: dict[str, Any], *, chat_id: int) -> dict[str, Any]:
    return {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": markup,
    }


_TG_TEXT_LIMIT = 4096


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


def _channel_post_text(promo_text: str, full_text: str) -> str:
    """One channel message: promo plus expandable 'Детально' (no second post)."""
    promo = promo_text.strip()
    full = (
        full_text.strip()
        .replace("</blockquote>", "")
        .replace("<blockquote expandable>", "")
        .replace("<blockquote>", "")
    )
    if not full or full == promo:
        return promo
    inner = f"<b>Детально</b>\n\n{full}"
    wrapper = "\n\n<blockquote expandable></blockquote>"
    room = _TG_TEXT_LIMIT - len(promo) - len(wrapper)
    if room < 40:
        return promo
    if len(inner) > room:
        inner = inner[: room - 1].rstrip() + "…"
    return f"{promo}\n\n<blockquote expandable>{inner}</blockquote>"


def _message_url(channel_id: Any, message_id: int) -> str:
    """Private/public channel post link: https://t.me/c/<id>/<message_id>."""
    cid = int(channel_id)
    raw = str(cid)
    # Supergroup/channel ids look like -100xxxxxxxxxx → t.me/c/xxxxxxxxxx/N
    internal = raw[4:] if raw.startswith("-100") else str(abs(cid))
    return f"https://t.me/c/{internal}/{int(message_id)}"


def _with_post_urls(telegram: dict[str, Any]) -> dict[str, Any]:
    channel_id = telegram.get("channel_id")
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


def send_catalog_post(
    *,
    token: str,
    chat_id: int,
    bot_username: str,
    course_data: dict[str, Any],
    invite_link: str = "",
    discussion_group_id: int | None = None,
    existing: dict[str, Any] | None = None,
    force: bool = False,
) -> tuple[dict[str, Any], bool]:
    """One expandable channel message. Skip send if this chat already has promo ids."""
    existing = dict(existing or {})
    promo_text, full_text = _promo_and_full_texts(course_data)
    post_text = _channel_post_text(promo_text, full_text)
    slug = str(course_data.get("slug") or "")
    markup = _order_markup(bot_username, slug)
    payload = _message_payload(post_text, markup, chat_id=chat_id)
    promo_ids = [int(x) for x in (existing.get("promo_message_ids") or [])]
    posted_chat = existing.get("channel_id")
    same_chat = posted_chat is not None and int(posted_chat) == int(chat_id)
    if promo_ids and same_chat and not force:
        for message_id in promo_ids:
            try:
                _bot_call(
                    "editMessageText",
                    {**payload, "message_id": message_id},
                    token=token,
                )
            except RuntimeError as exc:
                if "message is not modified" not in str(exc):
                    raise
        telegram = _with_post_urls(
            {
                **existing,
                "channel_id": chat_id,
                "discussion_group_id": discussion_group_id
                if discussion_group_id is not None
                else existing.get("discussion_group_id"),
                "invite_link": invite_link or existing.get("invite_link"),
                "promo_message_ids": promo_ids,
                "full_message_ids": [],
            }
        )
        return telegram, False

    sent = _bot_call("sendMessage", payload, token=token)
    telegram = _with_post_urls(
        {
            "channel_id": chat_id,
            "discussion_group_id": discussion_group_id,
            "invite_link": invite_link or None,
            "promo_message_ids": [int(sent["message_id"])],
            "full_message_ids": [],
        }
    )
    return telegram, True


def post_course(path: Path, *, bot_username: str, force: bool = False) -> bool:
    if config.CATALOG_CHANNEL_ID is None:
        raise SystemExit("Set CATALOG_CHANNEL_ID in .env")
    data = load_course(path)
    telegram, posted = send_catalog_post(
        token=config.BOT_TOKEN,
        chat_id=int(config.CATALOG_CHANNEL_ID),
        bot_username=bot_username,
        course_data=data,
        invite_link=config.CATALOG_INVITE_LINK or "",
        discussion_group_id=config.CATALOG_DISCUSSION_GROUP_ID,
        existing=data.get("telegram") or {},
        force=force,
    )
    promo_text, full_text = _promo_and_full_texts(data)
    saved = _save_public_state(path, data, telegram, promo_text, full_text)
    _print_post_links(path, saved, action="posted" if posted else "updated already posted")
    return posted


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
