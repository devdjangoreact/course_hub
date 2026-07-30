"""Upsert catalog JSON into Course Hub DB. Local only."""

from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import config
from course_json import load_course, select_course_json_files
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.entities.category import Category
from app.domain.entities.course import Course
from app.infrastructure.db.repositories.category_repository import SqlCategoryRepository
from app.infrastructure.db.repositories.course_repository import SqlCourseRepository


async def sync_one(session, data: dict) -> None:
    categories = SqlCategoryRepository(session)
    courses = SqlCourseRepository(session)
    cat_title = data["category"]["title"]
    category = await categories.get_by_name(cat_title)
    if category is None:
        category = await categories.add(
            Category(
                id=None,
                name=cat_title,
                extra={"catalog_slug": data["category"]["slug"]},
            )
        )
    slug = data["slug"]
    download = data["download_link"]
    description = str(data["short_description"]).replace(download, "").rstrip()
    tg = data.get("telegram") or {}
    extra = {
        "catalog_slug": slug,
        "download_link": download,
        "invite_link": tg.get("invite_link") or config.CATALOG_INVITE_LINK or None,
        "channel_id": tg.get("channel_id") or config.CATALOG_CHANNEL_ID,
        "promo_message_ids": tg.get("promo_message_ids") or [],
        "full_message_ids": tg.get("full_message_ids") or [],
        "public_text_sanitized": bool(tg.get("public_text_sanitized")),
        "original_url": data.get("original_url"),
        "year": data.get("year"),
        "tags": data.get("tags") or [],
        "authors": data.get("authors") or [],
        "links": data.get("links") or [],
    }
    existing = await courses.get_by_catalog_slug(slug)
    if existing is None:
        assert category.id is not None
        await courses.add(
            Course(
                id=None,
                name=data["title"],
                description=description,
                category_id=category.id,
                price=Decimal(str(data["price"])),
                link=download,
                is_active=True,
                extra=extra,
            )
        )
        return
    existing.name = data["title"]
    existing.description = description
    existing.price = Decimal(str(data["price"]))
    existing.link = download
    existing.extra = {**existing.extra, **extra}
    await courses.update(existing)


def _async_database_url(url: str) -> str:
    if url.startswith(("postgresql+asyncpg://", "sqlite+")):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    return url


async def main(
    *,
    paths: list[Path] | None = None,
    limit: int | None = None,
    post_ids: set[int] | None = None,
    newest_first: bool = True,
) -> int:
    database_url = config.DATABASE_URL or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL in .env")
    engine = create_async_engine(_async_database_url(database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
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
    async with session_factory() as session:
        for path in files:
            await sync_one(session, load_course(path))
            print("synced", path.name)
        await session.commit()
    await engine.dispose()
    return len(files)


if __name__ == "__main__":
    asyncio.run(main())
