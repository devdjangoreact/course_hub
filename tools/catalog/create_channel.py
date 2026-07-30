"""Deprecated for BotFather flow: create the private channel manually in Telegram,
add the bot as admin, then set CATALOG_CHANNEL_ID / CATALOG_INVITE_LINK in `.env`.
"""

from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "create_channel.py is not used with BotFather. "
        "Create the channel manually, add the bot as admin, "
        "set BOT_TOKEN, CATALOG_CHANNEL_ID, CATALOG_INVITE_LINK in .env"
    )


if __name__ == "__main__":
    main()
