"""multilingual catalog and search

Revision ID: 0002_multilingual_search
Revises: 0001_initial
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_multilingual_search"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON_DEFAULT = sa.text("'{}'")


def _extra() -> sa.Column:
    return sa.Column("extra", sa.JSON(), server_default=_JSON_DEFAULT, nullable=False)


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column("preferred_language", sa.String(), nullable=False, server_default="uk"),
    )
    op.create_index("ix_bot_users_preferred_language", "bot_users", ["preferred_language"])

    op.create_table(
        "supported_languages",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("native_name", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _extra(),
    )
    op.create_index("ix_supported_languages_is_default", "supported_languages", ["is_default"])
    op.create_index("ix_supported_languages_is_active", "supported_languages", ["is_active"])

    op.create_table(
        "category_translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column(
            "language_code", sa.String(), sa.ForeignKey("supported_languages.code"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        _extra(),
        sa.UniqueConstraint("category_id", "language_code"),
    )
    op.create_index(
        "ix_category_translations_category_id", "category_translations", ["category_id"]
    )
    op.create_index(
        "ix_category_translations_language_code", "category_translations", ["language_code"]
    )
    op.create_index("ix_category_translations_name", "category_translations", ["name"])

    op.create_table(
        "course_translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column(
            "language_code", sa.String(), sa.ForeignKey("supported_languages.code"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        _extra(),
        sa.UniqueConstraint("course_id", "language_code"),
    )
    op.create_index("ix_course_translations_course_id", "course_translations", ["course_id"])
    op.create_index(
        "ix_course_translations_language_code", "course_translations", ["language_code"]
    )
    op.create_index("ix_course_translations_name", "course_translations", ["name"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS localized_catalog_fts
            USING fts5(item_type, item_id UNINDEXED, language_code, title, body)
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TABLE IF EXISTS localized_catalog_fts")
    op.drop_table("course_translations")
    op.drop_table("category_translations")
    op.drop_table("supported_languages")
    op.drop_index("ix_bot_users_preferred_language", table_name="bot_users")
    op.drop_column("bot_users", "preferred_language")
