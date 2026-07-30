"""Create a Pyrogram user session from `.env` (TG_API_ID, TG_API_HASH, TG_PHONE).

Saves files to: sessions_parogram/<phone>/

  python scripts/create_pyrogram_session.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pyrogram import Client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "catalog"))

import config


def phone_dir_name(phone: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if not cleaned:
        raise SystemExit("Invalid TG_PHONE in .env")
    return cleaned


def main() -> None:
    if not config.TG_API_ID or not config.TG_API_HASH:
        raise SystemExit("Set TG_API_ID and TG_API_HASH in .env")
    if not config.TG_PHONE:
        raise SystemExit("Set TG_PHONE in .env")

    phone = phone_dir_name(config.TG_PHONE)
    workdir = config.SESSIONS_ROOT / phone
    workdir.mkdir(parents=True, exist_ok=True)

    app = Client(
        name="account",
        api_id=config.TG_API_ID,
        api_hash=config.TG_API_HASH,
        phone_number=phone,
        workdir=str(workdir),
    )
    with app:
        me = app.get_me()
        print(f"OK: {workdir} as @{me.username or me.id}")


if __name__ == "__main__":
    main()
