from sqlalchemy import Column, Connection, inspect, text

from app.core.config import Settings
from app.core.database import Database
from app.infrastructure.db import models  # noqa: F401  (register models on Base)
from app.infrastructure.db.base import Base


def _column_ddl(column: Column, dialect: object) -> str:
    """ALTER TABLE fragment for a column the models declare and the database lacks.

    ponytail: a NOT NULL column without a server_default is added nullable, because there is
    no value to backfill rows with; alembic owns that migration.
    """
    parts = [column.name, column.type.compile(dialect)]  # type: ignore[arg-type]
    default = column.server_default
    argument = getattr(default, "arg", None)
    if argument is not None:
        parts.append(f"DEFAULT {getattr(argument, 'text', argument)}")
        if not column.nullable:
            parts.append("NOT NULL")
    return " ".join(parts)


def _add_missing_columns(conn: Connection) -> None:
    """create_all creates missing tables but never adds a column to an existing one.

    Reads the columns off the models, so a database that drifted (or was built by create_all
    before a migration landed) catches up without a hand-written patch list.
    """
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {_column_ddl(column, conn.dialect)}"
            print(f"  {ddl}")
            conn.exec_driver_sql(ddl)


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
    """Bring the database up to the models: tables, drifted columns, SQLite FTS5 objects."""
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
        if settings.is_sqlite:
            for statement in _FTS_STATEMENTS:
                await conn.execute(text(statement))


if __name__ == "__main__":  # deploy bootstrap for a database alembic does not track yet
    import asyncio

    from app.core.config import get_settings

    async def _main() -> None:
        settings = get_settings()
        database = Database(settings)
        try:
            await create_schema(database, settings)
        finally:
            await database.dispose()
        print(f"OK  schema matches the models ({'sqlite' if settings.is_sqlite else 'postgres'})")

    asyncio.run(_main())
