"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON_DEFAULT = sa.text("'{}'")

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


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _extra() -> sa.Column:
    return sa.Column("extra", sa.JSON(), server_default=_JSON_DEFAULT, nullable=False)


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_categories_name", "categories", ["name"])

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("link", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_courses_name", "courses", ["name"])
    op.create_index("ix_courses_category_id", "courses", ["category_id"])
    op.create_index("ix_courses_is_active", "courses", ["is_active"])

    op.create_table(
        "bot_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_bot_users_telegram_id", "bot_users", ["telegram_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_user_id", sa.Integer(), sa.ForeignKey("bot_users.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("payment_reference", sa.String(), nullable=True, unique=True),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_orders_bot_user_id", "orders", ["bot_user_id"])
    op.create_index("ix_orders_course_id", "orders", ["course_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _extra(),
        *_timestamps(),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"])

    op.create_table(
        "bot_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_token", sa.String(), nullable=False, server_default=""),
        sa.Column("backend_url", sa.String(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _extra(),
        *_timestamps(),
    )

    op.create_table(
        "payment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False, server_default="simulated"),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("secret_key", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _extra(),
        *_timestamps(),
    )

    if op.get_bind().dialect.name == "sqlite":
        for statement in _FTS_STATEMENTS:
            op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS courses_au")
        op.execute("DROP TRIGGER IF EXISTS courses_ad")
        op.execute("DROP TRIGGER IF EXISTS courses_ai")
        op.execute("DROP TABLE IF EXISTS courses_fts")
    op.drop_table("payment_settings")
    op.drop_table("bot_settings")
    op.drop_table("admin_users")
    op.drop_table("orders")
    op.drop_table("bot_users")
    op.drop_table("courses")
    op.drop_table("categories")
