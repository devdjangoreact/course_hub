"""Post promo + full description via BotFather BOT_TOKEN (Bot API)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from course_json import load_course, save_course, select_course_json_files


def _bot_call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not config.BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in .env")
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/{method}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram Bot API {method} failed: {detail}") from exc
    if not body.get("ok"):
        raise RuntimeError(f"Telegram Bot API {method} error: {body}")
    return body["result"]


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


def _save_public_state(
    path: Path,
    data: dict[str, Any],
    telegram: dict[str, Any],
    promo_text: str,
    full_text: str,
) -> None:
    data["promo"] = {**(data.get("promo") or {}), "text": promo_text}
    data["full_description"] = full_text
    data["telegram"] = {**telegram, "public_text_sanitized": True}
    save_course(path, data)


def post_course(path: Path, *, bot_username: str, force: bool = False) -> bool:
    if config.CATALOG_CHANNEL_ID is None:
        raise SystemExit("Set CATALOG_CHANNEL_ID in .env")
    data = load_course(path)
    telegram = data.get("telegram") or {}
    download_link = str(data.get("download_link") or "")
    promo_text = _public_text(str((data.get("promo") or {}).get("text") or ""), download_link)
    full_text = _public_text(str(data.get("full_description") or ""), download_link)
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
        _save_public_state(path, data, telegram, promo_text, full_text)
        print("updated already posted", path.name)
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
    _save_public_state(path, data, telegram, promo_text, full_text)
    print("posted", path.name)
    return True


def post_all(
    *,
    paths: list[Path] | None = None,
    limit: int | None = None,
    post_ids: set[int] | None = None,
    newest_first: bool = True,
    force: bool = False,
) -> int:
    files = (
        paths
        if paths is not None
        else select_course_json_files(
            config.CATALOG_ROOT,
            limit=limit,
            post_ids=post_ids,
            newest_first=newest_first,
        )
    )
    if not files:
        return 0
    bot_username = str(_bot_call("getMe", {}).get("username") or "").lstrip("@")
    if not bot_username:
        raise RuntimeError("Telegram Bot API getMe returned no username")
    return sum(post_course(path, bot_username=bot_username, force=force) for path in files)


if __name__ == "__main__":
    post_all()
