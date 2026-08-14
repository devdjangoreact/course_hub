"""Import bots / channels / courses / channel_courses from JSON into the DB.

Usage:
  python scripts/import_telegram_catalog.py path/to/data.json
  python scripts/import_telegram_catalog.py path/to/data.json --dry-run

Uses DATABASE_URL from the environment / .env (local or production).
Bot username is always resolved via Telegram getMe (never taken from JSON).

See scripts/telegram_catalog.example.json for the schema.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger
from sqlalchemy import select

from app.bot.telegram_identity import fetch_bot_username
from app.core.config import get_settings
from app.core.database import Database
from app.domain.entities.course import Course
from app.domain.entities.telegram_bot import TelegramBot
from app.domain.entities.telegram_channel import TelegramChannel
from app.infrastructure.db.models.channel_course import ChannelCourseModel
from app.infrastructure.db.models.course import CourseModel
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository
from app.infrastructure.db.repositories.telegram_bot_repository import SqlTelegramBotRepository
from app.infrastructure.db.repositories.telegram_channel_repository import (
    SqlTelegramChannelRepository,
)


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    return bool(value)


def _as_extra(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


async def _find_course(
    session, *, stable_key: str, name: str, category_id: int, link: str
) -> Course | None:
    from app.infrastructure.db.repositories.course_repository import _to_entity

    if stable_key:
        stmt = select(CourseModel).where(CourseModel.extra["stable_key"].as_string() == stable_key)
        model = (await session.execute(stmt)).scalar_one_or_none()
        if model is not None:
            return _to_entity(model)
    stmt = select(CourseModel).where(
        CourseModel.name == name,
        CourseModel.category_id == category_id,
        CourseModel.link == link,
    )
    model = (await session.execute(stmt)).scalar_one_or_none()
    return _to_entity(model) if model is not None else None


async def _upsert_course(session, raw: dict[str, Any], *, dry_run: bool) -> Course:
    name = str(raw["name"]).strip()
    description = str(raw.get("description") or "")
    category_id = int(raw["category_id"])
    price = Decimal(str(raw["price"]))
    link = str(raw.get("link") or "")
    is_active = _as_bool(raw.get("is_active"), True)
    extra = _as_extra(raw.get("extra"))
    stable_key = str(raw.get("stable_key") or extra.get("stable_key") or "").strip()
    if stable_key:
        extra = {**extra, "stable_key": stable_key}

    existing = await _find_course(
        session, stable_key=stable_key, name=name, category_id=category_id, link=link
    )
    courses = SqlCourseRepository(session)
    if existing is None:
        course = Course(
            id=None,
            name=name,
            description=description,
            category_id=category_id,
            price=price,
            link=link,
            is_active=is_active,
            extra=extra,
        )
        if dry_run:
            logger.info("DRY-RUN create course name={!r} category_id={}", name, category_id)
            return course
        saved = await courses.add(course)
        logger.info("Created course id={} name={!r}", saved.id, saved.name)
        return saved

    existing.name = name
    existing.description = description
    existing.category_id = category_id
    existing.price = price
    existing.link = link
    existing.is_active = is_active
    existing.extra = {**existing.extra, **extra}
    if dry_run:
        logger.info("DRY-RUN update course id={} name={!r}", existing.id, name)
        return existing
    saved = await courses.update(existing)
    logger.info("Updated course id={} name={!r}", saved.id, saved.name)
    return saved


async def _ensure_channel_course(
    session, *, channel_id: int, course_id: int, extra: dict[str, Any], dry_run: bool
) -> None:
    stmt = select(ChannelCourseModel).where(
        ChannelCourseModel.channel_id == channel_id,
        ChannelCourseModel.course_id == course_id,
    )
    model = (await session.execute(stmt)).scalar_one_or_none()
    if model is not None:
        model.extra = {**dict(model.extra), **extra}
        logger.info("Channel-course link exists channel_id={} course_id={}", channel_id, course_id)
        return
    if dry_run:
        logger.info("DRY-RUN link channel_id={} course_id={}", channel_id, course_id)
        return
    session.add(
        ChannelCourseModel(channel_id=channel_id, course_id=course_id, extra=extra)
    )
    await session.flush()
    logger.info("Linked channel_id={} course_id={}", channel_id, course_id)


async def _upsert_bot(session, raw: dict[str, Any], *, dry_run: bool) -> TelegramBot:
    token = str(raw["token"]).strip()
    username = await fetch_bot_username(token)
    bots = SqlTelegramBotRepository(session)
    existing = await bots.get_by_token(token)
    if existing is None:
        existing = await bots.get_by_username(username)

    bot = TelegramBot(
        id=existing.id if existing else None,
        username=username,
        token=token,
        webhook_secret=str(raw.get("webhook_secret") or (existing.webhook_secret if existing else "")),
        is_active=_as_bool(raw.get("is_active"), True),
        title=str(raw.get("title") or (existing.title if existing else "") or username),
        notes=str(raw.get("notes") or (existing.notes if existing else "")),
        extra={**(existing.extra if existing else {}), **_as_extra(raw.get("extra"))},
    )
    if dry_run:
        logger.info(
            "DRY-RUN {} bot @{} token=…{}",
            "update" if existing else "create",
            username,
            token[-6:],
        )
        return bot
    saved = await bots.save(bot)
    logger.info("{} bot id={} @{}", "Updated" if existing else "Created", saved.id, saved.username)
    return saved


async def _upsert_channel(
    session, bot_id: int, raw: dict[str, Any], *, dry_run: bool
) -> TelegramChannel:
    chat_id = int(raw["telegram_chat_id"])
    channels = SqlTelegramChannelRepository(session)
    existing = await channels.get_by_bot_and_chat(bot_id, chat_id)
    channel = TelegramChannel(
        id=existing.id if existing else None,
        bot_id=bot_id,
        telegram_chat_id=chat_id,
        discussion_group_id=(
            int(raw["discussion_group_id"])
            if raw.get("discussion_group_id") is not None
            else (existing.discussion_group_id if existing else None)
        ),
        is_public=_as_bool(raw.get("is_public"), False),
        discussion_is_public=_as_bool(raw.get("discussion_is_public"), False),
        invite_link=str(raw.get("invite_link") or (existing.invite_link if existing else "")),
        discussion_invite_link=str(
            raw.get("discussion_invite_link")
            or (existing.discussion_invite_link if existing else "")
        ),
        title=str(raw.get("title") or (existing.title if existing else "")),
        slug=str(raw.get("slug") or (existing.slug if existing else "")),
        is_active=_as_bool(raw.get("is_active"), True),
        extra={**(existing.extra if existing else {}), **_as_extra(raw.get("extra"))},
    )
    if dry_run:
        logger.info(
            "DRY-RUN {} channel chat_id={} bot_id={}",
            "update" if existing else "create",
            chat_id,
            bot_id,
        )
        return channel
    saved = await channels.save(channel)
    logger.info(
        "{} channel id={} chat_id={}",
        "Updated" if existing else "Created",
        saved.id,
        saved.telegram_chat_id,
    )
    return saved


async def import_payload(payload: dict[str, Any], *, dry_run: bool) -> None:
    settings = get_settings()
    database = Database(settings)
    bots_raw = payload.get("bots")
    if not isinstance(bots_raw, list):
        raise ValueError("JSON root must contain a 'bots' array")

    async with database.session_factory() as session:
        for bot_raw in bots_raw:
            if not isinstance(bot_raw, dict) or not bot_raw.get("token"):
                raise ValueError("Each bot requires a non-empty token")
            # username in JSON is ignored (must come from Telegram)
            if "username" in bot_raw:
                logger.warning("Ignoring JSON username={!r}; using Telegram getMe", bot_raw.get("username"))

            bot = await _upsert_bot(session, bot_raw, dry_run=dry_run)
            if bot.id is None and dry_run:
                # cannot nest real FK ids in dry-run without DB rows
                logger.info("DRY-RUN skip nested channels for unresolved bot id")
                continue
            assert bot.id is not None

            for channel_raw in bot_raw.get("channels") or []:
                if not isinstance(channel_raw, dict):
                    raise ValueError("channel entries must be objects")
                channel = await _upsert_channel(session, bot.id, channel_raw, dry_run=dry_run)
                if channel.id is None and dry_run:
                    logger.info("DRY-RUN skip courses for unresolved channel")
                    continue
                assert channel.id is not None

                for course_raw in channel_raw.get("courses") or []:
                    if not isinstance(course_raw, dict):
                        raise ValueError("course entries must be objects")
                    course = await _upsert_course(session, course_raw, dry_run=dry_run)
                    if course.id is None and dry_run:
                        continue
                    assert course.id is not None
                    await _ensure_channel_course(
                        session,
                        channel_id=channel.id,
                        course_id=course.id,
                        extra=_as_extra(course_raw.get("link_extra")),
                        dry_run=dry_run,
                    )

        if dry_run:
            await session.rollback()
            logger.info("DRY-RUN complete (rolled back)")
        else:
            await session.commit()
            logger.info("Import committed")

    await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path, help="Path to import JSON")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve getMe / validate and log actions without committing",
    )
    args = parser.parse_args()
    path: Path = args.json_path
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("JSON root must be an object")
    asyncio.run(import_payload(payload, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
