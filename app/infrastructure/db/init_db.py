from sqlalchemy import text

from app.core.config import Settings
from app.core.database import Database
from app.infrastructure.db import models  # noqa: F401  (register models on Base)
from app.infrastructure.db.base import Base

# Columns added after initial deploy; SQLite create_all does not alter existing tables.
_SQLITE_COLUMN_PATCHES: dict[str, dict[str, str]] = {
    "bot_users": {
        "preferred_language": "VARCHAR NOT NULL DEFAULT 'uk'",
    },
}


async def _apply_sqlite_column_patches(conn) -> None:
    for table_name, columns in _SQLITE_COLUMN_PATCHES.items():
        result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
        rows = result.fetchall()
        if not rows:
            continue
        existing = {row[1] for row in rows}
        for column_name, column_ddl in columns.items():
            if column_name not in existing:
                await conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}")
                )


_FTS_STATEMENTS = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS courses_fts
    USING fts5(name, description, content='courses', content_rowid='id')
    """,
    """
    CREATE TRIGGER IF NOT EXISTS courses_ai AFTER INSERT ON courses BEGIN
        INSERT INTO courses_fts(rowid, name, description)
        VALUES (new.id, new.name, new.description);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS courses_ad AFTER DELETE ON courses BEGIN
        INSERT INTO courses_fts(courses_fts, rowid, name, description)
        VALUES ('delete', old.id, old.name, old.description);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS courses_au AFTER UPDATE ON courses BEGIN
        INSERT INTO courses_fts(courses_fts, rowid, name, description)
        VALUES ('delete', old.id, old.name, old.description);
        INSERT INTO courses_fts(rowid, name, description)
        VALUES (new.id, new.name, new.description);
    END
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS localized_catalog_fts
    USING fts5(item_type, item_id UNINDEXED, language_code, title, body)
    """,
)


async def create_schema(database: Database, settings: Settings) -> None:
    """Create ORM tables and, on SQLite, the FTS5 search table + sync triggers."""
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.is_sqlite:
            await _apply_sqlite_column_patches(conn)
            for statement in _FTS_STATEMENTS:
                await conn.execute(text(statement))
