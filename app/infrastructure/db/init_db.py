from sqlalchemy import text

from app.core.config import Settings
from app.core.database import Database
from app.infrastructure.db.base import Base
from app.infrastructure.db import models  # noqa: F401  (register models on Base)

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
)


async def create_schema(database: Database, settings: Settings) -> None:
    """Create ORM tables and, on SQLite, the FTS5 search table + sync triggers."""
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.is_sqlite:
            for statement in _FTS_STATEMENTS:
                await conn.execute(text(statement))
